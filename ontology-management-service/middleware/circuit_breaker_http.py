"""
HTTP 서킷 브레이커 데코레이터
HTTP 응답 코드를 기반으로 서킷 브레이커를 적용합니다.
"""
import logging
from functools import wraps
from typing import Callable, Set, Optional
from fastapi import HTTPException

from middleware.circuit_breaker import CircuitBreaker, CircuitConfig

logger = logging.getLogger(__name__)


class HTTPError(Exception):
    """HTTP 에러를 나타내는 예외"""
    def __init__(self, status_code: int, detail: str = None):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")


def http_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    success_threshold: int = 3,
    timeout_seconds: float = 30,
    error_status_codes: Optional[Set[int]] = None,
    **kwargs
) -> Callable:
    """
    HTTP 응답 코드를 고려하는 서킷 브레이커 데코레이터
    
    Args:
        name: 서킷 브레이커 이름
        failure_threshold: 실패 임계값
        success_threshold: 성공 임계값  
        timeout_seconds: 타임아웃 시간
        error_status_codes: 실패로 간주할 HTTP 상태 코드 (기본값: 4xx, 5xx)
        **kwargs: 추가 서킷 브레이커 설정
    """
    if error_status_codes is None:
        # 기본값: 4xx, 5xx 상태 코드를 에러로 간주
        error_status_codes = set(range(400, 600))
    
    def decorator(func: Callable) -> Callable:
        # 서킷 브레이커 설정
        config = CircuitConfig(
            name=name,
            failure_threshold=failure_threshold,
            success_threshold=success_threshold,
            timeout_seconds=timeout_seconds,
            **kwargs
        )
        
        breaker = CircuitBreaker(config)
        
        @wraps(func)
        async def wrapper(*args, **func_kwargs):
            async def protected_func(*args, **kwargs):
                try:
                    result = await func(*args, **kwargs)
                    return result
                except HTTPException as e:
                    # HTTPException을 HTTP 상태 코드로 변환
                    if e.status_code in error_status_codes:
                        logger.debug(f"HTTP {e.status_code} treated as circuit breaker failure")
                        raise HTTPError(e.status_code, e.detail)
                    # 에러로 간주하지 않는 상태 코드는 그대로 통과
                    raise
                except Exception as e:
                    # 기타 예외는 그대로 처리
                    raise
            
            try:
                return await breaker.call(protected_func, *args, **func_kwargs)
            except HTTPError as e:
                # HTTPError를 다시 HTTPException으로 변환
                raise HTTPException(status_code=e.status_code, detail=e.detail)
        
        # 서킷 브레이커 참조 추가 (디버깅용)
        wrapper._circuit_breaker = breaker
        
        return wrapper
    
    return decorator