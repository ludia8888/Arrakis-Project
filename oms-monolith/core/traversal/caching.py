"""
Enterprise-grade Caching System for Graph Traversal

Multi-level caching with TTL, LRU eviction, and cache warming capabilities.
Designed for high-performance graph traversal operations.
"""

import asyncio
import time
import hashlib
import json
import threading
from typing import Dict, Any, Optional, List, Set, Callable, TypeVar, Generic
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import OrderedDict
from abc import ABC, abstractmethod
from enum import Enum

from core.traversal.config import CacheConfig, get_config
from core.traversal.models import TraversalResult, TraversalQuery


T = TypeVar('T')


class CacheLevel(str, Enum):
    """Cache level enumeration"""
    L1_MEMORY = "l1_memory"
    L2_PERSISTENT = "l2_persistent"  
    L3_DISTRIBUTED = "l3_distributed"


class EvictionPolicy(str, Enum):
    """Cache eviction policy"""
    LRU = "lru"
    LFU = "lfu"
    FIFO = "fifo"
    TTL_BASED = "ttl_based"


@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    key: str
    value: Any
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    access_count: int = 0
    ttl_seconds: Optional[int] = None
    size_bytes: int = 0
    
    @property
    def is_expired(self) -> bool:
        """Check if entry is expired"""
        if self.ttl_seconds is None:
            return False
        return (datetime.utcnow() - self.created_at).total_seconds() > self.ttl_seconds
    
    @property
    def age_seconds(self) -> float:
        """Get entry age in seconds"""
        return (datetime.utcnow() - self.created_at).total_seconds()
    
    def touch(self):
        """Update access metadata"""
        self.last_accessed = datetime.utcnow()
        self.access_count += 1


class CacheInterface(ABC, Generic[T]):
    """Abstract cache interface"""
    
    @abstractmethod
    def get(self, key: str) -> Optional[T]:
        """Get value from cache"""
        pass
    
    @abstractmethod
    def put(self, key: str, value: T, ttl_seconds: Optional[int] = None) -> None:
        """Put value in cache"""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all entries"""
        pass
    
    @abstractmethod
    def size(self) -> int:
        """Get cache size"""
        pass
    
    @abstractmethod
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        pass


class LRUCache(CacheInterface[T]):
    """
    Thread-safe LRU cache implementation with TTL support.
    
    Features:
    - Least Recently Used eviction
    - TTL-based expiration
    - Thread-safe operations
    - Memory usage tracking
    - Access statistics
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: Optional[int] = None):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        
    def get(self, key: str) -> Optional[T]:
        """Get value from cache with LRU update"""
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None
            
            entry = self._cache[key]
            
            # Check expiration
            if entry.is_expired:
                del self._cache[key]
                self._misses += 1
                return None
            
            # Update access metadata and move to end (most recent)
            entry.touch()
            self._cache.move_to_end(key)
            self._hits += 1
            
            return entry.value
    
    def put(self, key: str, value: T, ttl_seconds: Optional[int] = None) -> None:
        """Put value in cache with eviction if necessary"""
        with self._lock:
            # Calculate entry size
            size_bytes = len(str(value)) if value is not None else 0
            ttl = ttl_seconds or self.default_ttl
            
            # Create entry
            entry = CacheEntry(
                key=key,
                value=value,
                ttl_seconds=ttl,
                size_bytes=size_bytes
            )
            
            # Remove if already exists
            if key in self._cache:
                del self._cache[key]
            
            # Add new entry
            self._cache[key] = entry
            
            # Evict if necessary
            self._evict_if_necessary()
    
    def delete(self, key: str) -> bool:
        """Delete entry from cache"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear(self) -> None:
        """Clear all entries"""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0
    
    def size(self) -> int:
        """Get current cache size"""
        with self._lock:
            return len(self._cache)
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0
            
            total_size = sum(entry.size_bytes for entry in self._cache.values())
            
            return {
                "cache_type": "LRU",
                "max_size": self.max_size,
                "current_size": len(self._cache),
                "total_memory_bytes": total_size,
                "hit_rate": hit_rate,
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "oldest_entry_age": self._get_oldest_entry_age(),
                "avg_entry_size": total_size / len(self._cache) if self._cache else 0
            }
    
    def _evict_if_necessary(self) -> None:
        """Evict entries if cache is over capacity"""
        # Remove expired entries first
        expired_keys = [
            key for key, entry in self._cache.items() 
            if entry.is_expired
        ]
        for key in expired_keys:
            del self._cache[key]
        
        # Evict LRU entries if still over capacity
        while len(self._cache) > self.max_size:
            # Remove least recently used (first in OrderedDict)
            self._cache.popitem(last=False)
            self._evictions += 1
    
    def _get_oldest_entry_age(self) -> float:
        """Get age of oldest entry in seconds"""
        if not self._cache:
            return 0.0
        
        oldest_entry = next(iter(self._cache.values()))
        return oldest_entry.age_seconds


class MultiLevelCache:
    """
    Multi-level cache with L1 (memory) and L2 (persistent) levels.
    
    Cache hierarchy:
    - L1: Fast in-memory LRU cache
    - L2: Persistent cache (could be Redis, file-based, etc.)
    - L3: Distributed cache (future enhancement)
    """
    
    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or get_config().cache
        
        # Initialize L1 cache (memory)
        self.l1_cache = LRUCache(
            max_size=self.config.query_cache_max_size,
            default_ttl=self.config.query_cache_ttl
        )
        
        # Initialize L2 cache (simplified - in real implementation would be Redis/DB)
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
            "l1_cache": l1_stats,
            "l2_cache": l2_stats
        }


class CacheWarmer:
    """
    Cache warming service for preloading frequently used data.
    
    Strategies:
    - Predictive warming based on access patterns
    - Scheduled warming of common queries
    - Priority-based warming
    """
    
    def __init__(self, cache: MultiLevelCache, config: Optional[CacheConfig] = None):
        self.cache = cache
        self.config = config or get_config().cache
        self._warming_queries: List[str] = self.config.cache_warming_queries
        self._warming_active = False
        self._warming_thread: Optional[threading.Thread] = None
        
    def start_warming(self, query_executor: Callable[[str], Any]) -> None:
        """Start cache warming process"""
        if self._warming_active or not self.config.enable_cache_warming:
            return
            
        self._warming_active = True
        self._warming_thread = threading.Thread(
            target=self._warming_worker,
            args=(query_executor,),
            daemon=True
        )
        self._warming_thread.start()
    
    def stop_warming(self) -> None:
        """Stop cache warming process"""
        self._warming_active = False
        if self._warming_thread:
            self._warming_thread.join(timeout=5.0)
    
    def add_warming_query(self, query: str) -> None:
        """Add query to warming list"""
        if query not in self._warming_queries:
            self._warming_queries.append(query)
    
    def _warming_worker(self, query_executor: Callable[[str], Any]) -> None:
        """Background worker for cache warming"""
        while self._warming_active:
            try:
                for query in self._warming_queries:
                    if not self._warming_active:
                        break
                        
                    # Check if query result is already cached
                    cache_key = self._generate_cache_key(query)
                    if self.cache.get(cache_key) is None:
                        # Execute query and cache result
                        try:
                            result = query_executor(query)
                            if result is not None:
                                self.cache.put(cache_key, result, "query_results")
                        except (ConnectionError, TimeoutError) as e:
                            # Log network error but continue warming
                            continue
                        except RuntimeError as e:
                            # Log error but continue warming
                            continue
                
                # Sleep between warming cycles
                time.sleep(30)  # 30 seconds between cycles
                
            except RuntimeError as e:
                # Log error and continue
                time.sleep(60)  # Wait longer on error
    
    def _generate_cache_key(self, query: str) -> str:
        """Generate cache key for query"""
        return f"warming:{hashlib.md5(query.encode()).hexdigest()}"


class TraversalCacheManager:
    """
    Specialized cache manager for graph traversal operations.
    
    Provides caching for:
    - Query results
    - Query execution plans
    - Graph metrics
    - Dependency paths
    """
    
    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or get_config().cache
        self.cache = MultiLevelCache(self.config)
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
            "eviction_policy": self.config.eviction_policy,
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


# Global cache manager instance
_cache_manager: Optional[TraversalCacheManager] = None

def get_cache_manager(config: Optional[CacheConfig] = None) -> TraversalCacheManager:
    """Get global cache manager instance"""
    global _cache_manager
    
    if _cache_manager is None:
        _cache_manager = TraversalCacheManager(config)
    
    return _cache_manager

def reset_cache_manager():
    """Reset global cache manager (useful for testing)"""
    global _cache_manager
    if _cache_manager:
        _cache_manager.stop_cache_warming()
    _cache_manager = None