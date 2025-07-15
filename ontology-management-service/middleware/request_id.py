"""
Request ID Middleware
Adds unique request ID to each request for tracking
"""
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import logging

logger = logging.getLogger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
 """
 Middleware that adds a unique request ID to each request
 """

 async def dispatch(self, request: Request, call_next):
 # Generate unique request ID
 request_id = request.headers.get("X-Request-Id")

 if not request_id:
 request_id = str(uuid.uuid4())

 # Store request ID in request state
 request.state.request_id = request_id

 # Log request with ID
 logger.info(f"Request {request_id}: {request.method} {request.url.path}")

 # Process request
 response = await call_next(request)

 # Add request ID to response headers
 response.headers["X-Request-Id"] = request_id

 return response
