"""Configuration management system"""

import json
import os
from functools import lru_cache
from typing import Any, Dict, Optional, Type

import yaml
from pydantic import Field, validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class YamlConfigSettingsSource(PydanticBaseSettingsSource):
    """
    A settings source that loads variables from a YAML file
    at a specified path.
    """

    def __init__(self, settings_cls: Type[BaseSettings], yaml_file_path: str):
        super().__init__(settings_cls)
        self.yaml_file_path = yaml_file_path

    def get_field_value(self, field, field_name):
        # This source is designed to load a whole file content into one field
        return None

    def __call__(self) -> Dict[str, Any]:
        if not os.path.exists(self.yaml_file_path):
            return {}
        with open(self.yaml_file_path, "r") as f:
            return yaml.safe_load(f) or {}


class TerminusDBConfig(BaseSettings):
 """TerminusDB configuration"""

 endpoint: str = Field(
 default = "http://localhost:6363", validation_alias = "TERMINUSDB_ENDPOINT"
 )
 team: str = Field(default = "admin", validation_alias = "TERMINUSDB_TEAM")
 db: str = Field(default = "arrakis_db", validation_alias = "TERMINUSDB_DB")
 user: str = Field(default = "admin", validation_alias = "TERMINUSDB_USER")
 key: Optional[str] = Field(
 default = None,
 validation_alias = "TERMINUSDB_ADMIN_PASS",
 description = "TerminusDB admin password - REQUIRED for production",
 )

 @validator("key")
 def validate_key(cls, v):
 """Validate TerminusDB key is set for production"""
 env = os.getenv("ENVIRONMENT", "development")
 if env in ["production", "staging"] and not v:
 raise ValueError(
 "🚨 SECURITY ERROR: TERMINUSDB_ADMIN_PASS is required for production environments. "
 "Set TERMINUSDB_ADMIN_PASS environment variable."
 )
 return v

 # Cache settings
 lru_cache_size: int = Field(
 default = 500000000,
 validation_alias = "TERMINUSDB_LRU_CACHE_SIZE",
 description = "Size of TerminusDB's internal LRU cache in bytes.",
 )
 cache_enabled: bool = Field(
 default = True,
 validation_alias = "TERMINUSDB_CACHE_ENABLED",
 description = "Enable/disable TerminusDB's internal cache.",
 )

 # mTLS settings
 use_mtls: bool = Field(
 default = False,
 validation_alias = "TERMINUSDB_USE_MTLS",
 description = "Enable/disable mTLS for TerminusDB connection.",
 )
 cert_path: Optional[str] = Field(
 default = None,
 validation_alias = "TERMINUSDB_CERT_PATH",
 description = "Path to client certificate for mTLS.",
 )
 key_path: Optional[str] = Field(
 default = None,
 validation_alias = "TERMINUSDB_KEY_PATH",
 description = "Path to client key for mTLS.",
 )
 ca_path: Optional[str] = Field(
 default = None,
 validation_alias = "TERMINUSDB_CA_PATH",
 description = "Path to CA certificate for mTLS.",
 )

 # Connection pool settings (via httpx.Limits)
 max_connections: int = Field(default = 20, validation_alias = "DB_MAX_CONNECTIONS")
 min_connections: int = Field(default = 5, validation_alias = "DB_MIN_CONNECTIONS")
 max_idle_time: int = Field(default = 300, validation_alias = "DB_MAX_IDLE_TIME")
 connection_timeout: int = Field(
 default = 30, validation_alias = "DB_CONNECTION_TIMEOUT"
 )

 model_config = SettingsConfigDict(env_prefix = "TERMINUSDB_")


class PostgresConfig(BaseSettings):
 """PostgreSQL configuration"""

 host: str = Field(default = "localhost", validation_alias = "POSTGRES_HOST")
 port: int = Field(default = 5432, validation_alias = "POSTGRES_PORT")
 user: str = Field(default = "arrakis_user", validation_alias = "POSTGRES_USER")
 password: Optional[str] = Field(
 default = None,
 validation_alias = "POSTGRES_PASSWORD",
 description = "PostgreSQL password - REQUIRED for production",
 )
 database: str = Field(default = "arrakis_db", validation_alias = "POSTGRES_DB")

 @validator("password")
 def validate_password(cls, v):
 """Validate PostgreSQL password is set for production"""
 env = os.getenv("ENVIRONMENT", "development")
 if env in ["production", "staging"] and not v:
 raise ValueError(
 "🚨 SECURITY ERROR: PostgreSQL password is required for production environments. "
 "Set POSTGRES_PASSWORD environment variable."
 )
 return v

 model_config = SettingsConfigDict(env_prefix = "POSTGRES_")


# SQLiteConfig removed - PostgreSQL-only architecture


class EventConfig(BaseSettings):
 """Event system configuration"""

 broker_url: str = Field(
 default = "redis://localhost:6379", validation_alias = "EVENT_BROKER_URL"
 )
 max_retries: int = Field(default = 3, validation_alias = "EVENT_MAX_RETRIES")
 retry_delay: int = Field(default = 1000, validation_alias = "EVENT_RETRY_DELAY")

 model_config = SettingsConfigDict(env_prefix = "EVENT_")


class ServiceConfig(BaseSettings):
 """Service-level configuration"""

 name: str = Field(default = "oms-monolith", validation_alias = "SERVICE_NAME")
 log_level: str = Field(default = "INFO", validation_alias = "LOG_LEVEL")
 debug: bool = Field(default = False, validation_alias = "DEBUG")
 environment: str = Field(default = "development", validation_alias = "ENVIRONMENT")
 resilience_timeout: float = Field(
 default = 0.5,
 validation_alias = "RESILIENCE_TIMEOUT",
 description = "Default timeout in seconds for resilient operations",
 )

 model_config = SettingsConfigDict(env_prefix = "SERVICE_")


class UserServiceConfig(BaseSettings):
 """User Service configuration"""

 url: str = Field(
 default = "http://user-service:8000", validation_alias = "USER_SERVICE_URL"
 )

 model_config = SettingsConfigDict(env_prefix = "USER_SERVICE_")


class LockConfig(BaseSettings):
 """Distributed Lock configuration"""

 backend: str = Field(
 default = "redis",
 validation_alias = "LOCK_BACKEND",
 description = "Lock backend (redis, memory)",
 )
 redis_url: str = Field(
 default = "redis://localhost:6379/1", validation_alias = "LOCK_REDIS_URL"
 )
 namespace: str = Field(default = "oms:locks", validation_alias = "LOCK_NAMESPACE")
 ttl: int = Field(
 default = 300,
 validation_alias = "LOCK_TTL_SECONDS",
 description = "Default lock TTL in seconds",
 )
 max_wait: int = Field(
 default = 30,
 validation_alias = "LOCK_MAX_WAIT_SECONDS",
 description = "Max time to wait for a lock",
 )

 model_config = SettingsConfigDict(env_prefix = "LOCK_")


class RedisConfig(BaseSettings):
 """Redis configuration"""

 host: str = Field(default = "localhost", validation_alias = "REDIS_HOST")
 port: int = Field(default = 6379, validation_alias = "REDIS_PORT")
 db: int = Field(default = 0, validation_alias = "REDIS_DB")
 password: Optional[str] = Field(default = None, validation_alias = "REDIS_PASSWORD")
 username: Optional[str] = Field(default = None, validation_alias = "REDIS_USERNAME")
 ssl: bool = Field(default = False, validation_alias = "REDIS_SSL")

 # Connection pool settings
 max_connections: int = Field(default = 50, validation_alias = "REDIS_MAX_CONNECTIONS")
 socket_timeout: float = Field(default = 5.0, validation_alias = "REDIS_SOCKET_TIMEOUT")

 # Cluster/Sentinel settings
 cluster_mode: bool = Field(default = False, validation_alias = "REDIS_CLUSTER_MODE")
 sentinel_mode: bool = Field(default = False, validation_alias = "REDIS_SENTINEL_MODE")
 sentinel_service: str = Field(
 default = "mymaster", validation_alias = "REDIS_SENTINEL_SERVICE"
 )

 model_config = SettingsConfigDict(env_prefix = "REDIS_")


class CircuitBreakerConfig(BaseSettings):
 """Circuit Breaker configuration"""

 failure_threshold: int = Field(
 default = 5, validation_alias = "CIRCUIT_BREAKER_FAILURE_THRESHOLD"
 )
 success_threshold: int = Field(
 default = 3, validation_alias = "CIRCUIT_BREAKER_SUCCESS_THRESHOLD"
 )
 timeout_seconds: float = Field(
 default = 60, validation_alias = "CIRCUIT_BREAKER_TIMEOUT_SECONDS"
 )
 error_rate_threshold: float = Field(
 default = 0.5, validation_alias = "CIRCUIT_BREAKER_ERROR_RATE_THRESHOLD"
 )
 window_size: int = Field(default = 60,
     validation_alias = "CIRCUIT_BREAKER_WINDOW_SIZE")
 half_open_max_calls: int = Field(
 default = 3, validation_alias = "CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS"
 )

 model_config = SettingsConfigDict(env_prefix = "CIRCUIT_BREAKER_")


class AppConfig(BaseSettings):
 """Application configuration"""

 terminusdb: Optional[TerminusDBConfig] = Field(default_factory = TerminusDBConfig)
 postgres: Optional[PostgresConfig] = Field(default_factory = PostgresConfig)
 # sqlite: SQLite support removed - PostgreSQL-only architecture

 event: EventConfig = Field(default_factory = EventConfig)
 service: ServiceConfig = Field(default_factory = ServiceConfig)
 user_service: UserServiceConfig = Field(default_factory = UserServiceConfig)
 lock: LockConfig = Field(default_factory = LockConfig)
 redis: Optional[RedisConfig] = Field(default_factory = RedisConfig)
 circuit_breaker: CircuitBreakerConfig = Field(default_factory = CircuitBreakerConfig)
 scope_mapping: Dict[str, Any] = Field(default_factory = dict)

 def __init__(self, **values: Any):
 super().__init__(**values)
 self._load_yaml_configs()

 def _load_yaml_configs(self):
 """Load additional configurations from YAML files."""
 # Load scope mapping
 scope_config_path = "config/scope_mapping.yaml"
 if os.path.exists(scope_config_path):
 with open(scope_config_path, "r") as f:
 self.scope_mapping = yaml.safe_load(f) or {}

 model_config = SettingsConfigDict(
 env_file = ".env", env_file_encoding = "utf-8", extra = "ignore"
 )


@lru_cache()
def get_config() -> AppConfig:
 """Get cached configuration instance"""
 return AppConfig()
