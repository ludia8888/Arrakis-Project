"""
Audit Log Middleware
Logs all API requests for audit purposes
"""
import time
import json
from datetime import datetime
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import logging

logger = logging.getLogger(__name__)


class AuditLogMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs all requests for audit purposes
    """
    
    async def dispatch(self, request: Request, call_next):
        # Start timing
        start_time = time.time()
        
        # Get request info
        request_info = {
            "timestamp": datetime.utcnow().isoformat(),
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "client_host": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent", ""),
        }
        
        # Get user info if available
        if hasattr(request.state, "user_context"):
            request_info["user_id"] = request.state.user_context.user_id
            request_info["username"] = request.state.user_context.username
        
        # Get request ID if available
        if hasattr(request.state, "request_id"):
            request_info["request_id"] = request.state.request_id
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log audit entry
        audit_entry = {
            **request_info,
            "status_code": response.status_code,
            "duration_ms": round(duration * 1000, 2),
        }
        
        # Log based on status code
        if response.status_code >= 500:
            logger.error(f"Audit Log: {json.dumps(audit_entry)}")
        elif response.status_code >= 400:
            logger.warning(f"Audit Log: {json.dumps(audit_entry)}")
        else:
            logger.info(f"Audit Log: {json.dumps(audit_entry)}")
        
        return response