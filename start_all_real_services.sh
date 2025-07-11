#!/bin/bash
echo "🚀 Starting ALL Real Arrakis Services..."

# Stop any existing mock services first
pkill -f run_simple_services.py

# Start User Service
echo "🔑 Starting User Service..."
cd /Users/isihyeon/Desktop/Arrakis-Project/user-service
python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload &

# Start Audit Service  
echo "📋 Starting Audit Service..."
cd /Users/isihyeon/Desktop/Arrakis-Project/audit-service
python3 -m uvicorn main:app --host 0.0.0.0 --port 8092 --reload &

# Start OMS Monolith
echo "🗄️ Starting OMS Monolith..."
cd /Users/isihyeon/Desktop/Arrakis-Project/ontology-management-service
python3 -m uvicorn main:app --host 0.0.0.0 --port 8091 --reload &

echo "✅ All Real Services Started!"
echo "User Service: http://localhost:8080"
echo "Audit Service: http://localhost:8092"  
echo "OMS Monolith: http://localhost:8091"

wait
