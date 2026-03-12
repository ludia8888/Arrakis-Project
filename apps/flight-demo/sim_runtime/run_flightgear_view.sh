#!/bin/bash
set -euo pipefail

SIM_ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SIM_ROOT/common.sh"

runtime_require_dir "$ARRAKIS_ARDUPILOT_DIR" "ardupilot dir"
runtime_require_dir "$ARRAKIS_FLIGHTGEAR_AIRCRAFT_DIR" "FlightGear aircraft dir"

if [[ ! -f "$ARRAKIS_FLIGHTGEAR_AIRCRAFT_DIR/Rascal/Rascal110-JSBSim-set.xml" ]]; then
  echo "[sim-runtime] FlightGear aircraft assets not found in $ARRAKIS_FLIGHTGEAR_AIRCRAFT_DIR" >&2
  exit 1
fi

if [[ ! -x "$ARRAKIS_FLIGHTGEAR_BIN" ]]; then
  echo "[sim-runtime] FlightGear binary missing or not executable at $ARRAKIS_FLIGHTGEAR_BIN" >&2
  echo "[sim-runtime] install FlightGear on the host or set ARRAKIS_FLIGHTGEAR_BIN" >&2
  exit 1
fi

echo "[sim-runtime] launching FlightGear direct view-only renderer"
echo "[sim-runtime] using FlightGear binary $ARRAKIS_FLIGHTGEAR_BIN"

extra_args=(
  "--native-fdm=socket,in,10,,${ARRAKIS_FLIGHTGEAR_NATIVE_FDM_PORT},udp"
  "--fdm=external"
  "--aircraft=${ARRAKIS_FLIGHTGEAR_AIRCRAFT}"
  "--fg-aircraft=${ARRAKIS_FLIGHTGEAR_AIRCRAFT_DIR}"
  "--airport=${ARRAKIS_FLIGHTGEAR_AIRPORT}"
  "--geometry=${ARRAKIS_FLIGHTGEAR_GEOMETRY}"
  "--bpp=32"
  "--disable-hud-3d"
  "--disable-horizon-effect"
  "--disable-sound"
  "--disable-fullscreen"
  "--disable-random-objects"
  "--disable-ai-models"
  "--fog-disable"
  "--disable-specular-highlight"
  "--disable-anti-alias-hud"
  "--wind=0@0"
  "--timeofday=noon"
  "--prop:/sim/current-view/internal=${ARRAKIS_FLIGHTGEAR_INTERNAL_VIEW}"
  "--prop:/sim/current-view/view-number=${ARRAKIS_FLIGHTGEAR_VIEW_NUMBER}"
  "--prop:/sim/chase-distance-m=${ARRAKIS_FLIGHTGEAR_CHASE_DISTANCE_M}"
)

if [[ "$ARRAKIS_FLIGHTGEAR_DISABLE_SPLASH" == "1" ]]; then
  extra_args+=("--disable-splash-screen")
fi

if [[ -n "${ARRAKIS_FLIGHTGEAR_EXTRA_ARGS:-}" ]]; then
  # shellcheck disable=SC2206
  extra_args+=(${ARRAKIS_FLIGHTGEAR_EXTRA_ARGS})
fi

printf '[sim-runtime] command: %q' "$ARRAKIS_FLIGHTGEAR_BIN"
printf ' %q' "${extra_args[@]}"
printf '\n'
printf '[sim-runtime] extra args:'
printf ' %q' "${extra_args[@]}"
printf '\n'

# The macOS FlightGear app bundle sets FG_LAUNCHER=1 via Info.plist, which
# forces the launcher/splash path and ignores the fgfs-style arguments we rely
# on for view-only SITL rendering.
unset FG_LAUNCHER
exec "$ARRAKIS_FLIGHTGEAR_BIN" "${extra_args[@]}"
