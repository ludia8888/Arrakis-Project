"""
Unified backoff calculator implementation
"""

import random
import math
from typing import Optional

from ..interfaces import (
    BackoffCalculatorInterface,
    RetryConfig,
    RetryStrategy
)


class UnifiedBackoffCalculator(BackoffCalculatorInterface):
    """
    Unified backoff calculator supporting all strategies.
    
    Consolidates:
    - Exponential backoff from retry_strategy.py
    - Linear/Fixed/Fibonacci from schedule_calculator.py
    - Jitter algorithms
    """
    
    def calculate_delay(
        self,
        attempt: int,
        config: RetryConfig
    ) -> float:
        """Calculate delay before next retry attempt"""
        if config.custom_backoff:
            delay = config.custom_backoff(attempt)
        else:
            delay = self._calculate_base_delay(attempt, config)
        
        # Apply jitter if enabled
        if config.jitter_enabled:
            delay = self.add_jitter(delay, config.jitter_factor)
        
        # Cap at max delay
        return min(delay, config.max_delay)
    
    def add_jitter(
        self,
        delay: float,
        jitter_factor: float
    ) -> float:
        """Add jitter to delay to prevent thundering herd"""
        # Full jitter: random between 0 and delay
        if jitter_factor >= 1.0:
            return random.uniform(0, delay)
        
        # Partial jitter: delay ± (delay * jitter_factor)
        jitter_range = delay * jitter_factor
        return delay + random.uniform(-jitter_range, jitter_range)
    
    def _calculate_base_delay(
        self,
        attempt: int,
        config: RetryConfig
    ) -> float:
        """Calculate base delay based on strategy"""
        strategy = config.strategy
        
        # Map predefined strategies to calculation methods
        if strategy == RetryStrategy.AGGRESSIVE:
            return self._aggressive_backoff(attempt, config)
        elif strategy == RetryStrategy.STANDARD:
            return self._standard_backoff(attempt, config)
        elif strategy == RetryStrategy.CONSERVATIVE:
            return self._conservative_backoff(attempt, config)
        
        # Basic strategies
        elif strategy == RetryStrategy.FIXED:
            return config.initial_delay
        
        elif strategy == RetryStrategy.LINEAR:
            return config.initial_delay * attempt
        
        elif strategy == RetryStrategy.EXPONENTIAL:
            return config.initial_delay * (config.exponential_base ** (attempt - 1))
        
        elif strategy == RetryStrategy.EXPONENTIAL_WITH_JITTER:
            # Exponential with built-in jitter
            base_delay = config.initial_delay * (config.exponential_base ** (attempt - 1))
            return base_delay
        
        elif strategy == RetryStrategy.FIBONACCI:
            return config.initial_delay * self._fibonacci(attempt)
        
        elif strategy == RetryStrategy.DECORRELATED_JITTER:
            # AWS-style decorrelated jitter
            if not hasattr(self, '_last_delay'):
                self._last_delay = config.initial_delay
            
            self._last_delay = random.uniform(
                config.initial_delay,
                self._last_delay * 3
            )
            return min(self._last_delay, config.max_delay)
        
        else:
            # Default to exponential
            return config.initial_delay * (config.exponential_base ** (attempt - 1))
    
    def _aggressive_backoff(self, attempt: int, config: RetryConfig) -> float:
        """Aggressive strategy - fast retries"""
        # Override config for aggressive approach
        initial = 0.1
        base = 1.3
        return initial * (base ** (attempt - 1))
    
    def _standard_backoff(self, attempt: int, config: RetryConfig) -> float:
        """Standard strategy - balanced approach"""
        initial = 1.0
        base = 2.0
        return initial * (base ** (attempt - 1))
    
    def _conservative_backoff(self, attempt: int, config: RetryConfig) -> float:
        """Conservative strategy - slow retries"""
        initial = 2.0
        base = 3.0
        return initial * (base ** (attempt - 1))
    
    def _fibonacci(self, n: int) -> int:
        """Calculate nth Fibonacci number"""
        if n <= 1:
            return n
        
        a, b = 0, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        return b