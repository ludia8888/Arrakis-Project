"""
Metrics Collection System
Simple implementation for tracking application metrics
"""
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import threading
import statistics


class MetricType(Enum):
    """Types of metrics"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class Metric:
    """Individual metric data"""
    name: str
    value: float
    type: MetricType
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MetricsCollector:
    """Collects and manages application metrics"""
    
    def __init__(self):
        self._metrics: Dict[str, List[Metric]] = {}
        self._lock = threading.Lock()
        self._start_time = time.time()
    
    def increment(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        """Increment a counter metric"""
        with self._lock:
            metric = Metric(
                name=name,
                value=value,
                type=MetricType.COUNTER,
                labels=labels or {}
            )
            if name not in self._metrics:
                self._metrics[name] = []
            self._metrics[name].append(metric)
    
    def gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Set a gauge metric"""
        with self._lock:
            metric = Metric(
                name=name,
                value=value,
                type=MetricType.GAUGE,
                labels=labels or {}
            )
            # Gauges replace previous values
            self._metrics[name] = [metric]
    
    def histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Record a histogram metric"""
        with self._lock:
            metric = Metric(
                name=name,
                value=value,
                type=MetricType.HISTOGRAM,
                labels=labels or {}
            )
            if name not in self._metrics:
                self._metrics[name] = []
            self._metrics[name].append(metric)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all collected metrics"""
        with self._lock:
            result = {}
            
            for name, metrics in self._metrics.items():
                if not metrics:
                    continue
                
                metric_type = metrics[0].type
                
                if metric_type == MetricType.COUNTER:
                    # Sum all counter values
                    result[name] = sum(m.value for m in metrics)
                
                elif metric_type == MetricType.GAUGE:
                    # Latest gauge value
                    result[name] = metrics[-1].value if metrics else 0
                
                elif metric_type == MetricType.HISTOGRAM:
                    # Calculate statistics for histograms
                    values = [m.value for m in metrics]
                    if values:
                        result[f"{name}_count"] = len(values)
                        result[f"{name}_sum"] = sum(values)
                        result[f"{name}_avg"] = statistics.mean(values)
                        result[f"{name}_min"] = min(values)
                        result[f"{name}_max"] = max(values)
                        
                        if len(values) >= 2:
                            result[f"{name}_median"] = statistics.median(values)
                            if len(values) >= 20:
                                quantiles = statistics.quantiles(values, n=20)
                                result[f"{name}_p95"] = quantiles[18]  # 95th percentile
                                if len(values) >= 100:
                                    quantiles = statistics.quantiles(values, n=100)
                                    result[f"{name}_p99"] = quantiles[98]  # 99th percentile
            
            # Add system metrics
            result["uptime_seconds"] = time.time() - self._start_time
            result["metrics_count"] = len(self._metrics)
            
            return result
    
    def clear(self):
        """Clear all metrics"""
        with self._lock:
            self._metrics.clear()
    
    def get_metric_by_name(self, name: str) -> List[Metric]:
        """Get specific metric by name"""
        with self._lock:
            return self._metrics.get(name, []).copy()


# Global metrics collector instance
metrics_collector = MetricsCollector()