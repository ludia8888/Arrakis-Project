"""
Shared Configuration Module
공통 설정 모듈
"""
from typing import Dict, Any, Optional
from shared.config.environment import get_config, ConfigurationError
from shared.config.unified_env import unified_env, ConfigurationError

class SharedConfig:
    """공유 설정"""

    def __init__(self):
        from shared.config.environment import get_config as get_env_config
        self._env_config = get_env_config()
        self.environment = self._env_config.environment.value
        self.debug = self._env_config.get_bool('ONTOLOGY_DEBUG', True)
        self.service_name = unified_env.get('ONTOLOGY_SERVICE_NAME')
        self.service_version = unified_env.get('ONTOLOGY_SERVICE_VERSION')
        self.secret_key = unified_env.get('ONTOLOGY_SECRET_KEY')
        if not self.secret_key:
            raise ValueError('ONTOLOGY_SECRET_KEY environment variable is required for security')
        self.jwt_algorithm = unified_env.get('ONTOLOGY_JWT_ALGORITHM')
        self.jwt_expiration_minutes = int(unified_env.get('ONTOLOGY_JWT_EXPIRATION_MINUTES'))
        self.database_url = self._env_config.get_terminus_db_url()
        self.database_username = self._env_config.get('ONTOLOGY_DATABASE_USERNAME', 'admin')
        self.database_password = self._env_config.get('ONTOLOGY_DATABASE_PASSWORD', 'root')
        self.redis_url = self._env_config.get_redis_url()
        self.redis_prefix = self._env_config.get('ONTOLOGY_REDIS_PREFIX', 'ontology:')
        self.event_retention_days = int(unified_env.get('ONTOLOGY_EVENT_RETENTION_DAYS'))
        self.event_batch_size = int(unified_env.get('ONTOLOGY_EVENT_BATCH_SIZE'))
        self.jetstream_url = self._env_config.get_nats_url()
        self.jetstream_subject_prefix = unified_env.get('JETSTREAM_SUBJECT_PREFIX')
        self.jetstream_consumer_name = unified_env.get('JETSTREAM_CONSUMER_NAME')
        self.jetstream_max_inflight = int(unified_env.get('JETSTREAM_MAX_INFLIGHT'))
        self.jetstream_ack_timeout_seconds = int(unified_env.get('JETSTREAM_ACK_TIMEOUT'))
        self.enable_event_deduplication = unified_env.get('ENABLE_EVENT_DEDUPLICATION').lower() == 'true'
        self.event_cache_ttl_seconds = int(unified_env.get('EVENT_CACHE_TTL_SECONDS'))
        self.event_processing_timeout_seconds = int(unified_env.get('EVENT_PROCESSING_TIMEOUT'))
        self.log_level = unified_env.get('ONTOLOGY_LOG_LEVEL')
        self.log_format = unified_env.get('ONTOLOGY_LOG_FORMAT')
        self.USE_TERMINUS_NATIVE_BRANCH = True
        self.USE_UNIFIED_MERGE_ENGINE = True
        self.TERMINUS_SERVER_URL = self._env_config.get_terminus_db_url()
        self.TERMINUS_DB = unified_env.get('TERMINUS_DB')
        self.TERMINUS_ORGANIZATION = unified_env.get('TERMINUS_ORGANIZATION')
_config = None

def get_config() -> SharedConfig:
    """설정 인스턴스 반환"""
    global _config
    if _config is None:
        _config = SharedConfig()
    return _config
config = get_config()
settings = config