"""
TerminusDB Cache Adapter - Implements unified interface for TerminusDB-backed cache
"""

import json
import hashlib
import logging
from typing import Optional, Any, Dict
from datetime import datetime, timedelta
from collections import defaultdict

from ..interfaces import (
    AsyncCacheInterface,
    CacheMetricsInterface,
    CacheStats,
    CacheMetrics,
    CacheConfig,
    CacheLevel
)
from ..terminusdb_cache import TerminusDBCacheManager

logger = logging.getLogger(__name__)


class TerminusDBCacheAdapter(AsyncCacheInterface[str, Any], CacheMetricsInterface):
    """
    Adapter that wraps existing TerminusDBCacheManager to implement unified interface
    """
    
    def __init__(self, config: Optional[CacheConfig] = None, db_client=None):
        self.config = config or CacheConfig()
        self.cache_name = "terminus_cache"
        self.cache_level = CacheLevel.L3_PERSISTENT
        
        # Use existing TerminusDB cache implementation
        self._impl = TerminusDBCacheManager(
            db_client=db_client,
            cache_db=self.config.terminus_db_name or "_cache"
        )
        
        # Override TTL from config
        self._impl.default_ttl = int(self.config.default_ttl.total_seconds())
        
        # Local metrics tracking
        self._metrics = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "operations": defaultdict(list)
        }
    
    async def aget(self, key: str) -> Optional[Any]:
        """Get from TerminusDB cache"""
        import time
        start = time.time()
        
        try:
            result = await self._impl.get(key)
            if result is not None:
                self._metrics["hits"] += 1
            else:
                self._metrics["misses"] += 1
            return result
        finally:
            self._record_duration("get", time.time() - start)
    
    async def aput(self, key: str, value: Any, ttl: Optional[timedelta] = None) -> None:
        """Put to TerminusDB cache"""
        import time
        start = time.time()
        
        try:
            ttl_seconds = int(ttl.total_seconds()) if ttl else None
            await self._impl.set(key, value, ttl=ttl_seconds)
        finally:
            self._record_duration("put", time.time() - start)
    
    async def adelete(self, key: str) -> bool:
        """Delete from TerminusDB cache"""
        import time
        start = time.time()
        
        try:
            result = await self._impl.delete(key)
            if result:
                self._metrics["evictions"] += 1
            return result
        finally:
            self._record_duration("delete", time.time() - start)
    
    async def aexists(self, key: str) -> bool:
        """Check if key exists in cache"""
        result = await self._impl.get(key)
        return result is not None
    
    async def aclear(self) -> None:
        """Clear all cache entries"""
        await self._impl.clear()
        self._metrics["evictions"] += await self.asize()
    
    async def asize(self) -> int:
        """Get number of entries"""
        # TerminusDB doesn't provide direct size, estimate from stats
        stats = await self._impl.get_stats()
        return stats.get("total_entries", 0)
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics"""
        # Get basic counts from metrics
        return CacheStats(
            cache_name=self.cache_name,
            cache_level=self.cache_level,
            current_size=0,  # Will be updated by async call
            max_size=self.config.max_entries,
            hit_count=self._metrics["hits"],
            miss_count=self._metrics["misses"],
            eviction_count=self._metrics["evictions"],
            total_memory_bytes=0  # TerminusDB manages its own memory
        )
    
    def get_metrics(self) -> CacheMetrics:
        """Get Prometheus metrics"""
        stats = self.get_stats()
        label = f"{self.cache_name}:{self.cache_level.value}"
        
        return CacheMetrics(
            cache_hits_total={label: stats.hit_count},
            cache_misses_total={label: stats.miss_count},
            cache_evictions_total={label: stats.eviction_count},
            cache_size_bytes={label: 0},  # Not applicable for TerminusDB
            cache_entries={label: stats.current_size},
            cache_operation_duration_seconds=dict(self._metrics["operations"])
        )
    
    def reset_metrics(self) -> None:
        """Reset metrics"""
        self._metrics = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "operations": defaultdict(list)
        }
    
    def _record_duration(self, operation: str, duration: float):
        """Record operation duration"""
        if self.config.enable_metrics:
            self._metrics["operations"][operation].append(duration)
            # Keep only last 1000 measurements
            if len(self._metrics["operations"][operation]) > 1000:
                self._metrics["operations"][operation] = \
                    self._metrics["operations"][operation][-1000:]