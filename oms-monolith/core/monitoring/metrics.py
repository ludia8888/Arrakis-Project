"""
Metrics module for monitoring
Provides Prometheus metrics for performance tracking
"""
from prometheus_client import Counter, Histogram, Gauge

# Operation counters
operation_counter = Counter(
    'oms_operations_total',
    'Total number of operations',
    ['operation', 'implementation', 'status']
)

# Operation duration histogram
operation_histogram = Histogram(
    'oms_operation_duration_seconds',
    'Operation duration in seconds',
    ['operation', 'implementation']
)

# Active operations gauge
active_operations = Gauge(
    'oms_active_operations',
    'Number of currently active operations',
    ['operation']
)

# Migration progress gauge
migration_progress = Gauge(
    'oms_migration_progress',
    'Progress of migration from legacy to native',
    ['component']
)