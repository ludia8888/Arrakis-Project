#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cat <<'EOF'
[sim-runtime] Bootstrapping Ubuntu VM runtime for Arrakis flight demo
[sim-runtime] This script targets Ubuntu 22.04/24.04 inside UTM or another local VM.
EOF

sudo apt-get update
sudo apt-get install -y \
  ca-certificates \
  curl \
  gpg \
  lsb-release \
  git \
  build-essential \
  cmake \
  ninja-build \
  ccache \
  pkg-config \
  python3 \
  python3-pip \
  python3-venv \
  python3-dev \
  python3-opencv \
  rapidjson-dev \
  libopencv-dev \
  libgstreamer1.0-dev \
  libgstreamer-plugins-base1.0-dev \
  gstreamer1.0-tools \
  gstreamer1.0-libav \
  gstreamer1.0-plugins-bad \
  gstreamer1.0-plugins-good \
  flightgear || true

cat <<EOF
[sim-runtime] Ubuntu VM bootstrap complete

Next steps inside the VM:
1. Clone ArduPilot:
   git clone --filter=blob:none --recurse-submodules https://github.com/ArduPilot/ardupilot.git \$HOME/Developer/ardupilot
2. Primary runtime path:
   ${SCRIPT_DIR}/run_ardupilot_quadplane.sh
3. Optional FlightGear view-only:
   ${SCRIPT_DIR}/run_flightgear_view.sh
4. Copy ${SCRIPT_DIR}/runtime.env.example to runtime.env on the macOS host and point:
   ARRAKIS_ARDUPILOT_CONNECTION=udp://<vm-ip>:14550
   ARRAKIS_ARDUPILOT_VIDEO_SOURCE=
EOF
