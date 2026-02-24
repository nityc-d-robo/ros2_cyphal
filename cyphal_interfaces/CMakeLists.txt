cmake_minimum_required(VERSION 3.8)
project(cyphal_interfaces)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(Python3 REQUIRED COMPONENTS Interpreter)

# ==============================================================================
# Python Venv Setup
# ==============================================================================
set(VENV_DIR "${CMAKE_CURRENT_BINARY_DIR}/venv")
set(VENV_PYTHON "${VENV_DIR}/bin/python")

# venvを作成し、requirements.txtをインストールする
add_custom_command(
  OUTPUT "${VENV_DIR}/.installed"
  COMMAND Python3::Interpreter -m venv "${VENV_DIR}"
  COMMAND "${VENV_PYTHON}" -m pip install --upgrade pip
  COMMAND "${VENV_PYTHON}" -m pip install -r "${CMAKE_CURRENT_SOURCE_DIR}/scripts/requirements.txt"
  COMMAND ${CMAKE_COMMAND} -E touch "${VENV_DIR}/.installed"
  DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/scripts/requirements.txt"
  COMMENT "Setting up Python virtual environment and installing nunavut..."
)

# ==============================================================================
# DSDL to C Headers Codegen (nunavut)
# ==============================================================================
set(DSDL_DIR "${CMAKE_CURRENT_SOURCE_DIR}/dsdl/public_regulated_data_types")
set(CODEGEN_OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/generated/cyphal_c")

# Ensure the codegen output directory exists during configuration so that
# ament_export_include_directories() does not warn about a missing path.
file(MAKE_DIRECTORY "${CODEGEN_OUTPUT}")

# CMakeが「生成完了」を判定するための代表ファイルを定義
set(TARGET_HEADER "${CODEGEN_OUTPUT}/uavcan/node/Heartbeat_1_0.hpp")

add_custom_command(
  OUTPUT "${TARGET_HEADER}"
  COMMAND ${CMAKE_COMMAND} -E make_directory "${CODEGEN_OUTPUT}"
  # 1. uavcan 名前空間
  COMMAND "${VENV_PYTHON}" -m nunavut --outdir "${CODEGEN_OUTPUT}" --target-language c "${DSDL_DIR}/uavcan"
  # 2. reg 名前空間 (UDRAL等)
  #    The reg namespace uses types defined in the standard uavcan namespace
  #    so we must tell nunavut where to look for them using --lookup-dir.
  COMMAND "${VENV_PYTHON}" -m nunavut --outdir "${CODEGEN_OUTPUT}" --target-language c  --lookup-dir "${DSDL_DIR}/uavcan" "${DSDL_DIR}/reg"
  # Update dependencies to cover files from both namespaces, ensuring rebuild
  DEPENDS "${VENV_DIR}/.installed"
  DEPENDS "${DSDL_DIR}/uavcan/node/7509.Heartbeat.1.0.dsdl"
  DEPENDS "${DSDL_DIR}/reg/udral/physics/acoustics/Note.0.1.dsdl"
  COMMENT "Generating Cyphal C headers via nunavut..."
)

add_custom_target(generate_cyphal_c_headers ALL DEPENDS "${TARGET_HEADER}")

# ==============================================================================
# ヘッダのエクスポート (他のパッケージから include できるように公開)
# ==============================================================================
ament_export_include_directories("${CODEGEN_OUTPUT}")

install(
  DIRECTORY "${CODEGEN_OUTPUT}/"
  DESTINATION "include/${PROJECT_NAME}"
)

ament_package()
