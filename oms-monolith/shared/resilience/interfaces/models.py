"""
Unified resilience data models
"""

from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum


class RetryStrategy(str, Enum):
    """Standard retry strategies across all implementations"""
    # Basic strategies
    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    FIBONACCI = "fibonacci"
    
    # Advanced strategies
    EXPONENTIAL_WITH_JITTER = "exponential_with_jitter"
    DECORRELATED_JITTER = "decorrelated_jitter"
    
    # Predefined configurations
    AGGRESSIVE = "aggressive"      # Fast retries, low delay
    STANDARD = "standard"          # Balanced approach
    CONSERVATIVE = "conservative"  # Slow retries, high delay
    CUSTOM = "custom"             # User-defined strategy


class CircuitState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "closed"        # Normal operation
    OPEN = "open"           # Failing, reject requests
    HALF_OPEN = "half_open" # Testing recovery


@dataclass
class RetryConfig:
    """Unified retry configuration"""
    # Basic retry settings
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_WITH_JITTER
    max_attempts: int = 3
    initial_delay: float = 1.0  # seconds
    max_delay: float = 60.0     # seconds
    
    # Backoff settings
    exponential_base: float = 2.0
    jitter_enabled: bool = True
    jitter_factor: float = 0.1  # 10% randomization
    
    # Advanced features
    circuit_breaker_enabled: bool = True
    bulkhead_enabled: bool = False
    retry_budget_enabled: bool = True
    
    # Retryable conditions
    retryable_exceptions: List[type] = field(default_factory=lambda: [
        ConnectionError, TimeoutError
    ])
    retryable_status_codes: List[int] = field(default_factory=lambda: [
        500, 502, 503, 504
    ])
    
    # Custom handlers
    on_retry: Optional[Callable[[int, Exception], None]] = None
    custom_backoff: Optional[Callable[[int], float]] = None


@dataclass
class RetryPolicy:
    """
    High-level retry policy for specific use cases.
    Maps to RetryConfig with appropriate settings.
    """
    name: str
    description: str
    max_retries: int
    initial_delay: float
    max_delay: float
    backoff_multiplier: float = 2.0
    jitter: bool = True
    
    def to_config(self) -> RetryConfig:
        """Convert policy to detailed config"""
        return RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL_WITH_JITTER if self.jitter else RetryStrategy.EXPONENTIAL,
            max_attempts=self.max_retries + 1,  # attempts = retries + 1
            initial_delay=self.initial_delay,
            max_delay=self.max_delay,
            exponential_base=self.backoff_multiplier,
            jitter_enabled=self.jitter
        )


# Predefined policies for common use cases
RETRY_POLICIES = {
    "standard": RetryPolicy(
        name="standard",
        description="Standard retry policy (replaces RetryStrategy.STANDARD)",
        max_retries=3,
        initial_delay=1.0,
        max_delay=10.0,
        backoff_multiplier=2.0,
        jitter=True
    ),
    "network": RetryPolicy(
        name="network",
        description="For network/HTTP requests",
        max_retries=3,
        initial_delay=0.5,
        max_delay=10.0,
        backoff_multiplier=2.0,
        jitter=True
    ),
    "conservative": RetryPolicy(
        name="conservative",
        description="Conservative retry policy (replaces RetryStrategy.CONSERVATIVE)",
        max_retries=2,
        initial_delay=2.0,
        max_delay=20.0,
        backoff_multiplier=1.5,
        jitter=True
    ),
    "database": RetryPolicy(
        name="database",
        description="For database operations",
        max_retries=5,
        initial_delay=1.0,
        max_delay=30.0,
        backoff_multiplier=1.5,
        jitter=True
    ),
    "webhook": RetryPolicy(
        name="webhook",
        description="For webhook deliveries",
        max_retries=3,
        initial_delay=30.0,
        max_delay=300.0,
        backoff_multiplier=2.0,
        jitter=False
    ),
    "validation": RetryPolicy(
        name="validation",
        description="For validation operations",
        max_retries=1,
        initial_delay=1.0,
        max_delay=1.0,
        backoff_multiplier=1.0,
        jitter=False
    ),
    "critical": RetryPolicy(
        name="critical",
        description="For critical operations",
        max_retries=10,
        initial_delay=0.1,
        max_delay=60.0,
        backoff_multiplier=1.3,
        jitter=True
    )
}


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""
    failure_threshold: int = 5
    success_threshold: int = 3
    timeout: timedelta = timedelta(seconds=60)
    half_open_timeout: timedelta = timedelta(seconds=30)
    
    # What to track as failures
    track_exceptions: List[type] = field(default_factory=lambda: [Exception])
    track_status_codes: List[int] = field(default_factory=lambda: [500, 502, 503, 504])
    
    # Callbacks
    on_open: Optional[Callable[[], None]] = None
    on_close: Optional[Callable[[], None]] = None
    on_half_open: Optional[Callable[[], None]] = None


@dataclass
class BulkheadConfig:
    """Bulkhead (resource isolation) configuration"""
    max_concurrent: int = 10
    max_queue_size: int = 100
    timeout: timedelta = timedelta(seconds=30)
    
    # Resource pool settings
    pool_name: str = "default"
    reject_on_full: bool = True


@dataclass
class RetryBudgetConfig:
    """Retry budget configuration to prevent retry storms"""
    budget_percent: float = 10.0  # 10% of requests can be retries
    min_requests: int = 100       # Minimum requests before budget applies
    window_size: timedelta = timedelta(minutes=1)
    
    # Token bucket settings
    tokens_per_second: float = 10.0
    max_tokens: int = 100


@dataclass
class RetryMetrics:
    """Metrics for retry operations"""
    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    retries_exhausted: int = 0
    
    # Timing
    total_retry_time: float = 0.0
    avg_retry_time: float = 0.0
    max_retry_time: float = 0.0
    
    # Circuit breaker metrics
    circuit_opens: int = 0
    circuit_closes: int = 0
    requests_rejected: int = 0
    
    # Retry budget metrics
    budget_exhausted: int = 0
    budget_remaining_percent: float = 100.0
    
    # Per-exception breakdown
    exceptions_by_type: Dict[str, int] = field(default_factory=dict)
    
    def record_attempt(self, success: bool, duration: float, exception: Optional[Exception] = None):
        """Record a retry attempt"""
        self.total_attempts += 1
        if success:
            self.successful_attempts += 1
        else:
            self.failed_attempts += 1
            if exception:
                exc_type = type(exception).__name__
                self.exceptions_by_type[exc_type] = self.exceptions_by_type.get(exc_type, 0) + 1
        
        self.total_retry_time += duration
        self.avg_retry_time = self.total_retry_time / self.total_attempts
        self.max_retry_time = max(self.max_retry_time, duration)


@dataclass
class RetryResult:
    """Result of a retry operation"""
    success: bool
    result: Optional[Any] = None
    exception: Optional[Exception] = None
    attempts: int = 0
    total_delay: float = 0.0
    metrics: Optional[RetryMetrics] = None


class RetryError(Exception):
    """Raised when all retry attempts are exhausted"""
    def __init__(self, message: str, attempts: int, last_exception: Optional[Exception] = None):
        super().__init__(message)
        self.attempts = attempts
        self.last_exception = last_exception