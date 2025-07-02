"""
Enterprise validation interface contracts
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Set

from .models import (
    ValidationResult,
    ValidationError,
    ValidationLevel,
    ValidationScope,
    ValidationCategory,
    ValidationMetrics
)


class ValidationRuleInterface(ABC):
    """Base interface for validation rules"""
    
    @abstractmethod
    def validate(self, data: Dict[str, Any], context: Dict[str, Any]) -> List[ValidationError]:
        """Validate data and return list of errors"""
        pass
    
    @abstractmethod
    def get_rule_id(self) -> str:
        """Get unique rule identifier"""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """Get rule description"""
        pass
    
    @abstractmethod
    def get_category(self) -> ValidationCategory:
        """Get rule category"""
        pass


class ValidationCacheInterface(ABC):
    """Interface for validation result caching"""
    
    @abstractmethod
    def get(self, key: str) -> Optional[ValidationResult]:
        """Get cached validation result"""
        pass
    
    @abstractmethod
    def set(self, key: str, result: ValidationResult, ttl_seconds: int) -> None:
        """Cache validation result"""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete cached result"""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all cached results"""
        pass


class ValidationServiceInterface(ABC):
    """Main validation service interface"""
    
    @abstractmethod
    def validate(
        self,
        data: Dict[str, Any],
        validation_level: Optional[ValidationLevel] = None,
        validation_scope: Optional[ValidationScope] = None,
        skip_rules: Optional[Set[str]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """Perform comprehensive validation"""
        pass
    
    @abstractmethod
    def register_rule(self, rule: ValidationRuleInterface) -> None:
        """Register a validation rule"""
        pass
    
    @abstractmethod
    def unregister_rule(self, rule_id: str) -> bool:
        """Unregister a validation rule"""
        pass
    
    @abstractmethod
    def get_metrics(self) -> ValidationMetrics:
        """Get validation service metrics"""
        pass
    
    @abstractmethod
    def reset_metrics(self) -> None:
        """Reset validation metrics"""
        pass