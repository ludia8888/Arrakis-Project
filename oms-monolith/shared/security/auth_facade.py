"""
Authentication Facade - Single Source of Truth for Authentication
모든 인증 로직을 통합하여 우회 불가능한 단일 진입점 제공
"""

import asyncio
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from pydantic import BaseModel

from core.auth import UserContext
from shared.utils.logger import get_logger
from shared.exceptions import OntologyException

logger = get_logger(__name__)


class AuthenticationState(str, Enum):
    """인증 상태"""
    AUTHENTICATED = "authenticated"
    UNAUTHENTICATED = "unauthenticated" 
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    RATE_LIMITED = "rate_limited"


class SecurityLevel(str, Enum):
    """보안 수준"""
    PUBLIC = "public"        # 인증 불필요
    AUTHENTICATED = "authenticated"  # 기본 인증 필요
    PRIVILEGED = "privileged"       # 특권 역할 필요
    ADMIN = "admin"          # 관리자 전용
    LIFE_CRITICAL = "life_critical"  # 생명안전 등급


@dataclass
class SecurityContext:
    """통합 보안 컨텍스트 - 모든 보안 정보의 단일 소스"""
    user_context: Optional[UserContext] = None
    authentication_state: AuthenticationState = AuthenticationState.UNAUTHENTICATED
    security_level: SecurityLevel = SecurityLevel.PUBLIC
    
    # 요청 메타데이터
    request_id: str = ""
    client_ip: str = ""
    user_agent: str = ""
    timestamp: float = field(default_factory=time.time)
    
    # 보안 플래그
    is_verified: bool = False
    bypass_rate_limit: bool = False
    bypass_circuit_breaker: bool = False
    
    # 감사 정보
    audit_metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_authenticated(self) -> bool:
        """인증된 상태인지 확인"""
        return (
            self.user_context is not None and 
            self.authentication_state == AuthenticationState.AUTHENTICATED and
            self.is_verified
        )
    
    @property
    def user_id(self) -> Optional[str]:
        """사용자 ID 반환"""
        return self.user_context.user_id if self.user_context else None
    
    @property
    def roles(self) -> List[str]:
        """사용자 역할 반환"""
        return self.user_context.roles if self.user_context else []
    
    def require_authentication(self) -> None:
        """인증 필수 확인 - 인증되지 않으면 예외 발생"""
        if not self.is_authenticated:
            raise SecurityViolation(
                "Authentication required",
                violation_type="AUTHENTICATION_REQUIRED",
                context={"state": self.authentication_state}
            )
    
    def require_role(self, required_role: str) -> None:
        """특정 역할 필수 확인"""
        self.require_authentication()
        if not self.user_context.has_role(required_role):
            raise SecurityViolation(
                f"Role '{required_role}' required",
                violation_type="INSUFFICIENT_PRIVILEGES",
                context={"required_role": required_role, "user_roles": self.roles}
            )
    
    def require_any_role(self, required_roles: List[str]) -> None:
        """여러 역할 중 하나 필수 확인"""
        self.require_authentication()
        if not self.user_context.has_any_role(required_roles):
            raise SecurityViolation(
                f"One of roles {required_roles} required",
                violation_type="INSUFFICIENT_PRIVILEGES", 
                context={"required_roles": required_roles, "user_roles": self.roles}
            )
    
    def require_security_level(self, required_level: SecurityLevel) -> None:
        """보안 수준 확인"""
        level_hierarchy = {
            SecurityLevel.PUBLIC: 0,
            SecurityLevel.AUTHENTICATED: 1,
            SecurityLevel.PRIVILEGED: 2,
            SecurityLevel.ADMIN: 3,
            SecurityLevel.LIFE_CRITICAL: 4
        }
        
        current_level = level_hierarchy[self.security_level]
        required_level_value = level_hierarchy[required_level]
        
        if current_level < required_level_value:
            raise SecurityViolation(
                f"Security level '{required_level}' required, current: '{self.security_level}'",
                violation_type="INSUFFICIENT_SECURITY_LEVEL",
                context={
                    "required_level": required_level,
                    "current_level": self.security_level
                }
            )


class SecurityViolation(OntologyException):
    """보안 위반 예외"""
    
    def __init__(
        self,
        message: str,
        violation_type: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.violation_type = violation_type
        self.context = context or {}
        self.timestamp = time.time()


class UserContextValidator:
    """사용자 컨텍스트 검증기 - 토큰 파싱과 검증을 담당"""
    
    def __init__(self):
        self._cached_validations: Dict[str, tuple] = {}
        self._cache_ttl = 300  # 5분 캐시
    
    async def validate_token(self, token: str) -> Optional[UserContext]:
        """JWT 토큰 검증 및 UserContext 생성"""
        if not token:
            return None
        
        # 캐시 확인
        cache_key = f"token:{hash(token)}"
        if cache_key in self._cached_validations:
            cached_context, cached_time = self._cached_validations[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return cached_context
        
        try:
            # 실제 토큰 검증 로직 (기존 middleware/auth_secure.py 로직 활용)
            from middleware.auth_secure import LifeCriticalAuthMiddleware
            
            # 임시 인스턴스로 토큰 검증
            auth_middleware = LifeCriticalAuthMiddleware()
            user_context = await auth_middleware._validate_token_internal(token)
            
            # 캐시 저장
            if user_context:
                self._cached_validations[cache_key] = (user_context, time.time())
            
            return user_context
            
        except Exception as e:
            logger.warning(f"Token validation failed: {e}")
            return None
    
    def determine_security_level(self, user_context: UserContext) -> SecurityLevel:
        """사용자 역할에 따른 보안 수준 결정"""
        if not user_context:
            return SecurityLevel.PUBLIC
        
        if user_context.has_role("life_critical_admin"):
            return SecurityLevel.LIFE_CRITICAL
        elif user_context.is_admin:
            return SecurityLevel.ADMIN
        elif user_context.has_any_role(["developer", "reviewer", "operator"]):
            return SecurityLevel.PRIVILEGED
        else:
            return SecurityLevel.AUTHENTICATED


class AuthenticationFacade:
    """
    인증 Facade - 모든 인증 관련 작업의 단일 진입점
    
    이 클래스를 통해서만 인증을 수행하여 우회 불가능한 보안 구조 구축
    """
    
    def __init__(self):
        self.validator = UserContextValidator()
        self._active_sessions: Dict[str, SecurityContext] = {}
    
    async def authenticate_request(
        self,
        token: Optional[str] = None,
        request_id: str = "",
        client_ip: str = "",
        user_agent: str = "",
        bypass_flags: Optional[Dict[str, bool]] = None
    ) -> SecurityContext:
        """
        요청 인증 및 보안 컨텍스트 생성
        
        Args:
            token: JWT 토큰
            request_id: 요청 식별자
            client_ip: 클라이언트 IP
            user_agent: User-Agent 헤더
            bypass_flags: 보안 우회 플래그 (테스트용)
        
        Returns:
            SecurityContext: 검증된 보안 컨텍스트
        """
        bypass_flags = bypass_flags or {}
        
        # 토큰 검증
        user_context = None
        auth_state = AuthenticationState.UNAUTHENTICATED
        
        if token:
            user_context = await self.validator.validate_token(token)
            if user_context:
                auth_state = AuthenticationState.AUTHENTICATED
            else:
                auth_state = AuthenticationState.EXPIRED
        
        # 보안 수준 결정
        security_level = self.validator.determine_security_level(user_context)
        
        # 보안 컨텍스트 생성
        security_context = SecurityContext(
            user_context=user_context,
            authentication_state=auth_state,
            security_level=security_level,
            request_id=request_id,
            client_ip=client_ip,
            user_agent=user_agent,
            is_verified=user_context is not None,
            bypass_rate_limit=bypass_flags.get("rate_limit", False),
            bypass_circuit_breaker=bypass_flags.get("circuit_breaker", False),
            audit_metadata={
                "auth_method": "jwt_token",
                "security_level": security_level,
                "client_info": {
                    "ip": client_ip,
                    "user_agent": user_agent
                }
            }
        )
        
        # 세션 등록
        if request_id:
            self._active_sessions[request_id] = security_context
        
        logger.info(
            f"Authentication completed - User: {security_context.user_id}, "
            f"State: {auth_state}, Level: {security_level}"
        )
        
        return security_context
    
    def get_session(self, request_id: str) -> Optional[SecurityContext]:
        """세션 조회"""
        return self._active_sessions.get(request_id)
    
    def invalidate_session(self, request_id: str) -> None:
        """세션 무효화"""
        self._active_sessions.pop(request_id, None)
    
    async def verify_graphql_context(
        self,
        query: str,
        user_context: Any,  # GraphQL에서 전달받은 컨텍스트
        request_id: str
    ) -> SecurityContext:
        """
        GraphQL 요청의 보안 컨텍스트 검증
        
        GraphQL 계층에서 독립적으로 user_context를 생성하지 못하도록 차단
        반드시 이미 인증된 세션의 컨텍스트만 사용
        """
        # 기존 세션에서 보안 컨텍스트 조회
        security_context = self.get_session(request_id)
        
        if not security_context:
            raise SecurityViolation(
                "No authenticated session found for GraphQL request",
                violation_type="SESSION_NOT_FOUND",
                context={"request_id": request_id}
            )
        
        # GraphQL에서 전달받은 user_context와 세션의 컨텍스트 일치 확인
        if user_context and security_context.user_context:
            if user_context.user_id != security_context.user_context.user_id:
                raise SecurityViolation(
                    "User context mismatch between session and GraphQL request",
                    violation_type="CONTEXT_MISMATCH",
                    context={
                        "session_user": security_context.user_context.user_id,
                        "graphql_user": getattr(user_context, "user_id", None)
                    }
                )
        
        logger.info(f"GraphQL context verified for user: {security_context.user_id}")
        return security_context


# 글로벌 인스턴스
_auth_facade_instance: Optional[AuthenticationFacade] = None


def get_auth_facade() -> AuthenticationFacade:
    """글로벌 AuthenticationFacade 인스턴스 반환"""
    global _auth_facade_instance
    if _auth_facade_instance is None:
        _auth_facade_instance = AuthenticationFacade()
    return _auth_facade_instance


# 편의 함수들
async def authenticate_request(
    token: Optional[str] = None,
    request_id: str = "",
    client_ip: str = "",
    user_agent: str = ""
) -> SecurityContext:
    """요청 인증 편의 함수"""
    facade = get_auth_facade()
    return await facade.authenticate_request(token, request_id, client_ip, user_agent)


def require_authentication(security_context: SecurityContext) -> None:
    """인증 필수 확인 편의 함수"""
    security_context.require_authentication()


def require_role(security_context: SecurityContext, role: str) -> None:
    """역할 확인 편의 함수"""
    security_context.require_role(role)