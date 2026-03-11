#!/bin/bash
set -euo pipefail

SIM_ROOT="$(cd "$(dirname "$0")" && pwd)"

if ! command -v brew >/dev/null 2>&1; then
  echo "[sim-runtime] Homebrew is required but not installed" >&2
  exit 1
fi

if [[ "$(uname -m)" == "arm64" ]] && ! /usr/bin/pgrep oahd >/dev/null 2>&1; then
  echo "[sim-runtime] Rosetta does not appear to be installed. Install it first:" >&2
  echo "  softwareupdate --install-rosetta --agree-to-license" >&2
  exit 1
fi

echo "[sim-runtime] installing local runtime prerequisites via Homebrew"
brew install rapidjson opencv gstreamer cmake pkg-config python@3.12 flightgear || true

cat <<'EOF'

[sim-runtime] bootstrap completed

Next manual steps:
1. Clone ArduPilot:
   git clone https://github.com/ArduPilot/ardupilot.git "$HOME/Developer/ardupilot"
   cd "$HOME/Developer/ardupilot"
   git submodule update --init --recursive

2. Copy runtime template:
   cd /Users/isihyeon/Desktop/Arrakis-Project/apps/flight-demo/sim_runtime
   cp runtime.env.example runtime.env

3. Primary runtime path:
   ./run_ardupilot_quadplane.sh

4. Optional view-only FlightGear:
   ./run_flightgear_view.sh

5. Then run:
   ./check_environment.sh
EOF
