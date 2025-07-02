"""
Additional environment variable registration
Registers remaining environment variables found during migration
"""

from shared.config.unified_env import unified_env, EnvVar, ConfigNamespace


def register_additional_env_vars():
    """Register additional environment variables"""
    
    # Create additional namespaces
    app_ns = ConfigNamespace("app", "Application-specific configuration")
    ontology_ns = ConfigNamespace("ontology", "Ontology service configuration")
    jetstream_ns = ConfigNamespace("jetstream", "JetStream messaging configuration")
    
    # Application variables
    app_vars = [
        EnvVar("API_HOST", str, False, default="0.0.0.0",
               description="API server host"),
        EnvVar("API_PORT", int, False, default=8000,
               description="API server port"),
        EnvVar("LOG_FORMAT", str, False, default="json",
               description="Log format (json/text)"),
        EnvVar("NATS_SERVERS", str, False, default="nats://localhost:4222",
               description="NATS server URLs"),
        EnvVar("MTLS_ENABLED", bool, False, default=False,
               description="Enable mTLS"),
        EnvVar("NATS_ENABLED", bool, False, default=True,
               description="Enable NATS messaging"),
        EnvVar("METRICS_ENABLED", bool, False, default=True,
               description="Enable metrics collection"),
    ]
    
    # Ontology-specific variables
    ontology_vars = [
        EnvVar("ONTOLOGY_SERVICE_NAME", str, False, default="ontology-management-system",
               description="Ontology service name"),
        EnvVar("ONTOLOGY_SERVICE_VERSION", str, False, default="2.0.0",
               description="Ontology service version"),
        EnvVar("ONTOLOGY_SECRET_KEY", str, True,
               description="Ontology secret key",
               validator=lambda v: len(v) >= 32),
        EnvVar("ONTOLOGY_JWT_ALGORITHM", str, False, default="HS256",
               description="JWT algorithm for ontology"),
        EnvVar("ONTOLOGY_JWT_EXPIRATION_MINUTES", int, False, default=30,
               description="JWT expiration in minutes"),
        EnvVar("ONTOLOGY_EVENT_RETENTION_DAYS", int, False, default=30,
               description="Event retention period in days"),
        EnvVar("ONTOLOGY_EVENT_BATCH_SIZE", int, False, default=100,
               description="Event batch size"),
        EnvVar("ONTOLOGY_LOG_LEVEL", str, False, default="INFO",
               description="Ontology log level"),
        EnvVar("ONTOLOGY_LOG_FORMAT", str, False, default="json",
               description="Ontology log format"),
    ]
    
    # JetStream variables
    jetstream_vars = [
        EnvVar("JETSTREAM_SUBJECT_PREFIX", str, False, default="ontology.",
               description="JetStream subject prefix"),
        EnvVar("JETSTREAM_CONSUMER_NAME", str, False, default="ontology-consumer",
               description="JetStream consumer name"),
        EnvVar("JETSTREAM_MAX_INFLIGHT", int, False, default=100,
               description="Maximum inflight messages"),
        EnvVar("JETSTREAM_ACK_TIMEOUT", int, False, default=30,
               description="ACK timeout in seconds"),
        EnvVar("ENABLE_EVENT_DEDUPLICATION", bool, False, default=True,
               description="Enable event deduplication"),
        EnvVar("EVENT_CACHE_TTL_SECONDS", int, False, default=300,
               description="Event cache TTL in seconds"),
        EnvVar("EVENT_PROCESSING_TIMEOUT", int, False, default=60,
               description="Event processing timeout in seconds"),
    ]
    
    # Traversal-specific variables
    traversal_vars = [
        EnvVar("TRAVERSAL_MAX_DEPTH", int, False, default=10,
               description="Maximum traversal depth"),
        EnvVar("TRAVERSAL_DEFAULT_BRANCH", str, False, default="main",
               description="Default branch for traversal"),
    ]
    
    # Register all variables
    for var in app_vars:
        app_ns.add_var(var)
    
    for var in ontology_vars:
        ontology_ns.add_var(var)
        
    for var in jetstream_vars:
        jetstream_ns.add_var(var)
    
    # Register traversal vars in core namespace
    for var in traversal_vars:
        unified_env.register_var(var, namespace="core")
    
    # Policy engine variables
    policy_vars = [
        EnvVar("CI", str, False, default="false",
               description="CI environment flag"),
        EnvVar("GITHUB_EVENT_NAME", str, False, default="",
               description="GitHub event name"),
        EnvVar("RUNTIME_MODE", str, False, default="",
               description="Runtime mode (batch/stream)"),
        EnvVar("POLICY_FAIL_FAST", bool, False, default=False,
               description="Policy fail fast mode"),
        EnvVar("POLICY_MAX_WARNINGS", int, False, default=100,
               description="Maximum policy warnings"),
        EnvVar("POLICY_MAX_ALERTS", int, False, default=50,
               description="Maximum policy alerts"),
        EnvVar("POLICY_DEFAULT_ACTION", str, False, default="warn",
               description="Default policy action"),
        EnvVar("POLICY_CONFIG_FILE", str, False, default=None,
               description="Policy configuration file path"),
    ]
    
    # Validation engine variables
    validation_vars = [
        EnvVar("DEFAULT_VALIDATION_LEVEL", str, False, default="standard",
               description="Default validation level (standard/strict/relaxed)"),
        EnvVar("VALIDATE_RESPONSES", bool, False, default=True,
               description="Enable response validation"),
        EnvVar("VALIDATION_METRICS", bool, False, default=True,
               description="Enable validation metrics collection"),
        EnvVar("LOG_VALIDATION_ERRORS", bool, False, default=True,
               description="Log validation errors"),
        EnvVar("PREVENT_INFO_DISCLOSURE", bool, False, default=True,
               description="Prevent information disclosure in validation errors"),
    ]
    
    # IAM integration variables
    iam_vars = [
        EnvVar("IAM_ENABLE_FALLBACK", bool, False, default=True,
               description="Enable IAM fallback mode"),
        EnvVar("IAM_JWKS_ENABLED", bool, False, default=False,
               description="Enable JWKS validation mode"),
        EnvVar("NATS_URL", str, False, default="nats://nats-server:4222",
               description="NATS server URL"),
        EnvVar("WS_URL", str, False, default="ws://api-gateway:8080",
               description="WebSocket server URL"),
    ]
    
    # SIEM integration variables
    siem_vars = [
        EnvVar("ENABLE_SIEM_INTEGRATION", bool, False, default=True,
               description="Enable SIEM integration"),
        EnvVar("SIEM_SEND_TAMPERING_EVENTS", bool, False, default=True,
               description="Send tampering events to SIEM"),
        EnvVar("SIEM_SEND_INFO_TAMPERING", bool, False, default=False,
               description="Send INFO level tampering events to SIEM"),
    ]
    
    # Additional cache and system variables
    misc_vars = [
        EnvVar("ISSUE_TRACKING_ENABLED", bool, False, default=True,
               description="Enable issue tracking middleware"),
        EnvVar("CACHE_DEFAULT_TTL", int, False, default=3600,
               description="Default cache TTL in seconds"),
        EnvVar("TEST_MODE", bool, False, default=False,
               description="Running in test mode"),
        EnvVar("IDP_ENDPOINT", str, False, default=None,
               description="IDP endpoint URL"),
    ]
    
    # Register all variables
    for var in app_vars:
        app_ns.add_var(var)
    
    for var in ontology_vars:
        ontology_ns.add_var(var)
        
    for var in jetstream_vars:
        jetstream_ns.add_var(var)
    
    # Register traversal vars in core namespace
    for var in traversal_vars:
        unified_env.register_var(var, namespace="core")
        
    # Register policy vars in core namespace
    for var in policy_vars:
        unified_env.register_var(var, namespace="core")
        
    # Register validation vars in core namespace
    for var in validation_vars:
        unified_env.register_var(var, namespace="core")
        
    # Register IAM vars in core namespace
    for var in iam_vars:
        unified_env.register_var(var, namespace="core")
        
    # Register SIEM vars in core namespace
    for var in siem_vars:
        unified_env.register_var(var, namespace="core")
        
    # Register misc vars in core namespace
    for var in misc_vars:
        unified_env.register_var(var, namespace="core")
    
    # Register namespaces
    unified_env.register_namespace(app_ns)
    unified_env.register_namespace(ontology_ns)
    unified_env.register_namespace(jetstream_ns)
    
    print(f"✅ Registered {len(app_vars) + len(ontology_vars) + len(jetstream_vars) + len(traversal_vars) + len(policy_vars) + len(validation_vars) + len(iam_vars) + len(siem_vars) + len(misc_vars)} additional environment variables")


# Auto-register when imported
register_additional_env_vars()