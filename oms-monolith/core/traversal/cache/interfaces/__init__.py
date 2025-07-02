"""
Cache interfaces and data models - Interface Layer
"""

from .models import (
    CacheLevel,
    EvictionPolicy,
    CacheEntry,
    CacheStats,
    CacheConfig
)

from .contracts import (
    CacheInterface,
    CacheWarmerInterface,
    CacheManagerInterface
)

__all__ = [
    # Models
    'CacheLevel',
    'EvictionPolicy',
    'CacheEntry',
    'CacheStats',
    'CacheConfig',
    # Contracts
    'CacheInterface',
    'CacheWarmerInterface',
    'CacheManagerInterface'
]