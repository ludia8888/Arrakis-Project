# ADR-015: Async Threading Analysis and Migration Plan

## Status
Proposed

## Context
Following the successful migration of `core/traversal/caching.py` from `threading.RLock` to `asyncio.Lock`, a comprehensive analysis was performed on the entire codebase to identify other areas that may benefit from similar improvements.

## Analysis Results

### Already Using Async Patterns (No Changes Needed) ✅
These files already use `asyncio.Lock` and are properly implemented:
- `middleware/auth_secure.py` - Uses `asyncio.Lock` for token cache
- `core/validation/rules/timeseries_event_mapping_rule.py` - Uses `asyncio.Lock` for processing
- `core/idempotent/consumer_service.py` - Uses `asyncio.Lock` for processing and checkpoints
- `core/audit/audit_service.py` - Uses `asyncio.Lock` for batch processing
- `core/audit/audit_repository.py` - Uses `asyncio.Lock` for initialization
- `shared/infrastructure/unified_nats_client.py` - Uses `asyncio.Lock` for connections

### Potential Issues but Low Risk 🟡
These components use threading patterns but in contexts where it's acceptable:

1. **Background Services**
   - `core/event_consumer/*` - Event consumers running in separate processes
   - `services/grpc/server.py` - gRPC server with its own thread pool
   - `scripts/*` - Command-line utilities not running in async context

2. **Migration Scripts**
   - `migrations/migrate_to_distributed_locks.py` - One-time migration script

3. **SDK Code**
   - `sdks/python/oms_event_sdk_py/*` - Client SDK that needs to work in both sync/async contexts

### No Threading Usage Found ✅
Many files in the initial grep results only import models or use the word "Lock" in variable names/comments, but don't actually use threading:
- `core/branch/*` - Branch lock managers (use database locks, not threading)
- `core/optimistic_lock.py` - Database optimistic locking
- `api/graphql/*` - GraphQL resolvers (already async)
- `models/*` - Data models only

## Recommendations

### 1. No Immediate Action Required
The codebase is already well-architected for async operations. Most components that could benefit from async patterns are already using them.

### 2. Best Practices Going Forward
1. **New Code**: Always use `asyncio.Lock` in FastAPI/async contexts
2. **Code Reviews**: Check for threading usage in async code paths
3. **Testing**: Include concurrent access tests for new cache/state management code

### 3. Monitoring Points
While no immediate changes are needed, monitor these areas:
- Event consumer performance under high load
- gRPC server thread pool utilization
- SDK performance in async applications

## Decision
No additional threading-to-async migrations are necessary at this time. The codebase follows async best practices where appropriate.

## Consequences

### Positive
- Codebase is already optimized for async operations
- Clear separation between sync (scripts, SDKs) and async (API, services) contexts
- Minimal technical debt related to threading

### Negative
- None identified

## Future Considerations
1. If event consumers are moved to async (e.g., using aiokafka), review their threading usage
2. Consider async version of Python SDK for better async application integration
3. Monitor for new threading usage in code reviews