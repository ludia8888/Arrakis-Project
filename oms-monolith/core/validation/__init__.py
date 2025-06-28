# Validation Service Core Package

# Lazy import to prevent circular dependencies
def get_validation_service():
    from .service_refactored import ValidationServiceRefactored
    return ValidationServiceRefactored

# Direct imports
from .models import ValidationResult, ValidationContext
from .naming_config import NamingConfigService as NamingConfig
from .naming_convention import NamingConvention
from .naming_history import NamingConventionHistoryService as NamingHistory
from .policy_signing import PolicySigner
from .version_manager import VersionManager
from .service_refactored import ValidationServiceRefactored as ValidationService
from .merge_validation_service import MergeValidationService

__all__ = [
    "get_validation_service",
    "ValidationService",
    "ValidationResult", 
    "ValidationContext",
    "NamingConfig",
    "NamingConvention",
    "NamingHistory",
    "PolicySigner",
    "VersionManager",
    "MergeValidationService"
]
