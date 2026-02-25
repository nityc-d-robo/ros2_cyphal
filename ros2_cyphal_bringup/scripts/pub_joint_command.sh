#!/usr/bin/env bash
# joint_position_controller (ForwardCommandController) へ position コマンドを送る
# → cyphal_system_hardware の write() が subject_id=201 に PlanarTs フレームを送出する
# → recv_cyphal_planar_ts.sh で yakut 側から確認できる
#
# 使い方:
#   ./pub_joint_command.sh [position_rad] [rate_hz] [count]
#
# 例:
#   ./pub_joint_command.sh 1.57          # 1.57 rad を 10 Hz で送り続ける
#   ./pub_joint_command.sh 1.57 5 20     # 1.57 rad を 5 Hz で 20 回送る
#   ./pub_joint_command.sh               # デフォルト: 0.0 rad を 10 Hz で送り続ける

set -uo pipefail

POSITION="${1:-0.0}"
RATE="${2:-10}"
COUNT="${3:-}"

echo "============================================================"
echo "  ros2 topic pub: /joint_position_controller/commands"
echo "  joint1 position コマンド: ${POSITION} rad @ ${RATE} Hz"
echo "  → cyphal_system_hardware write() → subject_id=201 (PlanarTs)"
echo "============================================================"
echo ""

COUNT_OPT="--once"
if [[ -n "${COUNT}" ]]; then
    COUNT_OPT="-t ${COUNT}"
else
    COUNT_OPT="-r ${RATE}"
fi

# shellcheck disable=SC2086
ros2 topic pub \
    ${COUNT_OPT} \
    /joint_position_controller/commands \
    std_msgs/msg/Float64MultiArray \
    "{data: [${POSITION}]}"
