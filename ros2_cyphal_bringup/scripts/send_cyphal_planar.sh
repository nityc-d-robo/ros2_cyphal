#!/usr/bin/env bash
# subject_id 101: reg.udral.physics.kinematics.rotation.Planar.0.1
# ros2_cyphal_hardware の joint1 RX チャンネルへ position/velocity を送る
#
# 使い方:
#   ./send_cyphal_planar.sh [position_rad] [velocity_rad_per_sec] [period_sec] [count]
#
# 例:
#   ./send_cyphal_planar.sh 1.57 0.0 0.1 10   # 1.57 rad を 0.1秒周期で10回送る
#   ./send_cyphal_planar.sh                    # デフォルト: sin波、0.05秒周期、無限ループ

set -uo pipefail

POSITION="${1:-}"
VELOCITY="${2:-0.0}"
PERIOD="${3:-0.05}"
COUNT="${4:-}"

# CAN インターフェース設定
export UAVCAN__CAN__IFACE="socketcan:vcan0"
# CAN FD MTU=64 を明示
export UAVCAN__CAN__MTU=64
# yakut が使うノードID（環境変数未設定なら 42 を使用）
export UAVCAN__NODE__ID="${UAVCAN__NODE__ID:-42}"

echo "使用インターフェース: ${UAVCAN__CAN__IFACE}  ノードID: ${UAVCAN__NODE__ID}"

COUNT_OPT=""
if [[ -n "${COUNT}" ]]; then
    COUNT_OPT="-N ${COUNT}"
fi

if [[ -n "${POSITION}" ]]; then
    # 固定値モード: 指定した position / velocity を送り続ける
    echo "固定値モード: position=${POSITION} rad, velocity=${VELOCITY} rad/s, period=${PERIOD}s"
    # shellcheck disable=SC2086
    yakut pub \
        -T "${PERIOD}" \
        ${COUNT_OPT} \
        "101:reg.udral.physics.kinematics.rotation.Planar.0.1" \
        "{angular_position: {radian: ${POSITION}}, angular_velocity: {radian_per_second: ${VELOCITY}}}"
else
    # sin波モード: 1 Hz, 振幅 1.0 rad のサイン波を送り続ける
    echo "sin波モード: 1 Hz, 振幅 1.0 rad, period=${PERIOD}s (Ctrl+C で停止)"
    # shellcheck disable=SC2086
    yakut pub \
        -T "${PERIOD}" \
        ${COUNT_OPT} \
        "101:reg.udral.physics.kinematics.rotation.Planar.0.1" \
        "{angular_position: {radian: !$ 'sin(t * pi * 2)'}, angular_velocity: {radian_per_second: !$ 'cos(t * pi * 2) * pi * 2'}}"
fi
