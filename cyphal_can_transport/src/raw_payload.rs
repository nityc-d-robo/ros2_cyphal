use canadensis_encoding::{DataType, Message, Serialize, WriteCursor};

pub struct RawPayload {
    pub data: Vec<u8>,
}

impl DataType for RawPayload {
    const EXTENT_BYTES: Option<u32> = None;
}

impl Message for RawPayload {}

impl Serialize for RawPayload {
    fn size_bits(&self) -> usize {
        self.data.len() * 8
    }

    fn serialize(&self, cursor: &mut WriteCursor<'_>) {
        // WriteCursorの内部バッファに直接バイト列を書き込む
        cursor.write_aligned_bytes(&self.data);
    }
}
