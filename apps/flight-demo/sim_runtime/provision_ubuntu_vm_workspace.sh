#!/usr/bin/env bash
set -euo pipefail

: "${ARRAKIS_VM_WORKSPACE:=$HOME/Developer}"
: "${ARRAKIS_VM_ARDUPILOT_DIR:=$ARRAKIS_VM_WORKSPACE/ardupilot}"
mkdir -p "$ARRAKIS_VM_WORKSPACE"

if [[ ! -d "$ARRAKIS_VM_ARDUPILOT_DIR/.git" ]]; then
  git clone --filter=blob:none --recurse-submodules https://github.com/ArduPilot/ardupilot.git "$ARRAKIS_VM_ARDUPILOT_DIR"
else
  echo "[sim-runtime] ardupilot already present at $ARRAKIS_VM_ARDUPILOT_DIR"
fi

python3 -m pip install --user \
  pexpect \
  pymavlink \
  MAVProxy \
  "empy==3.3.4"

cat <<EOF
[sim-runtime] VM workspace provisioned
[sim-runtime] ArduPilot: $ARRAKIS_VM_ARDUPILOT_DIR

Next steps:
1. verify sim_vehicle.py:
   $ARRAKIS_VM_ARDUPILOT_DIR/Tools/autotest/sim_vehicle.py --help | head
2. run QuadPlane SITL:
   /Users/isihyeon/Desktop/Arrakis-Project/apps/flight-demo/sim_runtime/run_ardupilot_quadplane.sh
EOF
