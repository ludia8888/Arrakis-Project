"""
TerminusDB Native Schema Validation Rule

Consolidates schema constraint validation by leveraging TerminusDB's native
schema validation instead of duplicating logic in semantic_validator.
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from core.validation.rules.base import BaseRule, RuleResult
from core.validation.models import BreakingChange, Severity, ValidationContext, MigrationStrategy
from core.validation.interfaces import BreakingChangeRule
from core.validation.ports import TerminusPort

logger = logging.getLogger(__name__)


class TerminusNativeSchemaRule(BreakingChangeRule):
    """
    Leverages TerminusDB's native schema validation instead of duplicating constraint checks.
    
    This rule acts as a "pre-filter" that validates basic schema constraints using
    TerminusDB's built-in validation, reducing duplication with semantic_validator.
    """
    
    def __init__(self, terminus_port: TerminusPort):
        super().__init__(
            rule_id="terminus_native_schema",
            name="TerminusDB Native Schema Validation",
            description="Leverages TerminusDB native schema validation for constraints"
        )
        self.terminus_port = terminus_port
        self.priority = 10  # Run early as pre-filter
    
    @property
    def rule_id(self) -> str:
        return self._rule_id
    
    @property
    def description(self) -> str:
        return self._description
    
    def check(self, old_schema: Dict, new_schema: Dict) -> List[BreakingChange]:
        """Synchronous check method for interface compatibility"""
        # Create a minimal context for async execution
        import asyncio
        try:
            # Run the async validation in a new event loop if needed
            return asyncio.run(self._async_check(old_schema, new_schema))
        except RuntimeError:
            # If already in event loop, create a task
            loop = asyncio.get_event_loop()
            task = loop.create_task(self._async_check(old_schema, new_schema))
            return task.result() if task.done() else []
    
    async def estimate_impact(self, breaking_change: BreakingChange, data_source: Any) -> Dict[str, Any]:
        """Estimate impact of breaking change"""
        return {
            "affected_entities": 0,  # Would query TerminusDB to count
            "estimated_fix_time": "depends on validation complexity",
            "automation_possible": True,
            "risk_level": "low",  # Native validation is safe
            "rollback_feasible": True
        }
    
    async def _async_check(self, old_schema: Dict, new_schema: Dict) -> List[BreakingChange]:
        """Internal async validation logic"""
        result = RuleResult()
        
        try:
            # Let TerminusDB validate the schema changes natively
            schema_changes = context.schema_changes
            
            if not schema_changes:
                return result
            
            # Use TerminusDB's native validation via the adapter
            validation_result = await self.terminus_port.validate_schema_changes(schema_changes)
            
            # Convert TerminusDB validation errors to our format
            for error in validation_result.get('errors', []):
                breaking_change = self._convert_terminus_error_to_breaking_change(error, context)
                if breaking_change:
                    result.breaking_changes.append(breaking_change)
            
            # Add metadata about native validation
            result.metadata.update({
                "native_validation_used": True,
                "terminus_validator": "native_schema",
                "validation_timestamp": datetime.utcnow().isoformat(),
                "replaces_semantic_validator": ["domain_range", "cardinality", "type_constraints", "required_properties"]
            })
            
            logger.info(f"TerminusDB native schema validation found {len(result.breaking_changes)} issues")
            
        except Exception as e:
            logger.error(f"TerminusDB native schema validation failed: {e}")
            # Create a breaking change to indicate validation failure
            result.breaking_changes.append(BreakingChange(
                rule_id=self.rule_id,
                severity=Severity.HIGH,
                object_type="schema",
                field_name="validation",
                description=f"Native schema validation failed: {str(e)}",
                old_value=None,
                new_value=str(schema_changes),
                impact={"validation_failure": True, "native_validator": False},
                suggested_strategies=[MigrationStrategy.MANUAL_REVIEW],
                detected_at=datetime.utcnow()
            ))
        
        return result
    
    def _convert_terminus_error_to_breaking_change(
        self, 
        terminus_error: Dict[str, Any], 
        context: ValidationContext
    ) -> Optional[BreakingChange]:
        """Convert TerminusDB validation error to BreakingChange format"""
        
        error_type = terminus_error.get('type', 'unknown')
        message = terminus_error.get('message', 'Unknown validation error')
        field = terminus_error.get('field', 'unknown')
        
        # Map TerminusDB error types to our severity levels
        severity_mapping = {
            'schema_error': Severity.CRITICAL,
            'constraint_violation': Severity.HIGH,
            'type_mismatch': Severity.HIGH,
            'cardinality_violation': Severity.MEDIUM,
            'domain_violation': Severity.MEDIUM,
            'range_violation': Severity.MEDIUM,
            'required_field_missing': Severity.HIGH,
            'unknown': Severity.MEDIUM
        }
        
        # Map to migration strategies
        strategy_mapping = {
            'schema_error': [MigrationStrategy.MANUAL_REVIEW],
            'constraint_violation': [MigrationStrategy.UPDATE_CONSTRAINTS, MigrationStrategy.DATA_MIGRATION],
            'type_mismatch': [MigrationStrategy.TYPE_CONVERSION, MigrationStrategy.COMPATIBILITY_LAYER],
            'cardinality_violation': [MigrationStrategy.UPDATE_CONSTRAINTS],
            'domain_violation': [MigrationStrategy.UPDATE_CONSTRAINTS],
            'range_violation': [MigrationStrategy.UPDATE_CONSTRAINTS],
            'required_field_missing': [MigrationStrategy.ADD_DEFAULTS, MigrationStrategy.MANUAL_REVIEW],
            'unknown': [MigrationStrategy.MANUAL_REVIEW]
        }
        
        return BreakingChange(
            rule_id=self.rule_id,
            severity=severity_mapping.get(error_type, Severity.MEDIUM),
            object_type=terminus_error.get('object_type', 'entity'),
            field_name=field,
            description=f"TerminusDB native validation: {message}",
            old_value=terminus_error.get('old_value'),
            new_value=terminus_error.get('new_value'),
            impact={
                "native_validation": True,
                "error_type": error_type,
                "terminus_error": terminus_error
            },
            suggested_strategies=strategy_mapping.get(error_type, [MigrationStrategy.MANUAL_REVIEW]),
            detected_at=datetime.utcnow()
        )


class TerminusNativeCircularDependencyRule(BaseRule):
    """
    Uses TerminusDB's native path() queries for circular dependency detection.
    
    Replaces duplicate logic in dependency_analyzer by leveraging TerminusDB's
    built-in transitive closure capabilities.
    """
    
    def __init__(self, terminus_port: TerminusPort):
        super().__init__(
            rule_id="terminus_native_circular_deps",
            name="TerminusDB Native Circular Dependency Detection",
            description="Uses TerminusDB path() queries for circular dependency detection"
        )
        self.terminus_port = terminus_port
        self.priority = 20
    
    async def execute(self, context: ValidationContext) -> RuleResult:
        """
        Use TerminusDB's native path() queries to detect circular dependencies.
        
        This replaces manual cycle detection in dependency_analyzer.
        """
        result = RuleResult()
        
        try:
            # Use TerminusDB's native path queries for cycle detection
            cycles = await self.terminus_port.detect_circular_dependencies()
            
            for cycle in cycles:
                breaking_change = BreakingChange(
                    rule_id=self.rule_id,
                    severity=Severity.HIGH,
                    object_type="dependency",
                    field_name="circular_reference",
                    description=f"Circular dependency detected: {' -> '.join(cycle['path'])}",
                    old_value=None,
                    new_value=cycle['path'],
                    impact={
                        "circular_dependency": True,
                        "cycle_length": len(cycle['path']),
                        "affected_entities": cycle['path']
                    },
                    suggested_strategies=[
                        MigrationStrategy.BREAK_DEPENDENCY_CYCLE,
                        MigrationStrategy.INTRODUCE_INTERFACE
                    ],
                    detected_at=datetime.utcnow()
                )
                result.breaking_changes.append(breaking_change)
            
            result.metadata.update({
                "native_path_queries_used": True,
                "cycles_detected": len(cycles),
                "replaces_dependency_analyzer": True
            })
            
            logger.info(f"TerminusDB native circular dependency detection found {len(cycles)} cycles")
            
        except Exception as e:
            logger.error(f"TerminusDB native circular dependency detection failed: {e}")
            
        return result


class TerminusNativeMergeConflictRule(BaseRule):
    """
    Uses TerminusDB's native diff/merge capabilities for conflict detection.
    
    Consolidates merge conflict detection by leveraging TerminusDB's Git-like
    branching instead of duplicating logic across multiple validators.
    """
    
    def __init__(self, terminus_port: TerminusPort):
        super().__init__(
            rule_id="terminus_native_merge_conflicts",
            name="TerminusDB Native Merge Conflict Detection", 
            description="Uses TerminusDB native diff/merge for conflict detection"
        )
        self.terminus_port = terminus_port
        self.priority = 30
    
    async def execute(self, context: ValidationContext) -> RuleResult:
        """
        Use TerminusDB's native merge conflict detection.
        
        This replaces duplicate logic in both traversal merge_validator
        and validation merge_validation_service.
        """
        result = RuleResult()
        
        # Only run during merge validation context
        if not context.context.get("merge_validation"):
            return result
        
        try:
            source_branch = context.context.get("source_branch")
            target_branch = context.context.get("target_branch") 
            base_branch = context.context.get("base_branch", "main")
            
            if not source_branch or not target_branch:
                return result
            
            # Use TerminusDB's native merge conflict detection
            conflicts = await self.terminus_port.detect_merge_conflicts(
                source_branch, target_branch, base_branch
            )
            
            for conflict in conflicts:
                breaking_change = BreakingChange(
                    rule_id=self.rule_id,
                    severity=self._assess_conflict_severity(conflict),
                    object_type=conflict.get('object_type', 'entity'),
                    field_name=conflict.get('field', 'unknown'),
                    description=f"Merge conflict: {conflict.get('description', 'Unknown conflict')}",
                    old_value=conflict.get('base_value'),
                    new_value=conflict.get('head_value'),
                    impact={
                        "merge_conflict": True,
                        "conflict_type": conflict.get('type'),
                        "branches": [source_branch, target_branch]
                    },
                    suggested_strategies=self._get_conflict_resolution_strategies(conflict),
                    detected_at=datetime.utcnow()
                )
                result.breaking_changes.append(breaking_change)
            
            result.metadata.update({
                "native_merge_detection": True,
                "conflicts_found": len(conflicts),
                "replaces_validators": ["merge_validator", "merge_validation_service"]
            })
            
            logger.info(f"TerminusDB native merge conflict detection found {len(conflicts)} conflicts")
            
        except Exception as e:
            logger.error(f"TerminusDB native merge conflict detection failed: {e}")
            
        return result
    
    def _assess_conflict_severity(self, conflict: Dict[str, Any]) -> Severity:
        """Assess the severity of a merge conflict"""
        conflict_type = conflict.get('type', '').lower()
        
        if 'critical' in conflict_type or 'schema' in conflict_type:
            return Severity.CRITICAL
        elif 'type' in conflict_type or 'constraint' in conflict_type:
            return Severity.HIGH
        elif 'property' in conflict_type:
            return Severity.MEDIUM
        else:
            return Severity.LOW
    
    def _get_conflict_resolution_strategies(self, conflict: Dict[str, Any]) -> List[MigrationStrategy]:
        """Get appropriate resolution strategies for conflict type"""
        conflict_type = conflict.get('type', '').lower()
        
        if 'type' in conflict_type:
            return [MigrationStrategy.TYPE_CONVERSION, MigrationStrategy.MANUAL_REVIEW]
        elif 'constraint' in conflict_type:
            return [MigrationStrategy.UPDATE_CONSTRAINTS, MigrationStrategy.COMPATIBILITY_LAYER]
        elif 'property' in conflict_type:
            return [MigrationStrategy.MERGE_PROPERTIES, MigrationStrategy.MANUAL_REVIEW]
        else:
            return [MigrationStrategy.MANUAL_REVIEW]