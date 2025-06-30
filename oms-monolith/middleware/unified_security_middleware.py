"""
Unified Security Middleware - Single Security Layer
모든 보안 기능을 통합한 단일 미들웨어
"""

import uuid
import time
from typing import Optional, Dict, Any, List
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from shared.security import (
    get_auth_facade,
    get_protection_facade,
    get_security_exception_handler,
    SecurityContext,
    SecurityViolation,
    ProtectionViolation,
    CircuitBreakerConfig,
    RateLimiterConfig,
    RateLimitStrategy
)
from shared.utils.logger import get_logger

logger = get_logger(__name__)


class UnifiedSecurityMiddleware(BaseHTTPMiddleware):
    """
    통합 보안 미들웨어
    
    모든 요청에 대해 순차적으로 다음을 수행:
    1. 인증/인가 (AuthenticationFacade)
    2. Rate Limiting (ProtectionFacade)
    3. Circuit Breaking (ProtectionFacade)
    4. 보안 컨텍스트 주입
    """
    
    def __init__(
        self,
        app,
        enable_rate_limiting: bool = True,
        enable_circuit_breaking: bool = True,
        bypass_paths: Optional[List[str]] = None
    ):
        super().__init__(app)
        
        # 설정
        self.enable_rate_limiting = enable_rate_limiting
        self.enable_circuit_breaking = enable_circuit_breaking
        self.bypass_paths = bypass_paths or ["/health", "/metrics", "/docs", "/openapi.json"]
        
        # 통합 보안 계층 인스턴스
        self.auth_facade = get_auth_facade()
        self.protection_facade = get_protection_facade()
        self.exception_handler = get_security_exception_handler()
        
        # 보호 설정 초기화
        self._setup_protection_configs()
    
    def _setup_protection_configs(self):
        """보호 계층 설정 초기화"""
        
        # Rate Limiter 설정
        rate_config = RateLimiterConfig(
            strategy=RateLimitStrategy.SLIDING_WINDOW,
            requests_per_window=100,  # 기본: 분당 100 요청
            window_size=60,
            use_distributed_state=True,
            redis_key_prefix="unified_rate_limiter"
        )
        
        # 기본 Rate Limiter 생성
        self.protection_facade.get_rate_limiter("api_default", rate_config)
        
        # GraphQL 전용 Rate Limiter (더 엄격)
        graphql_rate_config = RateLimiterConfig(
            strategy=RateLimitStrategy.SLIDING_WINDOW,
            requests_per_window=50,  # GraphQL은 더 제한적
            window_size=60,
            use_distributed_state=True,
            redis_key_prefix="graphql_rate_limiter"
        )
        self.protection_facade.get_rate_limiter("graphql", graphql_rate_config)
        
        # Circuit Breaker 설정
        circuit_config = CircuitBreakerConfig(
            failure_threshold=5,
            success_threshold=3,
            timeout=60.0,
            use_distributed_state=True,
            redis_key_prefix="unified_circuit_breaker"
        )
        
        # 서비스별 Circuit Breaker 생성
        self.protection_facade.get_circuit_breaker("api_service", circuit_config)
        self.protection_facade.get_circuit_breaker("graphql_service", circuit_config)
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """요청 처리"""
        
        # 요청 메타데이터 수집
        request_id = str(uuid.uuid4())
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        path = request.url.path
        
        # 요청 상태에 request_id 저장
        request.state.request_id = request_id
        
        # 우회 경로 확인
        if self._should_bypass_security(path):
            logger.debug(f"Bypassing security for path: {path}")
            return await call_next(request)
        
        start_time = time.time()
        
        try:
            # 1. 인증/인가 처리
            security_context = await self._authenticate_request(
                request, request_id, client_ip, user_agent
            )
            
            # 보안 컨텍스트를 요청 상태에 저장
            request.state.security_context = security_context
            
            # 2. 보호된 실행 (Rate Limiting + Circuit Breaking)
            response = await self._protected_execution(
                request, security_context, call_next
            )
            
            # 3. 응답 후처리
            execution_time = time.time() - start_time
            await self._log_successful_request(
                request_id, security_context, path, execution_time
            )
            
            return response
            
        except SecurityViolation as e:
            return await self.exception_handler.handle_security_violation(request, e)
        
        except ProtectionViolation as e:
            return await self.exception_handler.handle_protection_violation(request, e)
        
        except Exception as e:
            return await self.exception_handler.handle_general_exception(request, e)
        
        finally:
            # 세션 정리 (메모리 누수 방지)
            self.auth_facade.invalidate_session(request_id)
    
    async def _authenticate_request(
        self,
        request: Request,
        request_id: str,
        client_ip: str,
        user_agent: str
    ) -> SecurityContext:
        """요청 인증 처리"""
        
        # JWT 토큰 추출
        token = self._extract_token(request)
        
        # 인증 수행
        security_context = await self.auth_facade.authenticate_request(
            token=token,
            request_id=request_id,
            client_ip=client_ip,
            user_agent=user_agent
        )
        
        # 경로별 인증 요구사항 확인
        if self._requires_authentication(request.url.path):
            security_context.require_authentication()
        
        # 관리자 경로 접근 확인
        if self._requires_admin_access(request.url.path):
            security_context.require_role("admin")
        
        logger.info(
            f"Request authenticated - User: {security_context.user_id}, "
            f"Level: {security_context.security_level}, Path: {request.url.path}"
        )
        
        return security_context
    
    async def _protected_execution(
        self,
        request: Request,
        security_context: SecurityContext,
        call_next
    ) -> Response:
        """보호된 요청 실행"""
        
        path = request.url.path
        user_id = security_context.user_id or "anonymous"
        
        # Rate Limiter 이름 결정
        if path.startswith("/graphql"):
            rate_limiter_name = "graphql"
            circuit_breaker_name = "graphql_service"
        else:
            rate_limiter_name = "api_default"
            circuit_breaker_name = "api_service"
        
        # 보호 우회 플래그 확인
        bypass_rate_limit = security_context.bypass_rate_limit
        bypass_circuit_breaker = security_context.bypass_circuit_breaker
        
        # Rate Limiting 확인 (우회 플래그가 없는 경우만)
        if self.enable_rate_limiting and not bypass_rate_limit:
            rate_limiter = self.protection_facade.get_rate_limiter(rate_limiter_name)
            rate_violation = await rate_limiter.check_limit(user_id)
            
            if rate_violation:
                raise ProtectionViolation(
                    rate_violation["message"],
                    rate_violation["violation_type"],
                    rate_violation
                )
        
        # Circuit Breaker로 보호된 실행
        if self.enable_circuit_breaking and not bypass_circuit_breaker:
            circuit_breaker = self.protection_facade.get_circuit_breaker(circuit_breaker_name)
            return await circuit_breaker.execute(call_next, request)
        else:
            return await call_next(request)
    
    def _extract_token(self, request: Request) -> Optional[str]:
        """JWT 토큰 추출"""
        
        # Authorization 헤더에서 추출
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:]
        
        # 쿠키에서 추출
        return request.cookies.get("access_token")
    
    def _get_client_ip(self, request: Request) -> str:
        """클라이언트 IP 추출"""
        
        # X-Forwarded-For 헤더 확인 (프록시 환경)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        # X-Real-IP 헤더 확인
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # 직접 연결
        return request.client.host if request.client else "unknown"
    
    def _should_bypass_security(self, path: str) -> bool:
        """보안 우회 경로 확인"""
        return any(path.startswith(bypass_path) for bypass_path in self.bypass_paths)
    
    def _requires_authentication(self, path: str) -> bool:
        """인증 필수 경로 확인"""
        
        public_paths = ["/", "/health", "/metrics", "/docs", "/openapi.json"]
        return not any(path.startswith(public_path) for public_path in public_paths)
    
    def _requires_admin_access(self, path: str) -> bool:
        """관리자 접근 필수 경로 확인"""
        
        admin_paths = ["/admin", "/api/v1/admin", "/management"]
        return any(path.startswith(admin_path) for admin_path in admin_paths)
    
    async def _log_successful_request(
        self,
        request_id: str,
        security_context: SecurityContext,
        path: str,
        execution_time: float
    ):
        """성공적인 요청 로그"""
        
        logger.info(
            f"Request completed - ID: {request_id}, "
            f"User: {security_context.user_id}, "
            f"Path: {path}, "
            f"Time: {execution_time:.3f}s"
        )


# 편의 함수
def create_unified_security_middleware(
    enable_rate_limiting: bool = True,
    enable_circuit_breaking: bool = True,
    bypass_paths: Optional[List[str]] = None
) -> UnifiedSecurityMiddleware:
    """통합 보안 미들웨어 생성"""
    
    def middleware_factory(app):
        return UnifiedSecurityMiddleware(
            app,
            enable_rate_limiting=enable_rate_limiting,
            enable_circuit_breaking=enable_circuit_breaking,
            bypass_paths=bypass_paths
        )
    
    return middleware_factory