# Async Cache Usage Guidelines

## Overview

After the 3-layer architecture refactoring, we have both sync and async cache implementations. This guide ensures proper usage to avoid thread lock issues.

## Key Principles

### 1. Use Async Cache in Async Contexts

```python
# ❌ BAD: Using sync cache in async function
async def get_data():
    cache = get_cache_manager()  # Returns sync cache
    result = cache.get(key)  # BLOCKS event loop!
    
# ✅ GOOD: Using async cache in async function
async def get_data():
    cache = get_async_cache_manager()  # Returns async cache
    result = await cache.aget(key)  # Non-blocking
```

### 2. Cache Manager Selection

```python
from core.traversal.cache.services import (
    get_cache_manager,        # For sync contexts
    get_async_cache_manager   # For async contexts
)

# In sync code (e.g., traditional Flask routes)
def sync_handler():
    cache = get_cache_manager()
    return cache.get_query_result(query)

# In async code (e.g., GraphQL resolvers, FastAPI)
async def async_handler():
    cache = get_async_cache_manager()
    return await cache.aget_query_result(query)
```

### 3. Method Naming Convention

All async methods are prefixed with 'a':
- `get()` → `aget()`
- `put()` → `aput()`
- `delete()` → `adelete()`
- `clear()` → `aclear()`
- `stats()` → `astats()`

### 4. Import Restrictions

The following imports are forbidden by import-linter:

```python
# ❌ FORBIDDEN in api.graphql modules:
from core.traversal.cache.implementations.lru_cache import LRUCache
cache = LRUCache()  # Will fail CI

# ✅ ALLOWED:
from core.traversal.cache.services import get_async_cache_manager
cache = get_async_cache_manager()
```

## CI Gates

### 1. Import Linter
- Prevents direct usage of sync cache methods in async modules
- Enforces layer dependencies

### 2. Thread Lock Detector
- `scripts/ci/detect_thread_locks.py`
- Detects threading.Lock usage in async functions
- Part of CI pipeline

### 3. Testing

```python
# Test both sync and async paths
def test_sync_cache():
    cache = get_cache_manager()
    cache.put("key", "value")
    assert cache.get("key") == "value"

async def test_async_cache():
    cache = get_async_cache_manager()
    await cache.aput("key", "value")
    assert await cache.aget("key") == "value"
```

## Migration Checklist

When migrating existing code:

1. ✅ Identify async functions using cache
2. ✅ Replace `get_cache_manager()` with `get_async_cache_manager()`
3. ✅ Add `await` to all cache method calls
4. ✅ Update method names (add 'a' prefix)
5. ✅ Run thread lock detector
6. ✅ Test both sync and async paths

## Common Pitfalls

### 1. Mixing Sync/Async
```python
# ❌ BAD: Causes deadlock
async def process():
    cache = get_cache_manager()  # Sync cache
    async with some_async_resource():
        cache.get(key)  # DEADLOCK!
```

### 2. Forgetting await
```python
# ❌ BAD: Returns coroutine, not value
result = cache.aget(key)  # Missing await

# ✅ GOOD:
result = await cache.aget(key)
```

### 3. Wrong Cache Type
```python
# ❌ BAD: RuntimeError
cache = get_cache_manager()
await cache.aget(key)  # Sync cache doesn't have aget()

# ✅ GOOD:
cache = get_async_cache_manager()
await cache.aget(key)
```