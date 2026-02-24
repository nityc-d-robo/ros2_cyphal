cmake_minimum_required(VERSION 3.8)
project(ros2_cyphal_hardware)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# ==============================================================================
# 依存パッケージの検索
# ==============================================================================
find_package(ament_cmake REQUIRED)
find_package(hardware_interface REQUIRED)
find_package(pluginlib REQUIRED)
find_package(rclcpp REQUIRED)
find_package(cyphal_interfaces REQUIRED)      # nunavutのCヘッダを提供

find_package(Python3 REQUIRED)

# ==============================================================================
# Corrosion (Rust統合) のセットアップ
# ==============================================================================
include(FetchContent)
FetchContent_Declare(
    Corrosion
    GIT_REPOSITORY https://github.com/corrosion-rs/corrosion.git
    GIT_TAG v0.6.1 # 適宜最新バージョンに
)
FetchContent_MakeAvailable(Corrosion)

# Rust パッケージ (cyphal_can_transport) を CMake のターゲットとしてインポート
corrosion_import_crate(MANIFEST_PATH ${CMAKE_CURRENT_SOURCE_DIR}/../cyphal_can_transport/Cargo.toml)

# CXX ブリッジ生成ヘッダ (lib.rs.h, rust/cxx.h) を CMake ターゲットとして公開
corrosion_add_cxxbridge(cyphal_can_transport_cxxbridge
    CRATE cyphal_can_transport
    FILES lib.rs    # Corrosion が manifest_dir/src/ を自動で付加するので src/ は不要
)

# cxxbridge が生成する lib.cpp は cyphal_callback.hpp をインクルードするため
# cyphal_can_transport の include ディレクトリを追加する
target_include_directories(cyphal_can_transport_cxxbridge PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/../cyphal_can_transport/include
)

# 共有ライブラリ (ros2_cyphal_hardware.so) にリンクするために -fPIC が必要
set_target_properties(cyphal_can_transport_cxxbridge PROPERTIES POSITION_INDEPENDENT_CODE ON)

# ==============================================================================
# †メタプログラミング†: JointRouter の自動生成
# ==============================================================================
set(GENERATED_BASE_DIR "${CMAKE_CURRENT_BINARY_DIR}/generated")
set(JOINT_ROUTER_HPP "${GENERATED_BASE_DIR}/joint_router.hpp")

add_custom_command(
  OUTPUT "${JOINT_ROUTER_HPP}"
  COMMAND ${CMAKE_COMMAND} -E make_directory "${GENERATED_BASE_DIR}"
  COMMAND Python3::Interpreter "${CMAKE_CURRENT_SOURCE_DIR}/scripts/generate_joint_router.py"
          --xacro "${CMAKE_CURRENT_SOURCE_DIR}/urdf/robot.xacro"
          --template-dir "${CMAKE_CURRENT_SOURCE_DIR}/scripts/templates"
          --output "${JOINT_ROUTER_HPP}"
  DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/urdf/robot.xacro"
          "${CMAKE_CURRENT_SOURCE_DIR}/scripts/templates/joint_router.hpp.jinja2"
          "${CMAKE_CURRENT_SOURCE_DIR}/scripts/generate_joint_router.py"
  COMMENT "† Generating JointRouter from URDF... †"
)

# ==============================================================================
# プラグインライブラリのビルド
# ==============================================================================
add_library(${PROJECT_NAME} SHARED
  src/cyphal_system_hardware.cpp
  "${JOINT_ROUTER_HPP}"
)

# 生成されたヘッダのパスを通す
target_include_directories(${PROJECT_NAME} PRIVATE
  include
  "${GENERATED_BASE_DIR}"
  ${CMAKE_CURRENT_SOURCE_DIR}/../cyphal_can_transport/include
)

# 依存関係のリンク
ament_target_dependencies(${PROJECT_NAME}
  hardware_interface
  pluginlib
  rclcpp
  cyphal_interfaces
)

# Rust ライブラリ + CXX ブリッジヘッダをリンク
target_link_libraries(${PROJECT_NAME}
    cyphal_can_transport
    cyphal_can_transport_cxxbridge
)

# ==============================================================================
# pluginlib 用のエクスポート
# ==============================================================================
install(
  FILES cyphal_hardware.xml
  DESTINATION share/${PROJECT_NAME}
)

pluginlib_export_plugin_description_file(hardware_interface cyphal_hardware.xml)

# ==============================================================================
# インストール設定
# ==============================================================================
install(
  TARGETS ${PROJECT_NAME}
  DESTINATION lib
)

install(
  DIRECTORY urdf config
  DESTINATION share/${PROJECT_NAME}
)

ament_export_include_directories(include)
ament_export_libraries(${PROJECT_NAME})
ament_package()
