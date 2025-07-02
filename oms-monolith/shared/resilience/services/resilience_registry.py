"""
Resilience component registry - Central management for all resilience patterns
"""

import threading
from typing import Dict, Optional

from ..interfaces import (
    RetryConfig,
    CircuitBreakerConfig,
    RetryBudgetConfig
)
from ..implementations import (
    UnifiedRetryExecutor,
    UnifiedCircuitBreaker,
    UnifiedRetryBudget,
    UnifiedBackoffCalculator
)


class ResilienceRegistry:
    """
    Central registry for resilience components.
    Ensures single instances are shared across the application.
    """
    
    _lock = threading.Lock()
    _retry_executors: Dict[str, UnifiedRetryExecutor] = {}
    _circuit_breakers: Dict[str, UnifiedCircuitBreaker] = {}
    _retry_budgets: Dict[str, UnifiedRetryBudget] = {}
    _backoff_calculator = UnifiedBackoffCalculator()
    
    @classmethod
    def get_retry_executor(
        cls,
        name: str = "default",
        circuit_breaker_name: Optional[str] = None,
        retry_budget_name: Optional[str] = None
    ) -> UnifiedRetryExecutor:
        """Get or create a retry executor"""
        with cls._lock:
            if name not in cls._retry_executors:
                # Get associated components if specified
                circuit_breaker = None
                if circuit_breaker_name:
                    circuit_breaker = cls.get_circuit_breaker(circuit_breaker_name)
                
                retry_budget = None
                if retry_budget_name:
                    retry_budget = cls.get_retry_budget(retry_budget_name)
                
                # Create executor
                executor = UnifiedRetryExecutor(
                    backoff_calculator=cls._backoff_calculator,
                    circuit_breaker=circuit_breaker,
                    retry_budget=retry_budget
                )
                
                cls._retry_executors[name] = executor
            
            return cls._retry_executors[name]
    
    @classmethod
    def get_circuit_breaker(
        cls,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ) -> UnifiedCircuitBreaker:
        """Get or create a circuit breaker"""
        with cls._lock:
            if name not in cls._circuit_breakers:
                cls._circuit_breakers[name] = UnifiedCircuitBreaker(name, config)
            
            return cls._circuit_breakers[name]
    
    @classmethod
    def get_retry_budget(
        cls,
        name: str = "default",
        config: Optional[RetryBudgetConfig] = None
    ) -> UnifiedRetryBudget:
        """Get or create a retry budget"""
        with cls._lock:
            if name not in cls._retry_budgets:
                cls._retry_budgets[name] = UnifiedRetryBudget(config)
            
            return cls._retry_budgets[name]
    
    @classmethod
    def reset_circuit_breaker(cls, name: str) -> None:
        """Reset a specific circuit breaker"""
        with cls._lock:
            if name in cls._circuit_breakers:
                cls._circuit_breakers[name].reset()
    
    @classmethod
    def reset_all_circuit_breakers(cls) -> None:
        """Reset all circuit breakers"""
        with cls._lock:
            for cb in cls._circuit_breakers.values():
                cb.reset()
    
    @classmethod
    def get_metrics(cls) -> Dict[str, any]:
        """Get metrics from all resilience components"""
        with cls._lock:
            metrics = {
                "retry_executors": {},
                "circuit_breakers": {},
                "retry_budgets": {}
            }
            
            # Retry executor metrics
            for name, executor in cls._retry_executors.items():
                metrics["retry_executors"][name] = executor.get_metrics().__dict__
            
            # Circuit breaker metrics
            for name, cb in cls._circuit_breakers.items():
                metrics["circuit_breakers"][name] = cb.get_metrics()
            
            # Retry budget metrics
            for name, budget in cls._retry_budgets.items():
                metrics["retry_budgets"][name] = budget.get_metrics()
            
            return metrics
    
    @classmethod
    def clear(cls) -> None:
        """Clear all registered components (useful for testing)"""
        with cls._lock:
            cls._retry_executors.clear()
            cls._circuit_breakers.clear()
            cls._retry_budgets.clear()