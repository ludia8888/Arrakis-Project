"""
Global Exception Handler Middleware
Centralized exception handling with proper error responses and logging
"""
import traceback
from typing import Dict, Any, Optional
from datetime import datetime
from uuid import uuid4

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from shared.exceptions import (
    OntologyException, ValidationError, NotFoundError, 
    AuthenticationError, AuthorizationError, ConflictError,
    ServiceException, InfrastructureException,
    CircuitBreakerOpenError, RateLimitExceededError
)
from shared.exceptions.domain_exceptions import (
    SchemaValidationError, PolicyViolationError,
    BranchLockError, EventOrderingError
)
from utils.logger import get_logger

logger = get_logger(__name__)


class GlobalExceptionHandlerMiddleware(BaseHTTPMiddleware):
    """
    Global exception handler that converts exceptions to proper HTTP responses
    """
    
    # Exception to HTTP status code mapping
    EXCEPTION_STATUS_MAP = {
        ValidationError: status.HTTP_400_BAD_REQUEST,
        SchemaValidationError: status.HTTP_400_BAD_REQUEST,
        PolicyViolationError: status.HTTP_400_BAD_REQUEST,
        NotFoundError: status.HTTP_404_NOT_FOUND,
        AuthenticationError: status.HTTP_401_UNAUTHORIZED,
        AuthorizationError: status.HTTP_403_FORBIDDEN,
        ConflictError: status.HTTP_409_CONFLICT,
        BranchLockError: status.HTTP_409_CONFLICT,
        RateLimitExceededError: status.HTTP_429_TOO_MANY_REQUESTS,
        CircuitBreakerOpenError: status.HTTP_503_SERVICE_UNAVAILABLE,
        ServiceException: status.HTTP_502_BAD_GATEWAY,
        InfrastructureException: status.HTTP_503_SERVICE_UNAVAILABLE,
    }
    
    def __init__(self, app, enable_stack_trace: bool = False):
        super().__init__(app)
        self.enable_stack_trace = enable_stack_trace
    
    async def dispatch(self, request: Request, call_next):
        """Handle exceptions and convert to proper responses"""
        request_id = str(uuid4())
        
        try:
            response = await call_next(request)
            return response
            
        except OntologyException as e:
            # Handle known business exceptions
            return await self._handle_ontology_exception(e, request, request_id)
            
        except Exception as e:
            # Handle unexpected exceptions
            return await self._handle_unexpected_exception(e, request, request_id)
    
    async def _handle_ontology_exception(
        self, 
        exc: OntologyException, 
        request: Request,
        request_id: str
    ) -> JSONResponse:
        """Handle known business exceptions"""
        # Get appropriate status code
        status_code = self._get_status_code(exc)
        
        # Build error response
        error_response = self._build_error_response(
            exc=exc,
            status_code=status_code,
            request_id=request_id,
            path=str(request.url)
        )
        
        # Log the exception
        if status_code >= 500:
            logger.error(
                f"Server error: {exc.__class__.__name__}: {str(exc)}",
                extra={
                    "request_id": request_id,
                    "path": str(request.url),
                    "method": request.method,
                    "error_code": exc.code if hasattr(exc, 'code') else None
                }
            )
        else:
            logger.warning(
                f"Client error: {exc.__class__.__name__}: {str(exc)}",
                extra={
                    "request_id": request_id,
                    "path": str(request.url),
                    "method": request.method,
                    "error_code": exc.code if hasattr(exc, 'code') else None
                }
            )
        
        return JSONResponse(
            status_code=status_code,
            content=error_response,
            headers=self._get_error_headers(exc, request_id)
        )
    
    async def _handle_unexpected_exception(
        self,
        exc: Exception,
        request: Request,
        request_id: str
    ) -> JSONResponse:
        """Handle unexpected exceptions"""
        # Log full exception with traceback
        logger.error(
            f"Unexpected error: {exc.__class__.__name__}: {str(exc)}",
            exc_info=True,
            extra={
                "request_id": request_id,
                "path": str(request.url),
                "method": request.method
            }
        )
        
        # Build generic error response
        error_response = {
            "error": {
                "type": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat(),
                "path": str(request.url)
            }
        }
        
        # Include stack trace in development
        if self.enable_stack_trace:
            error_response["error"]["debug"] = {
                "exception": exc.__class__.__name__,
                "message": str(exc),
                "traceback": traceback.format_exc()
            }
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response,
            headers={"X-Request-ID": request_id}
        )
    
    def _get_status_code(self, exc: OntologyException) -> int:
        """Get HTTP status code for exception"""
        # Check exact type match first
        exc_type = type(exc)
        if exc_type in self.EXCEPTION_STATUS_MAP:
            return self.EXCEPTION_STATUS_MAP[exc_type]
        
        # Check inheritance
        for exc_class, status_code in self.EXCEPTION_STATUS_MAP.items():
            if isinstance(exc, exc_class):
                return status_code
        
        # Default to 500 for unknown OntologyException
        return status.HTTP_500_INTERNAL_SERVER_ERROR
    
    def _build_error_response(
        self,
        exc: OntologyException,
        status_code: int,
        request_id: str,
        path: str
    ) -> Dict[str, Any]:
        """Build standardized error response"""
        error_response = {
            "error": {
                "type": exc.code if hasattr(exc, 'code') else exc.__class__.__name__,
                "message": str(exc),
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat(),
                "path": path
            }
        }
        
        # Add exception-specific details
        if hasattr(exc, 'details') and exc.details:
            error_response["error"]["details"] = exc.details
        
        if hasattr(exc, 'violations') and exc.violations:
            error_response["error"]["violations"] = exc.violations
        
        if hasattr(exc, 'retry_after'):
            error_response["error"]["retry_after"] = exc.retry_after
        
        return error_response
    
    def _get_error_headers(self, exc: OntologyException, request_id: str) -> Dict[str, str]:
        """Get response headers for error"""
        headers = {
            "X-Request-ID": request_id,
            "X-Error-Type": exc.code if hasattr(exc, 'code') else exc.__class__.__name__
        }
        
        # Add retry-after header for rate limiting
        if isinstance(exc, RateLimitExceededError) and hasattr(exc, 'retry_after'):
            headers["Retry-After"] = str(exc.retry_after)
        
        # Add retry-after for circuit breaker
        if isinstance(exc, CircuitBreakerOpenError) and hasattr(exc, 'retry_after'):
            headers["Retry-After"] = str(exc.retry_after)
        
        return headers


def configure_exception_handling(app, enable_stack_trace: bool = False):
    """Configure global exception handling for the application"""
    app.add_middleware(
        GlobalExceptionHandlerMiddleware,
        enable_stack_trace=enable_stack_trace
    )
    
    logger.info(
        "Global exception handler configured",
        extra={"enable_stack_trace": enable_stack_trace}
    )