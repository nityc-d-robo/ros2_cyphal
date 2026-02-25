#!/usr/bin/env bash
# subject_id 201: reg.udral.physics.kinematics.rotation.PlanarTs.0.1
# cyphal_system_hardware (joint1) が TX するコマンドフレームをモニタリングする
#
# 使い方:
#   ./recv_cyphal_planar_ts.sh [count]
#
# 例:
#   ./recv_cyphal_planar_ts.sh        # 無限に受信し続ける (Ctrl+C で停止)
#   ./recv_cyphal_planar_ts.sh 20     # 20フレーム受信して終了

set -uo pipefail

COUNT="${1:-}"

# CAN インターフェース設定
export UAVCAN__CAN__IFACE="socketcan:vcan0"
# CAN FD MTU=64 を明示 (デフォルトは MTU=8 のクラシカル CAN になり Rust 側と不一致になる)
export UAVCAN__CAN__MTU=64
# yakut が使うノードID（環境変数未設定なら 42 を使用）
export UAVCAN__NODE__ID="${UAVCAN__NODE__ID:-42}"

echo "============================================================"
echo "  Cyphal TX モニタ: reg.udral.physics.kinematics.rotation.PlanarTs.0.1"
echo "  subject_id : 201"
echo "  送信元     : cyphal_system_hardware (node_id=123, joint1 command)"
echo "  インターフェース: ${UAVCAN__CAN__IFACE}  ノードID: ${UAVCAN__NODE__ID}"
echo "============================================================"

COUNT_OPT=""
if [[ -n "${COUNT}" ]]; then
    COUNT_OPT="-N ${COUNT}"
    echo "受信予定フレーム数: ${COUNT}"
else
    echo "受信中... (Ctrl+C で停止)"
fi

echo ""

# shellcheck disable=SC2086
yakut sub \
    ${COUNT_OPT} \
    "201:reg.udral.physics.kinematics.rotation.PlanarTs.0.1"
