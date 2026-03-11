#!/usr/bin/env bash
set -euo pipefail

echo "[sim-runtime] host: $(hostname)"
echo "[sim-runtime] arch: $(uname -m)"
echo "[sim-runtime] python3: $(command -v python3 || echo missing)"
echo "[sim-runtime] sim_vehicle.py: $(command -v sim_vehicle.py || echo missing)"
echo "[sim-runtime] fgfs: $(command -v fgfs || echo missing)"

echo
echo "[sim-runtime] VM runtime is ready when:"
echo "- sim_vehicle.py is available"
echo "- ArduPilot checkout is built enough to launch quadplane SITL"
echo "- FlightGear is optional for view-only rendering"
