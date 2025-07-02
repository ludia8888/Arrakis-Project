"""
Multi-level cache implementation
"""

from typing import Optional, Any, Dict, List

from ..interfaces.models import CacheLevel, CacheConfig
from ..interfaces.contracts import CacheInterface
from .lru_cache import LRUCache, AsyncLRUCache


class MultiLevelCache:
    """
    Multi-level cache with L1 (memory) and L2 (persistent) levels.
    
    Cache hierarchy:
    - L1: Fast in-memory LRU cache
    - L2: Persistent cache (could be Redis, file-based, etc.)
    - L3: Distributed cache (future enhancement)
    """
    
    def __init__(self, config: Optional[CacheConfig] = None, async_mode: bool = False):
        self.config = config or CacheConfig()
        self.async_mode = async_mode
        
        # Initialize L1 cache (memory)
        if async_mode:
            self.l1_cache = AsyncLRUCache(
                max_size=self.config.query_cache_max_size,
                default_ttl=self.config.query_cache_ttl
            )
        else:
            self.l1_cache = LRUCache(
                max_size=self.config.query_cache_max_size,
                default_ttl=self.config.query_cache_ttl
            )
        
        # Initialize L2 cache (simplified - in real implementation would be Redis/DB)
        if async_mode:
            self.l2_cache = AsyncLRUCache(
                max_size=self.config.result_cache_max_size,
                default_ttl=self.config.result_cache_ttl
            )
        else:
            self.l2_cache = LRUCache(
                max_size=self.config.result_cache_max_size,
                default_ttl=self.config.result_cache_ttl
            )
        
        # Cache level preferences
        self._level_preferences = {
            "query_results": [CacheLevel.L1_MEMORY, CacheLevel.L2_PERSISTENT],
            "query_plans": [CacheLevel.L1_MEMORY],
            "graph_metrics": [CacheLevel.L1_MEMORY, CacheLevel.L2_PERSISTENT]
        }
        
        # Statistics
        self._l1_requests = 0
        self._l2_requests = 0
        self._l1_hits = 0
        self._l2_hits = 0
    
    def get(self, key: str, cache_type: str = "query_results") -> Optional[Any]:
        """Get value from multi-level cache"""
        levels = self._level_preferences.get(cache_type, [CacheLevel.L1_MEMORY])
        
        for level in levels:
            if level == CacheLevel.L1_MEMORY:
                self._l1_requests += 1
                value = self.l1_cache.get(key)
                if value is not None:
                    self._l1_hits += 1
                    return value
                    
            elif level == CacheLevel.L2_PERSISTENT:
                self._l2_requests += 1
                value = self.l2_cache.get(key)
                if value is not None:
                    self._l2_hits += 1
                    # Promote to L1
                    self.l1_cache.put(key, value)
                    return value
        
        return None
    
    def put(self, key: str, value: Any, cache_type: str = "query_results", 
            ttl_seconds: Optional[int] = None) -> None:
        """Put value in appropriate cache levels"""
        levels = self._level_preferences.get(cache_type, [CacheLevel.L1_MEMORY])
        
        for level in levels:
            if level == CacheLevel.L1_MEMORY:
                self.l1_cache.put(key, value, ttl_seconds)
            elif level == CacheLevel.L2_PERSISTENT:
                self.l2_cache.put(key, value, ttl_seconds)
    
    def delete(self, key: str) -> bool:
        """Delete from all cache levels"""
        deleted = False
        deleted |= self.l1_cache.delete(key)
        deleted |= self.l2_cache.delete(key)
        return deleted
    
    def clear(self, cache_type: Optional[str] = None) -> None:
        """Clear specific cache type or all caches"""
        if cache_type is None:
            self.l1_cache.clear()
            self.l2_cache.clear()
        else:
            levels = self._level_preferences.get(cache_type, [])
            for level in levels:
                if level == CacheLevel.L1_MEMORY:
                    self.l1_cache.clear()
                elif level == CacheLevel.L2_PERSISTENT:
                    self.l2_cache.clear()
    
    def stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        l1_stats = self.l1_cache.stats()
        l2_stats = self.l2_cache.stats()
        
        total_l1_requests = self._l1_requests
        total_l2_requests = self._l2_requests
        
        return {
            "multi_level_stats": {
                "l1_hit_rate": self._l1_hits / total_l1_requests if total_l1_requests > 0 else 0,
                "l2_hit_rate": self._l2_hits / total_l2_requests if total_l2_requests > 0 else 0,
                "total_requests": total_l1_requests + total_l2_requests,
                "cache_promotion_rate": self._l2_hits / total_l2_requests if total_l2_requests > 0 else 0
            },
            "l1_cache": l1_stats.__dict__,
            "l2_cache": l2_stats.__dict__
        }
    
    # Async methods for async mode
    async def aget(self, key: str, cache_type: str = "query_results") -> Optional[Any]:
        """Async get value from multi-level cache"""
        if not self.async_mode:
            raise RuntimeError("aget() called on non-async MultiLevelCache")
        
        levels = self._level_preferences.get(cache_type, [CacheLevel.L1_MEMORY])
        
        for level in levels:
            if level == CacheLevel.L1_MEMORY:
                self._l1_requests += 1
                value = await self.l1_cache.aget(key)
                if value is not None:
                    self._l1_hits += 1
                    return value
                    
            elif level == CacheLevel.L2_PERSISTENT:
                self._l2_requests += 1
                value = await self.l2_cache.aget(key)
                if value is not None:
                    self._l2_hits += 1
                    # Promote to L1
                    await self.l1_cache.aput(key, value)
                    return value
        
        return None
    
    async def aput(self, key: str, value: Any, cache_type: str = "query_results", 
                   ttl_seconds: Optional[int] = None) -> None:
        """Async put value in appropriate cache levels"""
        if not self.async_mode:
            raise RuntimeError("aput() called on non-async MultiLevelCache")
        
        levels = self._level_preferences.get(cache_type, [CacheLevel.L1_MEMORY])
        
        for level in levels:
            if level == CacheLevel.L1_MEMORY:
                await self.l1_cache.aput(key, value, ttl_seconds)
            elif level == CacheLevel.L2_PERSISTENT:
                await self.l2_cache.aput(key, value, ttl_seconds)
    
    async def adelete(self, key: str) -> bool:
        """Async delete from all cache levels"""
        if not self.async_mode:
            raise RuntimeError("adelete() called on non-async MultiLevelCache")
        
        deleted = False
        deleted |= await self.l1_cache.adelete(key)
        deleted |= await self.l2_cache.adelete(key)
        return deleted
    
    async def aclear(self, cache_type: Optional[str] = None) -> None:
        """Async clear specific cache type or all caches"""
        if not self.async_mode:
            raise RuntimeError("aclear() called on non-async MultiLevelCache")
        
        if cache_type is None:
            await self.l1_cache.aclear()
            await self.l2_cache.aclear()
        else:
            levels = self._level_preferences.get(cache_type, [])
            for level in levels:
                if level == CacheLevel.L1_MEMORY:
                    await self.l1_cache.aclear()
                elif level == CacheLevel.L2_PERSISTENT:
                    await self.l2_cache.aclear()
    
    async def astats(self) -> Dict[str, Any]:
        """Async get comprehensive cache statistics"""
        if not self.async_mode:
            raise RuntimeError("astats() called on non-async MultiLevelCache")
        
        l1_stats = await self.l1_cache.astats()
        l2_stats = await self.l2_cache.astats()
        
        total_l1_requests = self._l1_requests
        total_l2_requests = self._l2_requests
        
        return {
            "multi_level_stats": {
                "l1_hit_rate": self._l1_hits / total_l1_requests if total_l1_requests > 0 else 0,
                "l2_hit_rate": self._l2_hits / total_l2_requests if total_l2_requests > 0 else 0,
                "total_requests": total_l1_requests + total_l2_requests,
                "cache_promotion_rate": self._l2_hits / total_l2_requests if total_l2_requests > 0 else 0
            },
            "l1_cache": l1_stats.__dict__,
            "l2_cache": l2_stats.__dict__
        }