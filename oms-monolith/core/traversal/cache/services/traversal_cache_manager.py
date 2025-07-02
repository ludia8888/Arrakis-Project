"""
Traversal cache manager service
"""

import hashlib
import json
from typing import Optional, Any, Dict, Callable

from ..interfaces.contracts import CacheManagerInterface
from ..interfaces.models import CacheConfig
from ..implementations.multi_level_cache import MultiLevelCache
from ..implementations.cache_warmer import CacheWarmer, AsyncCacheWarmer
from core.traversal.models import TraversalQuery, TraversalResult
from ..config_adapter import get_cache_config


class TraversalCacheManager(CacheManagerInterface):
    """
    Specialized cache manager for graph traversal operations.
    
    Provides caching for:
    - Query results
    - Query execution plans
    - Graph metrics
    - Dependency paths
    """
    
    def __init__(self, config: Optional[CacheConfig] = None, async_mode: bool = False):
        self.config = config or get_cache_config()
        self.async_mode = async_mode
        self.cache = MultiLevelCache(self.config, async_mode=async_mode)
        
        # Use appropriate warmer based on mode
        if async_mode:
            self.warmer = AsyncCacheWarmer(self.cache, self.config)
        else:
            self.warmer = CacheWarmer(self.cache, self.config)
        
        # Query result cache keys
        self._result_cache_prefix = "result:"
        self._plan_cache_prefix = "plan:"
        self._metrics_cache_prefix = "metrics:"
        self._path_cache_prefix = "path:"
    
    def get_query_result(self, query: TraversalQuery) -> Optional[TraversalResult]:
        """Get cached query result"""
        cache_key = self._generate_query_cache_key(query)
        return self.cache.get(cache_key, "query_results")
    
    def cache_query_result(self, query: TraversalQuery, result: TraversalResult, 
                          ttl_seconds: Optional[int] = None) -> None:
        """Cache query result"""
        cache_key = self._generate_query_cache_key(query)
        ttl = ttl_seconds or self.config.query_cache_ttl
        self.cache.put(cache_key, result, "query_results", ttl)
    
    def get_query_plan(self, query_fingerprint: str) -> Optional[Any]:
        """Get cached query execution plan"""
        cache_key = f"{self._plan_cache_prefix}{query_fingerprint}"
        return self.cache.get(cache_key, "query_plans")
    
    def cache_query_plan(self, query_fingerprint: str, plan: Any, 
                        ttl_seconds: Optional[int] = None) -> None:
        """Cache query execution plan"""
        cache_key = f"{self._plan_cache_prefix}{query_fingerprint}"
        ttl = ttl_seconds or self.config.plan_cache_ttl
        self.cache.put(cache_key, plan, "query_plans", ttl)
    
    def get_graph_metrics(self, metrics_key: str) -> Optional[Any]:
        """Get cached graph metrics"""
        cache_key = f"{self._metrics_cache_prefix}{metrics_key}"
        return self.cache.get(cache_key, "graph_metrics")
    
    def cache_graph_metrics(self, metrics_key: str, metrics: Any, 
                           ttl_seconds: Optional[int] = None) -> None:
        """Cache graph metrics"""
        cache_key = f"{self._metrics_cache_prefix}{metrics_key}"
        ttl = ttl_seconds or self.config.result_cache_ttl
        self.cache.put(cache_key, metrics, "graph_metrics", ttl)
    
    def invalidate_query_cache(self, pattern: Optional[str] = None) -> None:
        """Invalidate query cache (useful after schema changes)"""
        if pattern is None:
            self.cache.clear("query_results")
        else:
            # In a real implementation, would support pattern-based invalidation
            self.cache.clear("query_results")
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        stats = self.cache.stats()
        
        # Add traversal-specific metrics
        stats["traversal_cache"] = {
            "result_cache_enabled": self.config.enable_result_cache,
            "plan_cache_enabled": self.config.enable_plan_cache,
            "warming_enabled": self.config.enable_cache_warming,
            "eviction_policy": self.config.eviction_policy.value,
            "cache_levels": len(self.cache._level_preferences)
        }
        
        return stats
    
    def start_cache_warming(self, query_executor: Callable[[str], Any]) -> None:
        """Start cache warming service"""
        self.warmer.start_warming(query_executor)
    
    def stop_cache_warming(self) -> None:
        """Stop cache warming service"""
        self.warmer.stop_warming()
    
    def _generate_query_cache_key(self, query: TraversalQuery) -> str:
        """Generate cache key for traversal query"""
        # Create deterministic hash of query parameters
        query_dict = {
            'start_nodes': sorted(query.start_nodes),
            'relations': sorted(query.relations),
            'direction': query.direction.value,
            'max_depth': query.max_depth,
            'limit': query.limit,
            'filters': dict(sorted(query.filters.items())),
            'include_metadata': query.include_metadata
        }
        
        query_json = json.dumps(query_dict, sort_keys=True)
        query_hash = hashlib.md5(query_json.encode()).hexdigest()
        
        return f"{self._result_cache_prefix}{query_hash}"
    
    # Async methods for async mode
    async def aget_query_result(self, query: TraversalQuery) -> Optional[TraversalResult]:
        """Async get cached query result"""
        if not self.async_mode:
            raise RuntimeError("Async method called on non-async TraversalCacheManager")
        cache_key = self._generate_query_cache_key(query)
        return await self.cache.aget(cache_key, "query_results")
    
    async def acache_query_result(self, query: TraversalQuery, result: TraversalResult, 
                                  ttl_seconds: Optional[int] = None) -> None:
        """Async cache query result"""
        if not self.async_mode:
            raise RuntimeError("Async method called on non-async TraversalCacheManager")
        cache_key = self._generate_query_cache_key(query)
        ttl = ttl_seconds or self.config.query_cache_ttl
        await self.cache.aput(cache_key, result, "query_results", ttl)
    
    async def aget_query_plan(self, query_fingerprint: str) -> Optional[Any]:
        """Async get cached query execution plan"""
        if not self.async_mode:
            raise RuntimeError("Async method called on non-async TraversalCacheManager")
        cache_key = f"{self._plan_cache_prefix}{query_fingerprint}"
        return await self.cache.aget(cache_key, "query_plans")
    
    async def acache_query_plan(self, query_fingerprint: str, plan: Any, 
                                ttl_seconds: Optional[int] = None) -> None:
        """Async cache query execution plan"""
        if not self.async_mode:
            raise RuntimeError("Async method called on non-async TraversalCacheManager")
        cache_key = f"{self._plan_cache_prefix}{query_fingerprint}"
        ttl = ttl_seconds or self.config.plan_cache_ttl
        await self.cache.aput(cache_key, plan, "query_plans", ttl)
    
    async def aget_graph_metrics(self, metrics_key: str) -> Optional[Any]:
        """Async get cached graph metrics"""
        if not self.async_mode:
            raise RuntimeError("Async method called on non-async TraversalCacheManager")
        cache_key = f"{self._metrics_cache_prefix}{metrics_key}"
        return await self.cache.aget(cache_key, "graph_metrics")
    
    async def acache_graph_metrics(self, metrics_key: str, metrics: Any, 
                                   ttl_seconds: Optional[int] = None) -> None:
        """Async cache graph metrics"""
        if not self.async_mode:
            raise RuntimeError("Async method called on non-async TraversalCacheManager")
        cache_key = f"{self._metrics_cache_prefix}{metrics_key}"
        ttl = ttl_seconds or self.config.result_cache_ttl
        await self.cache.aput(cache_key, metrics, "graph_metrics", ttl)
    
    async def ainvalidate_query_cache(self, pattern: Optional[str] = None) -> None:
        """Async invalidate query cache"""
        if not self.async_mode:
            raise RuntimeError("Async method called on non-async TraversalCacheManager")
        if pattern is None:
            await self.cache.aclear("query_results")
        else:
            # In a real implementation, would support pattern-based invalidation
            await self.cache.aclear("query_results")
    
    async def aget_cache_statistics(self) -> Dict[str, Any]:
        """Async get comprehensive cache statistics"""
        if not self.async_mode:
            raise RuntimeError("Async method called on non-async TraversalCacheManager")
        stats = await self.cache.astats()
        
        # Add traversal-specific metrics
        stats["traversal_cache"] = {
            "result_cache_enabled": self.config.enable_result_cache,
            "plan_cache_enabled": self.config.enable_plan_cache,
            "warming_enabled": self.config.enable_cache_warming,
            "eviction_policy": self.config.eviction_policy.value,
            "cache_levels": len(self.cache._level_preferences),
            "async_mode": self.async_mode
        }
        
        return stats
    
    async def astart_cache_warming(self, query_executor: Callable[[str], Any]) -> None:
        """Async start cache warming service"""
        if not self.async_mode:
            raise RuntimeError("Async method called on non-async TraversalCacheManager")
        await self.warmer.start_warming(query_executor)
    
    async def astop_cache_warming(self) -> None:
        """Async stop cache warming service"""
        if not self.async_mode:
            raise RuntimeError("Async method called on non-async TraversalCacheManager")
        await self.warmer.stop_warming()


# Global cache manager instances
_cache_manager: Optional[TraversalCacheManager] = None
_async_cache_manager: Optional[TraversalCacheManager] = None

def get_cache_manager(config: Optional[CacheConfig] = None) -> TraversalCacheManager:
    """Get global cache manager instance (sync version)"""
    global _cache_manager
    
    if _cache_manager is None:
        _cache_manager = TraversalCacheManager(config, async_mode=False)
    
    return _cache_manager

def get_async_cache_manager(config: Optional[CacheConfig] = None) -> TraversalCacheManager:
    """Get global async cache manager instance"""
    global _async_cache_manager
    
    if _async_cache_manager is None:
        _async_cache_manager = TraversalCacheManager(config, async_mode=True)
    
    return _async_cache_manager

def reset_cache_manager():
    """Reset global cache manager (useful for testing)"""
    global _cache_manager, _async_cache_manager
    
    if _cache_manager:
        _cache_manager.stop_cache_warming()
    _cache_manager = None
    
    if _async_cache_manager:
        # For async cache manager, we need to handle async stop
        # This is a sync function, so we can't await here
        # The async warmer will be cancelled when the event loop closes
        if hasattr(_async_cache_manager.warmer, '_warming_task'):
            task = _async_cache_manager.warmer._warming_task
            if task and not task.done():
                task.cancel()
    _async_cache_manager = None