# Ontology Management System - Complete Developer Guide

> **⚠️ 중요**: 이 문서는 시스템의 이상적인 설계를 설명합니다. 실제 구현 상태와 차이가 있으므로 반드시 다음 문서들을 참고하세요:
> - [CRITICAL_NOTES.md](./CRITICAL_NOTES.md) - 긴급 참고사항
> - [ACCURATE_SYSTEM_DOCUMENTATION.md](./ACCURATE_SYSTEM_DOCUMENTATION.md) - 100% 정확한 현재 상태

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture Deep Dive](#architecture-deep-dive)
3. [Technology Stack](#technology-stack)
4. [Project Structure](#project-structure)
5. [Core Concepts](#core-concepts)
6. [Development Setup](#development-setup)
7. [API Reference](#api-reference)
8. [Database Schema](#database-schema)
9. [Event System](#event-system)
10. [Security Architecture](#security-architecture)
11. [Testing Strategy](#testing-strategy)
12. [Deployment Guide](#deployment-guide)
13. [Troubleshooting](#troubleshooting)
14. [Code Standards](#code-standards)

---

## 1. System Overview

### What is the Ontology Management System?

The Ontology Management System is an enterprise-grade platform for managing formal knowledge representations (ontologies) with Git-style version control. Think of it as "Git for your data schemas" - it allows teams to collaboratively define, version, and evolve their data models while preventing breaking changes that could disrupt production systems.

#### Real-World Use Cases

1. **Healthcare Systems**: Managing complex medical ontologies (diseases, symptoms, treatments) that need to evolve while maintaining compatibility with existing patient records
2. **Financial Services**: Versioning financial product schemas that must comply with regulations while supporting new features
3. **E-commerce Platforms**: Evolving product catalogs and customer data models across multiple microservices
4. **Research Institutions**: Collaborating on scientific ontologies with strict validation and peer review processes

#### Core Problems It Solves

- **Schema Drift**: When different teams or services have different versions of the same data model
- **Breaking Changes**: Accidentally removing or modifying fields that existing systems depend on
- **Collaboration Conflicts**: Multiple teams trying to modify the same schemas simultaneously
- **Audit Requirements**: Regulatory need to track who changed what and when
- **Migration Complexity**: Understanding the impact of schema changes on existing data

### Key Features

1. **Version Control for Schemas**
   - **Git-style branching and merging**: Create feature branches like `feature/add-customer-email` to develop schemas in isolation
   - **Conflict resolution strategies**: Automatic resolution for non-conflicting changes, manual review for conflicts
   - **Three-way merge support**: Intelligently merges changes from multiple branches using common ancestor comparison
   - **Branch protection rules**: Prevent direct commits to main branch, require reviews for schema changes
   - **Distributed locking**: Prevents concurrent modifications to the same branch

2. **Validation Engine** *(부분 구현)*
   - **Breaking change detection**: Identifies changes that would break existing systems (e.g., removing required fields)
   - **Type compatibility checking**: Ensures type changes are safe (e.g., int to float is ok, string to int is not)
   - **Data impact analysis**: Calculates how many records would be affected by a schema change
   - **Migration planning**: Generates migration scripts for safe schema evolution
   - **Custom validation rules**: Define organization-specific rules (e.g., "all customer fields must have PII tags")
   - **Note**: ValidationService는 현재 None으로 설정되어 있어 일부 기능이 작동하지 않을 수 있습니다

3. **Multi-Protocol API**
   - **RESTful API**: Traditional REST endpoints for CRUD operations with branch context
   - **GraphQL with subscriptions**: Real-time updates when schemas change, with DataLoader for performance
   - **gRPC for high performance**: Binary protocol for service-to-service communication
   - **WebSocket for real-time updates**: Live notifications for schema changes and validation results

4. **Enterprise Features**
   - **Multi-tenancy support**: Isolated schema spaces for different organizations or teams
   - **Role-based access control (RBAC)**: Fine-grained permissions (e.g., "can modify schemas in dev branch but not main")
   - **Comprehensive audit logging**: Every change tracked with who, what, when, why, and from where
   - **PII detection and handling**: Automatic detection of personally identifiable information with configurable policies
   - **Schema freeze capabilities**: Lock schemas during critical periods (e.g., Black Friday for e-commerce)
   - **Issue tracking integration**: Built-in issue management for schema change requests
   - **Shadow indexing**: Performance optimization for large-scale schema operations
   - **MSA (Microservices Architecture) authentication**: Optional integration with external authentication services

---

## 2. Architecture Deep Dive

### System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           API Gateway                                │
│  (JWT/MSA Auth, Rate Limiting, Circuit Breaker, ETag Cache)        │
└─────────────┬──────────────┬──────────────┬───────────────────────┘
              │              │              │
              ▼              ▼              ▼
        ┌─────────┐    ┌─────────┐    ┌─────────┐
        │  REST   │    │GraphQL  │    │  gRPC   │
        │ API v1  │    │   API   │    │Services │
        └────┬────┘    └────┬────┘    └────┬────┘
             │              │              │
             └──────────────┴──────────────┘
                           │
                  ┌────────────────────────────────────────┐
                  │            Core Services                │
                  └────────────────────────────────────────┘
                           │
   ┌───────────────────────┼───────────────────────────┐
   ▼                       ▼                           ▼
┌─────────────┐    ┌──────────────┐    ┌─────────────────────┐
│   Schema    │    │  Validation  │    │      Branch         │
│  Service    │    │   Service    │    │     Service         │
│             │    │              │    │                     │
│ • Registry  │    │ • Rules      │    │ • Distributed Lock  │
│ • Versions  │    │ • Adapters   │    │ • Three-way Merge   │
│ • Conflicts │    │ • Migration  │    │ • Protection Rules  │
└──────┬──────┘    └──────┬───────┘    └──────────┬──────────┘
       │                  │                        │
       └──────────────────┴────────────────────────┘
                          │
        ┌─────────────────┴──────────────────┐
        ▼                                    ▼
┌────────────────┐                   ┌─────────────────┐
│  TerminusDB    │                   │     Redis       │
│(Graph Database)│                   │    (Cache)      │
└────────────────┘                   └─────────────────┘
        │                                    │
        ├────────────────┬───────────────────┘
        ▼                ▼
┌────────────────┐  ┌─────────────────┐
│  PostgreSQL    │  │      NATS       │
│(Advisory Locks)│  │ (Event Broker)  │
└────────────────┘  └─────────────────┘
```

### Component Interactions

1. **API Layer**
   - **API Gateway**: Central entry point handling cross-cutting concerns
     - JWT token validation with caching for performance
     - Optional MSA (Microservices Architecture) authentication mode
     - Rate limiting per user/endpoint with Redis backend
     - Circuit breaker for downstream service protection
     - ETag generation and validation for HTTP caching
   - **Protocol Handlers**: Transform requests to internal format
     - REST: Branch-based routing (e.g., `/api/v1/schemas/{branch}/object-types`)
     - GraphQL: DataLoader pattern for N+1 query prevention
     - gRPC: High-performance binary protocol for service mesh

2. **Core Services**
   - **Schema Service**: Manages ontology definitions
     - Schema registry with version tracking
     - Conflict resolution for concurrent modifications
     - Shadow index manager for performance optimization
   - **Validation Service**: Ensures data integrity
     - Pluggable validation rules architecture
     - Breaking change detection algorithms
     - Migration plan generation
   - **Branch Service**: Git-like version control
     - PostgreSQL advisory locks prevent race conditions
     - Three-way merge with transactional consistency
     - Branch protection rules enforcement
     - DistributedLockManager for multi-instance safety

3. **Data Layer**
   - **TerminusDB**: Primary storage for ontologies
     - Graph-based storage optimized for relationships
     - Built-in version control at database level
     - JSON-LD support for semantic web compatibility
   - **Redis**: High-performance caching
     - Schema cache with TTL management
     - Session storage for authentication
     - Rate limiting counters
     - Temporary data coordination
   - **PostgreSQL**: Distributed lock management and critical state
     - Advisory locks for branch operations (강한 일관성 보장)
     - Three-way merge 트랜잭션 보호
     - 세션 종료 시 자동 lock 해제
     - Branch state 영구 저장
   - **SQLite**: Specialized local storage
     - Issue tracking database
     - Idempotent event consumer state
     - Audit log buffer for reliability

4. **Event System**
   - **NATS with JetStream**: Reliable event streaming
     - CloudEvents format for standardization
     - At-least-once delivery guarantee
     - Event replay capability for recovery
   - **Event Publisher**: Outbox pattern implementation
     - Database-backed reliability
     - Automatic retry with exponential backoff
     - Dead letter queue for failed events
   - **Event Consumers**: Process schema changes
     - IAM synchronization
     - Search index updates
     - Webhook notifications

5. **External Integrations**
   - **IAM Service**: Enhanced authentication/authorization
     - User service integration for token validation
     - Permission service for fine-grained access control
     - Fallback to local JWT validation
   - **Monitoring Stack**
     - Prometheus metrics collection
     - Grafana dashboards for visualization
     - Jaeger distributed tracing
     - Custom OMS load test dashboard
   - **SIEM Integration**: Security event monitoring
     - Structured security event logging
     - Tamper detection for critical operations
     - Compliance audit trail

### Design Patterns and Architecture Decisions

#### Core Patterns

1. **Repository Pattern**: Data access abstraction
   - Each domain entity has a dedicated repository
   - Abstracts database-specific operations
   - Enables easy testing with mock repositories

2. **Service Layer Pattern**: Business logic encapsulation
   - Services contain all business rules
   - Thin controllers delegate to services
   - Services are composable and reusable

3. **Event Sourcing**: Complete audit trail
   - Every change is an event
   - Events are immutable and append-only
   - System state can be reconstructed from events

4. **CQRS (Command Query Responsibility Segregation)**
   - Separate models for reads and writes
   - Optimized read models for queries
   - Write models enforce business rules

#### Resilience Patterns

5. **Circuit Breaker**: Prevents cascade failures
   - Implemented in middleware and service clients
   - Configurable thresholds and timeout periods
   - Graceful degradation when services are down

6. **Bulkhead Pattern**: Resource isolation
   - Separate thread pools for different operations
   - Prevents one slow operation from affecting others
   - Configurable resource limits

7. **Retry with Exponential Backoff**: Handles transient failures
   - Smart retry strategy with jitter
   - Different strategies for different error types
   - Maximum retry limits to prevent infinite loops

#### Performance Patterns

8. **DataLoader Pattern**: Batch loading for GraphQL
   - Prevents N+1 queries in GraphQL resolvers
   - Automatic batching of database requests
   - Request-scoped caching

9. **Shadow Indexing**: Performance optimization
   - Background index updates
   - Read-through cache warming
   - Zero-downtime index rebuilding

10. **ETag Caching**: HTTP-level caching
    - Automatic ETag generation for resources
    - Client-side caching support
    - Bandwidth optimization

11. **PostgreSQL Advisory Locks**: Git-style 강한 일관성 보장
    - **트랜잭션 통합**: Lock과 데이터 변경이 하나의 트랜잭션으로 처리
    - **자동 해제**: 세션 종료나 오류 시 자동으로 lock 해제 (no zombie locks)
    - **Three-way merge 보호**: 충돌 해결 중 다른 변경 방지
    - **Schema 정합성**: Breaking change 검증 중 동시 수정 차단
    - Redis와 달리 TTL 만료로 인한 중간 해제 위험 없음

#### Architecture Decisions (ADRs)

- **ADR-005**: Naming Convention Strategy
  - Database uses camelCase for JSON compatibility
  - Python code uses snake_case per PEP-8
  - Automatic conversion at boundaries
  - Prevents naming conflicts across systems

---

## 3. Technology Stack

### Core Technologies

| Component | Technology | Version | Purpose | Why This Choice |
|-----------|------------|---------|---------|------------------|
| Language | Python | 3.9+ | Primary development language | Async support, type hints, rich ecosystem |
| Web Framework | FastAPI | 0.104.1 | High-performance async web framework | Auto-documentation, async native, high performance |
| ASGI Server | Uvicorn | 0.24.0 | Production ASGI server | Fast, supports HTTP/2, WebSocket |
| Primary Database | TerminusDB | Latest | Graph database for ontologies | Built-in version control, perfect for relationships |
| Cache | Redis | 5.0.1 | Distributed caching | High performance, pub/sub support |
| Lock Manager | PostgreSQL | 13+ | Distributed locking | Advisory locks, transactional safety |
| Message Broker | NATS | 2.6.0 | Event streaming and pub/sub | Lightweight, cloud-native, JetStream persistence |
| GraphQL | Strawberry | 0.209.0 | GraphQL implementation | Type-safe, async support, DataLoader |
| Authentication | PyJWT | 2.8.0 | Token-based authentication | Industry standard, flexible claims |
| Monitoring | Prometheus | 0.19.0 | Metrics collection | Time-series data, PromQL, Kubernetes native |
| Tracing | OpenTelemetry | 1.21.0 | Distributed tracing | Vendor-neutral, comprehensive instrumentation |
| Task Queue | Celery | 5.3.4 | Async task processing | Distributed, reliable, monitoring support |
| HTTP Client | httpx | 0.25.2 | Async HTTP client | Async support, connection pooling |
| Database ORM | SQLAlchemy | 2.0.23 | SQL database toolkit | Async support, powerful ORM |
| Validation | Pydantic | 2.5.2 | Data validation | Fast, type-safe, JSON Schema generation |

### Development Tools

- **Poetry**: Dependency management
- **Black**: Code formatting
- **isort**: Import sorting
- **mypy**: Static type checking
- **ruff**: Fast Python linter
- **pytest**: Testing framework

---

## 4. Project Structure

```
ontology-management-system/
├── api/                    # API Layer
│   ├── v1/                # REST API v1 
│   │   ├── audit_routes.py          # 감사 로그 API ✅
│   │   ├── batch_routes.py          # 배치 작업 API ✅
│   │   ├── branch_lock_routes.py    # 브랜치 잠금 API ✅
│   │   ├── idempotent_routes.py     # 멱등성 API ✅
│   │   ├── issue_tracking_routes.py # 이슈 관리 API ✅
│   │   ├── shadow_index_routes.py   # 샘도우 인덱싱 API ✅
│   │   ├── version_routes.py        # 버전 관리 API ✅
│   │   └── schema_generation/       # SDK 생성 엔드포인트
│   ├── graphql/           # GraphQL API
│   │   ├── main.py       # GraphQL app setup
│   │   ├── schema.py     # Type definitions
│   │   ├── resolvers.py  # Query/Mutation resolvers
│   │   ├── subscriptions.py # Real-time subscriptions
│   │   └── dataloader.py    # N+1 query prevention
│   └── gateway/           # API Gateway
│       ├── main.py       # Gateway server
│       └── middleware.py # Gateway middleware stack
│
├── core/                  # Business Logic
│   ├── schema/           # Schema management ✅
│   │   ├── service.py        # Main schema operations
│   │   ├── service.py        # 스키마 서비스 구현
│   │   │   # ⚠️ main.py는 service_fixed.py를 import하지만 파일이 없음!
│   │   ├── registry.py       # Schema registry
│   │   ├── conflict_resolver.py # Merge conflicts
│   │   └── shadow_index_manager.py # Performance
│   ├── validation/       # Validation engine ⚠️ (코드는 있지만 사용 안됨)
│   │   ├── service.py            # main.py에서 None으로 설정
│   │   ├── service_refactored.py # Clean architecture
│   │   ├── rules/               # Validation rules
│   │   │   ├── breaking_change.py
│   │   │   ├── type_compatibility.py
│   │   │   ├── required_field.py
│   │   │   └── data_impact_analyzer.py
│   │   ├── adapters.py     # External adapters
│   │   ├── ports.py        # Interface definitions
│   │   └── migration_planner.py # Migration strategies
│   ├── branch/           # Branch management (리팩토링됨)
│   │   ├── service.py                  # Branch operations
│   │   ├── three_way_merge.py          # Git-style merging
│   │   ├── distributed_lock_manager.py # PostgreSQL advisory locks
│   │   ├── conflict_resolver.py        # Merge conflict resolution
│   │   ├── diff_engine.py              # Diff 계산 엔진
│   │   ├── merge_strategies.py         # Squash/Rebase 전략
│   │   ├── models.py                   # Domain models
│   │   │
│   │   │   # Lock management (모듈화됨)
│   │   ├── lock_manager.py             # Lock orchestrator (399줄)
│   │   ├── lock_manager_core.py        # Core locking logic
│   │   ├── lock_state_manager.py       # State management
│   │   ├── lock_heartbeat_service.py   # Heartbeat monitoring
│   │   └── lock_cleanup_service.py     # Cleanup operations
│   ├── audit/            # Audit logging
│   │   ├── audit_service.py     # Audit operations
│   │   └── audit_publisher.py   # Event publishing
│   ├── event_publisher/  # Event system
│   │   ├── service.py           # Main publisher
│   │   ├── nats_publisher.py    # NATS integration
│   │   ├── outbox_service.py    # Outbox pattern
│   │   └── change_detector.py   # Change detection
│   ├── iam/              # Identity & Access
│   │   └── iam_integration.py   # IAM service client
│   ├── issue_tracking/   # Issue management
│   │   └── issue_service.py     # Issue operations
│   └── health/           # Health checks
│       └── health_checker.py     # Service health
│   └── health/          # Health checks
│
├── database/            # Data Access Layer
│   ├── clients/
│   │   └── terminus_db.py
│   ├── migrations/
│   └── redis_ha.py
│
├── models/              # Domain Models
│   ├── domain.py       # Core domain entities
│   ├── semantic_types.py
│   ├── struct_types.py
│   └── permissions.py
│
├── middleware/          # HTTP Middleware
│   ├── auth.py
│   ├── rate_limiter.py
│   ├── circuit_breaker.py
│   └── etag.py
│
├── shared/              # Shared Utilities
│   ├── config.py       # Configuration
│   ├── exceptions.py   # Custom exceptions
│   ├── cache/          # Caching utilities
│   └── events/         # Event utilities
│
├── infrastructure/      # Infrastructure Code
│   ├── aws/            # AWS integrations
│   ├── kubernetes/     # K8s manifests
│   └── terraform/      # IaC definitions
│
├── scripts/            # Utility Scripts
├── tests/              # ❌ 디렉토리 자체가 없음!
├── monitoring/         # Monitoring Config
├── main.py             # 기본 Entry Point ✅
├── main_secure.py      # 보안 강화 Entry Point ✅
└── docs/              # Documentation
```

---

## 5. Core Concepts

### Understanding the Naming Convention (Critical!)

**IMPORTANT**: This system uses a dual naming convention strategy (ADR-005) that you MUST understand:

1. **Database/API Layer**: Uses `camelCase` (TerminusDB/JSON-LD standard)
   - Example: `objectTypeId`, `displayName`, `isRequired`

2. **Python Domain Models**: Uses `snake_case` (PEP-8 standard)
   - Example: `object_type_id`, `display_name`, `is_required`

3. **Conversion**: Automatic conversion happens at service boundaries
   - Database → Python: `from_document()` methods convert camelCase to snake_case
   - Python → Database: `to_document()` methods convert snake_case to camelCase

```python
# Example of naming convention in action
# Database document (camelCase)
{
    "objectTypeId": "obj_123",
    "displayName": "Customer",
    "isRequired": true
}

# Python domain model (snake_case)
class Property:
    object_type_id: str
    display_name: str 
    is_required: bool
```

### Domain Model

#### ObjectType
Represents an entity in the ontology (e.g., Person, Product, Order). Think of it as a "class" or "table" in traditional systems.

```python
class ObjectType(BaseModel):
    """Core entity definition in the ontology"""
    id: str                           # Unique identifier (e.g., "obj_customer")
    name: str                         # Technical name (e.g., "Customer")
    display_name: str                 # User-friendly name (e.g., "Customer Record")
    description: Optional[str]        # Detailed explanation of purpose
    category: Optional[str]           # Grouping (e.g., "core", "reference")
    source: Optional[str]             # Origin system (e.g., "salesforce")
    type_class: TypeClass             # OBJECT, INTERFACE, LINK, EMBEDDED
    status: Status                    # ACTIVE, EXPERIMENTAL, DEPRECATED
    version_hash: str                 # Content hash for change detection
    created_at: datetime
    modified_at: datetime
    
    # Relationships
    properties: List[Property] = []   # Fields/attributes
    links: List[LinkType] = []        # Relationships to other types
    interfaces: List[str] = []        # Implemented interfaces
    
    # Advanced features
    indexes: List[Index] = []         # Performance optimization
    constraints: List[Constraint] = [] # Business rules
    triggers: List[Trigger] = []      # Event handlers
```

#### Property
Attributes of an ObjectType. These are the "fields" or "columns" that hold data.

```python
class Property(BaseModel):
    """Field definition with rich type system"""
    # Identity
    id: str                           # Unique identifier
    object_type_id: str               # Parent ObjectType
    name: str                         # Field name (validated: ^[a-zA-Z][a-zA-Z0-9_]*$)
    display_name: str                 # User-friendly label
    description: Optional[str]        # Help text
    
    # Type System
    data_type_id: str                 # Basic type (string, integer, etc.)
    semantic_type_id: Optional[str]   # Semantic meaning (email, phone, url)
    struct_type_id: Optional[str]     # Complex type (address, money)
    
    # Validation & Constraints
    is_required: bool = False         # Must have value
    is_primary_key: bool = False      # Unique identifier
    is_indexed: bool = False          # Create database index
    is_unique: bool = False           # Enforce uniqueness
    is_searchable: bool = False       # Full-text searchable
    is_array: bool = False            # Multiple values allowed
    is_encrypted: bool = False        # Encrypt at rest
    
    # Behavior
    default_value: Optional[Any]      # Default if not provided
    enum_values: Optional[List[str]]  # Allowed values for enums
    reference_type: Optional[str]     # For reference fields
    validation_rules: Dict[str, Any]  # Custom validation
    
    # UI Hints
    sort_order: int = 0               # Display order
    visibility: Visibility            # VISIBLE, HIDDEN, ADVANCED
    ui_hints: Dict[str, Any]          # Widget type, placeholder, etc.
    
    # Audit
    version_hash: str                 # Content hash
    created_at: datetime
    modified_at: datetime
```

#### LinkType
Relationships between ObjectTypes. Defines how entities relate to each other.

```python
class LinkType(BaseModel):
    """Relationship definition between ObjectTypes"""
    id: str
    name: str                         # Relationship name
    display_name: str
    description: Optional[str]
    
    # Relationship Definition
    source_type_id: str               # From ObjectType
    target_type_id: str               # To ObjectType
    cardinality: Cardinality          # ONE_TO_ONE, ONE_TO_MANY, MANY_TO_MANY
    directionality: Directionality    # UNIDIRECTIONAL, BIDIRECTIONAL
    
    # Behavior
    is_required: bool = False         # Must have at least one
    cascade_delete: bool = False      # Delete related on parent delete
    inverse_name: Optional[str]       # Name from target perspective
    
    # Constraints
    min_items: Optional[int]          # Minimum related items
    max_items: Optional[int]          # Maximum related items
    
    # Performance
    is_indexed: bool = True           # Index for fast lookup
    eager_load: bool = False          # Load with parent
```

### Version Control Concepts

#### Branch
Isolated development environment for schema changes. Works like Git branches.

```python
class Branch(BaseModel):
    """Schema development branch"""
    id: str                           # Unique identifier
    name: str                         # Branch name (e.g., "feature/add-customer-email")
    base_branch: str                  # Parent branch (usually "main")
    
    # Metadata
    created_by: str                   # User who created
    created_at: datetime
    description: Optional[str]        # Purpose of branch
    
    # Status
    status: BranchStatus              # ACTIVE, MERGED, ARCHIVED, LOCKED
    merged_at: Optional[datetime]
    merged_by: Optional[str]
    
    # Protection
    protection_rules: List[BranchProtectionRule]
    is_locked: bool = False           # Prevent all changes
    lock_reason: Optional[str]
    
    # Conflict Management
    has_conflicts: bool = False
    conflict_details: Optional[Dict]
```

#### Schema Version
Point-in-time snapshot of schema state. Every change creates a new version.

```python
class SchemaVersion(BaseModel):
    """Immutable schema snapshot"""
    id: str                           # Version ID
    branch_id: str                    # Branch context
    version_number: int               # Sequential version
    
    # Change Information
    changes: List[SchemaChange]       # What changed
    change_summary: str               # Human-readable summary
    breaking_changes: List[BreakingChange]
    
    # Metadata
    author: str                       # Who made the change
    timestamp: datetime               # When it happened
    commit_message: str               # Why it was done
    
    # Validation Results
    validation_status: ValidationStatus
    validation_errors: List[ValidationError]
    
    # Content Hash
    content_hash: str                 # For integrity verification
    parent_hash: Optional[str]        # Previous version hash
```

### Validation System

#### Breaking Change Detection
The system automatically detects changes that would break existing systems:

```python
# Examples of breaking changes
1. Removing a required field
   Before: {"email": {"required": true}}
   After: Field removed → BREAKING!

2. Changing field type incompatibly
   Before: {"age": {"type": "integer"}}
   After: {"age": {"type": "string"}} → BREAKING!

3. Making optional field required
   Before: {"phone": {"required": false}}
   After: {"phone": {"required": true}} → BREAKING!

4. Removing enum values
   Before: {"status": {"enum": ["active", "inactive", "pending"]}}
   After: {"status": {"enum": ["active", "inactive"]}} → BREAKING!
```

#### Type Compatibility Rules
The system understands safe type transitions:

```python
# Safe type changes (non-breaking)
- integer → float      # Numbers can widen
- string → text        # Short to long strings
- enum + new values    # Adding options is safe

# Unsafe type changes (breaking)
- float → integer      # Loss of precision
- string → integer     # Type mismatch
- text → string[50]    # Length restriction
```

#### Data Impact Analysis
Before applying changes, the system analyzes impact:

```python
class DataImpactReport(BaseModel):
    """Analysis of how schema changes affect existing data"""
    # Scope
    total_records_affected: int
    percentage_affected: float
    
    # By change type
    records_needing_migration: int
    records_with_data_loss: int
    records_with_validation_errors: int
    
    # Performance impact
    indexes_to_rebuild: List[str]
    estimated_migration_time: timedelta
    required_downtime: bool
    
    # Recommendations
    migration_strategy: MigrationStrategy
    rollback_plan: Dict[str, Any]
```

### Advanced Features

#### Schema Freeze
Lock schemas during critical periods:

```python
class SchemaFreeze(BaseModel):
    """Temporary lock on schema modifications"""
    id: str
    branch_pattern: str               # Which branches to freeze
    start_time: datetime
    end_time: datetime
    reason: str                       # e.g., "Black Friday freeze"
    created_by: str
    
    # Exceptions
    allowed_users: List[str]          # Who can still modify
    allowed_operations: List[str]     # What's still permitted
```

#### Shadow Indexing
Performance optimization without downtime:

```python
class ShadowIndex(BaseModel):
    """Background index creation"""
    id: str
    object_type_id: str
    property_names: List[str]
    
    # Status
    status: IndexStatus               # BUILDING, READY, FAILED
    progress_percentage: float
    
    # Performance metrics
    estimated_completion: datetime
    rows_processed: int
    rows_per_second: float
```

### Lock Management Architecture

#### Modular Lock System
The lock management system has been refactored into focused modules:

1. **Lock Manager Core** (`lock_manager_core.py`)
   - Core locking operations
   - Conflict detection logic
   - Lock timeout management
   - In-memory lock storage

2. **Lock State Manager** (`lock_state_manager.py`)
   - Branch state persistence
   - State transitions (ACTIVE → LOCKED_FOR_WRITE → READY)
   - Cache management (Redis + in-memory)
   - Transition validation

3. **Lock Heartbeat Service** (`lock_heartbeat_service.py`)
   - Distributed lock health monitoring
   - Heartbeat tracking and expiration
   - Service liveness detection
   - Health status reporting

4. **Lock Cleanup Service** (`lock_cleanup_service.py`)
   - TTL-based lock expiration
   - Heartbeat-based cleanup
   - Batch processing for performance
   - Cleanup statistics

5. **Lock Manager Orchestrator** (`lock_manager.py`)
   - Coordinates all lock services
   - Provides unified API
   - Handles complex workflows
   - Global instance management

#### Lock Types and Scopes

```python
class LockType(Enum):
    INDEXING = "indexing"        # For data indexing operations
    MAINTENANCE = "maintenance"  # For maintenance tasks
    MIGRATION = "migration"      # For schema migrations
    BACKUP = "backup"           # For backup operations
    MANUAL = "manual"           # For manual locks

class LockScope(Enum):
    BRANCH = "branch"           # Lock entire branch
    RESOURCE_TYPE = "type"      # Lock specific resource type
    RESOURCE = "resource"       # Lock individual resource
```

#### Distributed Lock with PostgreSQL

```python
# PostgreSQL Advisory Lock usage
async with distributed_lock("branch:main", timeout_ms=5000):
    # Perform atomic operations
    # Lock automatically released on completion or error
```

---

## 6. Development Setup

### Prerequisites

- Python 3.9+
- Docker & Docker Compose
- Redis (via Docker)
- TerminusDB (via Docker)
- NATS (via Docker)

### Quick Start

```bash
# Clone the repository
git clone <repository-url>
cd ontology-management-system

# Install dependencies
pip install -r requirements.txt
# OR if using Poetry:
pip install poetry
poetry install

# Start ALL infrastructure services
docker-compose up -d

# Wait for services to be ready (important!)
sleep 30

# Initialize databases
python scripts/init_databases.py

# Run the application (두 가지 선택사항)
# Option 1: main.py 수정 후 실행
# 먼저 import 오류 수정 필요!
# Line 17: from core.schema.service_fixed → from core.schema.service
# Line 338: rbac_test_routes import 제거
uvicorn main:app --reload --port 8002  # main.py는 8002 포트 사용

# Option 2: main_secure.py 실행 (수정 없이 실행 가능)
export JWT_SECRET="your-secret"
export USER_SERVICE_URL="http://localhost:18002"
export AUDIT_SERVICE_URL="http://localhost:28002"
uvicorn main_secure:app --reload --port 8002

# Verify health
curl http://localhost:8000/health

# 현재 상태 확인
curl http://localhost:8000/health/detailed  # 인증 필요
```

### Development Workflow

```bash
# 현재 작동하는 워크플로우 (main.py 수정 후 또는 main_secure.py 사용 시):

# 1. 브랜치에서 스키마 조회 (✅ 작동)
curl http://localhost:8002/api/v1/schemas/main/object-types

# 2. 새 ObjectType 생성 (✅ 작동)
curl -X POST http://localhost:8002/api/v1/schemas/main/object-types \
  -H "Content-Type: application/json" \
  -d '{"name": "Customer", "displayName": "Customer Record"}'

# 3. 브랜치 잠금 (✅ 작동)
curl -X POST http://localhost:8002/api/v1/branch-locks \
  -H "Content-Type: application/json" \
  -d '{"branchName": "main", "reason": "Critical update", "ttl": 3600}'

# 4. 이슈 생성 (✅ 작동)
curl -X POST http://localhost:8002/api/v1/issues \
  -H "Content-Type: application/json" \
  -d '{"title": "Add email field", "description": "Need email for customers"}'

# 5. 섀도우 인덱스 생성 (✅ 작동)
curl -X POST http://localhost:8002/api/v1/shadow-indexes \
  -H "Content-Type: application/json" \
  -d '{"indexName": "customer_email_idx", "objectType": "Customer", "properties": ["email"]}'

# 미구현 기능들:
# - 브랜치 생성/병합 (❌ BranchService = None)
# - 검증 (❌ ValidationService = None)
# - 속성 관리 (❌ API 없음)
# - 히스토리 (❌ HistoryService = None)
```

### Environment Configuration

Create a `.env` file:

```env
# Application
ONTOLOGY_ENVIRONMENT=development
ONTOLOGY_DEBUG=true
ONTOLOGY_SERVICE_NAME=ontology-management-system
ONTOLOGY_SERVICE_VERSION=3.0.0

# Security
ONTOLOGY_SECRET_KEY=your-secret-key-here
ONTOLOGY_JWT_ALGORITHM=HS256
ONTOLOGY_JWT_EXPIRATION_MINUTES=30

# Authentication Mode
USE_MSA_AUTH=false  # Set to true for microservices auth
IAM_SERVICE_URL=http://localhost:8001  # If using MSA

# Database
ONTOLOGY_DATABASE_URL=http://localhost:6363
ONTOLOGY_DATABASE_USERNAME=admin
ONTOLOGY_DATABASE_PASSWORD=root
TERMINUSDB_URL=http://terminusdb:6363  # Docker internal

# Redis
ONTOLOGY_REDIS_URL=redis://localhost:6379
ONTOLOGY_REDIS_PREFIX=ontology:
REDIS_URL=redis://redis:6379  # Docker internal

# NATS
NATS_URL=nats://localhost:4222

# Monitoring
PROMETHEUS_PORT=9090
JAEGER_ENDPOINT=http://localhost:14268/api/traces

# Features
GRAPHQL_ENABLED=true
ENABLE_ISSUE_TRACKING=true
ENABLE_SHADOW_INDEXING=true
```

### Common Configuration Issues

1. **Database Connection Failed**
   ```bash
   # Check TerminusDB is running
   docker ps | grep terminusdb
   
   # Test connection
   curl http://localhost:6363/api/status
   ```

2. **Redis Connection Failed**
   ```bash
   # Check Redis is running
   docker ps | grep redis
   
   # Test connection
   redis-cli ping
   ```

3. **Port Already in Use**
   ```bash
   # Find process using port 8000
   lsof -i :8000
   
   # Use different port
   uvicorn main:app --port 8080
   ```

### IDE Setup

#### VS Code
```json
{
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "python.formatting.provider": "black",
  "python.pythonPath": ".venv/bin/python",
  "editor.formatOnSave": true
}
```

#### PyCharm
1. Set Python interpreter to Poetry environment
2. Enable Black formatter
3. Configure mypy for type checking

---

## 7. API Reference

### REST API Overview

**IMPORTANT**: All schema operations are branch-scoped. You must specify the branch in the URL.

### Base URLs
- Local Development: `http://localhost:8002`  # main.py가 8002 포트 사용!
- API v1: `http://localhost:8002/api/v1`
- GraphQL: `http://localhost:8002/graphql`
- Health: `http://localhost:8002/health`

### Authentication

> **⚠️ 주의**: 현재 인증 엔드포인트가 구현되지 않았습니다. 개발 환경에서는 인증이 비활성화되어 있을 수 있습니다.

All API requests (except health checks) require authentication:

```http
Authorization: Bearer <your-jwt-token>
```

토큰 획득 (미구현):
```bash
# /auth/login 엔드포인트가 없습니다.
# 개발 시 테스트 토큰을 사용하거나 인증을 비활성화하세요.
```

### Schema Management Endpoints

> **⚠️ 주의**: 현재 실제로 구현된 API는 아래 두 개뿐입니다. 나머지는 계획된 기능입니다.

#### List Object Types ✅
```http
GET /api/v1/schemas/{branch}/object-types

Example:
GET /api/v1/schemas/main/object-types

Response:
{
  "objectTypes": [
    {
      "id": "obj_customer",
      "name": "Customer",
      "displayName": "Customer Record",
      "description": "Customer information",
      "status": "active"
    }
  ],
  "branch": "main",
  "source": "real_database"  // 'real_database' = 실제 DB, 'mock' = 가짜 데이터
}
```

#### Create Object Type ✅
```http
POST /api/v1/schemas/{branch}/object-types
Content-Type: application/json

{
  "name": "Customer",
  "displayName": "Customer Record",
  "description": "Store customer information"
}

Response:
{
  "objectType": {
    "id": "obj_customer_123",
    "name": "Customer",
    "displayName": "Customer Record",
    "versionHash": "abc123..."
  },
  "source": "real_database"
}
```

#### Get Object Type Properties ❌ (미구현)
```http
GET /api/v1/schemas/{branch}/object-types/{objectTypeId}/properties

Example:
GET /api/v1/schemas/main/object-types/obj_customer/properties

# 현재 이 엔드포인트는 구현되지 않았습니다.
```

#### Add Property to Object Type ❌ (미구현)
```http
POST /api/v1/schemas/{branch}/object-types/{objectTypeId}/properties
Content-Type: application/json

{
  "name": "email",
  "displayName": "Email Address",
  "dataType": "string",
  "semanticType": "email",
  "isRequired": true,
  "isUnique": true,
  "isIndexed": true
}

# 현재 이 엔드포인트는 구현되지 않았습니다.
```

### Branch Management

#### Branch Lock Management ✅ (실제 구현됨)
```http
# 브랜치 잠금 확득
POST /api/v1/branch-locks
Content-Type: application/json

{
  "branchName": "feature/critical-update",
  "reason": "Performing schema migration",
  "ttl": 3600  // 초 단위 잠금 시간
}

# 잠금 해제  
DELETE /api/v1/branch-locks/{lockId}

# 현재 잠금 목록 조회
GET /api/v1/branch-locks
```

#### List Branches ❌ (미구현)
```http
GET /api/v1/branches

# BranchService가 None으로 설정되어 있어 작동하지 않습니다.
```

#### Create Branch ❌ (미구현)
```http
POST /api/v1/branches

# BranchService가 None으로 설정되어 있어 작동하지 않습니다.
```

#### Merge Branch ❌ (미구현)
```http
POST /api/v1/branches/{branchName}/merge

# BranchService가 None으로 설정되어 있어 작동하지 않습니다.
```

### Actually Implemented Endpoints ✅

#### Audit Log
```http
GET /api/v1/audit
GET /api/v1/audit/{auditId}

# 감사 로그 조회
```

#### Issue Tracking  
```http
GET /api/v1/issues
POST /api/v1/issues
GET /api/v1/issues/{issueId}
PUT /api/v1/issues/{issueId}
DELETE /api/v1/issues/{issueId}

# 이슈 관리 시스템
```

#### Version Tracking
```http
GET /api/v1/versions
GET /api/v1/versions/{versionId}

# 버전 추적
```

#### Shadow Index Management
```http
GET /api/v1/shadow-indexes
POST /api/v1/shadow-indexes
GET /api/v1/shadow-indexes/{indexId}
POST /api/v1/shadow-indexes/{indexId}/rebuild

# 무중단 인덱싱
```

#### Batch Operations
```http
POST /api/v1/batch/load

# GraphQL DataLoader를 위한 배치 로드
```

### Validation Endpoints ❌ (미구현)

#### Validate Schema Changes
```http
POST /api/v1/validation/check

# ValidationService가 None으로 설정되어 있어 작동하지 않습니다.
}

Response:
{
  "isValid": false,
  "breakingChanges": [
    {
      "type": "REQUIRED_FIELD_REMOVED",
      "severity": "error",
      "objectType": "Customer",
      "property": "email",
      "message": "Cannot remove required field 'email' - 1,234 records would be affected",
      "dataImpact": {
        "affectedRecords": 1234,
        "percentageAffected": 100
      }
    }
  ],
  "warnings": [],
  "migrationPlan": null
}
```

### Audit & History

#### Get Audit Log
```http
GET /api/v1/audit?startDate=2024-01-01&endDate=2024-01-31&objectType=Customer

Response:
{
  "events": [
    {
      "id": "evt_123",
      "timestamp": "2024-01-15T10:30:00Z",
      "user": "admin@example.com",
      "action": "schema.property.add",
      "resource": "Customer.email",
      "branch": "feature/customer-email",
      "details": {
        "propertyName": "email",
        "dataType": "string",
        "isRequired": true
      },
      "ipAddress": "192.168.1.100"
    }
  ],
  "pagination": {
    "page": 1,
    "pageSize": 50,
    "totalCount": 123
  }
}
```

### Issue Tracking

#### Create Issue
```http
POST /api/v1/issues
Content-Type: application/json

{
  "title": "Add email validation to Customer",
  "description": "Customer email should validate format",
  "objectTypeId": "obj_customer",
  "propertyName": "email",
  "priority": "high",
  "labels": ["validation", "customer"]
}
```

### Batch Operations

#### Batch Load (for GraphQL DataLoader)
```http
POST /api/v1/batch/load
Content-Type: application/json

{
  "requests": [
    {"type": "objectType", "id": "obj_customer"},
    {"type": "objectType", "id": "obj_order"},
    {"type": "property", "id": "prop_email"}
  ]
}
```

### GraphQL API

The GraphQL API provides a more flexible way to query and manipulate schemas. Available at `http://localhost:8000/graphql`.

#### Query Examples

**Get Object Type with Properties**
```graphql
query GetObjectType($branch: String!, $objectTypeId: ID!) {
  objectType(branch: $branch, id: $objectTypeId) {
    id
    name
    displayName
    description
    status
    properties {
      id
      name
      displayName
      dataType {
        id
        name
        baseType
      }
      semanticType {
        id
        name
        validationPattern
      }
      isRequired
      isUnique
      isIndexed
    }
    links {
      id
      name
      targetType {
        id
        name
      }
      cardinality
    }
  }
}
```

**Search Object Types**
```graphql
query SearchObjectTypes($branch: String!, $query: String!) {
  searchObjectTypes(branch: $branch, query: $query) {
    results {
      id
      name
      displayName
      matchScore
      matchedFields
    }
    totalCount
  }
}
```

#### Mutation Examples

**Create Object Type with Properties**
```graphql
mutation CreateObjectType($branch: String!, $input: ObjectTypeInput!) {
  createObjectType(branch: $branch, input: $input) {
    objectType {
      id
      name
      versionHash
    }
    validationResults {
      isValid
      warnings
    }
  }
}

# Variables:
{
  "branch": "feature/new-customer",
  "input": {
    "name": "Customer",
    "displayName": "Customer Record",
    "properties": [
      {
        "name": "email",
        "displayName": "Email Address",
        "dataTypeId": "dt_string",
        "semanticTypeId": "st_email",
        "isRequired": true,
        "isUnique": true
      }
    ]
  }
}
```

#### Subscription Examples

**Real-time Schema Changes**
```graphql
subscription OnSchemaChanges($branch: String!) {
  schemaChanges(branch: $branch) {
    eventType  # CREATED, UPDATED, DELETED
    objectType {
      id
      name
      modifiedBy
      modifiedAt
    }
    changedProperties {
      propertyName
      changeType
      oldValue
      newValue
    }
  }
}
```

**Validation Results Stream**
```graphql
subscription ValidationProgress($validationId: ID!) {
  validationProgress(id: $validationId) {
    progress
    currentStep
    totalSteps
    currentObjectType
    errors {
      type
      message
      severity
    }
  }
}
```

#### DataLoader Support

The GraphQL API uses DataLoader to batch and cache requests:

```graphql
# This query will batch-load all referenced types
query EfficientQuery($branch: String!) {
  objectTypes(branch: $branch) {
    id
    properties {  # Batched
      dataType {  # Batched
        name
      }
      semanticType {  # Batched
        name
      }
    }
  }
}
```

### Error Responses

The API uses consistent error formatting across all endpoints:

#### Standard Error Format
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Schema validation failed",
    "details": [
      {
        "field": "properties.email.semantic_type",
        "issue": "Invalid semantic type 'email-address'. Use 'email'",
        "suggestion": "Available semantic types: email, url, phone"
      }
    ],
    "request_id": "req_123456",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

#### Common Error Codes

| Code | HTTP Status | Description | Example |
|------|-------------|-------------|----------|
| `VALIDATION_ERROR` | 400 | Input validation failed | Invalid property name format |
| `BREAKING_CHANGE` | 400 | Operation would break compatibility | Removing required field |
| `AUTHENTICATION_REQUIRED` | 401 | No valid auth token | Missing or expired token |
| `PERMISSION_DENIED` | 403 | Insufficient permissions | Can't modify protected branch |
| `NOT_FOUND` | 404 | Resource doesn't exist | Unknown object type ID |
| `CONFLICT` | 409 | Resource conflict | Duplicate property name |
| `BRANCH_LOCKED` | 423 | Branch is locked | Another user has lock |
| `RATE_LIMITED` | 429 | Too many requests | Exceeded 100 req/min |
| `INTERNAL_ERROR` | 500 | Server error | Database connection failed |
| `SERVICE_UNAVAILABLE` | 503 | Service down | TerminusDB offline |

#### Error Details Structure

```typescript
interface ErrorDetail {
  field?: string;        // Specific field that caused error
  issue: string;         // What went wrong
  suggestion?: string;   // How to fix it
  code?: string;         // Specific error code
  metadata?: any;        // Additional context
}
```

#### Validation Error Example

```json
{
  "error": {
    "code": "BREAKING_CHANGE",
    "message": "Cannot apply changes - breaking changes detected",
    "details": [
      {
        "field": "Customer.email",
        "issue": "Cannot remove required field",
        "metadata": {
          "affectedRecords": 15234,
          "percentageAffected": 100,
          "severity": "critical"
        },
        "suggestion": "Mark field as deprecated instead of removing"
      },
      {
        "field": "Customer.age",
        "issue": "Type change from integer to string is incompatible",
        "metadata": {
          "currentType": "integer",
          "newType": "string",
          "dataLossRisk": true
        },
        "suggestion": "Create new field and migrate data"
      }
    ],
    "request_id": "req_789012"
  }
}
```

---

## 8. Database Schema

### Database Architecture

#### TerminusDB Structure

TerminusDB stores data as JSON-LD documents with graph relationships. Each database has multiple named graphs:

- **Instance Graph**: Actual data (object types, properties, etc.)
- **Schema Graph**: Meta-schema defining allowed structures
- **Inference Graph**: Derived relationships and computed properties

#### Core Collections

**ObjectType Collection**
```json
{
  "@id": "ObjectType/Customer",
  "@type": "ObjectType",
  "name": "Customer",
  "displayName": "Customer Record",
  "description": "Customer information",
  "typeClass": "object",
  "status": "active",
  "versionHash": "sha256:abc123...",
  "properties": [
    {"@id": "Property/Customer.email", "@type": "@id"},
    {"@id": "Property/Customer.name", "@type": "@id"}
  ],
  "createdAt": "2024-01-01T00:00:00Z",
  "modifiedAt": "2024-01-15T10:30:00Z"
}
```

**Property Collection**
```json
{
  "@id": "Property/Customer.email",
  "@type": "Property",
  "objectTypeId": "ObjectType/Customer",
  "name": "email",
  "displayName": "Email Address",
  "dataTypeId": "DataType/string",
  "semanticTypeId": "SemanticType/email",
  "isRequired": true,
  "isUnique": true,
  "isIndexed": true,
  "validationRules": {
    "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
    "maxLength": 255
  },
  "versionHash": "sha256:def456..."
}
```

**Branch Collection**
```json
{
  "@id": "Branch/feature-add-customer-phone",
  "@type": "Branch",
  "name": "feature/add-customer-phone",
  "baseBranch": {"@id": "Branch/main", "@type": "@id"},
  "status": "active",
  "description": "Add phone number to customer",
  "createdBy": "user@example.com",
  "createdAt": "2024-01-15T09:00:00Z",
  "commits": [
    {"@id": "Commit/abc123", "@type": "@id"}
  ]
}
```

**Audit Event Collection**
```json
{
  "@id": "AuditEvent/evt_20240115_103000_abc123",
  "@type": "AuditEvent",
  "timestamp": "2024-01-15T10:30:00Z",
  "action": "property.create",
  "resource": "Property/Customer.phone",
  "branch": "Branch/feature-add-customer-phone",
  "user": "admin@example.com",
  "ipAddress": "192.168.1.100",
  "userAgent": "Mozilla/5.0...",
  "changes": {
    "before": null,
    "after": {
      "name": "phone",
      "dataType": "string",
      "semanticType": "phone"
    }
  },
  "metadata": {
    "requestId": "req_123456",
    "sessionId": "sess_789012",
    "apiVersion": "v1"
  }
}
```

#### Additional Databases

**SQLite - Issue Tracking**
```sql
-- issue_tracking.db schema
CREATE TABLE issues (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT,
  object_type_id TEXT,
  property_name TEXT,
  status TEXT DEFAULT 'open',
  priority TEXT DEFAULT 'medium',
  created_by TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE issue_comments (
  id TEXT PRIMARY KEY,
  issue_id TEXT REFERENCES issues(id),
  comment TEXT NOT NULL,
  author TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**SQLite - Idempotent Consumer**
```sql
-- idempotent_consumer.db schema  
CREATE TABLE processed_events (
  event_id TEXT PRIMARY KEY,
  processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  handler TEXT NOT NULL,
  status TEXT NOT NULL,
  retry_count INTEGER DEFAULT 0
);
```

### Redis Key Patterns

Redis is used for caching, distributed locking, and session management:

```bash
# Schema Cache (TTL: 5 minutes)
ontology:schema:{branch}:{object_type_id} → ObjectType JSON
ontology:properties:{branch}:{object_type_id} → Properties Array

# Branch Locks (TTL: configurable, default 1 hour)  
ontology:lock:branch:{branch_name} → {
  "holder": "user@example.com",
  "acquired_at": "2024-01-15T10:00:00Z",
  "expires_at": "2024-01-15T11:00:00Z",
  "reason": "Performing schema migration"
}

# User Sessions (TTL: 30 minutes, refreshed on activity)
ontology:session:{session_id} → {
  "user_id": "user@example.com",
  "roles": ["developer", "reviewer"],
  "permissions": ["schema:read", "schema:write"],
  "created_at": "2024-01-15T10:00:00Z"
}

# Rate Limiting (TTL: 1 minute sliding window)
ontology:rate:{user_id}:{endpoint} → Request count
ontology:rate:global:{endpoint} → Global request count

# ETag Cache (TTL: 1 hour)
ontology:etag:{resource_type}:{resource_id} → {
  "etag": "W/\"abc123def456\"",
  "last_modified": "2024-01-15T10:30:00Z",
  "size": 2048
}

# Validation Results Cache (TTL: 10 minutes)
ontology:validation:{branch}:{validation_hash} → ValidationResult JSON

# Event Processing State
ontology:event:last_processed:{handler_name} → "evt_123456"
ontology:event:retry:{event_id} → Retry attempt count

# Distributed Locks (Various TTLs)
ontology:lock:merge:{branch_name} → Lock info
ontology:lock:validation:{validation_id} → Lock info
ontology:lock:index:{index_id} → Lock info

# Performance Metrics (TTL: 5 minutes)
ontology:metrics:api:{endpoint}:count → Request count
ontology:metrics:api:{endpoint}:latency → Average latency
ontology:metrics:cache:hit_rate → Cache hit percentage
```

### Cache Invalidation Strategy

1. **Write-through Cache**: Updates go to database first, then cache
2. **Cache-aside Pattern**: Application manages cache population
3. **TTL-based Expiration**: Automatic expiration for all cached data
4. **Event-based Invalidation**: Schema changes trigger cache clear

```python
# Example cache invalidation flow
def update_object_type(branch: str, object_type_id: str, data: dict):
    # 1. Update database
    db.update(object_type_id, data)
    
    # 2. Invalidate related caches
    redis.delete(f"ontology:schema:{branch}:{object_type_id}")
    redis.delete(f"ontology:properties:{branch}:{object_type_id}")
    
    # 3. Publish invalidation event
    publish_event("cache.invalidate", {
        "type": "object_type",
        "id": object_type_id,
        "branch": branch
    })
```

---

## 9. Event System

### Overview

The event system uses NATS JetStream for reliable event streaming with CloudEvents format for standardization. Events follow an "at-least-once" delivery guarantee with idempotent consumers.

### Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Service   │────▶│ Event Outbox │────▶│    NATS     │
│             │     │   (SQLite)   │     │  JetStream  │
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                 │
                    ┌──────────────┐             │
                    │  Consumers   │◀────────────┘
                    │ (Idempotent) │
                    └──────────────┘
```

### Event Flow

1. **Event Creation**: Service creates event with CloudEvents format
2. **Outbox Write**: Event written to SQLite outbox (transactional)
3. **Async Publish**: Background processor publishes to NATS
4. **Consumer Processing**: Subscribers process events idempotently
5. **Acknowledgment**: Consumer acks successful processing

### Event Categories

#### Schema Lifecycle Events

```python
# Event names follow pattern: {resource}.{action}
"objecttype.created"
"objecttype.updated" 
"objecttype.deleted"
"property.added"
"property.modified"
"property.removed"
"linktype.created"
"linktype.updated"
```

#### Validation Events

```python
"validation.started"
"validation.completed"
"validation.failed"
"breaking_change.detected"
"migration.required"
```

#### Branch Events

```python
"branch.created"
"branch.locked"
"branch.unlocked"
"branch.merged"
"branch.conflict_detected"
```

### CloudEvents Format

All events follow the CloudEvents 1.0 specification:

```json
{
  "specversion": "1.0",
  "id": "evt_20240115_103000_abc123",
  "source": "ontology-management-system",
  "type": "com.ontology.objecttype.created",
  "time": "2024-01-15T10:30:00Z",
  "datacontenttype": "application/json",
  "subject": "ObjectType/Customer",
  "data": {
    "objectTypeId": "obj_customer",
    "name": "Customer",
    "branch": "feature/add-customer",
    "author": "user@example.com",
    "versionHash": "sha256:abc123..."
  },
  "extensions": {
    "correlationid": "req_123456",
    "tenantid": "tenant_abc",
    "userid": "user@example.com"
  }
}
```

### Publishing Events

```python
from core.event_publisher import get_event_publisher
from cloudevents.http import CloudEvent

# Get publisher instance
publisher = get_event_publisher()

# Create CloudEvent
event = CloudEvent({
    "type": "com.ontology.objecttype.created",
    "source": "schema-service",
    "subject": f"ObjectType/{object_type_id}",
    "data": {
        "objectTypeId": object_type_id,
        "name": object_type.name,
        "branch": branch,
        "author": current_user.email,
        "changes": change_details
    }
})

# Publish (goes to outbox first)
await publisher.publish(event)
```

### Consuming Events

```python
from core.event_consumer import EventConsumer
from typing import Dict, Any

class SchemaIndexUpdater(EventConsumer):
    """Updates search index when schemas change"""
    
    def __init__(self):
        super().__init__(
            consumer_name="schema-index-updater",
            subscriptions=[
                "com.ontology.objecttype.*",
                "com.ontology.property.*"
            ]
        )
    
    async def process_event(self, event: CloudEvent) -> None:
        """Process event idempotently"""
        
        # Check if already processed
        if await self.is_processed(event.id):
            logger.info(f"Event {event.id} already processed")
            return
        
        # Process based on event type
        if event.type == "com.ontology.objecttype.created":
            await self._index_object_type(event.data)
        elif event.type == "com.ontology.property.added":
            await self._update_property_index(event.data)
        
        # Mark as processed
        await self.mark_processed(event.id)
    
    async def _index_object_type(self, data: Dict[str, Any]):
        """Add object type to search index"""
        await search_service.index({
            "id": data["objectTypeId"],
            "name": data["name"],
            "type": "object_type"
        })
```

### Event Reliability Features

#### Outbox Pattern

```python
class EventOutbox:
    """Ensures events are published even if NATS is down"""
    
    async def store_event(self, event: CloudEvent) -> None:
        """Store event in SQLite outbox"""
        async with self.db.transaction():
            await self.db.execute(
                "INSERT INTO event_outbox (id, event, status) VALUES (?, ?, ?)",
                [event.id, event.to_json(), "pending"]
            )
    
    async def process_pending_events(self) -> None:
        """Background job to publish pending events"""
        pending = await self.db.fetch(
            "SELECT * FROM event_outbox WHERE status = 'pending' LIMIT 100"
        )
        
        for row in pending:
            try:
                await self.nats.publish(row["event"])
                await self.mark_published(row["id"])
            except Exception as e:
                await self.mark_failed(row["id"], str(e))
```

#### Retry Strategy

```python
class EventRetryStrategy:
    """Exponential backoff with jitter"""
    
    def get_retry_delay(self, attempt: int) -> float:
        """Calculate delay before next retry"""
        base_delay = 1.0  # 1 second
        max_delay = 300.0  # 5 minutes
        
        # Exponential backoff
        delay = min(base_delay * (2 ** attempt), max_delay)
        
        # Add jitter (±25%)
        jitter = delay * 0.25 * (2 * random.random() - 1)
        
        return delay + jitter
```

### Event Monitoring

```python
# Prometheus metrics for event system
event_published_total = Counter(
    "ontology_event_published_total",
    "Total events published",
    ["event_type"]
)

event_processed_total = Counter(
    "ontology_event_processed_total", 
    "Total events processed",
    ["event_type", "consumer", "status"]
)

event_processing_duration = Histogram(
    "ontology_event_processing_duration_seconds",
    "Event processing duration",
    ["event_type", "consumer"]
)
```
### Common Event Patterns

#### Request-Reply Pattern

```python
# Request validation and wait for result
validation_id = str(uuid.uuid4())

# Subscribe to reply
reply_subject = f"validation.result.{validation_id}"
await nats.subscribe(reply_subject)

# Publish validation request
await publisher.publish(CloudEvent({
    "type": "com.ontology.validation.requested",
    "data": {
        "validationId": validation_id,
        "branch": "feature/customer",
        "replyTo": reply_subject
    }
}))

# Wait for result
result = await nats.wait_for_message(reply_subject, timeout=30)
```

#### Event Sourcing Pattern

```python
# Reconstruct object state from events
async def rebuild_object_type_state(object_type_id: str) -> ObjectType:
    """Rebuild object type state from event history"""
    
    events = await event_store.get_events(
        subject=f"ObjectType/{object_type_id}",
        order="asc"
    )
    
    state = None
    for event in events:
        if event.type == "com.ontology.objecttype.created":
            state = ObjectType(**event.data)
        elif event.type == "com.ontology.property.added":
            state.properties.append(Property(**event.data["property"]))
        elif event.type == "com.ontology.property.removed":
            state.properties = [
                p for p in state.properties 
                if p.name != event.data["propertyName"]
            ]
    
    return state
```

### Event Consumer Examples

#### IAM Synchronization

```python
class IAMSyncConsumer(EventConsumer):
    """Syncs permission changes to IAM service"""
    
    subscriptions = [
        "com.ontology.objecttype.created",
        "com.ontology.objecttype.deleted",
        "com.ontology.branch.protection.updated"
    ]
    
    async def process_event(self, event: CloudEvent):
        if event.type == "com.ontology.objecttype.created":
            # Create resource in IAM
            await iam_client.create_resource({
                "id": f"schema:{event.data['objectTypeId']}",
                "type": "schema",
                "name": event.data["name"],
                "permissions": ["read", "write", "delete"]
            })
```

#### Webhook Dispatcher

```python
class WebhookDispatcher(EventConsumer):
    """Sends events to configured webhooks"""
    
    async def process_event(self, event: CloudEvent):
        # Get webhooks for this event type
        webhooks = await self.get_webhooks(event.type)
        
        for webhook in webhooks:
            await self.dispatch_webhook(webhook, event)
    
    async def dispatch_webhook(self, webhook: Webhook, event: CloudEvent):
        """Send event to webhook with retry"""
        
        payload = {
            "event": event.to_dict(),
            "timestamp": datetime.utcnow().isoformat(),
            "signature": self.sign_payload(event, webhook.secret)
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                webhook.url,
                json=payload,
                timeout=30.0
            )
```

### Dead Letter Queue

```python
class DeadLetterHandler:
    """Handles events that failed processing"""
    
    async def handle_failed_event(
        self,
        event: CloudEvent,
        error: Exception,
        attempts: int
    ):
        """Move event to DLQ after max retries"""
        
        await self.store_to_dlq({
            "event": event.to_dict(),
            "error": str(error),
            "error_type": type(error).__name__,
            "attempts": attempts,
            "failed_at": datetime.utcnow().isoformat(),
            "consumer": self.consumer_name
        })
        
        # Alert on critical failures
        if self.is_critical_event(event):
            await self.send_alert(event, error)
```

---

## 10. Security Architecture

### Authentication

#### JWT Token Structure
```json
{
  "sub": "user@example.com",
  "iat": 1609459200,
  "exp": 1609462800,
  "scope": ["schema:read", "schema:write"],
  "tenant_id": "tenant_123",
  "roles": ["developer", "reviewer"]
}
```

#### Token Validation Flow
```python
# Middleware implementation
async def verify_token(token: str) -> User:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm]
        )
        return User(**payload)
    except JWTError:
        raise UnauthorizedException()
```

### Authorization

#### RBAC Model
```python
# Permission structure
class Permission:
    resource: str      # e.g., "schema", "branch"
    action: str        # e.g., "read", "write", "delete"
    constraints: Dict  # e.g., {"branch": "main"}

# Role definition
class Role:
    name: str
    permissions: List[Permission]
    
# Built-in roles
ROLES = {
    "viewer": ["schema:read", "branch:read"],
    "developer": ["schema:*", "branch:create"],
    "admin": ["*:*"]
}
```

#### Resource-Based Access Control
```python
# Check resource access
async def can_access_schema(user: User, schema_id: str) -> bool:
    # Check direct permissions
    if has_permission(user, "schema:read"):
        return True
    
    # Check resource ownership
    schema = await get_schema(schema_id)
    if schema.owner == user.id:
        return True
    
    # Check team membership
    if user.team_id == schema.team_id:
        return True
    
    return False
```

### Data Security

#### PII Detection
```python
# Automatic PII detection in schemas
PII_PATTERNS = {
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "ssn": r"\d{3}-\d{2}-\d{4}",
    "phone": r"\+?1?\d{9,15}",
    "credit_card": r"\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}"
}

async def detect_pii(data: Dict) -> List[PIIMatch]:
    matches = []
    for field, value in data.items():
        for pii_type, pattern in PII_PATTERNS.items():
            if re.match(pattern, str(value)):
                matches.append(PIIMatch(
                    field=field,
                    type=pii_type,
                    confidence=0.9
                ))
    return matches
```

#### Encryption
- **At Rest**: TerminusDB encryption, Redis TLS
- **In Transit**: HTTPS/TLS 1.3, mTLS for service communication
- **Secrets**: HashiCorp Vault integration or AWS Secrets Manager

### Security Headers
```python
# Security middleware
async def security_headers_middleware(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response
```

---

## 11. Testing Strategy

### Test Structure

```
tests/
├── unit/              # Unit tests
│   ├── test_schema_service.py
│   ├── test_validation_rules.py
│   └── test_branch_merger.py
├── integration/       # Integration tests
│   ├── test_api_endpoints.py
│   ├── test_database_operations.py
│   └── test_event_flow.py
├── e2e/              # End-to-end tests
│   ├── test_schema_lifecycle.py
│   └── test_branch_workflow.py
└── fixtures/         # Test data
    ├── schemas.json
    └── users.json
```

### Unit Testing

```python
# Example unit test
import pytest
from core.schema.service import SchemaService
from models.domain import ObjectType, Property

@pytest.fixture
def schema_service():
    return SchemaService()

async def test_create_schema(schema_service):
    # Arrange
    schema_data = {
        "name": "TestSchema",
        "properties": [
            {
                "name": "id",
                "data_type": "string",
                "required": True
            }
        ]
    }
    
    # Act
    schema = await schema_service.create_schema(schema_data)
    
    # Assert
    assert schema.name == "TestSchema"
    assert len(schema.properties) == 1
    assert schema.properties[0].required is True
```

### Integration Testing

```python
# Example integration test
import httpx
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client():
    from main import app
    return TestClient(app)

def test_schema_api_workflow(client, auth_token):
    # Create schema
    response = client.post(
        "/api/v1/schemas",
        json={
            "name": "Customer",
            "properties": [...]
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 201
    schema_id = response.json()["id"]
    
    # Update schema
    response = client.put(
        f"/api/v1/schemas/{schema_id}",
        json={"properties": [...]},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    
    # Validate changes
    response = client.post(
        f"/api/v1/schemas/{schema_id}/validate",
        json={"changes": [...]},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
```

### Performance Testing

```python
# Locust performance test
from locust import HttpUser, task, between

class OntologyUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        # Login and get token
        response = self.client.post("/auth/login", json={
            "username": "test@example.com",
            "password": "password"
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    @task(3)
    def get_schema(self):
        self.client.get("/api/v1/schemas/customer", headers=self.headers)
    
    @task(1)
    def create_schema(self):
        self.client.post(
            "/api/v1/schemas",
            json={"name": f"Schema_{self.environment.runner.user_count}"},
            headers=self.headers
        )
```

### Test Coverage Goals

- Unit Tests: 80% coverage minimum
- Integration Tests: All API endpoints
- E2E Tests: Critical user workflows
- Performance Tests: Load and stress testing

---

## 12. Deployment Guide

### Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Run as non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Start application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Kubernetes Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ontology-management-system
  labels:
    app: ontology-management-system
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ontology-management-system
  template:
    metadata:
      labels:
        app: ontology-management-system
    spec:
      containers:
      - name: app
        image: ontology-management-system:latest
        ports:
        - containerPort: 8000
        env:
        - name: ONTOLOGY_DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: ontology-secrets
              key: database-url
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

### Production Checklist

#### Pre-deployment
- [ ] All tests passing
- [ ] Security scan completed
- [ ] Performance benchmarks met
- [ ] Documentation updated
- [ ] Database migrations tested
- [ ] Rollback plan prepared

#### Configuration
- [ ] Environment variables set
- [ ] Secrets properly managed
- [ ] SSL certificates installed
- [ ] Monitoring configured
- [ ] Logging configured
- [ ] Backup strategy implemented

#### Post-deployment
- [ ] Health checks passing
- [ ] Metrics being collected
- [ ] Logs being aggregated
- [ ] Alerts configured
- [ ] Performance monitoring active
- [ ] Security monitoring active

### Scaling Considerations

1. **Horizontal Scaling**
   - Stateless application design
   - Session management in Redis
   - Database connection pooling

2. **Vertical Scaling**
   - Resource limits configured
   - Memory profiling completed
   - CPU optimization done

3. **Database Scaling**
   - Read replicas for TerminusDB
   - Redis cluster mode
   - Connection pool tuning

---

## 13. Troubleshooting

### Diagnostic Tools

#### System Health Dashboard
```bash
# Quick system check
curl -s http://localhost:8000/health/detailed | jq .

# Response shows all component status:
{
  "status": "degraded",
  "components": {
    "database": {
      "status": "healthy",
      "latency_ms": 12,
      "version": "v10.0.1"
    },
    "redis": {
      "status": "healthy",
      "latency_ms": 2,
      "connections": 5
    },
    "nats": {
      "status": "unhealthy",
      "error": "Connection refused",
      "last_seen": "2024-01-15T10:25:00Z"
    }
  }
}
```

### Common Issues and Solutions

#### 1. Database Connection Issues

**Symptoms:**
- 503 Service Unavailable errors
- "Schema service not available" messages
- Slow response times

**Diagnosis:**
```bash
# 1. Check if TerminusDB is running
docker ps | grep terminusdb

# 2. Test direct connection
curl -u admin:root http://localhost:6363/api/status

# 3. Check connection from app
python -c "
import asyncio
from database.clients.terminus_db import SimpleTerminusDBClient

async def test():
    client = SimpleTerminusDBClient('http://localhost:6363', 'admin', 'root')
    result = await client.test_connection()
    print(f'Connection: {result}')

asyncio.run(test())
"

# 4. Check logs for connection errors
docker logs ontology-management-terminusdb --tail 50
```

**Common Fixes:**
```bash
# Fix 1: Restart TerminusDB
docker-compose restart terminusdb

# Fix 2: Reset TerminusDB data (WARNING: Data loss!)
docker-compose down
docker volume rm oms-monolith_terminusdb-data
docker-compose up -d terminusdb

# Fix 3: Check environment variables
echo $TERMINUSDB_URL
echo $ONTOLOGY_DATABASE_URL

# Fix 4: Network issues
# If using Docker, ensure services are on same network
docker network ls
docker network inspect ontology-management-network
```

#### 2. Authentication/Authorization Issues

**Symptoms:**
- 401 Unauthorized errors
- 403 Forbidden errors  
- "Invalid token" messages

**Diagnosis:**
```python
# 1. Decode JWT token (without verification)
import jwt
import json

token = "paste.your.token.here"
try:
    # Decode without verification to see contents
    decoded = jwt.decode(token, options={"verify_signature": False})
    print("Token contents:")
    print(json.dumps(decoded, indent=2))
    
    # Check expiration
    import datetime
    exp = datetime.datetime.fromtimestamp(decoded['exp'])
    print(f"\nExpires at: {exp}")
    print(f"Current time: {datetime.datetime.now()}")
    print(f"Expired: {exp < datetime.datetime.now()}")
except Exception as e:
    print(f"Token decode error: {e}")
```

**Common Fixes:**
```bash
# Fix 1: Generate new token
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password"}'

# Fix 2: Check MSA vs legacy auth mode
echo $USE_MSA_AUTH

# Fix 3: Verify secret key matches
echo $ONTOLOGY_SECRET_KEY

# Fix 4: Check user permissions
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/users/me/permissions
```

#### 3. Performance Issues

**Symptoms:**
- Slow API responses (>1s)
- High CPU/memory usage
- Redis connection pool exhausted

**Diagnosis:**
```bash
# 1. Check response times
curl -w "@curl-format.txt" -o /dev/null -s \
  http://localhost:8000/api/v1/schemas/main/object-types

# curl-format.txt:
time_namelookup:  %{time_namelookup}s\n
time_connect:  %{time_connect}s\n
time_appconnect:  %{time_appconnect}s\n
time_pretransfer:  %{time_pretransfer}s\n
time_redirect:  %{time_redirect}s\n
time_starttransfer:  %{time_starttransfer}s\n
----------\n
time_total:  %{time_total}s\n

# 2. Profile slow endpoints
python -m cProfile -o profile.stats main.py
python -m pstats profile.stats
>>> sort cumtime
>>> stats 20

# 3. Monitor Redis operations
redis-cli monitor | grep -E "SLOW|BLOCKED"

# 4. Check for N+1 queries
ONTOLOGY_LOG_LEVEL=DEBUG uvicorn main:app 2>&1 | grep "SELECT"
```

**Common Fixes:**
```python
# Fix 1: Enable caching
from shared.cache import SmartCacheManager

cache = SmartCacheManager()
await cache.enable_aggressive_caching()

# Fix 2: Use DataLoader for GraphQL
from api.graphql.dataloader import create_loaders

loaders = create_loaders()
# Use loaders in resolvers

# Fix 3: Add database indexes
CREATE INDEX idx_object_type_branch 
ON object_types(branch_id, status);

# Fix 4: Increase connection pools
REDIS_MAX_CONNECTIONS=100
DATABASE_POOL_SIZE=20
```

#### 4. Event System Issues

**Symptoms:**
- Events not being processed
- Dead letter queue growing
- Event processing delays

**Diagnosis:**
```bash
# 1. Check NATS connection
nats-cli --server nats://localhost:4222 ping

# 2. List streams and consumers
nats stream list
nats consumer list ONTOLOGY_EVENTS

# 3. Check event outbox
sqlite3 event_outbox.db \
  "SELECT status, COUNT(*) FROM events GROUP BY status;"

# 4. Monitor event metrics
curl -s http://localhost:8000/metrics | \
  grep -E "event_published|event_processed|event_failed"
```

**Common Fixes:**
```bash
# Fix 1: Restart event processors
docker-compose restart event-processor

# Fix 2: Process stuck outbox events
python scripts/process_event_outbox.py --force

# Fix 3: Clear dead letter queue
nats stream purge ONTOLOGY_EVENTS_DLQ

# Fix 4: Increase consumer replicas
docker-compose scale event-processor=3
```

#### 5. Schema Validation Failures

**Symptoms:**
- "Breaking change detected" errors
- Validation timeouts
- Incorrect validation results

**Diagnosis:**
```python
# Test validation directly
from core.validation import ValidationService

service = ValidationService()
result = await service.validate_changes(
    source_branch="main",
    target_branch="feature/test",
    changes=[...]
)
print(f"Valid: {result.is_valid}")
print(f"Errors: {result.errors}")
```

### Advanced Debugging

#### Memory Profiling
```python
# Install memory profiler
pip install memory-profiler

# Run with memory profiling
python -m memory_profiler main.py

# Generate memory report
import tracemalloc
tracemalloc.start()

# ... run your code ...

snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')
for stat in top_stats[:10]:
    print(stat)
```

#### Distributed Tracing
```python
# Enable Jaeger tracing
export OTEL_EXPORTER_JAEGER_ENDPOINT=http://localhost:14268/api/traces
export OTEL_SERVICE_NAME=ontology-management-system

# View traces
open http://localhost:16686  # Jaeger UI
```

#### Database Query Analysis
```sql
-- Find slow queries in TerminusDB
SELECT 
  query,
  duration_ms,
  timestamp
FROM system.query_log
WHERE duration_ms > 100
ORDER BY duration_ms DESC
LIMIT 10;

-- Check index usage
EXPLAIN ANALYZE
SELECT * FROM object_types 
WHERE branch_id = 'main' 
AND status = 'active';
```

### Debug Mode and Logging

#### Enabling Debug Mode
```bash
# Global debug mode
export ONTOLOGY_DEBUG=true
export ONTOLOGY_LOG_LEVEL=DEBUG

# Component-specific debugging
export DEBUG_SCHEMA_SERVICE=true      # Schema operations
export DEBUG_VALIDATION=true          # Validation details
export DEBUG_EVENTS=true              # Event processing
export DEBUG_CACHE=true               # Cache operations
export DEBUG_AUTH=true                # Authentication flow

# SQL query logging
export LOG_SQL_QUERIES=true
export LOG_SLOW_QUERIES_MS=100       # Log queries >100ms

# HTTP request/response logging  
export LOG_HTTP_REQUESTS=true
export LOG_HTTP_BODIES=true           # WARNING: May log sensitive data
```

#### Structured Logging

**Log Format:**
```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "ERROR",
  "logger": "core.schema.service",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "span_id": "7372656e-6368-2065-7374-207370616e21",
  "user_id": "admin@example.com",
  "tenant_id": "tenant_123",
  "message": "Failed to create object type",
  "error": {
    "type": "ValidationError",
    "message": "Object type name already exists",
    "stack_trace": "..."
  },
  "context": {
    "branch": "main",
    "object_type_name": "Customer",
    "operation": "create_object_type",
    "duration_ms": 145
  },
  "system": {
    "hostname": "ontology-prod-1",
    "pid": 12345,
    "memory_mb": 512
  }
}
```

**Log Aggregation:**
```bash
# Search logs by trace ID
grep "550e8400-e29b-41d4-a716-446655440000" /var/log/ontology/*.log

# Find all errors for a user
jq 'select(.level == "ERROR" and .user_id == "user@example.com")' \
  /var/log/ontology/app.log

# Performance analysis
jq 'select(.context.duration_ms > 1000) | 
  {endpoint: .context.endpoint, duration: .context.duration_ms}' \
  /var/log/ontology/api.log | \
  jq -s 'group_by(.endpoint) | 
  map({endpoint: .[0].endpoint, 
       avg_ms: (map(.duration) | add / length),
       count: length})'
```

#### Debug Endpoints

```python
# Add debug endpoints (dev only!)
if settings.ONTOLOGY_DEBUG:
    @app.get("/debug/config")
    async def debug_config():
        """Show current configuration"""
        return {
            "environment": settings.ONTOLOGY_ENVIRONMENT,
            "services": {
                "database": settings.ONTOLOGY_DATABASE_URL,
                "redis": settings.ONTOLOGY_REDIS_URL,
                "nats": settings.NATS_URL
            },
            "features": {
                "msa_auth": settings.USE_MSA_AUTH,
                "graphql": settings.GRAPHQL_ENABLED
            }
        }
    
    @app.get("/debug/cache/stats")
    async def cache_stats():
        """Show cache statistics"""
        return await cache_manager.get_stats()
    
    @app.get("/debug/connections")
    async def connection_pool_stats():
        """Show connection pool statistics"""
        return {
            "database": db_pool.get_stats(),
            "redis": redis_pool.get_stats()
        }
```

### Health Checks

```bash
# Basic health check
curl http://localhost:8000/health

# Detailed health check
curl http://localhost:8000/health/detailed

# Response format:
{
  "status": "healthy",
  "version": "3.0.0",
  "checks": {
    "database": "ok",
    "redis": "ok",
    "nats": "ok"
  },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

---

## 14. Code Standards

### Python Style Guide

#### Naming Conventions
```python
# Classes: PascalCase
class SchemaValidator:
    pass

# Functions/Methods: snake_case
def validate_schema(schema: Schema) -> ValidationResult:
    pass

# Constants: UPPER_SNAKE_CASE
MAX_RETRY_ATTEMPTS = 3

# Private methods: leading underscore
def _internal_helper():
    pass
```

#### Type Hints
```python
from typing import List, Dict, Optional, Union
from models.domain import Schema, Property

async def create_schema(
    name: str,
    properties: List[Property],
    metadata: Optional[Dict[str, Any]] = None
) -> Schema:
    """Create a new schema with validation."""
    pass
```

#### Docstrings
```python
def validate_breaking_changes(
    old_schema: Schema,
    new_schema: Schema
) -> ValidationResult:
    """
    Validate schema changes for breaking changes.
    
    Args:
        old_schema: The current schema version
        new_schema: The proposed schema version
        
    Returns:
        ValidationResult containing any breaking changes found
        
    Raises:
        ValidationError: If schemas are incompatible
        
    Example:
        >>> result = validate_breaking_changes(old, new)
        >>> if result.has_breaking_changes:
        ...     print(result.breaking_changes)
    """
    pass
```

### Git Workflow

#### Branch Naming
- Feature: `feature/description`
- Bugfix: `fix/description`
- Hotfix: `hotfix/description`
- Release: `release/version`

#### Commit Messages
```
feat: Add schema validation endpoint

- Implement POST /api/v1/schemas/validate
- Add breaking change detection
- Include migration suggestions

Closes #123
```

#### Pull Request Template
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No new warnings
```

### Security Practices

1. **Never commit secrets**
   ```python
   # Bad
   API_KEY = "sk-1234567890"
   
   # Good
   API_KEY = os.getenv("API_KEY")
   ```

2. **Validate all inputs**
   ```python
   from pydantic import BaseModel, validator
   
   class SchemaCreate(BaseModel):
       name: str
       
       @validator("name")
       def validate_name(cls, v):
           if not v.strip():
               raise ValueError("Name cannot be empty")
           return v
   ```

3. **Use parameterized queries**
   ```python
   # Bad
   query = f"SELECT * FROM schemas WHERE id = '{schema_id}'"
   
   # Good
   query = "SELECT * FROM schemas WHERE id = %s"
   cursor.execute(query, (schema_id,))
   ```

### Performance Guidelines

1. **Use async/await consistently**
2. **Implement pagination for list endpoints**
3. **Cache expensive operations**
4. **Use database indexes appropriately**
5. **Profile before optimizing**

---

## Appendix A: Complete Environment Variables Reference

### Core Configuration

| Variable | Description | Default | Required | Example |
|----------|-------------|---------|----------|----------|
| ONTOLOGY_ENVIRONMENT | Environment mode | development | No | production |
| ONTOLOGY_DEBUG | Enable debug mode | false | No | true |
| ONTOLOGY_SERVICE_NAME | Service identifier | ontology-management-system | No | oms-prod |
| ONTOLOGY_SERVICE_VERSION | Service version | 3.0.0 | No | 3.1.0 |

### Security

| Variable | Description | Default | Required | Example |
|----------|-------------|---------|----------|----------|
| ONTOLOGY_SECRET_KEY | JWT signing key | - | Yes | your-256-bit-secret |
| ONTOLOGY_JWT_ALGORITHM | JWT algorithm | HS256 | No | RS256 |
| ONTOLOGY_JWT_EXPIRATION_MINUTES | Token lifetime | 30 | No | 60 |
| USE_MSA_AUTH | Use microservices auth | false | No | true |
| IAM_SERVICE_URL | IAM service endpoint | - | If MSA | http://iam:8001 |
| ENABLE_MTLS | Enable mutual TLS | false | No | true |
| TLS_CERT_PATH | TLS certificate path | - | If mTLS | /certs/server.crt |
| TLS_KEY_PATH | TLS key path | - | If mTLS | /certs/server.key |

### Database

| Variable | Description | Default | Required | Example |
|----------|-------------|---------|----------|----------|
| ONTOLOGY_DATABASE_URL | TerminusDB URL | http://localhost:6363 | No | http://terminusdb:6363 |
| ONTOLOGY_DATABASE_USERNAME | DB username | admin | No | ontology_user |
| ONTOLOGY_DATABASE_PASSWORD | DB password | - | Yes | secure-password |
| TERMINUSDB_URL | Docker internal URL | - | No | http://terminusdb:6363 |
| DATABASE_POOL_SIZE | Connection pool size | 10 | No | 20 |
| DATABASE_POOL_TIMEOUT | Pool timeout (seconds) | 30 | No | 60 |

### Caching

| Variable | Description | Default | Required | Example |
|----------|-------------|---------|----------|----------|
| ONTOLOGY_REDIS_URL | Redis URL | redis://localhost:6379 | No | redis://redis:6379 |
| ONTOLOGY_REDIS_PREFIX | Key prefix | ontology: | No | prod:ontology: |
| REDIS_URL | Docker internal URL | - | No | redis://redis:6379 |
| REDIS_MAX_CONNECTIONS | Max connections | 50 | No | 100 |
| CACHE_TTL_SECONDS | Default cache TTL | 300 | No | 600 |
| ENABLE_CACHE | Enable caching | true | No | false |

### Messaging

| Variable | Description | Default | Required | Example |
|----------|-------------|---------|----------|----------|
| NATS_URL | NATS server URL | nats://localhost:4222 | No | nats://nats:4222 |
| NATS_CLUSTER_ID | Cluster identifier | ontology-cluster | No | prod-cluster |
| NATS_CLIENT_ID | Client identifier | - | No | worker-1 |
| EVENT_BATCH_SIZE | Event batch size | 100 | No | 500 |
| EVENT_RETENTION_DAYS | Event retention | 30 | No | 90 |

### Features

| Variable | Description | Default | Required | Example |
|----------|-------------|---------|----------|----------|
| GRAPHQL_ENABLED | Enable GraphQL API | true | No | false |
| ENV | Environment (production/staging/development/test/local) | development | No | production |
| ENABLE_ISSUE_TRACKING | Issue tracking | true | No | false |
| ENABLE_SHADOW_INDEXING | Shadow indexes | true | No | false |
| ENABLE_AUDIT_LOG | Audit logging | true | No | false |
| ENABLE_METRICS | Prometheus metrics | true | No | false |

### Monitoring

| Variable | Description | Default | Required | Example |
|----------|-------------|---------|----------|----------|
| PROMETHEUS_PORT | Metrics port | 9090 | No | 9091 |
| JAEGER_ENDPOINT | Jaeger collector | - | No | http://jaeger:14268 |
| OTEL_SERVICE_NAME | OpenTelemetry name | - | No | ontology-prod |
| SENTRY_DSN | Sentry DSN | - | No | https://key@sentry.io/123 |
| LOG_LEVEL | Global log level | INFO | No | DEBUG |
| LOG_FORMAT | Log format | json | No | plain |

### Performance

| Variable | Description | Default | Required | Example |
|----------|-------------|---------|----------|----------|
| WORKER_THREADS | Worker thread count | 4 | No | 8 |
| REQUEST_TIMEOUT | Request timeout (s) | 30 | No | 60 |
| MAX_REQUEST_SIZE | Max request size | 10MB | No | 50MB |
| RATE_LIMIT_PER_MINUTE | Rate limit | 100 | No | 1000 |
| SLOW_QUERY_THRESHOLD_MS | Slow query threshold | 100 | No | 200 |

## Appendix B: API Error Codes

| Code | Description | HTTP Status |
|------|-------------|-------------|
| VALIDATION_ERROR | Input validation failed | 400 |
| AUTHENTICATION_REQUIRED | No valid auth token | 401 |
| PERMISSION_DENIED | Insufficient permissions | 403 |
| RESOURCE_NOT_FOUND | Resource does not exist | 404 |
| CONFLICT | Resource conflict | 409 |
| BREAKING_CHANGE_DETECTED | Schema has breaking changes | 422 |
| RATE_LIMIT_EXCEEDED | Too many requests | 429 |
| INTERNAL_ERROR | Server error | 500 |

## Appendix C: Monitoring Metrics

| Metric | Type | Description |
|--------|------|-------------|
| ontology_request_duration_seconds | Histogram | HTTP request duration |
| ontology_request_total | Counter | Total HTTP requests |
| ontology_schema_operations_total | Counter | Schema operations by type |
| ontology_validation_duration_seconds | Histogram | Validation processing time |
| ontology_cache_hits_total | Counter | Cache hit rate |
| ontology_db_connections_active | Gauge | Active DB connections |
| ontology_event_published_total | Counter | Events published by type |

## Appendix D: Command Reference

### Development Commands

```bash
# Environment Setup
make dev                    # Start full dev environment
make dev-minimal           # Start only essential services
make clean                 # Clean up all containers and volumes

# Code Quality
make lint                  # Run all linters (ruff, mypy, black)
make format               # Auto-format code
make type-check          # Run type checking
make security-scan       # Run security analysis

# Testing
make test                 # Run all tests
make test-unit           # Run unit tests only
make test-integration    # Run integration tests
make test-coverage       # Generate coverage report
make test-performance    # Run performance tests

# Documentation
make docs                # Generate API documentation
make docs-serve         # Serve docs locally
```

### Operational Commands

```bash
# Service Management
docker-compose up -d                  # Start all services
docker-compose up -d --scale app=3   # Scale app instances
docker-compose ps                    # Show service status
docker-compose logs -f app           # Follow app logs
docker-compose exec app bash         # Shell into app container
docker-compose down                  # Stop services
docker-compose down -v              # Stop and remove volumes

# Database Operations
python scripts/init_databases.py         # Initialize all databases
python scripts/migrate.py               # Run migrations
python scripts/backup_db.py            # Backup database
python scripts/restore_db.py backup.tar # Restore from backup
python scripts/validate_db.py          # Validate database integrity

# Cache Management  
redis-cli FLUSHDB                      # Clear Redis cache
redis-cli --scan --pattern ontology:*  # List all cache keys
redis-cli INFO memory                  # Check memory usage

# Event System
nats-cli stream list                           # List all streams
nats-cli stream info ONTOLOGY_EVENTS          # Stream details
nats-cli consumer info ONTOLOGY_EVENTS ALL    # Consumer status
nats-cli stream purge ONTOLOGY_EVENTS         # Purge stream
```

### Debugging Commands

```bash
# Health Checks
curl -s http://localhost:8002/health | jq .
curl -s http://localhost:8000/health/detailed | jq .
curl -s http://localhost:8000/metrics | grep -E "up{|ontology_"

# Performance Analysis
ab -n 1000 -c 10 http://localhost:8000/api/v1/schemas/main/object-types
wrk -t12 -c400 -d30s --latency http://localhost:8000/health

# Log Analysis
tail -f logs/app.log | jq 'select(.level == "ERROR")'
tail -f logs/app.log | jq -r '[.timestamp, .message] | @tsv'
grep -r "ERROR" logs/ | wc -l

# Database Queries
sqlite3 issue_tracking.db "SELECT COUNT(*) FROM issues WHERE status='open';"
sqlite3 idempotent_consumer.db ".tables"

# Memory Profiling
ps aux | grep python | awk '{sum+=$6} END {print "Total RSS: " sum/1024 " MB"}'
docker stats --no-stream
```

### Deployment Commands

```bash
# Build & Push
docker build -t ontology-management-system:latest .
docker tag ontology-management-system:latest registry.example.com/oms:v3.0.0
docker push registry.example.com/oms:v3.0.0

# Kubernetes
kubectl apply -f k8s/
kubectl rollout status deployment/ontology-management-system
kubectl scale deployment/ontology-management-system --replicas=5
kubectl logs -f deployment/ontology-management-system

# Backup & Restore
kubectl exec -it terminusdb-0 -- terminusdb backup /backup/$(date +%Y%m%d)
kubectl cp terminusdb-0:/backup ./backups/
```

### Utility Scripts

```bash
# Schema Operations
python scripts/export_schema.py --branch main --output schema.json
python scripts/import_schema.py --branch feature/import --file schema.json
python scripts/compare_schemas.py --source main --target feature/test

# Data Migration
python scripts/generate_migration.py --from v1 --to v2
python scripts/run_migration.py --migration 001_add_customer_email.py

# Performance Tuning
python scripts/analyze_slow_queries.py --threshold 100
python scripts/optimize_indexes.py --dry-run
python scripts/cache_warmup.py --branch main

# Security
python scripts/rotate_secrets.py --service jwt
python scripts/audit_permissions.py --user admin@example.com
python scripts/scan_pii.py --branch main
```

---

## Appendix E: Architecture Decision Records (ADRs)

### ADR-001: Monolith First Architecture
**Status**: Accepted  
**Context**: Need to build a complex system quickly with a small team  
**Decision**: Start with a well-structured monolith that can be split into microservices later  
**Consequences**: Simpler deployment, easier debugging, but potential scaling limitations  

### ADR-002: Dual Entry Points
**Status**: Implemented  
**Context**: Need both standard and life-critical security modes  
**Decision**: Two separate main.py files - standard and secure  
**Consequences**: Different startup procedures, port conflicts if run simultaneously  

### ADR-003: PostgreSQL Advisory Locks for Branch Operations
**Status**: Implemented  
**Context**: Git-style branch operations require strong consistency to prevent conflicts  
**Decision**: Use PostgreSQL advisory locks instead of Redis for distributed locking  
**Consequences**: 
- ✅ Automatic lock release on session/transaction end (no stuck locks)
- ✅ Integrated with database transactions (rollback on failure)
- ✅ No external dependency for critical operations
- ⚠️ Requires PostgreSQL instance (additional infrastructure)

### ADR-004: Lock Manager Modularization
**Status**: Implemented  
**Context**: lock_manager.py grew to 928 lines, violating single responsibility principle  
**Decision**: Split into 5 focused modules with clear responsibilities  
**Implementation**:
- `lock_manager.py` (399 lines) - Orchestrator coordinating all services
- `lock_manager_core.py` - Core locking logic and conflict detection
- `lock_state_manager.py` - Branch state persistence and transitions
- `lock_heartbeat_service.py` - Distributed lock health monitoring
- `lock_cleanup_service.py` - TTL and heartbeat-based cleanup
**Consequences**: 
- ✅ Better maintainability and testability
- ✅ Clear separation of concerns
- ✅ Easier to extend individual components
- ✅ Reduced cognitive load per file

### ADR-005: Dual Naming Convention
**Status**: Accepted  
**Context**: TerminusDB uses camelCase, Python convention is snake_case  
**Decision**: Use camelCase in database/API, snake_case in Python, with explicit conversion  
**Consequences**: Some complexity at boundaries but maintains compatibility with both ecosystems  

### ADR-007: Event Sourcing for Audit
**Status**: Accepted  
**Context**: Need complete audit trail for compliance  
**Decision**: Every change creates an immutable event  
**Consequences**: Complete history but increased storage requirements  

### ADR-012: GraphQL with DataLoader
**Status**: Accepted  
**Context**: N+1 query problems with nested schema queries  
**Decision**: Implement DataLoader pattern for automatic batching  
**Consequences**: Better performance but more complex resolver implementation  

## Appendix F: Glossary

| Term | Definition |
|------|------------|
| **Ontology** | A formal representation of knowledge as a set of concepts and relationships |
| **Object Type** | A class or entity in the ontology (like "Customer" or "Product") |
| **Property** | An attribute of an Object Type (like "email" or "price") |
| **Link Type** | A relationship between Object Types |
| **Semantic Type** | The meaning of a property beyond its data type (e.g., "email" vs just "string") |
| **Branch** | An isolated version of the schema for development |
| **Breaking Change** | A schema modification that would cause existing systems to fail |
| **Three-way Merge** | Merge strategy using common ancestor to resolve conflicts |
| **Shadow Index** | Background index creation without blocking operations |
| **Outbox Pattern** | Reliability pattern for event publishing |
| **DataLoader** | Pattern for batching and caching database requests |
| **CloudEvents** | Standard format for event data |
| **MSA** | Microservices Architecture authentication mode |
| **PII** | Personally Identifiable Information |
| **RBAC** | Role-Based Access Control |

---

## Final Notes

This comprehensive guide represents the current state of the Ontology Management System as of version 3.0.0. The system is actively developed and some details may change. Always refer to:

1. **Code Comments**: For implementation-specific details
2. **ADR Documents**: For understanding architectural decisions  
3. **API Documentation**: Available at `/docs` when running
4. **Team Chat**: For questions not covered in documentation

### Getting Help

- **Slack Channel**: #ontology-management-system
- **Email**: ontology-team@company.com
- **Issue Tracker**: https://github.com/company/ontology-management-system/issues
- **Wiki**: https://wiki.company.com/ontology-management-system

### Contributing

We welcome contributions! Please:

1. Read this guide thoroughly
2. Follow the code standards
3. Write tests for new features
4. Update documentation
5. Submit PR with clear description

Thank you for working with the Ontology Management System!

---

## ⚠️ 현재 구현 상태 요약

### ✅ 구현 완료
- 기본 ObjectType 조회/생성 (2개 API)
- 감사 로그 시스템
- 이슈 트래킹
- 브랜치 잠금 관리
- 섀도우 인덱싱
- ETag 캐싱
- 헬스 체크
- GraphQL (기본)

### ❌ 미구현
- 대부분의 CRUD API
- ValidationService (None으로 설정)
- BranchService (None으로 설정)  
- HistoryService (None으로 설정)
- 인증 엔드포인트 (/auth/login)
- 브랜치 생성/병합
- 속성 관리 API

### 🚨 주의사항
1. **두 개의 main.py**: `main.py`(기본) vs `main_secure.py`(보안 강화)
2. **DB 연결 문제**: "DB 연결 문제 해결 버전" 주석이 있음
3. **Mock 데이터**: API 응답에 `source: "real_database"` 표시
4. **테스트 부족**: tests/ 디렉토리가 거의 비어있음

**프로덕션 사용 전 반드시 다음 문서들을 참고하세요:**
- [CRITICAL_NOTES.md](./CRITICAL_NOTES.md) - 긴급 주의사항
- [ACCURATE_SYSTEM_DOCUMENTATION.md](./ACCURATE_SYSTEM_DOCUMENTATION.md) - 100% 정확한 현재 구현 상태

**⚠️ 경고: main.py는 import 오류로 인해 수정 없이는 실행되지 않습니다!**