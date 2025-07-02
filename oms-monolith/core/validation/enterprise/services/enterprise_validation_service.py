"""
Enterprise validation service implementation
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, Any, Optional, List, Set
from datetime import datetime

from ..interfaces.contracts import ValidationServiceInterface, ValidationRuleInterface
from ..interfaces.models import (
    ValidationResult,
    ValidationError,
    ValidationLevel,
    ValidationScope,
    ValidationCategory,
    ValidationMetrics,
    ValidationConfig
)
from ..implementations.validation_cache import ValidationCache
from ..implementations.rule_registry import ValidationRuleRegistry
from ..implementations.validation_rules import (
    RequiredFieldsRule,
    FieldLengthRule,
    NamingConventionRule,
    DataTypeValidationRule,
    SecurityValidationRule,
    ReferenceIntegrityRule,
    ReservedNamesRule,
    DuplicateDetectionRule
)

from core.validation.input_sanitization import (
    InputSanitizer, SanitizationLevel, get_input_sanitizer
)
from shared.monitoring.metrics import metrics_collector
from shared.events import EventPublisher

logger = logging.getLogger(__name__)


class EnterpriseValidationService(ValidationServiceInterface):
    """
    Production-grade validation service with comprehensive security,
    performance optimization, and monitoring capabilities.
    """
    
    def __init__(
        self,
        config: Optional[ValidationConfig] = None,
        event_publisher: Optional[EventPublisher] = None,
        metrics_collector: Optional[Any] = None
    ):
        self.config = config or ValidationConfig()
        self.event_publisher = event_publisher
        self.metrics_collector = metrics_collector
        
        # Initialize components
        self.rule_registry = ValidationRuleRegistry()
        self.cache = ValidationCache(
            max_size=self.config.max_cache_size,
            default_ttl=self.config.cache_ttl_seconds
        ) if self.config.enable_caching else None
        
        self.input_sanitizer = get_input_sanitizer() if self.config.enable_input_sanitization else None
        
        # Initialize metrics
        self.metrics = ValidationMetrics()
        self._metrics_lock = asyncio.Lock() if asyncio._get_running_loop() else None
        
        # Register default rules
        self._register_default_rules()
        
        # Start metrics reporting if enabled
        if self.config.enable_metrics and self.metrics_collector:
            self._start_metrics_reporting()
    
    def validate(
        self,
        data: Dict[str, Any],
        validation_level: Optional[ValidationLevel] = None,
        validation_scope: Optional[ValidationScope] = None,
        skip_rules: Optional[Set[str]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """Perform comprehensive validation"""
        start_time = time.time()
        request_id = str(uuid.uuid4())
        
        # Use default level if not specified
        validation_level = validation_level or self.config.default_validation_level
        validation_scope = validation_scope or ValidationScope.REQUEST
        skip_rules = skip_rules or set()
        context = context or {}
        
        # Check cache first
        cache_key = None
        if self.cache and self.config.enable_caching:
            cache_key = ValidationCache.generate_cache_key(
                data, validation_level.value, validation_scope.value
            )
            cached_result = self.cache.get(cache_key)
            if cached_result:
                self._update_metrics_cache_hit()
                cached_result.cache_used = True
                return cached_result
        
        # Sanitize input if enabled
        sanitized_data = data
        if self.input_sanitizer and self.config.enable_input_sanitization:
            sanitization_result = self.input_sanitizer.sanitize(
                data,
                SanitizationLevel.STRICT if validation_level == ValidationLevel.PARANOID else SanitizationLevel.STANDARD
            )
            sanitized_data = sanitization_result.sanitized_data
        
        # Get applicable rules
        rules = self.rule_registry.get_rules_for_level(validation_level)
        
        # Apply rules
        all_errors = []
        warnings = []
        security_score = 100
        
        for rule in rules:
            if rule.get_rule_id() in skip_rules:
                continue
            
            try:
                errors = rule.validate(sanitized_data, context)
                
                # Categorize errors
                for error in errors:
                    if error.severity in ["critical", "high"]:
                        all_errors.append(error)
                        # Deduct security score for security errors
                        if error.category == ValidationCategory.SECURITY:
                            security_score -= 20
                    else:
                        warnings.append(error)
                        if error.category == ValidationCategory.SECURITY:
                            security_score -= 5
                            
            except Exception as e:
                logger.error(f"Rule {rule.get_rule_id()} failed: {str(e)}")
                # Add error about rule failure
                all_errors.append(ValidationError(
                    field="__system__",
                    message=f"Validation rule '{rule.get_rule_id()}' failed",
                    category=ValidationCategory.PERFORMANCE,
                    severity="medium",
                    code="RULE_EXECUTION_FAILED",
                    context={"rule_id": rule.get_rule_id(), "error": str(e)}
                ))
        
        # Create result
        is_valid = len(all_errors) == 0 and security_score >= self.config.max_security_score_threshold
        
        result = ValidationResult(
            request_id=request_id,
            is_valid=is_valid,
            validation_level=validation_level,
            errors=all_errors,
            warnings=warnings,
            sanitized_data=sanitized_data if sanitized_data != data else None,
            security_score=max(0, security_score),
            performance_impact_ms=(time.time() - start_time) * 1000,
            cache_used=False,
            metadata={
                "rules_applied": len(rules) - len(skip_rules),
                "validation_scope": validation_scope.value,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        # Cache result if enabled
        if self.cache and self.config.enable_caching and cache_key:
            self.cache.set(cache_key, result, self.config.cache_ttl_seconds)
        
        # Update metrics
        self._update_metrics(result)
        
        # Publish event if publisher available
        if self.event_publisher:
            self._publish_validation_event(result)
        
        return result
    
    def register_rule(self, rule: ValidationRuleInterface) -> None:
        """Register a validation rule"""
        self.rule_registry.register(rule)
    
    def unregister_rule(self, rule_id: str) -> bool:
        """Unregister a validation rule"""
        return self.rule_registry.unregister(rule_id)
    
    def get_metrics(self) -> ValidationMetrics:
        """Get validation service metrics"""
        return self.metrics.copy()
    
    def reset_metrics(self) -> None:
        """Reset validation metrics"""
        self.metrics = ValidationMetrics()
    
    def _register_default_rules(self):
        """Register default validation rules"""
        # Required fields rule
        self.register_rule(RequiredFieldsRule(
            required_fields={'name', 'type'}
        ))
        
        # Field length constraints
        self.register_rule(FieldLengthRule(
            field_constraints={
                'name': {'min': 1, 'max': 255},
                'description': {'min': 0, 'max': 1000},
                'type': {'min': 1, 'max': 50}
            }
        ))
        
        # Naming conventions
        self.register_rule(NamingConventionRule(
            naming_patterns={
                'name': r'^[a-zA-Z][a-zA-Z0-9_]*$',
                'type': r'^[a-zA-Z][a-zA-Z0-9_]*$'
            }
        ))
        
        # Data type validation
        self.register_rule(DataTypeValidationRule(
            type_constraints={
                'name': str,
                'type': str,
                'active': bool,
                'created_at': (str, datetime)
            }
        ))
        
        # Security validation
        if self.config.enable_security_validation:
            self.register_rule(SecurityValidationRule())
        
        # Reserved names
        self.register_rule(ReservedNamesRule(
            reserved_names={
                'admin', 'root', 'system', 'null', 'undefined',
                'true', 'false', 'id', '_id', '__proto__'
            }
        ))
    
    def _update_metrics(self, result: ValidationResult):
        """Update validation metrics"""
        self.metrics.total_validations += 1
        
        if result.is_valid:
            self.metrics.successful_validations += 1
        else:
            self.metrics.failed_validations += 1
        
        # Update average time
        current_avg = self.metrics.average_validation_time_ms
        new_avg = (
            (current_avg * (self.metrics.total_validations - 1) + result.performance_impact_ms) /
            self.metrics.total_validations
        )
        self.metrics.average_validation_time_ms = new_avg
        
        # Update error categories
        for error in result.errors:
            category = error.category.value
            self.metrics.errors_by_category[category] = (
                self.metrics.errors_by_category.get(category, 0) + 1
            )
        
        # Update security threats
        security_errors = [e for e in result.errors if e.category == ValidationCategory.SECURITY]
        if security_errors:
            self.metrics.security_threats_detected += len(security_errors)
    
    def _update_metrics_cache_hit(self):
        """Update cache hit metrics"""
        self.metrics.cache_hits += 1
    
    def _publish_validation_event(self, result: ValidationResult):
        """Publish validation event"""
        if not self.event_publisher:
            return
        
        event_data = {
            "request_id": result.request_id,
            "is_valid": result.is_valid,
            "validation_level": result.validation_level.value,
            "error_count": len(result.errors),
            "warning_count": len(result.warnings),
            "security_score": result.security_score,
            "performance_ms": result.performance_impact_ms,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            self.event_publisher.publish(
                "validation.completed",
                event_data
            )
        except Exception as e:
            logger.error(f"Failed to publish validation event: {str(e)}")
    
    def _start_metrics_reporting(self):
        """Start periodic metrics reporting"""
        # This would start a background task to report metrics
        # Implementation depends on the specific metrics collector
        pass


# Global instance
_validation_service: Optional[EnterpriseValidationService] = None

def get_enterprise_validation_service(
    config: Optional[ValidationConfig] = None,
    event_publisher: Optional[EventPublisher] = None,
    metrics_collector: Optional[Any] = None
) -> EnterpriseValidationService:
    """Get or create the global validation service instance"""
    global _validation_service
    
    if _validation_service is None:
        _validation_service = EnterpriseValidationService(
            config=config,
            event_publisher=event_publisher,
            metrics_collector=metrics_collector
        )
    
    return _validation_service