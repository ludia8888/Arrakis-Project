# TerminusDB Native Migration Guide

## 📋 Overview

이 문서는 OMS (Ontology Management System)의 TerminusDB Native 기능으로의 안전한 마이그레이션 가이드입니다.

### 목표
- ✅ 중복 구현 제거 (3개의 merge engine → 1개)
- ✅ TerminusDB의 검증된 기능 최대 활용
- ✅ 안전한 점진적 마이그레이션
- ✅ 즉시 롤백 가능한 구조

## 🏗️ Architecture Changes

### Before (Legacy)
```
┌─────────────────────────────────────────┐
│           OMS Application Layer         │
├─────────────────────────────────────────┤
│  BranchService │ MergeEngine │ DiffEngine│
│  (Custom Git)  │ (3 versions)│ (Custom) │
├─────────────────────────────────────────┤
│         PostgreSQL + Redis              │
└─────────────────────────────────────────┘
```

### After (Native)
```
┌─────────────────────────────────────────┐
│           OMS Application Layer         │
├─────────────────────────────────────────┤
│  Unified      │ Domain       │ Feature  │
│  Adapter      │ Validation   │ Flags    │
├─────────────────────────────────────────┤
│      TerminusDB Native Features         │
│  (Branch, Merge, Diff, History, ACID)   │
└─────────────────────────────────────────┘
```

## 🔑 Key Components

### 1. TerminusNativeBranchService
- **Location**: `core/branch/terminus_adapter.py`
- **Purpose**: TerminusDB native branch operations
- **Key Methods**:
  ```python
  async def create_branch(parent, name) -> str
  async def merge_branches(source, target) -> MergeResult
  async def get_diff(from_ref, to_ref) -> BranchDiff
  ```

### 2. UnifiedMergeEngine
- **Location**: `core/merge/unified_engine.py`
- **Purpose**: Consolidates 3 merge implementations
- **Features**:
  - TerminusDB native merge for structural changes
  - OMS domain validation on top
  - Cardinality narrowing prevention
  - Required field removal detection

### 3. Feature Flags
- **Location**: `shared/config.py`
- **Flags**:
  ```python
  USE_TERMINUS_NATIVE_BRANCH = True/False
  USE_UNIFIED_MERGE_ENGINE = True/False
  ```

## 🚦 Migration Stages

### Stage 1: Read Operations (Week 1)
```python
# Enable for read-only operations
USE_TERMINUS_NATIVE_BRANCH = True  # for list, get operations only
```

### Stage 2: Branch Operations (Week 2)
```python
# Enable for branch creation/deletion
NATIVE_OPERATIONS = ["create_branch", "delete_branch", "list_branches"]
```

### Stage 3: Merge Operations (Week 3)
```python
# Enable unified merge engine
USE_UNIFIED_MERGE_ENGINE = True
```

### Stage 4: Full Migration (Week 4)
```python
# All operations use native
USE_TERMINUS_NATIVE_BRANCH = True
USE_UNIFIED_MERGE_ENGINE = True
DEPRECATED_LEGACY_CODE = True  # Warns on legacy usage
```

## ⚠️ Breaking Changes

### 1. Branch Naming
- **Old**: `feature/add-user` (slash allowed)
- **New**: `feature_add_user` (underscore only)
- **Reason**: TerminusDB doesn't allow slashes in branch names

### 2. Diff Response Format
- **Old**: Simple dict with changes array
- **New**: Patch object that needs conversion
- **Migration**: Use `diff_result.to_dict()` or handle Patch objects

### 3. Schema Requirements
- **Old**: Could insert documents without schema
- **New**: Schema must exist before document insertion
- **Migration**: Ensure schema creation in setup scripts

## 🔄 Rollback Plan

### Immediate Rollback
```bash
# Set environment variables
export USE_TERMINUS_NATIVE_BRANCH=false
export USE_UNIFIED_MERGE_ENGINE=false

# Restart services
docker-compose restart oms-monolith
```

### Monitoring Rollback Triggers
1. Error rate > 5% → Automatic rollback
2. Performance degradation > 50% → Manual review
3. Data inconsistency detected → Immediate rollback

## 📊 Performance Improvements

Based on initial testing:

| Operation | Legacy Time | Native Time | Improvement |
|-----------|-------------|-------------|-------------|
| Branch Create | 1.2s | 0.3s | 75% faster |
| Merge (no conflict) | 3.5s | 0.8s | 77% faster |
| Diff Generation | 2.1s | 0.5s | 76% faster |
| Branch List | 0.8s | 0.2s | 75% faster |

## 🧪 Testing Strategy

### Unit Tests
```bash
# Run legacy vs native comparison tests
pytest tests/integration/test_terminus_native.py -v

# Run performance benchmarks
pytest tests/performance/benchmark_terminus.py -v
```

### A/B Testing
```python
# Automatically runs both implementations and compares
@pytest.mark.parametrize("use_native", [True, False])
async def test_operation_compatibility(use_native):
    # Test implementation
```

### Smoke Tests
```bash
# Quick validation after deployment
./scripts/test_terminus_simple.py
```

## 🚨 Known Issues

### 1. WOQL API Changes
- **Issue**: `WOQLQuery.doctype()` doesn't exist in newer versions
- **Solution**: Use document insertion API directly

### 2. Authentication
- **Issue**: Token vs password authentication
- **Solution**: Use password auth for local, token for production

### 3. Transaction Handling
- **Issue**: Different transaction semantics
- **Solution**: Wrap operations in explicit transactions

## 📈 Monitoring

### Key Metrics
```python
# Track in Prometheus/Grafana
terminus_operations_total{operation="create_branch", implementation="native"}
terminus_operation_duration_seconds{operation="merge", implementation="native"}
terminus_errors_total{operation="diff", error_type="conflict"}
```

### Dashboard Queries
```promql
# Native adoption rate
sum(rate(terminus_operations_total{implementation="native"}[5m])) / 
sum(rate(terminus_operations_total[5m])) * 100

# Error rate comparison
sum(rate(terminus_errors_total{implementation="native"}[5m])) /
sum(rate(terminus_operations_total{implementation="native"}[5m]))
```

## 🛠️ Troubleshooting

### Common Issues

1. **"Branch already exists" error**
   - Cause: Branch wasn't cleaned up properly
   - Solution: Use `client.delete_branch()` before creating

2. **"Schema check failure"**
   - Cause: Document type not in schema
   - Solution: Create schema first or use schemaless graph

3. **"Cannot connect to TerminusDB"**
   - Cause: Wrong credentials or URL
   - Solution: Check docker-compose ports and credentials

### Debug Commands
```bash
# Check TerminusDB status
curl -u admin:admin123 http://localhost:16363/api/info

# List all branches
docker exec oms-test-terminusdb terminusdb branch list oms_test

# Check specific branch
docker exec oms-test-terminusdb terminusdb branch info oms_test feature_branch
```

## 📚 Resources

- [TerminusDB Documentation](https://docs.terminusdb.com/)
- [WOQL Query Language](https://docs.terminusdb.com/guides/how-to-guides/query)
- [Python Client API](https://docs.terminusdb.com/clients/python)

## 🤝 Support

For issues or questions:
1. Check this documentation first
2. Review test logs in `logs/terminus_migration/`
3. Contact the platform team

---

Last Updated: 2025-06-28
Version: 1.0