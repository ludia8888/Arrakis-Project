"""
Test unified cache implementation
"""

import pytest
import asyncio
from datetime import timedelta

from shared.cache import (
    CacheRegistry,
    UnifiedLRUCache,
    UnifiedAsyncLRUCache,
    CacheConfig,
    get_traversal_cache,
    get_validation_cache
)


def test_cache_interface_compliance():
    """Test that all caches implement the unified interface"""
    cache = UnifiedLRUCache()
    
    # Test interface methods exist
    assert hasattr(cache, 'get')
    assert hasattr(cache, 'put')
    assert hasattr(cache, 'delete')
    assert hasattr(cache, 'exists')
    assert hasattr(cache, 'clear')
    assert hasattr(cache, 'size')
    assert hasattr(cache, 'get_stats')
    assert hasattr(cache, 'get_metrics')


def test_sync_cache_operations():
    """Test synchronous cache operations"""
    cache = UnifiedLRUCache(CacheConfig(max_entries=10))
    
    # Test put/get
    cache.put("key1", "value1")
    assert cache.get("key1") == "value1"
    
    # Test exists
    assert cache.exists("key1") is True
    assert cache.exists("nonexistent") is False
    
    # Test delete
    assert cache.delete("key1") is True
    assert cache.get("key1") is None
    assert cache.delete("key1") is False
    
    # Test TTL
    cache.put("key2", "value2", ttl=timedelta(milliseconds=100))
    assert cache.get("key2") == "value2"
    
    import time
    time.sleep(0.2)
    assert cache.get("key2") is None  # Expired


@pytest.mark.asyncio
async def test_async_cache_operations():
    """Test asynchronous cache operations"""
    cache = UnifiedAsyncLRUCache(CacheConfig(max_entries=10))
    
    # Test aput/aget
    await cache.aput("key1", "value1")
    assert await cache.aget("key1") == "value1"
    
    # Test aexists
    assert await cache.aexists("key1") is True
    assert await cache.aexists("nonexistent") is False
    
    # Test adelete
    assert await cache.adelete("key1") is True
    assert await cache.aget("key1") is None
    
    # Test clear
    await cache.aput("key2", "value2")
    await cache.aput("key3", "value3")
    assert await cache.asize() == 2
    
    await cache.aclear()
    assert await cache.asize() == 0


def test_cache_registry():
    """Test cache registry functionality"""
    # Clear registry first
    CacheRegistry.clear_all()
    
    # Register a cache
    CacheRegistry.register(
        "test_cache",
        UnifiedLRUCache,
        CacheConfig(max_entries=100)
    )
    
    # Get cache instance
    cache1 = CacheRegistry.get("test_cache", async_mode=False)
    cache2 = CacheRegistry.get("test_cache", async_mode=False)
    
    # Should return same instance
    assert cache1 is cache2
    
    # Test operations
    cache1.put("key", "value")
    assert cache2.get("key") == "value"


def test_cache_metrics():
    """Test cache metrics collection"""
    cache = UnifiedLRUCache(CacheConfig(enable_metrics=True))
    
    # Perform operations
    cache.put("key1", "value1")
    cache.get("key1")  # Hit
    cache.get("key2")  # Miss
    cache.delete("key1")
    
    # Check stats
    stats = cache.get_stats()
    assert stats.hit_count == 1
    assert stats.miss_count == 1
    assert stats.hit_rate == 0.5
    
    # Check metrics
    metrics = cache.get_metrics()
    assert len(metrics.cache_hits_total) > 0
    assert len(metrics.cache_operation_duration_seconds) > 0


def test_cache_eviction():
    """Test LRU eviction behavior"""
    cache = UnifiedLRUCache(CacheConfig(max_entries=3))
    
    # Fill cache
    cache.put("key1", "value1")
    cache.put("key2", "value2")
    cache.put("key3", "value3")
    
    # Access key1 to make it recently used
    cache.get("key1")
    
    # Add new entry, should evict key2 (least recently used)
    cache.put("key4", "value4")
    
    assert cache.exists("key1") is True
    assert cache.exists("key2") is False  # Evicted
    assert cache.exists("key3") is True
    assert cache.exists("key4") is True
    
    stats = cache.get_stats()
    assert stats.eviction_count > 0


def test_backward_compatibility():
    """Test backward compatibility aliases"""
    from shared.cache import SmartCacheManager
    
    # Should be same as UnifiedLRUCache
    assert SmartCacheManager is UnifiedLRUCache


def test_convenience_functions():
    """Test convenience cache getters"""
    traversal_cache = get_traversal_cache(async_mode=True)
    validation_cache = get_validation_cache(async_mode=False)
    
    assert isinstance(traversal_cache, UnifiedAsyncLRUCache)
    assert isinstance(validation_cache, UnifiedLRUCache)
    
    # Should return same instances on subsequent calls
    assert traversal_cache is get_traversal_cache(async_mode=True)
    assert validation_cache is get_validation_cache(async_mode=False)