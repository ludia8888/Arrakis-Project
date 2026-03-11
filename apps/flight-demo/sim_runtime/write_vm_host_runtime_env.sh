#!/usr/bin/env bash
set -euo pipefail

SIM_ROOT="$(cd "$(dirname "$0")" && pwd)"
RUNTIME_ENV="$SIM_ROOT/runtime.env"

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <vm-ip> [mavlink-port]" >&2
  exit 1
fi

VM_IP="$1"
MAVLINK_PORT="${2:-14551}"

cat >"$RUNTIME_ENV" <<EOF
ARRAKIS_ARDUPILOT_DIR=${HOME}/Developer/ardupilot
ARRAKIS_ARDUPILOT_VEHICLE=ArduPlane
ARRAKIS_ARDUPILOT_FRAME=quadplane
ARRAKIS_ARDUPILOT_MODEL=
ARRAKIS_ARDUPILOT_MAP=1
ARRAKIS_ARDUPILOT_CONSOLE=1
ARRAKIS_ARDUPILOT_WIPE=1
ARRAKIS_ARDUPILOT_OUT=10.0.2.2:${MAVLINK_PORT}
ARRAKIS_MAVPROXY_ARGS="--daemon --non-interactive --nowait"
ARRAKIS_ARDUPILOT_CONNECTION=udp:0.0.0.0:${MAVLINK_PORT}
ARRAKIS_VTOL_LANDING_APPROACH_MIN_M=140
ARRAKIS_ARDUPILOT_VIDEO_SOURCE=
ARRAKIS_FLIGHTGEAR_SCRIPT=${HOME}/Developer/ardupilot/Tools/autotest/fg_plane_view.sh
ARRAKIS_FLIGHTGEAR_BIN=/Applications/FlightGear.app/Contents/MacOS/FlightGear

# Experimental Gazebo path only:
# ARRAKIS_GZ_VERSION=harmonic
# ARRAKIS_ARDUPILOT_GAZEBO_DIR=${HOME}/Developer/ardupilot_gazebo
# ARRAKIS_GZ_WORLD=zephyr_runway.sdf
# ARRAKIS_GZ_VERBOSE=4
# ARRAKIS_GZ_CAMERA_ENABLE_TOPIC=
EOF

echo "[sim-runtime] wrote $RUNTIME_ENV"
echo "[sim-runtime] guest should forward MAVLink to host-reachable address 10.0.2.2:${MAVLINK_PORT}"
echo "[sim-runtime] ARRAKIS_ARDUPILOT_CONNECTION=udp:0.0.0.0:${MAVLINK_PORT}"
echo "[sim-runtime] ARRAKIS_ARDUPILOT_VIDEO_SOURCE=<empty>"
echo "[sim-runtime] note: vm ip ${VM_IP} is not used as the host bind address"
