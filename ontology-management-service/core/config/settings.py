"""
Centralized configuration management for ontology-management-service
Addresses technical debt: hardcoded values scattered throughout codebase
"""
from typing import Optional

from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
 """Database configuration settings"""

 model_config = SettingsConfigDict(env_prefix = "DB_")

 @validator("terminus_password")
 def validate_terminus_password(cls, v, values):
 """Validate TerminusDB password is set for production"""
 env = values.get("environment", "development")
 if env in ["production", "staging"] and not v:
 raise ValueError(
 "🚨 SECURITY ERROR: TERMINUSDB_ADMIN_PASS is required for production environments. "
 "Set DB_TERMINUS_PASSWORD environment variable."
 )
 return v

 @validator("postgres_password")
 def validate_postgres_password(cls, v, values):
 """Validate PostgreSQL password is set for production"""
 env = values.get("environment", "development")
 if env in ["production", "staging"] and not v:
 raise ValueError(
 "🚨 SECURITY ERROR: PostgreSQL password is required for production environments. "
 "Set DB_POSTGRES_PASSWORD environment variable."
 )
 return v

 # SQLite
 sqlite_path: str = Field(
 default = "./data/oms.db", description = "SQLite database path"
 )

 # PostgreSQL
 postgres_host: str = Field(default = "localhost", description = "PostgreSQL host")
 postgres_port: int = Field(default = 5432, description = "PostgreSQL port")
 postgres_user: str = Field(default = "arrakis_user", description = "PostgreSQL user")
 postgres_password: Optional[str] = Field(
 default = None, description = "PostgreSQL password - REQUIRED for production"
 )
 postgres_database: str = Field(
 default = "arrakis_db", description = "PostgreSQL database"
 )

 # TerminusDB
 terminus_url: str = Field(
 default = "http://localhost:6363", description = "TerminusDB URL"
 )
 terminus_user: str = Field(default = "admin", description = "TerminusDB user")
 terminus_password: Optional[str] = Field(
 default = None, description = "TerminusDB password - REQUIRED for production"
 )
 terminus_organization: str = Field(
 default = "admin", description = "TerminusDB organization"
 )
 terminus_database: str = Field(
 default = "arrakis_db", description = "TerminusDB database"
 )

 # Connection pool
 pool_size: int = Field(default = 20, description = "Connection pool size")
 max_overflow: int = Field(default = 10, description = "Max overflow connections")
 pool_timeout: int = Field(default = 30, description = "Pool timeout in seconds")


class RedisSettings(BaseSettings):
 """Redis configuration settings"""

 model_config = SettingsConfigDict(env_prefix = "REDIS_")

 url: str = Field(default = "redis://localhost:6379/0", description = "Redis URL")
 max_connections: int = Field(default = 50, description = "Max Redis connections")
 socket_timeout: int = Field(default = 5, description = "Socket timeout in seconds")
 socket_connect_timeout: int = Field(
 default = 5, description = "Connect timeout in seconds"
 )
 retry_on_timeout: bool = Field(default = True, description = "Retry on timeout")

 # Cache settings
 cache_ttl: int = Field(default = 300, description = "Default cache TTL in seconds")
 lock_ttl: int = Field(default = 60, description = "Lock TTL in seconds")


class ServiceSettings(BaseSettings):
 """External service configuration"""

 model_config = SettingsConfigDict(env_prefix = "SERVICE_")

 # IAM Service
 iam_url: str = Field(
 default = "http://user-service:8000", description = "IAM service URL"
 )
 iam_verify_ssl: bool = Field(default = True, description = "Verify IAM SSL")
 iam_timeout: int = Field(default = 30, description = "IAM request timeout")

 # Audit Service
 audit_url: str = Field(
 default = "http://audit-service:8000", description = "Audit service URL"
 )
 audit_enabled: bool = Field(default = True, description = "Enable audit logging")

 # NATS
 nats_url: str = Field(default = "nats://localhost:4222", description = "NATS URL")
 nats_cluster_id: str = Field(default = "oms-cluster", description = "NATS cluster ID")

 # WebSocket
 websocket_url: str = Field(
 default = "ws://localhost:8080", description = "WebSocket URL"
 )


class ObservabilitySettings(BaseSettings):
 """Observability configuration"""

 model_config = SettingsConfigDict(env_prefix = "OBSERVABILITY_")

 # OpenTelemetry
 otlp_endpoint: str = Field(default = "localhost:4317", description = "OTLP endpoint")
 otlp_headers: Optional[str] = Field(default = None, description = "OTLP headers")
 service_name: str = Field(
 default = "ontology-management-service", description = "Service name"
 )

 # Metrics
 metrics_enabled: bool = Field(default = True, description = "Enable metrics")
 metrics_port: int = Field(default = 9090, description = "Metrics port")

 # Logging
 log_level: str = Field(default = "INFO", description = "Log level")
 log_format: str = Field(default = "json", description = "Log format")

 # SIEM
 siem_enabled: bool = Field(default = True, description = "Enable SIEM integration")
 siem_endpoint: str = Field(
 default = "http://elasticsearch:9200", description = "SIEM endpoint"
 )
 kafka_bootstrap_servers: str = Field(
 default = "localhost:9092", description = "Kafka servers"
 )


class SecuritySettings(BaseSettings):
 """Security configuration"""

 model_config = SettingsConfigDict(env_prefix = "SECURITY_")

 @validator("jwt_secret")
 def validate_jwt_secret(cls, v, values):
 """Validate JWT secret is set for production"""
 env = values.get("environment", "development")
 if env in ["production", "staging"] and not v:
 raise ValueError(
 "🚨 SECURITY ERROR: JWT secret is required for production environments. "
 "Set SECURITY_JWT_SECRET environment variable with a strong secret key."
 )
 if v and len(v) < 32:
 raise ValueError(
 "🚨 SECURITY ERROR: JWT secret must be at least 32 characters long for security."
 )
 return v

 @validator("encryption_key")
 def validate_encryption_key(cls, v, values):
 """Validate encryption key is set for production"""
 env = values.get("environment", "development")
 if env in ["production", "staging"] and not v:
 raise ValueError(
 "🚨 SECURITY ERROR: Encryption key is required for production environments. "
 "Set SECURITY_ENCRYPTION_KEY environment variable."
 )
 if v and len(v) < 32:
 raise ValueError(
 "🚨 SECURITY ERROR: Encryption key must be at least 32 characters long for security."
 )
 return v

 @validator("cors_origins")
 def validate_cors_origins(cls, v, values):
 """Validate CORS origins are not wildcard in production"""
 env = values.get("environment", "development")
 if env in ["production", "staging"] and "*" in v:
 raise ValueError(
 "🚨 SECURITY ERROR: Wildcard CORS origins are not allowed in production. "
 "Specify explicit origins in SECURITY_CORS_ORIGINS."
 )
 return v

 # JWT
 jwt_secret: Optional[str] = Field(
 default = None, description = "JWT secret key - REQUIRED for production"
 )
 jwt_algorithm: str = Field(default = "HS256", description = "JWT algorithm")
 jwt_issuer: str = Field(default = "arrakis.oms", description = "JWT issuer")
 jwt_audience: str = Field(default = "oms-api", description = "JWT audience")
 access_token_expire_minutes: int = Field(
 default = 30, description = "Access token expiry"
 )

 # Encryption
 encryption_key: Optional[str] = Field(
 default = None, description = "Data encryption key - REQUIRED for production"
 )

 # CORS
 cors_origins: list[str] = Field(
 default = ["http://localhost:3000", "http://localhost:8080"],
 description = "Allowed CORS origins",
 )
 cors_allow_credentials: bool = Field(default = True, description = "Allow credentials")

 # Rate limiting
 rate_limit_enabled: bool = Field(default = True, description = "Enable rate limiting")
 rate_limit_per_minute: int = Field(default = 60, description = "Requests per minute")


class ApplicationSettings(BaseSettings):
 """Application configuration"""

 model_config = SettingsConfigDict(env_prefix = "APP_")

 name: str = Field(
 default = "ontology-management-service", description = "Application name"
 )
 version: str = Field(default = "1.0.0", description = "Application version")
 environment: str = Field(default = "development", description = "Environment")
 debug: bool = Field(
 default = False, description = "Debug mode - auto-disabled in production"
 )

 # API
 api_prefix: str = Field(default = "/api/v1", description = "API prefix")
 docs_url: str = Field(default = "/docs", description = "Docs URL")
 openapi_url: str = Field(default = "/openapi.json", description = "OpenAPI URL")

 # Timeouts
 default_timeout: int = Field(default = 30, description = "Default timeout in seconds")
 long_timeout: int = Field(default = 300, description = "Long operation timeout")

 # Pagination
 default_page_size: int = Field(default = 20, description = "Default page size")
 max_page_size: int = Field(default = 100, description = "Max page size")

 # Circuit breaker
 circuit_breaker_failure_threshold: int = Field(
 default = 5, description = "Failure threshold"
 )
 circuit_breaker_recovery_timeout: int = Field(
 default = 60, description = "Recovery timeout"
 )
 circuit_breaker_expected_exception: Optional[str] = Field(
 default = None, description = "Expected exception"
 )


class Settings(BaseSettings):
 """Main settings aggregator"""

 database: DatabaseSettings = Field(default_factory = DatabaseSettings)
 redis: RedisSettings = Field(default_factory = RedisSettings)
 service: ServiceSettings = Field(default_factory = ServiceSettings)
 observability: ObservabilitySettings = Field(default_factory = ObservabilitySettings)
 security: SecuritySettings = Field(default_factory = SecuritySettings)
 app: ApplicationSettings = Field(default_factory = ApplicationSettings)

 class Config:
 case_sensitive = False
 env_file = ".env"
 env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
 """Get global settings instance"""
 return settings
