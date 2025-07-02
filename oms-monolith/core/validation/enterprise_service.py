"""
Enterprise Validation Service

This module provides backward compatibility by re-exporting the refactored
3-layer architecture components.
"""

# Re-export interface layer
from core.validation.enterprise.interfaces import (
    ValidationLevel,
    ValidationScope,
    ValidationCategory,
    ValidationError,
    ValidationMetrics,
    ValidationResult,
    ValidationConfig
)

# Re-export implementation layer
from core.validation.enterprise.implementations import (
    BaseValidationRule as ValidationRule,
    RequiredFieldsRule,
    FieldLengthRule,
    NamingConventionRule,
    DataTypeValidationRule,
    SecurityValidationRule,
    ReferenceIntegrityRule,
    ReservedNamesRule,
    DuplicateDetectionRule,
    ValidationCache,
    ValidationRuleRegistry
)

# Re-export service layer
from core.validation.enterprise.services import (
    EnterpriseValidationService,
    get_enterprise_validation_service
)

# Maintain backward compatibility
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
    # Rules
    'ValidationRule',
    'RequiredFieldsRule',
    'FieldLengthRule',
    'NamingConventionRule',
    'DataTypeValidationRule',
    'SecurityValidationRule',
    'ReferenceIntegrityRule',
    'ReservedNamesRule',
    'DuplicateDetectionRule',
    # Infrastructure
    'ValidationCache',
    'ValidationRuleRegistry',
    # Services
    'EnterpriseValidationService',
    'get_enterprise_validation_service'
]