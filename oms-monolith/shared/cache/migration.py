"""
Cache migration helpers - Smooth transition from old implementations
"""

import warnings
from typing import Any, Optional

from .interfaces import CacheInterface, AsyncCacheInterface
from .services.cache_registry import CacheRegistry


def migrate_smart_cache_to_unified(old_cache_instance: Any) -> CacheInterface:
    """
    Migrate from SmartCacheManager to UnifiedLRUCache
    
    Args:
        old_cache_instance: Instance of SmartCacheManager
        
    Returns:
        UnifiedLRUCache instance with same data
    """
    warnings.warn(
        "SmartCacheManager is deprecated. Use shared.cache.UnifiedLRUCache instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    # Get new cache instance
    new_cache = CacheRegistry.get("validation", async_mode=False)
    
    # Migrate data if possible
    if hasattr(old_cache_instance, '_cache') and hasattr(new_cache, '_impl'):
        # Copy internal cache data
        if hasattr(new_cache._impl, '_cache'):
            new_cache._impl._cache = old_cache_instance._cache.copy()
    
    return new_cache


def migrate_traversal_cache_to_unified(old_cache_manager: Any) -> AsyncCacheInterface:
    """
    Migrate from TraversalCacheManager to unified cache
    
    Args:
        old_cache_manager: Instance of TraversalCacheManager
        
    Returns:
        Unified async cache instance
    """
    warnings.warn(
        "TraversalCacheManager should use shared.cache.get_traversal_cache() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    return CacheRegistry.get("traversal", async_mode=True)


def migrate_validation_cache_to_unified(old_cache: Any) -> CacheInterface:
    """
    Migrate from ValidationCache to unified cache
    
    Args:
        old_cache: Instance of ValidationCache
        
    Returns:
        Unified cache instance
    """
    warnings.warn(
        "ValidationCache should use shared.cache.get_validation_cache() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    return CacheRegistry.get("validation", async_mode=False)


# Monkey-patch imports for smooth migration
def patch_legacy_imports():
    """
    Patch legacy imports to use unified cache.
    Call this during application startup for zero-downtime migration.
    """
    import sys
    
    # Patch SmartCacheManager
    if 'shared.cache.smart_cache' in sys.modules:
        sys.modules['shared.cache.smart_cache'].SmartCacheManager = \
            lambda: migrate_smart_cache_to_unified(None)
    
    # Patch traversal cache
    if 'core.traversal.cache.services' in sys.modules:
        module = sys.modules['core.traversal.cache.services']
        original_get = getattr(module, 'get_cache_manager', None)
        if original_get:
            module.get_cache_manager = lambda config=None: \
                CacheRegistry.get("traversal", async_mode=False)
        
        original_get_async = getattr(module, 'get_async_cache_manager', None)
        if original_get_async:
            module.get_async_cache_manager = lambda config=None: \
                CacheRegistry.get("traversal", async_mode=True)