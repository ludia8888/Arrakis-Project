#!/usr/bin/env bash
set -euo pipefail

SIM_ROOT="$(cd "$(dirname "$0")" && pwd)"
RUNTIME_ENV="$SIM_ROOT/runtime.env"

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <vm-ip> [mavlink-port] [video-port]" >&2
  exit 1
fi

VM_IP="$1"
MAVLINK_PORT="${2:-14550}"
VIDEO_PORT="${3:-5600}"

cat >"$RUNTIME_ENV" <<EOF
ARRAKIS_GZ_VERSION=harmonic
ARRAKIS_ARDUPILOT_DIR=\$HOME/Developer/ardupilot
ARRAKIS_ARDUPILOT_GAZEBO_DIR=\$HOME/Developer/ardupilot_gazebo
ARRAKIS_GZ_WORLD=zephyr_runway.sdf
ARRAKIS_GZ_VERBOSE=4
ARRAKIS_GZ_CAMERA_ENABLE_TOPIC=
ARRAKIS_ARDUPILOT_VEHICLE=ArduPlane
ARRAKIS_ARDUPILOT_FRAME=gazebo-zephyr
ARRAKIS_ARDUPILOT_MODEL=JSON
ARRAKIS_ARDUPILOT_MAP=1
ARRAKIS_ARDUPILOT_CONSOLE=1
ARRAKIS_ARDUPILOT_CONNECTION=udp:${VM_IP}:${MAVLINK_PORT}
ARRAKIS_ARDUPILOT_VIDEO_SOURCE=udp://${VM_IP}:${VIDEO_PORT}
EOF

echo "[sim-runtime] wrote $RUNTIME_ENV"
echo "[sim-runtime] ARRAKIS_ARDUPILOT_CONNECTION=udp:${VM_IP}:${MAVLINK_PORT}"
echo "[sim-runtime] ARRAKIS_ARDUPILOT_VIDEO_SOURCE=udp://${VM_IP}:${VIDEO_PORT}"
