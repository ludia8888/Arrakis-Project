"""
Enterprise Validation Middleware
Production-grade middleware that integrates with the enterprise validation service
to provide comprehensive validation for all OMS endpoints.
"""
import json
import logging
import time
import uuid
from typing import Dict, Any, Optional, Set, Tuple
from urllib.parse import urlparse

from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.validation.enterprise_service import (
    EnterpriseValidationService, ValidationLevel, ValidationScope,
    get_enterprise_validation_service
)
from shared.monitoring.metrics import metrics_collector


logger = logging.getLogger(__name__)


class EnterpriseValidationMiddleware(BaseHTTPMiddleware):
    """
    Enterprise-grade validation middleware for all OMS endpoints
    
    Features:
    - Validates all incoming requests against entity schemas
    - Sanitizes input to prevent security threats
    - Provides consistent error responses
    - Tracks validation metrics
    - Supports configurable validation levels per endpoint
    - Prevents information disclosure
    """
    
    # Endpoint to entity type mapping
    ENDPOINT_ENTITY_MAP = {
        "/object-types": "object_type",
        "/properties": "property",
        "/shared-properties": "property",
        "/link-types": "link_type",
        "/action-types": "action_type",
        "/interfaces": "interface",
        "/semantic-types": "semantic_type",
        "/struct-types": "struct_type",
    }
    
    # Endpoints that require strict validation
    STRICT_VALIDATION_ENDPOINTS = {
        "/api/v1/schemas",
        "/api/v1/data",
        "/api/graphql"
    }
    
    # Endpoints excluded from validation
    EXCLUDED_ENDPOINTS = {
        "/health",
        "/metrics",
        "/docs",
        "/openapi.json",
        "/favicon.ico"
    }
    
    # Method to operation mapping
    METHOD_OPERATION_MAP = {
        "POST": "create",
        "PUT": "update",
        "PATCH": "update",
        "DELETE": "delete",
        "GET": "read"
    }
    
    def __init__(
        self,
        app,
        validation_service: Optional[EnterpriseValidationService] = None,
        default_level: ValidationLevel = ValidationLevel.STANDARD,
        enable_response_validation: bool = True,
        enable_metrics: bool = True,
        log_validation_errors: bool = True,
        prevent_info_disclosure: bool = True
    ):
        """
        Initialize enterprise validation middleware
        
        Args:
            app: FastAPI application
            validation_service: Enterprise validation service instance
            default_level: Default validation level
            enable_response_validation: Whether to validate responses
            enable_metrics: Whether to collect metrics
            log_validation_errors: Whether to log validation errors
            prevent_info_disclosure: Whether to prevent information disclosure
        """
        super().__init__(app)
        
        self.validation_service = validation_service
        self.app = app  # Store app reference to access app.state
        self.default_level = default_level
        self.enable_response_validation = enable_response_validation
        self.enable_metrics = enable_metrics
        self.log_validation_errors = log_validation_errors
        self.prevent_info_disclosure = prevent_info_disclosure
        
        # Validation level overrides per endpoint pattern
        self.endpoint_validation_levels = {
            "/api/v1/schemas": ValidationLevel.STRICT,
            "/api/v1/data": ValidationLevel.STRICT,
            "/api/graphql": ValidationLevel.PARANOID,
            "/api/public": ValidationLevel.STANDARD
        }
        
        logger.info(f"Enterprise validation middleware initialized with default level: {default_level}")
    
    async def dispatch(self, request: Request, call_next):
        """Process request with enterprise validation"""
        
        # Skip validation for excluded endpoints
        if self._should_skip_validation(request):
            return await call_next(request)
        
        # Get validation service from app.state if not set
        if not self.validation_service and hasattr(request.app.state, 'validation_service'):
            self.validation_service = request.app.state.validation_service
        
        # If still no validation service, skip validation
        if not self.validation_service:
            logger.warning("No validation service available, skipping validation")
            return await call_next(request)
        
        # Generate request ID for tracking
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Track validation timing
        start_time = time.time()
        
        try:
            # Validate request
            validation_result = await self._validate_request(request)
            
            if not validation_result["valid"]:
                return self._create_error_response(
                    status_code=400,
                    errors=validation_result["errors"],
                    request_id=request_id
                )
            
            # Store validated data for downstream use
            if validation_result.get("sanitized_data"):
                request.state.validated_data = validation_result["sanitized_data"]
            
            # Process request
            response = await call_next(request)
            
            # Validate response if enabled
            if self.enable_response_validation and response.status_code < 400:
                response = await self._validate_response(request, response)
            
            # Track metrics
            if self.enable_metrics:
                validation_time = (time.time() - start_time) * 1000
                await self._track_metrics(request, response, validation_time, True)
            
            return response
            
        except Exception as e:
            logger.error(f"Validation middleware error for request {request_id}: {e}")
            
            # Track error metrics
            if self.enable_metrics:
                validation_time = (time.time() - start_time) * 1000
                await self._track_metrics(request, None, validation_time, False)
            
            # Return generic error to prevent information disclosure
            if self.prevent_info_disclosure:
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": "Internal server error",
                        "request_id": request_id
                    }
                )
            else:
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": str(e),
                        "request_id": request_id
                    }
                )
    
    def _should_skip_validation(self, request: Request) -> bool:
        """Check if validation should be skipped for this request"""
        path = request.url.path
        
        # Skip excluded endpoints
        for excluded in self.EXCLUDED_ENDPOINTS:
            if path.startswith(excluded):
                return True
        
        # Skip OPTIONS requests
        if request.method == "OPTIONS":
            return True
        
        # Skip static files
        if path.startswith("/static"):
            return True
        
        return False
    
    def _validate_url_path(self, request: Request) -> Dict[str, Any]:
        """🔥 완전한 Path Traversal 차단 - 400 응답 보장 🔥"""
        
        try:
            path = request.url.path
            client_ip = request.client.host if request.client else 'unknown'
            
            # 🔥 직접적인 Path Traversal 패턴 검사 (import 없이)
            dangerous_patterns = [
                '../', '..\\\\', '%2e%2e%2f', '%2e%2e%5c', 
                '..%2f', '..%5c', '%252e%252e', 
                'etc/passwd', 'windows/system32', 'c:/windows'
            ]
            
            path_lower = path.lower()
            for pattern in dangerous_patterns:
                if pattern in path_lower:
                    logger.critical(f"🔥 PATH TRAVERSAL BLOCKED: {path} from {client_ip} - {pattern}")
                    return {
                        "valid": False,
                        "errors": ["Attack blocked"]
                    }
            
            return {"valid": True}
            
        except Exception as e:
            # 🔥 예외 발생 시도 안전하게 차단 (400 반환)
            logger.critical(f"🔥 PATH VALIDATION ERROR - BLOCKING FOR SAFETY: {e}")
            return {
                "valid": False,
                "errors": ["Attack blocked"]
            }
    
    async def _validate_request(self, request: Request) -> Dict[str, Any]:
        """Validate incoming request"""
        
        # First validate URL path for security threats
        path_validation = self._validate_url_path(request)
        if not path_validation["valid"]:
            return path_validation
        
        # Determine validation level
        validation_level = self._get_validation_level(request)
        
        # GET requests - validate query parameters
        if request.method == "GET":
            return await self._validate_query_params(request, validation_level)
        
        # Other methods - validate body
        if request.method in ["POST", "PUT", "PATCH"]:
            return await self._validate_request_body(request, validation_level)
        
        # DELETE requests - minimal validation
        if request.method == "DELETE":
            return {"valid": True, "sanitized_data": None}
        
        return {"valid": True, "sanitized_data": None}
    
    async def _validate_query_params(
        self,
        request: Request,
        validation_level: ValidationLevel
    ) -> Dict[str, Any]:
        """Validate query parameters"""
        
        # Convert query params to dict
        params = dict(request.query_params)
        
        if not params:
            return {"valid": True, "sanitized_data": None}
        
        # Determine entity type
        entity_type = self._get_entity_type(request)
        
        # Create validation context
        context = {
            "request_id": request.state.request_id,
            "method": request.method,
            "path": request.url.path,
            "user": getattr(request.state, "user", None)
        }
        
        # Validate parameters
        result = await self.validation_service.validate(
            data=params,
            entity_type=entity_type or "query",
            operation="read",
            level=validation_level,
            context=context
        )
        
        return {
            "valid": result.is_valid,
            "errors": [
                {
                    "field": error.field,
                    "message": error.message,
                    "code": error.code
                }
                for error in result.errors
                if error.severity in ["critical", "high"]
            ],
            "sanitized_data": result.sanitized_data
        }
    
    async def _validate_request_body(
        self,
        request: Request,
        validation_level: ValidationLevel
    ) -> Dict[str, Any]:
        """🔥 KILL ALL ATTACKS - 완전한 요청 본문 검증 🔥"""
        
        # Read body
        try:
            body = await request.body()
            if not body:
                return {"valid": True, "sanitized_data": None}
            
            # Store original body for downstream
            request._body = body
            # Reset stream consumed flag for Starlette 0.27+
            if hasattr(request, '_stream_consumed'):
                request._stream_consumed = False
            
            # 🔥 STEP 1: 기본적인 body 보안 검증만
            body_str = body.decode("utf-8", errors="ignore")
            
            # Null byte 검사만 (가장 기본적인 보안)
            if '\\x00' in body_str:
                logger.critical(f"🔥 NULL BYTE ATTACK BLOCKED in request body")
                return {
                    "valid": False,
                    "errors": [{"field": "body", "message": "Attack blocked", "code": "SECURITY_THREAT"}]
                }
            
            # Parse JSON
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                logger.warning(f"🔥 Invalid JSON attack blocked from {request_info['client_ip']}")
                return {
                    "valid": False,
                    "errors": [{"field": "body", "message": "Attack blocked", "code": "INVALID_JSON"}]
                }
            
            # 🔥 STEP 2: 간소화된 필드 검증 - False Positive 방지
            def simple_validate(obj, path=""):
                """필수 필드만 간단히 검증"""
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        field_path = f"{path}.{key}" if path else key
                        
                        # 값 검증만 (키는 스킵)
                        if value is not None:
                            from core.security.ultimate_killer import get_ultimate_killer
                            ultimate_killer = get_ultimate_killer()
                            is_safe, threats = ultimate_killer.kill_all_attacks(value, field_path)
                            if not is_safe:
                                logger.critical(f"🔥 ATTACK BLOCKED: {field_path} - {threats}")
                                return False
                        
                        # 재귀 검증 (중첩 객체만)
                        if isinstance(value, (dict, list)):
                            if not simple_validate(value, field_path):
                                return False
                
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        if not simple_validate(item, f"{path}[{i}]"):
                            return False
                
                return True
            
            # 간소화된 validation
            if not simple_validate(data):
                return {
                    "valid": False,
                    "errors": [{"field": "data", "message": "Attack blocked", "code": "SECURITY_THREAT"}]
                }
            
            # 🔥 STEP 3: 엔터프라이즈 검증 서비스 - 이중 검증
            if self.validation_service:
                try:
                    # Determine entity type and operation
                    entity_type = self._get_entity_type(request)
                    operation = self.METHOD_OPERATION_MAP.get(request.method, "unknown")
                    
                    # Create validation context
                    context = {
                        "request_id": request.state.request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "user": getattr(request.state, "user", None),
                        "branch": self._extract_branch_from_path(request.url.path)
                    }
                    
                    # Validate data
                    result = await self.validation_service.validate(
                        data=data,
                        entity_type=entity_type or "unknown",
                        operation=operation,
                        level=validation_level,
                        context=context
                    )
                    
                    if not result.is_valid:
                        logger.warning(f"🔥 Enterprise validation blocked attack: {len(result.errors)} violations")
                        return {
                            "valid": False,
                            "errors": [{"field": "data", "message": "Attack blocked", "code": "VALIDATION_FAILED"}]
                        }
                    
                    return {
                        "valid": True,
                        "sanitized_data": result.sanitized_data
                    }
                
                except Exception as e:
                    logger.error(f"🔥 Validation service error - blocking for safety: {e}")
                    return {
                        "valid": False,
                        "errors": [{"field": "system", "message": "Attack blocked", "code": "VALIDATION_ERROR"}]
                    }
            
            # 🔥 STEP 4: 최종 안전 처리
            logger.info(f"✅ Request validated and safe: {request.method} {request.url.path}")
            return {"valid": True, "sanitized_data": data}
            
        except Exception as e:
            logger.critical(f"🔥 CRITICAL ERROR - BLOCKING ALL: {e}")
            return {
                "valid": False,
                "errors": [{"field": "system", "message": "Attack blocked", "code": "CRITICAL_ERROR"}]
            }
    
    async def _validate_response(self, request: Request, response: Response) -> Response:
        """Validate response data"""
        
        # Only validate JSON responses
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response
        
        try:
            # Read response body
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            
            # Parse JSON
            data = json.loads(body)
            
            # Validate response structure
            entity_type = self._get_entity_type(request)
            if entity_type:
                # Perform light validation on response
                context = {
                    "request_id": request.state.request_id,
                    "response": True
                }
                
                result = await self.validation_service.validate(
                    data=data,
                    entity_type=entity_type,
                    operation="read",
                    level=ValidationLevel.MINIMAL,
                    context=context
                )
                
                if not result.is_valid:
                    logger.error(
                        f"Response validation failed for {request.url.path}: "
                        f"{len(result.errors)} errors"
                    )
            
            # Return new response with original body
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )
            
        except Exception as e:
            logger.error(f"Error validating response: {e}")
            return response
    
    def _get_validation_level(self, request: Request) -> ValidationLevel:
        """Determine validation level for request"""
        path = request.url.path
        
        # Check endpoint-specific overrides
        for pattern, level in self.endpoint_validation_levels.items():
            if path.startswith(pattern):
                return level
        
        # Check if strict validation required
        for strict_pattern in self.STRICT_VALIDATION_ENDPOINTS:
            if path.startswith(strict_pattern):
                return ValidationLevel.STRICT
        
        return self.default_level
    
    def _get_entity_type(self, request: Request) -> Optional[str]:
        """Extract entity type from request path"""
        path = request.url.path
        
        # Check direct mapping
        for pattern, entity_type in self.ENDPOINT_ENTITY_MAP.items():
            if pattern in path:
                return entity_type
        
        # Try to extract from path segments
        segments = path.strip("/").split("/")
        if len(segments) >= 3:
            # Format: /api/v1/schemas/{branch}/{entity-type}
            potential_entity = segments[-1].rstrip("s")  # Remove plural
            if potential_entity in ["object-type", "property", "link-type", "action-type"]:
                return potential_entity.replace("-", "_")
        
        return None
    
    def _extract_branch_from_path(self, path: str) -> Optional[str]:
        """Extract branch name from path"""
        segments = path.strip("/").split("/")
        
        # Look for schemas/{branch} pattern
        for i, segment in enumerate(segments):
            if segment == "schemas" and i + 1 < len(segments):
                return segments[i + 1]
        
        return None
    
    def _sanitize_error_message(self, message: str) -> str:
        """Sanitize error message to prevent information disclosure"""
        # Remove specific system paths
        import re
        message = re.sub(r'/[^/\s]+/[^/\s]+/', '/.../', message)
        
        # Remove SQL keywords to prevent SQL injection pattern disclosure
        sql_patterns = [
            r'(?i)(select|update|delete|insert|drop|create|alter|truncate|union|exec|execute)\s+\w+',
            r'(?i)(from|where|join|table|database|schema)\s+\w+',
            r'(?i)(or|and)\s+[\'"]?\d+[\'"]?\s*=\s*[\'"]?\d+',
        ]
        
        for pattern in sql_patterns:
            message = re.sub(pattern, '[SQL_REDACTED]', message)
        
        # Remove specific error details
        sensitive_patterns = [
            r'at line \d+',
            r'column \d+',
            r'position \d+',
            r'byte \d+',
            r'0x[0-9a-fA-F]+',
            r'[a-zA-Z]:\\\\[^\\s]+',  # Windows paths
            r'/home/[^/\s]+',  # Unix home paths
        ]
        
        for pattern in sensitive_patterns:
            message = re.sub(pattern, '[REDACTED]', message)
        
        return message
    
    def _create_error_response(
        self,
        status_code: int,
        errors: list,
        request_id: str
    ) -> JSONResponse:
        """Create standardized error response"""
        
        if self.prevent_info_disclosure:
            # Generic error response
            content = {
                "error": "Validation failed",
                "request_id": request_id,
                "details": [
                    {
                        "field": error["field"],
                        "code": error["code"]
                    }
                    for error in errors[:3]  # Limit number of errors shown
                ]
            }
        else:
            # Detailed error response
            content = {
                "error": "Validation failed",
                "request_id": request_id,
                "errors": errors
            }
        
        return JSONResponse(
            status_code=status_code,
            content=content
        )
    
    async def _track_metrics(
        self,
        request: Request,
        response: Optional[Response],
        validation_time: float,
        success: bool
    ):
        """Track validation metrics"""
        try:
            # Record validation time
            metrics_collector.histogram(
                "validation_duration_ms",
                validation_time,
                labels={
                    "method": request.method,
                    "endpoint": request.url.path,
                    "success": str(success).lower()
                }
            )
            
            # Count validations
            metrics_collector.increment(
                "validation_total",
                labels={
                    "method": request.method,
                    "endpoint": request.url.path,
                    "success": str(success).lower()
                }
            )
            
            # Track response status if available
            if response:
                metrics_collector.increment(
                    "validation_response_status",
                    labels={
                        "status_code": str(response.status_code),
                        "method": request.method
                    }
                )
                
        except Exception as e:
            logger.warning(f"Failed to track metrics: {e}")


def configure_enterprise_validation(
    app,
    validation_service: Optional[EnterpriseValidationService] = None,
    default_level: ValidationLevel = ValidationLevel.STANDARD,
    **kwargs
):
    """
    Configure enterprise validation middleware for FastAPI app
    
    Args:
        app: FastAPI application
        validation_service: Optional validation service instance
        default_level: Default validation level
        **kwargs: Additional middleware configuration
    """
    import os
    
    # Check if validation is enabled
    if os.getenv("ENTERPRISE_VALIDATION_ENABLED", "true").lower() == "false":
        logger.info("Enterprise validation middleware DISABLED")
        return
    
    # Get configuration from environment
    config = {
        "validation_service": validation_service,
        "default_level": ValidationLevel(os.getenv("VALIDATION_LEVEL", default_level.value)),
        "enable_response_validation": os.getenv("VALIDATE_RESPONSES", "true").lower() == "true",
        "enable_metrics": os.getenv("VALIDATION_METRICS", "true").lower() == "true",
        "log_validation_errors": os.getenv("LOG_VALIDATION_ERRORS", "true").lower() == "true",
        "prevent_info_disclosure": os.getenv("PREVENT_INFO_DISCLOSURE", "true").lower() == "true"
    }
    
    # Override with provided kwargs
    config.update(kwargs)
    
    # Add middleware
    app.add_middleware(EnterpriseValidationMiddleware, **config)
    
    logger.info(f"Enterprise validation middleware configured with level: {config['default_level']}")