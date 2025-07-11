#!/bin/bash
# Simple script to run GraphQL service

# Set required environment variables
export USER_SERVICE_URL=http://user-service:8000
export OMS_SERVICE_URL=http://localhost:8000
export REDIS_URL=redis://localhost:6379
export PYTHONPATH=.

# Run the GraphQL service
echo "Starting GraphQL service on port 8006..."
venv_new/bin/python -m uvicorn api.graphql.modular_main:app --host 0.0.0.0 --port 8006