"""
User Service Client
Handles JWT token validation and user information retrieval
"""
import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import HTTPException, status

from core.auth import UserContext
from utils.logger import get_logger
from shared.config.environment import StrictEnv
from shared.config.unified_env import unified_env

logger = get_logger(__name__)


class UserServiceError(Exception):
    """User Service related errors"""
    pass


class UserServiceClient:
    """
    Client for interacting with User Service MSA
    Handles JWT validation and user context retrieval
    """
    
    def __init__(self):
        self.base_url = StrictEnv.get("USER_SERVICE_URL")
        self.timeout = 30.0
        
        # JWT secret MUST be provided via environment variable
        self.jwt_secret = StrictEnv.get("JWT_SECRET")
        if not self.jwt_secret:
            raise ValueError(
                "JWT_SECRET environment variable is required. "
                "Set it to a secure random value (e.g., openssl rand -base64 32)"
            )
        
        self.jwt_algorithm = "HS256"
        
        # For development/testing, we can validate JWTs locally
        self.local_validation = unified_env.get("JWT_LOCAL_VALIDATION")
    
    async def validate_jwt_token(self, token: str) -> UserContext:
        """
        Validate JWT token and return user context
        
        Args:
            token: JWT token string
            
        Returns:
            UserContext: Validated user information
            
        Raises:
            UserServiceError: If validation fails
        """
        if self.local_validation:
            return await self._validate_token_locally(token)
        else:
            return await self._validate_token_remote(token)
    
    async def _validate_token_locally(self, token: str) -> UserContext:
        """
        Validate JWT token locally (for development/testing)
        """
        try:
            # Decode JWT
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=[self.jwt_algorithm]
            )
            
            # Check expiration
            exp = payload.get("exp")
            if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
                raise UserServiceError("Token has expired")
            
            # Extract user information
            user_context = UserContext(
                user_id=payload.get("sub", payload.get("user_id")),
                username=payload.get("username", payload.get("preferred_username")),
                email=payload.get("email"),
                roles=payload.get("roles", []),
                tenant_id=payload.get("tenant_id"),
                metadata=payload.get("metadata", {})
            )
            
            # Validate required fields
            if not user_context.user_id or not user_context.username:
                raise UserServiceError("Invalid token: missing user_id or username")
            
            return user_context
            
        except jwt.ExpiredSignatureError:
            raise UserServiceError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise UserServiceError(f"Invalid token: {str(e)}")
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            raise UserServiceError(f"Token validation failed: {str(e)}")
    
    async def _validate_token_remote(self, token: str) -> UserContext:
        """
        Validate JWT token via User Service API
        """
        async with httpx.AsyncClient(verify=False) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/v1/auth/validate",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    },
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return UserContext(**data)
                elif response.status_code == 401:
                    raise UserServiceError("Invalid or expired token")
                else:
                    raise UserServiceError(
                        f"User service returned {response.status_code}: {response.text}"
                    )
                    
            except httpx.TimeoutException:
                raise UserServiceError("User service timeout")
            except httpx.RequestError as e:
                logger.error(f"User service request error: {e}")
                raise UserServiceError(f"Failed to connect to user service: {str(e)}")
    
    async def get_user_by_id(self, user_id: str, auth_token: str) -> Dict[str, Any]:
        """
        Get detailed user information by ID
        """
        async with httpx.AsyncClient(verify=False) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/v1/users/{user_id}",
                    headers={
                        "Authorization": f"Bearer {auth_token}"
                    },
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    raise UserServiceError(f"User {user_id} not found")
                else:
                    raise UserServiceError(
                        f"Failed to get user: {response.status_code}"
                    )
                    
            except httpx.RequestError as e:
                raise UserServiceError(f"Failed to get user: {str(e)}")
    
    async def get_user_roles(self, user_id: str, auth_token: str) -> List[str]:
        """
        Get user's roles from User Service
        """
        user_data = await self.get_user_by_id(user_id, auth_token)
        return user_data.get("roles", [])


# Global client instance (lazy-initialized)
_user_service_client = None


def _get_user_service_client() -> UserServiceClient:
    """Get or create the global user service client"""
    global _user_service_client
    if _user_service_client is None:
        _user_service_client = UserServiceClient()
    return _user_service_client


async def validate_jwt_token(token: str) -> UserContext:
    """
    Global function to validate JWT token
    Used by AuthMiddleware
    """
    client = _get_user_service_client()
    return await client.validate_jwt_token(token)


def create_mock_jwt(
    user_id: str = "test-user",
    username: str = "testuser",
    roles: List[str] = None,
    expires_in: int = 3600
) -> str:
    """
    Create a mock JWT token for testing
    """
    if roles is None:
        roles = ["developer"]
    
    payload = {
        "sub": user_id,
        "username": username,
        "email": f"{username}@example.com",
        "roles": roles,
        "exp": datetime.now(timezone.utc) + timedelta(seconds=expires_in),
        "iat": datetime.now(timezone.utc),
        "tenant_id": "default"
    }
    
    client = _get_user_service_client()
    return jwt.encode(
        payload,
        client.jwt_secret,
        algorithm=client.jwt_algorithm
    )