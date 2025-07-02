"""
Enterprise validation interfaces and data models - Interface Layer
"""

from .models import (
    ValidationLevel,
    ValidationScope,
    ValidationCategory,
    ValidationError,
    ValidationMetrics,
    ValidationResult,
    ValidationConfig
)

from .contracts import (
    ValidationRuleInterface,
    ValidationCacheInterface,
    ValidationServiceInterface
)

__all__ = [
    # Enums
    'ValidationLevel',
    'ValidationScope',
    'ValidationCategory',
    # Models
    'ValidationError',
    'ValidationMetrics',
    'ValidationResult',
    'ValidationConfig',
    # Contracts
    'ValidationRuleInterface',
    'ValidationCacheInterface',
    'ValidationServiceInterface'
]