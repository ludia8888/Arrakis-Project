# ADR-010: Action Service Refactoring - DLQ Consolidation and Security Hardening

## Status
Accepted

## Context
The core/action module was identified as having several architectural issues that needed to be addressed:

1. **DLQ Handler Duplication**: Two separate DLQ implementations exist - one in `core/action/dlq_handler.py` (494 LOC) and another in `middleware/dlq_handler.py` (823 LOC), with overlapping functionality but different feature sets.

2. **Fallback Stub Anti-pattern**: The service uses try/except ImportError with stub implementations, which silently degrades functionality in production when dependencies are missing.

3. **Security Gaps**: API routes lack authentication and ETag support for caching.

4. **Missing Network Resilience**: No retry logic or circuit breaker for external Actions Service calls.

5. **Configuration Validation**: ACTIONS_SERVICE_URL not validated at startup.

## Decision

We have implemented a comprehensive refactoring of the core/action module following these principles:

### 1. DLQ Consolidation
- Created `shared/dlq/` package with unified DLQ domain models and handlers
- Implemented `ActionDLQHandler` as a specialized extension of the base DLQHandler
- Maintained backward compatibility through aliasing in the legacy location

### 2. Fail-Fast Dependencies
- Removed all fallback stub implementations
- Dependencies now fail immediately with ModuleNotFoundError on import failure
- This ensures issues are caught during deployment rather than runtime

### 3. API Security Enhancement
- Added JWT authentication to all routes using `Depends(get_current_user)`
- Implemented scope-based authorization (action:read, action:write, action:delete)
- Added ETag support for GET endpoints to enable efficient caching

### 4. Network Resilience
- Integrated `shared.utils.retry_strategy` with exponential backoff
- Added circuit breaker protection for Actions Service calls
- Failed requests after retry exhaustion are sent to DLQ for recovery

### 5. Configuration Management
- Added ACTIONS_SERVICE_URL to required production configurations
- Implemented health check validation for Actions Service connectivity
- Centralized configuration through EnvironmentConfig

## Implementation Details

### Shared DLQ Package Structure
```
shared/dlq/
├── __init__.py      # Public API exports
├── models.py        # DLQReason, DLQMessage, RetryPolicy
├── config.py        # DLQConfig, RetryConfig
└── handlers.py      # DLQHandler, ActionDLQHandler
```

### Security Implementation
```python
@router.post("", response_model=ActionTypeModel)
async def create_action_type(
    request: CreateActionTypeRequest,
    user: UserContext = Depends(get_current_user)
):
    if not user.has_scope("action:write"):
        raise HTTPException(status_code=403, detail="Requires 'action:write' scope")
```

### Retry Configuration
```python
ACTIONS_SERVICE_WRITE_CONFIG = RetryConfig(
    strategy=RetryStrategy.CUSTOM,
    max_attempts=5,
    initial_delay=0.5,
    max_delay=30.0,
    timeout=30.0,
    circuit_breaker_threshold=10,
    retry_budget_percent=15.0
)
```

## Consequences

### Positive
- **Reduced Code Duplication**: Single DLQ implementation reduces maintenance burden
- **Improved Reliability**: Fail-fast behavior catches configuration issues early
- **Enhanced Security**: All endpoints now require authentication and proper authorization
- **Better Performance**: ETag support reduces unnecessary data transfer
- **Increased Resilience**: Retry and circuit breaker prevent cascade failures
- **Operational Visibility**: Failed requests are tracked in DLQ for recovery

### Negative
- **Breaking Changes**: Services depending on the old DLQ location need updates
- **Stricter Requirements**: Missing dependencies now cause immediate failure
- **Additional Complexity**: More configuration required for retry policies

### Neutral
- **Migration Path**: Legacy imports are maintained but emit deprecation warnings
- **Testing Requirements**: Comprehensive test suite needed for all components

## Migration Guide

1. **Update DLQ Imports**:
   ```python
   # Old
   from core.action.dlq_handler import DLQHandler
   
   # New
   from shared.dlq import ActionDLQHandler
   ```

2. **Ensure Dependencies**:
   - Add all required packages to requirements.txt
   - No fallback stubs will be available

3. **Update Configuration**:
   - Set ACTIONS_SERVICE_URL environment variable
   - In production, this is now required

4. **API Authentication**:
   - Ensure all API calls include valid JWT tokens
   - Update client code to handle 403 responses

## Monitoring and Observability

The refactoring includes comprehensive metrics:
- DLQ message counts by queue and reason
- Retry attempts and success rates
- Circuit breaker state transitions
- API authentication failures

## Future Considerations

1. **Complete DLQ Migration**: Remove middleware/dlq_handler.py once all services migrate
2. **Async DLQ Processing**: Implement background workers for DLQ message recovery
3. **Advanced Retry Strategies**: Add per-operation custom retry policies
4. **Schema Registry**: Centralize ActionType schemas for better governance

## References
- Original analysis document
- Python logging best practices
- Circuit breaker pattern
- JWT authentication standards

## Date
2024-01-30

## Authors
- Architecture Team
- With assistance from Claude Code