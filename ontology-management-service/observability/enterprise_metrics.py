"""
Enterprise-Grade Comprehensive Metrics Collection
Complete Prometheus-based enterprise metrics system
"""
import asyncio
import gc
import logging
import os
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Dict, List, Optional

import psutil
from fastapi import Request, Response
from fastapi.responses import PlainTextResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    CollectorRegistry,
    Counter,
    Enum,
    Gauge,
    Histogram,
    Info,
    Summary,
    generate_latest,
    start_http_server,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Enterprise Metrics Registry
# =============================================================================


class EnterpriseMetricsRegistry:
 """Enterprise-grade metrics registry"""

 def __init__(self):
 self.registry = CollectorRegistry()
 self._initialize_all_metrics()

 def _initialize_all_metrics(self):
 """Initialize all enterprise metrics"""
 self._init_system_metrics()
 self._init_application_metrics()
 self._init_resilience_metrics()
 self._init_business_metrics()
 self._init_security_metrics()
 self._init_performance_metrics()
 self._init_garbage_collection_metrics()

 # =============================================================================
 # System & Infrastructure Metrics
 # =============================================================================

 def _init_system_metrics(self):
 """System level metrics"""

 # CPU Metrics
 self.cpu_usage_percent = Gauge(
 "system_cpu_usage_percent",
 "Current CPU usage percentage",
 ["core"],
 registry = self.registry,
 )

 self.cpu_load_average = Gauge(
 "system_cpu_load_average",
 "System load average",
 ["interval"], # 1m, 5m, 15m
 registry = self.registry,
 )

 # Memory Metrics
 self.memory_usage_bytes = Gauge(
 "system_memory_usage_bytes",
 "Current memory usage in bytes",
 ["type"], # total, available, used, free, cached, buffers
 registry = self.registry,
 )

 self.memory_usage_percent = Gauge(
 "system_memory_usage_percent",
 "Current memory usage percentage",
 registry = self.registry,
 )

 # Disk Metrics
 self.disk_usage_bytes = Gauge(
 "system_disk_usage_bytes",
 "Disk usage in bytes",
 ["device", "mountpoint", "type"], # total, used, free
 registry = self.registry,
 )

 self.disk_io_operations_total = Counter(
 "system_disk_io_operations_total",
 "Total disk I/O operations",
 ["device", "type"], # read, write
 registry = self.registry,
 )

 self.disk_io_bytes_total = Counter(
 "system_disk_io_bytes_total",
 "Total disk I/O bytes",
 ["device", "type"], # read, write
 registry = self.registry,
 )

 # Network Metrics
 self.network_io_bytes_total = Counter(
 "system_network_io_bytes_total",
 "Total network I/O bytes",
 ["interface", "direction"], # sent, received
 registry = self.registry,
 )

 self.network_io_packets_total = Counter(
 "system_network_io_packets_total",
 "Total network I/O packets",
 ["interface", "direction"], # sent, received
 registry = self.registry,
 )

 self.network_connections_active = Gauge(
 "system_network_connections_active",
 "Number of active network connections",
 ["state"], # ESTABLISHED, TIME_WAIT, etc.
 registry = self.registry,
 )

 # =============================================================================
 # Garbage Collection & Memory Management Metrics
 # =============================================================================

 def _init_garbage_collection_metrics(self):
 """Garbage collection and memory management metrics"""

 # GC Collection Metrics
 self.gc_collections_total = Counter(
 "python_gc_collections_total",
 "Total number of garbage collections",
 ["generation"], # 0, 1, 2
 registry = self.registry,
 )

 self.gc_collection_duration_seconds = Histogram(
 "python_gc_collection_duration_seconds",
 "Time spent in garbage collection",
 ["generation"],
 buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
 registry = self.registry,
 )

 self.gc_objects_collected_total = Counter(
 "python_gc_objects_collected_total",
 "Total number of objects collected",
 ["generation"],
 registry = self.registry,
 )

 self.gc_objects_uncollectable_total = Counter(
 "python_gc_objects_uncollectable_total",
 "Total number of uncollectable objects",
 ["generation"],
 registry = self.registry,
 )

 # Memory Object Tracking
 self.memory_objects_count = Gauge(
 "python_memory_objects_count",
 "Number of objects in memory",
 ["type"], # dict, list, tuple, set, etc.
 registry = self.registry,
 )

 self.memory_heap_size_bytes = Gauge(
 "python_memory_heap_size_bytes",
 "Python heap size in bytes",
 registry = self.registry,
 )

 self.memory_rss_bytes = Gauge(
 "process_memory_rss_bytes",
 "Resident set size in bytes",
 registry = self.registry,
 )

 self.memory_vms_bytes = Gauge(
 "process_memory_vms_bytes",
 "Virtual memory size in bytes",
 registry = self.registry,
 )

 # Python-specific Memory Metrics
 self.python_memory_pools = Gauge(
 "python_memory_pools_count",
 "Number of memory pools",
 ["status"], # used, available
 registry = self.registry,
 )

 self.python_memory_arena_bytes = Gauge(
 "python_memory_arena_bytes",
 "Memory arena size in bytes",
 ["type"], # total, available
 registry = self.registry,
 )

 # =============================================================================
 # Application Performance Metrics
 # =============================================================================

 def _init_application_metrics(self):
 """Application performance metrics"""

 # HTTP Request Metrics
 self.http_requests_total = Counter(
 "http_requests_total",
 "Total HTTP requests",
 ["method", "endpoint", "status_code", "service"],
 registry = self.registry,
 )

 self.http_request_duration_seconds = Histogram(
 "http_request_duration_seconds",
 "HTTP request duration in seconds",
 ["method", "endpoint", "service"],
 buckets=(
 0.005,
 0.01,
 0.025,
 0.05,
 0.1,
 0.25,
 0.5,
 1.0,
 2.5,
 5.0,
 10.0,
 30.0,
 ),
 registry = self.registry,
 )

 self.http_requests_in_progress = Gauge(
 "http_requests_in_progress",
 "HTTP requests currently being processed",
 ["method", "endpoint", "service"],
 registry = self.registry,
 )

 self.http_request_size_bytes = Histogram(
 "http_request_size_bytes",
 "HTTP request size in bytes",
 ["method", "endpoint"],
 buckets=(100, 1000, 10000, 100000, 1000000, 10000000, 100000000),
 registry = self.registry,
 )

 self.http_response_size_bytes = Histogram(
 "http_response_size_bytes",
 "HTTP response size in bytes",
 ["method", "endpoint", "status_code"],
 buckets=(100, 1000, 10000, 100000, 1000000, 10000000, 100000000),
 registry = self.registry,
 )

 # Application Process Metrics
 self.process_cpu_seconds_total = Counter(
 "process_cpu_seconds_total",
 "Total CPU time spent by process",
 registry = self.registry,
 )

 self.process_open_fds = Gauge(
 "process_open_fds",
 "Number of open file descriptors",
 registry = self.registry,
 )

 self.process_max_fds = Gauge(
 "process_max_fds",
 "Maximum number of open file descriptors",
 registry = self.registry,
 )

 self.process_threads = Gauge(
 "process_threads", "Number of threads", registry = self.registry
 )

 # Async Task Metrics
 self.asyncio_tasks_active = Gauge(
 "asyncio_tasks_active",
 "Number of active asyncio tasks",
 registry = self.registry,
 )

 self.asyncio_tasks_pending = Gauge(
 "asyncio_tasks_pending",
 "Number of pending asyncio tasks",
 registry = self.registry,
 )

 self.asyncio_event_loop_lag_seconds = Histogram(
 "asyncio_event_loop_lag_seconds",
 "Event loop lag in seconds",
 buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
 registry = self.registry,
 )

 # =============================================================================
 # Resilience Mechanism Metrics (Integrated)
 # =============================================================================

 def _init_resilience_metrics(self):
 """Resilience mechanism integrated metrics"""

 # Global Circuit Breaker Metrics
 self.circuit_breaker_state = Enum(
 "circuit_breaker_state",
 "Current state of circuit breaker",
 ["service", "circuit_name"],
 states = ["closed", "open", "half_open"],
 registry = self.registry,
 )

 self.circuit_breaker_calls_total = Counter(
 "circuit_breaker_calls_total",
 "Total calls through circuit breaker",
 ["service", "circuit_name", "result"], # success, failure, timeout
 registry = self.registry,
 )

 self.circuit_breaker_state_transitions_total = Counter(
 "circuit_breaker_state_transitions_total",
 "Total state transitions",
 ["service", "circuit_name", "from_state", "to_state"],
 registry = self.registry,
 )

 self.circuit_breaker_failure_rate = Gauge(
 "circuit_breaker_failure_rate",
 "Current failure rate",
 ["service", "circuit_name"],
 registry = self.registry,
 )

 self.circuit_breaker_consecutive_failures = Gauge(
 "circuit_breaker_consecutive_failures",
 "Number of consecutive failures",
 ["service", "circuit_name"],
 registry = self.registry,
 )

 # E-Tag Caching Metrics
 self.etag_cache_requests_total = Counter(
 "etag_cache_requests_total",
 "Total E-Tag cache requests",
 ["resource_type", "result"], # hit, miss, stale
 registry = self.registry,
 )

 self.etag_cache_ttl_seconds = Histogram(
 "etag_cache_ttl_seconds",
 "E-Tag cache TTL in seconds",
 ["resource_type"],
 buckets=(60, 300, 600, 1800, 3600, 7200, 14400, 86400),
 registry = self.registry,
 )

 self.etag_cache_adaptive_adjustments_total = Counter(
 "etag_cache_adaptive_adjustments_total",
 "Total adaptive TTL adjustments",
 ["resource_type", "direction"], # increase, decrease
 registry = self.registry,
 )

 self.etag_cache_hit_rate = Gauge(
 "etag_cache_hit_rate",
 "Current cache hit rate",
 ["resource_type"],
 registry = self.registry,
 )

 # Distributed Caching Metrics (Redis)
 self.redis_operations_total = Counter(
 "redis_operations_total",
 "Total Redis operations",
 ["operation", "result"], # get, set, del / success, failure, timeout
 registry = self.registry,
 )

 self.redis_operation_duration_seconds = Histogram(
 "redis_operation_duration_seconds",
 "Redis operation duration in seconds",
 ["operation"],
 buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
 registry = self.registry,
 )

 self.redis_connections_active = Gauge(
 "redis_connections_active",
 "Number of active Redis connections",
 registry = self.registry,
 )

 self.redis_memory_usage_bytes = Gauge(
 "redis_memory_usage_bytes",
 "Redis memory usage in bytes",
 ["type"], # used, peak, fragmentation
 registry = self.registry,
 )

 # Backpressure Metrics
 self.backpressure_queue_size = Gauge(
 "backpressure_queue_size",
 "Current queue size",
 ["service", "queue_type"],
 registry = self.registry,
 )

 self.backpressure_requests_rejected_total = Counter(
 "backpressure_requests_rejected_total",
 "Total requests rejected due to backpressure",
 ["service", "reason"], # queue_full, rate_limit, resource_exhaustion
 registry = self.registry,
 )

 self.backpressure_queue_wait_seconds = Histogram(
 "backpressure_queue_wait_seconds",
 "Time spent waiting in queue",
 ["service", "priority"],
 buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
 registry = self.registry,
 )

 # =============================================================================
 # Business & Domain Metrics
 # =============================================================================

 def _init_business_metrics(self):
 """Business domain metrics"""

 # Schema Operations
 self.schema_operations_total = Counter(
 "schema_operations_total",
 "Total schema operations",
 ["operation", "branch", "result"], # create, update, delete, validate
 registry = self.registry,
 )

 self.schema_validation_duration_seconds = Histogram(
 "schema_validation_duration_seconds",
 "Schema validation duration",
 ["validation_type"],
 buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
 registry = self.registry,
 )

 # Document Operations
 self.document_operations_total = Counter(
 "document_operations_total",
 "Total document operations",
 ["operation", "branch", "document_type", "result"],
 registry = self.registry,
 )

 self.document_size_bytes = Histogram(
 "document_size_bytes",
 "Document size in bytes",
 ["document_type"],
 buckets=(1000, 10000, 100000, 1000000, 10000000),
 registry = self.registry,
 )

 # Branch Operations
 self.branch_operations_total = Counter(
 "branch_operations_total",
 "Total branch operations",
 ["operation", "result"], # create, merge, switch, delete
 registry = self.registry,
 )

 self.branch_merge_duration_seconds = Histogram(
 "branch_merge_duration_seconds",
 "Branch merge duration",
 buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0),
 registry = self.registry,
 )

 # Audit Events
 self.audit_events_total = Counter(
 "audit_events_total",
 "Total audit events",
 ["event_type", "service", "result"],
 registry = self.registry,
 )

 self.audit_processing_duration_seconds = Histogram(
 "audit_processing_duration_seconds",
 "Audit event processing duration",
 ["event_type"],
 buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
 registry = self.registry,
 )

 # =============================================================================
 # Security & Compliance Metrics
 # =============================================================================

 def _init_security_metrics(self):
 """Security and compliance metrics"""

 # Authentication Metrics
 self.auth_attempts_total = Counter(
 "auth_attempts_total",
 "Total authentication attempts",
 ["method", "result"], # jwt, oauth, api_key / success, failure, expired
 registry = self.registry,
 )

 self.auth_token_validations_total = Counter(
 "auth_token_validations_total",
 "Total token validations",
 [
 "token_type",
 "result",
 ], # access, refresh, service / valid, invalid, expired
 registry = self.registry,
 )

 # Authorization Metrics
 self.authz_checks_total = Counter(
 "authz_checks_total",
 "Total authorization checks",
 ["resource", "action", "result"], # allowed, denied, error
 registry = self.registry,
 )

 self.rbac_evaluations_total = Counter(
 "rbac_evaluations_total",
 "Total RBAC evaluations",
 ["scope", "permission", "result"],
 registry = self.registry,
 )

 # Security Events
 self.security_events_total = Counter(
 "security_events_total",
 "Total security events",
 [
 "event_type",
 "severity",
 ], # intrusion, breach, anomaly / low, medium, high, critical
 registry = self.registry,
 )

 self.failed_login_attempts = Counter(
 "failed_login_attempts_total",
 "Total failed login attempts",
 ["source_ip", "user_agent"],
 registry = self.registry,
 )

 # Rate Limiting
 self.rate_limit_hits_total = Counter(
 "rate_limit_hits_total",
 "Total rate limit hits",
 ["endpoint", "user_id", "limit_type"],
 registry = self.registry,
 )

 # =============================================================================
 # Performance & Optimization Metrics
 # =============================================================================

 def _init_performance_metrics(self):
 """Performance and optimization metrics"""

 # Database Performance
 self.database_query_duration_seconds = Histogram(
 "database_query_duration_seconds",
 "Database query duration",
 ["database", "operation", "table"],
 buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
 registry = self.registry,
 )

 self.database_connections_active = Gauge(
 "database_connections_active",
 "Active database connections",
 ["database", "pool"],
 registry = self.registry,
 )

 self.database_slow_queries_total = Counter(
 "database_slow_queries_total",
 "Total slow queries",
 ["database", "table", "operation"],
 registry = self.registry,
 )

 # Cache Performance
 self.cache_operations_total = Counter(
 "cache_operations_total",
 "Total cache operations",
 [
 "cache_type",
 "operation",
 "result",
 ], # memory, redis / get, set, delete / hit, miss
 registry = self.registry,
 )

 self.cache_memory_usage_bytes = Gauge(
 "cache_memory_usage_bytes",
 "Cache memory usage in bytes",
 ["cache_type"],
 registry = self.registry,
 )

 # API Performance
 self.api_latency_percentiles = Summary(
 "api_latency_percentiles",
 "API latency percentiles",
 ["endpoint", "method"],
 registry = self.registry,
 )

 self.api_throughput_requests_per_second = Gauge(
 "api_throughput_requests_per_second",
 "API throughput in requests per second",
 ["endpoint"],
 registry = self.registry,
 )

 # Resource Utilization
 self.resource_utilization_percent = Gauge(
 "resource_utilization_percent",
 "Resource utilization percentage",
 ["resource_type"], # cpu, memory, disk, network
 registry = self.registry,
 )

 self.connection_pool_utilization = Gauge(
 "connection_pool_utilization_percent",
 "Connection pool utilization percentage",
 ["pool_type", "target"],
 registry = self.registry,
 )


# =============================================================================
# Enterprise Metrics Collector
# =============================================================================


class EnterpriseMetricsCollector:
 """Enterprise-grade metrics collector"""

 def __init__(self, registry: EnterpriseMetricsRegistry):
 self.registry = registry
 self._gc_stats = {}
 self._process = psutil.Process()
 self._last_collection_time = time.time()

 async def collect_all_metrics(self):
 """Collect all metrics"""
 await asyncio.gather(
 self.collect_system_metrics(),
 self.collect_gc_metrics(),
 self.collect_application_metrics(),
 return_exceptions = True,
 )

 async def collect_system_metrics(self):
 """Collect system metrics"""
 try:
 # CPU Metrics
 cpu_percent = psutil.cpu_percent(interval = None, percpu = True)
 for i, percent in enumerate(cpu_percent):
 self.registry.cpu_usage_percent.labels(core = f"cpu{i}").set(percent)

 load_avg = psutil.getloadavg()
 self.registry.cpu_load_average.labels(interval = "1m").set(load_avg[0])
 self.registry.cpu_load_average.labels(interval = "5m").set(load_avg[1])
 self.registry.cpu_load_average.labels(interval = "15m").set(load_avg[2])

 # Memory Metrics
 memory = psutil.virtual_memory()
 self.registry.memory_usage_bytes.labels(type = "total").set(memory.total)
 self.registry.memory_usage_bytes.labels(type = "available").set(
 memory.available
 )
 self.registry.memory_usage_bytes.labels(type = "used").set(memory.used)
 self.registry.memory_usage_bytes.labels(type = "free").set(memory.free)
 self.registry.memory_usage_percent.set(memory.percent)

 # Disk Metrics
 for partition in psutil.disk_partitions():
 try:
 usage = psutil.disk_usage(partition.mountpoint)
 device = partition.device.replace("/", "_")
 mountpoint = partition.mountpoint.replace("/", "_")

 self.registry.disk_usage_bytes.labels(
 device = device, mountpoint = mountpoint, type = "total"
 ).set(usage.total)
 self.registry.disk_usage_bytes.labels(
 device = device, mountpoint = mountpoint, type = "used"
 ).set(usage.used)
 self.registry.disk_usage_bytes.labels(
 device = device, mountpoint = mountpoint, type = "free"
 ).set(usage.free)
 except PermissionError as e:
 # No access to this partition - skip silently (common for system partitions)
 import logging

 logger = logging.getLogger(__name__)
 logger.debug(
 f"No permission to access partition {partition.mountpoint}: {e}"
 )
 continue
 except OSError as e:
 # Filesystem error or unavailable mount - log but continue
 import logging

 logger = logging.getLogger(__name__)
 logger.warning(
 f"Cannot access disk partition {partition.mountpoint}: {e}"
 )
 continue
 except Exception as e:
 # Log unexpected disk metrics errors
 import logging

 logger = logging.getLogger(__name__)
 logger.error(
 f"Unexpected disk metrics error for partition {partition.mountpoint}: {e}"
 )
 continue

 # Network Metrics
 net_io = psutil.net_io_counters(pernic = True)
 for interface, stats in net_io.items():
 self.registry.network_io_bytes_total.labels(
 interface = interface, direction = "sent"
 )._value._value = stats.bytes_sent
 self.registry.network_io_bytes_total.labels(
 interface = interface, direction = "received"
 )._value._value = stats.bytes_recv

 self.registry.network_io_packets_total.labels(
 interface = interface, direction = "sent"
 )._value._value = stats.packets_sent
 self.registry.network_io_packets_total.labels(
 interface = interface, direction = "received"
 )._value._value = stats.packets_recv

 except Exception as e:
 logger.error(f"Failed to collect system metrics: {e}")

 async def collect_gc_metrics(self):
 """Collect garbage collection metrics"""
 try:
 import gc

 # GC statistics
 stats = gc.get_stats()
 for generation, stat in enumerate(stats):
 collections = stat.get("collections", 0)
 collected = stat.get("collected", 0)
 uncollectable = stat.get("uncollectable", 0)

 # Add only increments compared to previous value
 prev_collections = self._gc_stats.get(f"gen{generation}_collections", 0)
 if collections > prev_collections:
 self.registry.gc_collections_total.labels(
 generation = str(generation)
 )._value._value = collections

 prev_collected = self._gc_stats.get(f"gen{generation}_collected", 0)
 if collected > prev_collected:
 self.registry.gc_objects_collected_total.labels(
 generation = str(generation)
 )._value._value = collected

 prev_uncollectable = self._gc_stats.get(
 f"gen{generation}_uncollectable", 0
 )
 if uncollectable > prev_uncollectable:
 self.registry.gc_objects_uncollectable_total.labels(
 generation = str(generation)
 )._value._value = uncollectable

 self._gc_stats[f"gen{generation}_collections"] = collections
 self._gc_stats[f"gen{generation}_collected"] = collected
 self._gc_stats[f"gen{generation}_uncollectable"] = uncollectable

 # Track object count
 import sys

 object_counts = {}
 for obj in gc.get_objects():
 obj_type = type(obj).__name__
 object_counts[obj_type] = object_counts.get(obj_type, 0) + 1

 # Track only top 10 object types
 for obj_type, count in sorted(
 object_counts.items(), key = lambda x: x[1], reverse = True
 )[:10]:
 self.registry.memory_objects_count.labels(type = obj_type).set(count)

 # Process memory information
 memory_info = self._process.memory_info()
 self.registry.memory_rss_bytes.set(memory_info.rss)
 self.registry.memory_vms_bytes.set(memory_info.vms)

 except Exception as e:
 logger.error(f"Failed to collect GC metrics: {e}")

 async def collect_application_metrics(self):
 """Collect application metrics"""
 try:
 # Process metrics
 self.registry.process_cpu_seconds_total._value._value = (
 self._process.cpu_times().user + self._process.cpu_times().system
 )
 self.registry.process_open_fds.set(self._process.num_fds())

 # System max FD count (Linux/Unix based)
 import resource

 max_fds = resource.getrlimit(resource.RLIMIT_NOFILE)[0]
 self.registry.process_max_fds.set(max_fds)

 self.registry.process_threads.set(self._process.num_threads())

 # AsyncIO task collection
 try:
 loop = asyncio.get_running_loop()
 tasks = asyncio.all_tasks(loop)
 active_tasks = len([task for task in tasks if not task.done()])
 pending_tasks = len(
 [task for task in tasks if task.done() and not task.cancelled()]
 )

 self.registry.asyncio_tasks_active.set(active_tasks)
 self.registry.asyncio_tasks_pending.set(pending_tasks)
 except RuntimeError as e:
 # No running event loop - skip asyncio metrics (normal in sync context)
 import logging

 logger = logging.getLogger(__name__)
 logger.debug(f"No asyncio loop running for task metrics: {e}")
 except Exception as e:
 # Log unexpected asyncio metrics errors
 import logging

 logger = logging.getLogger(__name__)
 logger.warning(f"Failed to collect asyncio task metrics: {e}")

 except Exception as e:
 logger.error(f"Failed to collect application metrics: {e}")


# =============================================================================
# Metrics Integration Utilities
# =============================================================================

# Global metrics instance
enterprise_metrics = EnterpriseMetricsRegistry()
metrics_collector = EnterpriseMetricsCollector(enterprise_metrics)


def get_metrics_registry() -> EnterpriseMetricsRegistry:
 """Return metrics registry"""
 return enterprise_metrics


def get_metrics_collector() -> EnterpriseMetricsCollector:
 """Return metrics collector"""
 return metrics_collector


async def start_metrics_collection():
 """Start metrics collection"""

 async def collect_periodically():
 while True:
 try:
 await metrics_collector.collect_all_metrics()
 await asyncio.sleep(15) # Collect every 15 seconds
 except Exception as e:
 logger.error(f"Metrics collection error: {e}")
 await asyncio.sleep(5)

 # Run as background task
 asyncio.create_task(collect_periodically())


# =============================================================================
# FastAPI Integration
# =============================================================================


async def metrics_endpoint() -> Response:
 """Prometheus metrics endpoint"""
 return PlainTextResponse(
 generate_latest(enterprise_metrics.registry), media_type = CONTENT_TYPE_LATEST
 )


# Metrics collection decorator
def track_request_metrics(endpoint: str):
 """HTTP request metrics tracking decorator"""

 def decorator(func):
 @wraps(func)
 async def wrapper(*args, **kwargs):
 start_time = time.time()
 method = kwargs.get("request", args[0] if args else None)
 method_str = getattr(method, "method", "UNKNOWN") if method else "UNKNOWN"

 # Increment in-progress requests
 enterprise_metrics.http_requests_in_progress.labels(
 method = method_str, endpoint = endpoint, service = "oms"
 ).inc()

 try:
 result = await func(*args, **kwargs)
 status_code = getattr(result, "status_code", 200)

 # Record success metrics
 enterprise_metrics.http_requests_total.labels(
 method = method_str,
 endpoint = endpoint,
 status_code = str(status_code),
 service = "oms",
 ).inc()

 return result

 except Exception as e:
 # Record error metrics
 enterprise_metrics.http_requests_total.labels(
 method = method_str,
 endpoint = endpoint,
 status_code = "500",
 service = "oms",
 ).inc()
 raise

 finally:
 # Request completed
 duration = time.time() - start_time
 enterprise_metrics.http_request_duration_seconds.labels(
 method = method_str, endpoint = endpoint, service = "oms"
 ).observe(duration)

 enterprise_metrics.http_requests_in_progress.labels(
 method = method_str, endpoint = endpoint, service = "oms"
 ).dec()

 return wrapper

 return decorator
