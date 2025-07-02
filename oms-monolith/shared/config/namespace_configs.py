"""
Domain-specific configuration namespace definitions
"""

from datetime import timedelta
from typing import Callable
from .unified_env import ConfigNamespace, EnvVar, unified_env

# Validators
def url_validator(v: str) -> bool:
    """Validate URL format"""
    return v.startswith(("http://", "https://"))

def port_validator(v: int) -> bool:
    """Validate port number"""
    return 1 <= v <= 65535

def positive_int_validator(v: int) -> bool:
    """Validate positive integer"""
    return v > 0

def jwt_algorithm_validator(v: str) -> bool:
    """Validate JWT algorithm"""
    return v in ["HS256", "HS384", "HS512", "RS256", "RS384", "RS512"]


def register_security_namespace():
    """Register security-related configuration"""
    ns = ConfigNamespace("security", "Security and authentication configuration")
    
    vars = [
        # JWT Configuration
        EnvVar("JWT_SECRET", str, True, None,
               "JWT secret key for token signing"),
        EnvVar("JWT_SECRET_KEY", str, True, None,
               "JWT secret key (alternate)"),
        EnvVar("JWT_ISSUER", str, False, "iam.company",
               "JWT token issuer"),
        EnvVar("JWT_AUDIENCE", str, False, "oms",
               "JWT token audience"),
        EnvVar("JWT_LOCAL_VALIDATION", bool, False, True,
               "Enable local JWT validation"),
        EnvVar("JWT_JWKS_URL", str, False, None,
               "JWKS endpoint URL", validator=url_validator),
        EnvVar("ONTOLOGY_JWT_ALGORITHM", str, False, "HS256",
               "JWT signing algorithm", validator=jwt_algorithm_validator),
        EnvVar("ONTOLOGY_JWT_EXPIRATION_MINUTES", int, False, 60,
               "JWT expiration time in minutes", validator=positive_int_validator),
        
        # OAuth Configuration
        EnvVar("OAUTH_CLIENT_ID", str, False, None,
               "OAuth client ID"),
        
        # Security Keys
        EnvVar("PII_ENCRYPTION_KEY", str, True, None,
               "Key for PII data encryption"),
        EnvVar("OMS_POLICY_API_KEY", str, False, None,
               "API key for policy service"),
        EnvVar("ONTOLOGY_SECRET_KEY", str, False, None,
               "Ontology service secret key"),
        
        # Cache Configuration
        EnvVar("AUTH_CACHE_TTL", int, False, 300,
               "Authentication cache TTL in seconds", validator=positive_int_validator),
    ]
    
    for var in vars:
        ns.add_var(var)
    
    unified_env.register_namespace(ns)


def register_database_namespace():
    """Register database-related configuration"""
    ns = ConfigNamespace("database", "Database connection configuration")
    
    vars = [
        # TerminusDB Configuration
        EnvVar("TERMINUS_DB_ENDPOINT", str, True, None,
               "TerminusDB endpoint URL", validator=url_validator),
        EnvVar("TERMINUS_DB_USER", str, True, None,
               "TerminusDB username"),
        EnvVar("TERMINUS_DB_PASSWORD", str, True, None,
               "TerminusDB password"),
        EnvVar("TERMINUS_DB", str, False, "oms",
               "TerminusDB database name"),
        EnvVar("TERMINUS_DB_KEY", str, False, None,
               "TerminusDB API key"),
        EnvVar("TERMINUS_ORGANIZATION", str, False, None,
               "TerminusDB organization"),
        EnvVar("TERMINUSDB_DEFAULT_DB", str, False, "oms",
               "Default TerminusDB database"),
        EnvVar("TERMINUSDB_DEFAULT_BRANCH", str, False, "main",
               "Default TerminusDB branch"),
        EnvVar("TERMINUSDB_TIMEOUT", int, False, 30,
               "TerminusDB connection timeout", validator=positive_int_validator),
        EnvVar("TERMINUSDB_USE_MTLS", bool, False, False,
               "Enable mTLS for TerminusDB"),
        EnvVar("TERMINUSDB_CACHE_ENABLED", bool, False, True,
               "Enable TerminusDB query cache"),
        EnvVar("TERMINUSDB_LRU_CACHE_SIZE", int, False, 1000,
               "TerminusDB LRU cache size", validator=positive_int_validator),
        
        # Redis Configuration
        EnvVar("REDIS_SENTINELS", list, False, [],
               "Redis sentinel addresses"),
        EnvVar("REDIS_MASTER_NAME", str, False, "mymaster",
               "Redis master name"),
        EnvVar("REDIS_PASSWORD", str, False, None,
               "Redis password"),
        EnvVar("REDIS_DB", int, False, 0,
               "Redis database number"),
        
        # PostgreSQL Configuration
        EnvVar("POSTGRES_URL", str, False, None,
               "PostgreSQL connection URL"),
        EnvVar("DB_NAME", str, False, "oms",
               "Database name"),
        
        # Connection Pool Configuration
        EnvVar("DB_MIN_CONNECTIONS", int, False, 5,
               "Minimum database connections", validator=positive_int_validator),
        EnvVar("DB_MAX_CONNECTIONS", int, False, 20,
               "Maximum database connections", validator=positive_int_validator),
        EnvVar("DB_CONNECTION_TIMEOUT", int, False, 30,
               "Database connection timeout", validator=positive_int_validator),
        EnvVar("DB_MAX_IDLE_TIME", int, False, 300,
               "Maximum idle time for connections", validator=positive_int_validator),
        
        # Feature Flags
        EnvVar("OMS_ENABLE_TERMINUS_CHECK", bool, False, True,
               "Enable TerminusDB health checks"),
    ]
    
    for var in vars:
        ns.add_var(var)
    
    unified_env.register_namespace(ns)


def register_service_namespace():
    """Register service integration configuration"""
    ns = ConfigNamespace("service", "External service configuration")
    
    vars = [
        EnvVar("IDP_ENDPOINT", str, False, None,
               "Identity Provider endpoint", validator=url_validator),
        EnvVar("ONTOLOGY_SERVICE_NAME", str, False, "oms",
               "Ontology service name"),
        EnvVar("ONTOLOGY_SERVICE_VERSION", str, False, "1.0.0",
               "Ontology service version"),
    ]
    
    for var in vars:
        ns.add_var(var)
    
    unified_env.register_namespace(ns)


def register_traversal_config():
    """Register traversal-specific configuration"""
    traversal_ns = ConfigNamespace("traversal", "Graph traversal configuration")
    
    traversal_vars = [
        # Cache settings
        EnvVar("TRAVERSAL_CACHE_ENABLED", bool, False, True,
               "Enable traversal result caching"),
        EnvVar("TRAVERSAL_CACHE_TTL", int, False, 3600,
               "Cache TTL in seconds", 
               validator=lambda v: v > 0),
        EnvVar("TRAVERSAL_CACHE_MAX_SIZE", int, False, 10000,
               "Maximum cache entries"),
        
        # Performance settings  
        EnvVar("TRAVERSAL_MAX_DEPTH", int, False, 10,
               "Maximum traversal depth",
               validator=lambda v: 1 <= v <= 50),
        EnvVar("TRAVERSAL_BATCH_SIZE", int, False, 1000,
               "Batch size for bulk operations"),
        EnvVar("TRAVERSAL_TIMEOUT_MS", int, False, 30000,
               "Query timeout in milliseconds"),
        
        # Feature flags
        EnvVar("TRAVERSAL_ENABLE_METRICS", bool, False, True,
               "Enable traversal metrics"),
        EnvVar("TRAVERSAL_ENABLE_TRACING", bool, False, False,
               "Enable distributed tracing"),
    ]
    
    for var in traversal_vars:
        traversal_ns.add_var(var)
    
    unified_env.register_namespace(traversal_ns)


def register_validation_config():
    """Register validation-specific configuration"""
    validation_ns = ConfigNamespace("validation", "Schema validation configuration")
    
    validation_vars = [
        # Validation levels
        EnvVar("VALIDATION_DEFAULT_LEVEL", str, False, "STANDARD",
               "Default validation level",
               validator=lambda v: v in ["MINIMAL", "STANDARD", "STRICT", "PARANOID"]),
        
        # Cache settings
        EnvVar("VALIDATION_CACHE_ENABLED", bool, False, True,
               "Enable validation result caching"),
        EnvVar("VALIDATION_CACHE_TTL", int, False, 300,
               "Cache TTL in seconds"),
        
        # Security settings
        EnvVar("VALIDATION_ENABLE_SECURITY", bool, False, True,
               "Enable security validation"),
        EnvVar("VALIDATION_MAX_SECURITY_SCORE", int, False, 70,
               "Maximum acceptable security score",
               validator=lambda v: 0 <= v <= 100),
        
        # Performance
        EnvVar("VALIDATION_RATE_LIMIT", int, False, 1000,
               "Validations per minute limit"),
        EnvVar("VALIDATION_TIMEOUT_MS", int, False, 5000,
               "Validation timeout in milliseconds"),
    ]
    
    for var in validation_vars:
        validation_ns.add_var(var)
    
    unified_env.register_namespace(validation_ns)


def register_scheduler_config():
    """Register scheduler-specific configuration"""
    scheduler_ns = ConfigNamespace("scheduler", "Job scheduler configuration")
    
    scheduler_vars = [
        # Redis settings
        EnvVar("SCHEDULER_REDIS_PREFIX", str, False, "scheduler:",
               "Redis key prefix"),
        EnvVar("SCHEDULER_REDIS_TTL", int, False, 86400,
               "Redis key TTL in seconds"),
        
        # Job settings
        EnvVar("SCHEDULER_MAX_RETRIES", int, False, 3,
               "Maximum job retry attempts"),
        EnvVar("SCHEDULER_RETRY_DELAY", int, False, 60,
               "Retry delay in seconds"),
        EnvVar("SCHEDULER_JOB_TIMEOUT", int, False, 300,
               "Job execution timeout in seconds"),
        
        # Worker settings
        EnvVar("SCHEDULER_WORKER_COUNT", int, False, 4,
               "Number of worker threads/processes"),
        EnvVar("SCHEDULER_QUEUE_SIZE", int, False, 1000,
               "Maximum queue size"),
    ]
    
    for var in scheduler_vars:
        scheduler_ns.add_var(var)
    
    unified_env.register_namespace(scheduler_ns)


def register_event_config():
    """Register event publishing configuration"""
    event_ns = ConfigNamespace("event", "Event publishing configuration")
    
    event_vars = [
        # NATS settings
        EnvVar("EVENT_NATS_URL", str, False, "nats://localhost:4222",
               "NATS server URL"),
        EnvVar("EVENT_NATS_CLUSTER", str, False, "oms-cluster",
               "NATS cluster name"),
        
        # Publishing settings
        EnvVar("EVENT_BATCH_SIZE", int, False, 100,
               "Event batch size"),
        EnvVar("EVENT_BATCH_TIMEOUT_MS", int, False, 100,
               "Batch timeout in milliseconds"),
        EnvVar("EVENT_MAX_RETRIES", int, False, 3,
               "Maximum retry attempts"),
        
        # Outbox settings
        EnvVar("EVENT_OUTBOX_ENABLED", bool, False, True,
               "Enable transactional outbox"),
        EnvVar("EVENT_OUTBOX_POLL_INTERVAL", int, False, 5,
               "Outbox poll interval in seconds"),
    ]
    
    for var in event_vars:
        event_ns.add_var(var)
    
    unified_env.register_namespace(event_ns)


def register_middleware_config():
    """Register middleware configuration"""
    middleware_ns = ConfigNamespace("middleware", "Middleware configuration")
    
    middleware_vars = [
        # Service discovery
        EnvVar("MIDDLEWARE_SERVICE_DISCOVERY_ENABLED", bool, False, True,
               "Enable service discovery"),
        EnvVar("MIDDLEWARE_SERVICE_REGISTRY_URL", str, False, "",
               "Service registry URL"),
        
        # Rate limiting
        EnvVar("MIDDLEWARE_RATE_LIMIT_ENABLED", bool, False, True,
               "Enable rate limiting"),
        EnvVar("MIDDLEWARE_RATE_LIMIT_WINDOW", int, False, 60,
               "Rate limit window in seconds"),
        EnvVar("MIDDLEWARE_RATE_LIMIT_MAX_REQUESTS", int, False, 100,
               "Maximum requests per window"),
        
        # Circuit breaker
        EnvVar("MIDDLEWARE_CIRCUIT_BREAKER_ENABLED", bool, False, True,
               "Enable circuit breaker"),
        EnvVar("MIDDLEWARE_CIRCUIT_BREAKER_THRESHOLD", int, False, 5,
               "Failure threshold"),
        EnvVar("MIDDLEWARE_CIRCUIT_BREAKER_TIMEOUT", int, False, 60,
               "Circuit breaker timeout in seconds"),
    ]
    
    for var in middleware_vars:
        middleware_ns.add_var(var)
    
    unified_env.register_namespace(middleware_ns)


def register_all_namespaces():
    """Register all domain-specific namespaces"""
    # Core namespaces
    register_security_namespace()
    register_database_namespace()
    register_service_namespace()
    
    # Domain-specific namespaces
    register_traversal_config()
    register_validation_config()
    register_scheduler_config()
    register_event_config()
    register_middleware_config()
    
    # Log registration summary
    from shared.utils.logger import get_logger
    logger = get_logger(__name__)
    
    schema = unified_env.export_schema()
    total_vars = sum(len(ns['vars']) for ns in schema['namespaces'].values())
    
    logger.info(f"Registered {len(schema['namespaces'])} namespaces with {total_vars} variables")
    for ns_name, ns_data in schema['namespaces'].items():
        logger.info(f"  - {ns_name}: {len(ns_data['vars'])} variables")


# Auto-register on import
register_all_namespaces()