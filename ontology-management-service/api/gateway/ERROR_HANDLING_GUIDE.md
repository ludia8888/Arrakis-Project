# Gateway Error Handling Guide

## Overview

This guide provides standardized error handling patterns for all gateway modules in the OMS service.

## Error Hierarchy

All exceptions should inherit from the base `OMSException` class defined in `models.exceptions`:

```
OMSException (Base)
├── ValidationError (400) - Invalid input/request data
├── ResourceNotFoundError (404) - Requested resource doesn't exist
├── AuthenticationError (401) - Authentication failures
├── ServiceUnavailableError (503) - Service temporarily unavailable
│   └── IAMServiceUnavailableError - IAM-specific unavailability
└── Other domain-specific exceptions...
```

## Standard Error Response Format

All errors should return responses in this format:

```json
{
    "error": {
        "type": "ValidationError",
        "message": "Invalid query format",
        "code": "VALIDATION_FAILED",
        "details": {
            "field": "query",
            "reason": "Missing operation name"
        }
    },
    "request_id": "req_123456789",
    "timestamp": "2024-01-15T10:30:00Z"
}
```

## Implementation Guidelines

### 1. Import Standard Exceptions

Always import exceptions from `models.exceptions`:

```python
from models.exceptions import (
    ValidationError,
    ResourceNotFoundError,
    ServiceUnavailableError,
    AuthenticationError
)
```

### 2. Use Appropriate Exception Types

| Scenario | Exception | HTTP Status |
|----------|-----------|-------------|
| Invalid input data | `ValidationError` | 400 |
| Missing required fields | `ValidationError` | 400 |
| Resource not found | `ResourceNotFoundError` | 404 |
| Authentication failure | `AuthenticationError` | 401 |
| Service down/unavailable | `ServiceUnavailableError` | 503 |
| Rate limit exceeded | `ValidationError` | 429 |

### 3. Error Handling in Routes

```python
from api.gateway.error_handler import handle_gateway_error

@router.post("/api/gateway/route")
async def gateway_route(request: Request):
    try:
        # Route logic here
        result = await process_request(request)
        return result
    except Exception as e:
        return handle_gateway_error(e, request.headers.get("X-Request-ID"))
```

### 4. Using the Error Handler Middleware

Add the middleware to your FastAPI app:

```python
from api.gateway.error_handler import GatewayErrorHandler

app = FastAPI()
app.add_middleware(GatewayErrorHandler)
```

### 5. Logging Best Practices

```python
logger.error(
    f"Service unavailable: {service_name}",
    extra={
        "request_id": request_id,
        "service": service_name,
        "error_type": "ServiceUnavailableError"
    },
    exc_info=True  # Include traceback for debugging
)
```

## Examples

### Validation Error

```python
if not query:
    raise ValidationError("Query parameter is required")

if len(query) > MAX_QUERY_LENGTH:
    raise ValidationError(
        f"Query exceeds maximum length of {MAX_QUERY_LENGTH} characters"
    )
```

### Service Unavailable

```python
try:
    response = await http_client.post(service_url, json=data)
except httpx.TimeoutException:
    raise ServiceUnavailableError(
        f"Service {service_name} timed out after {timeout}s"
    )
except httpx.ConnectError:
    raise ServiceUnavailableError(
        f"Cannot connect to service {service_name}"
    )
```

### Resource Not Found

```python
resource = await get_resource(resource_id)
if not resource:
    raise ResourceNotFoundError(
        f"Resource with ID '{resource_id}' not found"
    )
```

## Circuit Breaker Integration

When using circuit breakers, convert circuit breaker states to appropriate exceptions:

```python
if not await circuit_breaker.is_closed(service_name):
    raise ServiceUnavailableError(
        f"Circuit breaker open for service {service_name}"
    )
```

## Testing Error Handling

```python
import pytest
from models.exceptions import ValidationError

async def test_invalid_query_raises_validation_error():
    with pytest.raises(ValidationError) as exc_info:
        await process_query("")

    assert "Query parameter is required" in str(exc_info.value)
```

## Migration Checklist

When updating existing code:

1. [ ] Replace `ValueError` with `ValidationError`
2. [ ] Replace custom exception classes with standard ones
3. [ ] Import from `models.exceptions`
4. [ ] Add appropriate logging with request context
5. [ ] Ensure error messages are user-friendly
6. [ ] Test error scenarios

## Common Anti-patterns to Avoid

❌ **Don't define duplicate exception classes**
```python
# Bad
class ServiceUnavailableError(Exception):
    pass
```

❌ **Don't use generic exceptions for specific errors**
```python
# Bad
raise Exception("Invalid input")
```

❌ **Don't expose internal details in error messages**
```python
# Bad
raise ValidationError(f"Database query failed: {sql_error}")
```

✅ **Do use standard exceptions with clear messages**
```python
# Good
raise ValidationError("Invalid email format")
```

## Monitoring and Alerting

All errors are automatically tracked with:
- Error type metrics
- Response time impact
- Service-specific error rates
- Request tracing via X-Request-ID

Configure alerts for:
- High error rates (>5% of requests)
- Repeated ServiceUnavailableError (circuit breaker triggers)
- Authentication failures (potential security issue)
