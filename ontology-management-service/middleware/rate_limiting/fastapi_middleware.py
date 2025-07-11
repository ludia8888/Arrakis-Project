"""
FastAPI-compatible Rate Limiting Middleware
"""
from typing import Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
import logging

from .coordinator import RateLimitCoordinator
from .models import RateLimitConfig, RateLimitKey, RateLimitScope

logger = logging.getLogger(__name__)


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting using dispatch pattern
    """
    
    def __init__(self, app, config: Optional[RateLimitConfig] = None):
        super().__init__(app)
        self.coordinator = RateLimitCoordinator(config)
        self.enabled = True
        
    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Process request through rate limiting
        """
        if not self.enabled:
            return await call_next(request)
            
        # Extract rate limit key from request
        key = self._extract_key(request)
        
        # Check rate limit
        result = await self.coordinator.check_limit(
            key=key,
            endpoint=request.url.path,
            scope=self._determine_scope(request)
        )
        
        if not result.allowed:
            # Rate limit exceeded
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "retry_after": result.retry_after,
                    "limit": result.limit,
                    "remaining": result.remaining,
                    "reset": result.reset.isoformat() if result.reset else None
                },
                headers={
                    "X-RateLimit-Limit": str(result.limit),
                    "X-RateLimit-Remaining": str(result.remaining),
                    "X-RateLimit-Reset": str(int(result.reset.timestamp())) if result.reset else "",
                    "Retry-After": str(result.retry_after)
                }
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        if result.reset:
            response.headers["X-RateLimit-Reset"] = str(int(result.reset.timestamp()))
        
        return response
    
    def _extract_key(self, request: Request) -> RateLimitKey:
        """
        Extract rate limit key from request
        """
        # Try to get user ID from request state
        user_id = None
        if hasattr(request.state, "user_context") and request.state.user_context:
            user_id = request.state.user_context.user_id
            
        # Extract IP address
        ip = request.client.host if request.client else "unknown"
        
        return RateLimitKey(
            identifier=user_id or ip,
            type="user" if user_id else "ip"
        )
    
    def _determine_scope(self, request: Request) -> RateLimitScope:
        """
        Determine rate limit scope based on request
        """
        path = request.url.path
        
        # Admin endpoints
        if path.startswith("/api/v1/admin"):
            return RateLimitScope.ADMIN
        
        # Auth endpoints
        if path.startswith("/api/v1/auth"):
            return RateLimitScope.AUTH
        
        # Write operations
        if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
            return RateLimitScope.WRITE
        
        # Default to read
        return RateLimitScope.READ
    
    def set_enabled(self, enabled: bool):
        """Enable or disable rate limiting"""
        self.enabled = enabled
        logger.info(f"Rate limiting {'enabled' if enabled else 'disabled'}")