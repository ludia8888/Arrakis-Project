#!/bin/bash

# Set Python path to include app directory
export PYTHONPATH=/app:$PYTHONPATH

# Enable verbose logging
export LOG_LEVEL=DEBUG
export PYTHONUNBUFFERED=1

# Change to app directory
cd /app

# Start multiple services in background
echo "Starting OMS services..."

# Start main API server
echo "Starting main API server on port 8000..."
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1 --log-level debug &
MAIN_PID=$!

# Start GraphQL services
echo "Starting GraphQL API server on port 8001..."
python -m uvicorn api.graphql.main:app --host 0.0.0.0 --port 8001 --workers 1 --log-level debug &
GRAPHQL_PID=$!

# Start GraphQL subscription server
echo "Starting GraphQL subscription server on port 8002..."
python -m api.graphql.subscription_server --host 0.0.0.0 --port 8002 &
SUBSCRIPTION_PID=$!

# Wait for services to start
sleep 5

echo "Services started:"
echo "  Main API: http://0.0.0.0:8000"
echo "  GraphQL API: http://0.0.0.0:8001"
echo "  GraphQL Subscriptions: ws://0.0.0.0:8002"

# Function to handle shutdown
shutdown() {
    echo "Shutting down services..."
    kill $MAIN_PID 2>/dev/null
    kill $GRAPHQL_PID 2>/dev/null
    kill $SUBSCRIPTION_PID 2>/dev/null
    wait
    echo "All services stopped"
    exit 0
}

# Set up signal handling
trap shutdown SIGTERM SIGINT

# Wait for any process to exit
wait -n

# Exit with status of process that exited first
exit $?