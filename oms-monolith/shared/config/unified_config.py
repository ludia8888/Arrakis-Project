"""
Unified Configuration Service - 엔터프라이즈 레벨 통합 설정 관리
모든 설정을 중앙에서 관리하고 환경별로 구성
"""
import json
import logging
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from functools import lru_cache
from shared.utils.logger import get_logger
from shared.exceptions import OntologyException
from shared.config.unified_env import unified_env, ConfigurationError
logger = get_logger(__name__)

class Environment(str, Enum):
    """실행 환경"""
    DEVELOPMENT = 'development'
    STAGING = 'staging'
    PRODUCTION = 'production'
    TEST = 'test'

class ConfigurationError(OntologyException):
    """설정 오류"""
    pass

@dataclass
class DatabaseConfig:
    """데이터베이스 설정"""
    terminus_endpoint: str = ''
    terminus_username: str = 'admin'
    terminus_password: str = 'root'
    terminus_organization: str = 'admin'
    terminus_db: str = 'oms'
    terminus_key: str = 'root'
    terminus_connection_pool_size: int = 10
    terminus_timeout: int = 30
    redis_sentinels: List[str] = field(default_factory=list)
    redis_master_name: str = 'mymaster'
    redis_password: Optional[str] = None
    redis_db: int = 0
    redis_decode_responses: bool = True
    redis_health_check_interval: int = 30
    cache_type: str = 'redis'
    cache_ttl: int = 3600
    cache_max_size: int = 1000

@dataclass
class SecurityConfig:
    """보안 설정"""
    jwt_secret_key: str = ''
    jwt_algorithm: str = 'HS256'
    jwt_expiration_minutes: int = 60
    mtls_enabled: bool = False
    mtls_cert_path: Optional[str] = None
    mtls_key_path: Optional[str] = None
    mtls_ca_path: Optional[str] = None
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 60
    rate_limit_burst_size: int = 10
    circuit_breaker_enabled: bool = True
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_success_threshold: int = 3
    circuit_breaker_timeout_seconds: int = 60

@dataclass
class MessagingConfig:
    """메시징 설정"""
    nats_enabled: bool = True
    nats_servers: List[str] = field(default_factory=lambda: ['nats://localhost:4222'])
    nats_stream_name: str = 'oms-events'
    nats_durable_name: str = 'oms-consumer'
    nats_max_reconnects: int = 10
    eventbridge_enabled: bool = False
    eventbridge_bus_name: str = 'default'
    eventbridge_source: str = 'oms'

@dataclass
class MonitoringConfig:
    """모니터링 설정"""
    metrics_enabled: bool = True
    metrics_export_interval: int = 60
    prometheus_port: int = 9090
    log_level: str = 'INFO'
    log_format: str = 'json'
    log_file: Optional[str] = None
    tracing_enabled: bool = False
    jaeger_endpoint: Optional[str] = None
    trace_sample_rate: float = 0.1

@dataclass
class ApplicationConfig:
    """애플리케이션 설정"""
    app_name: str = 'oms-monolith'
    app_version: str = '2.0.1'
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    api_host: str = '0.0.0.0'
    api_port: int = 8000
    api_workers: int = 4
    api_cors_enabled: bool = True
    api_cors_origins: List[str] = field(default_factory=lambda: ['*'])
    graphql_enabled: bool = True
    graphql_playground_enabled: bool = True
    graphql_introspection_enabled: bool = True
    graphql_max_depth: int = 10
    graphql_max_complexity: int = 1000

@dataclass
class UnifiedConfig:
    """통합 설정"""
    app: ApplicationConfig = field(default_factory=ApplicationConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    messaging: MessagingConfig = field(default_factory=MessagingConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    custom: Dict[str, Any] = field(default_factory=dict)

class UnifiedConfigService:
    """
    통합 설정 서비스
    
    모든 설정의 로드, 검증, 관리를 담당하는 중앙 서비스
    - 환경 변수 우선
    - 설정 파일 지원 (JSON, YAML)
    - 동적 설정 업데이트
    - 설정 검증
    """
    _instance: Optional['UnifiedConfigService'] = None
    _config: Optional[UnifiedConfig] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._config is None:
            self._config = self._load_config()

    def _load_config(self) -> UnifiedConfig:
        """설정 로드"""
        config = UnifiedConfig()
        self._load_from_env(config)
        config_file = unified_env.get('CONFIG_FILE')
        if config_file and Path(config_file).exists():
            self._load_from_file(config, config_file)
        self._apply_environment_defaults(config)
        self._validate_config(config)
        logger.info(f'Configuration loaded for environment: {config.app.environment}')
        return config

    def _load_from_env(self, config: UnifiedConfig) -> None:
        """환경 변수에서 설정 로드"""
        config.app.environment = Environment(unified_env.get('ENVIRONMENT').lower())
        config.app.debug = unified_env.get('DEBUG').lower() == 'true'
        config.app.api_host = unified_env.get('API_HOST')
        config.app.api_port = int(unified_env.get('API_PORT'))
        config.database.terminus_endpoint = unified_env.get('TERMINUS_DB_ENDPOINT')
        config.database.terminus_username = unified_env.get('TERMINUS_DB_USER')
        config.database.terminus_password = unified_env.get('TERMINUS_DB_PASSWORD')
        config.database.terminus_organization = unified_env.get('TERMINUS_ORGANIZATION')
        config.database.terminus_db = unified_env.get('TERMINUS_DB')
        config.database.terminus_key = unified_env.get('TERMINUS_DB_KEY')
        sentinels = unified_env.get('REDIS_SENTINELS')
        if sentinels:
            config.database.redis_sentinels = [s.strip() for s in sentinels.split(',')]
        config.database.redis_master_name = unified_env.get('REDIS_MASTER_NAME')
        config.database.redis_password = unified_env.get('REDIS_PASSWORD')
        config.database.redis_db = int(unified_env.get('REDIS_DB'))
        config.security.jwt_secret_key = unified_env.get('JWT_SECRET_KEY')
        config.security.mtls_enabled = unified_env.get('MTLS_ENABLED').lower() == 'true'
        config.messaging.nats_enabled = unified_env.get('NATS_ENABLED').lower() == 'true'
        nats_servers = unified_env.get('NATS_SERVERS')
        if nats_servers:
            config.messaging.nats_servers = [s.strip() for s in nats_servers.split(',')]
        config.monitoring.log_level = unified_env.get('LOG_LEVEL')
        config.monitoring.log_format = unified_env.get('LOG_FORMAT')
        config.monitoring.metrics_enabled = unified_env.get('METRICS_ENABLED').lower() == 'true'

    def _load_from_file(self, config: UnifiedConfig, file_path: str) -> None:
        """파일에서 설정 로드"""
        try:
            path = Path(file_path)
            if path.suffix == '.json':
                with open(path, 'r') as f:
                    data = json.load(f)
            elif path.suffix in ['.yaml', '.yml']:
                import yaml
                with open(path, 'r') as f:
                    data = yaml.safe_load(f)
            else:
                raise ConfigurationError(f'Unsupported config file format: {path.suffix}')
            self._merge_config(config, data)
            logger.info(f'Configuration loaded from file: {file_path}')
        except (OSError, json.JSONDecodeError, ValueError) as e:
            logger.error(f'Failed to load config file: {e}')
            raise ConfigurationError(f'Failed to load config file: {e}')
        except ImportError as e:
            logger.error(f'YAML module not available: {e}')
            raise ConfigurationError(f'YAML module not available: {e}')

    def _merge_config(self, config: UnifiedConfig, data: Dict[str, Any]) -> None:
        """설정 병합"""
        for section in ['app', 'database', 'security', 'messaging', 'monitoring']:
            if section in data:
                section_config = getattr(config, section)
                for key, value in data[section].items():
                    if hasattr(section_config, key):
                        setattr(section_config, key, value)
        if 'custom' in data:
            config.custom.update(data['custom'])

    def _apply_environment_defaults(self, config: UnifiedConfig) -> None:
        """환경별 기본값 적용"""
        if config.app.environment == Environment.PRODUCTION:
            config.app.debug = False
            config.app.graphql_playground_enabled = False
            config.app.graphql_introspection_enabled = False
            config.monitoring.log_level = 'WARNING'
            config.monitoring.log_format = 'json'
            config.security.rate_limit_enabled = True
            config.security.circuit_breaker_enabled = True
        elif config.app.environment == Environment.DEVELOPMENT:
            config.app.debug = True
            config.monitoring.log_format = 'text'
            config.monitoring.trace_sample_rate = 1.0

    def _validate_config(self, config: UnifiedConfig) -> None:
        """설정 검증"""
        errors = []
        if not config.database.terminus_endpoint:
            errors.append('TerminusDB endpoint is required')
        if config.security.jwt_secret_key == '':
            if config.app.environment == Environment.PRODUCTION:
                errors.append('JWT secret key is required in production')
        if config.security.mtls_enabled:
            if not all([config.security.mtls_cert_path, config.security.mtls_key_path, config.security.mtls_ca_path]):
                errors.append('mTLS paths are required when mTLS is enabled')
        if errors:
            raise ConfigurationError(f"Configuration validation failed: {', '.join(errors)}")

    @property
    def config(self) -> UnifiedConfig:
        """현재 설정 반환"""
        return self._config

    def get(self, path: str, default: Any=None) -> Any:
        """
        점 표기법으로 설정 값 조회
        
        예: config.get("database.terminus_endpoint")
        """
        parts = path.split('.')
        value = self._config
        try:
            for part in parts:
                if hasattr(value, part):
                    value = getattr(value, part)
                elif isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return default
            return value
        except (AttributeError, KeyError, TypeError):
            return default

    def set(self, path: str, value: Any) -> None:
        """
        점 표기법으로 설정 값 변경
        
        예: config.set("database.cache_ttl", 7200)
        """
        parts = path.split('.')
        target = self._config
        for part in parts[:-1]:
            if hasattr(target, part):
                target = getattr(target, part)
            elif isinstance(target, dict) and part in target:
                target = target[part]
            else:
                raise ConfigurationError(f'Invalid config path: {path}')
        last_part = parts[-1]
        if hasattr(target, last_part):
            setattr(target, last_part, value)
        elif isinstance(target, dict):
            target[last_part] = value
        else:
            raise ConfigurationError(f'Cannot set value at path: {path}')

    def reload(self) -> None:
        """설정 재로드"""
        logger.info('Reloading configuration...')
        self._config = self._load_config()

    def to_dict(self) -> Dict[str, Any]:
        """설정을 딕셔너리로 변환"""

        def _convert(obj):
            if hasattr(obj, '__dict__'):
                return {k: _convert(v) for k, v in obj.__dict__.items() if not k.startswith('_')}
            elif isinstance(obj, list):
                return [_convert(item) for item in obj]
            elif isinstance(obj, Enum):
                return obj.value
            else:
                return obj
        return _convert(self._config)

    def export(self, file_path: str, format: str='json') -> None:
        """설정을 파일로 내보내기"""
        data = self.to_dict()
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if format == 'json':
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
        elif format in ['yaml', 'yml']:
            import yaml
            with open(path, 'w') as f:
                yaml.dump(data, f, default_flow_style=False)
        else:
            raise ConfigurationError(f'Unsupported export format: {format}')
        logger.info(f'Configuration exported to: {file_path}')
_config_service = UnifiedConfigService()

def get_config() -> UnifiedConfig:
    """전체 설정 반환"""
    return _config_service.config

def get_config_value(path: str, default: Any=None) -> Any:
    """특정 설정 값 반환"""
    return _config_service.get(path, default)

def set_config_value(path: str, value: Any) -> None:
    """특정 설정 값 변경"""
    _config_service.set(path, value)

def reload_config() -> None:
    """설정 재로드"""
    _config_service.reload()

def get_app_config() -> ApplicationConfig:
    """애플리케이션 설정 반환"""
    return _config_service.config.app

def get_database_config() -> DatabaseConfig:
    """데이터베이스 설정 반환"""
    return _config_service.config.database

def get_security_config() -> SecurityConfig:
    """보안 설정 반환"""
    return _config_service.config.security

def get_messaging_config() -> MessagingConfig:
    """메시징 설정 반환"""
    return _config_service.config.messaging

def get_monitoring_config() -> MonitoringConfig:
    """모니터링 설정 반환"""
    return _config_service.config.monitoring