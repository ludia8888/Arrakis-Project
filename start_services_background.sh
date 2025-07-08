#!/bin/bash
# 백그라운드에서 서비스들을 시작하는 스크립트

echo "Starting services in background..."

# User Service
echo "Starting User Service on port 8101..."
cd /Users/isihyeon/Desktop/Arrakis-Project/user-service
nohup python run_user_service.py > user_service.log 2>&1 &
echo $! > /tmp/user_service.pid
sleep 2

# Audit Service  
echo "Starting Audit Service on port 8002..."
cd /Users/isihyeon/Desktop/Arrakis-Project/audit-service
nohup python main.py > audit_service.log 2>&1 &
echo $! > /tmp/audit_service.pid
sleep 2

# OMS Monolith
echo "Starting OMS Monolith on port 8000..."
cd /Users/isihyeon/Desktop/Arrakis-Project/ontology-management-service
nohup python main.py > oms_monolith.log 2>&1 &
echo $! > /tmp/oms_monolith.pid

echo "All services started in background"
echo "PIDs saved to /tmp/*.pid files"
echo ""
echo "To check logs:"
echo "- User Service: tail -f /Users/isihyeon/Desktop/Arrakis-Project/user-service/user_service.log"
echo "- Audit Service: tail -f /Users/isihyeon/Desktop/Arrakis-Project/audit-service/audit_service.log"
echo "- OMS Monolith: tail -f /Users/isihyeon/Desktop/Arrakis-Project/ontology-management-service/oms_monolith.log"