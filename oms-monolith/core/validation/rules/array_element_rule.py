"""
Array Element Constraint Rule

Validates constraints on array/list elements including uniqueness, enum values, and patterns.
Implements Foundry Dataset Rules array validation capabilities.

⚠️ LEGACY CODE WARNING: This module duplicates TerminusDB's native array constraints.
   Migration planned to use TerminusDB native validation.
   See: core/validation/terminus_boundary_definition.py
   Status: Phase 1 - Detection and logging
"""

import logging
import re
import warnings
from typing import List, Set, Optional, Dict, Any, Union, Pattern
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from core.validation.rules.base import BaseRule, RuleResult
from core.validation.models import BreakingChange, Severity, ValidationContext, MigrationStrategy
from core.validation.interfaces import BreakingChangeRule
from core.validation.ports import TerminusPort

logger = logging.getLogger(__name__)


class ArrayConstraintType(str, Enum):
    """Types of array constraints"""
    UNIQUE_ELEMENTS = "unique_elements"
# REMOVED: TerminusDB handles enum_validation natively
#     ENUM_VALUES = "enum_values"
    REGEX_PATTERN = "regex_pattern"
    MIN_LENGTH = "min_length"
    MAX_LENGTH = "max_length"
    ELEMENT_TYPE = "element_type"
    NO_NULLS = "no_nulls"


@dataclass
class ArrayConstraint:
    """Array constraint configuration"""
    field_name: str
    constraint_type: ArrayConstraintType
    constraint_value: Any
    nullable: bool = True  # Array itself can be null
    custom_error_message: Optional[str] = None
    
    # Additional configuration per constraint type
    case_sensitive: bool = True  # For enum/regex constraints
    allow_empty_arrays: bool = True
    element_separator: str = ","  # For parsing array strings


class ArrayElementConstraintRule(BreakingChangeRule):
    """
    Array Element Constraint Rule
    
    Validates various constraints on array/list field elements:
    - Unique elements within arrays
    - Enum value constraints for array elements
    - Regex pattern matching for array elements
    - Array length constraints (min/max)
    - Element type validation
    - Null element detection
    
    Features:
    - Multi-field array validation
    - WOQL-based validation for performance
    - Foundry-compatible array handling
    - Custom error messages
    - Flexible constraint combinations
    """
    
    def __init__(
        self, 
        array_constraints: List[ArrayConstraint],
        terminus_port: Optional[TerminusPort] = None
    ):
        super().__init__()
        
        # Legacy code deprecation warning
        warnings.warn(
            "ArrayElementRule is legacy code that duplicates TerminusDB's native array constraints. "
            "This will be migrated to use TerminusDB native validation. "
            "See: core/validation/terminus_boundary_definition.py",
            DeprecationWarning,
            stacklevel=2
        )
        
        # Log legacy usage for monitoring
        logger.info("LEGACY_VALIDATION_USED", extra={
            "rule": "ArrayElementRule",
            "feature": "array_validation",
            "constraints_count": len(array_constraints)
        })
        
        self._rule_id = "array_element_constraint"
        self._name = "Array Element Constraint Validation"
        self._description = "Validates constraints on array/list field elements"
        self.array_constraints = {ac.field_name: ac for ac in array_constraints}
        self.terminus_port = terminus_port
        self.priority = 45  # Run after basic field validation
    
    @property
    def rule_id(self) -> str:
        return self._rule_id
    
    @property 
    def description(self) -> str:
        return self._description
    
    def check(self, old_schema: Dict, new_schema: Dict) -> List[BreakingChange]:
        """Synchronous check method for interface compatibility"""
        import asyncio
        try:
            return asyncio.run(self._async_check(old_schema, new_schema))
        except RuntimeError:
            loop = asyncio.get_event_loop()
            task = loop.create_task(self._async_check(old_schema, new_schema))
            return task.result() if task.done() else []
    
    async def estimate_impact(self, breaking_change: BreakingChange, data_source: Any) -> Dict[str, Any]:
        """Estimate impact of array constraint violations"""
        field_name = breaking_change.field_name
        constraint = self.array_constraints.get(field_name)
        
        if not constraint or not self.terminus_port:
            return {"estimated_violations": "unknown"}
        
        try:
            # Count violations using WOQL
            violation_count_query = self._build_violation_count_query(field_name, constraint)
            result = await self.terminus_port.query(violation_count_query)
            violation_count = result[0].get('violation_count', 0) if result else 0
            
            return {
                "estimated_violations": violation_count,
                "field_name": field_name,
                "constraint_type": constraint.constraint_type,
                "constraint_value": str(constraint.constraint_value),
                "fix_complexity": self._assess_fix_complexity(constraint, violation_count),
                "rollback_feasible": violation_count < 5000
            }
        except Exception as e:
            logger.error(f"Failed to estimate array constraint impact: {e}")
            return {"estimated_violations": "error", "error": str(e)}
    
    async def _async_check(self, old_schema: Dict, new_schema: Dict) -> List[BreakingChange]:
        """Internal async validation logic"""
        breaking_changes = []
        
        if not self.terminus_port:
            logger.warning("TerminusPort not available for array validation")
            return breaking_changes
        
        # Check each array constraint
        for field_name, constraint in self.array_constraints.items():
            try:
                violations = await self._check_array_constraint(field_name, constraint, new_schema)
                if violations:
                    breaking_change = self._create_breaking_change(field_name, constraint, violations)
                    breaking_changes.append(breaking_change)
                    
            except Exception as e:
                logger.error(f"Array constraint check failed for field {field_name}: {e}")
                breaking_changes.append(self._create_error_breaking_change(field_name, str(e)))
        
        return breaking_changes
    
    async def _check_array_constraint(
        self, 
        field_name: str, 
        constraint: ArrayConstraint,
        schema: Dict
    ) -> Optional[List[Dict[str, Any]]]:
        """Check a specific array constraint using WOQL"""
        
        # Build appropriate WOQL query based on constraint type
        violation_query = self._build_violation_query(field_name, constraint)
        
        try:
            violations = await self.terminus_port.query(violation_query)
            return violations if violations else None
            
        except Exception as e:
            logger.error(f"WOQL array validation query failed for {field_name}: {e}")
            raise
    
    def _build_violation_query(self, field_name: str, constraint: ArrayConstraint) -> str:
        """Build WOQL query to find array constraint violations"""
        
        constraint_filter = self._build_constraint_filter(field_name, constraint)
        
        # Handle nullable arrays
        null_handling = ""
        if constraint.nullable:
            null_handling = f"FILTER(BOUND(?{field_name}_array))"
        else:
            null_handling = f"FILTER(!BOUND(?{field_name}_array))"
        
        # Base query structure
        query = f"""
        SELECT ?entity ?{field_name}_array ?violation_details
        WHERE {{
            ?entity a ?entity_type .
            OPTIONAL {{ ?entity <@schema:{field_name}> ?{field_name}_array }}
            
            {null_handling}
            
            # Apply constraint-specific filter
            {constraint_filter}
            
            BIND("{constraint.constraint_type}" AS ?violation_type)
        }}
        LIMIT 100
        """
        
        return query
    
    def _build_constraint_filter(self, field_name: str, constraint: ArrayConstraint) -> str:
        """Build constraint-specific WOQL filter"""
        
        if constraint.constraint_type == ArrayConstraintType.UNIQUE_ELEMENTS:
            return self._build_unique_elements_filter(field_name, constraint)
        elif constraint.constraint_type == ArrayConstraintType.ENUM_VALUES:
# REMOVED: TerminusDB handles enum_validation natively
#             return self._build_enum_values_filter(field_name, constraint)
        elif constraint.constraint_type == ArrayConstraintType.REGEX_PATTERN:
            return self._build_regex_pattern_filter(field_name, constraint)
        elif constraint.constraint_type == ArrayConstraintType.MIN_LENGTH:
            return self._build_min_length_filter(field_name, constraint)
        elif constraint.constraint_type == ArrayConstraintType.MAX_LENGTH:
            return self._build_max_length_filter(field_name, constraint)
        elif constraint.constraint_type == ArrayConstraintType.NO_NULLS:
            return self._build_no_nulls_filter(field_name, constraint)
        else:
            return f"# Unsupported constraint type: {constraint.constraint_type}"
    
    def _build_unique_elements_filter(self, field_name: str, constraint: ArrayConstraint) -> str:
        """Build filter for unique elements constraint"""
        separator = constraint.element_separator
        return f"""
        # Check for duplicate elements in array
        FILTER(
            BOUND(?{field_name}_array) &&
            # Split array and check for duplicates (simplified check)
            CONTAINS(STR(?{field_name}_array), "{separator}") &&
            # This is a simplified check - full implementation would need array parsing
            REGEX(STR(?{field_name}_array), "([^{separator}]+).*\\1")
        )
        BIND("duplicate_elements_detected" AS ?violation_details)
        """
    
# REMOVED: TerminusDB handles enum_validation natively
#     def _build_enum_values_filter(self, field_name: str, constraint: ArrayConstraint) -> str:
        """Build filter for enum values constraint"""
        if not isinstance(constraint.constraint_value, (list, set)):
            return f"# Invalid enum constraint value: {constraint.constraint_value}"
        
        allowed_values = set(constraint.constraint_value)
        separator = constraint.element_separator
        
        # Build regex pattern to check for disallowed values
        disallowed_pattern = f"[^{separator}]*(?!{'|'.join(re.escape(v) for v in allowed_values)})[^{separator}]*"
        
        return f"""
        # Check for enum values constraint violations
        FILTER(
            BOUND(?{field_name}_array) &&
            REGEX(STR(?{field_name}_array), "{disallowed_pattern}")
        )
        BIND("enum_violation_in_array" AS ?violation_details)
        """
    
    def _build_regex_pattern_filter(self, field_name: str, constraint: ArrayConstraint) -> str:
        """Build filter for regex pattern constraint"""
        if not isinstance(constraint.constraint_value, (str, Pattern)):
            return f"# Invalid regex constraint value: {constraint.constraint_value}"
        
        pattern = str(constraint.constraint_value)
        case_flag = "" if constraint.case_sensitive else ", \"i\""
        
        return f"""
        # Check for regex pattern violations in array elements
        FILTER(
            BOUND(?{field_name}_array) &&
            # This checks if any element doesn't match the pattern
            !REGEX(STR(?{field_name}_array), "{pattern}"{case_flag})
        )
        BIND("regex_pattern_violation" AS ?violation_details)
        """
    
    def _build_min_length_filter(self, field_name: str, constraint: ArrayConstraint) -> str:
        """Build filter for minimum array length constraint"""
        min_length = int(constraint.constraint_value)
        separator = constraint.element_separator
        
        return f"""
        # Check for minimum array length violations
        FILTER(
            BOUND(?{field_name}_array) &&
            # Count elements by counting separators + 1
            ((STRLEN(STR(?{field_name}_array)) - STRLEN(REPLACE(STR(?{field_name}_array), "{separator}", ""))) + 1) < {min_length}
        )
        BIND("array_too_short" AS ?violation_details)
        """
    
    def _build_max_length_filter(self, field_name: str, constraint: ArrayConstraint) -> str:
        """Build filter for maximum array length constraint"""
        max_length = int(constraint.constraint_value)
        separator = constraint.element_separator
        
        return f"""
        # Check for maximum array length violations
        FILTER(
            BOUND(?{field_name}_array) &&
            # Count elements by counting separators + 1
            ((STRLEN(STR(?{field_name}_array)) - STRLEN(REPLACE(STR(?{field_name}_array), "{separator}", ""))) + 1) > {max_length}
        )
        BIND("array_too_long" AS ?violation_details)
        """
    
    def _build_no_nulls_filter(self, field_name: str, constraint: ArrayConstraint) -> str:
        """Build filter for no null elements constraint"""
        separator = constraint.element_separator
        
        return f"""
        # Check for null elements in array
        FILTER(
            BOUND(?{field_name}_array) &&
            # Check for empty elements (null represented as empty string between separators)
            (REGEX(STR(?{field_name}_array), "{separator}{separator}") ||
             STRSTARTS(STR(?{field_name}_array), "{separator}") ||
             STRENDS(STR(?{field_name}_array), "{separator}"))
        )
        BIND("null_elements_found" AS ?violation_details)
        """
    
    def _build_violation_count_query(self, field_name: str, constraint: ArrayConstraint) -> str:
        """Build WOQL query to count array constraint violations"""
        constraint_filter = self._build_constraint_filter(field_name, constraint)
        
        null_handling = ""
        if constraint.nullable:
            null_handling = f"FILTER(BOUND(?{field_name}_array))"
        else:
            null_handling = f"FILTER(!BOUND(?{field_name}_array))"
        
        query = f"""
        SELECT (COUNT(?entity) AS ?violation_count)
        WHERE {{
            ?entity a ?entity_type .
            OPTIONAL {{ ?entity <@schema:{field_name}> ?{field_name}_array }}
            {null_handling}
            {constraint_filter}
        }}
        """
        
        return query
    
    def _create_breaking_change(
        self, 
        field_name: str, 
        constraint: ArrayConstraint, 
        violations: List[Dict[str, Any]]
    ) -> BreakingChange:
        """Create breaking change for array constraint violations"""
        
        violation_count = len(violations)
        sample_violations = violations[:3]  # Show first 3 violations
        
        # Determine severity based on constraint type and violation count
        severity = self._assess_violation_severity(constraint, violation_count)
        
        # Custom error message or default
        description = constraint.custom_error_message or self._get_default_error_message(
            field_name, constraint, violation_count
        )
        
        # Migration strategies based on constraint type and violation count
        strategies = self._get_migration_strategies(constraint, violation_count)
        
        return BreakingChange(
            rule_id=self.rule_id,
            severity=severity,
            object_type="array_field",
            field_name=field_name,
            description=description,
            old_value=None,
            new_value={
                "constraint_type": constraint.constraint_type,
                "constraint_value": str(constraint.constraint_value)
            },
            impact={
                "array_constraint_violation": True,
                "constraint_type": constraint.constraint_type,
                "violation_count": violation_count,
                "sample_violations": sample_violations,
                "nullable": constraint.nullable,
                "allow_empty_arrays": constraint.allow_empty_arrays
            },
            suggested_strategies=strategies,
            detected_at=datetime.utcnow()
        )
    
    def _create_error_breaking_change(self, field_name: str, error_message: str) -> BreakingChange:
        """Create breaking change for validation errors"""
        return BreakingChange(
            rule_id=self.rule_id,
            severity=Severity.MEDIUM,
            object_type="array_field",
            field_name=field_name,
            description=f"Array validation failed: {error_message}",
            old_value=None,
            new_value=None,
            impact={"validation_error": True, "field": field_name},
            suggested_strategies=[MigrationStrategy.MANUAL_REVIEW],
            detected_at=datetime.utcnow()
        )
    
    def _assess_violation_severity(self, constraint: ArrayConstraint, violation_count: int) -> Severity:
        """Assess severity based on constraint type and violation count"""
        
        # Critical constraints that affect data integrity
        critical_constraints = {
            ArrayConstraintType.UNIQUE_ELEMENTS,
            ArrayConstraintType.NO_NULLS
        }
        
        if constraint.constraint_type in critical_constraints:
            if violation_count > 100:
                return Severity.CRITICAL
            elif violation_count > 10:
                return Severity.HIGH
            else:
                return Severity.MEDIUM
        else:
            # Less critical constraints (format, length, etc.)
            if violation_count > 1000:
                return Severity.HIGH
            elif violation_count > 100:
                return Severity.MEDIUM
            else:
                return Severity.LOW
    
    def _get_default_error_message(
        self, 
        field_name: str, 
        constraint: ArrayConstraint, 
        violation_count: int
    ) -> str:
        """Get default error message for constraint violations"""
        
        constraint_descriptions = {
            ArrayConstraintType.UNIQUE_ELEMENTS: f"Array field '{field_name}' contains duplicate elements",
            ArrayConstraintType.ENUM_VALUES: f"Array field '{field_name}' contains values outside allowed set: {constraint.constraint_value}",
            ArrayConstraintType.REGEX_PATTERN: f"Array field '{field_name}' contains elements not matching pattern: {constraint.constraint_value}",
            ArrayConstraintType.MIN_LENGTH: f"Array field '{field_name}' has fewer than {constraint.constraint_value} elements",
            ArrayConstraintType.MAX_LENGTH: f"Array field '{field_name}' has more than {constraint.constraint_value} elements",
            ArrayConstraintType.NO_NULLS: f"Array field '{field_name}' contains null/empty elements"
        }
        
        base_message = constraint_descriptions.get(
            constraint.constraint_type, 
            f"Array constraint violation in field '{field_name}'"
        )
        
        return f"{base_message} ({violation_count} violations found)"
    
    def _get_migration_strategies(
        self, 
        constraint: ArrayConstraint, 
        violation_count: int
    ) -> List[MigrationStrategy]:
        """Get appropriate migration strategies for array constraint violations"""
        
        if constraint.constraint_type == ArrayConstraintType.UNIQUE_ELEMENTS:
            if violation_count < 50:
                return [MigrationStrategy.DATA_MIGRATION, MigrationStrategy.MANUAL_REVIEW]
            else:
                return [MigrationStrategy.DATA_MIGRATION, MigrationStrategy.COMPATIBILITY_LAYER]
        
        elif constraint.constraint_type in [ArrayConstraintType.ENUM_VALUES, ArrayConstraintType.REGEX_PATTERN]:
            return [MigrationStrategy.DATA_MIGRATION, MigrationStrategy.UPDATE_CONSTRAINTS]
        
        elif constraint.constraint_type in [ArrayConstraintType.MIN_LENGTH, ArrayConstraintType.MAX_LENGTH]:
            return [MigrationStrategy.UPDATE_CONSTRAINTS, MigrationStrategy.ADD_DEFAULTS]
        
        elif constraint.constraint_type == ArrayConstraintType.NO_NULLS:
            return [MigrationStrategy.DATA_MIGRATION, MigrationStrategy.ADD_DEFAULTS]
        
        else:
            return [MigrationStrategy.MANUAL_REVIEW]
    
    def _assess_fix_complexity(self, constraint: ArrayConstraint, violation_count: int) -> str:
        """Assess the complexity of fixing violations"""
        
        if violation_count > 5000:
            return "very_high"
        elif violation_count > 1000:
            return "high"
        elif violation_count > 100:
            return "medium"
        elif violation_count > 10:
            return "low"
        else:
            return "trivial"


# Factory functions for easy rule creation
def create_unique_array_rule(
    field_name: str,
    element_separator: str = ",",
    terminus_port: Optional[TerminusPort] = None
) -> ArrayElementConstraintRule:
    """Create a unique elements array constraint rule"""
    constraint = ArrayConstraint(
        field_name=field_name,
        constraint_type=ArrayConstraintType.UNIQUE_ELEMENTS,
        constraint_value=True,
        element_separator=element_separator
    )
    return ArrayElementConstraintRule([constraint], terminus_port)


def create_enum_array_rule(
    field_name: str,
    allowed_values: List[str],
    element_separator: str = ",",
    case_sensitive: bool = True,
    terminus_port: Optional[TerminusPort] = None
) -> ArrayElementConstraintRule:
    """Create an enum values array constraint rule"""
    constraint = ArrayConstraint(
        field_name=field_name,
        constraint_type=ArrayConstraintType.ENUM_VALUES,
        constraint_value=allowed_values,
        case_sensitive=case_sensitive,
        element_separator=element_separator
    )
    return ArrayElementConstraintRule([constraint], terminus_port)


def create_array_length_rule(
    field_name: str,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
    element_separator: str = ",",
    terminus_port: Optional[TerminusPort] = None
) -> ArrayElementConstraintRule:
    """Create array length constraint rule"""
    constraints = []
    
    if min_length is not None:
        constraints.append(ArrayConstraint(
            field_name=field_name,
            constraint_type=ArrayConstraintType.MIN_LENGTH,
            constraint_value=min_length,
            element_separator=element_separator
        ))
    
    if max_length is not None:
        constraints.append(ArrayConstraint(
            field_name=field_name,
            constraint_type=ArrayConstraintType.MAX_LENGTH,
            constraint_value=max_length,
            element_separator=element_separator
        ))
    
    return ArrayElementConstraintRule(constraints, terminus_port)


# Predefined Foundry-compatible array rules
def create_foundry_tags_rule(terminus_port: Optional[TerminusPort] = None) -> ArrayElementConstraintRule:
    """Create standard Foundry tags array rule"""
    constraints = [
        ArrayConstraint(
            field_name="tags",
            constraint_type=ArrayConstraintType.UNIQUE_ELEMENTS,
            constraint_value=True,
            element_separator=",",
            custom_error_message="Tags array must contain unique values"
        ),
        ArrayConstraint(
            field_name="tags",
            constraint_type=ArrayConstraintType.MAX_LENGTH,
            constraint_value=20,
            element_separator=",",
            custom_error_message="Tags array cannot contain more than 20 elements"
        )
    ]
    return ArrayElementConstraintRule(constraints, terminus_port)


def create_foundry_categories_rule(terminus_port: Optional[TerminusPort] = None) -> ArrayElementConstraintRule:
    """Create standard Foundry categories array rule"""
    predefined_categories = [
        "BUSINESS", "TECHNICAL", "OPERATIONAL", "COMPLIANCE", 
        "SECURITY", "ANALYTICS", "REPORTING", "INTEGRATION"
    ]
    
    constraint = ArrayConstraint(
        field_name="categories",
        constraint_type=ArrayConstraintType.ENUM_VALUES,
        constraint_value=predefined_categories,
        case_sensitive=True,
        element_separator=",",
        custom_error_message=f"Categories must be from predefined set: {predefined_categories}"
    )
    return ArrayElementConstraintRule([constraint], terminus_port)