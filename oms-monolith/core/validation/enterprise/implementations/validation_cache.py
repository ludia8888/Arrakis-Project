"""
Validation result caching implementation
"""

import hashlib
import json
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from collections import OrderedDict
import threading

from ..interfaces.contracts import ValidationCacheInterface
from ..interfaces.models import ValidationResult


class ValidationCache(ValidationCacheInterface):
    """
    Thread-safe LRU cache for validation results
    """
    
    def __init__(self, max_size: int = 10000, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, tuple[ValidationResult, datetime]] = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[ValidationResult]:
        """Get cached validation result"""
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None
            
            result, expiry_time = self._cache[key]
            
            # Check expiration
            if datetime.utcnow() > expiry_time:
                del self._cache[key]
                self._misses += 1
                return None
            
            # Move to end (most recent)
            self._cache.move_to_end(key)
            self._hits += 1
            return result
    
    def set(self, key: str, result: ValidationResult, ttl_seconds: int) -> None:
        """Cache validation result"""
        with self._lock:
            expiry_time = datetime.utcnow() + timedelta(seconds=ttl_seconds)
            
            # Remove if already exists
            if key in self._cache:
                del self._cache[key]
            
            # Add new entry
            self._cache[key] = (result, expiry_time)
            
            # Evict if necessary
            self._evict_if_necessary()
    
    def delete(self, key: str) -> bool:
        """Delete cached result"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear(self) -> None:
        """Clear all cached results"""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0
            
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
                "total_requests": total_requests
            }
    
    def _evict_if_necessary(self) -> None:
        """Evict entries if cache is over capacity"""
        # Remove expired entries first
        current_time = datetime.utcnow()
        expired_keys = []
        
        for key, (_, expiry_time) in self._cache.items():
            if current_time > expiry_time:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._cache[key]
        
        # Then evict LRU entries if still over capacity
        while len(self._cache) > self.max_size:
            # Remove oldest (first) item
            self._cache.popitem(last=False)
    
    @staticmethod
    def generate_cache_key(data: Dict[str, Any], validation_level: str, validation_scope: str) -> str:
        """Generate deterministic cache key for validation request"""
        # Create a deterministic representation
        key_data = {
            "data": data,
            "level": validation_level,
            "scope": validation_scope
        }
        
        # Sort keys for consistency
        key_json = json.dumps(key_data, sort_keys=True)
        
        # Generate hash
        return hashlib.md5(key_json.encode()).hexdigest()