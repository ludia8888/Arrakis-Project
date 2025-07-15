"""
Service Configuration
Centralized configuration for all service URLs and settings
"""
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ServiceEndpoints:
 """Service endpoint configuration"""

 # Core services
 embedding_service: str = field(default_factory = lambda: os.getenv('EMBEDDING_SERVICE_URL', 'http://embedding-service:8001'))
 audit_service: str = field(default_factory = lambda: os.getenv('AUDIT_SERVICE_URL', 'http://audit-service:8000'))
 user_service: str = field(default_factory = lambda: os.getenv('USER_SERVICE_URL', 'http://user-service:8010'))
 data_kernel_service: str = field(default_factory = lambda: os.getenv('DATA_KERNEL_SERVICE_URL', 'http://data-kernel-service:8003'))
 ontology_service: str = field(default_factory = lambda: os.getenv('ONTOLOGY_SERVICE_URL', 'http://ontology-management-service:8000'))

 # Monitoring services
 prometheus_url: str = field(default_factory = lambda: os.getenv('PROMETHEUS_URL', 'http://prometheus:9090'))
 grafana_url: str = field(default_factory = lambda: os.getenv('GRAFANA_URL', 'http://grafana:3000'))
 jaeger_url: str = field(default_factory = lambda: os.getenv('JAEGER_URL', 'http://jaeger:16686'))

 # Message queue
 nats_url: str = field(default_factory = lambda: os.getenv('NATS_URL', 'nats://nats:4222'))

 # Database services
 redis_url: str = field(default_factory = lambda: os.getenv('REDIS_URL', 'redis://redis:6379'))
 postgres_url: str = field(default_factory = lambda: os.getenv('POSTGRES_URL', 'postgresql://postgres:postgres@postgres:5432/scheduler'))
 terminusdb_url: str = field(default_factory = lambda: os.getenv('TERMINUSDB_URL', 'http://terminusdb:6363'))


@dataclass
class ExecutorConfig:
 """Configuration for job executors"""

 # Timeout settings (in seconds)
 default_timeout: float = field(default_factory = lambda: float(os.getenv('EXECUTOR_DEFAULT_TIMEOUT', '30.0')))
 embedding_timeout: float = field(default_factory = lambda: float(os.getenv('EXECUTOR_EMBEDDING_TIMEOUT', '60.0')))
 audit_timeout: float = field(default_factory = lambda: float(os.getenv('EXECUTOR_AUDIT_TIMEOUT', '10.0')))
 cleanup_timeout: float = field(default_factory = lambda: float(os.getenv('EXECUTOR_CLEANUP_TIMEOUT', '120.0')))

 # Batch processing settings
 default_batch_size: int = field(default_factory = lambda: int(os.getenv('EXECUTOR_DEFAULT_BATCH_SIZE', '100')))
 large_batch_size: int = field(default_factory = lambda: int(os.getenv('EXECUTOR_LARGE_BATCH_SIZE', '1000')))
 max_batch_size: int = field(default_factory = lambda: int(os.getenv('EXECUTOR_MAX_BATCH_SIZE', '5000')))

 # Script execution limits
 max_script_size: int = field(default_factory = lambda: int(os.getenv('EXECUTOR_MAX_SCRIPT_SIZE', '10000'))) # 10KB
 script_timeout: float = field(default_factory = lambda: float(os.getenv('EXECUTOR_SCRIPT_TIMEOUT', '300.0'))) # 5 minutes

 # Retry settings
 max_retries: int = field(default_factory = lambda: int(os.getenv('EXECUTOR_MAX_RETRIES', '3')))
 retry_delay: float = field(default_factory = lambda: float(os.getenv('EXECUTOR_RETRY_DELAY', '1.0')))

 # Resource limits
 max_concurrent_jobs: int = field(default_factory = lambda: int(os.getenv('EXECUTOR_MAX_CONCURRENT_JOBS', '10')))
 memory_limit_mb: int = field(default_factory = lambda: int(os.getenv('EXECUTOR_MEMORY_LIMIT_MB', '512')))


@dataclass
class CleanupConfig:
 """Configuration for cleanup operations"""

 # Retention periods (in days)
 log_retention_days: int = field(default_factory = lambda: int(os.getenv('CLEANUP_LOG_RETENTION_DAYS', '30')))
 audit_retention_days: int = field(default_factory = lambda: int(os.getenv('CLEANUP_AUDIT_RETENTION_DAYS', '90')))
 temp_file_retention_days: int = field(default_factory = lambda: int(os.getenv('CLEANUP_TEMP_RETENTION_DAYS', '7')))
 cache_retention_days: int = field(default_factory = lambda: int(os.getenv('CLEANUP_CACHE_RETENTION_DAYS', '1')))

 # Cleanup batch sizes
 cleanup_batch_size: int = field(default_factory = lambda: int(os.getenv('CLEANUP_BATCH_SIZE', '1000')))
 max_files_per_cleanup: int = field(default_factory = lambda: int(os.getenv('CLEANUP_MAX_FILES', '10000')))

 # File size thresholds (in MB)
 large_file_threshold_mb: int = field(default_factory = lambda: int(os.getenv('CLEANUP_LARGE_FILE_THRESHOLD_MB', '100')))
 max_total_cleanup_size_gb: int = field(default_factory = lambda: int(os.getenv('CLEANUP_MAX_TOTAL_SIZE_GB', '10')))


@dataclass
class ValidationConfig:
 """Configuration for validation thresholds"""

 # Email validation
 email_local_max_length: int = field(default_factory = lambda: int(os.getenv('VALIDATION_EMAIL_LOCAL_MAX', '64')))
 email_domain_max_length: int = field(default_factory = lambda: int(os.getenv('VALIDATION_EMAIL_DOMAIN_MAX', '255')))

 # Phone validation
 phone_min_length: int = field(default_factory = lambda: int(os.getenv('VALIDATION_PHONE_MIN_LENGTH', '7')))
 phone_max_length: int = field(default_factory = lambda: int(os.getenv('VALIDATION_PHONE_MAX_LENGTH', '15')))

 # MFA validation
 mfa_code_length: int = field(default_factory = lambda: int(os.getenv('VALIDATION_MFA_CODE_LENGTH', '6')))
 backup_code_length: int = field(default_factory = lambda: int(os.getenv('VALIDATION_BACKUP_CODE_LENGTH', '8')))

 # General limits
 search_text_max_length: int = field(default_factory = lambda: int(os.getenv('VALIDATION_SEARCH_TEXT_MAX', '1000')))
 query_limit_max: int = field(default_factory = lambda: int(os.getenv('VALIDATION_QUERY_LIMIT_MAX', '10000')))
 query_offset_max: int = field(default_factory = lambda: int(os.getenv('VALIDATION_QUERY_OFFSET_MAX', '1000000')))


@dataclass
class RateLimitConfig:
 """Configuration for rate limiting"""

 # API rate limits (requests per second)
 api_rate_limit: float = field(default_factory = lambda: float(os.getenv('RATE_LIMIT_API_RPS', '10.0')))
 auth_rate_limit: float = field(default_factory = lambda: float(os.getenv('RATE_LIMIT_AUTH_RPS', '5.0')))
 admin_rate_limit: float = field(default_factory = lambda: float(os.getenv('RATE_LIMIT_ADMIN_RPS', '20.0')))

 # Burst allowances
 api_burst_size: int = field(default_factory = lambda: int(os.getenv('RATE_LIMIT_API_BURST', '20')))
 auth_burst_size: int = field(default_factory = lambda: int(os.getenv('RATE_LIMIT_AUTH_BURST', '10')))

 # Window settings (in seconds)
 rate_window_seconds: int = field(default_factory = lambda: int(os.getenv('RATE_LIMIT_WINDOW_SECONDS', '60')))


@dataclass
class MonitoringConfig:
 """Configuration for monitoring thresholds"""

 # Circuit breaker thresholds
 circuit_breaker_failure_threshold: float = field(default_factory = lambda: float(os.getenv('MONITORING_CB_FAILURE_THRESHOLD', '0.5')))
 cache_hit_rate_threshold: float = field(default_factory = lambda: float(os.getenv('MONITORING_CACHE_HIT_THRESHOLD', '0.7')))
 redis_failure_threshold: float = field(default_factory = lambda: float(os.getenv('MONITORING_REDIS_FAILURE_THRESHOLD', '0.1')))

 # Auth monitoring thresholds
 auth_failure_threshold: int = field(default_factory = lambda: int(os.getenv('MONITORING_AUTH_FAILURE_THRESHOLD', '5')))
 authz_denial_threshold: int = field(default_factory = lambda: int(os.getenv('MONITORING_AUTHZ_DENIAL_THRESHOLD', '10')))

 # Performance thresholds
 response_time_threshold_ms: int = field(default_factory = lambda: int(os.getenv('MONITORING_RESPONSE_TIME_THRESHOLD_MS', '1000')))
 error_rate_threshold: float = field(default_factory = lambda: float(os.getenv('MONITORING_ERROR_RATE_THRESHOLD', '0.05')))


class ServiceConfig:
 """Main configuration class combining all settings"""

 def __init__(self):
 self.endpoints = ServiceEndpoints()
 self.executor = ExecutorConfig()
 self.cleanup = CleanupConfig()
 self.validation = ValidationConfig()
 self.rate_limit = RateLimitConfig()
 self.monitoring = MonitoringConfig()

 def get_service_url(self, service_name: str) -> str:
 """Get service URL by name"""
 service_urls = {
 'embedding': self.endpoints.embedding_service,
 'audit': self.endpoints.audit_service,
 'user': self.endpoints.user_service,
 'data_kernel': self.endpoints.data_kernel_service,
 'ontology': self.endpoints.ontology_service,
 'prometheus': self.endpoints.prometheus_url,
 'grafana': self.endpoints.grafana_url,
 'jaeger': self.endpoints.jaeger_url,
 'nats': self.endpoints.nats_url,
 'redis': self.endpoints.redis_url,
 'postgres': self.endpoints.postgres_url,
 'terminusdb': self.endpoints.terminusdb_url,
 }

 url = service_urls.get(service_name)
 if url is None:
 raise ValueError(f"Unknown service name: {service_name}")
 return url

 def get_timeout(self, operation_type: str) -> float:
 """Get timeout value for operation type"""
 timeouts = {
 'default': self.executor.default_timeout,
 'embedding': self.executor.embedding_timeout,
 'audit': self.executor.audit_timeout,
 'cleanup': self.executor.cleanup_timeout,
 'script': self.executor.script_timeout,
 }

 return timeouts.get(operation_type, self.executor.default_timeout)

 def get_batch_size(self, operation_type: str) -> int:
 """Get batch size for operation type"""
 batch_sizes = {
 'default': self.executor.default_batch_size,
 'large': self.executor.large_batch_size,
 'cleanup': self.cleanup.cleanup_batch_size,
 }

 return batch_sizes.get(operation_type, self.executor.default_batch_size)

 def to_dict(self) -> Dict[str, Any]:
 """Convert configuration to dictionary"""
 return {
 'endpoints': self.endpoints.__dict__,
 'executor': self.executor.__dict__,
 'cleanup': self.cleanup.__dict__,
 'validation': self.validation.__dict__,
 'rate_limit': self.rate_limit.__dict__,
 'monitoring': self.monitoring.__dict__,
 }


# Global configuration instance
service_config = ServiceConfig()


# Convenience functions
def get_service_url(service_name: str) -> str:
 """Get service URL by name"""
 return service_config.get_service_url(service_name)


def get_timeout(operation_type: str) -> float:
 """Get timeout value for operation type"""
 return service_config.get_timeout(operation_type)


def get_batch_size(operation_type: str) -> int:
 """Get batch size for operation type"""
 return service_config.get_batch_size(operation_type)
