"""
HTTP circuit breaker decorator
Apply circuit breaker based on HTTP response codes.
"""
import logging
from functools import wraps
from typing import Callable, Optional, Set

from fastapi import HTTPException
from middleware.circuit_breaker import CircuitBreaker, CircuitConfig

logger = logging.getLogger(__name__)


class HTTPError(Exception):
    """Exception representing HTTP error"""

    def __init__(self, status_code: int, detail: str = None):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")


def http_circuit_breaker(
    name: str,
    failure_threshold: int = 3,  # lower threshold
    success_threshold: int = 2,
    timeout_seconds: float = 30,
    error_status_codes: Optional[Set[int]] = None,
    **kwargs,
) -> Callable:
    """
    Circuit breaker decorator that considers HTTP response codes

    Args:
        name: Circuit breaker name
        failure_threshold: Failure threshold
        success_threshold: Success threshold
        timeout_seconds: Timeout duration
        error_status_codes: HTTP status codes to consider as failures (default: 4xx, 5xx)
        **kwargs: Additional circuit breaker settings
    """
    if error_status_codes is None:
        # Default: Consider 4xx, 5xx status codes as errors
        error_status_codes = set(range(400, 600))

    def decorator(func: Callable) -> Callable:
        # Circuit breaker configuration
        config = CircuitConfig(
            name=name,
            failure_threshold=failure_threshold,
            success_threshold=success_threshold,
            timeout_seconds=timeout_seconds,
            **kwargs,
        )

        breaker = CircuitBreaker(config)

        @wraps(func)
        async def wrapper(*args, **func_kwargs):
            logger.info(
                f"Circuit breaker {name}: Processing request, current state: {breaker.state}"
            )

            async def protected_func(*args, **kwargs):
                try:
                    result = await func(*args, **kwargs)
                    logger.info(f"Circuit breaker {name}: Request succeeded")
                    return result
                except HTTPException as e:
                    # Convert HTTPException to HTTP status code
                    if e.status_code in error_status_codes:
                        logger.warning(
                            f"Circuit breaker {name}: HTTP {e.status_code} treated as failure - {e.detail}"
                        )
                        raise HTTPError(e.status_code, e.detail)
                    # Pass through status codes not considered as errors
                    logger.info(
                        f"Circuit breaker {name}: HTTP {e.status_code} not treated as failure"
                    )
                    raise
                except Exception as e:
                    logger.error(
                        f"Circuit breaker {name}: Exception occurred - {type(e).__name__}: {e}"
                    )
                    raise

            try:
                result = await breaker.call(protected_func, *args, **func_kwargs)
                logger.info(f"Circuit breaker {name}: Request completed successfully")
                return result
            except HTTPError as e:
                logger.warning(
                    f"Circuit breaker {name}: Converting HTTPError back to HTTPException - {e.status_code}"
                )
                # Convert HTTPError back to HTTPException
                raise HTTPException(status_code=e.status_code, detail=e.detail)
            except Exception as e:
                # Handle when circuit breaker is open
                if "circuit" in str(e).lower() and "open" in str(e).lower():
                    logger.warning(
                        f"Circuit breaker {name}: Circuit is OPEN, returning 503"
                    )
                    raise HTTPException(
                        status_code=503,
                        detail=f"Service temporarily unavailable - circuit breaker {name} is open",
                    )
                logger.error(
                    f"Circuit breaker {name}: Unhandled exception - {type(e).__name__}: {e}"
                )
                raise

        # Add circuit breaker reference (for debugging)
        wrapper._circuit_breaker = breaker

        return wrapper

    return decorator
