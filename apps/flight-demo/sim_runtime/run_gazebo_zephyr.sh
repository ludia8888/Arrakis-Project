#!/bin/bash
set -euo pipefail

SIM_ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SIM_ROOT/common.sh"

runtime_require_dir "$ARRAKIS_ARDUPILOT_GAZEBO_DIR" "ardupilot_gazebo dir"
runtime_export_gazebo_env
runtime_print_summary

if ! command -v gz >/dev/null 2>&1; then
  echo "[sim-runtime] gz not found in PATH" >&2
  exit 1
fi

echo "[sim-runtime] launching Gazebo world: $ARRAKIS_GZ_WORLD"
exec gz sim -v "$ARRAKIS_GZ_VERBOSE" "$ARRAKIS_GZ_WORLD"
