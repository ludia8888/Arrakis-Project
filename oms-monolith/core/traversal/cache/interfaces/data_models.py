"""
Cache data models
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    key: str
    value: Any
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    access_count: int = 0
    ttl_seconds: Optional[int] = None
    size_bytes: int = 0
    
    @property
    def is_expired(self) -> bool:
        """Check if entry is expired"""
        if self.ttl_seconds is None:
            return False
        return (datetime.utcnow() - self.created_at).total_seconds() > self.ttl_seconds
    
    @property
    def age_seconds(self) -> float:
        """Get entry age in seconds"""
        return (datetime.utcnow() - self.created_at).total_seconds()
    
    def touch(self):
        """Update access metadata"""
        self.last_accessed = datetime.utcnow()
        self.access_count += 1


@dataclass
class CacheStats:
    """Cache statistics data model"""
    cache_type: str
    max_size: int
    current_size: int
    total_memory_bytes: int
    hit_rate: float
    hits: int
    misses: int
    evictions: int
    oldest_entry_age: float
    avg_entry_size: float
    additional_stats: Dict[str, Any] = field(default_factory=dict)