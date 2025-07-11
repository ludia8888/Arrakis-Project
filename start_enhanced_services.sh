#!/bin/bash

# Enhanced MSA Services with Prometheus Metrics Startup Script

echo "🔥 Starting Enhanced MSA Services with Prometheus Metrics..."

# Kill any existing services
pkill -f enhanced_services_with_metrics.py
pkill -f run_simple_services.py

sleep 2

# Start each service in background
echo "🔑 Starting Enhanced User Service (Port 8012)..."
python3 -c "
import asyncio
import uvicorn
from enhanced_services_with_metrics import create_enhanced_user_service

app = create_enhanced_user_service()
config = uvicorn.Config(app, host='0.0.0.0', port=8012, log_level='info')
server = uvicorn.Server(config)
asyncio.run(server.serve())
" &

sleep 3

echo "🗄️ Starting Enhanced OMS Service (Port 8010)..."
python3 -c "
import asyncio
import uvicorn
from enhanced_services_with_metrics import create_enhanced_oms_service

app = create_enhanced_oms_service()
config = uvicorn.Config(app, host='0.0.0.0', port=8010, log_level='info')
server = uvicorn.Server(config)
asyncio.run(server.serve())
" &

sleep 3

echo "📋 Starting Enhanced Audit Service (Port 8011)..."
python3 -c "
import asyncio
import uvicorn
from enhanced_services_with_metrics import create_enhanced_audit_service

app = create_enhanced_audit_service()
config = uvicorn.Config(app, host='0.0.0.0', port=8011, log_level='info')
server = uvicorn.Server(config)
asyncio.run(server.serve())
" &

sleep 5

echo "✅ All Enhanced Services Started!"
echo "📊 Metrics Available:"
echo "   - User Service: http://localhost:8012/metrics"
echo "   - OMS Service: http://localhost:8010/metrics"
echo "   - Audit Service: http://localhost:8011/metrics"
echo ""
echo "❤️ Health Checks:"
echo "   - User Service: http://localhost:8012/health"
echo "   - OMS Service: http://localhost:8010/health"
echo "   - Audit Service: http://localhost:8011/health"

wait