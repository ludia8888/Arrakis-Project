"""
Unified HTTP Client - 엔터프라이즈 레벨 통합 HTTP 클라이언트
모든 HTTP 통신을 위한 단일 클라이언트 제공
"""

import asyncio
import ssl
import time
from typing import Dict, Any, Optional, Union, Callable, Type
from contextlib import asynccontextmanager
from functools import wraps
import httpx
from httpx import AsyncClient, Response, HTTPError

from shared.config.unified_config import get_security_config
from shared.utils.logger import get_logger
from shared.monitoring.unified_metrics import get_metrics_collector
from shared.exceptions import (
    ServiceUnavailableError,
    ServiceTimeoutError,
    CircuitBreakerOpenError,
    RetryBudgetExhaustedError
)

logger = get_logger(__name__)
metrics = get_metrics_collector()


class UnifiedHTTPClient:
    """
    통합 HTTP 클라이언트
    
    기능:
    - mTLS 지원
    - 자동 재시도 (지수 백오프)
    - Circuit Breaker 패턴
    - Connection pooling
    - 메트릭 수집
    - 분산 추적
    - 타임아웃 관리
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff_factor: float = 2.0,
        circuit_breaker_failure_threshold: int = 5,
        circuit_breaker_recovery_timeout: int = 60,
        use_mtls: bool = False,
        mtls_cert_path: Optional[str] = None,
        mtls_key_path: Optional[str] = None,
        mtls_ca_path: Optional[str] = None,
        pool_size: int = 10,
        pool_max_keepalive: int = 30,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ):
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff_factor = retry_backoff_factor
        
        # Circuit Breaker 설정
        self.cb_failure_threshold = circuit_breaker_failure_threshold
        self.cb_recovery_timeout = circuit_breaker_recovery_timeout
        self.cb_failure_count = 0
        self.cb_last_failure_time = 0
        self.cb_state = "closed"  # closed, open, half-open
        
        # mTLS 설정
        self.use_mtls = use_mtls
        self.ssl_context = None
        if use_mtls:
            self.ssl_context = self._create_ssl_context(
                cert_path=mtls_cert_path,
                key_path=mtls_key_path,
                ca_path=mtls_ca_path
            )
        
        # HTTP 클라이언트 설정
        self.client_config = {
            "base_url": base_url,
            "timeout": httpx.Timeout(timeout=timeout),
            "limits": httpx.Limits(
                max_keepalive_connections=pool_size,
                max_connections=pool_size * 2,
                keepalive_expiry=pool_max_keepalive
            ),
            "headers": headers or {},
            "verify": self.ssl_context if self.ssl_context else True,
            **kwargs
        }
        
        self._client: Optional[AsyncClient] = None
    
    def _create_ssl_context(
        self,
        cert_path: Optional[str] = None,
        key_path: Optional[str] = None,
        ca_path: Optional[str] = None
    ) -> ssl.SSLContext:
        """mTLS용 SSL 컨텍스트 생성"""
        # 보안 설정에서 경로 가져오기
        security_config = get_security_config()
        
        cert_path = cert_path or security_config.mtls_cert_path
        key_path = key_path or security_config.mtls_key_path
        ca_path = ca_path or security_config.mtls_ca_path
        
        if not all([cert_path, key_path]):
            raise ValueError("mTLS requires both certificate and key paths")
        
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        
        # 클라이언트 인증서 설정
        context.load_cert_chain(certfile=cert_path, keyfile=key_path)
        
        # CA 인증서 설정
        if ca_path:
            context.load_verify_locations(cafile=ca_path)
        
        # 보안 강화 설정
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        
        return context
    
    async def __aenter__(self):
        """비동기 컨텍스트 진입"""
        self._client = AsyncClient(**self.client_config)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 종료"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def _check_circuit_breaker(self) -> None:
        """Circuit Breaker 상태 확인"""
        current_time = time.time()
        
        if self.cb_state == "open":
            # 복구 타임아웃 확인
            if current_time - self.cb_last_failure_time > self.cb_recovery_timeout:
                self.cb_state = "half-open"
                self.cb_failure_count = 0
                logger.info("Circuit breaker transitioned to half-open")
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is open, retry after {self.cb_recovery_timeout}s",
                    retry_after=int(self.cb_recovery_timeout - (current_time - self.cb_last_failure_time))
                )
    
    def _record_success(self) -> None:
        """성공 기록"""
        if self.cb_state == "half-open":
            self.cb_state = "closed"
            self.cb_failure_count = 0
            logger.info("Circuit breaker closed after successful request")
    
    def _record_failure(self) -> None:
        """실패 기록"""
        self.cb_failure_count += 1
        self.cb_last_failure_time = time.time()
        
        if self.cb_failure_count >= self.cb_failure_threshold:
            self.cb_state = "open"
            logger.warning(f"Circuit breaker opened after {self.cb_failure_count} failures")
    
    async def _execute_with_retry(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> Response:
        """재시도 로직을 포함한 요청 실행"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                # Circuit Breaker 확인
                self._check_circuit_breaker()
                
                # 메트릭 시작
                start_time = time.time()
                
                # 요청 실행
                if not self._client:
                    raise RuntimeError("Client not initialized. Use 'async with' context.")
                
                response = await self._client.request(method, url, **kwargs)
                
                # 메트릭 기록
                duration = time.time() - start_time
                metrics.http_request_duration.labels(
                    method=method,
                    status=response.status_code,
                    service=self.base_url or "unknown"
                ).observe(duration)
                
                # 성공 기록
                self._record_success()
                
                # 4xx 에러는 재시도하지 않음
                if 400 <= response.status_code < 500:
                    response.raise_for_status()
                
                # 5xx 에러는 재시도
                if response.status_code >= 500:
                    raise ServiceUnavailableError(
                        f"Service returned {response.status_code}"
                    )
                
                return response
                
            except (httpx.TimeoutException, asyncio.TimeoutError) as e:
                last_exception = ServiceTimeoutError(f"Request timeout: {e}")
                self._record_failure()
                
            except httpx.HTTPStatusError as e:
                if 400 <= e.response.status_code < 500:
                    # 클라이언트 에러는 재시도하지 않음
                    raise
                last_exception = e
                self._record_failure()
                
            except (httpx.RequestError, HTTPError) as e:
                last_exception = ServiceUnavailableError(f"Request failed: {e}")
                self._record_failure()
                
            except CircuitBreakerOpenError:
                raise
                
            except Exception as e:
                last_exception = e
                self._record_failure()
            
            # 마지막 시도가 아니면 대기
            if attempt < self.max_retries:
                backoff_time = self.retry_backoff_factor ** attempt
                logger.warning(
                    f"Request failed (attempt {attempt + 1}/{self.max_retries + 1}), "
                    f"retrying in {backoff_time}s: {last_exception}"
                )
                await asyncio.sleep(backoff_time)
        
        # 모든 재시도 실패
        metrics.http_request_failures.labels(
            method=method,
            service=self.base_url or "unknown",
            reason="max_retries_exceeded"
        ).inc()
        
        raise RetryBudgetExhaustedError(
            f"All {self.max_retries + 1} attempts failed. Last error: {last_exception}"
        )
    
    # === 공개 API 메서드 ===
    
    async def get(self, url: str, **kwargs) -> Response:
        """GET 요청"""
        return await self._execute_with_retry("GET", url, **kwargs)
    
    async def post(self, url: str, **kwargs) -> Response:
        """POST 요청"""
        return await self._execute_with_retry("POST", url, **kwargs)
    
    async def put(self, url: str, **kwargs) -> Response:
        """PUT 요청"""
        return await self._execute_with_retry("PUT", url, **kwargs)
    
    async def patch(self, url: str, **kwargs) -> Response:
        """PATCH 요청"""
        return await self._execute_with_retry("PATCH", url, **kwargs)
    
    async def delete(self, url: str, **kwargs) -> Response:
        """DELETE 요청"""
        return await self._execute_with_retry("DELETE", url, **kwargs)
    
    async def head(self, url: str, **kwargs) -> Response:
        """HEAD 요청"""
        return await self._execute_with_retry("HEAD", url, **kwargs)
    
    async def options(self, url: str, **kwargs) -> Response:
        """OPTIONS 요청"""
        return await self._execute_with_retry("OPTIONS", url, **kwargs)
    
    async def request(self, method: str, url: str, **kwargs) -> Response:
        """일반 요청"""
        return await self._execute_with_retry(method.upper(), url, **kwargs)
    
    # === 헬스 체크 ===
    
    async def health_check(self, health_endpoint: str = "/health") -> bool:
        """헬스 체크"""
        try:
            response = await self.get(health_endpoint)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    # === 유틸리티 메서드 ===
    
    def get_circuit_breaker_state(self) -> Dict[str, Any]:
        """Circuit Breaker 상태 반환"""
        return {
            "state": self.cb_state,
            "failure_count": self.cb_failure_count,
            "last_failure_time": self.cb_last_failure_time,
            "recovery_timeout": self.cb_recovery_timeout
        }
    
    @classmethod
    async def create_client(
        cls,
        service_name: str,
        **kwargs
    ) -> 'UnifiedHTTPClient':
        """서비스별 클라이언트 생성 팩토리"""
        # 서비스별 기본 설정
        service_configs = {
            "user-service": {
                "base_url": "http://user-service:8000",
                "timeout": 10.0,
                "use_mtls": True
            },
            "iam-service": {
                "base_url": "http://iam-service:8000",
                "timeout": 15.0,
                "use_mtls": True
            },
            "audit-service": {
                "base_url": "http://audit-service:8000",
                "timeout": 5.0,
                "max_retries": 5
            }
        }
        
        # 서비스 설정과 사용자 설정 병합
        config = service_configs.get(service_name, {})
        config.update(kwargs)
        
        return cls(**config)


# === 편의 함수 ===

@asynccontextmanager
async def create_http_client(**kwargs) -> UnifiedHTTPClient:
    """HTTP 클라이언트 생성 (컨텍스트 매니저)"""
    async with UnifiedHTTPClient(**kwargs) as client:
        yield client


async def make_request(
    method: str,
    url: str,
    **kwargs
) -> Response:
    """단일 요청 실행"""
    async with create_http_client() as client:
        return await client.request(method, url, **kwargs)


# === 데코레이터 ===

def with_http_client(
    client_factory: Optional[Callable[..., UnifiedHTTPClient]] = None,
    **client_kwargs
):
    """HTTP 클라이언트를 주입하는 데코레이터"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if client_factory:
                client = client_factory(**client_kwargs)
            else:
                client = UnifiedHTTPClient(**client_kwargs)
            
            async with client as http_client:
                # 클라이언트를 함수에 주입
                return await func(*args, http_client=http_client, **kwargs)
        
        return wrapper
    return decorator