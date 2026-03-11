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
  gstreamer1.0-plugins-good

if [[ ! -f /etc/apt/keyrings/pkgs-osrf-archive-keyring.gpg ]]; then
  sudo mkdir -p /etc/apt/keyrings
  curl -fsSL https://packages.osrfoundation.org/gazebo.gpg | sudo gpg --dearmor -o /etc/apt/keyrings/pkgs-osrf-archive-keyring.gpg
fi

if [[ ! -f /etc/apt/sources.list.d/gazebo-stable.list ]]; then
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/pkgs-osrf-archive-keyring.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" \
    | sudo tee /etc/apt/sources.list.d/gazebo-stable.list >/dev/null
fi

sudo apt-get update
sudo apt-get install -y gz-harmonic

cat <<EOF
[sim-runtime] Ubuntu VM bootstrap complete

Next steps inside the VM:
1. Clone ArduPilot:
   git clone --filter=blob:none --recurse-submodules https://github.com/ArduPilot/ardupilot.git \$HOME/Developer/ardupilot
2. Clone ardupilot_gazebo:
   git clone https://github.com/ArduPilot/ardupilot_gazebo.git \$HOME/Developer/ardupilot_gazebo
3. Build the plugin:
   cd \$HOME/Developer/ardupilot_gazebo
   mkdir -p build && cd build
   cmake .. -DCMAKE_BUILD_TYPE=RelWithDebInfo
   cmake --build . -j$(nproc)
4. Copy ${SCRIPT_DIR}/runtime.env.example to runtime.env on the macOS host and point:
   ARRAKIS_ARDUPILOT_CONNECTION=udp://<vm-ip>:14550
   ARRAKIS_ARDUPILOT_VIDEO_SOURCE=udp://<vm-ip>:5600
EOF
