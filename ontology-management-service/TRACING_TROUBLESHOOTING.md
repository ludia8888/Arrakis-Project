# OpenTelemetry Tracing Troubleshooting Guide

## Issue: Jaeger UI is running but no application traces are being collected

### Root Cause Analysis

1. **FastAPI Instrumentation Issue**: The FastAPI application was not being properly instrumented with OpenTelemetry
2. **Environment Configuration**: Missing or incorrect environment variables for Jaeger endpoint
3. **Initialization Order**: Tracing initialization happening before or without the FastAPI app instance

### Solutions Applied

#### 1. Fixed FastAPI Instrumentation

Updated `observability/enterprise_integration.py` to properly instrument the FastAPI app:

```python
# In _integrate_with_fastapi method
try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=self.enterprise_tracer.get_tracer().trace.get_tracer_provider(),
        excluded_urls="/health,/metrics,/api/v1/health"
    )
    logger.info("✅ FastAPI instrumented for OpenTelemetry tracing")
except Exception as e:
    logger.warning(f"Failed to instrument FastAPI for tracing: {e}")
```

#### 2. Updated Jaeger Configuration

Modified `observability/enterprise_tracing.py` to use environment variables:

```python
jaeger_host = os.getenv("JAEGER_AGENT_HOST", "localhost")
jaeger_port = int(os.getenv("JAEGER_AGENT_PORT", "6831"))
collector_endpoint = os.getenv("JAEGER_COLLECTOR_ENDPOINT", self.config.jaeger_endpoint)
```

#### 3. Created Proper Environment Configuration

Created `run_with_tracing.sh` script with correct environment variables:

```bash
export ENABLE_TELEMETRY=true
export JAEGER_ENABLED=true
export JAEGER_AGENT_HOST=localhost
export JAEGER_AGENT_PORT=6831
export OTEL_SERVICE_NAME=oms-monolith
```

### How to Verify Tracing is Working

1. **Start Jaeger locally**:
   ```bash
   docker-compose -f docker-compose.tracing.yml up -d
   ```

2. **Run OMS with tracing enabled**:
   ```bash
   ./run_with_tracing.sh
   ```

3. **Test tracing**:
   ```bash
   python test_tracing.py
   ```

4. **Check Jaeger UI**:
   - Open http://localhost:16686
   - Look for service "oms-enterprise" or "oms-monolith"
   - You should see traces for API calls

### Key Configuration Points

1. **Jaeger Agent vs Collector**:
   - Agent Port (UDP): 6831 (recommended for local development)
   - Collector Port (HTTP): 14268 (for direct HTTP submission)

2. **Required Environment Variables**:
   - `ENABLE_TELEMETRY=true`
   - `JAEGER_ENABLED=true`
   - `JAEGER_AGENT_HOST=localhost` (or container name in Docker)
   - `JAEGER_AGENT_PORT=6831`

3. **Service Name**: Must be consistent across configuration
   - Set via `OTEL_SERVICE_NAME` environment variable
   - Or in TracingConfig when initializing

### Common Issues and Solutions

1. **No traces in Jaeger UI**:
   - Check if Jaeger is running: `docker ps | grep jaeger`
   - Verify OMS logs show "Enterprise tracing initialized"
   - Ensure FastAPI instrumentation log appears
   - Check network connectivity to Jaeger

2. **Connection errors to Jaeger**:
   - If running in Docker, use container name instead of localhost
   - Ensure correct port is used (6831 for UDP agent)
   - Check firewall/network policies

3. **Partial traces**:
   - Ensure all services use the same trace propagation format
   - Check `OTEL_PROPAGATORS=tracecontext,b3multi`

### Testing Commands

```bash
# Check if Jaeger is receiving data
curl http://localhost:16686/api/services

# Generate test traces
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/schemas
curl http://localhost:8000/metrics

# Check OMS observability config
curl http://localhost:8000/observability/config
```

### For Microservices

If using microservices architecture, ensure each service:
1. Has its own TracingConfig with unique service name
2. Uses the same Jaeger endpoint
3. Propagates trace context in HTTP headers
4. Has OpenTelemetry dependencies installed

### Dependencies Required

```txt
opentelemetry-api>=1.21.0
opentelemetry-sdk>=1.21.0
opentelemetry-instrumentation-fastapi>=0.42b0
opentelemetry-instrumentation-requests>=0.42b0
opentelemetry-exporter-jaeger>=1.21.0
```