"""
Cache interface contracts (abstract base classes)
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TypeVar, Generic, Callable

from .models import CacheStats

T = TypeVar('T')


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
    def stats(self) -> CacheStats:
        """Get cache statistics"""
        pass


class AsyncCacheInterface(ABC, Generic[T]):
    """Abstract async cache interface"""
    
    @abstractmethod
    async def aget(self, key: str) -> Optional[T]:
        """Async get value from cache"""
        pass
    
    @abstractmethod
    async def aput(self, key: str, value: T, ttl_seconds: Optional[int] = None) -> None:
        """Async put value in cache"""
        pass
    
    @abstractmethod
    async def adelete(self, key: str) -> bool:
        """Async delete value from cache"""
        pass
    
    @abstractmethod
    async def aclear(self) -> None:
        """Async clear all entries"""
        pass
    
    @abstractmethod
    async def asize(self) -> int:
        """Async get cache size"""
        pass
    
    @abstractmethod
    async def astats(self) -> CacheStats:
        """Async get cache statistics"""
        pass


class CacheWarmerInterface(ABC):
    """Abstract cache warmer interface"""
    
    @abstractmethod
    def start_warming(self, query_executor: Callable[[str], Any]) -> None:
        """Start cache warming process"""
        pass
    
    @abstractmethod
    def stop_warming(self) -> None:
        """Stop cache warming process"""
        pass
    
    @abstractmethod
    def add_warming_query(self, query: str) -> None:
        """Add query to warming list"""
        pass


class AsyncCacheWarmerInterface(ABC):
    """Abstract async cache warmer interface"""
    
    @abstractmethod
    async def start_warming(self, query_executor: Callable[[str], Any]) -> None:
        """Start async cache warming process"""
        pass
    
    @abstractmethod
    async def stop_warming(self) -> None:
        """Stop async cache warming process"""
        pass
    
    @abstractmethod
    def add_warming_query(self, query: str) -> None:
        """Add query to warming list"""
        pass


class CacheManagerInterface(ABC):
    """Abstract cache manager interface for traversal operations"""
    
    @abstractmethod
    def get_query_result(self, query: Any) -> Optional[Any]:
        """Get cached query result"""
        pass
    
    @abstractmethod
    def cache_query_result(self, query: Any, result: Any, ttl_seconds: Optional[int] = None) -> None:
        """Cache query result"""
        pass
    
    @abstractmethod
    def get_query_plan(self, query_fingerprint: str) -> Optional[Any]:
        """Get cached query execution plan"""
        pass
    
    @abstractmethod
    def cache_query_plan(self, query_fingerprint: str, plan: Any, ttl_seconds: Optional[int] = None) -> None:
        """Cache query execution plan"""
        pass
    
    @abstractmethod
    def invalidate_query_cache(self, pattern: Optional[str] = None) -> None:
        """Invalidate query cache"""
        pass
    
    @abstractmethod
    def get_cache_statistics(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        pass