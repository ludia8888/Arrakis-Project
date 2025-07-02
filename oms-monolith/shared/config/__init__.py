"""
Unified Configuration Module - Single source of truth for all configuration

This consolidates:
- shared/config/environment.py → Unified with namespace support
- shared/config/unified_config.py → Merged into unified system
- middleware/service_config.py → Service namespace
- core/traversal/config.py → Traversal namespace  
- core/validation/config.py → Validation namespace

All configuration now uses the namespace-based unified system.
"""

# Import unified configuration
from .unified_env import (
    UnifiedEnv,
    unified_env,
    Environment,
    ConfigurationError,
    EnvVar,
    ConfigNamespace,
    get_env,
    require_env,
    validate_env
)

# Import namespace configs (auto-registers them)
from .namespace_configs import (
    register_all_namespaces,
    register_traversal_config,
    register_validation_config,
    register_scheduler_config,
    register_event_config,
    register_middleware_config
)

# Import migration helpers
from .migration import (
    migrate_strict_env,
    migrate_traversal_config,
    migrate_validation_config,
    migrate_service_config,
    patch_legacy_configs,
    LegacyConfigAdapter
)

# Backward compatibility imports
from .environment import StrictEnv as _LegacyStrictEnv
StrictEnv = migrate_strict_env()  # Replace with compat wrapper

__all__ = [
    # Main interface
    'unified_env',
    'UnifiedEnv',
    'get_env',
    'require_env', 
    'validate_env',
    # Types
    'Environment',
    'ConfigurationError',
    'EnvVar',
    'ConfigNamespace',
    # Namespace registration
    'register_all_namespaces',
    # Migration
    'patch_legacy_configs',
    'LegacyConfigAdapter',
    # Backward compatibility
    'StrictEnv'
]

# Auto-patch legacy imports on module load
patch_legacy_configs()