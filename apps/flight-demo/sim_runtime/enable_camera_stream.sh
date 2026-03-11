#!/bin/bash
set -euo pipefail

SIM_ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SIM_ROOT/common.sh"

if ! command -v gz >/dev/null 2>&1; then
  echo "[sim-runtime] gz not found in PATH" >&2
  exit 1
fi

if [[ -z "${ARRAKIS_GZ_CAMERA_ENABLE_TOPIC:-}" ]]; then
  echo "[sim-runtime] ARRAKIS_GZ_CAMERA_ENABLE_TOPIC is unset in runtime.env" >&2
  echo "[sim-runtime] set it to the Gazebo camera control topic before running this script" >&2
  exit 1
fi

echo "[sim-runtime] enabling camera stream on topic: $ARRAKIS_GZ_CAMERA_ENABLE_TOPIC"
exec gz topic -t "$ARRAKIS_GZ_CAMERA_ENABLE_TOPIC" -m gz.msgs.Boolean -p 'data: true'
