"""
Enterprise Validation Service
Production-grade validation system with comprehensive security, performance optimization,
and monitoring capabilities for all OMS endpoints.
"""
import asyncio
import hashlib
import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable
from enum import Enum
from functools import lru_cache, wraps

from pydantic import BaseModel, Field, validator, ValidationError
import redis.asyncio as redis

from core.validation.input_sanitization import (
    InputSanitizer, SanitizationLevel, SanitizationResult,
    get_input_sanitizer
)
from core.validation.interfaces import ValidationResult as SchemaValidationResult
from shared.cache.smart_cache import SmartCacheManager
from shared.monitoring.metrics import metrics_collector
from shared.events import EventPublisher


logger = logging.getLogger(__name__)


class ValidationLevel(str, Enum):
    """Validation strictness levels"""
    MINIMAL = "minimal"      # Basic type checking only
    STANDARD = "standard"    # Standard validation with business rules
    STRICT = "strict"        # All validations including custom rules
    PARANOID = "paranoid"    # Maximum security with deep inspection


class ValidationScope(str, Enum):
    """Validation scope types"""
    REQUEST = "request"      # Incoming request validation
    RESPONSE = "response"    # Outgoing response validation
    SCHEMA = "schema"        # Schema change validation
    DATA = "data"           # Data integrity validation
    SECURITY = "security"   # Security-focused validation


class ValidationCategory(str, Enum):
    """Validation error categories"""
    SYNTAX = "syntax"
    SEMANTIC = "semantic"
    SECURITY = "security"
    BUSINESS = "business"
    PERFORMANCE = "performance"


class ValidationError(BaseModel):
    """Structured validation error"""
    field: str
    message: str
    category: ValidationCategory
    severity: str  # critical, high, medium, low
    code: str
    context: Dict[str, Any] = {}
    suggested_fix: Optional[str] = None


class ValidationMetrics(BaseModel):
    """Validation performance metrics"""
    total_validations: int = 0
    successful_validations: int = 0
    failed_validations: int = 0
    security_threats_detected: int = 0
    average_validation_time_ms: float = 0
    cache_hits: int = 0
    cache_misses: int = 0
    validation_by_type: Dict[str, int] = {}
    errors_by_category: Dict[str, int] = {}


class ValidationResult(BaseModel):
    """Comprehensive validation result"""
    request_id: str
    is_valid: bool
    validation_level: ValidationLevel
    errors: List[ValidationError] = []
    warnings: List[ValidationError] = []
    sanitized_data: Optional[Dict[str, Any]] = None
    security_score: int = 100  # 0-100, lower is worse
    performance_impact_ms: float = 0
    cache_used: bool = False
    metadata: Dict[str, Any] = {}


class ValidationRule:
    """Base class for validation rules"""
    
    def __init__(self, rule_id: str, description: str, category: ValidationCategory):
        self.rule_id = rule_id
        self.description = description
        self.category = category
        self.enabled = True
        self.priority = 50  # 0-100, higher runs first
    
    async def validate(self, data: Any, context: Dict[str, Any]) -> List[ValidationError]:
        """Validate data and return errors"""
        raise NotImplementedError


class ValidationRuleRegistry:
    """Registry for validation rules"""
    
    def __init__(self):
        self._rules: Dict[str, List[ValidationRule]] = defaultdict(list)
        self._global_rules: List[ValidationRule] = []
        self._rule_cache: Dict[str, ValidationRule] = {}
    
    def register_rule(self, rule: ValidationRule, entity_types: Optional[List[str]] = None):
        """Register a validation rule"""
        self._rule_cache[rule.rule_id] = rule
        
        if entity_types:
            for entity_type in entity_types:
                self._rules[entity_type].append(rule)
                self._rules[entity_type].sort(key=lambda r: r.priority, reverse=True)
        else:
            self._global_rules.append(rule)
            self._global_rules.sort(key=lambda r: r.priority, reverse=True)
    
    def get_rules_for_entity(self, entity_type: str) -> List[ValidationRule]:
        """Get all applicable rules for an entity type"""
        return self._rules.get(entity_type, []) + self._global_rules
    
    def enable_rule(self, rule_id: str):
        """Enable a rule"""
        if rule_id in self._rule_cache:
            self._rule_cache[rule_id].enabled = True
    
    def disable_rule(self, rule_id: str):
        """Disable a rule"""
        if rule_id in self._rule_cache:
            self._rule_cache[rule_id].enabled = False


class ValidationCache:
    """High-performance validation cache"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None, ttl_seconds: int = 300):
        self.redis_client = redis_client
        self.ttl_seconds = ttl_seconds
        self._local_cache = {}
        self._cache_stats = defaultdict(int)
    
    def _generate_cache_key(self, data: Any, validation_level: ValidationLevel, entity_type: str) -> str:
        """Generate deterministic cache key"""
        data_str = json.dumps(data, sort_keys=True, default=str)
        content = f"{entity_type}:{validation_level}:{data_str}"
        return f"validation:{hashlib.sha256(content.encode()).hexdigest()}"
    
    async def get(self, data: Any, validation_level: ValidationLevel, entity_type: str) -> Optional[ValidationResult]:
        """Get cached validation result"""
        key = self._generate_cache_key(data, validation_level, entity_type)
        
        # Check local cache first
        if key in self._local_cache:
            expiry, result = self._local_cache[key]
            if datetime.now(timezone.utc) < expiry:
                self._cache_stats['local_hits'] += 1
                return result
            else:
                del self._local_cache[key]
        
        # Check Redis if available
        if self.redis_client:
            try:
                cached = await self.redis_client.get(key)
                if cached:
                    self._cache_stats['redis_hits'] += 1
                    result = ValidationResult.parse_raw(cached)
                    # Update local cache
                    expiry = datetime.now(timezone.utc) + timedelta(seconds=self.ttl_seconds)
                    self._local_cache[key] = (expiry, result)
                    return result
            except Exception as e:
                logger.warning(f"Redis cache get error: {e}")
        
        self._cache_stats['misses'] += 1
        return None
    
    async def set(self, data: Any, validation_level: ValidationLevel, entity_type: str, result: ValidationResult):
        """Cache validation result"""
        key = self._generate_cache_key(data, validation_level, entity_type)
        
        # Update local cache
        expiry = datetime.now(timezone.utc) + timedelta(seconds=self.ttl_seconds)
        self._local_cache[key] = (expiry, result)
        
        # Update Redis if available
        if self.redis_client:
            try:
                await self.redis_client.setex(
                    key,
                    self.ttl_seconds,
                    result.json()
                )
            except Exception as e:
                logger.warning(f"Redis cache set error: {e}")
    
    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        return dict(self._cache_stats)


class EnterpriseValidationService:
    """
    Production-grade enterprise validation service
    Provides comprehensive validation for all OMS operations
    """
    
    def __init__(
        self,
        cache_manager: Optional[SmartCacheManager] = None,
        event_publisher: Optional[EventPublisher] = None,
        redis_client: Optional[redis.Redis] = None,
        default_level: ValidationLevel = ValidationLevel.STANDARD
    ):
        self.cache_manager = cache_manager
        self.event_publisher = event_publisher
        self.default_level = default_level
        
        # Initialize components
        self.sanitizer = InputSanitizer(SanitizationLevel.STRICT)
        self.rule_registry = ValidationRuleRegistry()
        self.validation_cache = ValidationCache(redis_client)
        
        # Metrics
        self.metrics = ValidationMetrics()
        self._validation_semaphore = asyncio.Semaphore(100)  # Limit concurrent validations
        
        # Entity type configurations
        self.entity_configs = self._initialize_entity_configs()
        
        # Load built-in rules
        self._load_builtin_rules()
        
        logger.info(f"Enterprise Validation Service initialized with level: {default_level}")
    
    def _initialize_entity_configs(self) -> Dict[str, Dict[str, Any]]:
        """Initialize validation configurations for each entity type"""
        return {
            "object_type": {
                "required_fields": ["name", "displayName"],
                "max_length": {"name": 255, "displayName": 500, "description": 2000},
                "naming_pattern": r"^[a-zA-Z][a-zA-Z0-9_]*$",
                "reserved_names": ["id", "type", "class", "meta", "system"],
                "custom_validators": []
            },
            "property": {
                "required_fields": ["name", "displayName", "dataType"],
                "max_length": {"name": 255, "displayName": 500},
                "valid_data_types": ["string", "integer", "float", "boolean", "date", "datetime", "json", "reference"],
                "naming_pattern": r"^[a-zA-Z][a-zA-Z0-9_]*$",
                "custom_validators": []
            },
            "link_type": {
                "required_fields": ["name", "displayName", "sourceObjectType", "targetObjectType"],
                "max_length": {"name": 255, "displayName": 500},
                "naming_pattern": r"^[a-zA-Z][a-zA-Z0-9_]*$",
                "custom_validators": []
            },
            "action_type": {
                "required_fields": ["name", "displayName", "targetTypes", "operations"],
                "max_length": {"name": 255, "displayName": 500},
                "valid_operations": ["create", "read", "update", "delete", "execute"],
                "custom_validators": []
            },
            "interface": {
                "required_fields": ["name", "displayName", "properties"],
                "max_length": {"name": 255, "displayName": 500},
                "naming_pattern": r"^[A-Z][a-zA-Z0-9]*$",  # PascalCase for interfaces
                "custom_validators": []
            },
            "semantic_type": {
                "required_fields": ["name", "displayName", "baseType"],
                "max_length": {"name": 255, "displayName": 500},
                "valid_base_types": ["string", "number", "date", "boolean"],
                "custom_validators": []
            },
            "struct_type": {
                "required_fields": ["name", "displayName", "fields"],
                "max_length": {"name": 255, "displayName": 500},
                "naming_pattern": r"^[A-Z][a-zA-Z0-9]*$",  # PascalCase for structs
                "custom_validators": []
            }
        }
    
    def _load_builtin_rules(self):
        """Load built-in validation rules"""
        # Required fields rule
        self.rule_registry.register_rule(RequiredFieldsRule())
        
        # Field length rule
        self.rule_registry.register_rule(FieldLengthRule(self.entity_configs))
        
        # Naming convention rule
        self.rule_registry.register_rule(NamingConventionRule(self.entity_configs))
        
        # Data type validation rule
        self.rule_registry.register_rule(DataTypeValidationRule(self.entity_configs))
        
        # Security validation rule
        self.rule_registry.register_rule(SecurityValidationRule())
        
        # Reference integrity rule
        self.rule_registry.register_rule(ReferenceIntegrityRule())
        
        # Business logic rules
        self.rule_registry.register_rule(ReservedNamesRule(self.entity_configs))
        self.rule_registry.register_rule(DuplicateDetectionRule())
    
    async def validate(
        self,
        data: Dict[str, Any],
        entity_type: str,
        operation: str = "create",
        level: Optional[ValidationLevel] = None,
        context: Optional[Dict[str, Any]] = None,
        use_cache: bool = True
    ) -> ValidationResult:
        """
        Main validation entry point
        
        Args:
            data: Data to validate
            entity_type: Type of entity (object_type, property, etc.)
            operation: Operation type (create, update, delete)
            level: Validation level (defaults to service default)
            context: Additional validation context
            use_cache: Whether to use cache
        
        Returns:
            Comprehensive validation result
        """
        request_id = context.get("request_id", str(time.time()))
        validation_level = level or self.default_level
        start_time = time.time()
        
        # Check cache first
        if use_cache and operation == "create":
            cached_result = await self.validation_cache.get(data, validation_level, entity_type)
            if cached_result:
                cached_result.cache_used = True
                self.metrics.cache_hits += 1
                return cached_result
        
        async with self._validation_semaphore:
            try:
                # Initialize result
                result = ValidationResult(
                    request_id=request_id,
                    is_valid=True,
                    validation_level=validation_level,
                    errors=[],
                    warnings=[],
                    security_score=100
                )
                
                # Step 1: Input sanitization
                sanitized_data = await self._sanitize_input(data, entity_type, result)
                result.sanitized_data = sanitized_data
                
                # Step 2: Schema validation
                if validation_level in [ValidationLevel.STANDARD, ValidationLevel.STRICT, ValidationLevel.PARANOID]:
                    await self._validate_schema(sanitized_data, entity_type, operation, result, context)
                
                # Step 3: Business rules validation
                if validation_level in [ValidationLevel.STRICT, ValidationLevel.PARANOID]:
                    await self._validate_business_rules(sanitized_data, entity_type, operation, result, context)
                
                # Step 4: Security validation
                if validation_level == ValidationLevel.PARANOID:
                    await self._validate_security(sanitized_data, entity_type, result, context)
                
                # Calculate final metrics
                result.performance_impact_ms = (time.time() - start_time) * 1000
                result.is_valid = len([e for e in result.errors if e.severity in ["critical", "high"]]) == 0
                
                # Update metrics
                self._update_metrics(result, entity_type)
                
                # Cache successful validations
                if use_cache and result.is_valid and operation == "create":
                    await self.validation_cache.set(data, validation_level, entity_type, result)
                
                # Publish validation event
                await self._publish_validation_event(result, entity_type, operation)
                
                return result
                
            except Exception as e:
                logger.error(f"Validation error for {entity_type}: {e}")
                return ValidationResult(
                    request_id=request_id,
                    is_valid=False,
                    validation_level=validation_level,
                    errors=[ValidationError(
                        field="system",
                        message=f"Internal validation error: {str(e)}",
                        category=ValidationCategory.SYNTAX,
                        severity="critical",
                        code="INTERNAL_ERROR"
                    )],
                    performance_impact_ms=(time.time() - start_time) * 1000
                )
    
    async def _sanitize_input(
        self,
        data: Dict[str, Any],
        entity_type: str,
        result: ValidationResult
    ) -> Dict[str, Any]:
        """Sanitize all input data"""
        sanitized = {}
        
        for field, value in data.items():
            if isinstance(value, str):
                sanitization_result = self.sanitizer.sanitize(
                    value,
                    SanitizationLevel.STRICT,
                    max_length=self.entity_configs.get(entity_type, {}).get("max_length", {}).get(field, 10000)
                )
                
                sanitized[field] = sanitization_result.sanitized_value
                
                # Add warnings for security threats
                if sanitization_result.detected_threats:
                    for threat in sanitization_result.detected_threats:
                        result.warnings.append(ValidationError(
                            field=field,
                            message=f"Security threat detected and sanitized: {threat}",
                            category=ValidationCategory.SECURITY,
                            severity="medium",
                            code=f"SECURITY_THREAT_{threat.upper()}"
                        ))
                    
                    # Reduce security score
                    result.security_score -= len(sanitization_result.detected_threats) * 5
                
            elif isinstance(value, dict):
                sanitized[field] = await self._sanitize_input(value, entity_type, result)
            elif isinstance(value, list):
                sanitized[field] = [
                    await self._sanitize_input(item, entity_type, result) if isinstance(item, dict)
                    else self.sanitizer.sanitize(item, SanitizationLevel.STRICT).sanitized_value if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                sanitized[field] = value
        
        return sanitized
    
    async def _validate_schema(
        self,
        data: Dict[str, Any],
        entity_type: str,
        operation: str,
        result: ValidationResult,
        context: Optional[Dict[str, Any]]
    ):
        """Validate against schema rules"""
        rules = self.rule_registry.get_rules_for_entity(entity_type)
        
        for rule in rules:
            if not rule.enabled:
                continue
            
            if rule.category != ValidationCategory.BUSINESS:
                try:
                    errors = await rule.validate(data, {
                        "entity_type": entity_type,
                        "operation": operation,
                        "context": context or {}
                    })
                    result.errors.extend(errors)
                except Exception as e:
                    logger.error(f"Rule {rule.rule_id} failed: {e}")
                    result.warnings.append(ValidationError(
                        field="system",
                        message=f"Validation rule {rule.rule_id} failed",
                        category=ValidationCategory.SYNTAX,
                        severity="low",
                        code="RULE_EXECUTION_ERROR"
                    ))
    
    async def _validate_business_rules(
        self,
        data: Dict[str, Any],
        entity_type: str,
        operation: str,
        result: ValidationResult,
        context: Optional[Dict[str, Any]]
    ):
        """Validate business-specific rules"""
        rules = [r for r in self.rule_registry.get_rules_for_entity(entity_type) 
                if r.category == ValidationCategory.BUSINESS and r.enabled]
        
        for rule in rules:
            try:
                errors = await rule.validate(data, {
                    "entity_type": entity_type,
                    "operation": operation,
                    "context": context or {}
                })
                result.errors.extend(errors)
            except Exception as e:
                logger.error(f"Business rule {rule.rule_id} failed: {e}")
    
    async def _validate_security(
        self,
        data: Dict[str, Any],
        entity_type: str,
        result: ValidationResult,
        context: Optional[Dict[str, Any]]
    ):
        """Deep security validation"""
        # Check for potential security issues
        security_patterns = {
            "script_injection": r'<script.*?>.*?</script>',
            "sql_injection": r'(\b(union|select|insert|update|delete|drop)\b|--)',
            "path_traversal": r'\.\./',
            "command_injection": r'[;&|`]',
        }
        
        def check_value(value: Any, path: str):
            if isinstance(value, str):
                for pattern_name, pattern in security_patterns.items():
                    import re
                    if re.search(pattern, value, re.IGNORECASE):
                        result.errors.append(ValidationError(
                            field=path,
                            message=f"Potential {pattern_name.replace('_', ' ')} detected",
                            category=ValidationCategory.SECURITY,
                            severity="high",
                            code=f"SECURITY_{pattern_name.upper()}"
                        ))
                        result.security_score -= 20
            elif isinstance(value, dict):
                for k, v in value.items():
                    check_value(v, f"{path}.{k}")
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    check_value(item, f"{path}[{i}]")
        
        for field, value in data.items():
            check_value(value, field)
    
    def _update_metrics(self, result: ValidationResult, entity_type: str):
        """Update validation metrics"""
        self.metrics.total_validations += 1
        
        if result.is_valid:
            self.metrics.successful_validations += 1
        else:
            self.metrics.failed_validations += 1
        
        if result.security_score < 100:
            self.metrics.security_threats_detected += 1
        
        # Update average time
        current_avg = self.metrics.average_validation_time_ms
        new_avg = (current_avg * (self.metrics.total_validations - 1) + result.performance_impact_ms) / self.metrics.total_validations
        self.metrics.average_validation_time_ms = new_avg
        
        # Update by type
        self.metrics.validation_by_type[entity_type] = self.metrics.validation_by_type.get(entity_type, 0) + 1
        
        # Update errors by category
        for error in result.errors:
            category_key = error.category.value
            self.metrics.errors_by_category[category_key] = self.metrics.errors_by_category.get(category_key, 0) + 1
    
    async def _publish_validation_event(
        self,
        result: ValidationResult,
        entity_type: str,
        operation: str
    ):
        """Publish validation event for monitoring"""
        if self.event_publisher:
            try:
                await self.event_publisher.publish(
                    event_type="validation.completed",
                    data={
                        "request_id": result.request_id,
                        "entity_type": entity_type,
                        "operation": operation,
                        "is_valid": result.is_valid,
                        "validation_level": result.validation_level.value,
                        "error_count": len(result.errors),
                        "warning_count": len(result.warnings),
                        "security_score": result.security_score,
                        "performance_ms": result.performance_impact_ms,
                        "cache_used": result.cache_used
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to publish validation event: {e}")
    
    def register_custom_rule(self, rule: ValidationRule, entity_types: Optional[List[str]] = None):
        """Register a custom validation rule"""
        self.rule_registry.register_rule(rule, entity_types)
        logger.info(f"Registered custom rule: {rule.rule_id}")
    
    def get_metrics(self) -> ValidationMetrics:
        """Get current validation metrics"""
        self.metrics.cache_hits = self.validation_cache.get_stats().get('local_hits', 0) + \
                                 self.validation_cache.get_stats().get('redis_hits', 0)
        self.metrics.cache_misses = self.validation_cache.get_stats().get('misses', 0)
        return self.metrics
    
    async def validate_batch(
        self,
        items: List[Dict[str, Any]],
        entity_type: str,
        operation: str = "create",
        level: Optional[ValidationLevel] = None,
        max_concurrency: int = 10
    ) -> List[ValidationResult]:
        """Validate multiple items concurrently"""
        semaphore = asyncio.Semaphore(max_concurrency)
        
        async def validate_item(item: Dict[str, Any]) -> ValidationResult:
            async with semaphore:
                return await self.validate(item, entity_type, operation, level)
        
        tasks = [validate_item(item) for item in items]
        return await asyncio.gather(*tasks)


# Built-in validation rules

class RequiredFieldsRule(ValidationRule):
    """Validates required fields are present"""
    
    def __init__(self):
        super().__init__(
            rule_id="required_fields",
            description="Ensures all required fields are present",
            category=ValidationCategory.SYNTAX
        )
        self.priority = 100
    
    async def validate(self, data: Any, context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        entity_type = context.get("entity_type")
        operation = context.get("operation")
        
        if operation == "create":
            # Get required fields from entity config
            from core.validation.enterprise_service import EnterpriseValidationService
            configs = EnterpriseValidationService._initialize_entity_configs(None)
            required_fields = configs.get(entity_type, {}).get("required_fields", [])
            
            for field in required_fields:
                if field not in data or data[field] is None or data[field] == "":
                    errors.append(ValidationError(
                        field=field,
                        message=f"Required field '{field}' is missing or empty",
                        category=self.category,
                        severity="high",
                        code="REQUIRED_FIELD_MISSING"
                    ))
        
        return errors


class FieldLengthRule(ValidationRule):
    """Validates field lengths"""
    
    def __init__(self, entity_configs: Dict[str, Dict[str, Any]]):
        super().__init__(
            rule_id="field_length",
            description="Validates field lengths against constraints",
            category=ValidationCategory.SYNTAX
        )
        self.entity_configs = entity_configs
        self.priority = 90
    
    async def validate(self, data: Any, context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        entity_type = context.get("entity_type")
        max_lengths = self.entity_configs.get(entity_type, {}).get("max_length", {})
        
        for field, max_length in max_lengths.items():
            if field in data and isinstance(data[field], str):
                if len(data[field]) > max_length:
                    errors.append(ValidationError(
                        field=field,
                        message=f"Field '{field}' exceeds maximum length of {max_length} characters",
                        category=self.category,
                        severity="medium",
                        code="FIELD_TOO_LONG",
                        suggested_fix=f"Truncate to {max_length} characters"
                    ))
        
        return errors


class NamingConventionRule(ValidationRule):
    """Validates naming conventions"""
    
    def __init__(self, entity_configs: Dict[str, Dict[str, Any]]):
        super().__init__(
            rule_id="naming_convention",
            description="Validates field naming conventions",
            category=ValidationCategory.SYNTAX
        )
        self.entity_configs = entity_configs
        self.priority = 80
    
    async def validate(self, data: Any, context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        entity_type = context.get("entity_type")
        naming_pattern = self.entity_configs.get(entity_type, {}).get("naming_pattern")
        
        if naming_pattern and "name" in data:
            import re
            if not re.match(naming_pattern, data["name"]):
                errors.append(ValidationError(
                    field="name",
                    message=f"Name '{data['name']}' does not match required pattern: {naming_pattern}",
                    category=self.category,
                    severity="medium",
                    code="INVALID_NAMING_CONVENTION",
                    suggested_fix="Use only letters, numbers, and underscores. Start with a letter."
                ))
        
        return errors


class DataTypeValidationRule(ValidationRule):
    """Validates data types"""
    
    def __init__(self, entity_configs: Dict[str, Dict[str, Any]]):
        super().__init__(
            rule_id="data_type_validation",
            description="Validates data types are correct",
            category=ValidationCategory.SEMANTIC
        )
        self.entity_configs = entity_configs
        self.priority = 85
    
    async def validate(self, data: Any, context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        entity_type = context.get("entity_type")
        
        # Check valid data types for properties
        if entity_type == "property" and "dataType" in data:
            valid_types = self.entity_configs.get("property", {}).get("valid_data_types", [])
            if data["dataType"] not in valid_types:
                errors.append(ValidationError(
                    field="dataType",
                    message=f"Invalid data type '{data['dataType']}'. Must be one of: {', '.join(valid_types)}",
                    category=self.category,
                    severity="high",
                    code="INVALID_DATA_TYPE"
                ))
        
        # Check valid operations for actions
        if entity_type == "action_type" and "operations" in data:
            valid_operations = self.entity_configs.get("action_type", {}).get("valid_operations", [])
            for op in data.get("operations", []):
                if op not in valid_operations:
                    errors.append(ValidationError(
                        field="operations",
                        message=f"Invalid operation '{op}'. Must be one of: {', '.join(valid_operations)}",
                        category=self.category,
                        severity="high",
                        code="INVALID_OPERATION"
                    ))
        
        return errors


class SecurityValidationRule(ValidationRule):
    """Security-focused validation"""
    
    def __init__(self):
        super().__init__(
            rule_id="security_validation",
            description="Validates against common security threats",
            category=ValidationCategory.SECURITY
        )
        self.priority = 95
    
    async def validate(self, data: Any, context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        
        # Check for potential XSS in display names
        if "displayName" in data:
            if "<" in data["displayName"] or ">" in data["displayName"]:
                errors.append(ValidationError(
                    field="displayName",
                    message="Display name contains potentially unsafe HTML characters",
                    category=self.category,
                    severity="medium",
                    code="POTENTIAL_XSS"
                ))
        
        # Check for SQL injection patterns in any string field
        import re
        sql_pattern = re.compile(r'(\b(union|select|insert|update|delete|drop)\b.*\b(from|where|table)\b)', re.IGNORECASE)
        
        def check_sql_injection(value: Any, field_path: str):
            if isinstance(value, str) and sql_pattern.search(value):
                errors.append(ValidationError(
                    field=field_path,
                    message="Potential SQL injection pattern detected",
                    category=self.category,
                    severity="high",
                    code="SQL_INJECTION_RISK"
                ))
            elif isinstance(value, dict):
                for k, v in value.items():
                    check_sql_injection(v, f"{field_path}.{k}")
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    check_sql_injection(item, f"{field_path}[{i}]")
        
        for field, value in data.items():
            check_sql_injection(value, field)
        
        return errors


class ReferenceIntegrityRule(ValidationRule):
    """Validates references to other entities"""
    
    def __init__(self):
        super().__init__(
            rule_id="reference_integrity",
            description="Validates references to other entities exist",
            category=ValidationCategory.SEMANTIC
        )
        self.priority = 70
    
    async def validate(self, data: Any, context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        entity_type = context.get("entity_type")
        
        # Check object type references in properties
        if entity_type == "property" and "objectType" in data:
            # This would normally check if the object type exists
            # For now, just validate format
            if not data["objectType"] or not isinstance(data["objectType"], str):
                errors.append(ValidationError(
                    field="objectType",
                    message="Invalid object type reference",
                    category=self.category,
                    severity="high",
                    code="INVALID_REFERENCE"
                ))
        
        # Check source/target references in link types
        if entity_type == "link_type":
            for field in ["sourceObjectType", "targetObjectType"]:
                if field in data and (not data[field] or not isinstance(data[field], str)):
                    errors.append(ValidationError(
                        field=field,
                        message=f"Invalid {field} reference",
                        category=self.category,
                        severity="high",
                        code="INVALID_REFERENCE"
                    ))
        
        return errors


class ReservedNamesRule(ValidationRule):
    """Checks for reserved names"""
    
    def __init__(self, entity_configs: Dict[str, Dict[str, Any]]):
        super().__init__(
            rule_id="reserved_names",
            description="Prevents use of reserved names",
            category=ValidationCategory.BUSINESS
        )
        self.entity_configs = entity_configs
        self.priority = 75
    
    async def validate(self, data: Any, context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        entity_type = context.get("entity_type")
        reserved_names = self.entity_configs.get(entity_type, {}).get("reserved_names", [])
        
        if "name" in data and data["name"].lower() in [r.lower() for r in reserved_names]:
            errors.append(ValidationError(
                field="name",
                message=f"'{data['name']}' is a reserved name and cannot be used",
                category=self.category,
                severity="high",
                code="RESERVED_NAME",
                suggested_fix=f"Choose a different name. Reserved names: {', '.join(reserved_names)}"
            ))
        
        return errors


class DuplicateDetectionRule(ValidationRule):
    """Detects potential duplicates"""
    
    def __init__(self):
        super().__init__(
            rule_id="duplicate_detection",
            description="Detects potential duplicate entries",
            category=ValidationCategory.BUSINESS
        )
        self.priority = 60
    
    async def validate(self, data: Any, context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        
        # This would normally check against existing data
        # For now, just check for obvious duplicates in arrays
        if "properties" in data and isinstance(data["properties"], list):
            seen_names = set()
            for i, prop in enumerate(data["properties"]):
                if isinstance(prop, dict) and "name" in prop:
                    if prop["name"] in seen_names:
                        errors.append(ValidationError(
                            field=f"properties[{i}].name",
                            message=f"Duplicate property name '{prop['name']}'",
                            category=self.category,
                            severity="medium",
                            code="DUPLICATE_PROPERTY"
                        ))
                    seen_names.add(prop["name"])
        
        return errors


# Singleton instance getter
_validation_service_instance = None

def get_enterprise_validation_service(
    cache_manager: Optional[SmartCacheManager] = None,
    event_publisher: Optional[EventPublisher] = None,
    redis_client: Optional[redis.Redis] = None,
    default_level: ValidationLevel = ValidationLevel.STANDARD
) -> EnterpriseValidationService:
    """Get or create the enterprise validation service singleton"""
    global _validation_service_instance
    if _validation_service_instance is None:
        _validation_service_instance = EnterpriseValidationService(
            cache_manager=cache_manager,
            event_publisher=event_publisher,
            redis_client=redis_client,
            default_level=default_level
        )
    return _validation_service_instance