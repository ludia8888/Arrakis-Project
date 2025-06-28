# TerminusDB Integration Guide

This document provides practical guidance for developers working with TerminusDB integration in the OMS system.

## Quick Reference

### Integration Strategies
- **DELEGATE**: Use TerminusDB directly (minimal wrapper)
- **ENHANCE**: TerminusDB + business logic
- **COORDINATE**: Both systems with conflict resolution
- **SIMULATE**: Test with TerminusDB, apply our rules

### Key Integration Points

```python
# Schema Validation (ENHANCE strategy)
from core.validation.pipeline import ValidationPipeline

pipeline = ValidationPipeline()
result = await pipeline.validate_entity("ObjectType", entity_data)

# Path Queries (ENHANCE strategy)  
from core.traversal.async_wrapper import create_async_traversal_facade

facade = await create_async_traversal_facade(terminus_client)
paths = await facade.find_dependency_paths("Entity1", "Entity2")

# Merge Validation (COORDINATE strategy)
from core.validation.merge_validation_service import MergeValidationService

service = MergeValidationService()
conflicts = await service.validate_merge("feature-branch", "main")
```

## Development Patterns

### 1. Adding New Business Rules

```python
# ✅ Correct: Enhance TerminusDB validation
class CustomBusinessRule(BreakingChangeRule):
    async def check(self, entity_data, context):
        # Let TerminusDB validate structure first
        if context.terminus_client:
            terminus_valid = await context.terminus_client.validate_schema_changes(
                entity_data, context.db, context.branch
            )
            if not terminus_valid["valid"]:
                return terminus_valid  # Return TerminusDB errors
        
        # Add business-specific validation
        return self._validate_business_logic(entity_data)
```

### 2. Querying with Business Context

```python
# ✅ Use TerminusDB native queries + business interpretation
async def find_critical_dependencies(start_entity: str):
    # Step 1: Use TerminusDB native path queries
    woql = WOQLQuery().path("@schema:depends_on", start_entity, None, {"@type": "Dependency"})
    raw_paths = await terminus_client.query(woql.to_dict())
    
    # Step 2: Add business interpretation
    critical_paths = []
    for path in raw_paths:
        criticality = calculate_business_criticality(path)
        if criticality > threshold:
            critical_paths.append({
                "terminus_path": path,
                "business_impact": criticality,
                "mitigation_strategy": suggest_mitigation(path)
            })
    
    return critical_paths
```

### 3. Error Handling

```python
async def safe_terminus_operation(operation_func):
    try:
        # Always try TerminusDB first
        terminus_result = await operation_func()
        
        if terminus_result.get("errors"):
            # Translate TerminusDB errors to business context
            return {
                "success": False,
                "errors": translate_to_business_errors(terminus_result["errors"]),
                "source": "terminus_native"
            }
        
        return {
            "success": True,
            "data": terminus_result,
            "source": "terminus_native"
        }
        
    except TerminusDBException as e:
        logger.error(f"TerminusDB operation failed: {e}")
        return {
            "success": False,
            "errors": [f"Database operation failed: {str(e)}"],
            "source": "terminus_error"
        }
```

## Performance Guidelines

### Caching Strategy
```python
# Cache TerminusDB results with business context
cache_key = f"terminus:path_query:{start}:{end}:{hash(business_params)}"

# Check cache first
cached = await cache.get(cache_key)
if cached:
    return add_business_context(cached)

# Query TerminusDB
terminus_result = await terminus_client.query(woql)

# Cache for future use
await cache.set(cache_key, terminus_result, ttl=300)  # 5 min TTL

return add_business_context(terminus_result)
```

### Query Optimization
```python
# ✅ Optimize WOQL queries for TerminusDB
def build_optimized_dependency_query(start_node: str, max_depth: int = 5):
    """Build efficient WOQL query using TerminusDB native features"""
    return (
        WOQLQuery()
        .limit(1000)  # Prevent runaway queries
        .path("@schema:depends_on", start_node, "v:End", {"@type": "v:PathType"})
        .opt()  # Use TerminusDB query optimization
        .select("v:End", "v:PathType")
        .where()
        .depth("v:End", max_depth)  # Use native depth limiting
    )
```

## Testing Patterns

### Unit Tests
```python
# Use mock adapters for unit testing
def test_business_validation():
    mock_terminus = MockTerminusAdapter()
    mock_terminus.set_validation_result({"valid": True})
    
    validator = BusinessValidator(terminus=mock_terminus)
    result = await validator.validate(test_data)
    
    assert result["business_rules_applied"]
    assert mock_terminus.call_count["validate_schema_changes"] == 1
```

### Integration Tests
```python
# Use real TerminusDB for integration testing
async def test_end_to_end_validation():
    real_terminus = TerminusDBAdapter(real_client)
    pipeline = ValidationPipeline(terminus=real_terminus)
    
    result = await pipeline.validate_entity("ObjectType", test_entity)
    
    # Verify both TerminusDB and business validation occurred
    assert result.stage_results[ValidationStage.TERMINUS_CHECK]["success"]
    assert result.stage_results[ValidationStage.RULE_ENGINE]["success"]
```

## Common Pitfalls

### ❌ Don't Duplicate TerminusDB Features
```python
# ❌ BAD: Reimplementing schema validation
def validate_entity_structure(entity):
    if not entity.get("@type"):
        return {"valid": False, "error": "Missing @type"}
    # ... more schema validation
```

```python
# ✅ GOOD: Use TerminusDB + add business value
async def validate_entity_with_business_rules(entity, context):
    # Let TerminusDB handle schema validation
    terminus_result = await context.terminus.validate_document(entity)
    
    if not terminus_result["valid"]:
        return terminus_result
    
    # Add business-specific validation
    return await apply_business_rules(entity, context)
```

### ❌ Don't Bypass TerminusDB When Available
```python
# ❌ BAD: Custom graph traversal
def find_dependencies_custom(start_node):
    visited = set()
    dependencies = []
    # ... custom BFS/DFS implementation
```

```python
# ✅ GOOD: Use TerminusDB path queries
async def find_dependencies_efficient(start_node):
    woql = WOQLQuery().path("@schema:depends_on", start_node, "v:Dep")
    return await terminus_client.query(woql.to_dict())
```

## Configuration

### Environment Variables
```bash
# TerminusDB Integration Settings
OMS_TERMINUS_DEFAULT_DB=oms
OMS_TERMINUS_DEFAULT_BRANCH=main
OMS_TERMINUS_QUERY_TIMEOUT=30.0
OMS_TERMINUS_ENABLE_NATIVE_VALIDATION=true

# Performance Settings
OMS_ENABLE_TERMINUS_CACHE=true
OMS_TERMINUS_CACHE_TTL=300
OMS_MAX_TRAVERSAL_DEPTH=20
```

### Validation Pipeline Configuration
```python
from core.validation.config import ValidationConfig

config = ValidationConfig(
    enable_terminus_validation=True,
    enable_rule_engine=True,
    fail_fast_mode=True,
    terminus_default_db="oms",
    terminus_default_branch="main"
)
```

## Monitoring & Debugging

### Performance Metrics
```python
# Monitor integration performance
logger.info(f"TerminusDB query time: {terminus_time_ms}ms")
logger.info(f"Business rules time: {business_time_ms}ms") 
logger.info(f"Total pipeline time: {total_time_ms}ms")

# Track boundary adherence
boundary_manager = get_boundary_manager()
validation_result = boundary_manager.validate_integration(
    TerminusFeature.SCHEMA_VALIDATION, 
    operation="validate_entity"
)
```

### Debug Logging
```python
# Enable detailed TerminusDB integration logging
logging.getLogger("core.validation.adapters.terminus_traversal_adapter").setLevel(logging.DEBUG)
logging.getLogger("core.traversal.traversal_engine").setLevel(logging.DEBUG)
```

## Migration Notes

When migrating existing code to use the boundary definitions:

1. **Identify TerminusDB Duplications**: Look for custom implementations of schema validation, graph traversal, or merge logic
2. **Replace with Enhanced Patterns**: Use the ENHANCE strategy to add business value on top of TerminusDB
3. **Add Boundary Validation**: Use `validate_terminus_integration()` to ensure proper integration
4. **Update Tests**: Use mock adapters for unit tests, real TerminusDB for integration tests

For detailed boundary definitions and architectural decisions, see [ADR-001: TerminusDB Integration Boundaries](./adr/TerminusDB_Integration_Boundaries.md).