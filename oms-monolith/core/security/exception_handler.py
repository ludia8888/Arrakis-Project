"""
생명과 개인정보를 다루는 시스템을 위한 완벽한 예외 처리

이 모듈은 어떠한 민감한 정보도 외부로 유출되지 않도록 보장합니다.
모든 에러는 안전한 형태로 변환되어 반환됩니다.
"""
import logging
import uuid
from typing import Any, Dict, Optional
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from starlette import status
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


# 에러 코드 매핑 - 절대 상세 정보를 노출하지 않음
ERROR_CODES = {
    # Validation errors
    "string_pattern_mismatch": "INVALID_FORMAT",
    "missing": "REQUIRED_FIELD",
    "value_error": "INVALID_VALUE",
    "type_error": "INVALID_TYPE",
    "too_short": "TOO_SHORT",
    "too_long": "TOO_LONG",
    
    # Security errors
    "sql_injection": "SECURITY_VIOLATION",
    "xss_attempt": "SECURITY_VIOLATION",
    "path_traversal": "SECURITY_VIOLATION",
    "command_injection": "SECURITY_VIOLATION",
    
    # Database errors
    "DocumentIdAlreadyExists": "ENTITY_EXISTS",
    "DocumentNotFound": "ENTITY_NOT_FOUND",
    "DatabaseTimeout": "SERVICE_UNAVAILABLE",
    "ConnectionError": "SERVICE_UNAVAILABLE",
}


def sanitize_error_detail(detail: Any) -> str:
    """
    생명 중요 시스템용 완전한 에러 정보 정제
    ZERO INFORMATION DISCLOSURE 정책
    """
    if not isinstance(detail, str):
        detail = str(detail)
    
    # 🔒 CRITICAL: 완전한 정보 제거
    import re
    
    # HTML 태그 완전 제거
    detail = re.sub(r'<[^>]*>', '[REMOVED]', detail)
    detail = re.sub(r'&[a-zA-Z0-9#]+;', '[REMOVED]', detail)
    
    # 스크립트 패턴 완전 제거  
    detail = re.sub(r'(?i)(script|javascript|vbscript)', '[REMOVED]', detail)
    detail = re.sub(r'(?i)(onload|onerror|onclick|onmouseover)', '[REMOVED]', detail)
    
    # JNDI/LDAP 패턴 완전 제거
    detail = re.sub(r'\$\{[^}]*\}', '[REMOVED]', detail)
    detail = re.sub(r'(?i)(jndi|ldap|rmi|dns):', '[REMOVED]', detail)
    
    # SQL 패턴 완전 제거
    detail = re.sub(r'(?i)(select|insert|update|delete|drop|create|alter|truncate)', '[REMOVED]', detail)
    detail = re.sub(r'(?i)(from|where|join|union|having|group|order)', '[REMOVED]', detail)
    
    # Command injection 패턴 제거
    detail = re.sub(r'[;&|`$(){}[\]\\]', '[REMOVED]', detail)
    detail = re.sub(r'(?i)(rm|del|format|cat|type|wget|curl)', '[REMOVED]', detail)
    
    # Path traversal 패턴 제거
    detail = re.sub(r'\.\.[\\/]', '[REMOVED]', detail)
    detail = re.sub(r'%2e%2e', '[REMOVED]', detail)
    
    # 모든 기술적 세부사항 제거
    detail = re.sub(r'\^[^$]+\$', '[REMOVED]', detail)
    detail = re.sub(r'[/\\][\w/\\.-]+\.(py|json|yml|yaml|xml|js|html)', '[REMOVED]', detail)
    detail = re.sub(r'[A-Za-z]:[\\\/][^\\\/\s]+', '[REMOVED]', detail)
    detail = re.sub(r'File\s+"[^"]+",\s+line\s+\d+', '[REMOVED]', detail)
    detail = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '[REMOVED]', detail)
    detail = re.sub(r':\d{2,5}\b', '[REMOVED]', detail)
    detail = re.sub(r'https?://[^\s]+', '[REMOVED]', detail)
    
    # 특수 문자 제거
    detail = re.sub(r'[<>{}[\]()&%#@!*+]', '[REMOVED]', detail)
    
    # 연속된 [REMOVED] 정리
    detail = re.sub(r'(\[REMOVED\]\s*){2,}', '[REMOVED] ', detail)
    
    # 최종 안전 처리 - 길이 제한
    if len(detail) > 30:
        return "Request blocked"
    
    return detail.strip() or "Request blocked"


async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Pydantic validation 에러를 안전하게 처리
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    
    # 내부 로깅 - 상세 정보 기록
    logger.error(f"Validation error for request {request_id}: {exc.errors()}")
    
    # 외부 응답 - 최소 정보만
    errors = []
    for error in exc.errors()[:3]:  # 최대 3개만
        field_path = ".".join(str(loc) for loc in error.get("loc", []))
        error_type = error.get("type", "validation_error")
        
        # 에러 코드 매핑
        safe_code = ERROR_CODES.get(error_type, "VALIDATION_ERROR")
        
        errors.append({
            "field": field_path,
            "code": safe_code
        })
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "Validation failed",
            "request_id": request_id,
            "errors": errors
        }
    )


async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
    """
    HTTP 예외를 안전하게 처리
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    
    # 내부 로깅
    logger.error(f"HTTP exception for request {request_id}: {exc.detail}")
    
    # 상세 정보 정제
    safe_detail = sanitize_error_detail(exc.detail) if isinstance(exc.detail, str) else "Error occurred"
    
    # 보안 위협 감지 시 일반화
    if any(keyword in str(exc.detail).lower() for keyword in ['drop', 'script', 'injection', 'traversal', 'security threat', 'security violation']):
        safe_detail = "Invalid request"
    
    # DocumentIdAlreadyExists는 정상적인 비즈니스 오류이므로 구체적으로 처리
    if 'DocumentIdAlreadyExists' in str(exc.detail):
        safe_detail = "Entity already exists"
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": safe_detail,
            "request_id": request_id
        }
    )


async def handle_generic_exception(request: Request, exc: Exception) -> JSONResponse:
    """
    예상치 못한 예외를 안전하게 처리
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    
    # 내부 로깅 - 전체 스택 트레이스
    logger.exception(f"Unhandled exception for request {request_id}: {exc}")
    
    # 외부 응답 - 아무 정보도 노출하지 않음
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "request_id": request_id
        }
    )


def register_exception_handlers(app):
    """
    모든 예외 핸들러를 앱에 등록
    """
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(ValidationError, handle_validation_error)
    app.add_exception_handler(HTTPException, handle_http_exception)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(Exception, handle_generic_exception)
    
    logger.info("✅ Secure exception handlers registered")