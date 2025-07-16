"""
공통 설정 클래스
모든 MSA 서비스에서 사용하는 기본 설정
"""
import os
from functools import lru_cache
from typing import Any, Dict, Optional

from pydantic import Field

# Production pydantic settings - required for configuration management
from pydantic_settings import BaseSettings as PydanticBaseSettings


class BaseSettings(PydanticBaseSettings):
    """기본 설정 클래스"""

    # 환경 설정
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")
    service_name: str = Field(default="unknown", env="SERVICE_NAME")

    # 서비스 URL
    user_service_url: str = Field(
        default="http://localhost:8002", env="USER_SERVICE_URL"
    )
    oms_service_url: str = Field(default="http://localhost:8000", env="OMS_SERVICE_URL")
    audit_service_url: str = Field(
        default="http://localhost:8001", env="AUDIT_SERVICE_URL"
    )
    iam_service_url: str = Field(default="http://localhost:8003", env="IAM_SERVICE_URL")

    # 로깅
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")

    class Config:
        env_file = ".env"
        case_sensitive = False

    def is_production(self) -> bool:
        """프로덕션 환경 여부"""
        return self.environment.lower() in ["production", "prod"]

    def is_development(self) -> bool:
        """개발 환경 여부"""
        return self.environment.lower() in ["development", "dev"]

    def get_service_url(self, service: str) -> Optional[str]:
        """서비스 URL 가져오기"""
        service_map = {
            "user": self.user_service_url,
            "oms": self.oms_service_url,
            "audit": self.audit_service_url,
            "iam": self.iam_service_url,
        }
        return service_map.get(service)


class JWTSettings(BaseSettings):
    """JWT 관련 설정"""

    # JWT 기본 설정
    jwt_algorithm: str = Field(default="RS256", env="JWT_ALGORITHM")
    jwt_issuer: str = Field(default="user-service", env="JWT_ISSUER")
    jwt_audience: str = Field(default="oms", env="JWT_AUDIENCE")
    jwt_expiration_minutes: int = Field(default=30, env="JWT_EXPIRATION_MINUTES")

    # JWT 키
    jwt_secret_key: Optional[str] = Field(default=None, env="JWT_SECRET_KEY")
    jwt_public_key_base64: Optional[str] = Field(
        default=None, env="JWT_PUBLIC_KEY_BASE64"
    )
    jwt_private_key_base64: Optional[str] = Field(
        default=None, env="JWT_PRIVATE_KEY_BASE64"
    )

    # JWKS 설정
    use_jwks: bool = Field(default=True, env="USE_JWKS")
    jwks_cache_ttl: int = Field(default=3600, env="JWKS_CACHE_TTL")

    def get_public_key(self) -> Optional[str]:
        """공개 키 가져오기"""
        if self.jwt_public_key_base64:
            import base64

            try:
                return base64.b64decode(self.jwt_public_key_base64).decode("utf-8")
            except:
                return self.jwt_public_key_base64
        return None

    def get_private_key(self) -> Optional[str]:
        """개인 키 가져오기"""
        if self.jwt_private_key_base64:
            import base64

            try:
                return base64.b64decode(self.jwt_private_key_base64).decode("utf-8")
            except:
                return self.jwt_private_key_base64
        return None


class DatabaseSettings(BaseSettings):
    """데이터베이스 관련 설정"""

    # 기본 데이터베이스
    database_url: str = Field(
        default="postgresql://CHANGE_USERNAME:CHANGE_PASSWORD@localhost:5432/db",
        env="DATABASE_URL",
    )

    # 연결 풀 설정
    db_pool_size: int = Field(default=20, env="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=0, env="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(default=30, env="DB_POOL_TIMEOUT")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379", env="REDIS_URL")
    redis_pool_size: int = Field(default=10, env="REDIS_POOL_SIZE")

    # TerminusDB (OMS용)
    terminus_server: Optional[str] = Field(default=None, env="TERMINUS_SERVER")
    terminus_db: Optional[str] = Field(default=None, env="TERMINUS_DB")
    terminus_user: Optional[str] = Field(default=None, env="TERMINUS_USER")
    terminus_password: Optional[str] = Field(default=None, env="TERMINUS_PASSWORD")

    def get_sqlalchemy_database_url(self) -> str:
        """SQLAlchemy용 데이터베이스 URL"""
        return self.database_url

    def get_async_database_url(self) -> str:
        """비동기 데이터베이스 URL"""
        if "postgresql://" in self.database_url:
            return self.database_url.replace("postgresql://", "postgresql+asyncpg://")
        return self.database_url


class SecuritySettings(BaseSettings):
    """보안 관련 설정"""

    # CORS
    cors_origins: str = Field(default="*", env="CORS_ORIGINS")
    cors_credentials: bool = Field(default=True, env="CORS_CREDENTIALS")

    # Rate Limiting
    rate_limit_enabled: bool = Field(default=True, env="RATE_LIMIT_ENABLED")
    rate_limit_requests: int = Field(default=100, env="RATE_LIMIT_REQUESTS")
    rate_limit_window: int = Field(default=60, env="RATE_LIMIT_WINDOW")

    # 암호화
    encryption_key: Optional[str] = Field(default=None, env="ENCRYPTION_KEY")

    # 세션
    session_secret_key: str = Field(
        default="PLACEHOLDER_CHANGE_IN_PRODUCTION", env="SESSION_SECRET_KEY"
    )
    session_expire_minutes: int = Field(default=1440, env="SESSION_EXPIRE_MINUTES")

    def get_cors_origins_list(self) -> list:
        """CORS 오리진 리스트"""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]


class ServiceSettings(BaseSettings):
    """서비스별 설정 (상속용)"""

    # 서비스 검색
    enable_service_discovery: bool = Field(
        default=False, env="ENABLE_SERVICE_DISCOVERY"
    )
    consul_host: Optional[str] = Field(default=None, env="CONSUL_HOST")
    consul_port: Optional[int] = Field(default=8500, env="CONSUL_PORT")

    # 메시징
    nats_url: Optional[str] = Field(default=None, env="NATS_URL")
    kafka_bootstrap_servers: Optional[str] = Field(
        default=None, env="KAFKA_BOOTSTRAP_SERVERS"
    )

    # 모니터링
    enable_metrics: bool = Field(default=True, env="ENABLE_METRICS")
    metrics_port: int = Field(default=9090, env="METRICS_PORT")

    # 트레이싱
    enable_tracing: bool = Field(default=False, env="ENABLE_TRACING")
    jaeger_host: Optional[str] = Field(default=None, env="JAEGER_HOST")
    jaeger_port: Optional[int] = Field(default=6831, env="JAEGER_PORT")


# 전역 설정 인스턴스
_settings: Optional[BaseSettings] = None


@lru_cache()
def get_settings() -> BaseSettings:
    """설정 인스턴스 가져오기 (싱글톤)"""
    global _settings
    if _settings is None:
        _settings = BaseSettings()
    return _settings


@lru_cache()
def get_jwt_settings() -> JWTSettings:
    """JWT 설정 가져오기"""
    return JWTSettings()


@lru_cache()
def get_database_settings() -> DatabaseSettings:
    """데이터베이스 설정 가져오기"""
    return DatabaseSettings()


@lru_cache()
def get_security_settings() -> SecuritySettings:
    """보안 설정 가져오기"""
    return SecuritySettings()


# 환경 변수 헬퍼 함수들
def get_env(key: str, default: Any = None) -> Any:
    """환경 변수 가져오기"""
    return os.getenv(key, default)


def is_production() -> bool:
    """프로덕션 환경 여부"""
    return get_settings().is_production()


def is_development() -> bool:
    """개발 환경 여부"""
    return get_settings().is_development()
