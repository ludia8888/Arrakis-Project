"""
Enhanced Authentication Middleware
User Service와 연동하여 JWT 토큰 검증 및 사용자 컨텍스트 주입

DESIGN INTENT - AUTHENTICATION LAYER:
This middleware handles ONLY authentication (who you are), NOT authorization (what you can do).
It operates as the first security layer in the middleware stack.

SEPARATION OF CONCERNS:
1. AuthMiddleware (THIS): Validates identity, creates user context
2. RBACMiddleware: Checks role-based permissions
3. AuditMiddleware: Logs security-relevant actions

WHY SEPARATE AUTH FROM RBAC:
- Single Responsibility: Auth = Identity, RBAC = Permissions
- Flexibility: Can swap auth methods (JWT, OAuth, SAML) without touching permissions
- Performance: Skip RBAC checks for public endpoints after auth
- Testing: Test authentication and authorization independently
- Compliance: Different audit requirements for auth vs access

MIDDLEWARE EXECUTION ORDER:
1. AuthMiddleware → Validates token, sets request.state.user
2. RBACMiddleware → Reads request.state.user, checks permissions
3. AuditMiddleware → Logs the authenticated action

ARCHITECTURE BENEFITS:
- Clean separation allows different caching strategies per layer
- Auth tokens can be cached longer than permission checks
- Failed auth stops the request early (fail-fast)
- Each middleware can be toggled on/off independently

USE THIS FOR:
- JWT token validation
- Session management
- User context injection
- Public path handling

NOT FOR:
- Permission checks (use RBACMiddleware)
- Access control lists (use RBACMiddleware)
- Audit logging (use AuditMiddleware)

Related modules:
- middleware/rbac_middleware.py: Role-based access control
- middleware/audit_middleware.py: Security audit logging
- core/auth/unified_auth.py: Core authentication logic
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

from core.auth import UserContext
from bootstrap.config import get_config
from middleware.circuit_breaker import CircuitBreakerGroup, CircuitBreakerError
from common_logging.setup import get_logger
from config.secure_config import secure_config

logger = get_logger(__name__)

class AuthMiddleware(BaseHTTPMiddleware):
    """
    Enhanced 인증 미들웨어
    - User Service를 통한 JWT 토큰 검증
    - 사용자 컨텍스트를 request.state에 저장
    - 공개 경로는 인증 스킵
    - 토큰 캐싱으로 성능 최적화
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        
        # 보안 설정 관리자에서 설정 조회
        self.jwt_config = secure_config.jwt_config
        self.user_service_url = secure_config.get_service_url('user_service')
        self.client = httpx.AsyncClient(timeout=5.0)
        
        self.public_paths = [
            "/health", "/metrics", "/docs", "/openapi.json", "/redoc",
            "/api/v1/health", "/api/v1/health/live", "/api/v1/health/ready",
            "/auth/login", "/auth/register", "/auth/refresh", "/auth/logout",
            "/api/v1/auth"  # Allow all auth routes
        ]
        self.cache_ttl = 300
        
        # JWKS 설정
        self.jwks_url = self.jwt_config.jwks_url
        self.jwks_cache = {}
        self.jwks_cache_ttl = self.jwt_config.cache_ttl
        
        logger.info(f"🔧 AuthMiddleware 초기화 - JWKS URL: {self.jwks_url}")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)

        if request.url.path == "/" or any(request.url.path.startswith(path) for path in self.public_paths):
            return await call_next(request)

        authorization = request.headers.get("Authorization")
        if not authorization or not authorization.startswith("Bearer "):
            return Response('{"detail": "Unauthorized"}', status_code=401, headers={"WWW-Authenticate": "Bearer"})
        
        token = authorization.split(" ")[1]

        try:
            # Get Redis client from container
            redis_client = None
            try:
                container = request.app.state.container
                redis_provider = container.redis_provider()
                redis_client = await redis_provider.provide()
            except Exception as e:
                logger.warning(f"Failed to get Redis client from container: {e}")
                redis_client = None
                
            user = await self._get_cached_user(token, redis_client) if redis_client else None

            if not user:
                user_data = None
                
                # JWKS 패턴으로 토큰 검증
                try:
                    user_data = await self._validate_token_with_jwks(token)
                except Exception as e:
                    logger.error(f"JWKS token validation failed: {e}")
                    # Fallback to user service validation
                    try:
                        container = request.app.state.container
                        cb_group: CircuitBreakerGroup = container.circuit_breaker_provider()
                        user_service_breaker = cb_group.get_breaker("user-service")
                        if user_service_breaker:
                            user_data = await user_service_breaker.call(self._validate_token, token)
                        else:
                            logger.warning("user-service circuit breaker not found. Calling service directly.")
                            user_data = await self._validate_token(token)
                    except CircuitBreakerError as e:
                        logger.error(f"Circuit breaker open for user-service: {e}")
                        return Response('{"detail": "User service unavailable"}', status_code=503)
                    except (AttributeError, KeyError):
                        logger.warning("Circuit breaker not in app state. Calling service directly.")
                        user_data = await self._validate_token(token)

                if user_data and isinstance(user_data, dict):
                    # Ensure required fields are present for UserContext
                    user_id = user_data.get("user_id")
                    if not user_id:
                        return Response('{"detail": "Invalid token: missing user_id"}', status_code=401)
                    
                    username = user_data.get("username", user_id) # Default username to user_id if missing
                    
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
                    return Response('{"detail": "Invalid token"}', status_code=401)
            
            request.state.user = user
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return Response('{"detail": "Internal server error"}', status_code=500)

        return await call_next(request)
    
    async def _get_cached_user(self, token: str, redis_client: redis.Redis) -> Optional[UserContext]:
        """Get user from Redis cache"""
        try:
            cached = await redis_client.get(f"auth_token:{token}")
            if cached:
                return UserContext.parse_raw(cached)
        except Exception as e:
            logger.error(f"Cache get failed: {e}")
        return None
    
    async def _cache_user(self, token: str, user: UserContext, redis_client: redis.Redis):
        """Cache user context in Redis"""
        try:
            await redis_client.setex(f"auth_token:{token}", self.cache_ttl, user.json())
        except Exception as e:
            logger.error(f"Cache set failed: {e}")

    async def _validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validates the JWT by calling the User Service."""
        headers = {"Authorization": f"Bearer {token}"}
        logger.info(f"AuthMiddleware: Validating token with User Service: {self.user_service_url}")
        try:
            res = await self.client.get(f"{self.user_service_url}/auth/account/userinfo", headers=headers)
            logger.info(f"AuthMiddleware: User Service response status: {res.status_code}")
            res.raise_for_status()
            data = res.json()
            logger.info(f"AuthMiddleware: Token validation successful for user: {data.get('user_id')}")
            return {
                "user_id": data.get("user_id"),
                "username": data.get("username") or data.get("user_id"), # Fallback for username
                "email": data.get("email"),
                "roles": data.get("roles", []),
                "permissions": data.get("scopes", []),
                "metadata": {
                    "scopes": data.get("scopes", [])
                }
            }
        except httpx.RequestError as e:
            logger.error(f"AuthMiddleware: Error calling user-service: {e}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"AuthMiddleware: User Service HTTP error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"AuthMiddleware: Token validation failed: {e}")
            return None

    async def _validate_token_with_jwks(self, token: str) -> Optional[Dict[str, Any]]:
        """
        진짜 JWKS 패턴으로 JWT 토큰 검증
        User Service의 JWKS 엔드포인트에서 공개키를 가져와 토큰을 검증합니다.
        MSA 원칙: OMS는 키를 소유하지 않고, User Service만 믿습니다.
        """
        import jwt
        from jwt import PyJWKClient
        import time
        
        try:
            # 진짜 JWKS 클라이언트: User Service의 JWKS 엔드포인트 호출
            jwks_client = PyJWKClient(
                self.jwks_url,  # http://user-service:8000/.well-known/jwks.json
                cache_keys=True,
                max_cached_keys=16
            )
            
            logger.debug(f"🔍 User Service JWKS에서 공개키 가져오기: {self.jwks_url}")
            
            # 토큰 헤더에서 kid 추출하고 User Service에서 해당 키 가져오기
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            
            # 토큰 검증 (User Service의 공개키 사용)
            payload = jwt.decode(
                token,
                signing_key.key,  # User Service에서 가져온 실제 공개키
                algorithms=self.jwt_config.algorithms,
                audience=self.jwt_config.audience,
                issuer=self.jwt_config.issuer,
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iss": True,
                    "verify_aud": True
                }
            )
            
            logger.info(f"🔐 JWKS JWT 검증 성공: user_id={payload.get('sub')}")
            
            # 토큰에서 사용자 정보 추출
            user_id = payload.get("sub") or payload.get("user_id")
            if not user_id:
                logger.error("JWKS JWT 검증 실패: 'sub' 또는 'user_id' 클레임이 없음")
                return None
            
            # scope 문자열을 권한 리스트로 변환
            scope_str = payload.get("scope", "")
            scopes = scope_str.split() if scope_str else []
            roles = payload.get("roles", [])
            
            # 사용자 데이터 구성
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
            
            logger.debug(f"🔐 JWKS JWT 검증 - 사용자 데이터: {user_data}")
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
    """
    현재 요청의 사용자 정보 반환
    FastAPI 의존성으로 사용
    """
    if not hasattr(request.state, 'user'):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return request.state.user