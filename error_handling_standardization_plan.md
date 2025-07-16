# Error Handling Standardization Plan

## Current State Analysis

### Multiple Definitions of ServiceUnavailableError

1. **Central Definition** - `models/exceptions.py:72`
   - Inherits from `OMSException`
   - Intended as the standard exception for service unavailability

2. **Duplicate Definitions**:
   - `api/gateway/router.py:22` - Custom definition, not importing central one
   - `core/integrations/iam_service_client_with_fallback.py:30` - Custom definition

3. **Variant Definition**:
   - `core/iam/iam_integration.py:35` - `IAMServiceUnavailableError` (domain-specific naming)

### Identified Issues

1. **Lack of Central Import**: Gateway modules are defining their own exceptions instead of importing from `models.exceptions`
2. **Inconsistent Naming**: Some modules use domain-specific prefixes (IAM), others don't
3. **Missing Exception Hierarchy**: Not leveraging the OMSException base class benefits
4. **Potential Catch Issues**: Different exception types might not be caught properly in unified error handlers

## Standardization Approach

### 1. Use Central Exceptions

All modules should import and use exceptions from `models.exceptions`:

```python
from models.exceptions import ServiceUnavailableError, ValidationError, ResourceNotFoundError
```

### 2. Domain-Specific Exceptions

For domain-specific cases, extend the central exceptions:

```python
# In models/exceptions.py or domain-specific exception modules
class IAMServiceUnavailableError(ServiceUnavailableError):
    """IAM-specific service unavailability"""
    pass
```

### 3. Exception Hierarchy

```
OMSException (Base)
├── ValidationError
├── ResourceNotFoundError
├── ServiceUnavailableError
│   ├── IAMServiceUnavailableError
│   ├── DatabaseServiceUnavailableError
│   └── ExternalAPIUnavailableError
└── AuthenticationError
```

### 4. Standardized Error Response Format

```python
{
    "error": {
        "type": "ServiceUnavailableError",
        "message": "User service is temporarily unavailable",
        "code": "SERVICE_UNAVAILABLE",
        "details": {
            "service": "user-service",
            "retry_after": 30
        }
    },
    "request_id": "req_123456",
    "timestamp": "2024-01-15T10:30:00Z"
}
```

## Implementation Tasks

### Phase 1: Update Exception Imports
1. Replace local ServiceUnavailableError definitions with imports from models.exceptions
2. Update all exception raising code to use central exceptions
3. Ensure proper exception handling in middleware

### Phase 2: Create Domain-Specific Exceptions
1. Add domain-specific exceptions to models/exceptions.py
2. Update IAM integration to use standardized hierarchy
3. Document exception usage patterns

### Phase 3: Implement Consistent Error Handlers
1. Create centralized error handling middleware
2. Standardize error response format across all services
3. Add proper logging and monitoring for exceptions

### Phase 4: Testing and Validation
1. Unit tests for exception handling
2. Integration tests for error propagation
3. Performance impact assessment

## Files to Update

### High Priority
- [ ] `api/gateway/router.py` - Remove local definition, import from models.exceptions
- [ ] `core/integrations/iam_service_client_with_fallback.py` - Use central exception
- [ ] `core/iam/iam_integration.py` - Standardize IAMServiceUnavailableError

### Medium Priority
- [ ] Create comprehensive exception hierarchy in models/exceptions.py
- [ ] Update all gateway modules to use consistent error handling
- [ ] Add exception documentation

### Low Priority
- [ ] Add metrics for exception tracking
- [ ] Create exception usage guidelines
- [ ] Update developer documentation

## Benefits

1. **Consistency**: Single source of truth for exceptions
2. **Maintainability**: Easier to update exception behavior
3. **Monitoring**: Centralized exception tracking
4. **Type Safety**: Better IDE support and type checking
5. **Error Handling**: Unified catch blocks can handle all service unavailability

## Next Steps

1. Start with Phase 1 - Update imports in the three identified files
2. Run tests to ensure no breaking changes
3. Gradually implement remaining phases
