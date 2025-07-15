"""
Enhanced Authentication Middleware
User Service와 연동하여 JWT 토큰 검증 및 사용자 컨텍스트 주입
"""
import os
from typing import Optional, Callable, Dict, Any
from fastapi import Request, HTTPException, status, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import redis.asyncio as redis
import json
import httpx
import inspect
import jwt
from jwt import PyJWKClient

from core.auth import UserContext
from bootstrap.config import get_config
from middleware.circuit_breaker import CircuitBreakerGroup, CircuitBreakerError
from arrakis_common import get_logger
from config.secure_config import secure_config

logger = get_logger(__name__)

class AuthMiddleware(BaseHTTPMiddleware):
 """
 Enhanced 인증 미들웨어
 - User Service의 JWKS 엔드포인트를 통한 JWT 토큰 검증
 - 사용자 컨텍스트를 request.state에 저장
 - 공개 경로는 인증 스킵
 - 토큰 캐싱으로 성능 최적화
 """

 def __init__(self, app: ASGIApp):
 super().__init__(app)

 self.jwt_config = secure_config.jwt_config
 self.user_service_url = secure_config.get_service_url('user_service')

 self.public_paths = [
 "/health", "/metrics", "/docs", "/openapi.json", "/redoc",
 "/api/v1/health", "/api/v1/health/live", "/api/v1/health/ready",
 "/auth/login", "/auth/register", "/auth/refresh", "/auth/logout",
 "/api/v1/auth", "/api/v1/test/health"
 ]
 self.cache_ttl = 300

 # JWKS 클라이언트 초기화
 self.jwks_url = self.jwt_config.jwks_url
 if self.jwks_url:
 self.jwks_client = PyJWKClient(self.jwks_url, cache_keys = True, max_cached_keys = 16)
 logger.info(f"🔧 AuthMiddleware 초기화 - JWKS URL: {self.jwks_url}")
 else:
 self.jwks_client = None
 logger.warning("AuthMiddleware 초기화 - JWKS URL이 설정되지 않았습니다.")

 async def dispatch(self, request: Request, call_next: Callable) -> Response:
 if request.method == "OPTIONS":
 return await call_next(request)

 if request.url.path == "/" or any(request.url.path.startswith(path) for path in self.public_paths):
 return await call_next(request)

 authorization = request.headers.get("Authorization")
 if not authorization or not authorization.startswith("Bearer "):
 return Response('{"detail": "Unauthorized"}', status_code = 401, headers={"WWW-Authenticate": "Bearer"})

 token = authorization.split(" ")[1]

 try:
 redis_client = None
 try:
 container = request.app.state.container
 redis_provider = container.redis_provider()
 redis_client = await redis_provider.provide()
 except Exception as e:
 logger.warning(f"Failed to get Redis client from container: {e}")

 user = await self._get_cached_user(token, redis_client) if redis_client else None

 if not user:
 if not self.jwks_client:
 logger.error("JWKS client not available.")
 return Response('{"detail": "Authentication service not configured"}', status_code = 503)

 user_data = await self._validate_token_with_jwks(token)

 if user_data and isinstance(user_data, dict):
 user_id = user_data.get("user_id")
 if not user_id:
 return Response('{"detail": "Invalid token: missing user_id"}', status_code = 401)

 username = user_data.get("username", user_id)

 user_context_data = {
 "user_id": user_id,
 "username": username,
 "email": user_data.get("email"),
 "roles": user_data.get("roles", []),
 "permissions": user_data.get("permissions", []),
 "metadata": user_data.get("metadata", {})
 }
 user = UserContext(**user_context_data)
 if redis_client:
 await self._cache_user(token, user, redis_client)
 else:
 return Response('{"detail": "Invalid token"}', status_code = 401)

 request.state.user = user
 request.state.user_context = user

 except Exception as e:
 logger.error(f"Authentication error: {e}")
 return Response('{"detail": "Internal server error"}', status_code = 500)

 return await call_next(request)

 async def _get_cached_user(self, token: str, redis_client: redis.Redis) -> Optional[UserContext]:
 try:
 cached = await redis_client.get(f"auth_token:{token}")
 if cached:
 return UserContext.parse_raw(cached)
 except Exception as e:
 logger.error(f"Cache get failed: {e}")
 return None

 async def _cache_user(self, token: str, user: UserContext, redis_client: redis.Redis):
 try:
 await redis_client.setex(f"auth_token:{token}", self.cache_ttl, user.json())
 except Exception as e:
 logger.error(f"Cache set failed: {e}")

 async def _validate_token_with_jwks(self, token: str) -> Optional[Dict[str, Any]]:
 try:
 signing_key = self.jwks_client.get_signing_key_from_jwt(token)

 payload = jwt.decode(
 token,
 signing_key.key,
 algorithms = self.jwt_config.algorithms,
 audience = self.jwt_config.audience,
 issuer = self.jwt_config.issuer,
 options={
 "verify_signature": True,
 "verify_exp": True,
 "verify_iss": True,
 "verify_aud": True
 }
 )

 logger.info(f"🔐 JWKS JWT 검증 성공: user_id={payload.get('sub')}")

 user_id = payload.get("sub") or payload.get("user_id")
 if not user_id:
 logger.error("JWKS JWT 검증 실패: 'sub' 또는 'user_id' 클레임이 없음")
 return None

 scope_str = payload.get("scope", "")
 scopes = scope_str.split() if scope_str else []
 roles = payload.get("roles", [])

 user_data = {
 "user_id": user_id,
 "username": payload.get("username", user_id),
 "email": payload.get("email"),
 "roles": roles,
 "permissions": scopes,
 "metadata": {
 "scopes": scopes,
 "tenant_id": payload.get("tenant_id"),
 "issuer": payload.get("iss"),
 "audience": payload.get("aud")
 }
 }

 return user_data

 except jwt.ExpiredSignatureError:
 logger.error("JWKS JWT 검증 실패: 토큰이 만료됨")
 return None
 except jwt.InvalidTokenError as e:
 logger.error(f"JWKS JWT 검증 실패: 유효하지 않은 토큰 - {e}")
 return None
 except Exception as e:
 logger.error(f"JWKS JWT 검증 실패: {e}")
 return None

def get_current_user(request: Request) -> UserContext:
 if not hasattr(request.state, 'user'):
 raise HTTPException(status_code = 401, detail = "Not authenticated")
 return request.state.user
