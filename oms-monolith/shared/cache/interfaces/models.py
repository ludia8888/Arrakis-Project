"""
Unified cache data models
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum


class CacheLevel(str, Enum):
    """Standard cache levels across all implementations"""
    L1_MEMORY = "l1_memory"      # In-process memory
    L2_REDIS = "l2_redis"         # Redis/shared memory
    L3_PERSISTENT = "l3_persistent"  # TerminusDB/disk


@dataclass
class CacheEntry:
    """Standard cache entry model"""
    key: str
    value: Any
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    access_count: int = 0
    ttl: Optional[timedelta] = None
    size_bytes: int = 0
    
    @property
    def is_expired(self) -> bool:
        """Check if entry has expired"""
        if self.ttl is None:
            return False
        return datetime.utcnow() > self.created_at + self.ttl
    
    @property
    def age(self) -> timedelta:
        """Get entry age"""
        return datetime.utcnow() - self.created_at


@dataclass
class CacheStats:
    """Standard cache statistics"""
    cache_name: str
    cache_level: CacheLevel
    current_size: int
    max_size: int
    hit_count: int
    miss_count: int
    eviction_count: int
    total_memory_bytes: int
    
    @property
    def hit_rate(self) -> float:
        """Calculate hit rate"""
        total = self.hit_count + self.miss_count
        return self.hit_count / total if total > 0 else 0.0


@dataclass
class CacheMetrics:
    """Prometheus-compatible cache metrics"""
    cache_hits_total: Dict[str, int] = field(default_factory=dict)  # labels: cache, level
    cache_misses_total: Dict[str, int] = field(default_factory=dict)
    cache_evictions_total: Dict[str, int] = field(default_factory=dict)
    cache_size_bytes: Dict[str, int] = field(default_factory=dict)
    cache_entries: Dict[str, int] = field(default_factory=dict)
    cache_operation_duration_seconds: Dict[str, List[float]] = field(default_factory=dict)


@dataclass
class CacheConfig:
    """Unified cache configuration"""
    # Size limits
    max_entries: int = 10000
    max_memory_bytes: int = 100 * 1024 * 1024  # 100MB
    
    # TTL settings
    default_ttl: timedelta = timedelta(hours=1)
    max_ttl: timedelta = timedelta(days=7)
    
    # Features
    enable_metrics: bool = True
    enable_compression: bool = False
    enable_encryption: bool = False
    
    # Backend specific
    redis_url: Optional[str] = None
    terminus_db_name: Optional[str] = "_cache"
    
    # Performance
    batch_size: int = 100
    async_workers: int = 4