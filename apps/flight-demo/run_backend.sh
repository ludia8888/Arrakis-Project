#!/bin/zsh

set -euo pipefail

cd "$(dirname "$0")/backend"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

. .venv/bin/activate
pip install -r requirements.txt
export ARRAKIS_FLIGHT_ADAPTER="${ARRAKIS_FLIGHT_ADAPTER:-mock}"
exec uvicorn main:app --host 127.0.0.1 --port 8010
