#!/usr/bin/env bash
# SITL (Software In The Loop) management utility
# Usage: ./scripts/sitl.sh [start|stop|status|wait|logs]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.sitl.yml"

case "${1:-help}" in
  start)
    SERVICE="${2:-sitl-quadplane}"
    echo "[SITL] Starting $SERVICE..."
    docker compose -f "$COMPOSE_FILE" up -d "$SERVICE"
    echo "[SITL] Container started. Use './scripts/sitl.sh wait' to wait for EKF convergence."
    ;;
  stop)
    echo "[SITL] Stopping all SITL containers..."
    docker compose -f "$COMPOSE_FILE" down
    echo "[SITL] Stopped."
    ;;
  status)
    docker compose -f "$COMPOSE_FILE" ps
    ;;
  wait)
    PORT="${2:-5760}"
    MAX_WAIT="${3:-120}"
    echo "[SITL] Waiting for EKF convergence on port $PORT (max ${MAX_WAIT}s)..."
    for i in $(seq 1 "$MAX_WAIT"); do
      if nc -z localhost "$PORT" 2>/dev/null; then
        echo "[SITL] TCP port $PORT ready after ${i}s"
        # Additional wait for EKF convergence after TCP is up
        echo "[SITL] Waiting 30s extra for EKF convergence..."
        sleep 30
        echo "[SITL] Ready."
        exit 0
      fi
      sleep 1
    done
    echo "[SITL] ERROR: Port $PORT not ready after ${MAX_WAIT}s"
    docker compose -f "$COMPOSE_FILE" logs --tail=50
    exit 1
    ;;
  logs)
    SERVICE="${2:-sitl-quadplane}"
    docker compose -f "$COMPOSE_FILE" logs -f "$SERVICE"
    ;;
  help|*)
    echo "Usage: $0 {start|stop|status|wait|logs} [service|port]"
    echo ""
    echo "Commands:"
    echo "  start [service]    Start SITL container (default: sitl-quadplane)"
    echo "  stop               Stop all SITL containers"
    echo "  status             Show container status"
    echo "  wait [port] [max]  Wait for SITL to be ready (default: port 5760, 120s max)"
    echo "  logs [service]     Follow container logs"
    echo ""
    echo "Environment for tests:"
    echo "  ARRAKIS_ARDUPILOT_CONNECTION=tcp:127.0.0.1:5760"
    echo "  ARRAKIS_ARDUPILOT_HEARTBEAT_TIMEOUT=120"
    echo "  ARRAKIS_TEST_REAL_ARDUPILOT=1"
    ;;
esac
