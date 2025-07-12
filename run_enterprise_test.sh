#!/bin/bash

# Run Enterprise Integration Test Suite
# This script starts necessary services and runs the test suite

set -e

echo "🚀 Starting Arrakis Enterprise Integration Test Suite"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if services are running
echo "\n📦 Checking required services..."

# Check PostgreSQL
if pg_isready -h localhost -p 5432 >/dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} PostgreSQL is running"
else
    echo -e "${RED}✗${NC} PostgreSQL is not running"
    echo "Starting PostgreSQL..."
    brew services start postgresql@14 || brew services start postgresql
fi

# Check Redis
if redis-cli ping >/dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Redis is running"
else
    echo -e "${RED}✗${NC} Redis is not running"
    echo "Starting Redis..."
    brew services start redis
fi

# Start services locally (not Docker)
echo "\n🔧 Starting services locally..."

# Kill existing services
echo "Stopping any existing services..."
pkill -f "uvicorn.*8010" || true
pkill -f "uvicorn.*8011" || true
pkill -f "uvicorn.*8000" || true
sleep 2

# Start User Service
echo "Starting User Service..."
(
    cd user-service
    source venv/bin/activate 2>/dev/null || python3 -m venv venv && source venv/bin/activate
    pip install -q -r requirements.txt
    export DATABASE_URL="postgresql://arrakis_user:arrakis_password@localhost:5432/user_service_db"
    # Generate or use secure JWT secret - never hardcode in production
    export JWT_SECRET="${JWT_SECRET:-$(openssl rand -hex 32)}"
    nohup uvicorn src.main:app --host 0.0.0.0 --port 8010 > user_service.log 2>&1 &
)

# Start Audit Service
echo "Starting Audit Service..."
(
    cd audit-service
    source venv/bin/activate 2>/dev/null || python3 -m venv venv && source venv/bin/activate
    pip install -q -r requirements.txt
    export DATABASE_URL="postgresql://arrakis_user:arrakis_password@localhost:5432/audit_db"
    # Generate or use secure JWT secret - never hardcode in production
    export JWT_SECRET="${JWT_SECRET:-$(openssl rand -hex 32)}"
    export USER_SERVICE_URL="http://localhost:8010"
    nohup uvicorn main:app --host 0.0.0.0 --port 8011 > audit_service.log 2>&1 &
)

# Start OMS Service
echo "Starting OMS Service..."
(
    cd ontology-management-service
    source venv/bin/activate 2>/dev/null || python3 -m venv venv && source venv/bin/activate
    pip install -q -r requirements.txt
    export REDIS_URL="redis://localhost:6379"
    export DATABASE_URL="postgresql://arrakis_user:arrakis_password@localhost:5432/oms_db"
    # Generate or use secure JWT secret - never hardcode in production
    export JWT_SECRET="${JWT_SECRET:-$(openssl rand -hex 32)}"
    export USER_SERVICE_URL="http://localhost:8010"
    export AUDIT_SERVICE_URL="http://localhost:8011"
    nohup python main.py > oms_service.log 2>&1 &
)

# Wait for services to start
echo "\n⏳ Waiting for services to start..."
sleep 10

# Check if services are running
echo "\n🔍 Verifying services..."
services_ok=true

for port in 8010 8011 8000; do
    if curl -s http://localhost:$port/health >/dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Service on port $port is healthy"
    else
        echo -e "${RED}✗${NC} Service on port $port is not responding"
        services_ok=false
    fi
done

if [ "$services_ok" = false ]; then
    echo -e "\n${RED}Some services failed to start. Check the logs:${NC}"
    echo "  - user-service/user_service.log"
    echo "  - audit-service/audit_service.log"
    echo "  - ontology-management-service/oms_service.log"
    exit 1
fi

# Run the test suite
echo -e "\n${GREEN}🧪 Running Enterprise Integration Test Suite...${NC}"
python3 enterprise_integration_test_suite.py

# Cleanup
echo "\n🧹 Cleaning up..."
pkill -f "uvicorn.*8010" || true
pkill -f "uvicorn.*8011" || true
pkill -f "uvicorn.*8000" || true

echo -e "\n${GREEN}✅ Test suite completed!${NC}"