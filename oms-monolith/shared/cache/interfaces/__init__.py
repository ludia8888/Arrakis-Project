"""
Unified Cache Interfaces - Single source of truth for all cache implementations
"""

from .contracts import (
    CacheInterface,
    AsyncCacheInterface,
    CacheMetricsInterface,
    CacheKey,
    CacheValue
)

from .models import (
    CacheLevel,
    CacheStats,
    CacheConfig,
    CacheEntry,
    CacheMetrics
)

__all__ = [
    # Contracts
    'CacheInterface',
    'AsyncCacheInterface',
    'CacheMetricsInterface',
    'CacheKey',
    'CacheValue',
    # Models
    'CacheLevel',
    'CacheStats',
    'CacheConfig',
    'CacheEntry',
    'CacheMetrics'
]