"""
Mock Authentication Middleware for Testing
Only enabled when BYPASS_AUTH=true environment variable is set
"""
import os
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from core.auth import UserContext


class MockAuthMiddleware(BaseHTTPMiddleware):
    """
    Bypass authentication for testing purposes
    Injects a dummy user into all requests
    """
    
    async def dispatch(self, request: Request, call_next):
        # Only activate if BYPASS_AUTH is explicitly set to true
        if os.getenv("BYPASS_AUTH", "false").lower() == "true":
            # Inject mock user into request state
            request.state.user = UserContext(
                user_id="test-user-001",
                username="test_user",
                email="test@example.com",
                roles=["admin", "user"],
                permissions=["*"],
                sub="test-user-001"
            )
        
        response = await call_next(request)
        return response