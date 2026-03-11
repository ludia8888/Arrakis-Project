#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$ROOT_DIR/../.." && pwd)"
PYTHON="$REPO_DIR/.venv/bin/python"

echo "[check] py_compile"
python3 -m py_compile \
  "$ROOT_DIR/backend/main.py" \
  "$ROOT_DIR/backend/schemas.py" \
  "$ROOT_DIR/backend/config.py" \
  "$ROOT_DIR/backend/logging_utils.py" \
  "$ROOT_DIR/backend/arrakis_core/"*.py \
  "$ROOT_DIR/backend/arrakis_core/perception_backends/"*.py \
  "$ROOT_DIR/backend/flight_adapters/"*.py

echo "[check] frontend build"
(
  cd "$ROOT_DIR/frontend"
  npm run build
)

echo "[check] adapter contract smoke"
(
  cd "$ROOT_DIR"
  "$PYTHON" -m pytest tests/test_adapter_contract.py -q
)

echo "[check] mock round trip"
ARRAKIS_STATE_DUMP_PATH=/tmp/arrakis_check_state_dump.jsonl "$PYTHON" <<'PY'
import sys
import time
from pathlib import Path

backend_dir = Path("/Users/isihyeon/Desktop/Arrakis-Project/apps/flight-demo/backend")
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from arrakis_core.controller import ArrakisController
from arrakis_core.route_planner import build_route_preview
from flight_adapters.instrumented import InstrumentedFlightAdapter
from flight_adapters.mock import MockAdapter
from schemas import LatLon, RouteRequest

dump_path = Path("/tmp/arrakis_check_state_dump.jsonl")
if dump_path.exists():
    dump_path.unlink()

controller = ArrakisController(InstrumentedFlightAdapter(MockAdapter(), logger_name="arrakis.adapter.mock"))
route = build_route_preview(
    RouteRequest(
        home=LatLon(lat=37.5665, lon=126.9780),
        waypoints=[
            LatLon(lat=37.5667, lon=126.9783),
            LatLon(lat=37.5669, lon=126.9786),
            LatLon(lat=37.5670, lon=126.9783),
            LatLon(lat=37.5668, lon=126.9781),
        ],
        cruise_alt_m=60.0,
    )
)
controller.set_route(route)
controller.start_mission()

start = time.time()
phase_history = []
while time.time() - start < 45:
    payload = controller.state_payload()
    if not phase_history or phase_history[-1] != payload.mission_phase:
        phase_history.append(payload.mission_phase)
    if payload.mission_phase == "COMPLETE":
        break
    time.sleep(0.2)
else:
    raise RuntimeError(f"mission did not complete, last phase={controller.state_payload().mission_phase}")

controller.shutdown()
if not dump_path.exists() or not dump_path.read_text(encoding="utf-8").strip():
    raise RuntimeError("state dump file was not written during check")

print("[check] phases:", " -> ".join(phase_history))
PY

echo "[check] all green"
