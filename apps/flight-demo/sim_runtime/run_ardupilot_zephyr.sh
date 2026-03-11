#!/bin/bash
set -euo pipefail

SIM_ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SIM_ROOT/common.sh"

runtime_require_dir "$ARRAKIS_ARDUPILOT_DIR" "ardupilot dir"
runtime_export_gazebo_env
runtime_print_summary

SIM_VEHICLE="$ARRAKIS_ARDUPILOT_DIR/Tools/autotest/sim_vehicle.py"
if [[ ! -f "$SIM_VEHICLE" ]]; then
  echo "[sim-runtime] sim_vehicle.py missing at $SIM_VEHICLE" >&2
  exit 1
fi

CMD=(
  python3 "$SIM_VEHICLE"
  -v "$ARRAKIS_ARDUPILOT_VEHICLE"
  -f "$ARRAKIS_ARDUPILOT_FRAME"
  --model "$ARRAKIS_ARDUPILOT_MODEL"
)

if [[ "$ARRAKIS_ARDUPILOT_MAP" == "1" ]]; then
  CMD+=(--map)
fi
if [[ "$ARRAKIS_ARDUPILOT_CONSOLE" == "1" ]]; then
  CMD+=(--console)
fi

echo "[sim-runtime] launching ArduPilot SITL"
printf '[sim-runtime] command: %q ' "${CMD[@]}"
printf '\n'
cd "$ARRAKIS_ARDUPILOT_DIR"
exec "${CMD[@]}"
