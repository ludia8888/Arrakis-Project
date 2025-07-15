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
 failure_threshold: int = 3, # 더 낮은 임계값
 success_threshold: int = 2,
 timeout_seconds: float = 30,
 error_status_codes: Optional[Set[int]] = None,
 **kwargs
) -> Callable:
 """
 Circuit breaker decorator that considers HTTP response codes

 Args:
 name: 서킷 브레이커 이름
 failure_threshold: 실패 임계값
 success_threshold: 성공 임계값
 timeout_seconds: 타임아웃 hours
 error_status_codes: 실패로 간주할 HTTP 상태 코드 (기본값: 4xx, 5xx)
 **kwargs: 추가 서킷 브레이커 설정
 """
 if error_status_codes is None:
 # 기본값: 4xx, 5xx 상태 코드를 에러로 간주
 error_status_codes = set(range(400, 600))

 def decorator(func: Callable) -> Callable:
 # 서킷 브레이커 설정
 config = CircuitConfig(
 name = name,
 failure_threshold = failure_threshold,
 success_threshold = success_threshold,
 timeout_seconds = timeout_seconds,
 **kwargs
 )

 breaker = CircuitBreaker(config)

 @wraps(func)
 async def wrapper(*args, **func_kwargs):
 logger.info(f"Circuit breaker {name}: Processing request,
     current state: {breaker.state}")

 async def protected_func(*args, **kwargs):
 try:
 result = await func(*args, **kwargs)
 logger.info(f"Circuit breaker {name}: Request succeeded")
 return result
 except HTTPException as e:
 # HTTPException을 HTTP 상태 코드로 변환
 if e.status_code in error_status_codes:
 logger.warning(f"Circuit breaker {name}: HTTP {e.status_code} treated as failure - {e.detail}")
 raise HTTPError(e.status_code, e.detail)
 # 에러로 간주하지 않는 상태 코드는 그대로 통과
 logger.info(f"Circuit breaker {name}: HTTP {e.status_code} not treated as failure")
 raise
 except Exception as e:
 logger.error(f"Circuit breaker {name}: Exception occurred - {type(e).__name__}: {e}")
 raise

 try:
 result = await breaker.call(protected_func, *args, **func_kwargs)
 logger.info(f"Circuit breaker {name}: Request completed successfully")
 return result
 except HTTPError as e:
 logger.warning(f"Circuit breaker {name}: Converting HTTPError back to HTTPException - {e.status_code}")
 # HTTPError를 다시 HTTPException으로 변환
 raise HTTPException(status_code = e.status_code, detail = e.detail)
 except Exception as e:
 # 서킷 브레이커가 열려있을 때의 처리
 if "circuit" in str(e).lower() and "open" in str(e).lower():
 logger.warning(f"Circuit breaker {name}: Circuit is OPEN, returning 503")
 raise HTTPException(
 status_code = 503,
 detail = f"Service temporarily unavailable - circuit breaker {name} is open"
 )
 logger.error(f"Circuit breaker {name}: Unhandled exception - {type(e).__name__}: {e}")
 raise

 # 서킷 브레이커 참조 추가 (디버깅용)
 wrapper._circuit_breaker = breaker

 return wrapper

 return decorator
