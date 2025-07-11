#!/bin/bash
echo "🔧 Starting All Microservices..."

# Embedding Service
echo "🧠 Starting Embedding Service..."
cd /Users/isihyeon/Desktop/Arrakis-Project/ontology-management-service/services/embedding-service
python3 -m uvicorn app.api:app --host 0.0.0.0 --port 8001 &

# Event Gateway
echo "📡 Starting Event Gateway..."
cd /Users/isihyeon/Desktop/Arrakis-Project/ontology-management-service/services/event-gateway
python3 -m uvicorn app.api:app --host 0.0.0.0 --port 8003 &

# Scheduler Service (fixed port)
echo "⏰ Starting Scheduler Service..."
cd /Users/isihyeon/Desktop/Arrakis-Project/ontology-management-service/services/scheduler-service
python3 -m uvicorn app.api:app --host 0.0.0.0 --port 8005 &

echo "✅ All Microservices Started!"
wait
