"""
Validation Configuration

엔터프라이즈 수준 Validation 레이어 공통 설정.
모든 하드코딩 임계값과 파일 경로를 외부화하여 단일 지점에서 관리하도록 한다.
"""

from dataclasses import dataclass, field
from typing import List, Optional
import os


@dataclass
class ValidationConfig:
    """Validation 레이어 전역 설정 - Single Source of Truth"""
    # JSON-Schema 관련
    schema_base_dir: str = field(default_factory=lambda: os.getenv("OMS_SCHEMA_BASE_DIR", "schemas"))
    default_draft: str = field(default_factory=lambda: os.getenv("OMS_JSON_SCHEMA_DRAFT", "2020-12"))
    enable_format_validation: bool = field(default_factory=lambda: os.getenv("OMS_SCHEMA_FORMAT_CHECK", "true").lower() == "true")

    # 캐시 설정 (Rule Registry, Adapters 통합)
    enable_schema_cache: bool = field(default_factory=lambda: os.getenv("OMS_SCHEMA_CACHE", "true").lower() == "true")
    cache_max_entries: int = field(default_factory=lambda: int(os.getenv("OMS_SCHEMA_CACHE_MAX", "256")))
    cache_ttl_seconds: int = field(default_factory=lambda: int(os.getenv("OMS_SCHEMA_CACHE_TTL", "600")))
    rule_cache_ttl_seconds: int = field(default_factory=lambda: int(os.getenv("OMS_RULE_CACHE_TTL", "300")))
    
    # Traversal/Merge 통합 임계값 (기존 traverse.config 대체)
    common_entities_conflict_threshold: int = field(default_factory=lambda: int(os.getenv("OMS_COMMON_ENTITIES_THRESHOLD", "10")))
    max_diff_items: int = field(default_factory=lambda: int(os.getenv("OMS_MAX_DIFF_ITEMS", "1000")))
    traversal_max_depth: int = field(default_factory=lambda: int(os.getenv("OMS_TRAVERSAL_MAX_DEPTH", "5")))
    dependency_cycle_max_length: int = field(default_factory=lambda: int(os.getenv("OMS_DEPENDENCY_CYCLE_MAX", "50")))
    
    # TraversalConfig 통합 - Single Source of Truth
    schema_namespace: str = "@schema"
    system_namespace: str = "@system"
    base_namespace: str = "@base"
    
    # Dependency Relations (기존 TraversalConfig에서 이전)
    dependency_relations: List[str] = field(default_factory=lambda: [
        "depends_on", "extends", "references", "inherits_from", "uses", "imports"
    ])
    structural_relations: List[str] = field(default_factory=lambda: [
        "has_property", "has_method", "contains", "includes"
    ])
    semantic_relations: List[str] = field(default_factory=lambda: [
        "subclass_of", "instance_of", "equivalent_to", "disjoint_with"
    ])
    
    # Traversal Performance 설정
    max_traversal_depth: int = field(default_factory=lambda: int(os.getenv("OMS_MAX_TRAVERSAL_DEPTH", "20")))
    default_traversal_depth: int = field(default_factory=lambda: int(os.getenv("OMS_DEFAULT_TRAVERSAL_DEPTH", "5")))
    critical_path_threshold: int = field(default_factory=lambda: int(os.getenv("OMS_CRITICAL_PATH_THRESHOLD", "3")))
    high_degree_threshold: int = field(default_factory=lambda: int(os.getenv("OMS_HIGH_DEGREE_THRESHOLD", "5")))
    impact_analysis_threshold: int = field(default_factory=lambda: int(os.getenv("OMS_IMPACT_ANALYSIS_THRESHOLD", "10")))
    max_entities_to_analyze: int = field(default_factory=lambda: int(os.getenv("OMS_MAX_ENTITIES_ANALYZE", "50")))
    max_high_degree_nodes: int = field(default_factory=lambda: int(os.getenv("OMS_MAX_HIGH_DEGREE_NODES", "10")))
    
    # Query Performance 설정
    default_query_limit: int = field(default_factory=lambda: int(os.getenv("OMS_DEFAULT_QUERY_LIMIT", "1000")))
    max_query_limit: int = field(default_factory=lambda: int(os.getenv("OMS_MAX_QUERY_LIMIT", "10000")))
    query_timeout_seconds: int = field(default_factory=lambda: int(os.getenv("OMS_QUERY_TIMEOUT", "30")))
    query_plan_validation_timeout_hours: int = field(default_factory=lambda: int(os.getenv("OMS_PLAN_VALIDATION_TIMEOUT_HOURS", "1")))
    
    # Branch and Version Control
    default_branch: str = field(default_factory=lambda: os.getenv("OMS_DEFAULT_BRANCH", "main"))
    merge_strategies: List[str] = field(default_factory=lambda: [
        "fast_forward", "three_way", "squash", "rebase"
    ])
    
    # Conflict Resolution 설정
    auto_resolve_threshold: float = field(default_factory=lambda: float(os.getenv("OMS_AUTO_RESOLVE_THRESHOLD", "0.8")))
    manual_review_threshold: float = field(default_factory=lambda: float(os.getenv("OMS_MANUAL_REVIEW_THRESHOLD", "0.4")))
    reject_merge_threshold: float = field(default_factory=lambda: float(os.getenv("OMS_REJECT_MERGE_THRESHOLD", "0.1")))
    max_merge_conflicts: int = field(default_factory=lambda: int(os.getenv("OMS_MAX_MERGE_CONFLICTS", "10")))
    
    # Business Rules 설정
    business_rule_types: List[str] = field(default_factory=lambda: [
        "validation", "constraint", "policy", "governance"
    ])
    
    # MSA Integration
    msa_service_mappings: dict = field(default_factory=lambda: {
        "Order": "order-service",
        "Product": "product-service", 
        "Customer": "customer-service",
        "Inventory": "inventory-service",
        "Payment": "payment-service",
        "User": "user-service",
        "Notification": "notification-service",
        "Analytics": "analytics-service"
    })
    msa_critical_services: List[str] = field(default_factory=lambda: [
        "user-service", "order-service", "payment-service"
    ])
    msa_high_impact_threshold: int = field(default_factory=lambda: int(os.getenv("OMS_MSA_HIGH_IMPACT_THRESHOLD", "3")))
    
    # Cache Configuration (기존 CacheConfig 통합)
    enable_query_cache: bool = field(default_factory=lambda: os.getenv("OMS_ENABLE_QUERY_CACHE", "true").lower() == "true")
    enable_plan_cache: bool = field(default_factory=lambda: os.getenv("OMS_ENABLE_PLAN_CACHE", "true").lower() == "true")
    enable_result_cache: bool = field(default_factory=lambda: os.getenv("OMS_ENABLE_RESULT_CACHE", "true").lower() == "true")
    
    query_cache_ttl: int = field(default_factory=lambda: int(os.getenv("OMS_QUERY_CACHE_TTL", "300")))
    plan_cache_ttl: int = field(default_factory=lambda: int(os.getenv("OMS_PLAN_CACHE_TTL", "1800")))
    result_cache_ttl: int = field(default_factory=lambda: int(os.getenv("OMS_RESULT_CACHE_TTL", "600")))
    
    query_cache_max_size: int = field(default_factory=lambda: int(os.getenv("OMS_QUERY_CACHE_MAX_SIZE", "1000")))
    plan_cache_max_size: int = field(default_factory=lambda: int(os.getenv("OMS_PLAN_CACHE_MAX_SIZE", "500")))
    result_cache_max_size: int = field(default_factory=lambda: int(os.getenv("OMS_RESULT_CACHE_MAX_SIZE", "2000")))
    
    eviction_policy: str = field(default_factory=lambda: os.getenv("OMS_EVICTION_POLICY", "LRU"))
    enable_cache_warming: bool = field(default_factory=lambda: os.getenv("OMS_ENABLE_CACHE_WARMING", "true").lower() == "true")
    cache_warming_queries: List[str] = field(default_factory=list)
    cache_warming_interval_seconds: int = field(default_factory=lambda: int(os.getenv("OMS_CACHE_WARMING_INTERVAL", "30")))
    cache_warming_error_delay_seconds: int = field(default_factory=lambda: int(os.getenv("OMS_CACHE_WARMING_ERROR_DELAY", "60")))
    
    # Metadata Properties
    metadata_properties: List[str] = field(default_factory=lambda: [
        "created_at", "modified_at", "created_by", "modified_by",
        "version", "status", "impact_level", "priority"
    ])
    
    # Validation Pipeline 설정
    enable_json_schema_validation: bool = field(default_factory=lambda: os.getenv("OMS_ENABLE_JSON_SCHEMA", "true").lower() == "true")
    enable_policy_validation: bool = field(default_factory=lambda: os.getenv("OMS_ENABLE_POLICY", "true").lower() == "true")
    enable_terminus_validation: bool = field(default_factory=lambda: os.getenv("OMS_ENABLE_TERMINUS_CHECK", "true").lower() == "true")
    enable_rule_engine: bool = field(default_factory=lambda: os.getenv("OMS_ENABLE_RULE_ENGINE", "true").lower() == "true")
    fail_fast_mode: bool = field(default_factory=lambda: os.getenv("OMS_FAIL_FAST", "false").lower() == "true")
    
    # Policy Server 설정
    policy_server_url: str = field(default_factory=lambda: os.getenv("OMS_POLICY_SERVER_URL", "http://localhost:8080/api/v1/policies"))
    policy_server_timeout: float = field(default_factory=lambda: float(os.getenv("OMS_POLICY_TIMEOUT", "10.0")))
    policy_server_api_key: Optional[str] = field(default_factory=lambda: os.getenv("OMS_POLICY_API_KEY"))
    
    # Dynamic Rule Loader 설정
    rule_reload_interval: int = field(default_factory=lambda: int(os.getenv("OMS_RULE_RELOAD_INTERVAL", "300")))
    
    # TerminusDB 통합 설정
    terminus_db_url: str = field(default_factory=lambda: os.getenv("TERMINUSDB_URL", "http://localhost:6363"))
    terminus_default_db: str = field(default_factory=lambda: os.getenv("TERMINUSDB_DEFAULT_DB", "oms"))
    terminus_default_branch: str = field(default_factory=lambda: os.getenv("TERMINUSDB_DEFAULT_BRANCH", "main"))
    terminus_timeout: float = field(default_factory=lambda: float(os.getenv("TERMINUSDB_TIMEOUT", "30.0")))
    
    # Traversal 특화 설정 (기존 TraversalConfig 완전 대체)
    orphan_detection_enabled: bool = field(default_factory=lambda: os.getenv("OMS_ORPHAN_DETECTION", "true").lower() == "true")
    
    # 로깅 & 모니터링
    verbose_logging: bool = field(default_factory=lambda: os.getenv("OMS_VALIDATION_VERBOSE", "false").lower() == "true")
    enable_performance_metrics: bool = field(default_factory=lambda: os.getenv("OMS_ENABLE_METRICS", "true").lower() == "true")
    
    # Foundry Alerting Configuration
    enable_foundry_alerting: bool = field(default_factory=lambda: os.getenv("OMS_ENABLE_FOUNDRY_ALERTING", "true").lower() == "true")
    foundry_alerting_enabled: bool = field(default_factory=lambda: os.getenv("OMS_FOUNDRY_ALERTING_ENABLED", "true").lower() == "true")
    foundry_alert_severity_threshold: str = field(default_factory=lambda: os.getenv("OMS_FOUNDRY_ALERT_SEVERITY_THRESHOLD", "medium"))
    foundry_alert_cooldown_minutes: int = field(default_factory=lambda: int(os.getenv("OMS_FOUNDRY_ALERT_COOLDOWN_MINUTES", "60")))
    foundry_max_alerts_per_hour: int = field(default_factory=lambda: int(os.getenv("OMS_FOUNDRY_MAX_ALERTS_PER_HOUR", "10")))
    foundry_notification_channels: List[str] = field(default_factory=lambda: 
        os.getenv("OMS_FOUNDRY_NOTIFICATION_CHANNELS", "email,slack").split(",")
    )
    foundry_escalation_threshold: str = field(default_factory=lambda: os.getenv("OMS_FOUNDRY_ESCALATION_THRESHOLD", "critical"))
    foundry_dataset_size_threshold: int = field(default_factory=lambda: int(os.getenv("OMS_FOUNDRY_DATASET_SIZE_THRESHOLD", "10000")))
    foundry_compliance_checks_enabled: bool = field(default_factory=lambda: os.getenv("OMS_FOUNDRY_COMPLIANCE_CHECKS", "true").lower() == "true")


# 싱글턴 인스턴스
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


# ValidationConfig에 Helper 메서드 추가 (기존 TraversalConfig 대체)
def add_config_methods():
    """Helper 메서드들을 ValidationConfig에 동적 추가"""
    
    def get_schema_uri(self, element: str) -> str:
        """스키마 URI 생성"""
        return f"{self.schema_namespace}:{element}"
    
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
            return "critical"
        elif score >= 0.6:
            return "high"
        elif score >= 0.4:
            return "medium"
        else:
            return "low"
    
    # 메서드를 ValidationConfig 클래스에 동적 추가
    ValidationConfig.get_schema_uri = get_schema_uri
    ValidationConfig.get_relation_uris = get_relation_uris
    ValidationConfig.get_msa_service = get_msa_service
    ValidationConfig.is_high_impact_change = is_high_impact_change
    ValidationConfig.is_critical_path = is_critical_path
    ValidationConfig.get_severity_level = get_severity_level

# 모듈 로드 시 helper 메서드 추가
add_config_methods() 