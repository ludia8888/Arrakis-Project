# Requirements.txt Dependency Analysis Report

## 1. Version Conflicts Between Services

### Critical Version Mismatches

#### FastAPI
- **user-service**: 0.104.1
- **audit-service**: 0.104.1
- **data-kernel-service**: 0.109.0 ⚠️
- **embedding-service**: 0.104.1
- **scheduler-service**: 0.115.6 ⚠️
- **event-gateway**: 0.115.6 ⚠️
- **ontology-management-service**: 0.104.1

#### Uvicorn
- **user-service**: 0.24.0
- **audit-service**: 0.24.0
- **data-kernel-service**: 0.27.0 ⚠️
- **embedding-service**: 0.24.0
- **scheduler-service**: 0.34.0 ⚠️
- **event-gateway**: 0.34.0 ⚠️
- **ontology-management-service**: 0.24.0

#### Pydantic
- **user-service**: 2.5.0[email]
- **audit-service**: 2.5.0
- **data-kernel-service**: 2.5.3 ⚠️
- **embedding-service**: 2.5.0
- **scheduler-service**: 2.10.4 ⚠️
- **event-gateway**: 2.10.4 ⚠️
- **ontology-management-service**: 2.5.0

#### HTTPX
- **user-service**: 0.25.2
- **audit-service**: 0.25.2
- **data-kernel-service**: 0.26.0 ⚠️
- **embedding-service**: 0.26.0 ⚠️
- **scheduler-service**: 0.28.1 ⚠️
- **event-gateway**: 0.28.1 ⚠️
- **ontology-management-service**: 0.25.2

#### gRPC
- **data-kernel-service**: 1.60.0
- **embedding-service**: 1.60.0
- **scheduler-service**: 1.68.1 ⚠️
- **event-gateway**: 1.68.1 ⚠️
- **ontology-management-service**: >=1.59.0

#### OpenTelemetry API
- **data-kernel-service**: 1.22.0
- **embedding-service**: 1.23.0 ⚠️
- **scheduler-service**: 1.29.0 ⚠️
- **event-gateway**: 1.29.0 ⚠️
- **ontology-management-service**: 1.21.0 ⚠️

#### OpenTelemetry Instrumentation FastAPI
- **data-kernel-service**: 0.43b0
- **embedding-service**: 0.45b0 ⚠️
- **scheduler-service**: 0.50b0 ⚠️
- **event-gateway**: 0.50b0 ⚠️
- **ontology-management-service**: 0.42b0 ⚠️

#### Prometheus Client
- **user-service**: 0.19.0
- **audit-service**: 0.19.0
- **data-kernel-service**: 0.19.0
- **embedding-service**: 0.19.0
- **scheduler-service**: 0.21.1 ⚠️
- **event-gateway**: 0.21.1 ⚠️
- **ontology-management-service**: 0.19.0

#### NATS-py
- **user-service**: 2.6.0
- **audit-service**: 2.6.0
- **data-kernel-service**: 2.6.0
- **embedding-service**: 2.6.0
- **scheduler-service**: 2.6.0
- **event-gateway**: 2.10.0 ⚠️
- **ontology-management-service**: 2.6.0

#### Python-multipart
- **user-service**: 0.0.6
- **scheduler-service**: 0.0.20 ⚠️
- **event-gateway**: 0.0.20 ⚠️
- **ontology-management-service**: 0.0.6

#### AsyncPG
- **user-service**: 0.29.0
- **audit-service**: 0.29.0
- **scheduler-service**: 0.30.0 ⚠️
- **ontology-management-service**: 0.29.0

#### Tenacity
- **event-gateway**: 9.0.0
- **ontology-management-service**: 8.2.3 ⚠️

#### CloudEvents
- **event-gateway**: 1.11.0
- **ontology-management-service**: 1.10.1 ⚠️

#### Python-json-logger
- **audit-service**: 2.0.7
- **scheduler-service**: 3.2.1 ⚠️
- **event-gateway**: 3.2.1 ⚠️

## 2. Recommendations for Version Alignment

### Immediate Actions Required

1. **Align Core Framework Versions**
   - FastAPI: Standardize to **0.115.6** (latest in your services)
   - Uvicorn: Standardize to **0.34.0** (latest in your services)
   - Pydantic: Standardize to **2.10.4** (latest in your services)

2. **Align Infrastructure Dependencies**
   - gRPC: Standardize to **1.68.1** (latest)
   - HTTPX: Standardize to **0.28.1** (latest)
   - Redis: Keep at **5.0.1** (consistent)
   - NATS-py: Standardize to **2.10.0** (latest)

3. **Align Observability Stack**
   - OpenTelemetry API: Standardize to **1.29.0**
   - OpenTelemetry SDK: Standardize to **1.29.0**
   - OpenTelemetry Instrumentation FastAPI: Standardize to **0.50b0**
   - Prometheus Client: Standardize to **0.21.1**

4. **Align Utility Libraries**
   - Python-multipart: Standardize to **0.0.20**
   - Python-json-logger: Standardize to **3.2.1**
   - AsyncPG: Standardize to **0.30.0**
   - Tenacity: Standardize to **9.0.0**
   - CloudEvents: Standardize to **1.11.0**

## 3. Missing Dependencies Analysis

### User Service
- Missing `pydantic-settings` (used in other services)
- Missing `structlog` for structured logging
- Missing OpenTelemetry instrumentation packages

### Audit Service
- Missing `structlog` for structured logging
- Missing OpenTelemetry instrumentation for Redis, SQLAlchemy

### Data Kernel Service
- Missing `sqlalchemy` and `alembic` for database migrations
- Missing `asyncpg` for async PostgreSQL operations
- Missing `python-json-logger` for JSON logging

### Embedding Service
- Missing `pydantic-settings`
- Missing `alembic` for database migrations
- Missing `aiofiles` for async file operations

### Scheduler Service
- Missing `redis` (though it has aioredis)
- Missing `pydantic-settings`
- Missing `python-dotenv`
- Missing `structlog`

### Event Gateway
- Missing `pydantic-settings`
- Missing `python-dotenv`
- Missing `structlog`
- Missing `sqlalchemy` if it needs database access

### Ontology Management Service
- Has the most comprehensive set but could benefit from:
  - Updating all OpenTelemetry packages to latest versions
  - Adding `structlog` for consistent logging across services

## 4. Potentially Unnecessary Dependencies

### Ontology Management Service
- Has many duplicate/overlapping dependencies:
  - Both `torch>=2.0.0` and specific `torch==2.1.0` in embedding section
  - Both `grpcio>=1.59.0` and specific versions in other services
  - Multiple embedding providers (OpenAI, Cohere) that might not all be used

### Audit Service
- `aioboto3==12.3.0` - Check if AWS S3 is actually used
- `testcontainers==3.7.1` - Should be in dev dependencies
- `pytest*` packages - Should be in dev dependencies

### Data Kernel Service
- `aiohttp==3.9.1` - Already has `httpx`, might be redundant

## 5. Security Concerns

1. **Cryptography Version**: Some services specify `cryptography==41.0.7` while others don't specify it at all
2. **PyJWT vs python-jose**: Both are used across services for JWT handling - standardize on one

## 6. Recommended Common Dependencies File

Create a `requirements-common.txt`:

```txt
# Core Framework
fastapi==0.115.6
uvicorn[standard]==0.34.0
pydantic==2.10.4
pydantic-settings==2.1.0

# Database
sqlalchemy==2.0.23
alembic==1.12.1
asyncpg==0.30.0
psycopg2-binary==2.9.9

# HTTP/Network
httpx==0.28.1
aiofiles==23.2.1
python-multipart==0.0.20

# Message Queue/Event Bus
redis==5.0.1
aioredis==2.0.1
nats-py==2.10.0
cloudevents==1.11.0

# gRPC
grpcio==1.68.1
grpcio-tools==1.68.1
grpcio-reflection==1.68.1

# Security
pyjwt==2.8.0
cryptography==41.0.7
passlib[bcrypt]==1.7.4

# Observability
prometheus-client==0.21.1
opentelemetry-api==1.29.0
opentelemetry-sdk==1.29.0
opentelemetry-instrumentation-fastapi==0.50b0
opentelemetry-instrumentation-grpc==0.50b0
opentelemetry-instrumentation-redis==0.50b0
opentelemetry-instrumentation-sqlalchemy==0.50b0

# Logging
python-json-logger==3.2.1
structlog==24.1.0

# Utilities
python-dotenv==1.0.0
tenacity==9.0.0
pytz==2024.2
pyyaml==6.0.1
```

## 7. Service-Specific Dependencies

Each service should then have its own requirements that include the common file:

```txt
# Include common dependencies
-r requirements-common.txt

# Service-specific dependencies
```

## Summary

The main issues are:
1. **Version fragmentation**: Services are using different versions of core dependencies
2. **Missing critical dependencies**: Some services lack essential packages for production
3. **Inconsistent observability setup**: Different OpenTelemetry versions affect tracing
4. **Test dependencies mixed with production**: Test packages should be separated

Implementing these recommendations will improve system stability, reduce debugging time, and ensure consistent behavior across all microservices.
