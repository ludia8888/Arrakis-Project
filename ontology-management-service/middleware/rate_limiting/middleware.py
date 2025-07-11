"""
Rate Limiting Middleware for FastAPI
"""
from typing import Callable, Optional
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
import logging

from .coordinator import RateLimitCoordinator
from .models import RateLimitConfig, RateLimitKey, RateLimitScope

logger = logging.getLogger(__name__)


class RateLimitingMiddleware:
    """
    FastAPI middleware for rate limiting
    """
    
    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.coordinator = RateLimitCoordinator(config)
        self.enabled = True
        
    async def __call__(self, request: Request, call_next: Callable) -> Response:
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
        """Extract rate limit key from request"""
        # Try to get authenticated user
        user = getattr(request.state, "user", None)
        if user:
            return RateLimitKey(
                type="user",
                value=user.user_id,
                metadata={"username": user.username}
            )
        
        # Fall back to IP address
        client = request.client
        if client:
            return RateLimitKey(
                type="ip",
                value=client.host,
                metadata={"port": str(client.port)}
            )
        
        # Default key
        return RateLimitKey(
            type="anonymous",
            value="anonymous",
            metadata={}
        )
    
    def _determine_scope(self, request: Request) -> RateLimitScope:
        """Determine rate limit scope from request"""
        path = request.url.path
        
        # API endpoints
        if path.startswith("/api/"):
            if "/auth/" in path:
                return RateLimitScope.AUTH
            elif any(op in path for op in ["create", "update", "delete", "merge"]):
                return RateLimitScope.WRITE
            else:
                return RateLimitScope.READ
        
        # Default to global scope
        return RateLimitScope.GLOBAL