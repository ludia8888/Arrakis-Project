#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
ARCH="$(uname -m)"
ROSETTA_STATUS="unknown"

if [[ "$ARCH" == "arm64" ]]; then
  if /usr/bin/pgrep oahd >/dev/null 2>&1; then
    ROSETTA_STATUS="installed"
  else
    ROSETTA_STATUS="not-detected"
  fi
fi

echo "[sim-runtime] host arch: $ARCH"
echo "[sim-runtime] rosetta: $ROSETTA_STATUS"
echo "[sim-runtime] sim_vehicle.py: $(command -v sim_vehicle.py || echo missing)"
echo "[sim-runtime] ardupilot: $(command -v ardupilot || echo missing)"
echo "[sim-runtime] gz: $(command -v gz || echo missing)"
echo "[sim-runtime] gazebo: $(command -v gazebo || echo missing)"
echo "[sim-runtime] python3: $(command -v python3 || echo missing)"
echo "[sim-runtime] repo sim_runtime dir: $ROOT_DIR"

cat <<'EOF'

Expected minimum for local Rosetta smoke:
- Apple Silicon host may show arch=arm64
- Rosetta should be installed if Gazebo/ArduPilot x86 path is used
- sim_vehicle.py should be available
- gz or gazebo should be available

If sim_vehicle.py or gz/gazebo is missing, install/runtime prep is still pending.
EOF
