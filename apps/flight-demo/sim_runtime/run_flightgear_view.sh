#!/bin/bash
set -euo pipefail

SIM_ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SIM_ROOT/common.sh"

runtime_require_dir "$ARRAKIS_ARDUPILOT_DIR" "ardupilot dir"

if [[ ! -x "$ARRAKIS_FLIGHTGEAR_SCRIPT" ]]; then
  echo "[sim-runtime] FlightGear helper missing or not executable at $ARRAKIS_FLIGHTGEAR_SCRIPT" >&2
  echo "[sim-runtime] expected ArduPilot checkout with Tools/autotest/fg_plane_view.sh" >&2
  exit 1
fi

if [[ ! -x "$ARRAKIS_FLIGHTGEAR_BIN" ]]; then
  echo "[sim-runtime] FlightGear binary missing or not executable at $ARRAKIS_FLIGHTGEAR_BIN" >&2
  echo "[sim-runtime] install FlightGear on the host or set ARRAKIS_FLIGHTGEAR_BIN" >&2
  exit 1
fi

shim_dir="$(mktemp -d "${TMPDIR:-/tmp}/arrakis-fgfs.XXXXXX")"
trap 'rm -rf "$shim_dir"' EXIT
cat >"$shim_dir/fgfs" <<EOF
#!/usr/bin/env bash
exec "$ARRAKIS_FLIGHTGEAR_BIN" "\$@"
EOF
chmod +x "$shim_dir/fgfs"
export PATH="$shim_dir:$PATH"

echo "[sim-runtime] launching FlightGear view-only helper"
echo "[sim-runtime] using FlightGear binary $ARRAKIS_FLIGHTGEAR_BIN"
printf '[sim-runtime] command: %q ' "$ARRAKIS_FLIGHTGEAR_SCRIPT"
printf '\n'
cd "$ARRAKIS_ARDUPILOT_DIR"
exec "$ARRAKIS_FLIGHTGEAR_SCRIPT"
