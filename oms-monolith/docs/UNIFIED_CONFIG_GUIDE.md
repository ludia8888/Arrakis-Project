# Unified Configuration Guide

## Overview

All configuration in the OMS monolith now flows through a unified, namespace-based system. This consolidates multiple configuration modules into a single source of truth.

## Architecture

```
shared/config/
├── unified_env.py       # Core unified configuration system
├── namespace_configs.py # Domain-specific namespace definitions
├── migration.py         # Legacy config migration helpers
└── __init__.py         # Public API and auto-patching
```

## Key Features

### 1. Namespace-Based Organization

Configuration is organized into namespaces by domain:

- **core**: System-wide settings (DB, Redis, JWT, etc.)
- **traversal**: Graph traversal settings
- **validation**: Schema validation settings
- **scheduler**: Job scheduler settings
- **event**: Event publishing settings
- **middleware**: Middleware settings

### 2. Type-Safe Environment Variables

```python
from shared.config import EnvVar, unified_env

# Define typed environment variable
var = EnvVar(
    name="TRAVERSAL_MAX_DEPTH",
    var_type=int,
    required=False,
    default=10,
    description="Maximum traversal depth",
    validator=lambda v: 1 <= v <= 50
)

# Register to namespace
unified_env.register_var(var, namespace="traversal")
```

### 3. Unified Access Pattern

```python
from shared.config import unified_env

# Get specific value
max_depth = unified_env.get("TRAVERSAL_MAX_DEPTH")

# Get entire namespace config
traversal_config = unified_env.get_namespace_config("traversal")

# Get with namespace hint
cache_ttl = unified_env.get("cache_ttl", namespace="traversal")
```

## Migration Guide

### From StrictEnv

```python
# OLD
from shared.config.environment import StrictEnv
db_url = StrictEnv.get("TERMINUS_DB_URL")

# NEW (automatic compatibility)
from shared.config import StrictEnv  # Works via migration wrapper
db_url = StrictEnv.get("TERMINUS_DB_URL")

# NEW (recommended)
from shared.config import unified_env
db_url = unified_env.get("TERMINUS_DB_URL")
```

### From Domain Configs

```python
# OLD
from core.traversal.config import get_config
config = get_config()
max_depth = config.max_depth

# NEW
from shared.config import unified_env
max_depth = unified_env.get("TRAVERSAL_MAX_DEPTH")
# or
config = unified_env.get_namespace_config("traversal")
max_depth = config["max_depth"]
```

## Adding New Configuration

### 1. Define in namespace_configs.py

```python
def register_myservice_config():
    """Register my service configuration"""
    ns = ConfigNamespace("myservice", "My service configuration")
    
    ns.add_var(EnvVar(
        "MYSERVICE_ENABLED",
        bool,
        required=False,
        default=True,
        description="Enable my service"
    ))
    
    ns.add_var(EnvVar(
        "MYSERVICE_TIMEOUT",
        int,
        required=False,
        default=30,
        description="Service timeout in seconds",
        validator=lambda v: v > 0
    ))
    
    unified_env.register_namespace(ns)
```

### 2. Use in Your Code

```python
from shared.config import unified_env

# Get individual values
enabled = unified_env.get("MYSERVICE_ENABLED")
timeout = unified_env.get("MYSERVICE_TIMEOUT")

# Get all namespace config
config = unified_env.get_namespace_config("myservice")
```

## Validation

### Startup Validation

```python
# In main.py or app startup
from shared.config import validate_env

# Validates all registered configuration
# Exits with error if required vars are missing
validate_env(fail_fast=True)
```

### Manual Validation

```python
from shared.config import unified_env

# Get validation errors without exiting
errors = unified_env.validate(fail_fast=False)
if errors:
    for error in errors:
        logger.error(f"Config error: {error}")
```

## Environment Variable Naming Convention

- Namespace prefix: `{NAMESPACE}_` (e.g., `TRAVERSAL_`, `VALIDATION_`)
- Use UPPER_SNAKE_CASE
- Be descriptive but concise
- Group related settings with common prefixes

Examples:
- `TRAVERSAL_CACHE_ENABLED`
- `TRAVERSAL_CACHE_TTL`
- `VALIDATION_DEFAULT_LEVEL`
- `SCHEDULER_WORKER_COUNT`

## Testing

```python
import os
from shared.config import unified_env

def test_with_config():
    # Override for testing
    os.environ["TRAVERSAL_MAX_DEPTH"] = "5"
    unified_env.clear_cache()  # Clear cached values
    
    assert unified_env.get("TRAVERSAL_MAX_DEPTH") == 5
```

## Monitoring Configuration

### Export Schema

```python
from shared.config import unified_env

# Get full configuration schema
schema = unified_env.export_schema()

# Use for documentation or config validation
print(json.dumps(schema, indent=2))
```

### Health Check

```python
def config_health_check():
    """Include in health endpoint"""
    errors = unified_env.validate(fail_fast=False)
    return {
        "status": "healthy" if not errors else "unhealthy",
        "errors": errors,
        "namespaces": list(unified_env._namespaces.keys())
    }
```

## Best Practices

1. **Always validate on startup**: Call `validate_env()` early in application initialization
2. **Use namespaces**: Group related configuration in namespaces
3. **Provide defaults**: Set sensible defaults for optional configuration
4. **Add validators**: Validate configuration values to catch errors early
5. **Document variables**: Always provide descriptions for EnvVar definitions
6. **Type your config**: Use appropriate var_type for type safety
7. **Cache namespace configs**: Call `get_namespace_config()` once and reuse

## Common Pitfalls

1. **Forgetting to register namespace**: Namespaces must be registered before use
2. **Case sensitivity**: Environment variable names are case-sensitive
3. **Type mismatches**: Ensure var_type matches expected usage
4. **Missing validators**: Add validators to prevent invalid configuration
5. **Circular imports**: Import config late or use lazy loading to avoid cycles

## Performance Considerations

- Configuration values are cached after first access
- Namespace configs are computed once
- Validation runs once unless explicitly called
- Use `clear_cache()` sparingly (mainly for testing)