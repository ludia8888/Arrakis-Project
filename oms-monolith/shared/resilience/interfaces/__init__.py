"""
Unified Resilience Interfaces - Single source of truth for all resilience patterns

This consolidates:
- shared/utils/retry_strategy.py → Unified retry with all strategies
- core/scheduler/schedule_calculator.py → Backoff calculations
- shared/dlq/config.py → DLQ retry policies
- Circuit breaker implementations from multiple modules
"""

from .contracts import (
    RetryStrategyInterface,
    BackoffCalculatorInterface,
    CircuitBreakerInterface,
    BulkheadInterface,
    RetryBudgetInterface,
    ResilienceMetricsInterface
)

from .models import (
    RetryStrategy,
    CircuitState,
    RetryConfig,
    RetryPolicy,
    RetryMetrics,
    CircuitBreakerConfig,
    BulkheadConfig,
    RetryBudgetConfig,
    RetryResult,
    RetryError
)

__all__ = [
    # Contracts
    'RetryStrategyInterface',
    'BackoffCalculatorInterface',
    'CircuitBreakerInterface',
    'BulkheadInterface',
    'RetryBudgetInterface',
    'ResilienceMetricsInterface',
    # Models
    'RetryStrategy',
    'CircuitState',
    'RetryConfig',
    'RetryPolicy',
    'RetryMetrics',
    'CircuitBreakerConfig',
    'BulkheadConfig',
    'RetryBudgetConfig',
    'RetryResult',
    'RetryError'
]