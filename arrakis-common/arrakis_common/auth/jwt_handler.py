"""
통합 JWT 처리 모듈
모든 MSA 서비스에서 공통으로 사용하는 JWT 로직

중복된 토큰 관리 로직을 모두 통합하여 일관성 확보:
- 토큰 생성 (Access, Refresh, Short-lived)
- 토큰 검증 및 디코딩
- 스코프 기반 권한 관리
- JWKS 지원
- 보안 강화 기능
"""
import base64
import logging
import os
import re
import secrets
from datetime import datetime, timedelta
from enum import Enum
from functools import lru_cache
from typing import Any, Dict, List, Optional, Union

import httpx
import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from jwt import PyJWKClient

logger = logging.getLogger(__name__)


class TokenType(str, Enum):
    """토큰 타입 정의"""

    ACCESS = "access"
    REFRESH = "refresh"
    SHORT_LIVED = "short_lived"
    SERVICE = "service"


class JWTSecurityLevel(str, Enum):
    """JWT 보안 레벨"""

    BASIC = "basic"
    ENHANCED = "enhanced"
    MAXIMUM = "maximum"


class JWTHandler:
    """JWT 처리를 위한 통합 핸들러"""

    def __init__(
        self,
        algorithm: str = None,
        secret_key: str = None,
        public_key: str = None,
        private_key: str = None,
        issuer: str = None,
        audience: str = None,
        jwks_url: str = None,
        use_jwks: bool = False,
    ):
        self.algorithm = algorithm or os.getenv("JWT_ALGORITHM", "RS256")
        self.issuer = issuer or os.getenv("JWT_ISSUER", "user-service")
        self.audience = audience or os.getenv("JWT_AUDIENCE", "oms")
        self.use_jwks = use_jwks or os.getenv("USE_JWKS", "true").lower() == "true"

        # JWKS URL 설정
        if jwks_url:
            self.jwks_url = jwks_url
        elif os.getenv("USER_SERVICE_URL"):
            self.jwks_url = f"{os.getenv('USER_SERVICE_URL')}/.well-known/jwks.json"
        else:
            self.jwks_url = None

        # 키 설정
        if self.algorithm.startswith("RS"):
            # RSA 알고리즘
            self._setup_rsa_keys(public_key, private_key)
        else:
            # 대칭키 알고리즘
            self.secret_key = secret_key or os.getenv("JWT_SECRET_KEY")
            if not self.secret_key:
                # Generate secure random key if not provided (development only)
                self.secret_key = secrets.token_urlsafe(32)
                logger.warning(
                    "🔧 JWT_SECRET_KEY not set. Generated random key for development. "
                    "Set JWT_SECRET_KEY environment variable for production."
                )

        # JWKS 클라이언트
        self._jwks_client = None
        if self.use_jwks and self.jwks_url:
            try:
                self._jwks_client = PyJWKClient(self.jwks_url, cache_jwk_set=True)
                logger.info(f"JWKS client initialized with URL: {self.jwks_url}")
            except Exception as e:
                logger.warning(f"Failed to initialize JWKS client: {e}")

    def _setup_rsa_keys(self, public_key: str = None, private_key: str = None):
        """RSA 키 설정"""
        # Base64로 인코딩된 키 처리
        if public_key:
            self.public_key = public_key
        elif os.getenv("JWT_PUBLIC_KEY_BASE64"):
            try:
                self.public_key = base64.b64decode(
                    os.getenv("JWT_PUBLIC_KEY_BASE64")
                ).decode("utf-8")
            except Exception:
                self.public_key = os.getenv("JWT_PUBLIC_KEY_BASE64")
        else:
            self.public_key = None

        if private_key:
            self.private_key = private_key
        elif os.getenv("JWT_PRIVATE_KEY_BASE64"):
            try:
                self.private_key = base64.b64decode(
                    os.getenv("JWT_PRIVATE_KEY_BASE64")
                ).decode("utf-8")
            except Exception:
                self.private_key = os.getenv("JWT_PRIVATE_KEY_BASE64")
        else:
            self.private_key = None

        # RSA 키가 없을 경우 테스트용 키 생성 (개발 환경에서만)
        if not self.private_key and not self.public_key:
            if os.getenv("ENVIRONMENT", "development") == "development":
                logger.warning("🔧 RSA 키가 없어 테스트용 키 생성 중...")
                self._generate_test_rsa_keys()

    def _generate_test_rsa_keys(self):
        """테스트용 RSA 키 생성"""
        try:
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric import rsa

            # RSA 키 쌍 생성
            private_key = rsa.generate_private_key(
                public_exponent=65537, key_size=2048, backend=default_backend()
            )

            # 개인키 직렬화
            self.private_key = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )

            # 공개키 직렬화
            public_key = private_key.public_key()
            self.public_key = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )

            logger.info("✅ 테스트용 RSA 키 생성 완료")

        except ImportError:
            logger.error("❌ cryptography 라이브러리가 필요합니다")
            # Fallback to HS256
            self.algorithm = "HS256"
            self.secret_key = secrets.token_urlsafe(32)
            logger.warning("🔄 HS256 알고리즘으로 폴백")

    def create_token(
        self, payload: Dict[str, Any], expires_delta: Optional[timedelta] = None
    ) -> str:
        """JWT 토큰 생성"""
        to_encode = payload.copy()

        # 만료 시간 설정
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)

        to_encode.update(
            {
                "exp": expire,
                "iat": datetime.utcnow(),
                "iss": self.issuer,
                "aud": self.audience,
            }
        )

        # 토큰 생성
        if self.algorithm.startswith("RS") and self.private_key:
            encoded_jwt = jwt.encode(
                to_encode, self.private_key, algorithm=self.algorithm
            )
        else:
            encoded_jwt = jwt.encode(
                to_encode, self.secret_key, algorithm=self.algorithm
            )

        return encoded_jwt

    def decode_token(self, token: str) -> Dict[str, Any]:
        """JWT 토큰 디코드"""
        try:
            # 헤더에서 알고리즘 확인
            unverified_header = jwt.get_unverified_header(token)
            token_algorithm = unverified_header.get("alg", self.algorithm)

            # JWKS 사용 시
            if self.use_jwks and self._jwks_client and token_algorithm.startswith("RS"):
                try:
                    signing_key = self._jwks_client.get_signing_key_from_jwt(token)
                    payload = jwt.decode(
                        token,
                        signing_key.key,
                        algorithms=[token_algorithm],
                        issuer=self.issuer,
                        audience=self.audience,
                    )
                    return payload
                except Exception as e:
                    logger.warning(f"JWKS validation failed: {e}")
                    # Fallback to local key if available

            # 로컬 키 사용
            if token_algorithm.startswith("RS") and self.public_key:
                payload = jwt.decode(
                    token,
                    self.public_key,
                    algorithms=[token_algorithm],
                    issuer=self.issuer,
                    audience=self.audience,
                )
            else:
                payload = jwt.decode(
                    token,
                    self.secret_key,
                    algorithms=[token_algorithm],
                    issuer=self.issuer,
                    audience=self.audience,
                )

            return payload

        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise ValueError(f"Invalid token: {e}")

    def verify_token(self, token: str) -> bool:
        """토큰 유효성 검증"""
        try:
            self.decode_token(token)
            return True
        except (
            jwt.InvalidTokenError,
            jwt.ExpiredSignatureError,
            jwt.InvalidSignatureError,
            ValueError,
        ) as e:
            # Log specific JWT validation failure for security monitoring
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"JWT validation failed: {type(e).__name__}: {e}")
            return False

    # ========== 확장된 토큰 관리 기능들 (중복 제거를 위한 통합) ==========

    def create_access_token(
        self,
        user_data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None,
        include_scopes: bool = True,
        additional_claims: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        액세스 토큰 생성 (user-service의 create_access_token 통합)

        Args:
            user_data: 사용자 정보 (id, username, email, roles, permissions 등)
            expires_delta: 만료 시간
            include_scopes: 스코프 포함 여부
            additional_claims: 추가 클레임
        """
        to_encode = {
            "sub": str(user_data.get("id", user_data.get("user_id", "unknown"))),
            "username": user_data.get("username"),
            "email": user_data.get("email"),
            "type": TokenType.ACCESS.value,
        }

        # 역할과 권한 추가
        if "roles" in user_data:
            to_encode["roles"] = user_data["roles"]
        if "permissions" in user_data:
            to_encode["permissions"] = user_data["permissions"]

        # 스코프 생성 (roles과 permissions 기반)
        if include_scopes:
            scopes = []
            if user_data.get("roles"):
                scopes.extend([f"role:{role}" for role in user_data["roles"]])
            if user_data.get("permissions"):
                scopes.extend([f"perm:{perm}" for perm in user_data["permissions"]])
            to_encode["scopes"] = scopes

        # 추가 클레임
        if additional_claims:
            to_encode.update(additional_claims)

        # 만료 시간 설정
        if not expires_delta:
            expires_delta = timedelta(hours=1)  # 기본 1시간

        return self.create_token(to_encode, expires_delta)

    def create_refresh_token(
        self, user_data: Dict[str, Any], expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        리프레시 토큰 생성 (user-service의 create_refresh_token 통합)

        Args:
            user_data: 사용자 정보
            expires_delta: 만료 시간 (기본 30일)
        """
        to_encode = {
            "sub": str(user_data.get("id", user_data.get("user_id", "unknown"))),
            "username": user_data.get("username"),
            "type": TokenType.REFRESH.value,
        }

        # 만료 시간 설정 (리프레시 토큰은 더 길게)
        if not expires_delta:
            expires_delta = timedelta(days=30)  # 기본 30일

        return self.create_token(to_encode, expires_delta)

    def create_short_lived_token(
        self,
        user_id: str,
        duration_seconds: int = 300,
        purpose: str = "general",
        additional_claims: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        단기 토큰 생성 (user-service의 create_short_lived_token 통합)

        Args:
            user_id: 사용자 ID
            duration_seconds: 지속 시간 (초)
            purpose: 토큰 목적
            additional_claims: 추가 클레임
        """
        to_encode = {
            "sub": str(user_id),
            "type": TokenType.SHORT_LIVED.value,
            "purpose": purpose,
        }

        if additional_claims:
            to_encode.update(additional_claims)

        expires_delta = timedelta(seconds=duration_seconds)
        return self.create_token(to_encode, expires_delta)

    def create_service_token(
        self,
        service_name: str,
        scopes: Optional[List[str]] = None,
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """
        서비스 간 통신용 토큰 생성

        Args:
            service_name: 서비스 이름
            scopes: 허용된 스코프
            expires_delta: 만료 시간
        """
        to_encode = {
            "sub": service_name,
            "type": TokenType.SERVICE.value,
            "service": service_name,
            "is_service_account": True,
        }

        if scopes:
            to_encode["scopes"] = scopes

        if not expires_delta:
            expires_delta = timedelta(hours=24)  # 서비스 토큰은 24시간

        return self.create_token(to_encode, expires_delta)

    def decode_token_with_scopes(self, token: str) -> Dict[str, Any]:
        """
        토큰 디코딩 및 스코프 파싱 (user-service의 decode_token_with_scopes 통합)

        Returns:
            디코딩된 페이로드 (파싱된 스코프 포함)
        """
        payload = self.decode_token(token)

        # 스코프 파싱
        if "scopes" in payload:
            parsed_scopes = {
                "roles": [],
                "permissions": [],
                "raw_scopes": payload["scopes"],
            }

            for scope in payload["scopes"]:
                if scope.startswith("role:"):
                    parsed_scopes["roles"].append(scope[5:])
                elif scope.startswith("perm:"):
                    parsed_scopes["permissions"].append(scope[5:])

            payload["parsed_scopes"] = parsed_scopes

        return payload

    def validate_token_scopes(self, token: str, required_scopes: List[str]) -> bool:
        """
        토큰의 스코프 검증 (user-service의 validate_token_scopes 통합)

        Args:
            token: JWT 토큰
            required_scopes: 필요한 스코프 리스트

        Returns:
            스코프 검증 성공 여부
        """
        try:
            payload = self.decode_token_with_scopes(token)
            token_scopes = payload.get("scopes", [])

            # 모든 필요한 스코프가 토큰에 있는지 확인
            return all(scope in token_scopes for scope in required_scopes)

        except Exception as e:
            logger.warning(f"스코프 검증 실패: {e}")
            return False

    def validate_token_advanced(
        self,
        token: str,
        required_scopes: Optional[List[str]] = None,
        expected_token_type: Optional[TokenType] = None,
        check_expiry: bool = True,
    ) -> Dict[str, Any]:
        """
        고급 토큰 검증 (여러 검증 로직 통합)

        Args:
            token: JWT 토큰
            required_scopes: 필요한 스코프
            expected_token_type: 예상 토큰 타입
            check_expiry: 만료 시간 체크 여부

        Returns:
            검증 결과와 페이로드
        """
        try:
            payload = self.decode_token_with_scopes(token)

            result = {"valid": True, "payload": payload, "errors": []}

            # 토큰 타입 검증
            if expected_token_type:
                token_type = payload.get("type")
                if token_type != expected_token_type.value:
                    result["valid"] = False
                    result["errors"].append(f"잘못된 토큰 타입: {token_type}")

            # 스코프 검증
            if required_scopes:
                if not self.validate_token_scopes(token, required_scopes):
                    result["valid"] = False
                    result["errors"].append("권한 부족")

            # 만료 시간 검증 (이미 decode_token에서 처리됨)
            if check_expiry:
                exp = payload.get("exp")
                if exp and datetime.fromtimestamp(exp) < datetime.utcnow():
                    result["valid"] = False
                    result["errors"].append("토큰 만료")

            return result

        except Exception as e:
            return {"valid": False, "payload": None, "errors": [str(e)]}

    @staticmethod
    def validate_jwt_secret(secret: str, min_length: int = 32) -> bool:
        """
        JWT 시크릿 보안 검증 (user-service의 validate_jwt_secret 통합)

        Args:
            secret: JWT 시크릿
            min_length: 최소 길이

        Returns:
            보안 검증 통과 여부
        """
        if not secret or len(secret) < min_length:
            return False

        # 복잡성 검사
        has_upper = bool(re.search(r"[A-Z]", secret))
        has_lower = bool(re.search(r"[a-z]", secret))
        has_digit = bool(re.search(r"\d", secret))
        has_special = bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', secret))

        # 최소 3가지 문자 유형 포함
        return sum([has_upper, has_lower, has_digit, has_special]) >= 3

    @staticmethod
    def generate_secure_secret(length: int = 64) -> str:
        """
        보안 JWT 시크릿 생성

        Args:
            length: 시크릿 길이

        Returns:
            생성된 보안 시크릿
        """
        return secrets.token_urlsafe(length)

    # ========== 설정 접근자 메서드들 (audit-service 중복 제거) ==========

    def get_jwt_secret(self) -> str:
        """JWT 시크릿 반환 (audit-service의 get_jwt_secret 통합)"""
        return self.secret_key

    def get_jwt_algorithm(self) -> str:
        """JWT 알고리즘 반환 (audit-service의 get_jwt_algorithm 통합)"""
        return self.algorithm

    def get_jwt_issuer(self) -> str:
        """JWT 발급자 반환 (audit-service의 get_jwt_issuer 통합)"""
        return self.issuer

    def get_jwt_audience(self) -> str:
        """JWT 대상자 반환"""
        return self.audience

    def get_jwks_url(self) -> Optional[str]:
        """JWKS URL 반환"""
        return self.jwks_url

    # ========== 토큰 분석 및 디버깅 유틸리티 ==========

    def analyze_token(self, token: str) -> Dict[str, Any]:
        """
        토큰 상세 분석 (디버깅용)

        Args:
            token: 분석할 토큰

        Returns:
            토큰 분석 결과
        """
        try:
            # 헤더 분석
            header = jwt.get_unverified_header(token)

            # 페이로드 분석 (검증 없이)
            unverified_payload = jwt.decode(token, options={"verify_signature": False})

            # 만료 시간 계산
            exp = unverified_payload.get("exp")
            iat = unverified_payload.get("iat")

            exp_dt = datetime.fromtimestamp(exp) if exp else None
            iat_dt = datetime.fromtimestamp(iat) if iat else None

            now = datetime.utcnow()
            is_expired = exp_dt < now if exp_dt else False
            time_to_expiry = exp_dt - now if exp_dt else None

            return {
                "header": header,
                "payload": unverified_payload,
                "issued_at": iat_dt.isoformat() if iat_dt else None,
                "expires_at": exp_dt.isoformat() if exp_dt else None,
                "is_expired": is_expired,
                "time_to_expiry_seconds": time_to_expiry.total_seconds()
                if time_to_expiry
                else None,
                "token_type": unverified_payload.get("type"),
                "subject": unverified_payload.get("sub"),
                "issuer": unverified_payload.get("iss"),
                "audience": unverified_payload.get("aud"),
                "scopes": unverified_payload.get("scopes", []),
            }

        except Exception as e:
            return {"error": str(e), "valid_format": False}

    @classmethod
    @lru_cache(maxsize=1)
    def get_default_handler(cls) -> "JWTHandler":
        """기본 JWT 핸들러 가져오기 (싱글톤)"""
        return cls()


# ========== 편의 함수들 (중복 제거용 전역 접근) ==========

_default_handler = None


def get_jwt_handler() -> JWTHandler:
    """기본 JWT 핸들러 가져오기"""
    global _default_handler
    if _default_handler is None:
        _default_handler = JWTHandler()
    return _default_handler


# 전역 편의 함수들 (기존 중복 코드들을 쉽게 교체하기 위함)


def create_access_token(user_data: Dict[str, Any], **kwargs) -> str:
    """액세스 토큰 생성 (전역 편의 함수)"""
    return get_jwt_handler().create_access_token(user_data, **kwargs)


def create_refresh_token(user_data: Dict[str, Any], **kwargs) -> str:
    """리프레시 토큰 생성 (전역 편의 함수)"""
    return get_jwt_handler().create_refresh_token(user_data, **kwargs)


def create_short_lived_token(user_id: str, **kwargs) -> str:
    """단기 토큰 생성 (전역 편의 함수)"""
    return get_jwt_handler().create_short_lived_token(user_id, **kwargs)


def decode_token(token: str) -> Dict[str, Any]:
    """토큰 디코드 (전역 편의 함수)"""
    return get_jwt_handler().decode_token(token)


def decode_token_with_scopes(token: str) -> Dict[str, Any]:
    """스코프와 함께 토큰 디코드 (전역 편의 함수)"""
    return get_jwt_handler().decode_token_with_scopes(token)


def verify_token(token: str) -> bool:
    """토큰 검증 (전역 편의 함수)"""
    return get_jwt_handler().verify_token(token)


def validate_token_scopes(token: str, required_scopes: List[str]) -> bool:
    """토큰 스코프 검증 (전역 편의 함수)"""
    return get_jwt_handler().validate_token_scopes(token, required_scopes)


def validate_token_advanced(token: str, **kwargs) -> Dict[str, Any]:
    """고급 토큰 검증 (전역 편의 함수)"""
    return get_jwt_handler().validate_token_advanced(token, **kwargs)


def get_jwt_secret() -> str:
    """JWT 시크릿 가져오기 (전역 편의 함수)"""
    return get_jwt_handler().get_jwt_secret()


def get_jwt_algorithm() -> str:
    """JWT 알고리즘 가져오기 (전역 편의 함수)"""
    return get_jwt_handler().get_jwt_algorithm()


def get_jwt_issuer() -> str:
    """JWT 발급자 가져오기 (전역 편의 함수)"""
    return get_jwt_handler().get_jwt_issuer()


def analyze_token(token: str) -> Dict[str, Any]:
    """토큰 분석 (전역 편의 함수)"""
    return get_jwt_handler().analyze_token(token)


# 마이그레이션을 위한 별칭들 (기존 함수명과 호환성)
validate_token = verify_token  # 기존 validate_token 함수들과 호환


async def get_current_user(token: str) -> Dict[str, Any]:
    """현재 사용자 정보 가져오기"""
    payload = decode_token(token)

    user_id = payload.get("sub") or payload.get("user_id")
    if not user_id:
        raise ValueError("Invalid token payload: missing user identifier")

    # 서비스 계정 처리
    if payload.get("is_service_account"):
        return {
            "user_id": user_id,
            "username": payload.get("username", payload.get("service_name")),
            "roles": ["service"],
            "permissions": payload.get("permissions", payload.get("scopes", [])),
            "is_service_account": True,
            "service_name": payload.get("service_name"),
            "client_id": payload.get("client_id"),
        }
    else:
        return {
            "user_id": user_id,
            "username": payload.get("username"),
            "email": payload.get("email"),
            "roles": payload.get("roles", []),
            "permissions": payload.get("permissions", []),
            "session_id": payload.get("sid"),
            "is_service_account": False,
        }
