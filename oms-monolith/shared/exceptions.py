"""
통합 예외 정의 - 엔터프라이즈 레벨 예외 관리
모든 예외를 중앙에서 관리하여 일관성 있는 오류 처리 제공
"""

from typing import Optional, Dict, Any
from fastapi import HTTPException as FastAPIHTTPException


# === 기본 예외 ===

class OntologyException(Exception):
    """
    Ontology Management System 기본 예외
    모든 OMS 예외의 기본 클래스
    """
    def __init__(self, message: str, code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__
        self.details = details or {}


# === 비즈니스 로직 예외 ===

class ValidationError(OntologyException):
    """검증 오류 - 입력 데이터나 상태가 유효하지 않을 때"""
    pass


class ConflictError(OntologyException):
    """충돌 오류 - 리소스 상태 충돌이나 동시성 문제"""
    pass


class NotFoundError(OntologyException):
    """리소스를 찾을 수 없음"""
    pass


class DuplicateError(OntologyException):
    """중복 오류 - 이미 존재하는 리소스"""
    pass


class InvalidStateError(OntologyException):
    """잘못된 상태 - 요청된 작업을 수행할 수 없는 상태"""
    pass


# === 보안/인증 예외 ===

class SecurityException(OntologyException):
    """보안 관련 예외의 기본 클래스"""
    pass


class AuthenticationError(SecurityException):
    """인증 실패 - 사용자 인증 불가"""
    pass


class AuthorizationError(SecurityException):
    """인가 실패 - 권한 없음"""
    pass


class PermissionError(SecurityException):
    """권한 오류 - 특정 작업에 대한 권한 없음"""
    pass


class SecurityViolation(SecurityException):
    """보안 위반 - 보안 정책 위반"""
    def __init__(
        self,
        message: str,
        violation_type: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, code=violation_type, details=context)
        self.violation_type = violation_type
        self.context = context or {}


class ProtectionViolation(SecurityException):
    """보호 계층 위반 - Rate limiting, Circuit breaker 등"""
    def __init__(
        self,
        message: str,
        violation_type: str,
        retry_after: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, code=violation_type, details=context)
        self.violation_type = violation_type
        self.retry_after = retry_after
        self.context = context or {}


# === 생명안전 등급 인증 예외 ===

class LifeCriticalAuthenticationError(SecurityException):
    """생명안전 등급 인증 오류의 기본 클래스"""
    pass


class SecurityConfigurationError(LifeCriticalAuthenticationError):
    """보안 설정 오류 - 잘못된 보안 설정"""
    pass


class AuthenticationServiceError(LifeCriticalAuthenticationError):
    """인증 서비스 오류 - 인증 서비스 장애"""
    pass


# === 서비스 통합 예외 ===

class ServiceException(OntologyException):
    """외부 서비스 관련 예외의 기본 클래스"""
    pass


class ServiceUnavailableError(ServiceException):
    """서비스 사용 불가 - 서비스 다운 또는 Circuit breaker open"""
    pass


class ServiceTimeoutError(ServiceException):
    """서비스 타임아웃 - 응답 시간 초과"""
    pass


class IAMServiceError(ServiceException):
    """IAM 서비스 오류"""
    pass


class UserServiceError(ServiceException):
    """사용자 서비스 오류"""
    pass


class AuditServiceError(ServiceException):
    """감사 서비스 오류"""
    pass


# === 인프라/시스템 예외 ===

class InfrastructureException(OntologyException):
    """인프라 관련 예외의 기본 클래스"""
    pass


class DatabaseConnectionError(InfrastructureException):
    """데이터베이스 연결 오류"""
    pass


class CacheError(InfrastructureException):
    """캐시 오류"""
    pass


class MessageQueueError(InfrastructureException):
    """메시지 큐 오류"""
    pass


class ConfigurationError(InfrastructureException):
    """설정 오류 - 잘못된 설정이나 누락된 설정"""
    pass


# === Circuit Breaker/Resilience 예외 ===

class ResilienceException(InfrastructureException):
    """복원력 패턴 관련 예외"""
    pass


class CircuitBreakerOpenError(ResilienceException):
    """Circuit breaker가 열려있음"""
    def __init__(self, message: str = "Circuit breaker is open", retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class BulkheadFullError(ResilienceException):
    """Bulkhead가 가득 참 - 동시 실행 한계 도달"""
    pass


class RetryBudgetExhaustedError(ResilienceException):
    """재시도 예산 소진"""
    pass


class RateLimitExceededError(ResilienceException):
    """Rate limit 초과"""
    def __init__(self, message: str = "Rate limit exceeded", retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


# === 동시성/트랜잭션 예외 ===

class ConcurrencyException(OntologyException):
    """동시성 관련 예외"""
    pass


class LockConflictError(ConcurrencyException):
    """잠금 충돌 - 리소스가 이미 잠김"""
    pass


class InvalidStateTransitionError(ConcurrencyException):
    """잘못된 상태 전환"""
    pass


class OptimisticConcurrencyError(ConcurrencyException):
    """낙관적 동시성 오류 - 버전 충돌"""
    pass


# === HTTP 특화 예외 ===

class HTTPException(FastAPIHTTPException):
    """
    FastAPI HTTPException 래퍼
    OMS 예외 시스템과 통합
    """
    def __init__(
        self,
        status_code: int,
        detail: Any = None,
        headers: Optional[Dict[str, Any]] = None,
        code: Optional[str] = None
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.code = code


class SchemaFreezeError(HTTPException):
    """스키마 동결 위반"""
    def __init__(self, detail: str = "Schema is frozen"):
        super().__init__(status_code=423, detail=detail, code="SCHEMA_FROZEN")


# === 예외 변환 유틸리티 ===

def to_http_exception(exc: OntologyException) -> HTTPException:
    """
    OntologyException을 HTTPException으로 변환
    
    상태 코드 매핑:
    - ValidationError -> 400
    - AuthenticationError -> 401
    - AuthorizationError, PermissionError -> 403
    - NotFoundError -> 404
    - ConflictError, DuplicateError -> 409
    - RateLimitExceededError -> 429
    - ServiceUnavailableError -> 503
    - 기타 -> 500
    """
    status_code_map = {
        ValidationError: 400,
        AuthenticationError: 401,
        AuthorizationError: 403,
        PermissionError: 403,
        NotFoundError: 404,
        ConflictError: 409,
        DuplicateError: 409,
        RateLimitExceededError: 429,
        ServiceUnavailableError: 503,
        CircuitBreakerOpenError: 503,
    }
    
    status_code = 500
    for exc_type, code in status_code_map.items():
        if isinstance(exc, exc_type):
            status_code = code
            break
    
    headers = {}
    if hasattr(exc, 'retry_after') and exc.retry_after:
        headers['Retry-After'] = str(exc.retry_after)
    
    return HTTPException(
        status_code=status_code,
        detail={
            "message": str(exc),
            "code": exc.code if hasattr(exc, 'code') else exc.__class__.__name__,
            "details": exc.details if hasattr(exc, 'details') else {}
        },
        headers=headers if headers else None
    )