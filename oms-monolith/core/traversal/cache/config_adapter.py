"""
Configuration adapter for cache module
"""

from typing import Optional
from core.traversal.config import get_config
from .interfaces.models import CacheConfig


def get_cache_config() -> CacheConfig:
    """Get cache configuration from traversal config"""
    traversal_config = get_config()
    
    # Map traversal config to cache config
    return CacheConfig(
        query_cache_max_size=traversal_config.cache.query_cache_max_size,
        result_cache_max_size=traversal_config.cache.result_cache_max_size,
        plan_cache_max_size=traversal_config.cache.plan_cache_max_size,
        query_cache_ttl=traversal_config.cache.query_cache_ttl,
        result_cache_ttl=traversal_config.cache.result_cache_ttl,
        plan_cache_ttl=traversal_config.cache.plan_cache_ttl,
        enable_result_cache=traversal_config.cache.enable_result_cache,
        enable_plan_cache=traversal_config.cache.enable_plan_cache,
        enable_cache_warming=traversal_config.cache.enable_cache_warming,
        eviction_policy=traversal_config.cache.eviction_policy,
        cache_warming_queries=traversal_config.cache.cache_warming_queries
    )