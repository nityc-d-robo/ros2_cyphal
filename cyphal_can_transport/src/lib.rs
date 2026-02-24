use std::convert::TryFrom;
use std::io::ErrorKind;
use std::time::Instant;

use socketcan::CanFdSocket;
use socketcan::Socket;

use canadensis::core::SubjectId;
use canadensis::node::{BasicNode, CoreNode};
use canadensis::requester::TransferIdFixedMap;
use canadensis::{Node, TransferHandler};
use canadensis_can::queue::{ArrayQueue, SingleQueueDriver};
use canadensis_can::{
    CanNodeId, CanReceiver, CanTransmitter, CanTransport, Error as CanError, Mtu,
};
use canadensis_data_types::uavcan::node::get_info_1_0::GetInfoResponse;
use canadensis_data_types::uavcan::node::version_1_0::Version;
use canadensis_linux::{LinuxCan, SystemClock};

mod raw_payload;

#[cxx::bridge(namespace = "ros2_cyphal::transport")]
mod ffi {
    // RustからC++の関数を呼ぶための定義
    unsafe extern "C++" {
        // 宣言ヘッダを CXX ブリッジのコンパイルスコープに取り込む
        include!("cyphal_callback.hpp");

        // C++側で実装するコールバック関数
        // rust::Slice<const uint8_t> として C++ 側に渡されます
        fn on_cyphal_message_received(subject_id: u16, payload: &[u8]);
    }

    extern "Rust" {
        type CyphalNode;

        // ノードの初期化
        fn create_cyphal_node(interface: &str, node_id: u8) -> Result<Box<CyphalNode>>;

        // subject_id の受信を購読登録する (receive() が届くために必須)
        fn subscribe_subject(
            self: &mut CyphalNode,
            subject_id: u16,
            payload_size_max: usize,
        ) -> Result<()>;

        // subject_id への送信を開始登録する (publish() の前に必須)
        fn start_publishing_subject(self: &mut CyphalNode, subject_id: u16) -> Result<()>;

        // バイト列の送信 (Thin FFI)
        fn publish(self: &mut CyphalNode, subject_id: u16, payload: &[u8]) -> Result<()>;

        // ROS 2のイベントループ (spin) から定期的に呼ぶための関数
        fn step(self: &mut CyphalNode) -> Result<()>;
    }
}

// ---------------------------------------------------------------------------
// 複雑なジェネリクスの型エイリアス
// ---------------------------------------------------------------------------
const QUEUE_CAPACITY: usize = 1210;
const TRANSFER_IDS: usize = 32; // サポートする送信トピック数
const PUBLISHERS: usize = 32;
const REQUESTERS: usize = 8;

type Queue = SingleQueueDriver<SystemClock, ArrayQueue<QUEUE_CAPACITY>, LinuxCan<CanFdSocket>>;

type MyCoreNode = CoreNode<
    SystemClock,
    CanTransmitter<SystemClock, Queue>,
    CanReceiver<SystemClock, Queue>,
    TransferIdFixedMap<CanTransport, TRANSFER_IDS>,
    Queue,
    PUBLISHERS,
    REQUESTERS,
>;

pub struct CyphalNode {
    node: BasicNode<MyCoreNode>, // canadensisのノード実体
    handler: BridgeHandler,       // 受信コールバック用ハンドラ
    start_time: Instant,
    prev_seconds: u64,
}

// ---------------------------------------------------------------------------
// 実装
// ---------------------------------------------------------------------------

impl CyphalNode {
    /// subject_id の受信を購読登録する
    /// canadensis は subscribe_message を呼ばないと receive() にフレームが届かない
    pub fn subscribe_subject(
        &mut self,
        subject_id: u16,
        payload_size_max: usize,
    ) -> Result<(), std::io::Error> {
        let subj = SubjectId::try_from(subject_id).map_err(|_| {
            std::io::Error::new(std::io::ErrorKind::InvalidInput, "Invalid Subject ID")
        })?;
        use canadensis::core::time::milliseconds;
        self.node
            .subscribe_message(subj, payload_size_max, milliseconds(1000))
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, format!("{:?}", e)))
    }

    /// subject_id への送信を開始登録する
    /// canadensis は start_publishing を呼ばないと publish() が NotPublishing エラーになる
    pub fn start_publishing_subject(&mut self, subject_id: u16) -> Result<(), std::io::Error> {
        let subj = SubjectId::try_from(subject_id).map_err(|_| {
            std::io::Error::new(std::io::ErrorKind::InvalidInput, "Invalid Subject ID")
        })?;
        use canadensis::core::time::milliseconds;
        use canadensis::core::Priority;
        self.node
            .start_publishing(subj, milliseconds(1000), Priority::Nominal.into())
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, format!("{:?}", e)))
    }

    /// C++から呼ばれる送信関数 (Thin FFI)
    pub fn publish(&mut self, subject_id: u16, payload: &[u8]) -> Result<(), std::io::Error> {
        let subj = SubjectId::try_from(subject_id).map_err(|_| {
            std::io::Error::new(std::io::ErrorKind::InvalidInput, "Invalid Subject ID")
        })?;

        let message = raw_payload::RawPayload {
            data: payload.to_vec(),
        };
        let _ = self.node.publish(subj, &message);
        Ok(())
    }

    /// ROS 2のメインループから定期的に（例：1msごと）呼ばれる関数
    pub fn step(&mut self) -> Result<(), std::io::Error> {
        // 1. CANバスからの受信とコールバック処理
        match self.node.receive(&mut self.handler) {
            Ok(_) => {}
            Err(CanError::Driver(e)) if e.kind() == ErrorKind::WouldBlock => {} // データ無しは無視
            Err(e) => eprintln!("[CyphalNode] Receive error: {:?}", e),
        }

        // 2. 定期タスク (Heartbeatの送信など) の処理
        let seconds = std::time::Instant::now()
            .duration_since(self.start_time)
            .as_secs();

        if seconds != self.prev_seconds {
            self.prev_seconds = seconds;
            // 1秒に1回、Heartbeat等をパブリッシュ
            let _ = self.node.run_per_second_tasks();
        }

        // 3. 送信キューに溜まったデータを実際にCANインターフェースに書き込む
        let _ = self.node.flush();

        Ok(())
    }
}

// ---------------------------------------------------------------------------
// 初期化ファクトリ
// ---------------------------------------------------------------------------

pub fn create_cyphal_node(interface: &str, node_id: u8) -> Result<Box<CyphalNode>, std::io::Error> {
    let node_id = CanNodeId::try_from(node_id).unwrap();

    // SocketCANのセットアップ (ノンブロッキングに設定)
    let can = CanFdSocket::open(interface).unwrap();
    can.set_nonblocking(true).unwrap(); // 非同期で処理するために必須
    let can_linux = LinuxCan::new(can);

    let node_info = GetInfoResponse {
        protocol_version: Version { major: 1, minor: 0 },
        hardware_version: Version { major: 0, minor: 0 },
        software_version: Version { major: 0, minor: 1 },
        software_vcs_revision_id: 0,
        unique_id: rand::random(),
        name: heapless::Vec::from_slice(b"ros2_cyphal_bridge").unwrap(),
        software_image_crc: heapless::Vec::new(),
        certificate_of_authenticity: Default::default(),
    };

    let queue_driver = SingleQueueDriver::new(ArrayQueue::new(), can_linux);
    let transmitter = CanTransmitter::new(Mtu::CanFd64);
    let receiver = CanReceiver::new(node_id);

    let core_node = CoreNode::new(
        SystemClock::new(),
        node_id,
        transmitter,
        receiver,
        queue_driver,
    );

    let node = BasicNode::new(core_node, node_info).unwrap();

    Ok(Box::new(CyphalNode {
        node,
        handler: BridgeHandler,
        start_time: Instant::now(),
        prev_seconds: 0,
    }))
}

// ---------------------------------------------------------------------------
// 受信ハンドラ
// ---------------------------------------------------------------------------
pub struct BridgeHandler;

impl<T: canadensis::core::transport::Transport> TransferHandler<T> for BridgeHandler {
    fn handle_message<N>(
        &mut self,
        _node: &mut N,
        transfer: &canadensis::core::transfer::MessageTransfer<Vec<u8>, T>,
    ) -> bool
    where
        N: Node<Transport = T>,
    {
        // 1. Subject ID を u16 に変換
        let subject_id = u16::from(transfer.header.subject);
        // 2. FFI経由で C++ のコールバック関数を叩く！
        ffi::on_cyphal_message_received(subject_id, &transfer.payload);
        // メッセージをメモリに保持し続ける必要はないので false を返す
        false
    }
    // (handle_request, handle_response も必要に応じて同様に ffi 関数を呼ぶように実装できます)
}
