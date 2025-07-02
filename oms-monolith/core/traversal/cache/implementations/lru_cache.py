"""
LRU Cache implementation with sync and async support
"""

import asyncio
import threading
import sys
from typing import Optional, TypeVar, Dict, Any
from collections import OrderedDict
from datetime import datetime

from ..interfaces.contracts import CacheInterface, AsyncCacheInterface
from ..interfaces.models import CacheEntry, CacheStats

T = TypeVar('T')


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
            size_bytes = self._calculate_size(value)
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
    
    def stats(self) -> CacheStats:
        """Get cache statistics"""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0
            
            total_size = sum(entry.size_bytes for entry in self._cache.values())
            
            return CacheStats(
                cache_type="LRU",
                max_size=self.max_size,
                current_size=len(self._cache),
                total_memory_bytes=total_size,
                hit_rate=hit_rate,
                hits=self._hits,
                misses=self._misses,
                evictions=self._evictions,
                oldest_entry_age=self._get_oldest_entry_age(),
                avg_entry_size=total_size / len(self._cache) if self._cache else 0
            )
    
    def _evict_if_necessary(self) -> None:
        """Evict entries if cache is over capacity - optimized version"""
        # Batch remove expired entries
        current_time = datetime.utcnow()
        expired_keys = []
        
        # Collect expired keys in single pass
        for key, entry in self._cache.items():
            if entry.ttl_seconds and (current_time - entry.created_at).total_seconds() > entry.ttl_seconds:
                expired_keys.append(key)
        
        # Batch delete expired entries
        for key in expired_keys:
            del self._cache[key]
        
        # Calculate how many more to evict
        over_capacity = len(self._cache) - self.max_size
        if over_capacity > 0:
            # Batch evict LRU entries
            keys_to_evict = list(self._cache.keys())[:over_capacity]
            for key in keys_to_evict:
                del self._cache[key]
                self._evictions += 1
    
    def _get_oldest_entry_age(self) -> float:
        """Get age of oldest entry in seconds"""
        if not self._cache:
            return 0.0
        
        oldest_entry = next(iter(self._cache.values()))
        return oldest_entry.age_seconds
    
    def _calculate_size(self, value: Any) -> int:
        """Calculate approximate size of value in bytes"""
        try:
            # For simple types, use sys.getsizeof
            if isinstance(value, (str, int, float, bool, type(None))):
                return sys.getsizeof(value)
            # For collections, estimate based on string representation
            elif isinstance(value, (list, dict, set, tuple)):
                return len(str(value))
            # For custom objects, fallback to string length
            else:
                return len(str(value))
        except Exception:
            # If size calculation fails, return conservative estimate
            return 1000


class AsyncLRUCache(LRUCache[T], AsyncCacheInterface[T]):
    """
    Async-safe LRU cache implementation for use in asyncio contexts.
    
    This implementation uses asyncio.Lock instead of threading.RLock
    to prevent event loop blocking in async environments.
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: Optional[int] = None, 
                 loop: Optional[asyncio.AbstractEventLoop] = None):
        # Initialize without calling super().__init__ to avoid RLock
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        
        # Use asyncio.Lock instead of threading.RLock
        self._lock = asyncio.Lock()
        self._loop = loop
        
        # Keep threading.RLock for backward compatibility with sync methods
        self._sync_lock = threading.RLock()
    
    async def aget(self, key: str) -> Optional[T]:
        """Async get value from cache with LRU update"""
        async with self._lock:
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
    
    async def aput(self, key: str, value: T, ttl_seconds: Optional[int] = None) -> None:
        """Async put value in cache with eviction if necessary"""
        async with self._lock:
            # Calculate entry size
            size_bytes = self._calculate_size(value)
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
            await self._async_evict_if_necessary()
    
    async def adelete(self, key: str) -> bool:
        """Async delete entry from cache"""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    async def aclear(self) -> None:
        """Async clear all entries"""
        async with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            self._evictions = 0
    
    async def asize(self) -> int:
        """Async get current cache size"""
        async with self._lock:
            return len(self._cache)
    
    async def astats(self) -> CacheStats:
        """Async get cache statistics"""
        async with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0
            
            total_size = sum(entry.size_bytes for entry in self._cache.values())
            
            return CacheStats(
                cache_type="AsyncLRU",
                max_size=self.max_size,
                current_size=len(self._cache),
                total_memory_bytes=total_size,
                hit_rate=hit_rate,
                hits=self._hits,
                misses=self._misses,
                evictions=self._evictions,
                oldest_entry_age=self._get_oldest_entry_age() if self._cache else 0,
                avg_entry_size=total_size / len(self._cache) if self._cache else 0
            )
    
    async def _async_evict_if_necessary(self) -> None:
        """Async evict entries if cache is over capacity"""
        # Batch remove expired entries
        current_time = datetime.utcnow()
        expired_keys = []
        
        # Collect expired keys in single pass
        for key, entry in self._cache.items():
            if entry.ttl_seconds and (current_time - entry.created_at).total_seconds() > entry.ttl_seconds:
                expired_keys.append(key)
        
        # Batch delete expired entries
        for key in expired_keys:
            del self._cache[key]
        
        # Calculate how many more to evict
        over_capacity = len(self._cache) - self.max_size
        if over_capacity > 0:
            # Batch evict LRU entries
            keys_to_evict = list(self._cache.keys())[:over_capacity]
            for key in keys_to_evict:
                del self._cache[key]
                self._evictions += 1
    
    # Override sync methods to use sync lock for backward compatibility
    def get(self, key: str) -> Optional[T]:
        """Sync get - for backward compatibility"""
        with self._sync_lock:
            return super().get(key)
    
    def put(self, key: str, value: T, ttl_seconds: Optional[int] = None) -> None:
        """Sync put - for backward compatibility"""
        with self._sync_lock:
            # Manually implement to avoid using parent's RLock
            size_bytes = self._calculate_size(value)
            ttl = ttl_seconds or self.default_ttl
            
            entry = CacheEntry(
                key=key,
                value=value,
                ttl_seconds=ttl,
                size_bytes=size_bytes
            )
            
            if key in self._cache:
                del self._cache[key]
            
            self._cache[key] = entry
            self._evict_if_necessary()
    
    def stats(self) -> CacheStats:
        """Sync stats - for backward compatibility"""
        with self._sync_lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0
            
            total_size = sum(entry.size_bytes for entry in self._cache.values())
            
            return CacheStats(
                cache_type="AsyncLRU",
                max_size=self.max_size,
                current_size=len(self._cache),
                total_memory_bytes=total_size,
                hit_rate=hit_rate,
                hits=self._hits,
                misses=self._misses,
                evictions=self._evictions,
                oldest_entry_age=self._get_oldest_entry_age() if self._cache else 0,
                avg_entry_size=total_size / len(self._cache) if self._cache else 0
            )
    
    def _evict_if_necessary(self) -> None:
        """Sync eviction for backward compatibility"""
        # Batch remove expired entries
        current_time = datetime.utcnow()
        expired_keys = []
        
        # Collect expired keys in single pass
        for key, entry in self._cache.items():
            if entry.ttl_seconds and (current_time - entry.created_at).total_seconds() > entry.ttl_seconds:
                expired_keys.append(key)
        
        # Batch delete expired entries
        for key in expired_keys:
            del self._cache[key]
        
        # Calculate how many more to evict
        over_capacity = len(self._cache) - self.max_size
        if over_capacity > 0:
            # Batch evict LRU entries
            keys_to_evict = list(self._cache.keys())[:over_capacity]
            for key in keys_to_evict:
                del self._cache[key]
                self._evictions += 1