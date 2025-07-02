"""
Circuit Breaker Adapters - Unifying multiple circuit breaker implementations
Following SSOT principle by adapting existing implementations to unified interface
"""

from typing import Optional, Callable, Any, List
from datetime import timedelta
import asyncio
import threading

from shared.resilience.interfaces import CircuitBreakerInterface, CircuitState, CircuitBreakerConfig
from shared.security.protection_facade import ProtectionFacade, CircuitBreakerConfig as FacadeConfig
from shared.utils.retry_strategy import CircuitBreaker as LegacyCircuitBreaker
from utils.logger import get_logger

logger = get_logger(__name__)


class ProtectionFacadeAdapter(CircuitBreakerInterface):
    """
    Adapter for Protection Facade's circuit breaker with Redis distribution
    Provides distributed state management capabilities
    """
    
    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        
        # Get protection facade instance
        self.protection_facade = ProtectionFacade.get_instance()
        
        # Convert config to facade format
        facade_config = FacadeConfig(
            failure_threshold=config.failure_threshold,
            success_threshold=config.success_threshold,
            timeout=config.timeout.total_seconds(),
            half_open_timeout=config.half_open_timeout.total_seconds(),
            enable_health_check=True,
            use_distributed_state=True  # Key feature: Redis-backed
        )
        
        # Get or create circuit breaker through facade
        self.circuit_breaker = self.protection_facade.get_circuit_breaker(
            name=name,
            failure_threshold=facade_config.failure_threshold,
            success_threshold=facade_config.success_threshold,
            timeout_seconds=facade_config.timeout,
            half_open_max_calls=facade_config.success_threshold
        )
    
    def call(self, func: Callable[[], Any]) -> Any:
        """Synchronous call through circuit breaker"""
        # Protection facade is async-first, so we need to run in event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an async context, create a task
            future = asyncio.create_task(self.circuit_breaker.call(func))
            return asyncio.run_coroutine_threadsafe(future, loop).result()
        else:
            # Create new event loop for sync call
            return asyncio.run(self.circuit_breaker.call(func))
    
    async def acall(self, func: Callable[[], Any]) -> Any:
        """Asynchronous call through circuit breaker"""
        return await self.circuit_breaker.call(func)
    
    def get_state(self) -> CircuitState:
        """Get current circuit state"""
        facade_state = self.circuit_breaker.state
        
        # Map facade states to unified states
        state_map = {
            "closed": CircuitState.CLOSED,
            "open": CircuitState.OPEN,
            "half_open": CircuitState.HALF_OPEN
        }
        
        return state_map.get(facade_state.lower(), CircuitState.CLOSED)
    
    def reset(self):
        """Reset circuit breaker to closed state"""
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(self.circuit_breaker._transition_to_closed())
        else:
            asyncio.run(self.circuit_breaker._transition_to_closed())
    
    def record_success(self):
        """Record a successful call"""
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(self.circuit_breaker._on_success())
        else:
            asyncio.run(self.circuit_breaker._on_success())
    
    def record_failure(self, exception: Optional[Exception] = None):
        """Record a failed call"""
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(self.circuit_breaker._on_failure())
        else:
            asyncio.run(self.circuit_breaker._on_failure())
    
    def is_closed(self) -> bool:
        """Check if circuit is closed (allowing requests)"""
        return self.get_state() == CircuitState.CLOSED
    
    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)"""
        return self.get_state() == CircuitState.OPEN
    
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)"""
        return self.get_state() == CircuitState.HALF_OPEN


class RetryStrategyAdapter(CircuitBreakerInterface):
    """
    Adapter for legacy retry_strategy.py circuit breaker
    Provides retry budget and bulkhead integration
    """
    
    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        
        # Create legacy circuit breaker
        self.circuit_breaker = LegacyCircuitBreaker(
            failure_threshold=config.failure_threshold,
            recovery_timeout=config.timeout.total_seconds(),
            expected_exception=Exception  # Track all exceptions by default
        )
        
        # State mapping
        self._state_map = {
            "closed": CircuitState.CLOSED,
            "open": CircuitState.OPEN,
            "half-open": CircuitState.HALF_OPEN
        }
    
    def call(self, func: Callable[[], Any]) -> Any:
        """Synchronous call through circuit breaker"""
        if self.circuit_breaker._state == "open":
            if not self.circuit_breaker._should_attempt_reset():
                raise Exception(f"Circuit breaker {self.name} is OPEN")
        
        try:
            result = func()
            self.circuit_breaker.record_success()
            return result
        except Exception as e:
            self.circuit_breaker.record_failure()
            raise
    
    async def acall(self, func: Callable[[], Any]) -> Any:
        """Asynchronous call through circuit breaker"""
        if self.circuit_breaker._state == "open":
            if not self.circuit_breaker._should_attempt_reset():
                raise Exception(f"Circuit breaker {self.name} is OPEN")
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func()
            else:
                result = func()
            self.circuit_breaker.record_success()
            return result
        except Exception as e:
            self.circuit_breaker.record_failure()
            raise
    
    def get_state(self) -> CircuitState:
        """Get current circuit state"""
        return self._state_map.get(self.circuit_breaker._state, CircuitState.CLOSED)
    
    def reset(self):
        """Reset circuit breaker to closed state"""
        with self.circuit_breaker._lock:
            self.circuit_breaker._state = "closed"
            self.circuit_breaker._failure_count = 0
            self.circuit_breaker._last_failure_time = None
            self.circuit_breaker._half_open_success_count = 0
    
    def record_success(self):
        """Record a successful call"""
        self.circuit_breaker.record_success()
    
    def record_failure(self, exception: Optional[Exception] = None):
        """Record a failed call"""
        self.circuit_breaker.record_failure()
    
    def is_closed(self) -> bool:
        """Check if circuit is closed"""
        return self.circuit_breaker._state == "closed"
    
    def is_open(self) -> bool:
        """Check if circuit is open"""
        return self.circuit_breaker._state == "open"
    
    def is_half_open(self) -> bool:
        """Check if circuit is half-open"""
        return self.circuit_breaker._state == "half-open"


class HTTPClientAdapter(CircuitBreakerInterface):
    """
    Adapter for HTTP client's simple circuit breaker
    Lightweight implementation for HTTP-specific operations
    """
    
    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        
        # Simple state management
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        self._success_count = 0
        self._lock = threading.Lock()
    
    def call(self, func: Callable[[], Any]) -> Any:
        """Synchronous call through circuit breaker"""
        with self._lock:
            if self._state == CircuitState.OPEN:
                # Check if we should transition to half-open
                if self._last_failure_time:
                    elapsed = (threading.current_thread().ident - self._last_failure_time)
                    if elapsed > self.config.timeout.total_seconds():
                        self._state = CircuitState.HALF_OPEN
                        self._success_count = 0
                else:
                    raise Exception(f"Circuit breaker {self.name} is OPEN")
        
        try:
            result = func()
            self._record_success()
            return result
        except Exception as e:
            self._record_failure()
            raise
    
    async def acall(self, func: Callable[[], Any]) -> Any:
        """Asynchronous call through circuit breaker"""
        # Similar logic but async
        return self.call(func)
    
    def get_state(self) -> CircuitState:
        """Get current circuit state"""
        return self._state
    
    def reset(self):
        """Reset circuit breaker"""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None
    
    def record_success(self):
        """Record success"""
        self._record_success()
    
    def record_failure(self, exception: Optional[Exception] = None):
        """Record failure"""
        self._record_failure()
    
    def _record_success(self):
        """Internal success recording"""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0
    
    def _record_failure(self):
        """Internal failure recording"""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = threading.current_thread().ident
            
            if self._failure_count >= self.config.failure_threshold:
                self._state = CircuitState.OPEN
                if self.config.on_open:
                    self.config.on_open()
            
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
    
    def is_closed(self) -> bool:
        return self._state == CircuitState.CLOSED
    
    def is_open(self) -> bool:
        return self._state == CircuitState.OPEN
    
    def is_half_open(self) -> bool:
        return self._state == CircuitState.HALF_OPEN


# Factory function to create appropriate adapter
def create_circuit_breaker_adapter(
    name: str,
    config: CircuitBreakerConfig,
    implementation: str = "unified"
) -> CircuitBreakerInterface:
    """
    Factory to create circuit breaker with specific implementation
    
    Args:
        name: Circuit breaker name
        config: Configuration
        implementation: Which implementation to use:
            - "unified": Use the new unified implementation (default)
            - "distributed": Use Protection Facade (Redis-backed)
            - "legacy": Use retry_strategy implementation
            - "lightweight": Use HTTP client implementation
    
    Returns:
        Circuit breaker instance with unified interface
    """
    if implementation == "distributed":
        logger.info(f"Creating distributed circuit breaker: {name}")
        return ProtectionFacadeAdapter(name, config)
    
    elif implementation == "legacy":
        logger.info(f"Creating legacy circuit breaker: {name}")
        return RetryStrategyAdapter(name, config)
    
    elif implementation == "lightweight":
        logger.info(f"Creating lightweight circuit breaker: {name}")
        return HTTPClientAdapter(name, config)
    
    else:
        # Default to unified implementation
        logger.info(f"Creating unified circuit breaker: {name}")
        from shared.resilience.implementations.circuit_breaker import UnifiedCircuitBreaker
        return UnifiedCircuitBreaker(config)