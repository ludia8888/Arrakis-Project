"""
Cache configuration models
"""

from typing import List
from dataclasses import dataclass, field
from .enums import EvictionPolicy


@dataclass
class CacheConfig:
    """Cache configuration model"""
    # Size limits
    query_cache_max_size: int = 1000
    result_cache_max_size: int = 5000
    plan_cache_max_size: int = 100
    
    # TTL settings (seconds)
    query_cache_ttl: int = 3600  # 1 hour
    result_cache_ttl: int = 1800  # 30 minutes
    plan_cache_ttl: int = 86400  # 24 hours
    
    # Features
    enable_result_cache: bool = True
    enable_plan_cache: bool = True
    enable_cache_warming: bool = True
    
    # Policies
    eviction_policy: EvictionPolicy = EvictionPolicy.LRU
    
    # Warming configuration
    cache_warming_queries: List[str] = field(default_factory=list)
    cache_warming_interval_seconds: int = 30