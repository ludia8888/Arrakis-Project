#!/bin/bash
set -euo pipefail

SIM_ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SIM_ROOT/common.sh"

runtime_require_dir "$ARRAKIS_ARDUPILOT_GAZEBO_DIR" "ardupilot_gazebo dir"

if ! command -v cmake >/dev/null 2>&1; then
  echo "[sim-runtime] cmake not found" >&2
  exit 1
fi

if ! command -v pkg-config >/dev/null 2>&1; then
  echo "[sim-runtime] pkg-config not found" >&2
  exit 1
fi

if ! command -v gz >/dev/null 2>&1; then
  echo "[sim-runtime] gz not found in PATH" >&2
  echo "[sim-runtime] install Gazebo Harmonic via the official Gazebo distribution first," >&2
  echo "[sim-runtime] or move to the Ubuntu VM fallback path documented in sim_runtime/README.md" >&2
  exit 1
fi

runtime_export_gazebo_env
runtime_print_summary

mkdir -p "$ARRAKIS_ARDUPILOT_GAZEBO_DIR/build"
cd "$ARRAKIS_ARDUPILOT_GAZEBO_DIR/build"

echo "[sim-runtime] configuring ardupilot_gazebo"
cmake .. -DCMAKE_BUILD_TYPE=RelWithDebInfo

echo "[sim-runtime] building ardupilot_gazebo"
cmake --build . -j4
