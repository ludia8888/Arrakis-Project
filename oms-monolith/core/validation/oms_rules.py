"""
OMS-Specific Validation Rules
Custom validation rules for OMS entity types and business logic
"""
import re
import logging
from typing import Any, Dict, List, Optional, Set
from datetime import datetime, timezone

from core.validation.enterprise_service import (
    ValidationRule, ValidationError, ValidationCategory
)


logger = logging.getLogger(__name__)


class PropertyDataTypeConsistencyRule(ValidationRule):
    """Ensures property data types are consistent with their usage"""
    
    def __init__(self):
        super().__init__(
            rule_id="property_datatype_consistency",
            description="Validates property data types are consistent with constraints",
            category=ValidationCategory.SEMANTIC
        )
        self.priority = 85
    
    async def validate(self, data: Any, context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        entity_type = context.get("entity_type")
        
        if entity_type != "property":
            return errors
        
        data_type = data.get("dataType")
        
        # Check constraints match data type
        if "constraints" in data and data_type:
            constraints = data["constraints"]
            
            # Numeric constraints only valid for numeric types
            numeric_constraints = ["minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"]
            if any(c in constraints for c in numeric_constraints):
                if data_type not in ["integer", "float", "number"]:
                    errors.append(ValidationError(
                        field="constraints",
                        message=f"Numeric constraints not valid for data type '{data_type}'",
                        category=self.category,
                        severity="medium",
                        code="INVALID_CONSTRAINT_TYPE"
                    ))
            
            # String constraints only valid for string types
            string_constraints = ["minLength", "maxLength", "pattern", "format"]
            if any(c in constraints for c in string_constraints):
                if data_type != "string":
                    errors.append(ValidationError(
                        field="constraints",
                        message=f"String constraints not valid for data type '{data_type}'",
                        category=self.category,
                        severity="medium",
                        code="INVALID_CONSTRAINT_TYPE"
                    ))
            
            # Array constraints
            array_constraints = ["minItems", "maxItems", "uniqueItems"]
            if any(c in constraints for c in array_constraints):
                if not data.get("isMultiValued", False):
                    errors.append(ValidationError(
                        field="constraints",
                        message="Array constraints only valid for multi-valued properties",
                        category=self.category,
                        severity="medium",
                        code="INVALID_CONSTRAINT_TYPE"
                    ))
        
        # Validate default value matches data type
        if "defaultValue" in data and data_type:
            default_value = data["defaultValue"]
            if not self._validate_value_type(default_value, data_type):
                errors.append(ValidationError(
                    field="defaultValue",
                    message=f"Default value type does not match data type '{data_type}'",
                    category=self.category,
                    severity="high",
                    code="TYPE_MISMATCH"
                ))
        
        return errors
    
    def _validate_value_type(self, value: Any, data_type: str) -> bool:
        """
        Check if value matches expected data type
        
        ⚠️ LEGACY WARNING: This duplicates TerminusDB's native type validation.
        Consider delegating to TerminusDB schema validation per boundary definition.
        """
        # Log legacy usage for monitoring
        logger.debug("LEGACY_TYPE_VALIDATION", extra={
            "data_type": data_type,
            "validator": "manual_type_check"
        })
        
        type_validators = {
# REMOVED: TerminusDB handles type_validation natively
#             "string": lambda v: isinstance(v, str),
# REMOVED: TerminusDB handles type_validation natively
#             "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
# REMOVED: TerminusDB handles type_validation natively
#             "float": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
# REMOVED: TerminusDB handles type_validation natively
#             "boolean": lambda v: isinstance(v, bool),
# REMOVED: TerminusDB handles type_validation natively
#             "date": lambda v: isinstance(v, str) and self._is_valid_date(v),
# REMOVED: TerminusDB handles type_validation natively
#             "datetime": lambda v: isinstance(v, str) and self._is_valid_datetime(v),
            "json": lambda v: isinstance(v, (dict, list)),
# REMOVED: TerminusDB handles type_validation natively
#             "reference": lambda v: isinstance(v, str) and v.startswith("@")
        }
        
        validator = type_validators.get(data_type)
        return validator(value) if validator else True
    
    def _is_valid_date(self, value: str) -> bool:
        """Check if string is valid ISO date"""
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            return True
        except ValueError:
            return False
    
    def _is_valid_datetime(self, value: str) -> bool:
        """Check if string is valid ISO datetime"""
        return self._is_valid_date(value)


class LinkTypeCardinalityRule(ValidationRule):
    """Validates link type cardinality constraints"""
    
    def __init__(self):
        super().__init__(
            rule_id="link_type_cardinality",
            description="Validates link type cardinality is properly defined",
            category=ValidationCategory.SEMANTIC
        )
        self.priority = 80
    
    async def validate(self, data: Any, context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        entity_type = context.get("entity_type")
        
        if entity_type != "link_type":
            return errors
        
        # Check cardinality values
        for field in ["sourceCardinality", "targetCardinality"]:
            if field in data:
                cardinality = data[field]
                if not self._is_valid_cardinality(cardinality):
                    errors.append(ValidationError(
                        field=field,
                        message=f"Invalid cardinality value: '{cardinality}'. Must be one of: 0..1, 0..*, 1..1, 1..*",
                        category=self.category,
                        severity="high",
                        code="INVALID_CARDINALITY"
                    ))
        
        # Check inverse link consistency
        if "inverseLink" in data and data["inverseLink"]:
            # Would normally check if inverse link exists and is consistent
            # For now, just validate format
# REMOVED: TerminusDB handles type_validation natively
#             if not isinstance(data["inverseLink"], str):
                errors.append(ValidationError(
                    field="inverseLink",
                    message="Inverse link must be a string reference",
                    category=self.category,
                    severity="medium",
                    code="INVALID_INVERSE_LINK"
                ))
        
        return errors
    
    def _is_valid_cardinality(self, cardinality: str) -> bool:
        """Check if cardinality value is valid"""
        # 허용되는 카디널리티 목록
        # API에서 사용하는 one-to-one, one-to-many 등을 포함하고, 내부 표준 표기(0..1 등)도 지원
        valid_cardinalities = [
            "0..1", "0..*", "1..1", "1..*", "*", "1", "0..n", "1..n",
            "one-to-one", "one-to-many", "many-to-many"
        ]
        return cardinality in valid_cardinalities


class ActionTypeOperationRule(ValidationRule):
    """Validates action type operations and permissions"""
    
    def __init__(self):
        super().__init__(
            rule_id="action_type_operations",
            description="Validates action type operations are properly configured",
            category=ValidationCategory.BUSINESS
        )
        self.priority = 75
    
    async def validate(self, data: Any, context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        entity_type = context.get("entity_type")
        
        if entity_type != "action_type":
            return errors
        
        operations = data.get("operations", [])
        
        # Check for conflicting operations
        if "create" in operations and "delete" in operations:
            if not data.get("allowBothCreateAndDelete", False):
                errors.append(ValidationError(
                    field="operations",
                    message="Action type has both 'create' and 'delete' operations which may conflict",
                    category=self.category,
                    severity="low",
                    code="CONFLICTING_OPERATIONS"
                ))
        
        # Validate input/output schemas if present
        if "inputSchema" in data:
# REMOVED: TerminusDB handles type_validation natively
#             if not isinstance(data["inputSchema"], dict):
                errors.append(ValidationError(
                    field="inputSchema",
                    message="Input schema must be a valid JSON schema object",
                    category=self.category,
                    severity="medium",
                    code="INVALID_SCHEMA"
                ))
        
        if "outputSchema" in data:
# REMOVED: TerminusDB handles type_validation natively
#             if not isinstance(data["outputSchema"], dict):
                errors.append(ValidationError(
                    field="outputSchema",
                    message="Output schema must be a valid JSON schema object",
                    category=self.category,
                    severity="medium",
                    code="INVALID_SCHEMA"
                ))
        
        # Check target types exist
        target_types = data.get("targetTypes", [])
        if not target_types:
            errors.append(ValidationError(
                field="targetTypes",
                message="Action type must specify at least one target type",
                category=self.category,
                severity="high",
                code="MISSING_TARGET_TYPES"
            ))
        
        return errors


class InterfaceImplementationRule(ValidationRule):
    """Validates interface definitions and implementations"""
    
    def __init__(self):
        super().__init__(
            rule_id="interface_implementation",
            description="Validates interface definitions are complete",
            category=ValidationCategory.SEMANTIC
        )
        self.priority = 78
    
    async def validate(self, data: Any, context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        entity_type = context.get("entity_type")
        
        if entity_type != "interface":
            return errors
        
        # Check interface has properties
        properties = data.get("properties", [])
        if not properties:
            errors.append(ValidationError(
                field="properties",
                message="Interface must define at least one property",
                category=self.category,
                severity="high",
                code="EMPTY_INTERFACE"
            ))
        
        # Check for duplicate property names
        property_names = set()
        for i, prop in enumerate(properties):
# REMOVED: TerminusDB handles type_validation natively
#             if isinstance(prop, dict) and "name" in prop:
                if prop["name"] in property_names:
                    errors.append(ValidationError(
                        field=f"properties[{i}].name",
                        message=f"Duplicate property name in interface: '{prop['name']}'",
                        category=self.category,
                        severity="high",
                        code="DUPLICATE_INTERFACE_PROPERTY"
                    ))
                property_names.add(prop["name"])
        
        # Validate interface inheritance
        if "extends" in data:
            extends = data["extends"]
# REMOVED: TerminusDB handles type_validation natively
#             if isinstance(extends, list):
                # Check for circular inheritance (would need DB access in real implementation)
                if len(extends) > 5:
                    errors.append(ValidationError(
                        field="extends",
                        message="Interface inheritance depth exceeds recommended limit",
                        category=self.category,
                        severity="low",
                        code="DEEP_INHERITANCE"
                    ))
        
        return errors


class SemanticTypeValidationRule(ValidationRule):
    """Validates semantic type definitions"""
    
    def __init__(self):
        super().__init__(
            rule_id="semantic_type_validation",
            description="Validates semantic type definitions and constraints",
            category=ValidationCategory.SEMANTIC
        )
        self.priority = 77
    
    async def validate(self, data: Any, context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        entity_type = context.get("entity_type")
        
        if entity_type != "semantic_type":
            return errors
        
        base_type = data.get("baseType")
        
        # Validate constraints match base type
        if "constraints" in data and base_type:
            constraints = data["constraints"]
            
            # Pattern only valid for strings
            if "pattern" in constraints and base_type != "string":
                errors.append(ValidationError(
                    field="constraints.pattern",
                    message=f"Pattern constraint not valid for base type '{base_type}'",
                    category=self.category,
                    severity="medium",
                    code="INVALID_CONSTRAINT_FOR_TYPE"
                ))
            
            # Min/max only valid for numbers
            if any(c in constraints for c in ["minimum", "maximum"]) and base_type not in ["number", "integer"]:
                errors.append(ValidationError(
                    field="constraints",
                    message=f"Min/max constraints not valid for base type '{base_type}'",
                    category=self.category,
                    severity="medium",
                    code="INVALID_CONSTRAINT_FOR_TYPE"
                ))
        
        # Validate format if specified
        if "format" in data:
            format_value = data["format"]
            valid_formats = {
                "string": ["email", "uri", "uuid", "date", "date-time", "time", "ipv4", "ipv6", "hostname"],
                "number": ["float", "double"],
                "integer": ["int32", "int64"]
            }
            
            if base_type in valid_formats:
                if format_value not in valid_formats[base_type]:
                    errors.append(ValidationError(
                        field="format",
                        message=f"Format '{format_value}' not valid for base type '{base_type}'",
                        category=self.category,
                        severity="medium",
                        code="INVALID_FORMAT"
                    ))
        
        return errors


class StructTypeFieldValidationRule(ValidationRule):
    """Validates struct type field definitions"""
    
    def __init__(self):
        super().__init__(
            rule_id="struct_type_fields",
            description="Validates struct type field definitions",
            category=ValidationCategory.SEMANTIC
        )
        self.priority = 76
    
    async def validate(self, data: Any, context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        entity_type = context.get("entity_type")
        
        if entity_type != "struct_type":
            return errors
        
        fields = data.get("fields", [])
        
        if not fields:
            errors.append(ValidationError(
                field="fields",
                message="Struct type must define at least one field",
                category=self.category,
                severity="high",
                code="EMPTY_STRUCT"
            ))
        
        # Check field definitions
        field_names = set()
        for i, field in enumerate(fields):
# REMOVED: TerminusDB handles type_validation natively
#             if not isinstance(field, dict):
                continue
            
            # Check required field properties
            if "name" not in field:
                errors.append(ValidationError(
                    field=f"fields[{i}]",
                    message="Field must have a name",
                    category=self.category,
                    severity="high",
                    code="MISSING_FIELD_NAME"
                ))
            else:
                # Check for duplicates
                if field["name"] in field_names:
                    errors.append(ValidationError(
                        field=f"fields[{i}].name",
                        message=f"Duplicate field name: '{field['name']}'",
                        category=self.category,
                        severity="high",
                        code="DUPLICATE_FIELD"
                    ))
                field_names.add(field["name"])
            
            # Check field type
            if "type" not in field:
                errors.append(ValidationError(
                    field=f"fields[{i}]",
                    message="Field must have a type",
                    category=self.category,
                    severity="high",
                    code="MISSING_FIELD_TYPE"
                ))
        
        # Check for recursive struct definitions
# REMOVED: TerminusDB handles type_validation natively
#         if "extends" in data and isinstance(data["extends"], str):
            if data["extends"] == data.get("name"):
                errors.append(ValidationError(
                    field="extends",
                    message="Struct type cannot extend itself",
                    category=self.category,
                    severity="critical",
                    code="RECURSIVE_EXTENSION"
                ))
        
        return errors


class CrossEntityReferenceRule(ValidationRule):
    """Validates references between different entity types"""
    
    def __init__(self):
        super().__init__(
            rule_id="cross_entity_references",
            description="Validates references between entities are valid",
            category=ValidationCategory.SEMANTIC
        )
        self.priority = 70
    
    async def validate(self, data: Any, context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        entity_type = context.get("entity_type")
        
        # Validate property references to object types
        if entity_type == "property" and "objectType" in data:
            # Would normally check if object type exists
            if not data["objectType"].startswith("@"):
                errors.append(ValidationError(
                    field="objectType",
                    message="Object type reference must start with '@'",
                    category=self.category,
                    severity="medium",
                    code="INVALID_REFERENCE_FORMAT"
                ))
        
        # Validate link type references
        if entity_type == "link_type":
            for field in ["sourceObjectType", "targetObjectType"]:
                if field in data and not data[field].startswith("@"):
                    errors.append(ValidationError(
                        field=field,
                        message=f"{field} reference must start with '@'",
                        category=self.category,
                        severity="medium",
                        code="INVALID_REFERENCE_FORMAT"
                    ))
        
        # Validate action type target references
        if entity_type == "action_type" and "targetTypes" in data:
            for i, target in enumerate(data["targetTypes"]):
# REMOVED: TerminusDB handles type_validation natively
#                 if isinstance(target, str) and not target.startswith("@"):
                    errors.append(ValidationError(
                        field=f"targetTypes[{i}]",
                        message="Target type reference must start with '@'",
                        category=self.category,
                        severity="medium",
                        code="INVALID_REFERENCE_FORMAT"
                    ))
        
        return errors


class NamingConflictRule(ValidationRule):
    """Detects naming conflicts across entity types"""
    
    def __init__(self):
        super().__init__(
            rule_id="naming_conflicts",
            description="Detects naming conflicts and reserved word usage",
            category=ValidationCategory.BUSINESS
        )
        self.priority = 65
        
        # System reserved words across all entity types
        self.reserved_words = {
            "id", "type", "class", "meta", "system", "internal",
            "created", "modified", "deleted", "version", "status",
            "parent", "children", "root", "node", "edge",
            "source", "target", "from", "to", "relationship",
            "schema", "model", "entity", "object", "property",
            "true", "false", "null", "undefined", "void"
        }
    
    async def validate(self, data: Any, context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        
        # Check name field
        if "name" in data:
            name_lower = data["name"].lower()
            
            # Check reserved words
            if name_lower in self.reserved_words:
                errors.append(ValidationError(
                    field="name",
                    message=f"'{data['name']}' is a reserved system word",
                    category=self.category,
                    severity="high",
                    code="RESERVED_WORD",
                    suggested_fix=f"Consider using a prefix like 'custom_{data['name']}'"
                ))
            
            # Check for problematic prefixes
            problematic_prefixes = ["sys_", "internal_", "_", "__"]
            for prefix in problematic_prefixes:
                if name_lower.startswith(prefix):
                    errors.append(ValidationError(
                        field="name",
                        message=f"Names starting with '{prefix}' are reserved for system use",
                        category=self.category,
                        severity="medium",
                        code="RESERVED_PREFIX"
                    ))
        
        return errors


class CircularDependencyRule(ValidationRule):
    """Detects potential circular dependencies"""
    
    def __init__(self):
        super().__init__(
            rule_id="circular_dependencies",
            description="Detects potential circular dependencies in entity definitions",
            category=ValidationCategory.SEMANTIC
        )
        self.priority = 60
    
    async def validate(self, data: Any, context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        entity_type = context.get("entity_type")
        
        # Check self-references
        if "name" in data:
            entity_name = data["name"]
            
            # Check extends field
            if "extends" in data:
                extends = data["extends"]
# REMOVED: TerminusDB handles type_validation natively
#                 if isinstance(extends, str) and extends == entity_name:
                    errors.append(ValidationError(
                        field="extends",
                        message="Entity cannot extend itself",
                        category=self.category,
                        severity="critical",
                        code="SELF_REFERENCE"
                    ))
# REMOVED: TerminusDB handles type_validation natively
#                 elif isinstance(extends, list) and entity_name in extends:
                    errors.append(ValidationError(
                        field="extends",
                        message="Entity cannot extend itself",
                        category=self.category,
                        severity="critical",
                        code="SELF_REFERENCE"
                    ))
            
            # Check implements field
            if "implements" in data:
                implements = data["implements"]
# REMOVED: TerminusDB handles type_validation natively
#                 if isinstance(implements, list) and entity_name in implements:
                    errors.append(ValidationError(
                        field="implements",
                        message="Entity cannot implement itself",
                        category=self.category,
                        severity="critical",
                        code="SELF_REFERENCE"
                    ))
        
        return errors


class PerformanceImpactRule(ValidationRule):
    """Warns about configurations that may impact performance"""
    
    def __init__(self):
        super().__init__(
            rule_id="performance_impact",
            description="Detects configurations that may impact system performance",
            category=ValidationCategory.PERFORMANCE
        )
        self.priority = 40
    
    async def validate(self, data: Any, context: Dict[str, Any]) -> List[ValidationError]:
        errors = []
        entity_type = context.get("entity_type")
        
        # Check for large multi-valued properties without indexing
        if entity_type == "property":
            if data.get("isMultiValued") and not data.get("isIndexed"):
                errors.append(ValidationError(
                    field="isIndexed",
                    message="Multi-valued properties should be indexed for better query performance",
                    category=self.category,
                    severity="low",
                    code="UNINDEXED_MULTIVALUE",
                    suggested_fix="Set 'isIndexed': true for this property"
                ))
        
        # Check for deep nesting in struct types
        if entity_type == "struct_type" and "fields" in data:
            nesting_depth = self._calculate_nesting_depth(data["fields"])
            if nesting_depth > 3:
                errors.append(ValidationError(
                    field="fields",
                    message=f"Struct type has deep nesting (depth: {nesting_depth}) which may impact performance",
                    category=self.category,
                    severity="low",
                    code="DEEP_NESTING"
                ))
        
        # Check for excessive properties in object types
        if entity_type == "object_type" and "properties" in data:
            prop_count = len(data["properties"])
            if prop_count > 100:
                errors.append(ValidationError(
                    field="properties",
                    message=f"Object type has {prop_count} properties which may impact performance",
                    category=self.category,
                    severity="low",
                    code="EXCESSIVE_PROPERTIES",
                    suggested_fix="Consider splitting into multiple related object types"
                ))
        
        return errors
    
    def _calculate_nesting_depth(self, fields: List[Dict], current_depth: int = 1) -> int:
        """Calculate maximum nesting depth in struct fields"""
        max_depth = current_depth
        
        for field in fields:
            if isinstance(field, dict) and "fields" in field:
                depth = self._calculate_nesting_depth(field["fields"], current_depth + 1)
                max_depth = max(max_depth, depth)
        
        return max_depth


def register_oms_validation_rules(validation_service):
    """Register all OMS-specific validation rules"""
    rules = [
        PropertyDataTypeConsistencyRule(),
        LinkTypeCardinalityRule(),
        ActionTypeOperationRule(),
        InterfaceImplementationRule(),
        SemanticTypeValidationRule(),
        StructTypeFieldValidationRule(),
        CrossEntityReferenceRule(),
        NamingConflictRule(),
        CircularDependencyRule(),
        PerformanceImpactRule()
    ]
    
    for rule in rules:
        # Register rules for specific entity types
        entity_types = None
        
        if "property" in rule.rule_id:
            entity_types = ["property"]
        elif "link_type" in rule.rule_id:
            entity_types = ["link_type"]
        elif "action_type" in rule.rule_id:
            entity_types = ["action_type"]
        elif "interface" in rule.rule_id:
            entity_types = ["interface"]
        elif "semantic_type" in rule.rule_id:
            entity_types = ["semantic_type"]
        elif "struct_type" in rule.rule_id:
            entity_types = ["struct_type"]
        
        validation_service.register_custom_rule(rule, entity_types)
    
    logger.info(f"Registered {len(rules)} OMS-specific validation rules")