"""
Environment Configuration Manager
Centralized configuration with validation and fail-fast behavior
"""
import os
import sys
from typing import Optional, Dict, Any, List, Set, callable
from dataclasses import dataclass, field
from enum import Enum

from utils.logger import get_logger

logger = get_logger(__name__)


class Environment(Enum):
    """Supported environments"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing"""
    pass


class ConfigErrorAction(Enum):
    """Actions to take when configuration errors are detected."""
    EXIT = "exit"
    WARN = "warn"
    IGNORE = "ignore"


@dataclass
class EnvVar:
    """Environment variable definition."""
    name: str
    required: bool = True
    default: Optional[str] = None
    description: Optional[str] = None
    validator: Optional[callable] = None
    
    def validate_value(self, value: str) -> bool:
        """Validate the environment variable value."""
        if self.validator:
            try:
                return self.validator(value)
            except Exception:
                return False
        return True


@dataclass 
class ValidationResult:
    """Result of environment validation."""
    valid: bool
    missing: List[str] = field(default_factory=list)
    invalid: List[tuple[str, str]] = field(default_factory=list)  # (name, reason)
    warnings: List[str] = field(default_factory=list)


class StrictEnv:
    """
    Strict environment variable validation and access.
    
    Provides fail-fast behavior for missing critical configuration
    to prevent runtime failures in production.
    """
    
    # Core required environment variables
    CORE_REQUIRED = [
        EnvVar("TERMINUS_DB_URL", description="TerminusDB connection URL"),
        EnvVar("TERMINUS_DB_TOKEN", description="TerminusDB authentication token"),
        EnvVar("TERMINUS_DB_TEAM", description="TerminusDB team name"),
        EnvVar("TERMINUS_DB_NAME", description="TerminusDB database name"),
        EnvVar("REDIS_URL", description="Redis connection URL"),
        EnvVar("JWT_SECRET", description="JWT signing secret"),
        EnvVar("JWT_SECRET_KEY", description="JWT signing secret key"),
        EnvVar("USER_SERVICE_URL", description="User service URL",
               validator=lambda v: v.startswith(("http://", "https://"))),
        EnvVar("IAM_SERVICE_URL", description="IAM service URL",
               validator=lambda v: v.startswith(("http://", "https://"))),
    ]
    
    # Service-specific required variables
    SERVICE_REQUIRED = {
        "actions": [
            EnvVar("ACTIONS_SERVICE_URL", description="Actions service URL",
                   validator=lambda v: v.startswith(("http://", "https://"))),
        ],
        "audit": [
            EnvVar("AUDIT_SERVICE_URL", description="Audit service URL",
                   validator=lambda v: v.startswith(("http://", "https://"))),
        ],
        "scheduler": [
            EnvVar("SCHEDULER_REDIS_PREFIX", default="scheduler:",
                   description="Redis key prefix for scheduler"),
        ],
        "nats": [
            EnvVar("NATS_URL", description="NATS messaging URL"),
        ],
    }
    
    # Optional variables with defaults
    OPTIONAL = [
        EnvVar("LOG_LEVEL", required=False, default="INFO",
               validator=lambda v: v in ["DEBUG", "INFO", "WARNING", "ERROR"]),
        EnvVar("ENVIRONMENT", required=False, default="development",
               validator=lambda v: v in ["development", "staging", "production", "test"]),
        EnvVar("MAX_RETRY_ATTEMPTS", required=False, default="3",
               validator=lambda v: v.isdigit() and 1 <= int(v) <= 10),
        EnvVar("VALIDATION_LEVEL", required=False, default="STANDARD"),
        EnvVar("ENABLE_METRICS", required=False, default="true"),
        EnvVar("ENABLE_TRACING", required=False, default="true"),
    ]
    
    @classmethod
    def validate(
        cls,
        services: Optional[List[str]] = None,
        action: ConfigErrorAction = ConfigErrorAction.EXIT
    ) -> ValidationResult:
        """
        Validate environment variables.
        
        Args:
            services: List of service names to validate specific requirements
            action: Action to take on validation failure
            
        Returns:
            ValidationResult object
        """
        result = ValidationResult(valid=True)
        
        # Skip validation in test environment
        if os.getenv("ENVIRONMENT", "").lower() == "test":
            return result
        
        # Check core required variables  
        cls._check_vars(cls.CORE_REQUIRED, result)
        
        # Check service-specific variables
        if services:
            for service in services:
                if service in cls.SERVICE_REQUIRED:
                    cls._check_vars(cls.SERVICE_REQUIRED[service], result)
        
        # Check optional variables and set defaults
        cls._check_optional_vars(cls.OPTIONAL, result)
        
        # Check for deprecated variables
        cls._check_deprecated_vars(result)
        
        # Take action based on validation result
        if not result.valid:
            cls._handle_validation_failure(result, action)
            
        return result
    
    @classmethod
    def validate_or_die(cls, services: Optional[List[str]] = None) -> None:
        """
        Validate environment and exit if invalid.
        
        This should be called at application startup.
        """
        cls.validate(services=services, action=ConfigErrorAction.EXIT)
    
    @classmethod
    def get(cls, name: str, default: Optional[str] = None) -> str:
        """
        Get environment variable value with validation.
        
        Args:
            name: Environment variable name
            default: Default value if not set
            
        Returns:
            Environment variable value
            
        Raises:
            ValueError: If variable is required but not set
        """
        value = os.getenv(name, default)
        if value is None and os.getenv("ENVIRONMENT", "").lower() != "test":
            raise ValueError(f"Required environment variable '{name}' is not set")
        return value
    
    @classmethod
    def get_bool(cls, name: str, default: bool = False) -> bool:
        """Get environment variable as boolean."""
        value = os.getenv(name, str(default)).lower()
        return value in ("true", "1", "yes", "on")
    
    @classmethod
    def get_int(cls, name: str, default: int = 0) -> int:
        """Get environment variable as integer."""
        value = os.getenv(name, str(default))
        try:
            return int(value)
        except ValueError:
            raise ValueError(f"Environment variable '{name}' must be an integer, got '{value}'")
    
    @classmethod
    def _check_vars(cls, vars: List[EnvVar], result: ValidationResult) -> None:
        """Check a list of environment variables."""
        for var in vars:
            value = os.getenv(var.name, var.default)
            
            if var.required and value is None:
                result.valid = False
                result.missing.append(var.name)
            elif value is not None and not var.validate_value(value):
                result.valid = False
                result.invalid.append((var.name, f"Invalid value: '{value}'"))
    
    @classmethod
    def _check_optional_vars(cls, vars: List[EnvVar], result: ValidationResult) -> None:
        """Check optional variables and set defaults if needed."""
        for var in vars:
            if not var.required and var.default is not None:
                current = os.getenv(var.name)
                if current is None:
                    os.environ[var.name] = var.default
                    result.warnings.append(
                        f"Optional variable '{var.name}' not set, using default: '{var.default}'"
                    )
    
    @classmethod
    def _check_deprecated_vars(cls, result: ValidationResult) -> None:
        """Check for deprecated environment variables."""
        deprecated = {
            "DB_URL": "Use TERMINUS_DB_URL instead",
            "API_KEY": "Use TERMINUS_DB_TOKEN instead",
            "USE_CACHE": "Caching is now always enabled",
        }
        
        for old_var, message in deprecated.items():
            if os.getenv(old_var):
                result.warnings.append(f"Deprecated variable '{old_var}': {message}")
    
    @classmethod
    def _handle_validation_failure(
        cls,
        result: ValidationResult,
        action: ConfigErrorAction
    ) -> None:
        """Handle validation failure based on action."""
        if action == ConfigErrorAction.IGNORE:
            return
            
        # Log validation errors
        logger.error("Environment validation failed")
        
        if result.missing:
            logger.error(f"Missing required variables: {', '.join(result.missing)}")
            
        for name, reason in result.invalid:
            logger.error(f"Invalid variable '{name}': {reason}")
            
        for warning in result.warnings:
            logger.warning(warning)
        
        if action == ConfigErrorAction.EXIT:
            logger.error("Exiting due to environment validation failure")
            sys.exit(1)


class EnvironmentConfig:
    """
    Centralized environment configuration
    Validates required environment variables and provides safe defaults
    """
    
    # Required environment variables in production
    REQUIRED_IN_PRODUCTION = [
        "TERMINUS_DB_URL",
        "REDIS_URL",
        "NATS_URL",
        "JWT_SECRET_KEY",
        "DATABASE_URL",
        "ACTIONS_SERVICE_URL"
    ]
    
    # Optional with sensible defaults
    OPTIONAL_WITH_DEFAULTS = {
        "LOG_LEVEL": "INFO",
        "VALIDATION_LEVEL": "STANDARD",
        "ENABLE_METRICS": "true",
        "ENABLE_TRACING": "true",
        "MAX_CONNECTIONS": "100",
        "CONNECTION_TIMEOUT": "30",
        "REQUEST_TIMEOUT": "300",
        "BATCH_SIZE": "50"
    }
    
    def __init__(self):
        self.environment = self._get_environment()
        self._validate_required_vars()
        self._config_cache: Dict[str, Any] = {}
    
    def _get_environment(self) -> Environment:
        """Get current environment with validation"""
        env_str = os.getenv("ENVIRONMENT", "development").lower()
        try:
            return Environment(env_str)
        except ValueError:
            raise ConfigurationError(
                f"Invalid environment: {env_str}. "
                f"Must be one of: {[e.value for e in Environment]}"
            )
    
    def _validate_required_vars(self):
        """Validate required environment variables"""
        if self.environment == Environment.PRODUCTION:
            missing_vars = []
            for var in self.REQUIRED_IN_PRODUCTION:
                if not os.getenv(var):
                    missing_vars.append(var)
            
            if missing_vars:
                raise ConfigurationError(
                    f"Missing required environment variables in production: {missing_vars}"
                )
    
    def get(self, key: str, default: Optional[str] = None) -> str:
        """
        Get configuration value with validation
        
        Args:
            key: Configuration key
            default: Default value if not set
            
        Returns:
            Configuration value
            
        Raises:
            ConfigurationError: If required value is missing
        """
        # Check cache first
        if key in self._config_cache:
            return self._config_cache[key]
        
        # Get from environment
        value = os.getenv(key)
        
        # Check optional defaults
        if value is None and key in self.OPTIONAL_WITH_DEFAULTS:
            value = self.OPTIONAL_WITH_DEFAULTS[key]
        
        # Use provided default
        if value is None and default is not None:
            value = default
        
        # Validate required values
        if value is None and self.environment == Environment.PRODUCTION:
            if key in self.REQUIRED_IN_PRODUCTION:
                raise ConfigurationError(
                    f"Required configuration '{key}' is missing in production"
                )
        
        # Prevent localhost in production
        if value and self.environment == Environment.PRODUCTION:
            if "localhost" in value or "127.0.0.1" in value:
                raise ConfigurationError(
                    f"Configuration '{key}' contains localhost URL in production: {value}"
                )
        
        # Cache the value
        if value is not None:
            self._config_cache[key] = value
        
        return value
    
    def get_int(self, key: str, default: int = 0) -> int:
        """Get configuration value as integer"""
        value = self.get(key, str(default))
        try:
            return int(value)
        except ValueError:
            raise ConfigurationError(f"Invalid integer value for '{key}': {value}")
    
    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get configuration value as boolean"""
        value = self.get(key, str(default).lower())
        return value.lower() in ("true", "1", "yes", "on")
    
    def get_list(self, key: str, default: Optional[list] = None) -> list:
        """Get configuration value as list (comma-separated)"""
        value = self.get(key)
        if value is None:
            return default or []
        return [item.strip() for item in value.split(",") if item.strip()]
    
    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment == Environment.PRODUCTION
    
    @property
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.environment == Environment.DEVELOPMENT
    
    @property
    def is_test(self) -> bool:
        """Check if running in test"""
        return self.environment == Environment.TEST
    
    def get_terminus_db_url(self) -> str:
        """Get TerminusDB URL with validation"""
        if self.is_development:
            return self.get("TERMINUS_DB_URL", "http://localhost:6363")
        return self.get("TERMINUS_DB_URL")  # Required in production
    
    def get_redis_url(self) -> str:
        """Get Redis URL with validation"""
        if self.is_development:
            return self.get("REDIS_URL", "redis://localhost:6379")
        return self.get("REDIS_URL")  # Required in production
    
    def get_nats_url(self) -> str:
        """Get NATS URL with validation"""
        if self.is_development:
            return self.get("NATS_URL", "nats://localhost:4222")
        return self.get("NATS_URL")  # Required in production
    
    def get_database_url(self) -> str:
        """Get database URL with validation"""
        if self.is_development:
            return self.get("DATABASE_URL", "postgresql://user:password@localhost/oms_db")
        return self.get("DATABASE_URL")  # Required in production
    
    def get_actions_service_url(self) -> str:
        """Get Actions Service URL with validation"""
        if self.is_development:
            return self.get("ACTIONS_SERVICE_URL", "http://localhost:8009")
        return self.get("ACTIONS_SERVICE_URL")  # Required in production
    
    async def validate_actions_service_health(self) -> bool:
        """Validate Actions Service health by calling /health endpoint"""
        import httpx
        import asyncio
        
        actions_url = self.get_actions_service_url()
        health_url = f"{actions_url.rstrip('/')}/health"
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(health_url)
                if response.status_code == 200:
                    logger.info(f"Actions Service health check passed: {health_url}")
                    return True
                else:
                    logger.warning(f"Actions Service health check failed: {health_url} -> {response.status_code}")
                    return False
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.error(f"Actions Service unreachable: {health_url} -> {e}")
            if self.is_production:
                raise ConfigurationError(f"Actions Service unreachable in production: {health_url}")
            return False
        except Exception as e:
            logger.error(f"Actions Service health check error: {e}")
            return False
    
    def validate_all(self) -> Dict[str, str]:
        """
        Validate all configuration and return summary
        
        Returns:
            Dictionary of all configuration values
        """
        config = {
            "environment": self.environment.value,
            "terminus_db_url": self.get_terminus_db_url(),
            "redis_url": "***" if self.get_redis_url() else None,  # Hide sensitive
            "nats_url": self.get_nats_url(),
            "database_url": "***" if self.get_database_url() else None,  # Hide sensitive
            "actions_service_url": self.get_actions_service_url(),
            "log_level": self.get("LOG_LEVEL"),
            "validation_level": self.get("VALIDATION_LEVEL"),
            "enable_metrics": self.get_bool("ENABLE_METRICS"),
            "enable_tracing": self.get_bool("ENABLE_TRACING")
        }
        
        logger.info(f"Configuration validated for {self.environment.value} environment")
        return config


# Global configuration instance
_config: Optional[EnvironmentConfig] = None


def get_config() -> EnvironmentConfig:
    """Get global configuration instance"""
    global _config
    if _config is None:
        _config = EnvironmentConfig()
    return _config


def validate_config():
    """Validate configuration on startup"""
    config = get_config()
    summary = config.validate_all()
    logger.info(f"Configuration summary: {summary}")
    return summary


# Convenience functions for backward compatibility
def get_env(name: str, default: Optional[str] = None) -> str:
    """Get environment variable (backward compatible)."""
    return StrictEnv.get(name, default)


def require_env(name: str) -> str:
    """Require environment variable (backward compatible)."""
    return StrictEnv.get(name)