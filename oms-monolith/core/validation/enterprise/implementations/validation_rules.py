"""
Concrete validation rule implementations
"""

import re
from typing import Dict, Any, List, Set, Optional
from datetime import datetime

from ..interfaces.contracts import ValidationRuleInterface
from ..interfaces.models import ValidationError, ValidationCategory


class BaseValidationRule(ValidationRuleInterface):
    """Base class for validation rules"""
    
    def __init__(self, rule_id: str, description: str, category: ValidationCategory):
        self.rule_id = rule_id
        self.description = description
        self.category = category
        self.enabled = True
    
    def get_rule_id(self) -> str:
        return self.rule_id
    
    def get_description(self) -> str:
        return self.description
    
    def get_category(self) -> ValidationCategory:
        return self.category
    
    def validate(self, data: Dict[str, Any], context: Dict[str, Any]) -> List[ValidationError]:
        """Default implementation - override in subclasses"""
        return []


class RequiredFieldsRule(BaseValidationRule):
    """Validate required fields are present"""
    
    def __init__(self, required_fields: Set[str]):
        super().__init__(
            rule_id="required_fields",
            description="Ensures all required fields are present",
            category=ValidationCategory.SYNTAX
        )
        self.required_fields = required_fields
    
    def validate(self, data: Dict[str, Any], context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        
        for field in self.required_fields:
            if field not in data or data[field] is None:
                errors.append(ValidationError(
                    field=field,
                    message=f"Required field '{field}' is missing",
                    category=self.category,
                    severity="high",
                    code="REQUIRED_FIELD_MISSING",
                    suggested_fix=f"Provide a value for '{field}'"
                ))
        
        return errors


class FieldLengthRule(BaseValidationRule):
    """Validate field length constraints"""
    
    def __init__(self, field_constraints: Dict[str, Dict[str, int]]):
        super().__init__(
            rule_id="field_length",
            description="Validates field length constraints",
            category=ValidationCategory.SYNTAX
        )
        self.field_constraints = field_constraints
    
    def validate(self, data: Dict[str, Any], context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        
        for field, constraints in self.field_constraints.items():
            if field in data and isinstance(data[field], str):
                value = data[field]
                min_length = constraints.get('min', 0)
                max_length = constraints.get('max', float('inf'))
                
                if len(value) < min_length:
                    errors.append(ValidationError(
                        field=field,
                        message=f"Field '{field}' is too short (minimum {min_length} characters)",
                        category=self.category,
                        severity="medium",
                        code="FIELD_TOO_SHORT",
                        context={"current_length": len(value), "min_length": min_length}
                    ))
                elif len(value) > max_length:
                    errors.append(ValidationError(
                        field=field,
                        message=f"Field '{field}' is too long (maximum {max_length} characters)",
                        category=self.category,
                        severity="medium",
                        code="FIELD_TOO_LONG",
                        context={"current_length": len(value), "max_length": max_length}
                    ))
        
        return errors


class NamingConventionRule(BaseValidationRule):
    """Validate naming conventions"""
    
    def __init__(self, naming_patterns: Dict[str, str]):
        super().__init__(
            rule_id="naming_convention",
            description="Validates naming conventions",
            category=ValidationCategory.BUSINESS
        )
        self.naming_patterns = {
            field: re.compile(pattern) 
            for field, pattern in naming_patterns.items()
        }
    
    def validate(self, data: Dict[str, Any], context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        
        for field, pattern in self.naming_patterns.items():
            if field in data and isinstance(data[field], str):
                value = data[field]
                if not pattern.match(value):
                    errors.append(ValidationError(
                        field=field,
                        message=f"Field '{field}' does not match naming convention",
                        category=self.category,
                        severity="medium",
                        code="INVALID_NAMING_CONVENTION",
                        context={"value": value, "pattern": pattern.pattern},
                        suggested_fix="Use snake_case, camelCase, or PascalCase as appropriate"
                    ))
        
        return errors


class DataTypeValidationRule(BaseValidationRule):
    """Validate data types and formats"""
    
    def __init__(self, type_constraints: Dict[str, type]):
        super().__init__(
            rule_id="data_type",
            description="Validates data types",
            category=ValidationCategory.SYNTAX
        )
        self.type_constraints = type_constraints
    
    def validate(self, data: Dict[str, Any], context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        
        for field, expected_type in self.type_constraints.items():
            if field in data and data[field] is not None:
                value = data[field]
                if not isinstance(value, expected_type):
                    errors.append(ValidationError(
                        field=field,
                        message=f"Field '{field}' has invalid type",
                        category=self.category,
                        severity="high",
                        code="INVALID_DATA_TYPE",
                        context={
                            "expected_type": expected_type.__name__,
                            "actual_type": type(value).__name__
                        },
                        suggested_fix=f"Ensure '{field}' is of type {expected_type.__name__}"
                    ))
        
        return errors


class SecurityValidationRule(BaseValidationRule):
    """Validate for security threats"""
    
    def __init__(self):
        super().__init__(
            rule_id="security",
            description="Validates for security threats",
            category=ValidationCategory.SECURITY
        )
        self.sql_injection_patterns = [
            re.compile(r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER)\b)", re.IGNORECASE),
            re.compile(r"(-{2}|/\*|\*/|;|\||&&|\|\|)", re.IGNORECASE)
        ]
        self.xss_patterns = [
            re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE),
            re.compile(r"javascript:", re.IGNORECASE),
            re.compile(r"on\w+\s*=", re.IGNORECASE)
        ]
    
    def validate(self, data: Dict[str, Any], context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        
        for field, value in data.items():
            if isinstance(value, str):
                # Check SQL injection
                for pattern in self.sql_injection_patterns:
                    if pattern.search(value):
                        errors.append(ValidationError(
                            field=field,
                            message=f"Potential SQL injection detected in '{field}'",
                            category=self.category,
                            severity="critical",
                            code="SQL_INJECTION_THREAT",
                            context={"suspicious_content": value[:100]},
                            suggested_fix="Remove or escape SQL keywords and special characters"
                        ))
                        break
                
                # Check XSS
                for pattern in self.xss_patterns:
                    if pattern.search(value):
                        errors.append(ValidationError(
                            field=field,
                            message=f"Potential XSS attack detected in '{field}'",
                            category=self.category,
                            severity="critical",
                            code="XSS_THREAT",
                            context={"suspicious_content": value[:100]},
                            suggested_fix="Remove or escape HTML/JavaScript content"
                        ))
                        break
        
        return errors


class ReferenceIntegrityRule(BaseValidationRule):
    """Validate reference integrity"""
    
    def __init__(self, reference_validator: Optional[callable] = None):
        super().__init__(
            rule_id="reference_integrity",
            description="Validates reference integrity",
            category=ValidationCategory.SEMANTIC
        )
        self.reference_validator = reference_validator
    
    def validate(self, data: Dict[str, Any], context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        
        # Check for references in specific fields
        reference_fields = ['parent_id', 'reference_id', 'related_to']
        
        for field in reference_fields:
            if field in data and data[field] is not None:
                ref_id = data[field]
                
                # If we have a validator function, use it
                if self.reference_validator:
                    if not self.reference_validator(ref_id):
                        errors.append(ValidationError(
                            field=field,
                            message=f"Invalid reference in '{field}'",
                            category=self.category,
                            severity="high",
                            code="INVALID_REFERENCE",
                            context={"reference_id": ref_id},
                            suggested_fix="Ensure the referenced entity exists"
                        ))
        
        return errors


class ReservedNamesRule(BaseValidationRule):
    """Validate against reserved names"""
    
    def __init__(self, reserved_names: Set[str]):
        super().__init__(
            rule_id="reserved_names",
            description="Validates against reserved names",
            category=ValidationCategory.BUSINESS
        )
        self.reserved_names = {name.lower() for name in reserved_names}
    
    def validate(self, data: Dict[str, Any], context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        
        name_fields = ['name', 'identifier', 'key', 'type']
        
        for field in name_fields:
            if field in data and isinstance(data[field], str):
                value = data[field].lower()
                if value in self.reserved_names:
                    errors.append(ValidationError(
                        field=field,
                        message=f"'{data[field]}' is a reserved name",
                        category=self.category,
                        severity="high",
                        code="RESERVED_NAME",
                        context={"reserved_name": data[field]},
                        suggested_fix="Choose a different name that is not reserved"
                    ))
        
        return errors


class DuplicateDetectionRule(BaseValidationRule):
    """Detect duplicate entries"""
    
    def __init__(self, duplicate_checker: Optional[callable] = None):
        super().__init__(
            rule_id="duplicate_detection",
            description="Detects duplicate entries",
            category=ValidationCategory.SEMANTIC
        )
        self.duplicate_checker = duplicate_checker
    
    def validate(self, data: Dict[str, Any], context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        
        # Check for duplicates if we have a checker function
        if self.duplicate_checker and 'name' in data:
            existing = self.duplicate_checker(data['name'])
            if existing:
                errors.append(ValidationError(
                    field='name',
                    message=f"Duplicate entry detected: '{data['name']}'",
                    category=self.category,
                    severity="high",
                    code="DUPLICATE_ENTRY",
                    context={"duplicate_name": data['name'], "existing_id": existing},
                    suggested_fix="Use a unique name or update the existing entry"
                ))
        
        return errors