#!/usr/bin/env bash
set -euo pipefail

echo "[sim-runtime] host: $(hostname)"
echo "[sim-runtime] arch: $(uname -m)"
echo "[sim-runtime] python3: $(command -v python3 || echo missing)"
echo "[sim-runtime] sim_vehicle.py: $(command -v sim_vehicle.py || echo missing)"
echo "[sim-runtime] gz: $(command -v gz || echo missing)"
echo "[sim-runtime] gazebo: $(command -v gazebo || echo missing)"

if command -v gz >/dev/null 2>&1; then
  echo "[sim-runtime] gz version:"
  gz sim --versions 2>/dev/null || true
fi

echo
echo "[sim-runtime] VM runtime is ready when:"
echo "- sim_vehicle.py is available"
echo "- gz is available"
echo "- ardupilot_gazebo build artifacts exist"
