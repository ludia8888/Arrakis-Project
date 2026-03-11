#!/bin/bash
set -euo pipefail

SIM_ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SIM_ROOT/common.sh"

runtime_require_dir "$ARRAKIS_ARDUPILOT_DIR" "ardupilot dir"
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
  --add-param-file "$ARRAKIS_ARDUPILOT_DEFAULTS"
  --out "$ARRAKIS_ARDUPILOT_OUT"
)

if [[ -n "$ARRAKIS_MAVPROXY_ARGS" ]]; then
  CMD+=(--mavproxy-args "$ARRAKIS_MAVPROXY_ARGS")
fi

if [[ -n "$ARRAKIS_ARDUPILOT_MODEL" ]]; then
  CMD+=(--model "$ARRAKIS_ARDUPILOT_MODEL")
fi
if [[ "$ARRAKIS_ARDUPILOT_MAP" == "1" ]]; then
  CMD+=(--map)
fi
if [[ "$ARRAKIS_ARDUPILOT_CONSOLE" == "1" ]]; then
  CMD+=(--console)
fi
if [[ "$ARRAKIS_ARDUPILOT_WIPE" == "1" ]]; then
  CMD+=(-w)
fi

echo "[sim-runtime] launching ArduPilot QuadPlane SITL"
printf '[sim-runtime] command: %q ' "${CMD[@]}"
printf '\n'
cd "$ARRAKIS_ARDUPILOT_DIR"
exec "${CMD[@]}"
