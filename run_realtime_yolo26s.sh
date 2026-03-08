#!/bin/zsh

set -euo pipefail

cd "$(dirname "$0")"
. .venv/bin/activate
exec python realtime_yolo26s.py "$@"
