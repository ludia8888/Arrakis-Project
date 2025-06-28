"""
Shared Configuration Module
공통 설정 모듈
"""
import os
from typing import Dict, Any, Optional

class SharedConfig:
    """공유 설정"""
    
    def __init__(self):
        # 환경 설정
        self.environment = os.getenv("ONTOLOGY_ENVIRONMENT", "development")
        self.debug = os.getenv("ONTOLOGY_DEBUG", "true").lower() == "true"
        
        # 서비스 설정
        self.service_name = os.getenv("ONTOLOGY_SERVICE_NAME", "ontology-management-system")
        self.service_version = os.getenv("ONTOLOGY_SERVICE_VERSION", "2.0.0")
        
        # 보안 설정
        self.secret_key = os.getenv("ONTOLOGY_SECRET_KEY", "default-secret-key")
        self.jwt_algorithm = os.getenv("ONTOLOGY_JWT_ALGORITHM", "HS256")
        self.jwt_expiration_minutes = int(os.getenv("ONTOLOGY_JWT_EXPIRATION_MINUTES", "30"))
        
        # 데이터베이스 설정
        self.database_url = os.getenv("ONTOLOGY_DATABASE_URL", "http://localhost:16363")
        self.database_username = os.getenv("ONTOLOGY_DATABASE_USERNAME", "admin")
        self.database_password = os.getenv("ONTOLOGY_DATABASE_PASSWORD", "root")
        
        # Redis 설정
        self.redis_url = os.getenv("ONTOLOGY_REDIS_URL", "redis://localhost:6379")
        self.redis_prefix = os.getenv("ONTOLOGY_REDIS_PREFIX", "ontology:")
        
        # 이벤트 설정
        self.event_retention_days = int(os.getenv("ONTOLOGY_EVENT_RETENTION_DAYS", "30"))
        self.event_batch_size = int(os.getenv("ONTOLOGY_EVENT_BATCH_SIZE", "100"))
        
        # 로깅 설정
        self.log_level = os.getenv("ONTOLOGY_LOG_LEVEL", "INFO")
        self.log_format = os.getenv("ONTOLOGY_LOG_FORMAT", "json")
        
        # TerminusDB Native Features - Now Permanently Enabled
        self.USE_TERMINUS_NATIVE_BRANCH = True  # Legacy code removed, always use native
        self.USE_TERMINUS_NATIVE_MERGE = True   # Legacy code removed, always use native
        self.USE_TERMINUS_NATIVE_DIFF = True    # Legacy code removed, always use native
        self.USE_UNIFIED_MERGE_ENGINE = True    # Consolidated to single engine
        
        # TerminusDB Connection Settings
        self.TERMINUS_SERVER_URL = os.getenv("TERMINUS_SERVER_URL", "http://localhost:16363")
        self.TERMINUS_DB = os.getenv("TERMINUS_DB", "oms_test")
        self.TERMINUS_ORGANIZATION = os.getenv("TERMINUS_ORGANIZATION", "admin")

# 전역 설정 인스턴스
_config = None

def get_config() -> SharedConfig:
    """설정 인스턴스 반환"""
    global _config
    if _config is None:
        _config = SharedConfig()
    return _config

# Convenience exports
config = get_config()
settings = config  # Alias for compatibility