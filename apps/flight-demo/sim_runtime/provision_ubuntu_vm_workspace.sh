#!/usr/bin/env bash
set -euo pipefail

: "${ARRAKIS_VM_WORKSPACE:=$HOME/Developer}"
: "${ARRAKIS_VM_ARDUPILOT_DIR:=$ARRAKIS_VM_WORKSPACE/ardupilot}"
: "${ARRAKIS_VM_ARDUPILOT_GAZEBO_DIR:=$ARRAKIS_VM_WORKSPACE/ardupilot_gazebo}"

mkdir -p "$ARRAKIS_VM_WORKSPACE"

if [[ ! -d "$ARRAKIS_VM_ARDUPILOT_DIR/.git" ]]; then
  git clone --filter=blob:none --recurse-submodules https://github.com/ArduPilot/ardupilot.git "$ARRAKIS_VM_ARDUPILOT_DIR"
else
  echo "[sim-runtime] ardupilot already present at $ARRAKIS_VM_ARDUPILOT_DIR"
fi

if [[ ! -d "$ARRAKIS_VM_ARDUPILOT_GAZEBO_DIR/.git" ]]; then
  git clone https://github.com/ArduPilot/ardupilot_gazebo.git "$ARRAKIS_VM_ARDUPILOT_GAZEBO_DIR"
else
  echo "[sim-runtime] ardupilot_gazebo already present at $ARRAKIS_VM_ARDUPILOT_GAZEBO_DIR"
fi

python3 -m pip install --user \
  pexpect \
  pymavlink \
  MAVProxy \
  "empy==3.3.4"

cat <<EOF
[sim-runtime] VM workspace provisioned
[sim-runtime] ArduPilot: $ARRAKIS_VM_ARDUPILOT_DIR
[sim-runtime] ardupilot_gazebo: $ARRAKIS_VM_ARDUPILOT_GAZEBO_DIR

Next steps:
1. build the Gazebo plugin:
   cd $ARRAKIS_VM_ARDUPILOT_GAZEBO_DIR
   mkdir -p build && cd build
   cmake .. -DCMAKE_BUILD_TYPE=RelWithDebInfo
   cmake --build . -j\$(nproc)
2. verify sim_vehicle.py:
   $ARRAKIS_VM_ARDUPILOT_DIR/Tools/autotest/sim_vehicle.py --help | head
EOF
