#!/usr/bin/env bash
# End-to-end SITL integration test runner
# Starts SITL, waits for readiness, runs tests, then stops.
#
# Usage:
#   ./scripts/run_sitl_tests.sh              # QuadPlane (default)
#   ./scripts/run_sitl_tests.sh copter       # ArduCopter
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

MODE="${1:-quadplane}"

if [ "$MODE" = "copter" ]; then
  SERVICE="sitl-copter"
  PORT=5770
else
  SERVICE="sitl-quadplane"
  PORT=5760
fi

echo "=========================================="
echo " SITL Integration Test Runner"
echo " Vehicle: $MODE  Port: $PORT"
echo "=========================================="

# 1. Start SITL
echo ""
echo "[1/4] Starting SITL ($SERVICE)..."
"$SCRIPT_DIR/sitl.sh" start "$SERVICE"

# 2. Wait for readiness
echo ""
echo "[2/4] Waiting for SITL readiness..."
"$SCRIPT_DIR/sitl.sh" wait "$PORT" 150

# 3. Run unit tests first (ensure no regressions)
echo ""
echo "[3/4] Running unit tests (non-SITL) to verify baseline..."
cd "$PROJECT_ROOT"
python -m pytest tests/ -v --timeout=60 -k "not sitl and not ARRAKIS_TEST_REAL" \
  2>&1 | tail -5

# 4. Run SITL integration tests (including flight sequences)
echo ""
echo "[4/4] Running SITL integration tests..."
ARRAKIS_ARDUPILOT_CONNECTION="tcp:127.0.0.1:$PORT" \
ARRAKIS_ARDUPILOT_HEARTBEAT_TIMEOUT=120 \
ARRAKIS_ARDUPILOT_COMMAND_TIMEOUT=45 \
ARRAKIS_TEST_REAL_ARDUPILOT=1 \
  python -m pytest tests/ -v -k "sitl" --timeout=600 \
  2>&1

RESULT=$?

# 5. Cleanup
echo ""
echo "[Cleanup] Stopping SITL..."
"$SCRIPT_DIR/sitl.sh" stop

if [ $RESULT -eq 0 ]; then
  echo ""
  echo "=========================================="
  echo " ALL SITL TESTS PASSED"
  echo "=========================================="
else
  echo ""
  echo "=========================================="
  echo " SITL TESTS FAILED (exit code: $RESULT)"
  echo "=========================================="
  exit $RESULT
fi
