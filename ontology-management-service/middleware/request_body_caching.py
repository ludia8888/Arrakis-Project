"""
Request Body Caching Middleware for FastAPI/Starlette

This middleware ensures that request bodies can be read multiple times
by caching them in the request state after the first read.
"""
import logging
import os
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RequestBodyCachingMiddleware(BaseHTTPMiddleware):
 """
 Middleware that caches request bodies to allow multiple reads.

 This is necessary because in ASGI/Starlette, request bodies can only be
 read once by default. This middleware intercepts the first read and
 caches the result for subsequent reads.
 """

 def __init__(self, app, max_body_size: int = None):
 super().__init__(app)
 self.max_body_size = max_body_size or int(
 os.getenv("REQUEST_BODY_MAX_SIZE", "52428800") # 50MB default
 )
 # Metrics
 self.cache_hits = 0
 self.cache_misses = 0
 self.body_size_violations = 0

 async def dispatch(self, request: Request, call_next: Callable) -> Response:
 """Process request with body caching."""
 # Only cache body for methods that typically have bodies
 if request.method in ("POST", "PUT", "PATCH"):
 # Check if body is already cached
 if not hasattr(request.state, "body"):
 try:
 # Read and cache the body
 body = await request.body()

 # Check size limit
 if len(body) > self.max_body_size:
 self.body_size_violations += 1
 logger.warning(
 f"Request body size {len(body)} exceeds limit {self.max_body_size}"
 )
 # You could raise an exception here if needed
 # raise ValueError(f"Request body too large: {len(body)} bytes > {self.max_body_size} bytes")

 request.state.body = body
 self.cache_misses += 1
 except Exception as e:
 logger.error(f"Error reading request body: {e}")
 # Let the request continue without cached body
 else:
 self.cache_hits += 1

 # Process the request
 response = await call_next(request)
 return response

 async def process_request_with_caching(self, request: Request) -> bytes:
 """
 Process request with body caching enabled.
 This method is used for direct testing of the caching logic.
 """
 if not hasattr(request.state, "body"):
 try:
 body = await request.body()

 # Check size limit
 if len(body) > self.max_body_size:
 self.body_size_violations += 1
 raise ValueError(
 f"Request body too large: {len(body)} bytes > {self.max_body_size} bytes"
 )

 request.state.body = body
 self.cache_misses += 1
 except RuntimeError as e:
 # Body already read, check if cached
 if hasattr(request.state, "body"):
 self.cache_hits += 1
 else:
 raise
 else:
 self.cache_hits += 1

 return request.state.body


# ASGI middleware version for lower-level control
class ASGIRequestBodyCachingMiddleware:
 """
 ASGI-level request body caching middleware.

 This provides more control over the request/response cycle
 and can handle edge cases better than the high-level middleware.
 """

 def __init__(self, app, max_body_size: int = None):
 self.app = app
 self.max_body_size = max_body_size or int(
 os.getenv("REQUEST_BODY_MAX_SIZE", "52428800") # 50MB default
 )
 # Metrics
 self.cache_hits = 0
 self.cache_misses = 0
 self.body_size_violations = 0

 async def __call__(self, scope, receive, send):
 """ASGI middleware implementation."""
 if scope["type"] != "http":
 await self.app(scope, receive, send)
 return

 # Create wrapped receive that caches body
 cached_body = None
 body_chunks = []

 async def cached_receive():
 nonlocal cached_body

 message = await receive()

 if message["type"] == "http.request":
 if cached_body is None:
 # First read - accumulate chunks
 body_chunks.append(message.get("body", b""))

 # Check if more body data is coming
 if not message.get("more_body", False):
 # All body data received
 cached_body = b"".join(body_chunks)
 body_chunks.clear()

 # Check body size limit
 if len(cached_body) > self.max_body_size:
 self.body_size_violations += 1
 # Create error response
 await send(
 {
 "type": "http.response.start",
 "status": 413, # Payload Too Large
 "headers": [[b"content-type", b"text/plain"]],
 }
 )
 await send(
 {
 "type": "http.response.body",
 "body": f"Request body too large: {len(cached_body)} bytes > {self.max_body_size} bytes".encode(),


 }
 )
 raise ValueError(
 f"Request body too large: {len(cached_body)} bytes"
 )

 self.cache_misses += 1
 message["body"] = cached_body
 else:
 # Subsequent reads - return cached body
 self.cache_hits += 1
 message["body"] = cached_body
 message["more_body"] = False

 return message

 # Pass the wrapped receive to the app
 await self.app(scope, cached_receive, send)
