#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$ROOT_DIR/common.sh"
ARCH="$(uname -m)"
ROSETTA_STATUS="unknown"

if [[ "$ARCH" == "arm64" ]]; then
  if /usr/bin/pgrep oahd >/dev/null 2>&1; then
    ROSETTA_STATUS="installed"
  else
    ROSETTA_STATUS="not-detected"
  fi
fi

SIM_VEHICLE_PATH="$ARRAKIS_ARDUPILOT_DIR/Tools/autotest/sim_vehicle.py"

echo "[sim-runtime] host arch: $ARCH"
echo "[sim-runtime] rosetta: $ROSETTA_STATUS"
echo "[sim-runtime] runtime.env: $(test -f "$ROOT_DIR/runtime.env" && echo present || echo missing)"
echo "[sim-runtime] sim_vehicle.py (PATH): $(command -v sim_vehicle.py || echo missing)"
echo "[sim-runtime] sim_vehicle.py (configured): $(test -f "$SIM_VEHICLE_PATH" && echo "$SIM_VEHICLE_PATH" || echo missing)"
echo "[sim-runtime] ardupilot: $(command -v ardupilot || echo missing)"
echo "[sim-runtime] ardupilot dir: $(test -d "$ARRAKIS_ARDUPILOT_DIR" && echo "$ARRAKIS_ARDUPILOT_DIR" || echo missing)"
echo "[sim-runtime] flightgear helper: $(test -x "$ARRAKIS_FLIGHTGEAR_SCRIPT" && echo "$ARRAKIS_FLIGHTGEAR_SCRIPT" || echo missing)"
echo "[sim-runtime] fgfs: $(command -v fgfs || echo missing)"
echo "[sim-runtime] python3: $(command -v python3 || echo missing)"
echo "[sim-runtime] repo sim_runtime dir: $ROOT_DIR"

cat <<'EOF'

Expected minimum for local QuadPlane smoke:
- Apple Silicon host may show arch=arm64
- sim_vehicle.py should be available
- FlightGear is optional and view-only

If sim_vehicle.py is missing, runtime prep is still pending.
EOF
