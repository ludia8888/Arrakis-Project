"""
Unified LRU Cache implementation that bridges all existing cache implementations
"""

import asyncio
import threading
from typing import Optional, Any, Dict
from datetime import timedelta
from collections import OrderedDict

from ..interfaces import (
    CacheInterface,
    AsyncCacheInterface,
    CacheMetricsInterface,
    CacheStats,
    CacheMetrics,
    CacheEntry,
    CacheConfig,
    CacheLevel
)

# Import existing implementations to reuse
from core.traversal.cache.implementations.lru_cache import (
    LRUCache as TraversalLRUCache,
    AsyncLRUCache as TraversalAsyncLRUCache
)


class UnifiedLRUCache(CacheInterface[str, Any], CacheMetricsInterface):
    """
    Unified LRU cache that implements the canonical interface.
    Wraps the existing TraversalLRUCache for backward compatibility.
    """
    
    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self.cache_name = "unified_lru"
        self.cache_level = CacheLevel.L1_MEMORY
        
        # Delegate to existing implementation
        self._impl = TraversalLRUCache(
            max_size=self.config.max_entries,
            default_ttl=int(self.config.default_ttl.total_seconds())
        )
        
        # Additional metrics
        self._operation_durations: Dict[str, list] = {
            "get": [],
            "put": [],
            "delete": []
        }
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        import time
        start = time.time()
        try:
            return self._impl.get(key)
        finally:
            self._record_duration("get", time.time() - start)
    
    def put(self, key: str, value: Any, ttl: Optional[timedelta] = None) -> None:
        """Put value in cache"""
        import time
        start = time.time()
        try:
            ttl_seconds = int(ttl.total_seconds()) if ttl else None
            self._impl.put(key, value, ttl_seconds)
        finally:
            self._record_duration("put", time.time() - start)
    
    def delete(self, key: str) -> bool:
        """Delete from cache"""
        import time
        start = time.time()
        try:
            return self._impl.delete(key)
        finally:
            self._record_duration("delete", time.time() - start)
    
    def exists(self, key: str) -> bool:
        """Check if key exists"""
        return self._impl.get(key) is not None
    
    def clear(self) -> None:
        """Clear cache"""
        self._impl.clear()
    
    def size(self) -> int:
        """Get cache size"""
        return self._impl.size()
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics"""
        impl_stats = self._impl.stats()
        return CacheStats(
            cache_name=self.cache_name,
            cache_level=self.cache_level,
            current_size=impl_stats.current_size,
            max_size=impl_stats.max_size,
            hit_count=impl_stats.hits,
            miss_count=impl_stats.misses,
            eviction_count=impl_stats.evictions,
            total_memory_bytes=impl_stats.total_memory_bytes
        )
    
    def get_metrics(self) -> CacheMetrics:
        """Get Prometheus-compatible metrics"""
        stats = self.get_stats()
        label = f"{self.cache_name}:{self.cache_level.value}"
        
        return CacheMetrics(
            cache_hits_total={label: stats.hit_count},
            cache_misses_total={label: stats.miss_count},
            cache_evictions_total={label: stats.eviction_count},
            cache_size_bytes={label: stats.total_memory_bytes},
            cache_entries={label: stats.current_size},
            cache_operation_duration_seconds=self._operation_durations.copy()
        )
    
    def reset_metrics(self) -> None:
        """Reset metrics"""
        self._impl._hits = 0
        self._impl._misses = 0
        self._impl._evictions = 0
        self._operation_durations = {"get": [], "put": [], "delete": []}
    
    def _record_duration(self, operation: str, duration: float):
        """Record operation duration for metrics"""
        if self.config.enable_metrics:
            durations = self._operation_durations.setdefault(operation, [])
            durations.append(duration)
            # Keep only last 1000 measurements
            if len(durations) > 1000:
                self._operation_durations[operation] = durations[-1000:]


class UnifiedAsyncLRUCache(AsyncCacheInterface[str, Any], CacheMetricsInterface):
    """
    Unified async LRU cache implementation
    """
    
    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self.cache_name = "unified_async_lru"
        self.cache_level = CacheLevel.L1_MEMORY
        
        # Delegate to existing async implementation
        self._impl = TraversalAsyncLRUCache(
            max_size=self.config.max_entries,
            default_ttl=int(self.config.default_ttl.total_seconds())
        )
        
        # Sync wrapper for metrics (thread-safe)
        self._sync_impl = UnifiedLRUCache(config)
    
    async def aget(self, key: str) -> Optional[Any]:
        """Async get from cache"""
        import time
        start = time.time()
        try:
            return await self._impl.aget(key)
        finally:
            self._sync_impl._record_duration("get", time.time() - start)
    
    async def aput(self, key: str, value: Any, ttl: Optional[timedelta] = None) -> None:
        """Async put to cache"""
        import time
        start = time.time()
        try:
            ttl_seconds = int(ttl.total_seconds()) if ttl else None
            await self._impl.aput(key, value, ttl_seconds)
        finally:
            self._sync_impl._record_duration("put", time.time() - start)
    
    async def adelete(self, key: str) -> bool:
        """Async delete from cache"""
        import time
        start = time.time()
        try:
            return await self._impl.adelete(key)
        finally:
            self._sync_impl._record_duration("delete", time.time() - start)
    
    async def aexists(self, key: str) -> bool:
        """Async check existence"""
        result = await self._impl.aget(key)
        return result is not None
    
    async def aclear(self) -> None:
        """Async clear cache"""
        await self._impl.aclear()
    
    async def asize(self) -> int:
        """Async get size"""
        return await self._impl.asize()
    
    def get_stats(self) -> CacheStats:
        """Get stats (sync method for compatibility)"""
        # Use sync stats from implementation
        impl_stats = self._impl.stats()
        return CacheStats(
            cache_name=self.cache_name,
            cache_level=self.cache_level,
            current_size=impl_stats.current_size,
            max_size=impl_stats.max_size,
            hit_count=impl_stats.hits,
            miss_count=impl_stats.misses,
            eviction_count=impl_stats.evictions,
            total_memory_bytes=impl_stats.total_memory_bytes
        )
    
    def get_metrics(self) -> CacheMetrics:
        """Get metrics (sync for Prometheus)"""
        return self._sync_impl.get_metrics()
    
    def reset_metrics(self) -> None:
        """Reset metrics"""
        self._impl._hits = 0
        self._impl._misses = 0
        self._impl._evictions = 0
        self._sync_impl.reset_metrics()