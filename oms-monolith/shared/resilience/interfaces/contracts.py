"""
Resilience pattern interface contracts
"""

from abc import ABC, abstractmethod
from typing import TypeVar, Callable, Awaitable, Optional, Union
import asyncio

from .models import (
    RetryConfig,
    RetryResult,
    RetryMetrics,
    CircuitState,
    CircuitBreakerConfig
)

T = TypeVar('T')


class RetryStrategyInterface(ABC):
    """Interface for retry strategies"""
    
    @abstractmethod
    def execute(
        self,
        func: Callable[[], T],
        config: RetryConfig
    ) -> RetryResult:
        """Execute function with retry logic (sync)"""
        pass
    
    @abstractmethod
    async def aexecute(
        self,
        func: Callable[[], Awaitable[T]],
        config: RetryConfig
    ) -> RetryResult:
        """Execute async function with retry logic"""
        pass
    
    @abstractmethod
    def get_metrics(self) -> RetryMetrics:
        """Get retry metrics"""
        pass
    
    @abstractmethod
    def reset_metrics(self) -> None:
        """Reset retry metrics"""
        pass


class BackoffCalculatorInterface(ABC):
    """Interface for backoff calculations"""
    
    @abstractmethod
    def calculate_delay(
        self,
        attempt: int,
        config: RetryConfig
    ) -> float:
        """Calculate delay before next retry attempt"""
        pass
    
    @abstractmethod
    def add_jitter(
        self,
        delay: float,
        jitter_factor: float
    ) -> float:
        """Add jitter to delay to prevent thundering herd"""
        pass


class CircuitBreakerInterface(ABC):
    """Interface for circuit breaker pattern"""
    
    @abstractmethod
    def call(
        self,
        func: Callable[[], T],
        fallback: Optional[Callable[[], T]] = None
    ) -> T:
        """Execute function through circuit breaker (sync)"""
        pass
    
    @abstractmethod
    async def acall(
        self,
        func: Callable[[], Awaitable[T]],
        fallback: Optional[Callable[[], Awaitable[T]]] = None
    ) -> T:
        """Execute async function through circuit breaker"""
        pass
    
    @abstractmethod
    def get_state(self) -> CircuitState:
        """Get current circuit state"""
        pass
    
    @abstractmethod
    def record_success(self) -> None:
        """Record successful execution"""
        pass
    
    @abstractmethod
    def record_failure(self, error: Exception) -> None:
        """Record failed execution"""
        pass
    
    @abstractmethod
    def reset(self) -> None:
        """Reset circuit breaker state"""
        pass


class BulkheadInterface(ABC):
    """Interface for bulkhead (resource isolation) pattern"""
    
    @abstractmethod
    def acquire(self, timeout: Optional[float] = None) -> bool:
        """Acquire resource from bulkhead"""
        pass
    
    @abstractmethod
    def release(self) -> None:
        """Release resource back to bulkhead"""
        pass
    
    @abstractmethod
    def get_available_permits(self) -> int:
        """Get number of available permits"""
        pass
    
    @abstractmethod
    def get_queue_size(self) -> int:
        """Get current queue size"""
        pass


class RetryBudgetInterface(ABC):
    """Interface for retry budget pattern"""
    
    @abstractmethod
    def can_retry(self) -> bool:
        """Check if retry is allowed within budget"""
        pass
    
    @abstractmethod
    def record_attempt(self, is_retry: bool) -> None:
        """Record an attempt (original or retry)"""
        pass
    
    @abstractmethod
    def get_remaining_budget_percent(self) -> float:
        """Get remaining retry budget as percentage"""
        pass
    
    @abstractmethod
    def reset(self) -> None:
        """Reset retry budget"""
        pass


class ResilienceMetricsInterface(ABC):
    """Interface for resilience metrics collection"""
    
    @abstractmethod
    def record_retry_attempt(
        self,
        strategy: str,
        attempt: int,
        success: bool,
        duration: float
    ) -> None:
        """Record retry attempt metrics"""
        pass
    
    @abstractmethod
    def record_circuit_state_change(
        self,
        circuit_name: str,
        old_state: CircuitState,
        new_state: CircuitState
    ) -> None:
        """Record circuit breaker state change"""
        pass
    
    @abstractmethod
    def record_bulkhead_rejection(
        self,
        bulkhead_name: str
    ) -> None:
        """Record bulkhead rejection"""
        pass
    
    @abstractmethod
    def record_retry_budget_exhaustion(
        self,
        budget_name: str
    ) -> None:
        """Record retry budget exhaustion"""
        pass
    
    @abstractmethod
    def get_metrics_summary(self) -> dict:
        """Get summary of all resilience metrics"""
        pass