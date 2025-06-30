"""
Security Exception Handler - 통합 보안 예외 처리
모든 보안 관련 예외의 단일 처리 지점
"""

import time
import traceback
from typing import Dict, Any, Optional, List, Union
from enum import Enum
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED, 
    HTTP_403_FORBIDDEN,
    HTTP_429_TOO_MANY_REQUESTS,
    HTTP_500_INTERNAL_SERVER_ERROR,
    HTTP_503_SERVICE_UNAVAILABLE
)

from shared.utils.logger import get_logger
from shared.exceptions import OntologyException
from .auth_facade import SecurityViolation
from .protection_facade import ProtectionViolation

logger = get_logger(__name__)


class SecurityErrorCode(str, Enum):
    """표준화된 보안 오류 코드"""
    # 인증 관련
    AUTHENTICATION_REQUIRED = "AUTH_001"
    INVALID_TOKEN = "AUTH_002"
    TOKEN_EXPIRED = "AUTH_003"
    AUTHENTICATION_FAILED = "AUTH_004"
    SESSION_NOT_FOUND = "AUTH_005"
    CONTEXT_MISMATCH = "AUTH_006"
    
    # 인가 관련
    INSUFFICIENT_PRIVILEGES = "AUTHZ_001"
    ROLE_REQUIRED = "AUTHZ_002"
    INSUFFICIENT_SECURITY_LEVEL = "AUTHZ_003"
    PERMISSION_DENIED = "AUTHZ_004"
    
    # Rate Limiting
    RATE_LIMIT_EXCEEDED = "RATE_001"
    QUOTA_EXCEEDED = "RATE_002"
    
    # Circuit Breaker
    CIRCUIT_OPEN = "CIRCUIT_001"
    SERVICE_UNAVAILABLE = "CIRCUIT_002"
    
    # GraphQL Security
    QUERY_TOO_COMPLEX = "GQL_001"
    QUERY_TOO_DEEP = "GQL_002"
    QUERY_TOO_LARGE = "GQL_003"
    INTROSPECTION_DISABLED = "GQL_004"
    
    # 일반 보안
    SECURITY_VIOLATION = "SEC_001"
    SUSPICIOUS_ACTIVITY = "SEC_002"
    IP_BLOCKED = "SEC_003"
    
    # 시스템
    INTERNAL_ERROR = "SYS_001"
    CONFIGURATION_ERROR = "SYS_002"


class SecurityResponse:
    """표준 보안 응답 생성기"""
    
    @staticmethod
    def create_error_response(
        error_code: SecurityErrorCode,
        message: str,
        status_code: int,
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ) -> JSONResponse:
        """표준 보안 오류 응답 생성"""
        
        response_data = {
            "error": {
                "code": error_code,
                "message": message,
                "timestamp": int(time.time())
            }
        }
        
        if request_id:
            response_data["error"]["request_id"] = request_id
        
        # 보안상 민감한 정보는 숨김
        if details and not SecurityResponse._is_production():
            response_data["error"]["details"] = SecurityResponse._sanitize_details(details)
        
        return JSONResponse(
            status_code=status_code,
            content=response_data,
            headers={
                "X-Security-Error": error_code,
                "X-Request-ID": request_id or "unknown"
            }
        )
    
    @staticmethod
    def _is_production() -> bool:
        """프로덕션 환경 확인"""
        import os
        return os.getenv("ENVIRONMENT", "development").lower() == "production"
    
    @staticmethod
    def _sanitize_details(details: Dict[str, Any]) -> Dict[str, Any]:
        """민감한 정보 제거"""
        sanitized = {}
        
        # 허용된 필드만 포함
        allowed_fields = {
            "limit", "window", "retry_after", "current_requests",
            "required_role", "required_level", "circuit_name",
            "violation_type", "field", "depth", "complexity"
        }
        
        for key, value in details.items():
            if key in allowed_fields:
                sanitized[key] = value
            elif key.endswith("_count") or key.endswith("_time"):
                sanitized[key] = value
        
        return sanitized


class SecurityExceptionHandler:
    """통합 보안 예외 처리기"""
    
    def __init__(self):
        self._error_mappings = self._build_error_mappings()
        self._audit_logger = None
        self._setup_audit_logger()
    
    def _setup_audit_logger(self):
        """감사 로거 설정"""
        try:
            from shared.audit.unified_audit_logger import get_unified_audit_logger
            self._audit_logger = get_unified_audit_logger()
        except Exception as e:
            logger.warning(f"Failed to setup audit logger: {e}")
    
    def _build_error_mappings(self) -> Dict[str, tuple]:
        """오류 유형별 매핑 생성 (error_code, status_code)"""
        return {
            # Authentication
            "AUTHENTICATION_REQUIRED": (SecurityErrorCode.AUTHENTICATION_REQUIRED, HTTP_401_UNAUTHORIZED),
            "INVALID_TOKEN": (SecurityErrorCode.INVALID_TOKEN, HTTP_401_UNAUTHORIZED),
            "TOKEN_EXPIRED": (SecurityErrorCode.TOKEN_EXPIRED, HTTP_401_UNAUTHORIZED),
            "AUTHENTICATION_FAILED": (SecurityErrorCode.AUTHENTICATION_FAILED, HTTP_401_UNAUTHORIZED),
            "SESSION_NOT_FOUND": (SecurityErrorCode.SESSION_NOT_FOUND, HTTP_401_UNAUTHORIZED),
            "CONTEXT_MISMATCH": (SecurityErrorCode.CONTEXT_MISMATCH, HTTP_401_UNAUTHORIZED),
            
            # Authorization
            "INSUFFICIENT_PRIVILEGES": (SecurityErrorCode.INSUFFICIENT_PRIVILEGES, HTTP_403_FORBIDDEN),
            "ROLE_REQUIRED": (SecurityErrorCode.ROLE_REQUIRED, HTTP_403_FORBIDDEN),
            "INSUFFICIENT_SECURITY_LEVEL": (SecurityErrorCode.INSUFFICIENT_SECURITY_LEVEL, HTTP_403_FORBIDDEN),
            "PERMISSION_DENIED": (SecurityErrorCode.PERMISSION_DENIED, HTTP_403_FORBIDDEN),
            
            # Rate Limiting
            "RATE_LIMIT_EXCEEDED": (SecurityErrorCode.RATE_LIMIT_EXCEEDED, HTTP_429_TOO_MANY_REQUESTS),
            "QUOTA_EXCEEDED": (SecurityErrorCode.QUOTA_EXCEEDED, HTTP_429_TOO_MANY_REQUESTS),
            
            # Circuit Breaker
            "CIRCUIT_OPEN": (SecurityErrorCode.CIRCUIT_OPEN, HTTP_503_SERVICE_UNAVAILABLE),
            "SERVICE_UNAVAILABLE": (SecurityErrorCode.SERVICE_UNAVAILABLE, HTTP_503_SERVICE_UNAVAILABLE),
            
            # GraphQL
            "COMPLEXITY_EXCEEDED": (SecurityErrorCode.QUERY_TOO_COMPLEX, HTTP_400_BAD_REQUEST),
            "DEPTH_EXCEEDED": (SecurityErrorCode.QUERY_TOO_DEEP, HTTP_400_BAD_REQUEST),
            "QUERY_SIZE_EXCEEDED": (SecurityErrorCode.QUERY_TOO_LARGE, HTTP_400_BAD_REQUEST),
            "INTROSPECTION_DISABLED": (SecurityErrorCode.INTROSPECTION_DISABLED, HTTP_403_FORBIDDEN),
        }
    
    async def handle_security_violation(
        self,
        request: Request,
        exc: SecurityViolation
    ) -> JSONResponse:
        """보안 위반 예외 처리"""
        
        request_id = getattr(request.state, "request_id", "unknown")
        client_ip = request.client.host if request.client else "unknown"
        
        # 오류 매핑 조회
        error_code, status_code = self._error_mappings.get(
            exc.violation_type,
            (SecurityErrorCode.SECURITY_VIOLATION, HTTP_403_FORBIDDEN)
        )
        
        # 감사 로그 기록
        await self._log_security_event(
            event_type="security_violation",
            request_id=request_id,
            client_ip=client_ip,
            violation_type=exc.violation_type,
            message=str(exc),
            context=exc.context
        )
        
        logger.warning(
            f"Security violation: {exc.violation_type} - {str(exc)} "
            f"[Request: {request_id}, IP: {client_ip}]"
        )
        
        return SecurityResponse.create_error_response(
            error_code=error_code,
            message=str(exc),
            status_code=status_code,
            details=exc.context,
            request_id=request_id
        )
    
    async def handle_protection_violation(
        self,
        request: Request,
        exc: ProtectionViolation
    ) -> JSONResponse:
        """보호 계층 위반 예외 처리"""
        
        request_id = getattr(request.state, "request_id", "unknown")
        client_ip = request.client.host if request.client else "unknown"
        
        # 오류 매핑 조회
        error_code, status_code = self._error_mappings.get(
            exc.violation_type,
            (SecurityErrorCode.SERVICE_UNAVAILABLE, HTTP_503_SERVICE_UNAVAILABLE)
        )
        
        # Rate Limit의 경우 추가 헤더 설정
        headers = {}
        if exc.violation_type == "RATE_LIMIT_EXCEEDED" and "retry_after" in exc.context:
            headers["Retry-After"] = str(exc.context["retry_after"])
        
        # 감사 로그 기록
        await self._log_security_event(
            event_type="protection_violation",
            request_id=request_id,
            client_ip=client_ip,
            violation_type=exc.violation_type,
            message=str(exc),
            context=exc.context
        )
        
        logger.warning(
            f"Protection violation: {exc.violation_type} - {str(exc)} "
            f"[Request: {request_id}, IP: {client_ip}]"
        )
        
        response = SecurityResponse.create_error_response(
            error_code=error_code,
            message=str(exc),
            status_code=status_code,
            details=exc.context,
            request_id=request_id
        )
        
        # 추가 헤더 설정
        for key, value in headers.items():
            response.headers[key] = value
        
        return response
    
    async def handle_graphql_security_violation(
        self,
        violations: List[Dict[str, Any]],
        request_id: str = "unknown"
    ) -> Dict[str, Any]:
        """GraphQL 보안 위반 처리"""
        
        # 감사 로그 기록
        await self._log_security_event(
            event_type="graphql_security_violation",
            request_id=request_id,
            violation_type="multiple",
            message=f"GraphQL security violations: {[v['type'] for v in violations]}",
            context={"violations": violations}
        )
        
        # GraphQL 형식의 오류 응답 생성
        errors = []
        for violation in violations:
            error_code, _ = self._error_mappings.get(
                violation["type"],
                (SecurityErrorCode.SECURITY_VIOLATION, HTTP_400_BAD_REQUEST)
            )
            
            errors.append({
                "message": violation["message"],
                "extensions": {
                    "code": error_code,
                    "violation_type": violation["type"],
                    **{k: v for k, v in violation.items() if k not in ["type", "message"]}
                }
            })
        
        return {"errors": errors}
    
    async def handle_general_exception(
        self,
        request: Request,
        exc: Exception
    ) -> JSONResponse:
        """일반 예외 처리 (보안 관련이 아닌 경우)"""
        
        request_id = getattr(request.state, "request_id", "unknown")
        client_ip = request.client.host if request.client else "unknown"
        
        # 스택 트레이스 수집 (개발 환경에서만)
        stack_trace = None
        if not SecurityResponse._is_production():
            stack_trace = traceback.format_exc()
        
        # 내부 오류 로그
        logger.error(
            f"Unhandled exception: {type(exc).__name__}: {str(exc)} "
            f"[Request: {request_id}, IP: {client_ip}]",
            exc_info=True
        )
        
        # 감사 로그 기록
        await self._log_security_event(
            event_type="internal_error",
            request_id=request_id,
            client_ip=client_ip,
            violation_type="INTERNAL_ERROR",
            message=str(exc),
            context={"exception_type": type(exc).__name__}
        )
        
        # 사용자에게는 일반적인 오류만 표시
        return SecurityResponse.create_error_response(
            error_code=SecurityErrorCode.INTERNAL_ERROR,
            message="An internal error occurred",
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            details={"stack_trace": stack_trace} if stack_trace else None,
            request_id=request_id
        )
    
    async def _log_security_event(
        self,
        event_type: str,
        request_id: str,
        client_ip: str,
        violation_type: str,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        """보안 이벤트 감사 로그 기록"""
        if not self._audit_logger:
            return
        
        try:
            await self._audit_logger.log_event(
                user_id="system",
                action=f"security.{event_type}",
                resource=f"request:{request_id}",
                details={
                    "client_ip": client_ip,
                    "violation_type": violation_type,
                    "message": message,
                    "context": context or {},
                    "severity": self._determine_severity(violation_type)
                }
            )
        except Exception as e:
            logger.error(f"Failed to log security event: {e}")
    
    def _determine_severity(self, violation_type: str) -> str:
        """위반 유형별 심각도 결정"""
        high_severity = {
            "AUTHENTICATION_FAILED", "CONTEXT_MISMATCH", "SUSPICIOUS_ACTIVITY",
            "INTERNAL_ERROR"
        }
        
        medium_severity = {
            "INSUFFICIENT_PRIVILEGES", "ROLE_REQUIRED", "CIRCUIT_OPEN"
        }
        
        if violation_type in high_severity:
            return "high"
        elif violation_type in medium_severity:
            return "medium"
        else:
            return "low"


# 글로벌 인스턴스
_security_exception_handler_instance: Optional[SecurityExceptionHandler] = None


def get_security_exception_handler() -> SecurityExceptionHandler:
    """글로벌 SecurityExceptionHandler 인스턴스 반환"""
    global _security_exception_handler_instance
    if _security_exception_handler_instance is None:
        _security_exception_handler_instance = SecurityExceptionHandler()
    return _security_exception_handler_instance


# FastAPI 예외 핸들러 등록용 함수들
async def security_violation_handler(request: Request, exc: SecurityViolation) -> JSONResponse:
    """FastAPI용 보안 위반 핸들러"""
    handler = get_security_exception_handler()
    return await handler.handle_security_violation(request, exc)


async def protection_violation_handler(request: Request, exc: ProtectionViolation) -> JSONResponse:
    """FastAPI용 보호 위반 핸들러"""
    handler = get_security_exception_handler()
    return await handler.handle_protection_violation(request, exc)


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """FastAPI용 일반 예외 핸들러"""
    handler = get_security_exception_handler()
    return await handler.handle_general_exception(request, exc)