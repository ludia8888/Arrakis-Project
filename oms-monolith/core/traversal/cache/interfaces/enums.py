"""
Cache-related enumerations
"""

from enum import Enum


class CacheLevel(str, Enum):
    """Cache level enumeration"""
    L1_MEMORY = "l1_memory"
    L2_PERSISTENT = "l2_persistent"  
    L3_DISTRIBUTED = "l3_distributed"


class EvictionPolicy(str, Enum):
    """Cache eviction policy"""
    LRU = "lru"
    LFU = "lfu"
    FIFO = "fifo"
    TTL_BASED = "ttl_based"