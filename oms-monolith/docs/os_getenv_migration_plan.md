# OS.getenv() to unified_env Migration Plan

## Overview

This document outlines the migration plan for replacing direct `os.getenv()` calls with the unified environment configuration system (`unified_env`).

## Current State Analysis

### Files Using os.getenv() Directly (32 files found)

#### Core System Files
1. **main_secure.py**
   - Line 262: `os.getenv("ENVIRONMENT", "production")`
   - Used for environment detection

2. **middleware/auth_secure.py**
   - Line 80: `os.getenv('ENVIRONMENT', 'production')`
   - Used for production environment detection

3. **core/iam/iam_integration.py**
   - Line 37: `os.getenv("JWT_ISSUER", "iam.company")`
   - Line 38: `os.getenv("JWT_AUDIENCE", "oms")`
   - Line 42: `os.getenv("JWT_LOCAL_VALIDATION", "true")`
   - JWT configuration parameters

4. **shared/database/unified_db_factory.py**
   - Lines 309-319: Multiple database configuration variables
   - TERMINUS_DB_ENDPOINT, TERMINUS_DB_USER, TERMINUS_DB_PASSWORD
   - REDIS_SENTINELS, REDIS_MASTER_NAME, REDIS_PASSWORD, REDIS_DB
   - CACHE_TYPE

#### Service Clients
5. **shared/clients/iam_service_client.py**
6. **shared/clients/user_service_client.py**
7. **shared/clients/terminus_db.py**
   - Service endpoint configurations

#### Configuration Files
8. **shared/config/environment.py**
9. **shared/config/unified_config.py**
10. **shared/config/base_config.py**
    - Legacy configuration systems that need consolidation

#### Security Components
11. **shared/security/pii_utils.py**
12. **shared/security/exception_handler.py**
13. **core/auth/resource_permission_checker.py**
14. **core/security/pii_handler.py**
    - Security-related configurations

#### Validation & Policy
15. **core/validation/integration.py**
16. **core/validation/policy_engine.py**
17. **core/validation/tampering_detection.py**
18. **core/validation/config.py**
19. **core/validation/dependencies.py**
    - Validation system configurations

#### Scripts & Tools
20. **scripts/production_readiness_check.py**
21. **scripts/deploy_production.py**
22. **scripts/dev-tools/clear_terminusdb.py**
23. **scripts/ci/validate_oms_changes.py**
    - Deployment and CI/CD configurations

#### Other Components
24. **migrations/migrate_to_distributed_locks.py**
25. **shared/cache/terminusdb_cache.py**
26. **core/schema_generator/sdk_generator.py**
27. **middleware/issue_tracking_middleware.py**
28. **services/grpc/server.py**
29. **core/traversal/config.py**
30. **core/integrations/__init__.py**

### Already Migrated/Using unified_env
- **shared/config/unified_env.py** - The new unified configuration system
- **scripts/migrate_os_getenv.py** - Migration tool

## Migration Strategy

### Phase 1: Critical Path Migration (Week 1)
Priority: Security and Authentication Components

1. **main_secure.py**
   - Replace environment detection with unified_env
   - Ensure fail-secure defaults

2. **middleware/auth_secure.py**
   - Migrate environment detection
   - Maintain security invariants

3. **core/iam/iam_integration.py**
   - Migrate JWT configuration
   - Add proper validators for JWT settings

### Phase 2: Service Integration (Week 2)
Priority: External Service Connections

1. **Service Clients**
   - iam_service_client.py
   - user_service_client.py
   - terminus_db.py

2. **Database Factory**
   - unified_db_factory.py
   - Consolidate all database configurations

### Phase 3: Configuration Consolidation (Week 3)
Priority: Remove Legacy Systems

1. **Legacy Config Files**
   - environment.py
   - unified_config.py
   - base_config.py
   - Merge into unified_env namespaces

2. **Validation Configs**
   - All core/validation/* config files
   - Create validation namespace

### Phase 4: Scripts and Tools (Week 4)
Priority: Operational Tools

1. **Production Scripts**
   - production_readiness_check.py
   - deploy_production.py

2. **Development Tools**
   - CI/CD scripts
   - Development utilities

## Implementation Guidelines

### 1. Namespace Organization
```python
# Core namespace (already exists)
- TERMINUS_DB_*
- REDIS_*
- JWT_*
- IAM_SERVICE_URL
- USER_SERVICE_URL

# Security namespace (new)
- SECURITY_PII_ENCRYPTION_KEY
- SECURITY_FAIL_SECURE_MODE
- SECURITY_AUDIT_LEVEL

# Validation namespace (new)
- VALIDATION_POLICY_ENGINE_URL
- VALIDATION_TAMPERING_DETECTION
- VALIDATION_NAMING_RULES

# Service namespace (new)
- SERVICE_GRPC_PORT
- SERVICE_HTTP_PORT
- SERVICE_CIRCUIT_BREAKER_*
```

### 2. Migration Pattern
```python
# Before
environment = os.getenv('ENVIRONMENT', 'production').lower().strip()

# After
from shared.config import unified_env
environment = unified_env.get('ENVIRONMENT', namespace='core')
```

### 3. Validation Requirements
- All URLs must validate protocol (http/https)
- Ports must be valid integers (1-65535)
- Secrets must meet minimum length requirements
- Environment values must be from allowed enum

### 4. Testing Strategy
1. Unit tests for each migrated component
2. Integration tests for service connections
3. Configuration validation tests
4. Backward compatibility tests

## Risk Mitigation

### 1. Gradual Rollout
- Use feature flags for new configuration system
- Maintain backward compatibility layer during migration
- Monitor for configuration errors

### 2. Validation Gates
- Pre-deployment configuration validation
- Runtime configuration health checks
- Automated rollback on configuration errors

### 3. Documentation
- Update all configuration documentation
- Create migration guide for developers
- Document new namespace structure

## Success Criteria

1. **Zero Configuration Errors**: No runtime configuration failures
2. **Improved Validation**: All configuration validated at startup
3. **Centralized Management**: Single source of truth for all config
4. **Better Documentation**: Clear namespace organization
5. **Type Safety**: All configuration values properly typed

## Timeline

- **Week 1**: Critical security components
- **Week 2**: Service integrations
- **Week 3**: Configuration consolidation
- **Week 4**: Scripts and tools
- **Week 5**: Testing and validation
- **Week 6**: Documentation and training

## Next Steps

1. Review and approve migration plan
2. Set up unified_env namespaces
3. Begin Phase 1 migration
4. Create automated tests for each phase
5. Monitor and adjust plan as needed