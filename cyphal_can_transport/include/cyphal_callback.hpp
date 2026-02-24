#pragma once
#include "rust/cxx.h"
#include <cstdint>

// CXX ブリッジの型チェック用: Rust 側が呼ぶ C++ コールバックの宣言
namespace ros2_cyphal {
namespace transport {
void on_cyphal_message_received(std::uint16_t subject_id,
                                ::rust::Slice<const std::uint8_t> payload);
} // namespace transport
} // namespace ros2_cyphal
