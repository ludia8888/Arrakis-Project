"""
Unified cache metrics exporter for Prometheus
"""

from typing import Dict, Any
from prometheus_client import Counter, Histogram, Gauge

from .services.cache_registry import CacheRegistry


# Define Prometheus metrics
cache_hits_total = Counter(
    'cache_hits_total',
    'Total number of cache hits',
    ['cache_name', 'cache_level']
)

cache_misses_total = Counter(
    'cache_misses_total', 
    'Total number of cache misses',
    ['cache_name', 'cache_level']
)

cache_evictions_total = Counter(
    'cache_evictions_total',
    'Total number of cache evictions',
    ['cache_name', 'cache_level']
)

cache_size_bytes = Gauge(
    'cache_size_bytes',
    'Current cache size in bytes',
    ['cache_name', 'cache_level']
)

cache_entries = Gauge(
    'cache_entries',
    'Current number of cache entries',
    ['cache_name', 'cache_level']
)

cache_operation_duration_seconds = Histogram(
    'cache_operation_duration_seconds',
    'Cache operation duration in seconds',
    ['cache_name', 'operation'],
    buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
)


def export_cache_metrics():
    """
    Export all cache metrics to Prometheus.
    Should be called periodically (e.g., every 30 seconds).
    """
    all_stats = CacheRegistry.get_stats()
    
    for cache_key, stats in all_stats.items():
        if isinstance(stats, dict) and 'error' not in stats:
            cache_name = stats.get('cache_name', cache_key.split(':')[0])
            cache_level = stats.get('cache_level', 'unknown')
            
            # Update counters (use increment from last known value)
            if hasattr(export_cache_metrics, '_last_stats'):
                last = export_cache_metrics._last_stats.get(cache_key, {})
                
                hits_delta = stats.get('hit_count', 0) - last.get('hit_count', 0)
                if hits_delta > 0:
                    cache_hits_total.labels(
                        cache_name=cache_name,
                        cache_level=cache_level
                    ).inc(hits_delta)
                
                misses_delta = stats.get('miss_count', 0) - last.get('miss_count', 0)
                if misses_delta > 0:
                    cache_misses_total.labels(
                        cache_name=cache_name,
                        cache_level=cache_level
                    ).inc(misses_delta)
                
                evictions_delta = stats.get('eviction_count', 0) - last.get('eviction_count', 0)
                if evictions_delta > 0:
                    cache_evictions_total.labels(
                        cache_name=cache_name,
                        cache_level=cache_level
                    ).inc(evictions_delta)
            
            # Update gauges
            cache_size_bytes.labels(
                cache_name=cache_name,
                cache_level=cache_level
            ).set(stats.get('total_memory_bytes', 0))
            
            cache_entries.labels(
                cache_name=cache_name,
                cache_level=cache_level
            ).set(stats.get('current_size', 0))
    
    # Store current stats for next delta calculation
    export_cache_metrics._last_stats = all_stats


# Initialize last stats
export_cache_metrics._last_stats = {}


def get_cache_summary() -> Dict[str, Any]:
    """
    Get human-readable cache summary for monitoring dashboards
    """
    all_stats = CacheRegistry.get_stats()
    
    summary = {
        "total_caches": len(all_stats),
        "total_entries": 0,
        "total_memory_bytes": 0,
        "overall_hit_rate": 0.0,
        "caches": {}
    }
    
    total_hits = 0
    total_requests = 0
    
    for cache_key, stats in all_stats.items():
        if isinstance(stats, dict) and 'error' not in stats:
            summary["total_entries"] += stats.get("current_size", 0)
            summary["total_memory_bytes"] += stats.get("total_memory_bytes", 0)
            
            hits = stats.get("hit_count", 0)
            misses = stats.get("miss_count", 0)
            requests = hits + misses
            
            total_hits += hits
            total_requests += requests
            
            hit_rate = hits / requests if requests > 0 else 0.0
            
            summary["caches"][cache_key] = {
                "size": stats.get("current_size", 0),
                "memory_bytes": stats.get("total_memory_bytes", 0),
                "hit_rate": hit_rate,
                "level": stats.get("cache_level", "unknown")
            }
    
    summary["overall_hit_rate"] = total_hits / total_requests if total_requests > 0 else 0.0
    
    return summary