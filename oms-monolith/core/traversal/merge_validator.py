"""
Enterprise-grade Semantic Merge Validator (DEPRECATED)

DEPRECATED: This module is deprecated in favor of core.validation.merge_validation_service
which provides better integration with the validation layer and eliminates code duplication.

Use core.validation.merge_validation_service.MergeValidationService instead.

This module remains for backward compatibility but will be removed in a future version.
"""

import asyncio
import warnings
from typing import Dict, Optional, Any, TYPE_CHECKING
from datetime import datetime

# Facade imports - delegate to validation layer
from core.validation.merge_validation_service import (
    MergeValidationService, MergeValidationResult, MergeStrategy
)
from core.validation.config import get_validation_config
from core.validation.rule_registry import RuleRegistry
from core.validation.adapters.terminus_traversal_adapter import create_terminus_traversal_adapter
from database.clients.terminus_db import TerminusDBClient

if TYPE_CHECKING:
    from core.traversal.traversal_engine import TraversalEngine
    from core.traversal.dependency_analyzer import DependencyAnalyzer
    from core.traversal.semantic_validator import SemanticValidator


# DEPRECATED: Use validation layer enums instead
# These are kept for backward compatibility only
from core.validation.merge_validation_service import MergeStrategy, MergeDecision

# Import original types for compatibility
from core.traversal.models import SemanticConflict, ConflictType

# Deprecation warning
warnings.warn(
    "core.traversal.merge_validator is deprecated. "
    "Use core.validation.merge_validation_service.MergeValidationService instead.",
    DeprecationWarning,
    stacklevel=2
)


class MergeConflictResolution:
    """DEPRECATED: Use core.validation.merge_validation_service.MergeConflictResolution"""
    def __init__(
        self,
        conflict: SemanticConflict,
        resolution_type: str,
        resolution_action: str,
        confidence: float,
        rationale: str
    ):
        self.conflict = conflict
        self.resolution_type = resolution_type
        self.resolution_action = resolution_action
        self.confidence = confidence
        self.rationale = rationale


class MergeValidationResult:
    """DEPRECATED: Use core.validation.merge_validation_service.MergeValidationResult"""
    def __init__(self):
        self.can_auto_merge: bool = False
        self.merge_decision = MergeDecision.MANUAL_RESOLUTION
        self.conflicts = []
        self.resolutions = []
        self.impact_analysis: Dict[str, Any] = {}
        self.recommended_strategy = MergeStrategy.THREE_WAY
        self.validation_timestamp: datetime = datetime.utcnow()
        self.estimated_merge_time: float = 0.0
        self.risk_assessment: Dict[str, str] = {}


class EnterpriseSemanticMergeValidator:
    """
    DEPRECATED Thin Facade for Enterprise Semantic Merge Validation
    
    This class is DEPRECATED and serves only as a thin facade to maintain
    backward compatibility. All functionality has been moved to:
    core.validation.merge_validation_service.MergeValidationService
    
    Please update your code to use the new validation layer service directly.
    """
    
    def __init__(
        self,
        traversal_engine: "TraversalEngine",
        dependency_analyzer: "DependencyAnalyzer",
        semantic_validator: "SemanticValidator",
        terminus_client: TerminusDBClient,
        config_manager = None  # Ignored - using ValidationConfig
    ):
        warnings.warn(
            "EnterpriseSemanticMergeValidator is deprecated. "
            "Use core.validation.merge_validation_service.MergeValidationService instead.",
            DeprecationWarning,
            stacklevel=2
        )
        
        # Store for facade delegation
        self.client = terminus_client
        self.config = get_validation_config()
        self._merge_service: Optional[MergeValidationService] = None
        
    async def validate_merge(
        self,
        source_branch: str,
        target_branch: str,
        base_branch: Optional[str] = None,
        strategy = MergeStrategy.THREE_WAY
    ) -> MergeValidationResult:
        """
        DEPRECATED: Facade method that delegates to the new validation layer service.
        
        This method maintains backward compatibility by delegating all functionality
        to core.validation.merge_validation_service.MergeValidationService.
        """
        warnings.warn(
            "validate_merge method is deprecated. "
            "Use core.validation.merge_validation_service.MergeValidationService.validate_merge instead.",
            DeprecationWarning,
            stacklevel=2
        )
        
        try:
            # Lazy initialization of the new service
            if self._merge_service is None:
                rule_registry = RuleRegistry()
                terminus_adapter = await create_terminus_traversal_adapter(
                    terminus_client=self.client,
                    database_name=self.config.terminus_default_db
                )
                
                self._merge_service = MergeValidationService(
                    rule_registry=rule_registry,
                    terminus_port=terminus_adapter,
                    config=self.config
                )
            
            # Delegate to new service
            new_result = await self._merge_service.validate_merge(
                source_branch=source_branch,
                target_branch=target_branch,
                base_branch=base_branch,
                strategy=strategy
            )
            
            # Convert new result to old format for backward compatibility
            old_result = MergeValidationResult()
            old_result.can_auto_merge = new_result.can_auto_merge
            old_result.merge_decision = new_result.merge_decision
            old_result.conflicts = self._convert_breaking_changes_to_conflicts(new_result.conflicts)
            old_result.resolutions = self._convert_resolutions(new_result.resolutions)
            old_result.impact_analysis = new_result.impact_analysis
            old_result.recommended_strategy = new_result.recommended_strategy
            old_result.validation_timestamp = new_result.validation_timestamp
            old_result.estimated_merge_time = new_result.estimated_merge_time
            old_result.risk_assessment = new_result.risk_assessment
            
            return old_result
            
        except Exception as e:
            raise RuntimeError(f"Merge validation failed: {e}")
    
    def _convert_breaking_changes_to_conflicts(self, breaking_changes) -> list:
        """Convert BreakingChange objects to SemanticConflict for compatibility"""
        conflicts = []
        for bc in breaking_changes:
            # Map BreakingChange to SemanticConflict
            conflict_type = ConflictType.TYPE_MISMATCH  # Default mapping
            if "circular" in bc.rule_id.lower():
                conflict_type = ConflictType.CIRCULAR_DEPENDENCY
            elif "orphan" in bc.rule_id.lower():
                conflict_type = ConflictType.ORPHANED_NODE
            elif "cardinality" in bc.rule_id.lower():
                conflict_type = ConflictType.CARDINALITY_VIOLATION
            elif "reference" in bc.rule_id.lower():
                conflict_type = ConflictType.DANGLING_REFERENCE
            
            conflict = SemanticConflict(
                conflict_type=conflict_type,
                severity=bc.severity.value,
                affected_nodes=[bc.field_name] if bc.field_name else [],
                description=bc.description,
                suggested_resolution=f"Apply {bc.suggested_strategies[0].value}" if bc.suggested_strategies else "Manual review required",
                impact_scope=list(bc.impact.keys()) if isinstance(bc.impact, dict) else [str(bc.impact)]
            )
            conflicts.append(conflict)
        
        return conflicts
    
    def _convert_resolutions(self, new_resolutions) -> list:
        """Convert new resolution format to old format"""
        old_resolutions = []
        for res in new_resolutions:
            # Create a dummy SemanticConflict for the old resolution format
            dummy_conflict = SemanticConflict(
                conflict_type=ConflictType.TYPE_MISMATCH,
                severity="medium",
                affected_nodes=[],
                description=f"Converted from rule_id: {res.conflict.rule_id}",
                suggested_resolution=res.resolution_action,
                impact_scope=[]
            )
            
            old_resolution = MergeConflictResolution(
                conflict=dummy_conflict,
                resolution_type=res.resolution_type,
                resolution_action=res.resolution_action,
                confidence=res.confidence,
                rationale=res.rationale
            )
            old_resolutions.append(old_resolution)
        
        return old_resolutions
    
    def _detect_structural_conflicts(self, source_branch: str, target_branch: str, base_branch: str):
        """DEPRECATED: This method is no longer used. All conflict detection is handled by the validation layer."""
        warnings.warn(
            "_detect_structural_conflicts is deprecated and no longer functional. "
            "Use MergeValidationService instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return []
    
    def _get_branch_entities(self, branch: str):
        """DEPRECATED: This method is no longer used."""
        warnings.warn(
            "_get_branch_entities is deprecated. Use TerminusTraversalAdapter instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return []
    
    def _validate_semantic_consistency(
        self,
        source_branch: str,
        target_branch: str,
        base_branch: str
    ) -> List[SemanticConflict]:
        """DEPRECATED: This method is no longer used. All validation is handled by the validation layer."""
        warnings.warn(
            "_validate_semantic_consistency is deprecated and no longer functional. "
            "Use MergeValidationService instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return []
    
    def _detect_merge_semantic_conflicts(
        self,
        source_branch: str,
        target_branch: str,
        base_branch: str
    ) -> List[SemanticConflict]:
        """DEPRECATED: This method is no longer used. All conflict detection is handled by the validation layer."""
        warnings.warn(
            "_detect_merge_semantic_conflicts is deprecated and no longer functional. "
            "Use MergeValidationService instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return []
    
    def _analyze_dependency_impacts(
        self,
        source_branch: str,
        target_branch: str,
        base_branch: str
    ) -> List[SemanticConflict]:
        """DEPRECATED: This method is no longer used. All impact analysis is handled by the validation layer."""
        warnings.warn(
            "_analyze_dependency_impacts is deprecated and no longer functional. "
            "Use MergeValidationService instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return []
    
    def _validate_business_rules(
        self,
        source_branch: str,
        target_branch: str,
        base_branch: str
    ) -> List[SemanticConflict]:
        """DEPRECATED: This method is no longer used. All business rule validation is handled by the validation layer."""
        warnings.warn(
            "_validate_business_rules is deprecated and no longer functional. "
            "Use MergeValidationService instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return []
    
    def _generate_resolutions(
        self, 
        conflicts: List[SemanticConflict]
    ) -> List[MergeConflictResolution]:
        """DEPRECATED: This method is no longer used. All resolution generation is handled by the validation layer."""
        warnings.warn(
            "_generate_resolutions is deprecated and no longer functional. "
            "Use MergeValidationService instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return []
    
    def _determine_merge_decision(
        self,
        conflicts: List[SemanticConflict],
        resolutions: List[MergeConflictResolution]
    ) -> MergeDecision:
        """DEPRECATED: This method is no longer used. All merge decision logic is handled by the validation layer."""
        warnings.warn(
            "_determine_merge_decision is deprecated and no longer functional. "
            "Use MergeValidationService instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return MergeDecision.MANUAL_RESOLUTION
    
    def _comprehensive_impact_analysis(
        self,
        source_branch: str,
        target_branch: str,
        conflicts: List[SemanticConflict]
    ) -> Dict[str, Any]:
        """DEPRECATED: This method is no longer used. All impact analysis is handled by the validation layer."""
        warnings.warn(
            "_comprehensive_impact_analysis is deprecated and no longer functional. "
            "Use MergeValidationService instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return {"total_affected_entities": 0, "conflicts_by_severity": {}, "msa_services_affected": []}
    
    def _assess_merge_risks(
        self,
        conflicts: List[SemanticConflict],
        impact_analysis: Dict[str, Any]
    ) -> Dict[str, str]:
        """DEPRECATED: This method is no longer used. All risk assessment is handled by the validation layer."""
        warnings.warn(
            "_assess_merge_risks is deprecated and no longer functional. "
            "Use MergeValidationService instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return {"data_integrity": "low", "performance": "low", "business_continuity": "low"}
    
    def _get_branch_changes(self, branch: str, base_branch: str) -> Set[str]:
        """DEPRECATED: This method is no longer used. Use TerminusTraversalAdapter instead."""
        warnings.warn(
            "_get_branch_changes is deprecated. Use TerminusTraversalAdapter instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return set()
    
    def _analyze_msa_service_impact(self, affected_entities: List[str]) -> List[str]:
        """DEPRECATED: This method is no longer used. MSA impact analysis is handled by the validation layer."""
        warnings.warn(
            "_analyze_msa_service_impact is deprecated. Use MergeValidationService instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return []
    
    def _estimate_resolution_time(self, conflicts: List[SemanticConflict]) -> float:
        """DEPRECATED: This method is no longer used. Time estimation is handled by the validation layer."""
        warnings.warn(
            "_estimate_resolution_time is deprecated. Use MergeValidationService instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return 30.0
    
    def _generate_testing_requirements(self, conflicts: List[SemanticConflict]) -> List[str]:
        """DEPRECATED: This method is no longer used. Testing requirements are handled by the validation layer."""
        warnings.warn(
            "_generate_testing_requirements is deprecated. Use MergeValidationService instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return ["Unit tests for affected entities"]
    
    def _deduplicate_conflicts(self, conflicts: List[SemanticConflict]) -> List[SemanticConflict]:
        """DEPRECATED: This method is no longer used. Conflict deduplication is handled by the validation layer."""
        warnings.warn(
            "_deduplicate_conflicts is deprecated. Use MergeValidationService instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return []
    
    def _initialize_conflict_resolvers(self) -> Dict[ConflictType, callable]:
        """DEPRECATED: This method is no longer used. Conflict resolution is handled by the validation layer."""
        warnings.warn(
            "_initialize_conflict_resolvers is deprecated. Use MergeValidationService instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return {}
    
    def _resolve_type_mismatch(self, conflict: SemanticConflict) -> MergeConflictResolution:
        """DEPRECATED: This method is no longer used. Conflict resolution is handled by the validation layer."""
        warnings.warn(
            "_resolve_type_mismatch is deprecated. Use MergeValidationService instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return MergeConflictResolution(
            conflict=conflict,
            resolution_type="deprecated",
            resolution_action="Use MergeValidationService",
            confidence=0.0,
            rationale="Method is deprecated"
        )
    
    def _resolve_circular_dependency(self, conflict: SemanticConflict) -> MergeConflictResolution:
        """DEPRECATED: This method is no longer used. Conflict resolution is handled by the validation layer."""
        warnings.warn(
            "_resolve_circular_dependency is deprecated. Use MergeValidationService instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return MergeConflictResolution(
            conflict=conflict,
            resolution_type="deprecated",
            resolution_action="Use MergeValidationService",
            confidence=0.0,
            rationale="Method is deprecated"
        )
    
    def _resolve_dangling_reference(self, conflict: SemanticConflict) -> MergeConflictResolution:
        """DEPRECATED: This method is no longer used. Conflict resolution is handled by the validation layer."""
        warnings.warn(
            "_resolve_dangling_reference is deprecated. Use MergeValidationService instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return MergeConflictResolution(
            conflict=conflict,
            resolution_type="deprecated",
            resolution_action="Use MergeValidationService",
            confidence=0.0,
            rationale="Method is deprecated"
        )
    
    def _resolve_cardinality_violation(self, conflict: SemanticConflict) -> MergeConflictResolution:
        """DEPRECATED: This method is no longer used. Conflict resolution is handled by the validation layer."""
        warnings.warn(
            "_resolve_cardinality_violation is deprecated. Use MergeValidationService instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return MergeConflictResolution(
            conflict=conflict,
            resolution_type="deprecated",
            resolution_action="Use MergeValidationService",
            confidence=0.0,
            rationale="Method is deprecated"
        )
    
    def _resolve_orphaned_node(self, conflict: SemanticConflict) -> MergeConflictResolution:
        """DEPRECATED: This method is no longer used. Conflict resolution is handled by the validation layer."""
        warnings.warn(
            "_resolve_orphaned_node is deprecated. Use MergeValidationService instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return MergeConflictResolution(
            conflict=conflict,
            resolution_type="deprecated",
            resolution_action="Use MergeValidationService",
            confidence=0.0,
            rationale="Method is deprecated"
        )