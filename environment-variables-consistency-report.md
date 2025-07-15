# Environment Variables Consistency Report

## Executive Summary
After analyzing all services in the docker-compose.yml file and their corresponding code, I've identified several critical inconsistencies and missing environment variables that could cause runtime issues.

## Critical Issues Found

### 1. JWT_SECRET Inconsistencies

**Issue**: While most services use the same JWT_SECRET, there are configuration mismatches:

- **User Service**: Expects `JWT_SECRET` but config validates it requires at least 32 characters and changes from default
- **Audit Service**: Has both `JWT_SECRET` and `JWT_SECRET_KEY` in config
- **Data Kernel Service**: Uses `JWT_SECRET` but no validation
- **OMS**: Missing `JWT_SECRET` in docker-compose.yml environment

**Fix Required**:
```yaml
# In docker-compose.yml for OMS service, add:
- JWT_SECRET=${JWT_SECRET:-your-very-secure-jwt-secret-key}
```

### 2. Database Connection String Issues

**User Service**:
- Docker-compose: `postgresql+asyncpg://arrakis_user:arrakis_password@postgres:5432/user_service_db`
- Expected by code: `DATABASE_URL` environment variable
- ✅ Correctly configured

**Audit Service**:
- Docker-compose: `postgresql+asyncpg://arrakis_user:arrakis_password@postgres:5432/audit_db`
- Expected by code: `DATABASE_URL` environment variable
- ✅ Correctly configured

**OMS Service**:
- Docker-compose: `postgresql://arrakis_user:arrakis_password@postgres:5432/oms_db`
- Issue: Missing `+asyncpg` for async operations
- **Fix Required**: Change to `postgresql+asyncpg://arrakis_user:arrakis_password@postgres:5432/oms_db`

### 3. Missing Required Environment Variables

**Data Kernel Service**:
- Missing but expected by code:
  - `TERMINUSDB_PASS` (docker-compose has `TERMINUSDB_ADMIN_PASS`)
  - **Fix**: Code expects `TERMINUSDB_PASS`, not `TERMINUSDB_ADMIN_PASS`

**Embedding Service**:
- Missing in docker-compose:
  - `TOKENIZERS_PARALLELISM` (set in code but not in docker-compose)
  - `TF_CPP_MIN_LOG_LEVEL` (set in code but not in docker-compose)
  - API keys for providers (OpenAI, Cohere, etc.) if using external providers

**Scheduler Service**:
- Missing but referenced in code:
  - `POSTGRES_URL` (service config expects it)
  - **Fix**: Add `POSTGRES_URL=postgresql://arrakis_user:arrakis_password@postgres:5432/scheduler_db`

**Event Gateway**:
- Missing configuration for:
  - `WEBHOOK_TIMEOUT`
  - `MAX_RETRIES`
  - Stream configuration settings

### 4. Service URL Inconsistencies

**OMS Service**:
- Has correct URLs for user-service and audit-service
- Missing URLs for microservices (but has gRPC endpoints correctly set)

**Scheduler Service**:
- References wrong ports in service_config.py:
  - `embedding-service:8001` ✅ Correct
  - `audit-service:8000` ❌ Should be `audit-service:8011`
  - `user-service:8010` ✅ Correct
  - `data-kernel-service:8003` ❌ Should be `data-kernel-service:8080`

### 5. Port Mismatches

**User Service**:
- Internal port: 8000
- External port: 8010
- ✅ Correctly configured

**Audit Service**:
- Internal port: 8000
- External port: 8011
- ✅ Correctly configured

**Data Kernel Service**:
- REST API: 8080 (internal and external)
- gRPC: 50051
- ✅ Correctly configured

**Embedding Service**:
- REST API: 8001 (internal and external)
- gRPC: 50055
- ✅ Correctly configured

**Scheduler Service**:
- REST API: 8002 (internal and external)
- gRPC: 50056
- ✅ Correctly configured

**Event Gateway**:
- REST API: 8003 (internal and external)
- gRPC: 50057
- ✅ Correctly configured

### 6. Redis Configuration Issues

**Different Redis databases used**:
- User Service: Not specified (defaults to 0)
- Audit Service: Not specified (defaults to 0)
- OMS: `redis://redis:6379` (defaults to 0)
- Embedding Service: `redis://redis:6379/5`
- Scheduler Service: `redis://redis:6379/6`
- Event Gateway: `redis://redis:6379/7`

**Potential Conflict**: User Service, Audit Service, and OMS all use Redis DB 0

### 7. Security Configuration Issues

**Missing in Production**:
1. **OMS Service** missing critical security env vars:
   - `SECURITY_JWT_SECRET` (required by settings.py validation)
   - `SECURITY_ENCRYPTION_KEY` (required for production)
   - `DB_TERMINUS_PASSWORD` (expects this instead of `TERMINUSDB_ADMIN_PASS`)
   - `DB_POSTGRES_PASSWORD` (expects this instead of implicit connection string)

2. **CORS Origins**:
   - Most services allow all origins (`*`) which is insecure for production
   - OMS validates against wildcard in production but docker-compose doesn't set proper origins

## Recommendations

### 1. Immediate Fixes Required

```yaml
# Update docker-compose.yml

# OMS Service - Add missing critical variables
oms:
  environment:
    # Add missing security variables
    - SECURITY_JWT_SECRET=${JWT_SECRET:-your-very-secure-jwt-secret-key}
    - SECURITY_ENCRYPTION_KEY=${ENCRYPTION_KEY:-your-32-char-encryption-key-here}
    - DB_TERMINUS_PASSWORD=${TERMINUSDB_ADMIN_PASS:-changeme-admin-pass}
    - DB_POSTGRES_PASSWORD=arrakis_password

    # Fix database URL for async
    - DATABASE_URL=postgresql+asyncpg://arrakis_user:arrakis_password@postgres:5432/oms_db

# Data Kernel Service - Fix environment variable name
data-kernel-service:
  environment:
    - TERMINUSDB_PASS=${TERMINUSDB_ADMIN_PASS:-changeme-admin-pass}  # Add this

# Scheduler Service - Add missing database URL
scheduler-service:
  environment:
    - POSTGRES_URL=postgresql://arrakis_user:arrakis_password@postgres:5432/scheduler_db
    - DATABASE_URL=postgresql+asyncpg://arrakis_user:arrakis_password@postgres:5432/scheduler_db
```

### 2. Redis Database Separation

```yaml
# Assign different Redis databases to avoid conflicts
user-service:
  environment:
    - REDIS_URL=redis://redis:6379/1  # Changed from default 0

audit-service:
  environment:
    - REDIS_URL=redis://redis:6379/2  # Changed from default 0

oms:
  environment:
    - REDIS_URL=redis://redis:6379/3  # Changed from default 0
```

### 3. Production Security Settings

Create a `.env.production` file:
```bash
# JWT and Security
JWT_SECRET=<generate-with-openssl-rand-base64-32>
ENCRYPTION_KEY=<generate-with-openssl-rand-base64-32>

# CORS (replace with actual domains)
CORS_ORIGINS=https://app.yourdomain.com,https://api.yourdomain.com

# Passwords (use strong passwords)
TERMINUSDB_ADMIN_PASS=<strong-password>
POSTGRES_PASSWORD=<strong-password>
REDIS_PASSWORD=<strong-password>

# Environment
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=WARNING
```

### 4. Service Discovery Fixes

Update scheduler service configuration:
```python
# In scheduler-service/app/config/service_config.py
audit_service: str = field(default_factory=lambda: os.getenv('AUDIT_SERVICE_URL', 'http://audit-service:8011'))  # Fix port
data_kernel_service: str = field(default_factory=lambda: os.getenv('DATA_KERNEL_SERVICE_URL', 'http://data-kernel-service:8080'))  # Fix port
```

## Testing Recommendations

1. **Environment Variable Validation Script**: Create a script to validate all required environment variables are set before starting services
2. **Health Check Enhancement**: Add environment variable checks to health endpoints
3. **Integration Tests**: Test inter-service communication with correct URLs
4. **Redis Collision Test**: Verify no key collisions between services sharing Redis databases

## Conclusion

The main issues are:
1. Missing critical security environment variables for OMS
2. Inconsistent database connection strings (missing async support)
3. Redis database conflicts between services
4. Incorrect service URLs in scheduler configuration
5. Missing production security configurations

These issues should be addressed before deploying to production to avoid runtime failures and security vulnerabilities.
