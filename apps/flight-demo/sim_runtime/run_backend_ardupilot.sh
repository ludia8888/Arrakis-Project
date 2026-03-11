#!/bin/bash
set -euo pipefail

SIM_ROOT="$(cd "$(dirname "$0")" && pwd)"
APP_ROOT="$(cd "$SIM_ROOT/.." && pwd)"
REPO_ROOT="$(cd "$APP_ROOT/../.." && pwd)"

# shellcheck disable=SC1091
source "$SIM_ROOT/common.sh"

export ARRAKIS_FLIGHT_ADAPTER=ardupilot
: "${ARRAKIS_ARDUPILOT_CONNECTION:=udp:127.0.0.1:14550}"
export ARRAKIS_ARDUPILOT_CONNECTION

echo "[sim-runtime] starting backend with adapter=$ARRAKIS_FLIGHT_ADAPTER connection=$ARRAKIS_ARDUPILOT_CONNECTION"
cd "$APP_ROOT/backend"
exec "$REPO_ROOT/.venv/bin/uvicorn" main:app --host 127.0.0.1 --port 8010
