"""
Enterprise-grade Caching System for Graph Traversal

This module provides backward compatibility by re-exporting the refactored
3-layer architecture components.
"""

# Re-export interface layer
from core.traversal.cache.interfaces import (
    CacheLevel,
    EvictionPolicy,
    CacheEntry,
    CacheInterface
)

# Re-export implementation layer
from core.traversal.cache.implementations import (
    LRUCache,
    AsyncLRUCache,
    MultiLevelCache,
    CacheWarmer,
    AsyncCacheWarmer
)

# Re-export service layer
from core.traversal.cache.services import (
    TraversalCacheManager,
    get_cache_manager,
    get_async_cache_manager,
    reset_cache_manager
)

# Maintain backward compatibility
__all__ = [
    # Enums
    'CacheLevel',
    'EvictionPolicy',
    # Models
    'CacheEntry',
    # Interfaces
    'CacheInterface',
    # Implementations
    'LRUCache',
    'AsyncLRUCache',
    'MultiLevelCache',
    'CacheWarmer',
    'AsyncCacheWarmer',
    # Services
    'TraversalCacheManager',
    'get_cache_manager',
    'get_async_cache_manager',
    'reset_cache_manager'
]