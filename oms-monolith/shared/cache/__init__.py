"""
Unified Cache Module - Single source of truth for all caching needs

This module consolidates:
- shared/cache/smart_cache.py → UnifiedLRUCache
- core/traversal/cache → UnifiedLRUCache with multi-level support
- core/validation/enterprise/implementations/validation_cache.py → UnifiedLRUCache

All caches now implement the same interface and report to unified metrics.
"""

from .interfaces import (
    CacheInterface,
    AsyncCacheInterface,
    CacheMetricsInterface,
    CacheStats,
    CacheMetrics,
    CacheConfig,
    CacheLevel,
    CacheEntry
)

from .services.cache_registry import (
    CacheRegistry,
    get_traversal_cache,
    get_validation_cache,
    get_event_cache
)

# Import implementations
from .implementations.unified_lru_cache import (
    UnifiedLRUCache,
    UnifiedAsyncLRUCache
)

# Keep backward compatibility
SmartCacheManager = UnifiedLRUCache  # Deprecated alias

__all__ = [
    # Interfaces
    'CacheInterface',
    'AsyncCacheInterface',
    'CacheMetricsInterface',
    # Models
    'CacheStats',
    'CacheMetrics',
    'CacheConfig',
    'CacheLevel',
    'CacheEntry',
    # Registry
    'CacheRegistry',
    'get_traversal_cache',
    'get_validation_cache',
    'get_event_cache',
    # Implementations
    'UnifiedLRUCache',
    'UnifiedAsyncLRUCache',
    # Backward compatibility
    'SmartCacheManager'
]


def initialize_caches():
    """
    Initialize all cache types in the registry.
    Called during application startup.
    """
    from datetime import timedelta
    from .implementations.terminus_cache_adapter import TerminusDBCacheAdapter
    
    # Register L1 Memory caches
    CacheRegistry.register(
        "traversal",
        UnifiedAsyncLRUCache,
        CacheConfig(
            max_entries=10000,
            default_ttl=timedelta(hours=1),
            enable_metrics=True
        ),
        level=CacheLevel.L1_MEMORY
    )
    
    CacheRegistry.register(
        "validation", 
        UnifiedLRUCache,
        CacheConfig(
            max_entries=5000,
            default_ttl=timedelta(minutes=30),
            enable_metrics=True
        ),
        level=CacheLevel.L1_MEMORY
    )
    
    CacheRegistry.register(
        "event",
        UnifiedAsyncLRUCache,
        CacheConfig(
            max_entries=20000,
            default_ttl=timedelta(minutes=15),
            enable_metrics=True
        ),
        level=CacheLevel.L1_MEMORY
    )
    
    # L3 Persistent cache (TerminusDB) can be registered when DB client is available
    # Example:
    # CacheRegistry.register(
    #     "persistent",
    #     TerminusDBCacheAdapter,
    #     CacheConfig(terminus_db_name="_cache"),
    #     level=CacheLevel.L3_PERSISTENT
    # )


# Auto-initialize on import
initialize_caches()