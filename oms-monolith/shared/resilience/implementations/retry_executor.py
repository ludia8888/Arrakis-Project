"""
Unified retry executor implementation
"""

import asyncio
import time
import logging
from typing import TypeVar, Callable, Awaitable, Optional, Union

from ..interfaces import (
    RetryStrategyInterface,
    RetryConfig,
    RetryResult,
    RetryMetrics,
    RetryError
)
from .backoff_calculator import UnifiedBackoffCalculator
from .circuit_breaker import UnifiedCircuitBreaker
from .retry_budget import UnifiedRetryBudget

logger = logging.getLogger(__name__)

T = TypeVar('T')


class UnifiedRetryExecutor(RetryStrategyInterface):
    """
    Unified retry executor that consolidates all retry patterns.
    
    Features:
    - Multiple backoff strategies
    - Circuit breaker integration
    - Retry budget management
    - Comprehensive metrics
    - Sync and async support
    """
    
    def __init__(
        self,
        backoff_calculator: Optional[UnifiedBackoffCalculator] = None,
        circuit_breaker: Optional[UnifiedCircuitBreaker] = None,
        retry_budget: Optional[UnifiedRetryBudget] = None
    ):
        self.backoff_calculator = backoff_calculator or UnifiedBackoffCalculator()
        self.circuit_breaker = circuit_breaker
        self.retry_budget = retry_budget
        self.metrics = RetryMetrics()
    
    def execute(
        self,
        func: Callable[[], T],
        config: RetryConfig
    ) -> RetryResult:
        """Execute function with retry logic (sync)"""
        start_time = time.time()
        last_exception = None
        total_delay = 0.0
        
        for attempt in range(config.max_attempts):
            try:
                # Check retry budget if enabled
                if config.retry_budget_enabled and self.retry_budget:
                    if attempt > 0 and not self.retry_budget.can_retry():
                        self.metrics.budget_exhausted += 1
                        raise RetryError(
                            "Retry budget exhausted",
                            attempts=attempt,
                            last_exception=last_exception
                        )
                    self.retry_budget.record_attempt(is_retry=attempt > 0)
                
                # Execute through circuit breaker if enabled
                if config.circuit_breaker_enabled and self.circuit_breaker:
                    result = self.circuit_breaker.call(func)
                else:
                    result = func()
                
                # Success
                duration = time.time() - start_time
                self.metrics.record_attempt(True, duration)
                
                return RetryResult(
                    success=True,
                    result=result,
                    attempts=attempt + 1,
                    total_delay=total_delay,
                    metrics=self.metrics
                )
                
            except Exception as e:
                last_exception = e
                
                # Check if retryable
                if not self._is_retryable(e, config):
                    duration = time.time() - start_time
                    self.metrics.record_attempt(False, duration, e)
                    raise
                
                # Record failure
                duration = time.time() - start_time
                self.metrics.record_attempt(False, duration, e)
                
                # Last attempt?
                if attempt >= config.max_attempts - 1:
                    self.metrics.retries_exhausted += 1
                    break
                
                # Calculate delay
                delay = self.backoff_calculator.calculate_delay(attempt + 1, config)
                total_delay += delay
                
                # Call retry callback if provided
                if config.on_retry:
                    try:
                        config.on_retry(attempt + 1, e)
                    except Exception as callback_error:
                        logger.error(f"Retry callback error: {callback_error}")
                
                # Sleep
                logger.debug(f"Retry {attempt + 1}/{config.max_attempts} after {delay:.2f}s delay")
                time.sleep(delay)
        
        # All retries exhausted
        raise RetryError(
            f"All {config.max_attempts} retry attempts failed",
            attempts=config.max_attempts,
            last_exception=last_exception
        )
    
    async def aexecute(
        self,
        func: Callable[[], Awaitable[T]],
        config: RetryConfig
    ) -> RetryResult:
        """Execute async function with retry logic"""
        start_time = time.time()
        last_exception = None
        total_delay = 0.0
        
        for attempt in range(config.max_attempts):
            try:
                # Check retry budget if enabled
                if config.retry_budget_enabled and self.retry_budget:
                    if attempt > 0 and not self.retry_budget.can_retry():
                        self.metrics.budget_exhausted += 1
                        raise RetryError(
                            "Retry budget exhausted",
                            attempts=attempt,
                            last_exception=last_exception
                        )
                    self.retry_budget.record_attempt(is_retry=attempt > 0)
                
                # Execute through circuit breaker if enabled
                if config.circuit_breaker_enabled and self.circuit_breaker:
                    result = await self.circuit_breaker.acall(func)
                else:
                    result = await func()
                
                # Success
                duration = time.time() - start_time
                self.metrics.record_attempt(True, duration)
                
                return RetryResult(
                    success=True,
                    result=result,
                    attempts=attempt + 1,
                    total_delay=total_delay,
                    metrics=self.metrics
                )
                
            except Exception as e:
                last_exception = e
                
                # Check if retryable
                if not self._is_retryable(e, config):
                    duration = time.time() - start_time
                    self.metrics.record_attempt(False, duration, e)
                    raise
                
                # Record failure
                duration = time.time() - start_time
                self.metrics.record_attempt(False, duration, e)
                
                # Last attempt?
                if attempt >= config.max_attempts - 1:
                    self.metrics.retries_exhausted += 1
                    break
                
                # Calculate delay
                delay = self.backoff_calculator.calculate_delay(attempt + 1, config)
                total_delay += delay
                
                # Call retry callback if provided
                if config.on_retry:
                    try:
                        config.on_retry(attempt + 1, e)
                    except Exception as callback_error:
                        logger.error(f"Retry callback error: {callback_error}")
                
                # Sleep
                logger.debug(f"Retry {attempt + 1}/{config.max_attempts} after {delay:.2f}s delay")
                await asyncio.sleep(delay)
        
        # All retries exhausted
        raise RetryError(
            f"All {config.max_attempts} retry attempts failed",
            attempts=config.max_attempts,
            last_exception=last_exception
        )
    
    def get_metrics(self) -> RetryMetrics:
        """Get retry metrics"""
        return self.metrics
    
    def reset_metrics(self) -> None:
        """Reset retry metrics"""
        self.metrics = RetryMetrics()
    
    def _is_retryable(self, exception: Exception, config: RetryConfig) -> bool:
        """Check if exception is retryable"""
        # Check exception type
        for exc_type in config.retryable_exceptions:
            if isinstance(exception, exc_type):
                return True
        
        # Check HTTP status code if available
        if hasattr(exception, 'status_code'):
            return exception.status_code in config.retryable_status_codes
        
        return False