#!/usr/bin/env bash
set -euo pipefail

SIM_ROOT="$(cd "$(dirname "$0")" && pwd)"
RUNTIME_ENV="$SIM_ROOT/runtime.env"
HOST_IP="${1:-10.0.2.2}"
MAVLINK_PORT="${2:-14551}"

cat >"$RUNTIME_ENV" <<EOF
ARRAKIS_ARDUPILOT_DIR=${HOME}/Developer/ardupilot
ARRAKIS_ARDUPILOT_VEHICLE=ArduPlane
ARRAKIS_ARDUPILOT_FRAME=quadplane
ARRAKIS_ARDUPILOT_MODEL=
ARRAKIS_ARDUPILOT_DEFAULTS=${HOME}/sim_runtime/params/quadplane_demo.parm
ARRAKIS_ARDUPILOT_MAP=0
ARRAKIS_ARDUPILOT_CONSOLE=0
ARRAKIS_ARDUPILOT_WIPE=1
ARRAKIS_ARDUPILOT_OUT=${HOST_IP}:${MAVLINK_PORT}
ARRAKIS_MAVPROXY_ARGS="--daemon --non-interactive --nowait"
ARRAKIS_ARDUPILOT_CONNECTION=udp:0.0.0.0:${MAVLINK_PORT}
ARRAKIS_VTOL_LANDING_APPROACH_MIN_M=140
ARRAKIS_ARDUPILOT_VIDEO_SOURCE=
ARRAKIS_FLIGHTGEAR_SCRIPT=${HOME}/Developer/ardupilot/Tools/autotest/fg_plane_view.sh
EOF

echo "[sim-runtime] wrote guest runtime env to $RUNTIME_ENV"
echo "[sim-runtime] guest MAVProxy out: ${HOST_IP}:${MAVLINK_PORT}"
echo "[sim-runtime] guest PATH should include \$HOME/.local/bin for mavproxy.py"
