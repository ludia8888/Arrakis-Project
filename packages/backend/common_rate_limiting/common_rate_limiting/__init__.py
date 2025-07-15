"""Common Rate Limiting Package

Unified rate limiting utilities for all services.
Provides consistent rate limiting implementations with multiple backends.
"""

from .algorithms import SlidingWindowAlgorithm, TokenBucketAlgorithm
from .backends import Backend, InMemoryBackend, RedisBackend
from .core import RateLimiter, RateLimitExceeded
from .middleware import (
    FastAPIRateLimitMiddleware,
    RateLimitMiddleware,
    rate_limit_decorator,
)

    FixedWindowAlgorithm

__version__ = "1.0.0"
__all__ = [
    "RateLimiter",
    "RateLimitExceeded",
    "RateLimitMiddleware",
    "FastAPIRateLimitMiddleware",
    "rate_limit_decorator",
    "RedisBackend",
    "InMemoryBackend",
    "Backend",
    "SlidingWindowAlgorithm",
    "TokenBucketAlgorithm",
    "FixedWindowAlgorithm",
]
