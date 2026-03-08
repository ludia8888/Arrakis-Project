#!/bin/zsh

set -euo pipefail

cd "$(dirname "$0")"
. .venv/bin/activate

echo "Open http://127.0.0.1:8000 in your browser"
echo "Model resolution order: \$ARRAKIS_MODEL_PATH -> ./best.pt -> ./yolo26s.pt"
exec uvicorn yolo_frontend_app:app --host 127.0.0.1 --port 8000
