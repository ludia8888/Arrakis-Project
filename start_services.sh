#!/bin/bash
# MSA 서비스 시작 스크립트

echo "🚀 MSA 서비스 시작..."

# Redis 시작
if ! pgrep -x "redis-server" > /dev/null; then
    echo "Starting Redis..."
    redis-server --daemonize yes
fi

# User Service 시작
echo "Starting User Service..."
cd user-service
uvicorn main:app --port 8002 --reload &
cd ..

# Audit Service 시작
echo "Starting Audit Service..."
cd audit-service
uvicorn main:app --port 8001 --reload &
cd ..

# OMS 시작
echo "Starting OMS..."
cd ontology-management-service
uvicorn main:app --port 8000 --reload &
cd ..

echo "✅ 모든 서비스가 시작되었습니다"
echo "User Service: http://localhost:8002"
echo "Audit Service: http://localhost:8001"
echo "OMS: http://localhost:8000"
