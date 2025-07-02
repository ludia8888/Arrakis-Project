"""
OMS-specific environment variable registration
Registers all OMS validation configuration variables
"""

from shared.config.unified_env import unified_env, EnvVar, ConfigNamespace


def register_oms_validation_config():
    """Register OMS validation configuration variables"""
    
    # Create OMS namespace
    oms_ns = ConfigNamespace("oms", "OMS validation and configuration settings")
    
    # Schema and validation settings
    oms_vars = [
        # Base configuration
        EnvVar("OMS_SCHEMA_BASE_DIR", str, False, default="/schemas", 
               description="Base directory for schemas"),
        EnvVar("OMS_JSON_SCHEMA_DRAFT", str, False, default="draft-07",
               description="JSON Schema draft version"),
        EnvVar("OMS_SCHEMA_FORMAT_CHECK", bool, False, default=True,
               description="Enable schema format validation"),
        EnvVar("OMS_SCHEMA_CACHE", bool, False, default=True,
               description="Enable schema caching"),
        EnvVar("OMS_SCHEMA_CACHE_MAX", int, False, default=1000,
               description="Maximum schema cache entries"),
        EnvVar("OMS_SCHEMA_CACHE_TTL", int, False, default=3600,
               description="Schema cache TTL in seconds"),
        
        # Rule and validation settings
        EnvVar("OMS_RULE_CACHE_TTL", int, False, default=300,
               description="Rule cache TTL in seconds"),
        EnvVar("OMS_COMMON_ENTITIES_THRESHOLD", int, False, default=5,
               description="Common entities conflict threshold"),
        EnvVar("OMS_MAX_DIFF_ITEMS", int, False, default=1000,
               description="Maximum diff items to process"),
        
        # Traversal settings
        EnvVar("OMS_TRAVERSAL_MAX_DEPTH", int, False, default=10,
               description="Maximum traversal depth"),
        EnvVar("OMS_DEFAULT_TRAVERSAL_DEPTH", int, False, default=3,
               description="Default traversal depth"),
        EnvVar("OMS_MAX_TRAVERSAL_DEPTH", int, False, default=20,
               description="Absolute maximum traversal depth"),
        EnvVar("OMS_DEPENDENCY_CYCLE_MAX", int, False, default=50,
               description="Maximum dependency cycle length"),
        
        # Analysis thresholds
        EnvVar("OMS_CRITICAL_PATH_THRESHOLD", int, False, default=3,
               description="Critical path length threshold"),
        EnvVar("OMS_HIGH_DEGREE_THRESHOLD", int, False, default=100,
               description="High degree node threshold"),
        EnvVar("OMS_IMPACT_ANALYSIS_THRESHOLD", int, False, default=50,
               description="Impact analysis threshold"),
        EnvVar("OMS_MAX_ENTITIES_ANALYZE", int, False, default=10000,
               description="Maximum entities to analyze"),
        EnvVar("OMS_MAX_HIGH_DEGREE_NODES", int, False, default=100,
               description="Maximum high degree nodes"),
        
        # Query settings
        EnvVar("OMS_DEFAULT_QUERY_LIMIT", int, False, default=100,
               description="Default query result limit"),
        EnvVar("OMS_MAX_QUERY_LIMIT", int, False, default=10000,
               description="Maximum query result limit"),
        EnvVar("OMS_QUERY_TIMEOUT", int, False, default=30,
               description="Query timeout in seconds"),
        EnvVar("OMS_PLAN_VALIDATION_TIMEOUT_HOURS", int, False, default=24,
               description="Query plan validation timeout in hours"),
        
        # Branch and merge settings
        EnvVar("OMS_DEFAULT_BRANCH", str, False, default="main",
               description="Default branch name"),
        EnvVar("OMS_AUTO_RESOLVE_THRESHOLD", float, False, default=0.8,
               description="Auto-resolve confidence threshold"),
        EnvVar("OMS_MANUAL_REVIEW_THRESHOLD", float, False, default=0.5,
               description="Manual review threshold"),
        EnvVar("OMS_REJECT_MERGE_THRESHOLD", float, False, default=0.2,
               description="Reject merge threshold"),
        EnvVar("OMS_MAX_MERGE_CONFLICTS", int, False, default=100,
               description="Maximum merge conflicts allowed"),
        
        # MSA settings
        EnvVar("OMS_MSA_HIGH_IMPACT_THRESHOLD", int, False, default=3,
               description="MSA high impact threshold"),
        
        # Cache settings
        EnvVar("OMS_ENABLE_QUERY_CACHE", bool, False, default=True,
               description="Enable query caching"),
        EnvVar("OMS_ENABLE_PLAN_CACHE", bool, False, default=True,
               description="Enable plan caching"),
        EnvVar("OMS_ENABLE_RESULT_CACHE", bool, False, default=True,
               description="Enable result caching"),
        EnvVar("OMS_QUERY_CACHE_TTL", int, False, default=300,
               description="Query cache TTL in seconds"),
        EnvVar("OMS_PLAN_CACHE_TTL", int, False, default=3600,
               description="Plan cache TTL in seconds"),
        EnvVar("OMS_RESULT_CACHE_TTL", int, False, default=600,
               description="Result cache TTL in seconds"),
        EnvVar("OMS_QUERY_CACHE_MAX_SIZE", int, False, default=1000,
               description="Query cache max size"),
        EnvVar("OMS_PLAN_CACHE_MAX_SIZE", int, False, default=500,
               description="Plan cache max size"),
        EnvVar("OMS_RESULT_CACHE_MAX_SIZE", int, False, default=10000,
               description="Result cache max size"),
        EnvVar("OMS_EVICTION_POLICY", str, False, default="LRU",
               description="Cache eviction policy"),
        EnvVar("OMS_ENABLE_CACHE_WARMING", bool, False, default=False,
               description="Enable cache warming"),
        EnvVar("OMS_CACHE_WARMING_INTERVAL", int, False, default=3600,
               description="Cache warming interval in seconds"),
        EnvVar("OMS_CACHE_WARMING_ERROR_DELAY", int, False, default=300,
               description="Cache warming error delay in seconds"),
        
        # Validation feature flags
        EnvVar("OMS_ENABLE_JSON_SCHEMA", bool, False, default=True,
               description="Enable JSON schema validation"),
        EnvVar("OMS_ENABLE_POLICY", bool, False, default=True,
               description="Enable policy validation"),
        EnvVar("OMS_ENABLE_TERMINUS_CHECK", bool, False, default=True,
               description="Enable TerminusDB validation"),
        EnvVar("OMS_ENABLE_RULE_ENGINE", bool, False, default=True,
               description="Enable rule engine"),
        EnvVar("OMS_FAIL_FAST", bool, False, default=False,
               description="Fail fast on first error"),
        
        # Policy settings
        EnvVar("OMS_POLICY_SERVER_URL", str, False, default="http://policy-server:8080/api/v1/policies",
               description="Policy server URL"),
        EnvVar("OMS_POLICY_TIMEOUT", float, False, default=10.0,
               description="Policy server timeout"),
        EnvVar("OMS_POLICY_API_KEY", str, False, default=None,
               description="Policy server API key"),
        EnvVar("OMS_RULE_RELOAD_INTERVAL", int, False, default=300,
               description="Rule reload interval in seconds"),
        
        # TerminusDB settings
        EnvVar("TERMINUSDB_DEFAULT_DB", str, False, default="oms",
               description="Default TerminusDB database"),
        EnvVar("TERMINUSDB_DEFAULT_BRANCH", str, False, default="main",
               description="Default TerminusDB branch"),
        EnvVar("TERMINUSDB_TIMEOUT", float, False, default=30.0,
               description="TerminusDB timeout"),
        
        # Detection and logging
        EnvVar("OMS_ORPHAN_DETECTION", bool, False, default=True,
               description="Enable orphan detection"),
        EnvVar("OMS_VALIDATION_VERBOSE", bool, False, default=False,
               description="Enable verbose validation logging"),
        EnvVar("OMS_ENABLE_METRICS", bool, False, default=True,
               description="Enable performance metrics"),
        
        # Foundry alerting
        EnvVar("OMS_ENABLE_FOUNDRY_ALERTING", bool, False, default=False,
               description="Enable Foundry alerting"),
        EnvVar("OMS_FOUNDRY_ALERTING_ENABLED", bool, False, default=False,
               description="Foundry alerting enabled flag"),
        EnvVar("OMS_FOUNDRY_ALERT_SEVERITY_THRESHOLD", str, False, default="high",
               description="Foundry alert severity threshold"),
        EnvVar("OMS_FOUNDRY_ALERT_COOLDOWN_MINUTES", int, False, default=60,
               description="Foundry alert cooldown in minutes"),
        EnvVar("OMS_FOUNDRY_MAX_ALERTS_PER_HOUR", int, False, default=10,
               description="Maximum Foundry alerts per hour"),
        EnvVar("OMS_FOUNDRY_NOTIFICATION_CHANNELS", str, False, default="email,slack",
               description="Foundry notification channels"),
        EnvVar("OMS_FOUNDRY_ESCALATION_THRESHOLD", str, False, default="critical",
               description="Foundry escalation threshold"),
        EnvVar("OMS_FOUNDRY_DATASET_SIZE_THRESHOLD", int, False, default=1000000,
               description="Foundry dataset size threshold"),
        EnvVar("OMS_FOUNDRY_COMPLIANCE_CHECKS", bool, False, default=True,
               description="Enable Foundry compliance checks"),
    ]
    
    # Register all variables
    for var in oms_vars:
        oms_ns.add_var(var)
    
    # Register namespace
    unified_env.register_namespace(oms_ns)
    
    print(f"✅ Registered {len(oms_vars)} OMS environment variables")


# Auto-register when imported
register_oms_validation_config()