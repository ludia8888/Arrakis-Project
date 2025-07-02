"""
Unified Resilience Module - Single source of truth for all resilience patterns

This consolidates:
- shared/utils/retry_strategy.py → Unified retry executor
- core/scheduler/schedule_calculator.py → Backoff strategies
- shared/dlq/config.py → Retry policies
- Multiple circuit breaker implementations → Unified circuit breaker

All resilience patterns now use the same interfaces and implementations.
"""

from typing import Optional
from functools import wraps
import asyncio

# Import interfaces
from .interfaces import (
    RetryStrategy,
    CircuitState,
    RetryConfig,
    RetryPolicy,
    RetryMetrics,
    CircuitBreakerConfig,
    BulkheadConfig,
    RetryBudgetConfig,
    RetryResult,
    RetryError,
    RETRY_POLICIES
)

# Import implementations
from .implementations.retry_executor import UnifiedRetryExecutor
from .implementations.backoff_calculator import UnifiedBackoffCalculator
from .implementations.circuit_breaker import UnifiedCircuitBreaker
from .implementations.retry_budget import UnifiedRetryBudget

# Import services
from .services.resilience_factory import ResilienceFactory
from .services.resilience_registry import ResilienceRegistry

__all__ = [
    # Enums
    'RetryStrategy',
    'CircuitState',
    # Models
    'RetryConfig',
    'RetryPolicy',
    'RetryMetrics',
    'CircuitBreakerConfig',
    'BulkheadConfig',
    'RetryBudgetConfig',
    'RetryResult',
    'RetryError',
    'RETRY_POLICIES',
    # Implementations
    'UnifiedRetryExecutor',
    'UnifiedBackoffCalculator',
    'UnifiedCircuitBreaker',
    'UnifiedRetryBudget',
    # Services
    'ResilienceFactory',
    'ResilienceRegistry',
    # Decorators
    'with_retry',
    'with_circuit_breaker',
    'with_resilience'
]


# Convenience decorators

def with_retry(
    config: Optional[RetryConfig] = None,
    policy: Optional[str] = None
):
    """
    Decorator to add retry logic to a function.
    
    Args:
        config: Detailed retry configuration
        policy: Name of predefined policy ('network', 'database', etc.)
    
    Example:
        @with_retry(policy='network')
        async def fetch_data():
            return await http_client.get('/api/data')
    """
    # Use policy if provided
    if policy and policy in RETRY_POLICIES:
        config = RETRY_POLICIES[policy].to_config()
    elif not config:
        config = RetryConfig()
    
    def decorator(func):
        # Get or create retry executor
        executor = ResilienceRegistry.get_retry_executor("default")
        
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                async def _func():
                    return await func(*args, **kwargs)
                result = await executor.aexecute(_func, config)
                return result.result
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                def _func():
                    return func(*args, **kwargs)
                result = executor.execute(_func, config)
                return result.result
            return sync_wrapper
    
    return decorator


def with_circuit_breaker(
    name: str,
    config: Optional[CircuitBreakerConfig] = None
):
    """
    Decorator to add circuit breaker protection to a function.
    
    Args:
        name: Circuit breaker name (for sharing state across calls)
        config: Circuit breaker configuration
    
    Example:
        @with_circuit_breaker('user-service')
        async def get_user(user_id):
            return await user_service.get(user_id)
    """
    def decorator(func):
        # Get or create circuit breaker
        circuit_breaker = ResilienceRegistry.get_circuit_breaker(name, config)
        
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                async def _func():
                    return await func(*args, **kwargs)
                return await circuit_breaker.acall(_func)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                def _func():
                    return func(*args, **kwargs)
                return circuit_breaker.call(_func)
            return sync_wrapper
    
    return decorator


def with_resilience(
    retry_config: Optional[RetryConfig] = None,
    retry_policy: Optional[str] = None,
    circuit_breaker_name: Optional[str] = None,
    circuit_breaker_config: Optional[CircuitBreakerConfig] = None
):
    """
    Combined decorator for retry and circuit breaker.
    
    Example:
        @with_resilience(
            retry_policy='network',
            circuit_breaker_name='external-api'
        )
        async def call_external_api():
            return await external_api.call()
    """
    def decorator(func):
        # Apply circuit breaker first (outer)
        if circuit_breaker_name:
            func = with_circuit_breaker(circuit_breaker_name, circuit_breaker_config)(func)
        
        # Then apply retry (inner)
        func = with_retry(retry_config, retry_policy)(func)
        
        return func
    
    return decorator