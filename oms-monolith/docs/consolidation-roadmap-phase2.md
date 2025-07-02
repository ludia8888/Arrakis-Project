# OMS Monolith Consolidation Roadmap - Phase 2

## Executive Summary

Based on the comprehensive analysis, we've identified remaining duplications and created a detailed roadmap for complete consolidation. While Phase 1 successfully unified resilience patterns (retry, circuit breaker, retry budget), several areas still require consolidation.

## Current State Analysis

### ✅ Completed (Phase 1)
1. **Unified Resilience Module** (`shared/resilience/`)
   - Consolidated retry/backoff logic
   - Unified circuit breaker implementation
   - Retry budget management
   - Successfully integrated with DLQ, Scheduler, and Event Publisher

### 🔄 In Progress
1. **Unified Cache System** (`shared/cache/`)
   - Interfaces defined
   - Registry pattern implemented
   - Partial migration completed

### ❌ Remaining Duplications

#### 1. Configuration Management
- **32 files** still using `os.getenv()` directly
- **191 total calls** to `os.getenv()`
- Multiple configuration systems co-existing

#### 2. Retry/Resilience Implementations
- `shared/utils/retry_strategy.py` - Still actively used by Action Service
- `api/gateway/router.py` - Hardcoded exponential backoff
- `core/scheduler/schedule_calculator.py` - Isolated retry delay calculation

#### 3. Circuit Breaker Implementations
- `shared/security/protection_facade.py` - Enterprise features with Redis distribution
- `shared/clients/unified_http_client.py` - Simple HTTP-focused implementation
- `shared/utils/retry_strategy.py` - Integrated with retry patterns

#### 4. Cache Implementations
- `core/validation/enterprise/implementations/validation_cache.py` - Sync-only, validation-specific
- Interface inconsistencies (timedelta vs ttl_seconds)
- Different storage backends (memory, Redis, TerminusDB)

#### 5. Security/Sanitization
- `shared/security/path_traversal_killer.py`
- `shared/security/pii_utils.py`
- Scattered input sanitization logic

#### 6. Logging/Metrics
- `utils.logging`
- `shared.observability`
- `shared.monitoring.unified_metrics`
- Multiple metric collection approaches

## Consolidation Roadmap

### Phase 2.1: Configuration Unification (Week 1-2)

#### Week 1: Critical Security Components
```python
# Priority 1: Security-critical variables (no defaults)
- JWT_SECRET
- PII_ENCRYPTION_KEY
- TERMINUS_DB_PASSWORD
- REDIS_PASSWORD
```

**Tasks:**
1. Run `scripts/migrate_os_getenv.py` on priority files:
   - `main_secure.py`
   - `middleware/auth_secure.py`
   - `core/iam/iam_integration.py`
2. Add validators for security configurations
3. Implement startup validation with clear error messages

#### Week 2: Service Integration
**Tasks:**
1. Migrate database clients to unified_env
2. Update service clients and external integrations
3. Add import-linter rule: `no-direct-os-getenv`
4. Set up CI gate to prevent new `os.getenv()` usage

### Phase 2.2: Complete Resilience Migration (Week 3-4)

#### Week 3: Action Service Migration
**Tasks:**
1. Replace `shared/utils/retry_strategy.py` usage in `core/action/service.py`:
   ```python
   # Old
   from shared.utils.retry_strategy import RetryExecutor
   
   # New
   from shared.resilience import with_retry, RETRY_POLICIES
   ```
2. Migrate API Gateway hardcoded retry logic
3. Update tests to use unified resilience

#### Week 4: Circuit Breaker Consolidation
**Tasks:**
1. Create adapter for Protection Facade's distributed features:
   ```python
   class DistributedCircuitBreaker(UnifiedCircuitBreaker):
       """Adds Redis-based state distribution"""
   ```
2. Migrate HTTP client to use unified circuit breaker
3. Deprecate old implementations

### Phase 2.3: Cache System Completion (Week 5-6)

#### Week 5: Interface Standardization
**Tasks:**
1. Standardize TTL handling:
   ```python
   # Create backward-compatible wrapper
   def set(key, value, ttl_seconds=None, ttl=None):
       if ttl_seconds:
           ttl = timedelta(seconds=ttl_seconds)
   ```
2. Migrate validation cache to unified interfaces
3. Ensure all caches report unified metrics

#### Week 6: Storage Backend Abstraction
**Tasks:**
1. Create storage backend interface:
   ```python
   class CacheStorageBackend(ABC):
       @abstractmethod
       async def get(self, key: str) -> Optional[Any]: ...
   ```
2. Implement adapters for Redis, Memory, TerminusDB
3. Complete migration to cache registry pattern

### Phase 2.4: Security & Observability (Week 7-8)

#### Week 7: Security Consolidation
**Tasks:**
1. Create `shared/security/sanitizers/` package:
   ```python
   - input_sanitizer.py
   - path_sanitizer.py
   - pii_sanitizer.py
   - sanitizer_chain.py
   ```
2. Implement strategy pattern for sanitization
3. Create unified security middleware

#### Week 8: Observability Unification
**Tasks:**
1. Standardize on OpenTelemetry:
   ```python
   # Create unified wrapper
   class UnifiedMetrics:
       def __init__(self, meter_provider):
           self.meter = meter_provider.get_meter("oms")
   ```
2. Migrate all metrics to unified system
3. Deprecate old logging/metrics modules

## Implementation Strategy

### 1. Backward Compatibility
- All changes must maintain backward compatibility
- Use adapter pattern for legacy interfaces
- Deprecation warnings before removal

### 2. Testing Strategy
- Write migration tests before changes
- Ensure 100% test coverage for new unified modules
- Integration tests for each migration

### 3. Rollout Plan
- Feature flags for gradual rollout
- Monitor metrics during migration
- Rollback plan for each phase

### 4. Documentation
- Update documentation for each unified module
- Migration guides for each component
- Architecture decision records (ADRs)

## Success Metrics

### Technical Metrics
- **0 circular dependencies** (maintain current state)
- **< 5 duplicate implementations** (from current ~30)
- **100% configuration through unified_env**
- **< 3 import layers** (simplified architecture)

### Quality Metrics
- **Test coverage > 90%** for unified modules
- **< 2% performance degradation**
- **0 breaking changes** in public APIs

### Business Metrics
- **30% reduction** in maintenance time
- **50% faster** feature development
- **90% reduction** in configuration-related incidents

## Risk Mitigation

### High Risks
1. **Breaking production services during migration**
   - Mitigation: Feature flags, canary deployments
2. **Performance degradation from abstraction**
   - Mitigation: Benchmark before/after, optimize hot paths

### Medium Risks
1. **Developer resistance to new patterns**
   - Mitigation: Clear documentation, training sessions
2. **Hidden dependencies on old implementations**
   - Mitigation: Comprehensive testing, gradual deprecation

## Next Steps

1. **Immediate Actions** (This Week):
   - Run `scripts/analyze_env_usage.py` for baseline
   - Start Week 1 security configuration migration
   - Set up import-linter rules

2. **Short Term** (Next 2 Weeks):
   - Complete Phase 2.1 (Configuration)
   - Begin Phase 2.2 (Resilience)

3. **Long Term** (Next 2 Months):
   - Complete all phases
   - Deprecate old modules
   - Document new architecture

## Appendix: Migration Scripts

### A. Configuration Migration
```bash
# Analyze current usage
python scripts/analyze_env_usage.py

# Migrate specific file
python scripts/migrate_os_getenv.py --file main_secure.py

# Validate migration
python scripts/validate_unified_env.py
```

### B. Resilience Migration
```python
# Example migration
# Old:
@retry_with_backoff(max_attempts=3)
def my_function():
    pass

# New:
from shared.resilience import with_retry

@with_retry(policy="standard")
def my_function():
    pass
```

### C. Cache Migration
```python
# Old:
from core.traversal.cache import LRUCache
cache = LRUCache(max_size=1000)

# New:
from shared.cache import CacheRegistry
cache = CacheRegistry.get_cache("my_cache", config={"max_size": 1000})
```