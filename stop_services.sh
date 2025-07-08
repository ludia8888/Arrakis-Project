#!/bin/bash
# 실행 중인 서비스들을 중지하는 스크립트

echo "Stopping all services..."

# PID 파일에서 프로세스 종료
for service in user_service audit_service oms_monolith; do
    if [ -f "/tmp/${service}.pid" ]; then
        PID=$(cat "/tmp/${service}.pid")
        if kill -0 "$PID" 2>/dev/null; then
            echo "Stopping $service (PID: $PID)..."
            kill "$PID"
        fi
        rm -f "/tmp/${service}.pid"
    fi
done

# Python 프로세스들도 확인하여 종료
pkill -f "run_user_service.py" 2>/dev/null
pkill -f "audit-service.*main.py" 2>/dev/null
pkill -f "ontology-management-service.*main.py" 2>/dev/null

echo "All services stopped"