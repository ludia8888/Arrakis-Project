"""
Cache Registry - Central point for cache dependency injection
"""

import logging
from typing import Dict, Optional, Type, Union
from functools import lru_cache

from ..interfaces import (
    CacheInterface, 
    AsyncCacheInterface,
    CacheConfig,
    CacheLevel
)

logger = logging.getLogger(__name__)


class CacheRegistry:
    """
    Central registry for all cache implementations.
    Enables dependency injection and unified configuration.
    """
    
    _caches: Dict[str, Union[CacheInterface, AsyncCacheInterface]] = {}
    _cache_types: Dict[str, Type[Union[CacheInterface, AsyncCacheInterface]]] = {}
    _configs: Dict[str, CacheConfig] = {}
    
    @classmethod
    def register(
        cls, 
        name: str, 
        cache_type: Type[Union[CacheInterface, AsyncCacheInterface]],
        config: Optional[CacheConfig] = None,
        level: CacheLevel = CacheLevel.L1_MEMORY
    ) -> None:
        """
        Register a cache implementation
        
        Args:
            name: Unique cache identifier (e.g., "traversal", "validation")
            cache_type: Cache implementation class
            config: Cache configuration
            level: Cache level (L1, L2, L3)
        """
        cls._cache_types[name] = cache_type
        if config:
            cls._configs[name] = config
        
        logger.info(f"Registered cache '{name}' with type {cache_type.__name__} at level {level}")
    
    @classmethod
    def get(cls, name: str, async_mode: bool = False) -> Union[CacheInterface, AsyncCacheInterface]:
        """
        Get or create a cache instance
        
        Args:
            name: Cache identifier
            async_mode: Whether to return async interface
            
        Returns:
            Cache instance implementing the appropriate interface
        """
        cache_key = f"{name}:{'async' if async_mode else 'sync'}"
        
        if cache_key not in cls._caches:
            if name not in cls._cache_types:
                raise ValueError(f"Cache '{name}' not registered. Available: {list(cls._cache_types.keys())}")
            
            cache_type = cls._cache_types[name]
            config = cls._configs.get(name, CacheConfig())
            
            # Instantiate cache
            cache_instance = cache_type(config=config)
            
            # Validate interface implementation
            if async_mode and not isinstance(cache_instance, AsyncCacheInterface):
                raise TypeError(f"Cache '{name}' does not implement AsyncCacheInterface")
            elif not async_mode and not isinstance(cache_instance, CacheInterface):
                raise TypeError(f"Cache '{name}' does not implement CacheInterface")
            
            cls._caches[cache_key] = cache_instance
            logger.info(f"Created cache instance '{cache_key}'")
        
        return cls._caches[cache_key]
    
    @classmethod
    def clear_all(cls) -> None:
        """Clear all cache instances (useful for testing)"""
        for cache in cls._caches.values():
            try:
                cache.clear()
            except Exception as e:
                logger.error(f"Failed to clear cache: {e}")
        
        cls._caches.clear()
        logger.info("Cleared all cache instances")
    
    @classmethod
    def get_stats(cls) -> Dict[str, Dict[str, Any]]:
        """Get statistics from all registered caches"""
        stats = {}
        
        for name, cache in cls._caches.items():
            try:
                if hasattr(cache, 'get_stats'):
                    stats[name] = cache.get_stats().__dict__
            except Exception as e:
                logger.error(f"Failed to get stats for cache '{name}': {e}")
                stats[name] = {"error": str(e)}
        
        return stats


# Convenience functions for common cache types
@lru_cache(maxsize=1)
def get_traversal_cache(async_mode: bool = False) -> Union[CacheInterface, AsyncCacheInterface]:
    """Get traversal cache instance"""
    return CacheRegistry.get("traversal", async_mode=async_mode)


@lru_cache(maxsize=1)
def get_validation_cache(async_mode: bool = False) -> Union[CacheInterface, AsyncCacheInterface]:
    """Get validation cache instance"""
    return CacheRegistry.get("validation", async_mode=async_mode)


@lru_cache(maxsize=1)
def get_event_cache(async_mode: bool = False) -> Union[CacheInterface, AsyncCacheInterface]:
    """Get event cache instance"""
    return CacheRegistry.get("event", async_mode=async_mode)