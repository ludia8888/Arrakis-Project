"""
Canonical cache interface contracts - All cache implementations MUST implement these
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, TypeVar, Generic, Dict
from datetime import timedelta

from .models import CacheStats, CacheMetrics

# Type definitions
CacheKey = TypeVar('CacheKey', str, bytes)
CacheValue = TypeVar('CacheValue')


class CacheInterface(ABC, Generic[CacheKey, CacheValue]):
    """
    Synchronous cache interface - canonical contract for all cache implementations
    """
    
    @abstractmethod
    def get(self, key: CacheKey) -> Optional[CacheValue]:
        """Get value from cache"""
        pass
    
    @abstractmethod
    def put(self, key: CacheKey, value: CacheValue, ttl: Optional[timedelta] = None) -> None:
        """Put value in cache with optional TTL"""
        pass
    
    @abstractmethod
    def delete(self, key: CacheKey) -> bool:
        """Delete value from cache, returns True if key existed"""
        pass
    
    @abstractmethod
    def exists(self, key: CacheKey) -> bool:
        """Check if key exists in cache"""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all entries from cache"""
        pass
    
    @abstractmethod
    def size(self) -> int:
        """Get number of entries in cache"""
        pass


class AsyncCacheInterface(ABC, Generic[CacheKey, CacheValue]):
    """
    Asynchronous cache interface - for async/await contexts
    """
    
    @abstractmethod
    async def aget(self, key: CacheKey) -> Optional[CacheValue]:
        """Async get value from cache"""
        pass
    
    @abstractmethod
    async def aput(self, key: CacheKey, value: CacheValue, ttl: Optional[timedelta] = None) -> None:
        """Async put value in cache with optional TTL"""
        pass
    
    @abstractmethod
    async def adelete(self, key: CacheKey) -> bool:
        """Async delete value from cache"""
        pass
    
    @abstractmethod
    async def aexists(self, key: CacheKey) -> bool:
        """Async check if key exists"""
        pass
    
    @abstractmethod
    async def aclear(self) -> None:
        """Async clear all entries"""
        pass
    
    @abstractmethod
    async def asize(self) -> int:
        """Async get cache size"""
        pass


class CacheMetricsInterface(ABC):
    """
    Unified metrics interface for all cache implementations
    """
    
    @abstractmethod
    def get_stats(self) -> CacheStats:
        """Get current cache statistics"""
        pass
    
    @abstractmethod
    def get_metrics(self) -> CacheMetrics:
        """Get Prometheus-compatible metrics"""
        pass
    
    @abstractmethod
    def reset_metrics(self) -> None:
        """Reset cache metrics (for testing)"""
        pass