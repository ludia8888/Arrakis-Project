#!/bin/bash

# 모든 서비스 시작 스크립트

echo "Starting all services..."

# User Service 시작 (포트 8001)
echo "Starting User Service on port 8001..."
cd /Users/isihyeon/Desktop/Arrakis-Project/user-service
python run_user_service.py &
USER_PID=$!
echo "User Service PID: $USER_PID"

# Audit Service 시작 (포트 8002)
echo "Starting Audit Service on port 8002..."
cd /Users/isihyeon/Desktop/Arrakis-Project/audit-service
python main.py &
AUDIT_PID=$!
echo "Audit Service PID: $AUDIT_PID"

# 서비스들이 시작될 시간을 줌
sleep 5

# OMS Monolith 시작 (포트 8000)
echo "Starting OMS Monolith on port 8000..."
cd /Users/isihyeon/Desktop/Arrakis-Project/ontology-management-service
python main.py &
OMS_PID=$!
echo "OMS Monolith PID: $OMS_PID"

echo "All services started!"
echo "User Service: http://localhost:8001"
echo "Audit Service: http://localhost:8002"
echo "OMS Monolith: http://localhost:8000"

# PID들을 파일에 저장
echo "$USER_PID" > /tmp/user_service.pid
echo "$AUDIT_PID" > /tmp/audit_service.pid
echo "$OMS_PID" > /tmp/oms_monolith.pid

# 종료 시그널 대기
wait