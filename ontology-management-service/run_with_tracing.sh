#!/bin/bash

# Script to run OMS with proper tracing configuration

echo "🚀 Starting OMS with OpenTelemetry tracing enabled..."

# Export tracing environment variables
export ENABLE_TELEMETRY=true
export JAEGER_ENABLED=true
export JAEGER_AGENT_HOST=localhost
export JAEGER_AGENT_PORT=6831
export JAEGER_COLLECTOR_ENDPOINT=""  # Empty to use agent instead of collector
export OTEL_SERVICE_NAME=oms-monolith
export OTEL_PYTHON_EXCLUDED_URLS="/health,/metrics,/api/v1/health"
export OTEL_LOG_LEVEL=INFO
export OTEL_PROPAGATORS=tracecontext,b3multi

# Log the configuration
echo "📋 Tracing Configuration:"
echo "   ENABLE_TELEMETRY=$ENABLE_TELEMETRY"
echo "   JAEGER_AGENT_HOST=$JAEGER_AGENT_HOST"
echo "   JAEGER_AGENT_PORT=$JAEGER_AGENT_PORT"
echo "   OTEL_SERVICE_NAME=$OTEL_SERVICE_NAME"

# Start the application
echo ""
echo "▶️  Starting OMS application..."
python main.py