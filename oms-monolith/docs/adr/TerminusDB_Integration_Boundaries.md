# ADR-001: TerminusDB Integration Boundary Definitions

## Status
Accepted

## Date
2024-06-28

## Context

The OMS (Ontology Management System) integrates with TerminusDB to provide enterprise-grade graph traversal and validation capabilities. To prevent duplication of functionality and ensure optimal performance, we need clear boundaries between TerminusDB native features and our custom business logic layers.

## Problem

Without clear boundaries, we risk:
- **Code Duplication**: Reimplementing functionality that TerminusDB already provides efficiently
- **Performance Degradation**: Using suboptimal approaches when native features are available
- **Maintenance Overhead**: Managing redundant validation logic across multiple layers
- **Integration Complexity**: Unclear responsibilities between system components

## Decision

We establish clear **Integration Boundaries** for each TerminusDB feature using four integration strategies:

### Integration Strategies

1. **DELEGATE**: Use TerminusDB directly with minimal wrapper
2. **ENHANCE**: Use TerminusDB as foundation + add business logic
3. **SIMULATE**: Test with TerminusDB, apply our validation rules
4. **COORDINATE**: Run both systems in parallel with conflict resolution

## Boundary Definitions

### 1. Schema Validation
**Strategy**: ENHANCE  
**TerminusDB Responsibility**: Basic schema constraint validation (types, cardinality, domain/range), referential integrity, ACID compliance  
**Our Layer Responsibility**: Business rule validation, policy enforcement, migration planning, impact analysis, error translation

**Integration Points**:
- `validation_pipeline.py`: TERMINUS_CHECK stage
- `terminus_error_handler.py`: Error translation  
- `rule_registry.py`: Business rules after schema validation

**Conflict Resolution**: TerminusDB validation runs first as 'pre-filter'. If TerminusDB rejects, we don't proceed to business rules. If TerminusDB accepts, we apply additional business validation.

**Performance**: TerminusDB validation is fast (native C++). Our business rules add ~10-50ms depending on complexity.

### 2. Branch Diff
**Strategy**: ENHANCE  
**TerminusDB Responsibility**: Raw entity-level differences between branches, structural change detection, commit history  
**Our Layer Responsibility**: Business impact analysis, breaking change detection, migration strategy recommendation, stakeholder notification

**Integration Points**:
- `ports.py`: get_branch_diff()
- `merge_validation_service.py`: Impact analysis
- `adapters/terminus_traversal_adapter.py`: Diff wrapper

**Conflict Resolution**: No conflict - complementary responsibilities. TerminusDB provides data, we analyze business meaning.

**Performance**: TerminusDB diff is O(log n) with Git-like efficiency. Our analysis is O(entities_changed × rules_count).

### 3. Merge Conflicts
**Strategy**: COORDINATE  
**TerminusDB Responsibility**: Structural merge conflicts (same entity modified in both branches), three-way merge resolution, conflict markers  
**Our Layer Responsibility**: Semantic conflict detection, business rule conflicts, resolution strategy recommendation, approval workflows

**Integration Points**:
- `merge_validation_service.py`: Full merge validation
- `traversal/merge_validator.py`: DEPRECATED facade
- `ports.py`: detect_merge_conflicts()

**Conflict Resolution**: Sequential processing: TerminusDB structural conflicts first, then our semantic conflicts. Both must be resolved for merge.

**Performance**: TerminusDB merge detection: ~50-200ms per branch. Our semantic analysis: ~100-500ms depending on rule complexity.

### 4. Path Queries
**Strategy**: ENHANCE  
**TerminusDB Responsibility**: Efficient graph traversal with path() queries, transitive closure computation, cycle detection  
**Our Layer Responsibility**: Business relationship semantics, dependency policy enforcement, critical path identification, impact propagation analysis

**Integration Points**:
- `traversal_engine.py`: WOQL path query construction
- `dependency_analyzer.py`: Business logic on traversal results
- `validation rules`: Dependency validation

**Conflict Resolution**: No conflict - layered approach. TerminusDB provides efficient traversal, we interpret results according to business rules.

**Performance**: TerminusDB path queries: O(V + E) with native optimization. Our analysis: O(results × business_rules).

### 5. ACL System
**Strategy**: COORDINATE  
**TerminusDB Responsibility**: Database-level access control, user authentication, branch-level permissions, query-level security  
**Our Layer Responsibility**: Business-level authorization, role-based policies, approval workflows, audit logging, enterprise governance

**Integration Points**:
- `policy_server_port.py`: Enterprise policy validation
- `pipeline.py`: POLICY stage before TerminusDB
- `middleware/auth_msa.py`: MSA authentication integration

**Conflict Resolution**: Policy hierarchy: PolicyServer (business) → TerminusDB (technical). Both must approve for operation to proceed. PolicyServer can be more restrictive.

**Performance**: TerminusDB ACL: ~1-5ms per operation. PolicyServer: ~10-50ms for complex business rules.

## Implementation Guidelines

### 1. Before Adding New Validation Logic
```python
# ❌ BAD: Reimplementing TerminusDB functionality
def validate_schema_constraints(schema):
    # Custom constraint checking
    pass

# ✅ GOOD: Enhancing TerminusDB validation
async def validate_business_rules(schema, terminus_result):
    if not terminus_result.valid:
        return terminus_result  # TerminusDB already rejected
    
    # Add business-specific validation
    return enhance_with_business_context(terminus_result)
```

### 2. Query Optimization Pattern
```python
# ✅ Use TerminusDB native features first
woql_query = WOQLQuery().path("@schema:depends_on", start_node, end_node)
terminus_paths = await terminus_client.query(woql_query)

# ✅ Then add business interpretation
business_paths = []
for path in terminus_paths:
    business_context = analyze_business_impact(path)
    business_paths.append({
        "technical_path": path,
        "business_impact": business_context,
        "critical_level": calculate_criticality(path)
    })
```

### 3. Error Handling Strategy
```python
try:
    # Let TerminusDB handle first
    terminus_result = await terminus_client.validate_schema(schema)
    
    if not terminus_result.success:
        # Translate TerminusDB errors to business context
        return translate_terminus_errors(terminus_result)
    
    # Add business validation
    business_result = await business_validator.validate(schema)
    return combine_results(terminus_result, business_result)
    
except TerminusDBError as e:
    # Clear error handling hierarchy
    return handle_terminus_error(e)
```

## Performance Characteristics

| Operation | TerminusDB Native | Our Enhancement | Total Pipeline |
|-----------|------------------|-----------------|----------------|
| Schema Validation | ~1-10ms | +10-50ms | ~11-60ms |
| Branch Diff | ~50-200ms | +20-100ms | ~70-300ms |
| Path Queries | ~5-50ms | +10-100ms | ~15-150ms |
| Merge Conflicts | ~50-200ms | +100-500ms | ~150-700ms |
| ACL Check | ~1-5ms | +10-50ms | ~11-55ms |

## Benefits

1. **No Duplication**: Clear separation prevents reimplementing TerminusDB features
2. **Optimal Performance**: Use TerminusDB strengths, add minimal overhead
3. **Clear Responsibility**: Each layer has distinct, well-defined roles
4. **Maintainable**: Changes to business logic don't affect TerminusDB integration
5. **Testable**: Mock boundaries for unit testing, real integration for system tests

## Implementation Status

- ✅ **Schema Validation**: Implemented with ENHANCE strategy
- ✅ **Branch Diff**: Implemented with ENHANCE strategy  
- ✅ **Merge Conflicts**: Implemented with COORDINATE strategy
- ✅ **Path Queries**: Implemented with ENHANCE strategy
- ✅ **ACL System**: Implemented with COORDINATE strategy

## Migration Path

### Phase 1: Boundary Enforcement (✅ Complete)
- Remove duplicate validation logic
- Implement clear integration points
- Add boundary validation checks

### Phase 2: Performance Optimization (✅ Complete)
- Profile each integration boundary
- Optimize business rule execution
- Add caching where appropriate

### Phase 3: Documentation & Training (Current)
- Document integration patterns
- Create developer guidelines
- Establish code review standards

## Related Documents

- [TerminusDB Python SDK Documentation](https://docs.terminusdb.com/python-client/)
- [WOQL Query Language Reference](https://docs.terminusdb.com/woql/)
- [Enterprise Validation Architecture](./Enterprise_Validation_Architecture.md)

## Code Examples

See implementation in:
- `core/validation/terminus_boundary_definition.py` - Boundary definitions
- `core/validation/pipeline.py` - Integration pipeline
- `core/validation/adapters/terminus_traversal_adapter.py` - Adapter implementation
- `core/traversal/traversal_engine.py` - Enhanced traversal engine

---

**This ADR ensures our OMS system leverages TerminusDB's native capabilities optimally while adding clear business value through our validation layers.**