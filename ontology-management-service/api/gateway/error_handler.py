"""
Standardized Error Handler for Gateway Modules
Provides consistent error responses and logging across all gateway components
"""
import logging
import traceback
from datetime import datetime
from typing import Dict, Optional, Union

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from models.exceptions import (
    AuthenticationError,
    IAMServiceUnavailableError,
    OMSException,
    ResourceNotFoundError,
    ServiceUnavailableError,
    ValidationError,
)

logger = logging.getLogger(__name__)


class ErrorResponse:
    """Standardized error response format"""

    @staticmethod
    def create(
        error_type: str,
        message: str,
        code: str,
        status_code: int,
        details: Optional[Dict] = None,
        request_id: Optional[str] = None,
    ) -> Dict:
        """Create standardized error response"""
        return {
            "error": {
                "type": error_type,
                "message": message,
                "code": code,
                "details": details or {},
            },
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }


class GatewayErrorHandler(BaseHTTPMiddleware):
    """
    Middleware for handling all gateway errors consistently
    """

    async def dispatch(self, request: Request, call_next):
        """Process request and handle any errors"""
        request_id = request.headers.get("X-Request-ID", "unknown")

        try:
            response = await call_next(request)
            return response

        except HTTPException as e:
            # FastAPI HTTPException - already has status code and detail
            logger.warning(
                f"HTTP exception: {e.status_code} - {e.detail}",
                extra={"request_id": request_id, "path": str(request.url.path)},
            )
            return JSONResponse(
                status_code=e.status_code,
                content=ErrorResponse.create(
                    error_type="HTTPException",
                    message=str(e.detail),
                    code=f"HTTP_{e.status_code}",
                    status_code=e.status_code,
                    request_id=request_id,
                ),
            )

        except ValidationError as e:
            # Validation errors - 400 Bad Request
            logger.warning(
                f"Validation error: {str(e)}",
                extra={"request_id": request_id, "path": str(request.url.path)},
            )
            return JSONResponse(
                status_code=400,
                content=ErrorResponse.create(
                    error_type="ValidationError",
                    message=str(e),
                    code="VALIDATION_FAILED",
                    status_code=400,
                    details=getattr(e, "details", {}),
                    request_id=request_id,
                ),
            )

        except ResourceNotFoundError as e:
            # Resource not found - 404
            logger.info(
                f"Resource not found: {str(e)}",
                extra={"request_id": request_id, "path": str(request.url.path)},
            )
            return JSONResponse(
                status_code=404,
                content=ErrorResponse.create(
                    error_type="ResourceNotFoundError",
                    message=str(e),
                    code="RESOURCE_NOT_FOUND",
                    status_code=404,
                    request_id=request_id,
                ),
            )

        except AuthenticationError as e:
            # Authentication errors - 401
            logger.warning(
                f"Authentication error: {str(e)}",
                extra={"request_id": request_id, "path": str(request.url.path)},
            )
            return JSONResponse(
                status_code=401,
                content=ErrorResponse.create(
                    error_type="AuthenticationError",
                    message=str(e),
                    code="AUTHENTICATION_FAILED",
                    status_code=401,
                    request_id=request_id,
                ),
            )

        except IAMServiceUnavailableError as e:
            # IAM service specific unavailability - 503
            logger.error(
                f"IAM service unavailable: {str(e)}",
                extra={"request_id": request_id, "path": str(request.url.path)},
            )
            return JSONResponse(
                status_code=503,
                content=ErrorResponse.create(
                    error_type="IAMServiceUnavailableError",
                    message=str(e),
                    code="IAM_SERVICE_UNAVAILABLE",
                    status_code=503,
                    details={"service": "iam", "retry_after": 30},
                    request_id=request_id,
                ),
            )

        except ServiceUnavailableError as e:
            # General service unavailability - 503
            logger.error(
                f"Service unavailable: {str(e)}",
                extra={"request_id": request_id, "path": str(request.url.path)},
            )
            return JSONResponse(
                status_code=503,
                content=ErrorResponse.create(
                    error_type="ServiceUnavailableError",
                    message=str(e),
                    code="SERVICE_UNAVAILABLE",
                    status_code=503,
                    details={"retry_after": 30},
                    request_id=request_id,
                ),
            )

        except OMSException as e:
            # Other OMS exceptions - 500
            logger.error(
                f"OMS exception: {str(e)}",
                extra={
                    "request_id": request_id,
                    "path": str(request.url.path),
                    "exception_type": type(e).__name__,
                },
                exc_info=True,
            )
            return JSONResponse(
                status_code=500,
                content=ErrorResponse.create(
                    error_type=type(e).__name__,
                    message=str(e),
                    code="INTERNAL_ERROR",
                    status_code=500,
                    request_id=request_id,
                ),
            )

        except ValueError as e:
            # Handle ValueError as validation error
            logger.warning(
                f"Value error: {str(e)}",
                extra={"request_id": request_id, "path": str(request.url.path)},
            )
            return JSONResponse(
                status_code=400,
                content=ErrorResponse.create(
                    error_type="ValueError",
                    message=str(e),
                    code="INVALID_VALUE",
                    status_code=400,
                    request_id=request_id,
                ),
            )

        except Exception as e:
            # Unexpected errors - 500
            logger.error(
                f"Unexpected error: {str(e)}",
                extra={
                    "request_id": request_id,
                    "path": str(request.url.path),
                    "exception_type": type(e).__name__,
                    "traceback": traceback.format_exc(),
                },
                exc_info=True,
            )
            return JSONResponse(
                status_code=500,
                content=ErrorResponse.create(
                    error_type="InternalServerError",
                    message="An unexpected error occurred",
                    code="INTERNAL_SERVER_ERROR",
                    status_code=500,
                    request_id=request_id,
                ),
            )


def handle_gateway_error(
    error: Exception, request_id: Optional[str] = None
) -> JSONResponse:
    """
    Utility function to handle errors in non-middleware contexts

    Args:
        error: The exception to handle
        request_id: Optional request ID for tracking

    Returns:
        JSONResponse with appropriate error format
    """
    if isinstance(error, HTTPException):
        return JSONResponse(
            status_code=error.status_code,
            content=ErrorResponse.create(
                error_type="HTTPException",
                message=str(error.detail),
                code=f"HTTP_{error.status_code}",
                status_code=error.status_code,
                request_id=request_id,
            ),
        )

    elif isinstance(error, ValidationError):
        return JSONResponse(
            status_code=400,
            content=ErrorResponse.create(
                error_type="ValidationError",
                message=str(error),
                code="VALIDATION_FAILED",
                status_code=400,
                details=getattr(error, "details", {}),
                request_id=request_id,
            ),
        )

    elif isinstance(error, ResourceNotFoundError):
        return JSONResponse(
            status_code=404,
            content=ErrorResponse.create(
                error_type="ResourceNotFoundError",
                message=str(error),
                code="RESOURCE_NOT_FOUND",
                status_code=404,
                request_id=request_id,
            ),
        )

    elif isinstance(error, ServiceUnavailableError):
        return JSONResponse(
            status_code=503,
            content=ErrorResponse.create(
                error_type="ServiceUnavailableError",
                message=str(error),
                code="SERVICE_UNAVAILABLE",
                status_code=503,
                details={"retry_after": 30},
                request_id=request_id,
            ),
        )

    else:
        return JSONResponse(
            status_code=500,
            content=ErrorResponse.create(
                error_type="InternalServerError",
                message="An unexpected error occurred",
                code="INTERNAL_SERVER_ERROR",
                status_code=500,
                request_id=request_id,
            ),
        )
