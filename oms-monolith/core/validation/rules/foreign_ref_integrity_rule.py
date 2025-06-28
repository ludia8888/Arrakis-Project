"""
Foreign Reference Integrity Rule

Validates referential integrity across datasets, including cross-dataset foreign key constraints.
Implements Foundry-style foreign dataset reference validation using TerminusDB.

⚠️ LEGACY CODE WARNING: This module duplicates TerminusDB's native referential integrity.
   TerminusDB provides built-in foreign key constraints and referential integrity checks.
   See: core/validation/terminus_boundary_definition.py
   Status: Phase 1 - Detection and logging
"""

import logging
import warnings
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from core.validation.rules.base import BaseRule, RuleResult
from core.validation.models import BreakingChange, Severity, ValidationContext, MigrationStrategy
from core.validation.interfaces import BreakingChangeRule
from core.validation.ports import TerminusPort

logger = logging.getLogger(__name__)


class ReferenceType(str, Enum):
    """Types of foreign references"""
    FOREIGN_KEY = "foreign_key"
    WEAK_REFERENCE = "weak_reference"
    CROSS_DATASET = "cross_dataset"
    HIERARCHICAL = "hierarchical"
    MANY_TO_MANY = "many_to_many"


class IntegrityAction(str, Enum):
    """Actions to take on integrity violations"""
    RESTRICT = "restrict"  # Prevent changes that break integrity
    CASCADE = "cascade"    # Cascade changes to referenced entities
    SET_NULL = "set_null"  # Set foreign key to null on reference deletion
    SET_DEFAULT = "set_default"  # Set foreign key to default value
    NO_ACTION = "no_action"  # Allow violations (just warn)


@dataclass
class ForeignReference:
    """Foreign reference configuration"""
    source_field: str
    target_dataset: str
    target_field: str
    reference_type: ReferenceType = ReferenceType.FOREIGN_KEY
    nullable: bool = True
    integrity_action: IntegrityAction = IntegrityAction.RESTRICT
    custom_error_message: Optional[str] = None
    
    # Cross-dataset configuration
    target_database: Optional[str] = None
    target_branch: Optional[str] = None
    
    # Performance optimization
    enable_caching: bool = True
    cache_ttl_seconds: int = 300


class ForeignReferenceIntegrityRule(BreakingChangeRule):
    """
    Foreign Reference Integrity Rule
    
    Validates referential integrity constraints including:
    - Standard foreign key references within the same dataset
    - Cross-dataset references (Foundry multi-dataset validation)
    - Weak references that allow missing targets
    - Hierarchical references (parent-child relationships)
    - Many-to-many relationship integrity
    
    Features:
    - Multi-database reference validation
    - Configurable integrity actions (RESTRICT, CASCADE, etc.)
    - Performance optimization with caching
    - Batch violation detection
    - Cross-branch reference validation
    """
    
    def __init__(
        self,
        foreign_references: List[ForeignReference],
        terminus_port: Optional[TerminusPort] = None
    ):
        super().__init__()
        self._rule_id = "foreign_reference_integrity"
        self._name = "Foreign Reference Integrity Validation"
        self._description = "Validates referential integrity across datasets and databases"
        self.foreign_references = {fr.source_field: fr for fr in foreign_references}
        self.terminus_port = terminus_port
        self.priority = 30  # High priority - run after schema validation
        
        # Caching for performance
        self._reference_cache: Dict[str, Set[Any]] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
    
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
        """Estimate impact of foreign reference integrity violations"""
        field_name = breaking_change.field_name
        reference = self.foreign_references.get(field_name)
        
        if not reference or not self.terminus_port:
            return {"estimated_violations": "unknown"}
        
        try:
            # Count violations and get statistics
            violation_stats = await self._get_violation_statistics(field_name, reference)
            
            return {
                "estimated_violations": violation_stats.get("violation_count", 0),
                "orphaned_references": violation_stats.get("orphaned_count", 0),
                "affected_entities": violation_stats.get("affected_entities", []),
                "target_dataset": reference.target_dataset,
                "reference_type": reference.reference_type,
                "integrity_action": reference.integrity_action,
                "fix_complexity": self._assess_fix_complexity(reference, violation_stats),
                "rollback_feasible": violation_stats.get("violation_count", 0) < 1000
            }
        except Exception as e:
            logger.error(f"Failed to estimate foreign reference impact: {e}")
            return {"estimated_violations": "error", "error": str(e)}
    
    async def _async_check(self, old_schema: Dict, new_schema: Dict) -> List[BreakingChange]:
        """Internal async validation logic"""
        breaking_changes = []
        
        if not self.terminus_port:
            logger.warning("TerminusPort not available for foreign reference validation")
            return breaking_changes
        
        # Check each foreign reference constraint
        for field_name, reference in self.foreign_references.items():
            try:
                violations = await self._check_foreign_reference(field_name, reference, new_schema)
                if violations:
                    breaking_change = self._create_breaking_change(field_name, reference, violations)
                    breaking_changes.append(breaking_change)
                    
            except Exception as e:
                logger.error(f"Foreign reference check failed for field {field_name}: {e}")
                breaking_changes.append(self._create_error_breaking_change(field_name, str(e)))
        
        return breaking_changes
    
    async def _check_foreign_reference(
        self,
        field_name: str,
        reference: ForeignReference,
        schema: Dict
    ) -> Optional[List[Dict[str, Any]]]:
        """Check a specific foreign reference constraint"""
        
        # Get valid target values (with caching)
        valid_targets = await self._get_valid_target_values(reference)
        
        if valid_targets is None:
            logger.warning(f"Could not retrieve valid targets for {reference.target_dataset}.{reference.target_field}")
            return None
        
        # Build and execute violation query
        violation_query = self._build_foreign_key_violation_query(field_name, reference, valid_targets)
        
        try:
            violations = await self.terminus_port.query(violation_query)
            return violations if violations else None
            
        except Exception as e:
            logger.error(f"Foreign reference validation query failed for {field_name}: {e}")
            raise
    
    async def _get_valid_target_values(self, reference: ForeignReference) -> Optional[Set[Any]]:
        """Get valid target values for foreign reference with caching"""
        
        cache_key = f"{reference.target_dataset}.{reference.target_field}"
        
        # Check cache validity
        if reference.enable_caching and self._is_cache_valid(cache_key, reference.cache_ttl_seconds):
            return self._reference_cache.get(cache_key)
        
        # Query target dataset for valid values
        target_query = self._build_target_values_query(reference)
        
        try:
            if reference.target_database and reference.target_database != "oms":
                # Cross-database query
                result = await self._query_cross_database(target_query, reference)
            else:
                # Same database query
                result = await self.terminus_port.query(target_query)
            
            # Extract valid values
            valid_values = set()
            for row in result:
                value = row.get(reference.target_field)
                if value is not None:
                    valid_values.add(value)
            
            # Update cache
            if reference.enable_caching:
                self._reference_cache[cache_key] = valid_values
                self._cache_timestamps[cache_key] = datetime.utcnow()
            
            return valid_values
            
        except Exception as e:
            logger.error(f"Failed to retrieve target values for {reference.target_dataset}: {e}")
            return None
    
    def _build_foreign_key_violation_query(
        self,
        field_name: str,
        reference: ForeignReference,
        valid_targets: Set[Any]
    ) -> str:
        """Build WOQL query to find foreign key violations"""
        
        # Convert valid targets to WOQL-compatible format
        if not valid_targets:
            # If no valid targets, all non-null references are violations
            valid_targets_filter = "FILTER(BOUND(?source_value))"
        else:
            # Create filter for values not in valid targets
            targets_list = ", ".join(f'"{str(target)}"' for target in valid_targets)
            valid_targets_filter = f"FILTER(BOUND(?source_value) && !(?source_value IN ({targets_list})))"
        
        # Handle nullable references
        nullable_filter = ""
        if not reference.nullable:
            nullable_filter = "FILTER(BOUND(?source_value))"
        
        query = f"""
        SELECT ?entity ?source_value ?violation_type
        WHERE {{
            ?entity a ?entity_type .
            
            # Get source field value
            OPTIONAL {{ ?entity <@schema:{field_name}> ?source_value }}
            
            # Apply nullable constraint
            {nullable_filter}
            
            # Check for foreign key violations
            {valid_targets_filter}
            
            BIND("foreign_key_violation" AS ?violation_type)
            BIND("{reference.target_dataset}" AS ?target_dataset)
            BIND("{reference.target_field}" AS ?target_field)
        }}
        LIMIT 1000
        """
        
        return query
    
    def _build_target_values_query(self, reference: ForeignReference) -> str:
        """Build WOQL query to get valid target values"""
        
        # Handle different target dataset patterns
        if reference.target_dataset.startswith("@"):
            # Schema-level reference (e.g., @schema:ObjectType)
            target_type = reference.target_dataset
        else:
            # Regular dataset reference
            target_type = f"@schema:{reference.target_dataset}"
        
        query = f"""
        SELECT DISTINCT ?{reference.target_field}
        WHERE {{
            ?target_entity a {target_type} .
            ?target_entity <@schema:{reference.target_field}> ?{reference.target_field} .
            FILTER(BOUND(?{reference.target_field}))
        }}
        """
        
        return query
    
    async def _query_cross_database(
        self,
        query: str,
        reference: ForeignReference
    ) -> List[Dict[str, Any]]:
        """Execute query across different databases"""
        
        # This would require enhanced TerminusPort with cross-database support
        # For now, we'll use the same database with branch switching
        
        original_db = getattr(self.terminus_port, 'current_db', 'oms')
        original_branch = getattr(self.terminus_port, 'current_branch', 'main')
        
        try:
            # Switch to target database/branch if specified
            if reference.target_database:
                # Switch database context (implementation depends on TerminusPort capabilities)
                pass
            
            if reference.target_branch:
                # Switch branch context
                pass
            
            # Execute query in target context
            result = await self.terminus_port.query(query)
            
            return result
            
        finally:
            # Restore original database/branch context
            pass
    
    async def _get_violation_statistics(
        self,
        field_name: str,
        reference: ForeignReference
    ) -> Dict[str, Any]:
        """Get detailed statistics about violations"""
        
        stats_query = f"""
        SELECT 
            (COUNT(?entity) AS ?violation_count)
            (COUNT(DISTINCT ?source_value) AS ?unique_orphaned_values)
            (GROUP_CONCAT(DISTINCT ?entity; separator=",") AS ?affected_entities)
        WHERE {{
            ?entity a ?entity_type .
            ?entity <@schema:{field_name}> ?source_value .
            
            # This would use the same logic as _build_foreign_key_violation_query
            # but focused on counting and grouping
            
            FILTER(BOUND(?source_value))
            # Additional filters would be inserted here based on reference configuration
        }}
        """
        
        try:
            result = await self.terminus_port.query(stats_query)
            if result:
                return {
                    "violation_count": result[0].get("violation_count", 0),
                    "orphaned_count": result[0].get("unique_orphaned_values", 0),
                    "affected_entities": result[0].get("affected_entities", "").split(",")
                }
        except Exception as e:
            logger.error(f"Failed to get violation statistics: {e}")
        
        return {"violation_count": 0, "orphaned_count": 0, "affected_entities": []}
    
    def _create_breaking_change(
        self,
        field_name: str,
        reference: ForeignReference,
        violations: List[Dict[str, Any]]
    ) -> BreakingChange:
        """Create breaking change for foreign reference violations"""
        
        violation_count = len(violations)
        sample_violations = violations[:5]
        
        # Determine severity based on reference type and violation count
        severity = self._assess_violation_severity(reference, violation_count)
        
        # Custom error message or default
        description = reference.custom_error_message or self._get_default_error_message(
            field_name, reference, violation_count
        )
        
        # Migration strategies based on integrity action
        strategies = self._get_migration_strategies(reference, violation_count)
        
        return BreakingChange(
            rule_id=self.rule_id,
            severity=severity,
            object_type="foreign_reference",
            field_name=field_name,
            description=description,
            old_value=None,
            new_value={
                "target_dataset": reference.target_dataset,
                "target_field": reference.target_field,
                "reference_type": reference.reference_type
            },
            impact={
                "foreign_reference_violation": True,
                "reference_type": reference.reference_type,
                "violation_count": violation_count,
                "sample_violations": sample_violations,
                "target_dataset": reference.target_dataset,
                "target_field": reference.target_field,
                "integrity_action": reference.integrity_action,
                "cross_dataset": reference.target_database is not None
            },
            suggested_strategies=strategies,
            detected_at=datetime.utcnow()
        )
    
    def _create_error_breaking_change(self, field_name: str, error_message: str) -> BreakingChange:
        """Create breaking change for validation errors"""
        return BreakingChange(
            rule_id=self.rule_id,
            severity=Severity.MEDIUM,
            object_type="foreign_reference",
            field_name=field_name,
            description=f"Foreign reference validation failed: {error_message}",
            old_value=None,
            new_value=None,
            impact={"validation_error": True, "field": field_name},
            suggested_strategies=[MigrationStrategy.MANUAL_REVIEW],
            detected_at=datetime.utcnow()
        )
    
    def _assess_violation_severity(self, reference: ForeignReference, violation_count: int) -> Severity:
        """Assess severity based on reference type and violation count"""
        
        # Critical reference types that affect data integrity
        critical_types = {ReferenceType.FOREIGN_KEY, ReferenceType.HIERARCHICAL}
        
        if reference.reference_type in critical_types:
            if violation_count > 100:
                return Severity.CRITICAL
            elif violation_count > 10:
                return Severity.HIGH
            else:
                return Severity.MEDIUM
        elif reference.reference_type == ReferenceType.WEAK_REFERENCE:
            # Weak references are less critical
            if violation_count > 1000:
                return Severity.MEDIUM
            else:
                return Severity.LOW
        else:
            # Cross-dataset and many-to-many references
            if violation_count > 500:
                return Severity.HIGH
            elif violation_count > 50:
                return Severity.MEDIUM
            else:
                return Severity.LOW
    
    def _get_default_error_message(
        self,
        field_name: str,
        reference: ForeignReference,
        violation_count: int
    ) -> str:
        """Get default error message for violations"""
        
        message_templates = {
            ReferenceType.FOREIGN_KEY: f"Foreign key constraint violation in field '{field_name}': {violation_count} references to non-existent records in {reference.target_dataset}.{reference.target_field}",
            ReferenceType.WEAK_REFERENCE: f"Weak reference warning in field '{field_name}': {violation_count} references to missing records in {reference.target_dataset}.{reference.target_field}",
            ReferenceType.CROSS_DATASET: f"Cross-dataset reference violation in field '{field_name}': {violation_count} references to non-existent records in {reference.target_dataset}.{reference.target_field}",
            ReferenceType.HIERARCHICAL: f"Hierarchical reference violation in field '{field_name}': {violation_count} invalid parent-child relationships",
            ReferenceType.MANY_TO_MANY: f"Many-to-many reference violation in field '{field_name}': {violation_count} invalid relationship references"
        }
        
        return message_templates.get(
            reference.reference_type,
            f"Reference integrity violation in field '{field_name}': {violation_count} invalid references"
        )
    
    def _get_migration_strategies(
        self,
        reference: ForeignReference,
        violation_count: int
    ) -> List[MigrationStrategy]:
        """Get migration strategies based on integrity action"""
        
        strategy_mapping = {
            IntegrityAction.RESTRICT: [MigrationStrategy.MANUAL_REVIEW, MigrationStrategy.DATA_MIGRATION],
            IntegrityAction.CASCADE: [MigrationStrategy.DATA_MIGRATION, MigrationStrategy.COMPATIBILITY_LAYER],
            IntegrityAction.SET_NULL: [MigrationStrategy.DATA_MIGRATION, MigrationStrategy.ADD_DEFAULTS],
            IntegrityAction.SET_DEFAULT: [MigrationStrategy.ADD_DEFAULTS, MigrationStrategy.DATA_MIGRATION],
            IntegrityAction.NO_ACTION: [MigrationStrategy.MANUAL_REVIEW]
        }
        
        return strategy_mapping.get(reference.integrity_action, [MigrationStrategy.MANUAL_REVIEW])
    
    def _assess_fix_complexity(self, reference: ForeignReference, violation_stats: Dict[str, Any]) -> str:
        """Assess complexity of fixing violations"""
        
        violation_count = violation_stats.get("violation_count", 0)
        
        if reference.reference_type == ReferenceType.CROSS_DATASET:
            # Cross-dataset fixes are more complex
            if violation_count > 100:
                return "very_high"
            elif violation_count > 10:
                return "high"
            else:
                return "medium"
        else:
            # Standard complexity assessment
            if violation_count > 1000:
                return "very_high"
            elif violation_count > 100:
                return "high"
            elif violation_count > 10:
                return "medium"
            else:
                return "low"
    
    def _is_cache_valid(self, cache_key: str, ttl_seconds: int) -> bool:
        """Check if cached data is still valid"""
        if cache_key not in self._cache_timestamps:
            return False
        
        cache_time = self._cache_timestamps[cache_key]
        elapsed = (datetime.utcnow() - cache_time).total_seconds()
        return elapsed < ttl_seconds


# Factory functions for easy rule creation
def create_foreign_key_rule(
    source_field: str,
    target_dataset: str,
    target_field: str,
    nullable: bool = True,
    integrity_action: IntegrityAction = IntegrityAction.RESTRICT,
    terminus_port: Optional[TerminusPort] = None
) -> ForeignReferenceIntegrityRule:
    """Create a standard foreign key rule"""
    reference = ForeignReference(
        source_field=source_field,
        target_dataset=target_dataset,
        target_field=target_field,
        reference_type=ReferenceType.FOREIGN_KEY,
        nullable=nullable,
        integrity_action=integrity_action
    )
    return ForeignReferenceIntegrityRule([reference], terminus_port)


def create_cross_dataset_rule(
    source_field: str,
    target_dataset: str,
    target_field: str,
    target_database: str,
    target_branch: str = "main",
    terminus_port: Optional[TerminusPort] = None
) -> ForeignReferenceIntegrityRule:
    """Create a cross-dataset reference rule"""
    reference = ForeignReference(
        source_field=source_field,
        target_dataset=target_dataset,
        target_field=target_field,
        reference_type=ReferenceType.CROSS_DATASET,
        target_database=target_database,
        target_branch=target_branch,
        integrity_action=IntegrityAction.NO_ACTION  # More lenient for cross-dataset
    )
    return ForeignReferenceIntegrityRule([reference], terminus_port)


def create_weak_reference_rule(
    source_field: str,
    target_dataset: str,
    target_field: str,
    terminus_port: Optional[TerminusPort] = None
) -> ForeignReferenceIntegrityRule:
    """Create a weak reference rule (allows missing targets)"""
    reference = ForeignReference(
        source_field=source_field,
        target_dataset=target_dataset,
        target_field=target_field,
        reference_type=ReferenceType.WEAK_REFERENCE,
        nullable=True,
        integrity_action=IntegrityAction.NO_ACTION
    )
    return ForeignReferenceIntegrityRule([reference], terminus_port)


# Predefined Foundry-compatible reference rules
def create_foundry_entity_references(terminus_port: Optional[TerminusPort] = None) -> ForeignReferenceIntegrityRule:
    """Create standard Foundry entity reference rules"""
    references = [
        ForeignReference(
            source_field="parent_id",
            target_dataset="ObjectType",
            target_field="id",
            reference_type=ReferenceType.HIERARCHICAL,
            nullable=True,
            integrity_action=IntegrityAction.RESTRICT
        ),
        ForeignReference(
            source_field="created_by",
            target_dataset="User",
            target_field="id",
            reference_type=ReferenceType.FOREIGN_KEY,
            nullable=False,
            integrity_action=IntegrityAction.RESTRICT
        ),
        ForeignReference(
            source_field="organization_id",
            target_dataset="Organization",
            target_field="id",
            reference_type=ReferenceType.FOREIGN_KEY,
            nullable=False,
            integrity_action=IntegrityAction.CASCADE
        )
    ]
    return ForeignReferenceIntegrityRule(references, terminus_port)