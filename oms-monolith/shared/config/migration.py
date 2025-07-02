"""
Configuration migration helpers - Smooth transition from old configs
"""

import warnings
from typing import Any, Optional, Dict
from .unified_env import unified_env, ConfigurationError


class LegacyConfigAdapter:
    """Adapter for legacy configuration access patterns"""
    
    def __init__(self, namespace: str):
        self.namespace = namespace
    
    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """Get config value with legacy interface"""
        try:
            return unified_env.get(key, namespace=self.namespace)
        except ConfigurationError:
            if default is not None:
                return default
            raise
    
    def __getattr__(self, name: str) -> Any:
        """Support attribute-style access"""
        return self.get(name.upper())


def migrate_strict_env():
    """
    Migrate from StrictEnv to unified configuration
    """
    warnings.warn(
        "StrictEnv is deprecated. Use shared.config.unified_env instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    class StrictEnvCompat:
        """Compatibility wrapper for StrictEnv"""
        
        @staticmethod
        def get(key: str, default: Optional[str] = None) -> str:
            try:
                return str(unified_env.get(key))
            except ConfigurationError:
                if default is not None:
                    return default
                raise
        
        @staticmethod
        def require(key: str) -> str:
            return str(unified_env.get(key))
        
        @staticmethod
        def validate(services: Optional[List[str]] = None, 
                    error_action: str = "exit") -> bool:
            errors = unified_env.validate(fail_fast=(error_action == "exit"))
            return len(errors) == 0
    
    return StrictEnvCompat()


def migrate_traversal_config():
    """
    Migrate from core.traversal.config to unified configuration
    """
    warnings.warn(
        "core.traversal.config is deprecated. Use shared.config.unified_env.get_namespace_config('traversal').",
        DeprecationWarning,
        stacklevel=2
    )
    
    return unified_env.get_namespace_config('traversal')


def migrate_validation_config():
    """
    Migrate from core.validation.config to unified configuration
    """
    warnings.warn(
        "core.validation.config is deprecated. Use shared.config.unified_env.get_namespace_config('validation').",
        DeprecationWarning,
        stacklevel=2
    )
    
    return unified_env.get_namespace_config('validation')


def migrate_service_config():
    """
    Migrate from middleware.service_config to unified configuration
    """
    warnings.warn(
        "middleware.service_config is deprecated. Use shared.config.unified_env.",
        DeprecationWarning,
        stacklevel=2
    )
    
    # Return a dict-like object with all service URLs
    service_urls = {}
    
    # Get all URLs from core namespace
    core_config = unified_env.get_namespace_config('core')
    for key, value in core_config.items():
        if key.endswith('_url'):
            service_name = key.replace('_service_url', '').replace('_url', '')
            service_urls[service_name] = value
    
    return service_urls


# Monkey-patch helpers
def patch_legacy_configs():
    """
    Patch legacy configuration imports for zero-downtime migration.
    Call during application startup.
    """
    import sys
    
    # Create mock modules for legacy imports
    class MockConfigModule:
        def __init__(self, namespace: str, migrator_func):
            self.namespace = namespace
            self.migrator_func = migrator_func
            self._config = None
        
        def __getattr__(self, name: str):
            if self._config is None:
                self._config = self.migrator_func()
            
            if hasattr(self._config, name):
                return getattr(self._config, name)
            
            # Try to get from unified env
            try:
                return unified_env.get(name, namespace=self.namespace)
            except ConfigurationError:
                raise AttributeError(f"Config '{name}' not found")
    
    # Patch StrictEnv
    if 'shared.config.environment' not in sys.modules:
        sys.modules['shared.config.environment'] = type(sys)('environment')
    sys.modules['shared.config.environment'].StrictEnv = migrate_strict_env
    
    # Patch traversal config
    if 'core.traversal.config' not in sys.modules:
        sys.modules['core.traversal.config'] = MockConfigModule(
            'traversal', migrate_traversal_config
        )
    
    # Patch validation config
    if 'core.validation.config' not in sys.modules:
        sys.modules['core.validation.config'] = MockConfigModule(
            'validation', migrate_validation_config
        )
    
    # Patch service config
    if 'middleware.service_config' not in sys.modules:
        sys.modules['middleware.service_config'] = MockConfigModule(
            'middleware', migrate_service_config
        )