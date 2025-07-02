# Circuit Breaker Migration Guide

## Overview

This guide helps migrate from various circuit breaker implementations to the unified resilience module, following the Single Source of Truth (SSOT) principle.

## Current Implementations

### 1. Protection Facade Circuit Breaker
- **Location**: `shared/security/protection_facade.py`
- **Features**: Redis-backed distributed state, rate limiting integration
- **Use Case**: Multi-instance deployments requiring shared state

### 2. Retry Strategy Circuit Breaker  
- **Location**: `shared/utils/retry_strategy.py`
- **Features**: Retry budget, bulkhead pattern, Prometheus metrics
- **Use Case**: Complex retry scenarios with resource isolation

### 3. HTTP Client Circuit Breaker
- **Location**: `shared/clients/unified_http_client.py`
- **Features**: Simple state management, HTTP-specific
- **Use Case**: Basic HTTP client protection

### 4. Unified Circuit Breaker (NEW)
- **Location**: `shared/resilience/implementations/circuit_breaker.py`
- **Features**: Clean interface, thread-safe, comprehensive metrics
- **Use Case**: New development and standardization

## Migration Patterns

### Pattern 1: Direct Migration to Unified Implementation

**Before** (using retry_strategy):
```python
from shared.utils.retry_strategy import CircuitBreaker

circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
    expected_exception=Exception
)

try:
    if not circuit_breaker._should_attempt_reset():
        raise Exception("Circuit open")
    result = make_call()
    circuit_breaker.record_success()
except Exception as e:
    circuit_breaker.record_failure()
    raise
```

**After** (using unified resilience):
```python
from shared.resilience import UnifiedCircuitBreaker, CircuitBreakerConfig

config = CircuitBreakerConfig(
    failure_threshold=5,
    timeout=timedelta(seconds=60),
    track_exceptions=[Exception]
)

circuit_breaker = UnifiedCircuitBreaker(config)

# Use the cleaner interface
result = circuit_breaker.call(make_call)
# Or async
result = await circuit_breaker.acall(make_async_call)
```

### Pattern 2: Using Decorators

**Before** (manual circuit breaker):
```python
def get_user_data(user_id):
    if circuit_breaker.is_open():
        raise ServiceUnavailableError()
    try:
        data = fetch_from_service(user_id)
        circuit_breaker.record_success()
        return data
    except Exception as e:
        circuit_breaker.record_failure()
        raise
```

**After** (using decorator):
```python
from shared.resilience import with_circuit_breaker

@with_circuit_breaker('user-service')
async def get_user_data(user_id):
    return await fetch_from_service(user_id)
```

### Pattern 3: Using Adapters for Gradual Migration

When you need specific features (like Redis distribution), use adapters:

```python
from shared.resilience.adapters import create_circuit_breaker_adapter
from shared.resilience import CircuitBreakerConfig

# For Redis-distributed state (multi-instance)
distributed_cb = create_circuit_breaker_adapter(
    name="payment-service",
    config=CircuitBreakerConfig(
        failure_threshold=10,
        success_threshold=5,
        timeout=timedelta(seconds=30)
    ),
    implementation="distributed"  # Uses Protection Facade
)

# For legacy compatibility
legacy_cb = create_circuit_breaker_adapter(
    name="legacy-service",
    config=CircuitBreakerConfig(...),
    implementation="legacy"  # Uses retry_strategy
)
```

## Migration Steps

### Step 1: Identify Usage
```bash
# Find all circuit breaker usage
grep -r "CircuitBreaker\|circuit_breaker" --include="*.py" .
```

### Step 2: Choose Migration Strategy

1. **New Code**: Always use `UnifiedCircuitBreaker` or decorators
2. **Simple Cases**: Direct migration to unified implementation
3. **Distributed State Needed**: Use adapter with `implementation="distributed"`
4. **Complex Retry Logic**: Consider keeping retry_strategy temporarily

### Step 3: Update Imports

```python
# Old imports to replace
from shared.utils.retry_strategy import CircuitBreaker
from shared.security.protection_facade import get_protection_facade
from shared.clients.unified_http_client import UnifiedHTTPClient

# New unified import
from shared.resilience import (
    UnifiedCircuitBreaker,
    CircuitBreakerConfig,
    with_circuit_breaker,
    create_circuit_breaker_adapter  # If using adapters
)
```

### Step 4: Update Configuration

Convert old configurations to new format:

```python
# Old (retry_strategy)
cb = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
    expected_exception=HTTPError
)

# New (unified)
from datetime import timedelta

config = CircuitBreakerConfig(
    failure_threshold=5,
    timeout=timedelta(seconds=60),
    track_exceptions=[HTTPError],
    on_open=lambda: logger.warning("Circuit opened!")
)
cb = UnifiedCircuitBreaker(config)
```

### Step 5: Test Thoroughly

1. Unit tests for state transitions
2. Integration tests for failure scenarios
3. Load tests to verify thresholds
4. Multi-instance tests if using distributed state

## Feature Comparison

| Feature | Unified | Protection Facade | Retry Strategy | HTTP Client |
|---------|---------|------------------|----------------|-------------|
| Thread-safe | ✅ | ✅ (async) | ✅ | ❌ |
| Async support | ✅ | ✅ | ❌ | ❌ |
| Metrics | ✅ | ✅ | ✅ | ❌ |
| Callbacks | ✅ | ❌ | ❌ | ❌ |
| Distributed | Via adapter | ✅ | ❌ | ❌ |
| Clean interface | ✅ | ❌ | ❌ | ❌ |

## Best Practices

1. **Use Decorators**: Cleanest approach for most cases
2. **Configure Appropriately**: Different services need different thresholds
3. **Monitor Metrics**: Track circuit breaker state changes
4. **Test Failure Modes**: Ensure graceful degradation
5. **Document Decisions**: Why specific thresholds were chosen

## Common Pitfalls

1. **Not Testing Half-Open State**: Test the recovery mechanism
2. **Too Aggressive Thresholds**: Can cause unnecessary outages
3. **Ignoring Metrics**: Monitor circuit breaker behavior in production
4. **Mixing Implementations**: Stick to one pattern per service

## Example: Complete Migration

### Before (Multiple Implementations)
```python
# File: user_service_client.py
from shared.utils.retry_strategy import CircuitBreaker, with_retry
from shared.security.protection_facade import get_protection_facade

class UserServiceClient:
    def __init__(self):
        # Two different circuit breakers!
        self.cb = CircuitBreaker(failure_threshold=5)
        self.protection = get_protection_facade()
        
    @with_retry("user_fetch", circuit_breaker=self.cb)
    async def get_user(self, user_id):
        # Complex retry logic
        return await self._fetch_user(user_id)
```

### After (Unified Approach)
```python
# File: user_service_client.py
from shared.resilience import with_resilience, CircuitBreakerConfig

class UserServiceClient:
    def __init__(self):
        # Single, clear configuration
        self.cb_config = CircuitBreakerConfig(
            failure_threshold=5,
            success_threshold=2,
            timeout=timedelta(seconds=30)
        )
    
    @with_resilience(
        retry_policy='network',
        circuit_breaker_name='user-service'
    )
    async def get_user(self, user_id):
        # Clean and simple
        return await self._fetch_user(user_id)
```

## Rollback Plan

If issues arise during migration:

1. Adapters allow using old implementations with new interface
2. Feature flags can toggle between implementations
3. Keep old imports until migration is verified
4. Monitor metrics closely during rollout

## Support

For questions or issues during migration:
1. Check `shared/resilience/README.md` for detailed API docs
2. Review test files for usage examples
3. Use adapters for gradual migration
4. File issues with the `resilience` tag