"""
DLQ configuration classes.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional

from .models import RetryPolicy


class RetryStrategy(Enum):
    """Retry strategies."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    CUSTOM = "custom"


@dataclass
class RetryConfig:
    """Retry configuration."""
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    initial_delay: float = 1.0
    max_delay: float = 300.0
    multiplier: float = 2.0
    jitter: bool = True
    custom_calculator: Optional[Callable[[int], float]] = None


@dataclass
class DLQConfig:
    """DLQ configuration."""
    name: str
    max_retries: int = 3
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    ttl: int = 86400  # 24 hours
    poison_threshold: int = 5
    deduplication_window: int = 3600  # 1 hour
    batch_size: int = 100
    processing_timeout: float = 300.0
    enable_compression: bool = True
    transform_function: Optional[Callable] = None
    success_callback: Optional[Callable] = None
    failure_callback: Optional[Callable] = None
    redis_key_prefix: str = "dlq"
    metrics_namespace: str = "dlq"