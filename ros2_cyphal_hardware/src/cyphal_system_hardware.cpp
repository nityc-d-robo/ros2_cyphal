#include <hardware_interface/system_interface.hpp>
#include <hardware_interface/types/hardware_interface_type_values.hpp>
#include <hardware_interface/types/hardware_component_interface_params.hpp>
#include <rclcpp/rclcpp.hpp>
#include <pluginlib/class_list_macros.hpp>
#include <optional>
#include <map>
#include <vector>

// 1. 自動生成された「そのロボット専用」のルーター
#include "joint_router.hpp"

// 2. Rust側の通信土管（FFI）: corrosion_add_cxxbridge が生成するヘッダ
#include "cyphal_can_transport_cxxbridge/lib.h"

namespace ros2_cyphal_hardware {

class CyphalSystemHardware : public hardware_interface::SystemInterface {
private:
    // Rustのノード管理 (rust::Box はデフォルトコンストラクタなし → optional でラップ)
    std::optional<rust::Box<ros2_cyphal::transport::CyphalNode>> cyphal_node_;

    // ros2_control 用の内部バッファ
    std::vector<double> hw_positions_;
    std::vector<double> hw_velocities_;
    std::vector<double> hw_commands_;

    // TX登録済みの (subject_id, joint_index) ペア
    // URDFの <param name="tx_subject_id"> が存在する関節のみ追加される
    std::vector<std::pair<uint16_t, size_t>> tx_subjects_;

public:
    hardware_interface::CallbackReturn on_init(
        const hardware_interface::HardwareComponentInterfaceParams & params) override {
        if (hardware_interface::SystemInterface::on_init(params) != hardware_interface::CallbackReturn::SUCCESS) {
            return hardware_interface::CallbackReturn::ERROR;
        }

        // 関節数に合わせてメモリ確保
        size_t joint_count = info_.joints.size();
        hw_positions_.assign(joint_count, 0.0);
        hw_velocities_.assign(joint_count, 0.0);
        hw_commands_.assign(joint_count, 0.0);

        // Rust土管の初期化
        std::string can_if = info_.hardware_parameters.at("can_interface");
        uint8_t node_id = static_cast<uint8_t>(std::stoi(info_.hardware_parameters.at("node_id")));
        cyphal_node_ = ros2_cyphal::transport::create_cyphal_node(can_if, node_id);

        // グローバルポインタに自身を登録（Rustからの受信コールバック用）
        g_current_hardware_interface = this;

        // =========================================================
        // JointRouter（コード生成済み）から subject_id を取得して登録
        // xacro の <cyphal> タグ情報はビルド時に JointRouter へ焼き込み済み
        // =========================================================

        // --- RX: <cyphal><state subject_id="..."> の購読登録 ---
        // canadensis は subscribe_subject を呼ばないと receive() にフレームが届かない
        for (uint16_t rx_id : JointRouter::get_rx_subject_ids()) {
            // payload_size_max: DSDLタイプの ExtentBytes。64 は小型メッセージに十分
            (*cyphal_node_)->subscribe_subject(rx_id, 64);
        }

        // --- TX: <cyphal><command subject_id="..."> の送信登録 ---
        // canadensis は start_publishing_subject を呼ばないと publish() が NotPublishing エラーになる
        for (uint16_t tx_id : JointRouter::get_tx_subject_ids()) {
            (*cyphal_node_)->start_publishing_subject(tx_id);
            tx_subjects_.emplace_back(tx_id, 0);  // joint_idx はルーター内に焼き込み済みのため未使用
        }

        return hardware_interface::CallbackReturn::SUCCESS;
    }

    // ROS 2 Control へのインターフェース公開
    std::vector<hardware_interface::StateInterface> export_state_interfaces() override {
        std::vector<hardware_interface::StateInterface> interfaces;
        for (size_t i = 0; i < info_.joints.size(); i++) {
            interfaces.emplace_back(info_.joints[i].name, hardware_interface::HW_IF_POSITION, &hw_positions_[i]);
            interfaces.emplace_back(info_.joints[i].name, hardware_interface::HW_IF_VELOCITY, &hw_velocities_[i]);
        }
        return interfaces;
    }

    std::vector<hardware_interface::CommandInterface> export_command_interfaces() override {
        std::vector<hardware_interface::CommandInterface> interfaces;
        for (size_t i = 0; i < info_.joints.size(); i++) {
            interfaces.emplace_back(info_.joints[i].name, hardware_interface::HW_IF_POSITION, &hw_commands_[i]);
        }
        return interfaces;
    }

    // =========================================================================
    // READ: Cyphal -> ros2_control
    // =========================================================================
    // step() 内で receive() → BridgeHandler::handle_message() →
    // ffi::on_cyphal_message_received() → handle_rx() → JointRouter::route_rx()
    // という流れで hw_positions_ / hw_velocities_ が更新される
    hardware_interface::return_type read(const rclcpp::Time &, const rclcpp::Duration &) override {
        (*cyphal_node_)->step();
        return hardware_interface::return_type::OK;
    }

    // =========================================================================
    // WRITE: ros2_control -> Cyphal
    // =========================================================================
    // JointRouter::route_tx() で DSDL シリアライズして publish する
    hardware_interface::return_type write(const rclcpp::Time &, const rclcpp::Duration &) override {
        std::map<std::string, double*> interfaces;
        interfaces["position"] = hw_commands_.data();
        for (const auto & [subject_id, joint_idx] : tx_subjects_) {
            (void)joint_idx; // joint.index はコード生成時に埋め込み済み
            auto bytes = JointRouter::route_tx(subject_id, interfaces);
            if (!bytes.empty()) {
                (*cyphal_node_)->publish(
                    subject_id,
                    rust::Slice<const uint8_t>(bytes.data(), bytes.size()));
            }
        }
        return hardware_interface::return_type::OK;
    }

    // 受信データを実際に処理する内部メソッド
    void handle_rx(uint16_t id, const uint8_t* payload, size_t size) {
        std::map<std::string, double*> interfaces;
        interfaces["position"] = hw_positions_.data();
        interfaces["velocity"] = hw_velocities_.data();
        JointRouter::route_rx(id, payload, size, interfaces);
    }

    // シングルトン的なインスタンス保持（FFIの制約上必要）
    static CyphalSystemHardware* g_current_hardware_interface;
};

CyphalSystemHardware* CyphalSystemHardware::g_current_hardware_interface = nullptr;

} // namespace ros2_cyphal_hardware

// =============================================================================
// Rust (FFI) から呼ばれるグローバルなコールバック関数
//
// フロー: step() [Rust] → receive() [canadensis] → BridgeHandler::handle_message() [Rust]
//        → ffi::on_cyphal_message_received() [CXX FFI] → ここ [C++]
//        → handle_rx() → JointRouter::route_rx() → hw_positions_[i] 更新
// =============================================================================
namespace ros2_cyphal {
namespace transport {
void on_cyphal_message_received(uint16_t id, rust::Slice<const uint8_t> payload) {
    if (ros2_cyphal_hardware::CyphalSystemHardware::g_current_hardware_interface) {
        ros2_cyphal_hardware::CyphalSystemHardware::g_current_hardware_interface->handle_rx(
            id, payload.data(), payload.size());
    }
}
}
}

PLUGINLIB_EXPORT_CLASS(ros2_cyphal_hardware::CyphalSystemHardware, hardware_interface::SystemInterface)
