"""
Unified circuit breaker implementation
"""

import asyncio
import time
import threading
from typing import TypeVar, Callable, Awaitable, Optional, Dict
from datetime import datetime, timedelta
import logging

from ..interfaces import (
    CircuitBreakerInterface,
    CircuitState,
    CircuitBreakerConfig
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class UnifiedCircuitBreaker(CircuitBreakerInterface):
    """
    Thread-safe circuit breaker implementation.
    
    Consolidates circuit breakers from:
    - shared/security/protection_facade.py
    - middleware/auth_secure.py
    - shared/clients/unified_http_client.py
    """
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        
        # State management
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._state_changed_at = datetime.utcnow()
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Metrics
        self._total_calls = 0
        self._total_failures = 0
        self._total_successes = 0
        self._rejections = 0
    
    def call(
        self,
        func: Callable[[], T],
        fallback: Optional[Callable[[], T]] = None
    ) -> T:
        """Execute function through circuit breaker (sync)"""
        with self._lock:
            self._total_calls += 1
            
            # Check if we should attempt the call
            if not self._can_attempt():
                self._rejections += 1
                if fallback:
                    return fallback()
                raise Exception(f"Circuit breaker '{self.name}' is OPEN")
            
            # For HALF_OPEN state
            was_half_open = self._state == CircuitState.HALF_OPEN
        
        # Execute the function (outside lock to prevent blocking)
        try:
            result = func()
            
            # Record success
            with self._lock:
                self._record_success()
                
                # If we were half-open and succeeded, check if we should close
                if was_half_open and self._success_count >= self.config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)
            
            return result
            
        except Exception as e:
            # Check if this exception should be tracked
            should_track = self._should_track_exception(e)
            
            with self._lock:
                if should_track:
                    self._record_failure(e)
                    
                    # Check if we should open the circuit
                    if (self._state == CircuitState.CLOSED and 
                        self._failure_count >= self.config.failure_threshold):
                        self._transition_to(CircuitState.OPEN)
                    elif self._state == CircuitState.HALF_OPEN:
                        # Any failure in half-open goes back to open
                        self._transition_to(CircuitState.OPEN)
            
            # Re-raise or use fallback
            if fallback and should_track:
                return fallback()
            raise
    
    async def acall(
        self,
        func: Callable[[], Awaitable[T]],
        fallback: Optional[Callable[[], Awaitable[T]]] = None
    ) -> T:
        """Execute async function through circuit breaker"""
        with self._lock:
            self._total_calls += 1
            
            # Check if we should attempt the call
            if not self._can_attempt():
                self._rejections += 1
                if fallback:
                    return await fallback()
                raise Exception(f"Circuit breaker '{self.name}' is OPEN")
            
            # For HALF_OPEN state
            was_half_open = self._state == CircuitState.HALF_OPEN
        
        # Execute the function (outside lock to prevent blocking)
        try:
            result = await func()
            
            # Record success
            with self._lock:
                self._record_success()
                
                # If we were half-open and succeeded, check if we should close
                if was_half_open and self._success_count >= self.config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)
            
            return result
            
        except Exception as e:
            # Check if this exception should be tracked
            should_track = self._should_track_exception(e)
            
            with self._lock:
                if should_track:
                    self._record_failure(e)
                    
                    # Check if we should open the circuit
                    if (self._state == CircuitState.CLOSED and 
                        self._failure_count >= self.config.failure_threshold):
                        self._transition_to(CircuitState.OPEN)
                    elif self._state == CircuitState.HALF_OPEN:
                        # Any failure in half-open goes back to open
                        self._transition_to(CircuitState.OPEN)
            
            # Re-raise or use fallback
            if fallback and should_track:
                return await fallback()
            raise
    
    def get_state(self) -> CircuitState:
        """Get current circuit state"""
        with self._lock:
            self._check_state_transition()
            return self._state
    
    def record_success(self) -> None:
        """Manually record successful execution"""
        with self._lock:
            self._record_success()
    
    def record_failure(self, error: Exception) -> None:
        """Manually record failed execution"""
        with self._lock:
            self._record_failure(error)
    
    def reset(self) -> None:
        """Reset circuit breaker state"""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None
            self._state_changed_at = datetime.utcnow()
            logger.info(f"Circuit breaker '{self.name}' reset to CLOSED")
    
    def get_metrics(self) -> Dict[str, any]:
        """Get circuit breaker metrics"""
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "total_calls": self._total_calls,
                "total_failures": self._total_failures,
                "total_successes": self._total_successes,
                "rejections": self._rejections,
                "uptime": (datetime.utcnow() - self._state_changed_at).total_seconds()
            }
    
    def _can_attempt(self) -> bool:
        """Check if we can attempt a call"""
        self._check_state_transition()
        
        if self._state == CircuitState.CLOSED:
            return True
        elif self._state == CircuitState.OPEN:
            return False
        else:  # HALF_OPEN
            # In half-open, we allow limited attempts
            return True
    
    def _check_state_transition(self) -> None:
        """Check if state should transition based on timeouts"""
        if self._state == CircuitState.OPEN:
            # Check if timeout has passed
            time_in_open = datetime.utcnow() - self._state_changed_at
            if time_in_open >= self.config.timeout:
                self._transition_to(CircuitState.HALF_OPEN)
    
    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state"""
        old_state = self._state
        self._state = new_state
        self._state_changed_at = datetime.utcnow()
        
        # Reset counters based on transition
        if new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._success_count = 0
            self._failure_count = 0
        
        logger.info(f"Circuit breaker '{self.name}' transitioned from {old_state.value} to {new_state.value}")
        
        # Call callbacks
        if new_state == CircuitState.OPEN and self.config.on_open:
            try:
                self.config.on_open()
            except Exception as e:
                logger.error(f"Error in on_open callback: {e}")
        elif new_state == CircuitState.CLOSED and self.config.on_close:
            try:
                self.config.on_close()
            except Exception as e:
                logger.error(f"Error in on_close callback: {e}")
        elif new_state == CircuitState.HALF_OPEN and self.config.on_half_open:
            try:
                self.config.on_half_open()
            except Exception as e:
                logger.error(f"Error in on_half_open callback: {e}")
    
    def _record_success(self) -> None:
        """Record a successful call"""
        self._success_count += 1
        self._total_successes += 1
        
        # In closed state, reset failure count on success
        if self._state == CircuitState.CLOSED:
            self._failure_count = 0
    
    def _record_failure(self, error: Exception) -> None:
        """Record a failed call"""
        self._failure_count += 1
        self._total_failures += 1
        self._last_failure_time = datetime.utcnow()
    
    def _should_track_exception(self, exception: Exception) -> bool:
        """Check if exception should be tracked by circuit breaker"""
        # Check exception type
        for exc_type in self.config.track_exceptions:
            if isinstance(exception, exc_type):
                return True
        
        # Check HTTP status code if available
        if hasattr(exception, 'status_code'):
            return exception.status_code in self.config.track_status_codes
        
        return False