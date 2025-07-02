"""
Validation Configuration

엔터프라이즈 수준 Validation 레이어 공통 설정.
모든 하드코딩 임계값과 파일 경로를 외부화하여 단일 지점에서 관리하도록 한다.
"""
from dataclasses import dataclass, field
from typing import List, Optional
from shared.config.unified_env import unified_env, ConfigurationError

@dataclass
class ValidationConfig:
    """Validation 레이어 전역 설정 - Single Source of Truth"""
    schema_base_dir: str = field(default_factory=lambda: unified_env.get('OMS_SCHEMA_BASE_DIR'))
    default_draft: str = field(default_factory=lambda: unified_env.get('OMS_JSON_SCHEMA_DRAFT'))
    enable_format_validation: bool = field(default_factory=lambda: unified_env.get('OMS_SCHEMA_FORMAT_CHECK').lower() == 'true')
    enable_schema_cache: bool = field(default_factory=lambda: unified_env.get('OMS_SCHEMA_CACHE').lower() == 'true')
    cache_max_entries: int = field(default_factory=lambda: int(unified_env.get('OMS_SCHEMA_CACHE_MAX')))
    cache_ttl_seconds: int = field(default_factory=lambda: int(unified_env.get('OMS_SCHEMA_CACHE_TTL')))
    rule_cache_ttl_seconds: int = field(default_factory=lambda: int(unified_env.get('OMS_RULE_CACHE_TTL')))
    common_entities_conflict_threshold: int = field(default_factory=lambda: int(unified_env.get('OMS_COMMON_ENTITIES_THRESHOLD')))
    max_diff_items: int = field(default_factory=lambda: int(unified_env.get('OMS_MAX_DIFF_ITEMS')))
    traversal_max_depth: int = field(default_factory=lambda: int(unified_env.get('OMS_TRAVERSAL_MAX_DEPTH')))
    dependency_cycle_max_length: int = field(default_factory=lambda: int(unified_env.get('OMS_DEPENDENCY_CYCLE_MAX')))
    schema_namespace: str = '@schema'
    system_namespace: str = '@system'
    base_namespace: str = '@base'
    dependency_relations: List[str] = field(default_factory=lambda: ['depends_on', 'extends', 'references', 'inherits_from', 'uses', 'imports'])
    structural_relations: List[str] = field(default_factory=lambda: ['has_property', 'has_method', 'contains', 'includes'])
    semantic_relations: List[str] = field(default_factory=lambda: ['subclass_of', 'instance_of', 'equivalent_to', 'disjoint_with'])
    max_traversal_depth: int = field(default_factory=lambda: int(unified_env.get('OMS_MAX_TRAVERSAL_DEPTH')))
    default_traversal_depth: int = field(default_factory=lambda: int(unified_env.get('OMS_DEFAULT_TRAVERSAL_DEPTH')))
    critical_path_threshold: int = field(default_factory=lambda: int(unified_env.get('OMS_CRITICAL_PATH_THRESHOLD')))
    high_degree_threshold: int = field(default_factory=lambda: int(unified_env.get('OMS_HIGH_DEGREE_THRESHOLD')))
    impact_analysis_threshold: int = field(default_factory=lambda: int(unified_env.get('OMS_IMPACT_ANALYSIS_THRESHOLD')))
    max_entities_to_analyze: int = field(default_factory=lambda: int(unified_env.get('OMS_MAX_ENTITIES_ANALYZE')))
    max_high_degree_nodes: int = field(default_factory=lambda: int(unified_env.get('OMS_MAX_HIGH_DEGREE_NODES')))
    default_query_limit: int = field(default_factory=lambda: int(unified_env.get('OMS_DEFAULT_QUERY_LIMIT')))
    max_query_limit: int = field(default_factory=lambda: int(unified_env.get('OMS_MAX_QUERY_LIMIT')))
    query_timeout_seconds: int = field(default_factory=lambda: int(unified_env.get('OMS_QUERY_TIMEOUT')))
    query_plan_validation_timeout_hours: int = field(default_factory=lambda: int(unified_env.get('OMS_PLAN_VALIDATION_TIMEOUT_HOURS')))
    default_branch: str = field(default_factory=lambda: unified_env.get('OMS_DEFAULT_BRANCH'))
    merge_strategies: List[str] = field(default_factory=lambda: ['fast_forward', 'three_way', 'squash', 'rebase'])
    auto_resolve_threshold: float = field(default_factory=lambda: float(unified_env.get('OMS_AUTO_RESOLVE_THRESHOLD')))
    manual_review_threshold: float = field(default_factory=lambda: float(unified_env.get('OMS_MANUAL_REVIEW_THRESHOLD')))
    reject_merge_threshold: float = field(default_factory=lambda: float(unified_env.get('OMS_REJECT_MERGE_THRESHOLD')))
    max_merge_conflicts: int = field(default_factory=lambda: int(unified_env.get('OMS_MAX_MERGE_CONFLICTS')))
    business_rule_types: List[str] = field(default_factory=lambda: ['validation', 'constraint', 'policy', 'governance'])
    msa_service_mappings: dict = field(default_factory=lambda: {'Order': 'order-service', 'Product': 'product-service', 'Customer': 'customer-service', 'Inventory': 'inventory-service', 'Payment': 'payment-service', 'User': 'user-service', 'Notification': 'notification-service', 'Analytics': 'analytics-service'})
    msa_critical_services: List[str] = field(default_factory=lambda: ['user-service', 'order-service', 'payment-service'])
    msa_high_impact_threshold: int = field(default_factory=lambda: int(unified_env.get('OMS_MSA_HIGH_IMPACT_THRESHOLD')))
    enable_query_cache: bool = field(default_factory=lambda: unified_env.get('OMS_ENABLE_QUERY_CACHE').lower() == 'true')
    enable_plan_cache: bool = field(default_factory=lambda: unified_env.get('OMS_ENABLE_PLAN_CACHE').lower() == 'true')
    enable_result_cache: bool = field(default_factory=lambda: unified_env.get('OMS_ENABLE_RESULT_CACHE').lower() == 'true')
    query_cache_ttl: int = field(default_factory=lambda: int(unified_env.get('OMS_QUERY_CACHE_TTL')))
    plan_cache_ttl: int = field(default_factory=lambda: int(unified_env.get('OMS_PLAN_CACHE_TTL')))
    result_cache_ttl: int = field(default_factory=lambda: int(unified_env.get('OMS_RESULT_CACHE_TTL')))
    query_cache_max_size: int = field(default_factory=lambda: int(unified_env.get('OMS_QUERY_CACHE_MAX_SIZE')))
    plan_cache_max_size: int = field(default_factory=lambda: int(unified_env.get('OMS_PLAN_CACHE_MAX_SIZE')))
    result_cache_max_size: int = field(default_factory=lambda: int(unified_env.get('OMS_RESULT_CACHE_MAX_SIZE')))
    eviction_policy: str = field(default_factory=lambda: unified_env.get('OMS_EVICTION_POLICY'))
    enable_cache_warming: bool = field(default_factory=lambda: unified_env.get('OMS_ENABLE_CACHE_WARMING').lower() == 'true')
    cache_warming_queries: List[str] = field(default_factory=list)
    cache_warming_interval_seconds: int = field(default_factory=lambda: int(unified_env.get('OMS_CACHE_WARMING_INTERVAL')))
    cache_warming_error_delay_seconds: int = field(default_factory=lambda: int(unified_env.get('OMS_CACHE_WARMING_ERROR_DELAY')))
    metadata_properties: List[str] = field(default_factory=lambda: ['created_at', 'modified_at', 'created_by', 'modified_by', 'version', 'status', 'impact_level', 'priority'])
    enable_json_schema_validation: bool = field(default_factory=lambda: unified_env.get('OMS_ENABLE_JSON_SCHEMA').lower() == 'true')
    enable_policy_validation: bool = field(default_factory=lambda: unified_env.get('OMS_ENABLE_POLICY').lower() == 'true')
    enable_terminus_validation: bool = field(default_factory=lambda: unified_env.get('OMS_ENABLE_TERMINUS_CHECK').lower() == 'true')
    enable_rule_engine: bool = field(default_factory=lambda: unified_env.get('OMS_ENABLE_RULE_ENGINE').lower() == 'true')
    fail_fast_mode: bool = field(default_factory=lambda: unified_env.get('OMS_FAIL_FAST').lower() == 'true')

    @property
    def policy_server_url(self) -> str:
        from shared.config.environment import get_config
        config = get_config()
        return config.get('OMS_POLICY_SERVER_URL', 'http://policy-server:8080/api/v1/policies')
    policy_server_timeout: float = field(default_factory=lambda: float(unified_env.get('OMS_POLICY_TIMEOUT')))
    policy_server_api_key: Optional[str] = field(default_factory=lambda: unified_env.get('OMS_POLICY_API_KEY'))
    rule_reload_interval: int = field(default_factory=lambda: int(unified_env.get('OMS_RULE_RELOAD_INTERVAL')))

    @property
    def terminus_db_url(self) -> str:
        from shared.config.environment import get_config
        config = get_config()
        return config.get_terminus_db_url()
    terminus_default_db: str = field(default_factory=lambda: unified_env.get('TERMINUSDB_DEFAULT_DB'))
    terminus_default_branch: str = field(default_factory=lambda: unified_env.get('TERMINUSDB_DEFAULT_BRANCH'))
    terminus_timeout: float = field(default_factory=lambda: float(unified_env.get('TERMINUSDB_TIMEOUT')))
    orphan_detection_enabled: bool = field(default_factory=lambda: unified_env.get('OMS_ORPHAN_DETECTION').lower() == 'true')
    verbose_logging: bool = field(default_factory=lambda: unified_env.get('OMS_VALIDATION_VERBOSE').lower() == 'true')
    enable_performance_metrics: bool = field(default_factory=lambda: unified_env.get('OMS_ENABLE_METRICS').lower() == 'true')
    enable_foundry_alerting: bool = field(default_factory=lambda: unified_env.get('OMS_ENABLE_FOUNDRY_ALERTING').lower() == 'true')
    foundry_alerting_enabled: bool = field(default_factory=lambda: unified_env.get('OMS_FOUNDRY_ALERTING_ENABLED').lower() == 'true')
    foundry_alert_severity_threshold: str = field(default_factory=lambda: unified_env.get('OMS_FOUNDRY_ALERT_SEVERITY_THRESHOLD'))
    foundry_alert_cooldown_minutes: int = field(default_factory=lambda: int(unified_env.get('OMS_FOUNDRY_ALERT_COOLDOWN_MINUTES')))
    foundry_max_alerts_per_hour: int = field(default_factory=lambda: int(unified_env.get('OMS_FOUNDRY_MAX_ALERTS_PER_HOUR')))
    foundry_notification_channels: List[str] = field(default_factory=lambda: unified_env.get('OMS_FOUNDRY_NOTIFICATION_CHANNELS').split(','))
    foundry_escalation_threshold: str = field(default_factory=lambda: unified_env.get('OMS_FOUNDRY_ESCALATION_THRESHOLD'))
    foundry_dataset_size_threshold: int = field(default_factory=lambda: int(unified_env.get('OMS_FOUNDRY_DATASET_SIZE_THRESHOLD')))
    foundry_compliance_checks_enabled: bool = field(default_factory=lambda: unified_env.get('OMS_FOUNDRY_COMPLIANCE_CHECKS').lower() == 'true')
_validation_config: Optional[ValidationConfig] = None

def get_validation_config() -> ValidationConfig:
    """ValidationConfig 싱글턴 반환"""
    global _validation_config
    if _validation_config is None:
        _validation_config = ValidationConfig()
    return _validation_config

def reset_validation_config():
    """테스트용: 싱글턴 리셋"""
    global _validation_config
    _validation_config = None

def add_config_methods():
    """Helper 메서드들을 ValidationConfig에 동적 추가"""

    def get_schema_uri(self, element: str) -> str:
        """스키마 URI 생성"""
        return f'{self.schema_namespace}:{element}'

    def get_relation_uris(self, relations: List[str]) -> List[str]:
        """관계 URI 목록 생성"""
        return [self.get_schema_uri(rel) for rel in relations]

    def get_msa_service(self, entity_type: str) -> Optional[str]:
        """엔티티 타입에 대한 MSA 서비스 반환"""
        return self.msa_service_mappings.get(entity_type)

    def is_high_impact_change(self, affected_count: int) -> bool:
        """높은 영향도 변경인지 판단"""
        return affected_count >= self.impact_analysis_threshold

    def is_critical_path(self, path_length: float) -> bool:
        """경로가 중요 경로인지 판단"""
        return path_length <= self.critical_path_threshold

    def get_severity_level(self, score: float) -> str:
        """점수를 기반으로 심각도 레벨 반환"""
        if score >= 0.8:
            return 'critical'
        elif score >= 0.6:
            return 'high'
        elif score >= 0.4:
            return 'medium'
        else:
            return 'low'
    ValidationConfig.get_schema_uri = get_schema_uri
    ValidationConfig.get_relation_uris = get_relation_uris
    ValidationConfig.get_msa_service = get_msa_service
    ValidationConfig.is_high_impact_change = is_high_impact_change
    ValidationConfig.is_critical_path = is_critical_path
    ValidationConfig.get_severity_level = get_severity_level
add_config_methods()