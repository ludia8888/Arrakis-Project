"""
Graph Traversal Configuration

Enterprise-grade configuration management for TerminusDB graph traversal operations.
Externalized configuration to eliminate hardcoded values.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import os


class SchemaNamespace(str, Enum):
    """Schema namespace definitions"""
    SCHEMA = "@schema"
    SYSTEM = "@system"  
    BASE = "@base"


@dataclass
class TraversalConfig:
    """Configuration for graph traversal operations"""
    
    # Schema and Namespace Configuration
    schema_namespace: str = "@schema"
    system_namespace: str = "@system"
    base_namespace: str = "@base"
    
    # Default Relations
    dependency_relations: List[str] = field(default_factory=lambda: [
        "depends_on", "extends", "references", "inherits_from", "uses", "imports"
    ])
    
    structural_relations: List[str] = field(default_factory=lambda: [
        "has_property", "has_method", "contains", "includes"
    ])
    
    semantic_relations: List[str] = field(default_factory=lambda: [
        "subclass_of", "instance_of", "equivalent_to", "disjoint_with"
    ])
    
    # Traversal Thresholds
    max_traversal_depth: int = 20
    default_traversal_depth: int = 5
    critical_path_threshold: int = 3
    high_degree_threshold: int = 5
    impact_analysis_threshold: int = 10
    orphan_detection_enabled: bool = True
    
    # Analysis Limits and Thresholds
    max_entities_to_analyze: int = 50  # Limit for performance in orphan detection
    max_high_degree_nodes: int = 10    # Limit for critical path analysis
    common_entities_conflict_threshold: int = 10  # Threshold for merge conflicts
    entity_properties_threshold: int = 5  # Properties threshold for complexity
    high_impact_change_threshold: int = 10  # Threshold for high impact changes
    merge_complexity_threshold: int = 10   # Max conflicts before deferring merge
    
    # Cache and Performance Timeouts
    cache_warming_interval_seconds: int = 30
    cache_warming_error_delay_seconds: int = 60
    query_plan_validation_timeout_hours: int = 1
    
    # Validation and Quality Thresholds
    max_cycle_length_for_high_severity: int = 2
    min_cycle_length_for_detection: int = 2
    resolution_confidence_threshold: float = 0.8
    auto_merge_confidence_threshold: float = 0.8
    
    # Performance Configuration
    default_query_limit: int = 1000
    max_query_limit: int = 10000
    query_timeout_seconds: int = 30
    cache_ttl_seconds: int = 300
    cache_max_size: int = 1000
    
    # Conflict Detection
    severity_levels: List[str] = field(default_factory=lambda: [
        "low", "medium", "high", "critical"
    ])
    
    # Resolution Thresholds
    auto_resolve_threshold: float = 0.8
    manual_review_threshold: float = 0.4
    reject_merge_threshold: float = 0.1
    
    # Conflict Resolution Time Estimates (minutes)
    base_resolution_time_minutes: float = 30.0
    critical_conflict_time_minutes: float = 120.0
    high_conflict_time_minutes: float = 60.0
    medium_conflict_time_minutes: float = 30.0
    low_conflict_time_minutes: float = 15.0
    
    # Branch and Version Control
    default_branch: str = "main"
    merge_strategies: List[str] = field(default_factory=lambda: [
        "fast_forward", "three_way", "squash", "rebase"
    ])
    
    # Business Rules
    business_rule_types: List[str] = field(default_factory=lambda: [
        "validation", "constraint", "policy", "governance"
    ])
    
    # MSA Integration  
    msa_service_mappings: Dict[str, str] = field(default_factory=lambda: {
        "Order": "order-service",
        "Product": "product-service", 
        "Customer": "customer-service",
        "Inventory": "inventory-service",
        "Payment": "payment-service",
        "User": "user-service",
        "Notification": "notification-service",
        "Analytics": "analytics-service"
    })
    
    # MSA Impact Analysis
    msa_critical_services: List[str] = field(default_factory=lambda: [
        "user-service", "order-service", "payment-service"
    ])
    msa_high_impact_threshold: int = 3  # Services affected before high impact
    
    # Metadata Properties
    metadata_properties: List[str] = field(default_factory=lambda: [
        "created_at", "modified_at", "created_by", "modified_by",
        "version", "status", "impact_level", "priority"
    ])


@dataclass 
class WOQLConfig:
    """Configuration for WOQL query construction"""
    
    # Query Construction
    use_optimized_queries: bool = True
    enable_query_caching: bool = True
    enable_parallel_execution: bool = False
    
    # Path Query Configuration
    path_max_depth: int = 10
    path_timeout_ms: int = 5000
    enable_path_caching: bool = True
    
    # Aggregation Configuration
    group_by_limit: int = 1000
    count_timeout_ms: int = 10000
    
    # Triple Pattern Configuration
    triple_batch_size: int = 100
    enable_triple_optimization: bool = True


@dataclass
class CacheConfig:
    """Configuration for caching system"""
    
    # Cache Levels
    enable_query_cache: bool = True
    enable_plan_cache: bool = True
    enable_result_cache: bool = True
    
    # TTL Configuration (seconds)
    query_cache_ttl: int = 300      # 5 minutes
    plan_cache_ttl: int = 1800      # 30 minutes  
    result_cache_ttl: int = 600     # 10 minutes
    
    # Size Limits
    query_cache_max_size: int = 1000
    plan_cache_max_size: int = 500
    result_cache_max_size: int = 2000
    
    # Cache Strategies
    eviction_policy: str = "LRU"    # LRU, LFU, FIFO
    enable_cache_warming: bool = True
    cache_warming_queries: List[str] = field(default_factory=list)


@dataclass
class SecurityConfig:
    """Configuration for security and access control"""
    
    # Access Control
    enable_acl: bool = True
    default_read_permission: bool = True
    default_write_permission: bool = False
    
    # Audit Configuration
    enable_audit_logging: bool = True
    audit_sensitive_operations: bool = True
    audit_log_retention_days: int = 90
    
    # Rate Limiting  
    enable_rate_limiting: bool = True
    requests_per_minute: int = 1000
    burst_limit: int = 100


class ConfigManager:
    """
    Centralized configuration manager for graph traversal operations.
    Supports environment-based configuration and runtime updates.
    """
    
    def __init__(self, env: str = "development"):
        self.env = env
        self._traversal_config = self._load_traversal_config()
        self._woql_config = self._load_woql_config()
        self._cache_config = self._load_cache_config()
        self._security_config = self._load_security_config()
    
    def _load_traversal_config(self) -> TraversalConfig:
        """Load traversal configuration with environment overrides"""
        config = TraversalConfig()
        
        # Environment-based overrides
        if self.env == "production":
            config.max_traversal_depth = 15
            config.query_timeout_seconds = 60
            config.cache_ttl_seconds = 600
            config.auto_resolve_threshold = 0.9
            
        elif self.env == "testing":
            config.max_traversal_depth = 5
            config.query_timeout_seconds = 10
            config.cache_ttl_seconds = 60
            config.orphan_detection_enabled = False
            
        # Environment variable overrides
        config.max_traversal_depth = int(os.getenv(
            "TRAVERSAL_MAX_DEPTH", config.max_traversal_depth
        ))
        config.default_branch = os.getenv(
            "TRAVERSAL_DEFAULT_BRANCH", config.default_branch
        )
        
        return config
    
    def _load_woql_config(self) -> WOQLConfig:
        """Load WOQL configuration"""
        config = WOQLConfig()
        
        if self.env == "production":
            config.enable_parallel_execution = True
            config.path_timeout_ms = 10000
            
        return config
    
    def _load_cache_config(self) -> CacheConfig:
        """Load cache configuration"""
        config = CacheConfig()
        
        if self.env == "production":
            config.query_cache_ttl = 1800  # 30 minutes in production
            config.result_cache_max_size = 5000
            
        elif self.env == "testing":
            config.enable_cache_warming = False
            config.query_cache_ttl = 60
            
        return config
    
    def _load_security_config(self) -> SecurityConfig:
        """Load security configuration"""
        config = SecurityConfig()
        
        if self.env == "production":
            config.enable_audit_logging = True
            config.requests_per_minute = 500  # More restrictive in production
            
        elif self.env == "testing":
            config.enable_acl = False
            config.enable_audit_logging = False
            
        return config
    
    @property
    def traversal(self) -> TraversalConfig:
        """Get traversal configuration"""
        return self._traversal_config
    
    @property 
    def woql(self) -> WOQLConfig:
        """Get WOQL configuration"""
        return self._woql_config
    
    @property
    def cache(self) -> CacheConfig:
        """Get cache configuration"""
        return self._cache_config
    
    @property
    def security(self) -> SecurityConfig:
        """Get security configuration"""
        return self._security_config
    
    def get_schema_uri(self, entity_type: str) -> str:
        """Generate schema URI for entity type"""
        return f"{self.traversal.schema_namespace}:{entity_type}"
    
    def get_relation_uris(self, relation_types: List[str]) -> List[str]:
        """Generate schema URIs for relation types"""
        return [f"{self.traversal.schema_namespace}:{rel}" for rel in relation_types]
    
    def is_critical_path(self, path_length: int) -> bool:
        """Determine if path is critical based on length"""
        return path_length <= self.traversal.critical_path_threshold
    
    def is_high_impact_change(self, affected_count: int) -> bool:
        """Determine if change has high impact"""
        return affected_count > self.traversal.impact_analysis_threshold
    
    def get_severity_level(self, impact_score: float) -> str:
        """Get severity level based on impact score"""
        if impact_score >= 0.8:
            return "critical"
        elif impact_score >= 0.6:
            return "high" 
        elif impact_score >= 0.3:
            return "medium"
        else:
            return "low"
    
    def can_auto_resolve(self, confidence: float) -> bool:
        """Determine if conflict can be auto-resolved"""
        return confidence >= self.traversal.auto_resolve_threshold
    
    def needs_manual_review(self, confidence: float) -> bool:
        """Determine if conflict needs manual review"""
        return confidence <= self.traversal.manual_review_threshold
    
    def get_msa_service(self, entity_type: str) -> Optional[str]:
        """Get MSA service for entity type"""
        return self.traversal.msa_service_mappings.get(entity_type)
    
    def update_config(self, section: str, updates: Dict[str, Any]):
        """Update configuration at runtime"""
        if section == "traversal":
            for key, value in updates.items():
                if hasattr(self._traversal_config, key):
                    setattr(self._traversal_config, key, value)
        elif section == "woql":
            for key, value in updates.items():
                if hasattr(self._woql_config, key):
                    setattr(self._woql_config, key, value)
        # Add other sections as needed


# Global configuration instance
_config_manager: Optional[ConfigManager] = None

def get_config(env: str = None) -> ConfigManager:
    """Get global configuration manager instance"""
    global _config_manager
    
    if _config_manager is None or (env and _config_manager.env != env):
        _config_manager = ConfigManager(env or os.getenv("ENVIRONMENT", "development"))
    
    return _config_manager

def reset_config():
    """Reset global configuration (useful for testing)"""
    global _config_manager
    _config_manager = None