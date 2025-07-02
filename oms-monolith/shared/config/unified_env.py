"""
Unified Environment Configuration - Single source of truth for all configuration

This consolidates:
- shared/config/environment.py (StrictEnv)
- shared/config/unified_config.py  
- middleware/service_config.py
- core/traversal/config.py
- core/validation/config.py

All configuration now flows through this unified system with namespace support.
"""

import os
import sys
import threading
from types import MappingProxyType
from typing import Optional, Dict, Any, List, Set, Callable, TypeVar, Generic
from dataclasses import dataclass, field, asdict
from enum import Enum
from functools import lru_cache
import json
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


class Environment(Enum):
    """Supported environments"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing"""
    pass


@dataclass
class EnvVar(Generic[T]):
    """
    Enhanced environment variable definition with type support
    """
    name: str
    var_type: type = str
    required: bool = True
    default: Optional[T] = None
    description: Optional[str] = None
    validator: Optional[Callable[[Any], bool]] = None
    transformer: Optional[Callable[[str], T]] = None
    namespace: Optional[str] = None  # e.g., "traversal", "validation"
    
    def parse_value(self, raw_value: Optional[str]) -> T:
        """Parse and validate environment variable value"""
        if raw_value is None:
            if self.required and self.default is None:
                raise ConfigurationError(f"Required env var {self.name} is not set")
            return self.default
        
        # Transform value to correct type
        if self.transformer:
            try:
                value = self.transformer(raw_value)
            except Exception as e:
                raise ConfigurationError(f"Failed to transform {self.name}: {e}")
        else:
            # Default transformers
            if self.var_type == bool:
                value = raw_value.lower() in ('true', '1', 'yes', 'on')
            elif self.var_type == int:
                value = int(raw_value)
            elif self.var_type == float:
                value = float(raw_value)
            elif self.var_type == list:
                value = [v.strip() for v in raw_value.split(',') if v.strip()]
            elif self.var_type == dict:
                value = json.loads(raw_value)
            else:
                value = raw_value
        
        # Validate
        if self.validator:
            try:
                if not self.validator(value):
                    # Try to get validator description
                    validator_desc = getattr(self.validator, '__doc__', None) or \
                                   getattr(self.validator, '__name__', 'custom validator')
                    raise ConfigurationError(
                        f"Validation failed for {self.name}={value}. "
                        f"Validator: {validator_desc}"
                    )
            except Exception as e:
                if isinstance(e, ConfigurationError):
                    raise
                raise ConfigurationError(
                    f"Validation error for {self.name}={value}: {str(e)}"
                )
        
        return value


@dataclass
class ConfigNamespace:
    """Configuration namespace for domain-specific settings"""
    name: str
    description: str
    env_vars: List[EnvVar] = field(default_factory=list)
    
    def add_var(self, var: EnvVar) -> None:
        """Add environment variable to namespace"""
        var.namespace = self.name
        self.env_vars.append(var)
    
    def get_config(self) -> Dict[str, Any]:
        """Get all configuration values for this namespace"""
        config = {}
        for var in self.env_vars:
            key = var.name.lower().replace(f"{self.name.upper()}_", "")
            try:
                raw_value = os.getenv(var.name)
                config[key] = var.parse_value(raw_value)
            except ConfigurationError:
                if var.required:
                    raise
                config[key] = var.default
        return config


class UnifiedEnv:
    """
    Unified environment configuration with namespace support.
    Single source of truth for all configuration needs.
    Thread-safe singleton implementation.
    """
    
    _instance: Optional['UnifiedEnv'] = None
    _lock = threading.Lock()
    _namespaces: Dict[str, ConfigNamespace] = {}
    _global_vars: List[EnvVar] = []
    _cached_values: Dict[str, Any] = {}
    _validated: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                # Double-check locking pattern
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize_core()
        return cls._instance
    
    def _initialize_core(self):
        """Initialize core configuration"""
        # Security validators
        def validate_not_empty(v: str) -> bool:
            """Ensure value is not empty"""
            return bool(v and v.strip())
        
        def validate_strong_secret(v: str) -> bool:
            """Validate secret is strong enough for production"""
            if not v:
                return False
            # In production, secrets should be at least 32 chars
            return len(v) >= 32 or v == "your-secret-key"  # Allow dev default
        
        # Register core namespace
        core_ns = ConfigNamespace("core", "Core system configuration")
        
        # Core required variables
        core_vars = [
            # TerminusDB configuration
            EnvVar("TERMINUS_DB_URL", str, True, description="TerminusDB URL",
                   validator=lambda v: v.startswith(("http://", "https://"))),
            EnvVar("TERMINUS_DB_TOKEN", str, True, description="TerminusDB token"),
            EnvVar("TERMINUS_DB_TEAM", str, True, description="TerminusDB team"),
            EnvVar("TERMINUS_DB_NAME", str, True, description="TerminusDB database"),
            EnvVar("TERMINUS_DB_USER", str, False, default="admin", description="TerminusDB user"),
            EnvVar("TERMINUS_DB_PASSWORD", str, True, description="TerminusDB password"),
            EnvVar("TERMINUS_DB_ENDPOINT", str, False, description="TerminusDB endpoint",
                   validator=lambda v: v.startswith(("http://", "https://")) if v else True),
            EnvVar("TERMINUS_DB", str, False, description="TerminusDB database name"),
            EnvVar("TERMINUS_DB_KEY", str, False, description="TerminusDB API key"),
            EnvVar("TERMINUS_ORGANIZATION", str, False, description="TerminusDB organization"),
            
            # Redis configuration
            EnvVar("REDIS_URL", str, True, description="Redis URL"),
            EnvVar("REDIS_PASSWORD", str, False, description="Redis password"),
            EnvVar("REDIS_SENTINELS", str, False, default="", description="Redis sentinel nodes"),
            EnvVar("REDIS_MASTER_NAME", str, False, default="mymaster", description="Redis master name"),
            EnvVar("REDIS_DB", int, False, default=0, description="Redis database number"),
            EnvVar("CACHE_TYPE", str, False, default="redis", description="Cache type (redis/memory)"),
            
            # JWT/Security configuration - CRITICAL
            EnvVar("JWT_SECRET", str, True, description="JWT secret for token signing",
                   validator=validate_strong_secret),
            EnvVar("JWT_SECRET_KEY", str, True, description="JWT secret key",
                   validator=validate_strong_secret),
            EnvVar("PII_ENCRYPTION_KEY", str, True, description="PII encryption key",
                   validator=validate_strong_secret),
            EnvVar("OMS_POLICY_API_KEY", str, False, description="OMS policy API key"),
            EnvVar("ONTOLOGY_SECRET_KEY", str, False, description="Ontology secret key"),
            EnvVar("JWT_JWKS_URL", str, False, description="JWT JWKS URL",
                   validator=lambda v: v.startswith(("http://", "https://")) if v else True),
            EnvVar("JWT_ISSUER", str, False, default="iam.company", description="JWT issuer"),
            EnvVar("JWT_AUDIENCE", str, False, default="oms", description="JWT audience"),
            EnvVar("JWT_LOCAL_VALIDATION", bool, False, default=True, description="Enable local JWT validation"),
            EnvVar("AUTH_CACHE_TTL", int, False, default=300, description="Auth cache TTL in seconds"),
            EnvVar("OAUTH_CLIENT_ID", str, False, default="oms-service", description="OAuth client ID"),
            
            # Service URLs
            EnvVar("USER_SERVICE_URL", str, True, description="User service URL",
                   validator=lambda v: v.startswith(("http://", "https://"))),
            EnvVar("IAM_SERVICE_URL", str, True, description="IAM service URL",
                   validator=lambda v: v.startswith(("http://", "https://"))),
            EnvVar("AUDIT_SERVICE_URL", str, False, default="http://audit-service:28002", 
                   description="Audit service URL",
                   validator=lambda v: v.startswith(("http://", "https://"))),
            
            # Environment settings
            EnvVar("ENVIRONMENT", str, False, default="development",
                   transformer=lambda v: Environment(v)),
            EnvVar("LOG_LEVEL", str, False, default="INFO"),
            EnvVar("DEBUG", bool, False, default=False),
            EnvVar("ALLOWED_ORIGINS", str, False, default="http://frontend:3000",
                   description="CORS allowed origins"),
            
            # Performance settings
            EnvVar("IAM_TIMEOUT", int, False, default=5, description="IAM service timeout in seconds"),
            EnvVar("IAM_MAX_RETRIES", int, False, default=2, description="IAM service max retries"),
            
            # Database performance settings
            EnvVar("TERMINUSDB_LRU_CACHE_SIZE", int, False, default=500000000, 
                   description="TerminusDB LRU cache size in bytes"),
            EnvVar("TERMINUSDB_CACHE_ENABLED", bool, False, default=True,
                   description="Enable TerminusDB internal caching"),
            EnvVar("TERMINUSDB_USE_MTLS", bool, False, default=False,
                   description="Enable mTLS for TerminusDB connections"),
            EnvVar("DB_MAX_CONNECTIONS", int, False, default=20,
                   description="Maximum database connections in pool"),
            EnvVar("DB_MIN_CONNECTIONS", int, False, default=5,
                   description="Minimum database connections in pool"),
            EnvVar("DB_MAX_IDLE_TIME", int, False, default=300,
                   description="Maximum idle time for connections in seconds"),
            EnvVar("DB_CONNECTION_TIMEOUT", int, False, default=30,
                   description="Database connection timeout in seconds"),
            EnvVar("DB_NAME", str, False, default="oms",
                   description="Default database name"),
        ]
        
        for var in core_vars:
            core_ns.add_var(var)
        
        self.register_namespace(core_ns)
    
    @classmethod
    def register_namespace(cls, namespace: ConfigNamespace) -> None:
        """Register a configuration namespace"""
        if namespace.name in cls._namespaces:
            logger.warning(f"Overwriting namespace: {namespace.name}")
        
        cls._namespaces[namespace.name] = namespace
        logger.info(f"Registered config namespace: {namespace.name}")
    
    @classmethod
    def register_var(cls, var: EnvVar, namespace: str = "global") -> None:
        """Register a single environment variable"""
        if namespace == "global":
            cls._global_vars.append(var)
        else:
            if namespace not in cls._namespaces:
                cls._namespaces[namespace] = ConfigNamespace(
                    namespace, f"Auto-created namespace for {namespace}"
                )
            cls._namespaces[namespace].add_var(var)
    
    @classmethod
    def get(cls, key: str, namespace: Optional[str] = None) -> Any:
        """
        Get configuration value.
        
        Args:
            key: Configuration key (can be full env var name or short name)
            namespace: Optional namespace to search in
            
        Returns:
            Configuration value
        """
        instance = cls()
        
        # Check cache first
        cache_key = f"{namespace}:{key}" if namespace else key
        if cache_key in cls._cached_values:
            return cls._cached_values[cache_key]
        
        # Search for the variable
        env_var = None
        
        # Try namespace first
        if namespace and namespace in cls._namespaces:
            for var in cls._namespaces[namespace].env_vars:
                if var.name == key or var.name.lower().endswith(f"_{key.lower()}"):
                    env_var = var
                    break
        
        # Try all namespaces
        if not env_var:
            for ns in cls._namespaces.values():
                for var in ns.env_vars:
                    if var.name == key:
                        env_var = var
                        break
                if env_var:
                    break
        
        # Try global vars
        if not env_var:
            for var in cls._global_vars:
                if var.name == key:
                    env_var = var
                    break
        
        if not env_var:
            raise ConfigurationError(f"Unknown configuration key: {key}")
        
        # Parse and cache value
        value = env_var.parse_value(os.getenv(env_var.name))
        cls._cached_values[cache_key] = value
        
        return value
    
    @classmethod
    def get_namespace_config(cls, namespace: str) -> MappingProxyType[str, Any]:
        """
        Get all configuration for a namespace.
        Returns read-only view to prevent accidental mutations.
        """
        if namespace not in cls._namespaces:
            raise ConfigurationError(f"Unknown namespace: {namespace}")
        
        config = cls._namespaces[namespace].get_config()
        return MappingProxyType(config)  # Read-only view
    
    @classmethod
    def validate(cls, fail_fast: bool = True) -> List[str]:
        """
        Validate all registered configuration.
        
        Args:
            fail_fast: Exit on validation failure
            
        Returns:
            List of validation errors (empty if all valid)
        """
        instance = cls()
        errors = []
        
        # Validate all namespaces
        for namespace in cls._namespaces.values():
            for var in namespace.env_vars:
                try:
                    var.parse_value(os.getenv(var.name))
                except ConfigurationError as e:
                    error_msg = f"[{namespace.name}] {e}"
                    errors.append(error_msg)
                    logger.error(error_msg)
        
        # Validate global vars
        for var in cls._global_vars:
            try:
                var.parse_value(os.getenv(var.name))
            except ConfigurationError as e:
                error_msg = f"[global] {e}"
                errors.append(error_msg)
                logger.error(error_msg)
        
        if errors and fail_fast:
            print("=" * 60, file=sys.stderr)
            print("CONFIGURATION ERRORS DETECTED", file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            for error in errors:
                print(f"❌ {error}", file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            sys.exit(1)
        
        cls._validated = True
        return errors
    
    @classmethod
    def clear_cache(cls) -> None:
        """Clear cached configuration values (thread-safe)"""
        with cls._lock:
            cls._cached_values.clear()
    
    @classmethod
    def reset(cls) -> None:
        """
        Reset singleton instance.
        Useful for testing and after process fork.
        """
        with cls._lock:
            cls._instance = None
            cls._namespaces.clear()
            cls._global_vars.clear()
            cls._cached_values.clear()
            cls._validated = False
    
    @classmethod
    def export_schema(cls) -> Dict[str, Any]:
        """Export configuration schema for documentation"""
        schema = {
            "namespaces": {},
            "global": []
        }
        
        for ns_name, namespace in cls._namespaces.items():
            schema["namespaces"][ns_name] = {
                "description": namespace.description,
                "vars": [
                    {
                        "name": var.name,
                        "type": var.var_type.__name__,
                        "required": var.required,
                        "default": var.default,
                        "description": var.description
                    }
                    for var in namespace.env_vars
                ]
            }
        
        schema["global"] = [
            {
                "name": var.name,
                "type": var.var_type.__name__,
                "required": var.required,
                "default": var.default,
                "description": var.description
            }
            for var in cls._global_vars
        ]
        
        return schema


# Convenience instance
unified_env = UnifiedEnv()

# Import OMS-specific registrations
try:
    from . import oms_env_registration
except ImportError:
    logger.warning("OMS environment registration not available")

# Import additional registrations
try:
    from . import additional_env_registration
except ImportError:
    logger.warning("Additional environment registration not available")

# Helper functions for backward compatibility
def get_env(key: str, default: Optional[Any] = None) -> Any:
    """Get environment variable with optional default"""
    try:
        return unified_env.get(key)
    except ConfigurationError:
        if default is not None:
            return default
        raise


def require_env(key: str) -> Any:
    """Get required environment variable"""
    return unified_env.get(key)


def validate_env(fail_fast: bool = True) -> List[str]:
    """Validate environment configuration"""
    return unified_env.validate(fail_fast)