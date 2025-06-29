"""
Enum Value Constraint Rule

Validates that column values are within allowed enumeration sets.
Implements Foundry Dataset Rules enum validation with nullable options.
"""

import logging
from typing import List, Set, Optional, Dict, Any, Union
from datetime import datetime
from dataclasses import dataclass

from core.validation.rules.base import BaseRule, RuleResult
from core.validation.models import BreakingChange, Severity, ValidationContext, MigrationStrategy
from core.validation.interfaces import BreakingChangeRule
from core.validation.ports import TerminusPort

logger = logging.getLogger(__name__)


@dataclass
class EnumConstraint:
    """Enum constraint configuration"""
    field_name: str
    allowed_values: Set[str]
    nullable: bool = False
    case_sensitive: bool = True
    custom_error_message: Optional[str] = None


class EnumValueConstraintRule(BreakingChangeRule):
    """
    Enum Value Constraint Rule
    
    Validates that specified fields contain only values from predefined enumerations.
    Supports Foundry-style enum validation with nullable and case-sensitivity options.
    
    Features:
    - Multi-field enum validation
    - Nullable enum support (Foundry NULL-friendly)
    - Case-sensitive/insensitive matching
    - Custom error messages
    - WOQL-based validation for performance
    """
    
    def __init__(
        self, 
        enum_constraints: List[EnumConstraint],
        terminus_port: Optional[TerminusPort] = None
    ):
        super().__init__()
        self._rule_id = "enum_value_constraint"
        self._name = "Enum Value Constraint Validation"
        self._description = "Validates that column values are within allowed enumeration sets"
        self.enum_constraints = {ec.field_name: ec for ec in enum_constraints}
        self.terminus_port = terminus_port
        self.priority = 40  # Medium priority - run after basic validation
    
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
        """Estimate impact of enum constraint violations"""
        field_name = breaking_change.field_name
        constraint = self.enum_constraints.get(field_name)
        
        if not constraint or not self.terminus_port:
            return {"estimated_violations": "unknown"}
        
        # Count total violations using WOQL
        violation_count_query = self._build_violation_count_query(field_name, constraint)
        
        try:
            result = await self.terminus_port.query(violation_count_query)
            violation_count = result[0].get('violation_count', 0) if result else 0
            
            return {
                "estimated_violations": violation_count,
                "field_name": field_name,
                "allowed_values": list(constraint.allowed_values),
                "nullable": constraint.nullable,
                "fix_complexity": "medium" if violation_count < 1000 else "high",
                "rollback_feasible": violation_count < 10000
            }
        except Exception as e:
            logger.error(f"Failed to estimate enum constraint impact: {e}")
            return {"estimated_violations": "error", "error": str(e)}
    
    async def _async_check(self, old_schema: Dict, new_schema: Dict) -> List[BreakingChange]:
        """Internal async validation logic"""
        breaking_changes = []
        
        if not self.terminus_port:
            logger.warning("TerminusPort not available for enum validation")
            return breaking_changes
        
        # Check each enum constraint
        for field_name, constraint in self.enum_constraints.items():
            try:
                violations = await self._check_enum_constraint(field_name, constraint, new_schema)
                if violations:
                    breaking_change = self._create_breaking_change(field_name, constraint, violations)
                    breaking_changes.append(breaking_change)
                    
            except Exception as e:
                logger.error(f"Enum constraint check failed for field {field_name}: {e}")
                # Create error breaking change
                breaking_changes.append(BreakingChange(
                    rule_id=self.rule_id,
                    severity=Severity.MEDIUM,
                    object_type="field",
                    field_name=field_name,
                    description=f"Enum validation failed: {str(e)}",
                    old_value=None,
                    new_value=None,
                    impact={"validation_error": True, "field": field_name},
                    suggested_strategies=[MigrationStrategy.MANUAL_REVIEW],
                    detected_at=datetime.utcnow()
                ))
        
        return breaking_changes
    
    async def _check_enum_constraint(
        self, 
        field_name: str, 
        constraint: EnumConstraint,
        schema: Dict
    ) -> Optional[List[Dict[str, Any]]]:
        """Check a specific enum constraint using WOQL"""
        
        # Build WOQL query to find violations
        violation_query = self._build_violation_query(field_name, constraint)
        
        try:
            violations = await self.terminus_port.query(violation_query)
            return violations if violations else None
            
        except Exception as e:
            logger.error(f"WOQL enum validation query failed for {field_name}: {e}")
            raise
    
    def _build_violation_query(self, field_name: str, constraint: EnumConstraint) -> str:
        """Build WOQL query to find enum constraint violations"""
        
        # Create allowed values filter
        allowed_values_filter = self._build_allowed_values_filter(constraint)
        
        # Handle nullable option
        null_filter = ""
        if constraint.nullable:
            null_filter = f"FILTER(!BOUND(?{field_name}_value) || ({allowed_values_filter}))"
        else:
            null_filter = f"FILTER(BOUND(?{field_name}_value) && ({allowed_values_filter}))"
        
        # Build complete query
        query = f"""
        SELECT ?entity ?{field_name}_value ?violation_type
        WHERE {{
            ?entity a ?entity_type .
            ?entity <@schema:{field_name}> ?{field_name}_value .
            
            # Check enum constraint violations
            {null_filter}
            
            BIND("enum_violation" AS ?violation_type)
        }}
        LIMIT 100
        """
        
        return query
    
    def _build_violation_count_query(self, field_name: str, constraint: EnumConstraint) -> str:
        """Build WOQL query to count enum constraint violations"""
        
        allowed_values_filter = self._build_allowed_values_filter(constraint)
        
        null_filter = ""
        if constraint.nullable:
            null_filter = f"FILTER(!BOUND(?{field_name}_value) || ({allowed_values_filter}))"
        else:
            null_filter = f"FILTER(BOUND(?{field_name}_value) && ({allowed_values_filter}))"
        
        query = f"""
        SELECT (COUNT(?entity) AS ?violation_count)
        WHERE {{
            ?entity a ?entity_type .
            ?entity <@schema:{field_name}> ?{field_name}_value .
            {null_filter}
        }}
        """
        
        return query
    
    def _build_allowed_values_filter(self, constraint: EnumConstraint) -> str:
        """Build WOQL filter for allowed values"""
        
        if constraint.case_sensitive:
            # Case-sensitive exact match
            values_list = ", ".join(f'"{value}"' for value in constraint.allowed_values)
            return f"?{constraint.field_name}_value IN ({values_list})"
        else:
            # Case-insensitive match using REGEX
            regex_pattern = "|".join(f"^{value}$" for value in constraint.allowed_values)
            return f'REGEX(STR(?{constraint.field_name}_value), "{regex_pattern}", "i")'
    
    def _create_breaking_change(
        self, 
        field_name: str, 
        constraint: EnumConstraint, 
        violations: List[Dict[str, Any]]
    ) -> BreakingChange:
        """Create breaking change for enum constraint violations"""
        
        violation_count = len(violations)
        sample_violations = violations[:5]  # Show first 5 violations
        
        # Determine severity based on violation count
        if violation_count > 1000:
            severity = Severity.CRITICAL
        elif violation_count > 100:
            severity = Severity.HIGH
        elif violation_count > 10:
            severity = Severity.MEDIUM
        else:
            severity = Severity.LOW
        
        # Custom error message or default
        if constraint.custom_error_message:
            description = constraint.custom_error_message
        else:
            description = (
                f"Enum constraint violation in field '{field_name}': "
                f"{violation_count} values found outside allowed set {list(constraint.allowed_values)}"
            )
        
        # Migration strategies based on violation count
        if violation_count < 10:
            strategies = [MigrationStrategy.DATA_MIGRATION, MigrationStrategy.MANUAL_REVIEW]
        elif violation_count < 100:
            strategies = [MigrationStrategy.DATA_MIGRATION, MigrationStrategy.ADD_DEFAULTS]
        else:
            strategies = [MigrationStrategy.UPDATE_CONSTRAINTS, MigrationStrategy.COMPATIBILITY_LAYER]
        
        return BreakingChange(
            rule_id=self.rule_id,
            severity=severity,
            object_type="field",
            field_name=field_name,
            description=description,
            old_value=None,
            new_value={"constraint": "enum", "allowed_values": list(constraint.allowed_values)},
            impact={
                "enum_constraint_violation": True,
                "violation_count": violation_count,
                "sample_violations": sample_violations,
                "nullable": constraint.nullable,
                "case_sensitive": constraint.case_sensitive,
                "allowed_values": list(constraint.allowed_values)
            },
            suggested_strategies=strategies,
            detected_at=datetime.utcnow()
        )


class EnumSchemaChangeRule(BaseRule):
    """
    Detects when enum constraints are being added/removed/modified in schema changes.
    
    Complementary to EnumValueConstraintRule - focuses on schema evolution rather than data validation.
    """
    
    def __init__(self):
        super().__init__(
            rule_id="enum_schema_change",
            name="Enum Schema Change Detection", 
            description="Detects addition, removal, or modification of enum constraints"
        )
        self.priority = 35  # Run before data validation
    
    async def execute(self, context: ValidationContext) -> RuleResult:
        """Execute enum schema change detection"""
        result = RuleResult()
        
        schema_changes = context.schema_changes
        if not schema_changes:
            return result
        
        # Look for enum-related schema changes
        enum_changes = self._detect_enum_changes(schema_changes)
        
        for change in enum_changes:
            breaking_change = BreakingChange(
                rule_id=self.rule_id,
                severity=self._assess_enum_change_severity(change),
                object_type="schema",
                field_name=change.get("field_name", "unknown"),
                description=f"Enum constraint change: {change['change_type']}",
                old_value=change.get("old_constraint"),
                new_value=change.get("new_constraint"),
                impact={
                    "enum_schema_change": True,
                    "change_type": change["change_type"],
                    "field_affected": change.get("field_name")
                },
                suggested_strategies=self._get_enum_change_strategies(change),
                detected_at=datetime.utcnow()
            )
            result.breaking_changes.append(breaking_change)
        
        result.metadata.update({
            "enum_changes_detected": len(enum_changes),
            "enum_change_types": [c["change_type"] for c in enum_changes]
        })
        
        return result
    
    def _detect_enum_changes(self, schema_changes: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect enum constraint changes in schema"""
        enum_changes = []
        
        # Look through different types of schema changes
        for change_type, changes in schema_changes.items():
            if "constraint" in change_type.lower() or "enum" in change_type.lower():
                for change in changes:
                    if self._is_enum_related(change):
                        enum_changes.append({
                            "change_type": change_type,
                            "field_name": change.get("field_name", change.get("name")),
                            "old_constraint": change.get("old_value"),
                            "new_constraint": change.get("new_value"),
                            "details": change
                        })
        
        return enum_changes
    
    def _is_enum_related(self, change: Any) -> bool:
        """Check if a schema change is enum-related"""
        if isinstance(change, dict):
            # Check for enum keywords in change description
            change_str = str(change).lower()
            enum_keywords = ["enum", "allowed_values", "valid_values", "choices", "options"]
            return any(keyword in change_str for keyword in enum_keywords)
        return False
    
    def _assess_enum_change_severity(self, change: Dict[str, Any]) -> Severity:
        """Assess severity of enum constraint changes"""
        change_type = change.get("change_type", "").lower()
        
        if "removal" in change_type:
            return Severity.HIGH  # Removing constraints can cause data quality issues
        elif "addition" in change_type:
            return Severity.MEDIUM  # Adding constraints may break existing data
        elif "modification" in change_type:
            return Severity.MEDIUM  # Modifying constraints requires careful review
        else:
            return Severity.LOW
    
    def _get_enum_change_strategies(self, change: Dict[str, Any]) -> List[MigrationStrategy]:
        """Get appropriate migration strategies for enum changes"""
        change_type = change.get("change_type", "").lower()
        
        if "removal" in change_type:
            return [MigrationStrategy.MANUAL_REVIEW, MigrationStrategy.UPDATE_CONSTRAINTS]
        elif "addition" in change_type:
            return [MigrationStrategy.DATA_MIGRATION, MigrationStrategy.ADD_DEFAULTS]
        else:
            return [MigrationStrategy.COMPATIBILITY_LAYER, MigrationStrategy.MANUAL_REVIEW]


# Factory functions for easy rule creation
def create_enum_constraint_rule(
    field_name: str,
    allowed_values: List[str],
    nullable: bool = False,
    case_sensitive: bool = True,
    custom_error_message: Optional[str] = None,
    terminus_port: Optional[TerminusPort] = None
) -> EnumValueConstraintRule:
    """Create a single-field enum constraint rule"""
    constraint = EnumConstraint(
        field_name=field_name,
        allowed_values=set(allowed_values),
        nullable=nullable,
        case_sensitive=case_sensitive,
        custom_error_message=custom_error_message
    )
    return EnumValueConstraintRule([constraint], terminus_port)


def create_multi_enum_rule(
    constraints: List[EnumConstraint],
    terminus_port: Optional[TerminusPort] = None
) -> EnumValueConstraintRule:
    """Create a multi-field enum constraint rule"""
    return EnumValueConstraintRule(constraints, terminus_port)


# Predefined common enum rules for Foundry compliance
def create_foundry_status_enum_rule(terminus_port: Optional[TerminusPort] = None) -> EnumValueConstraintRule:
    """Create standard Foundry status enum rule"""
    constraint = EnumConstraint(
        field_name="status",
        allowed_values={"ACTIVE", "INACTIVE", "PENDING", "ARCHIVED", "DELETED"},
        nullable=False,
        case_sensitive=True,
        custom_error_message="Status field must be one of: ACTIVE, INACTIVE, PENDING, ARCHIVED, DELETED"
    )
    return EnumValueConstraintRule([constraint], terminus_port)


def create_foundry_priority_enum_rule(terminus_port: Optional[TerminusPort] = None) -> EnumValueConstraintRule:
    """Create standard Foundry priority enum rule"""
    constraint = EnumConstraint(
        field_name="priority",
        allowed_values={"LOW", "MEDIUM", "HIGH", "CRITICAL"},
        nullable=True,  # Priority can be null
        case_sensitive=True,
        custom_error_message="Priority field must be one of: LOW, MEDIUM, HIGH, CRITICAL (or null)"
    )
    return EnumValueConstraintRule([constraint], terminus_port)