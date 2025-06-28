"""
TerminusDB Boundary Definition

Defines clear boundaries between TerminusDB native capabilities and custom validation layers.
This module establishes the integration strategy and prevents duplication of functionality.

Architecture Decision Record (ADR):
- TerminusDB provides native validation → Our layer adds business context
- TerminusDB provides diff/merge → Our layer adds policy enforcement  
- TerminusDB provides path queries → Our layer adds semantic analysis
- TerminusDB provides ACL → Our PolicyServer adds enterprise governance
"""

import logging
from typing import Dict, Any, List, Optional, Protocol
from enum import Enum
from dataclasses import dataclass

from core.validation.config import get_validation_config

logger = logging.getLogger(__name__)


class TerminusFeature(str, Enum):
    """TerminusDB native features that we integrate with"""
    SCHEMA_VALIDATION = "schema_validation"
    BRANCH_DIFF = "branch_diff"  
    MERGE_CONFLICTS = "merge_conflicts"
    PATH_QUERIES = "path_queries"
    TRANSITIVE_CLOSURE = "transitive_closure"
    ACL_SYSTEM = "acl_system"
    TRANSACTION_ISOLATION = "transaction_isolation"
    QUERY_OPTIMIZATION = "query_optimization"


class IntegrationStrategy(str, Enum):
    """How we integrate with each TerminusDB feature"""
    DELEGATE = "delegate"           # Use TerminusDB directly, minimal wrapper
    ENHANCE = "enhance"             # Use TerminusDB + add business logic
    SIMULATE = "simulate"           # Test with TerminusDB, apply our rules
    COORDINATE = "coordinate"       # Run in parallel with coordination
    OVERRIDE = "override"          # Replace with our implementation


@dataclass  
class BoundaryDefinition:
    """Defines how we interact with a specific TerminusDB feature"""
    terminus_feature: TerminusFeature
    strategy: IntegrationStrategy
    our_layer_responsibility: str
    terminus_responsibility: str
    integration_points: List[str]
    conflict_resolution: str
    performance_notes: str


class TerminusBoundaryManager:
    """
    Manages boundaries between TerminusDB and our validation layers.
    
    Ensures clear separation of concerns and prevents duplicate functionality.
    """
    
    def __init__(self):
        self.config = get_validation_config()
        self.boundaries = self._define_boundaries()
    
    def _define_boundaries(self) -> Dict[TerminusFeature, BoundaryDefinition]:
        """Define clear boundaries for each TerminusDB feature"""
        return {
            # Schema Validation: TerminusDB validates structure, we add business context
            TerminusFeature.SCHEMA_VALIDATION: BoundaryDefinition(
                terminus_feature=TerminusFeature.SCHEMA_VALIDATION,
                strategy=IntegrationStrategy.ENHANCE,
                our_layer_responsibility=(
                    "Business rule validation, policy enforcement, "
                    "migration planning, impact analysis, error translation"
                ),
                terminus_responsibility=(
                    "Basic schema constraint validation (types, cardinality, "
                    "domain/range), referential integrity, ACID compliance"
                ),
                integration_points=[
                    "validation_pipeline.py: TERMINUS_CHECK stage",
                    "terminus_error_handler.py: Error translation",
                    "rule_registry.py: Business rules after schema validation"
                ],
                conflict_resolution=(
                    "TerminusDB validation runs first as 'pre-filter'. "
                    "If TerminusDB rejects, we don't proceed to business rules. "
                    "If TerminusDB accepts, we apply additional business validation."
                ),
                performance_notes=(
                    "TerminusDB validation is fast (native C++). "
                    "Our business rules add ~10-50ms depending on complexity."
                )
            ),
            
            # Branch Diff: TerminusDB provides raw diff, we analyze business impact  
            TerminusFeature.BRANCH_DIFF: BoundaryDefinition(
                terminus_feature=TerminusFeature.BRANCH_DIFF,
                strategy=IntegrationStrategy.ENHANCE,
                our_layer_responsibility=(
                    "Business impact analysis, breaking change detection, "
                    "migration strategy recommendation, stakeholder notification"
                ),
                terminus_responsibility=(
                    "Raw entity-level differences between branches, "
                    "structural change detection, commit history"
                ),
                integration_points=[
                    "ports.py: get_branch_diff()",
                    "merge_validation_service.py: Impact analysis",
                    "adapters/terminus_traversal_adapter.py: Diff wrapper"
                ],
                conflict_resolution=(
                    "No conflict - complementary responsibilities. "
                    "TerminusDB provides data, we analyze business meaning."
                ),
                performance_notes=(
                    "TerminusDB diff is O(log n) with Git-like efficiency. "
                    "Our analysis is O(entities_changed * rules_count)."
                )
            ),
            
            # Merge Conflicts: TerminusDB detects structural conflicts, we handle semantic conflicts
            TerminusFeature.MERGE_CONFLICTS: BoundaryDefinition(
                terminus_feature=TerminusFeature.MERGE_CONFLICTS,
                strategy=IntegrationStrategy.COORDINATE,
                our_layer_responsibility=(
                    "Semantic conflict detection, business rule conflicts, "
                    "resolution strategy recommendation, approval workflows"
                ),
                terminus_responsibility=(
                    "Structural merge conflicts (same entity modified in both branches), "
                    "three-way merge resolution, conflict markers"
                ),
                integration_points=[
                    "merge_validation_service.py: Full merge validation",
                    "traversal/merge_validator.py: DEPRECATED facade", 
                    "ports.py: detect_merge_conflicts()"
                ],
                conflict_resolution=(
                    "Sequential processing: TerminusDB structural conflicts first, "
                    "then our semantic conflicts. Both must be resolved for merge."
                ),
                performance_notes=(
                    "TerminusDB merge detection: ~50-200ms per branch. "
                    "Our semantic analysis: ~100-500ms depending on rule complexity."
                )
            ),
            
            # Path Queries: TerminusDB provides graph traversal, we add business semantics
            TerminusFeature.PATH_QUERIES: BoundaryDefinition(
                terminus_feature=TerminusFeature.PATH_QUERIES,
                strategy=IntegrationStrategy.ENHANCE,
                our_layer_responsibility=(
                    "Business relationship semantics, dependency policy enforcement, "
                    "critical path identification, impact propagation analysis"
                ),
                terminus_responsibility=(
                    "Efficient graph traversal with path() queries, "
                    "transitive closure computation, cycle detection"
                ),
                integration_points=[
                    "traversal_engine.py: WOQL path query construction",
                    "dependency_analyzer.py: Business logic on traversal results",
                    "validation rules: Dependency validation"
                ],
                conflict_resolution=(
                    "No conflict - layered approach. TerminusDB provides efficient traversal, "
                    "we interpret results according to business rules."
                ),
                performance_notes=(
                    "TerminusDB path queries: O(V + E) with native optimization. "
                    "Our analysis: O(results * business_rules)."
                )
            ),
            
            # ACL System: TerminusDB provides database-level access, PolicyServer provides business governance
            TerminusFeature.ACL_SYSTEM: BoundaryDefinition(
                terminus_feature=TerminusFeature.ACL_SYSTEM,
                strategy=IntegrationStrategy.COORDINATE,
                our_layer_responsibility=(
                    "Business-level authorization, role-based policies, "
                    "approval workflows, audit logging, enterprise governance"
                ),
                terminus_responsibility=(
                    "Database-level access control, user authentication, "
                    "branch-level permissions, query-level security"
                ),
                integration_points=[
                    "policy_server_port.py: Enterprise policy validation",
                    "pipeline.py: POLICY stage before TerminusDB",
                    "middleware/auth_msa.py: MSA authentication integration"
                ],
                conflict_resolution=(
                    "Policy hierarchy: PolicyServer (business) → TerminusDB (technical). "
                    "Both must approve for operation to proceed. PolicyServer can be more restrictive."
                ),
                performance_notes=(
                    "TerminusDB ACL: ~1-5ms per operation. "
                    "PolicyServer: ~10-50ms for complex business rules."
                )
            )
        }
    
    def get_boundary(self, feature: TerminusFeature) -> Optional[BoundaryDefinition]:
        """Get boundary definition for a specific TerminusDB feature"""
        return self.boundaries.get(feature)
    
    def validate_integration(self, feature: TerminusFeature, operation: str) -> Dict[str, Any]:
        """
        Validate that an operation follows the defined boundary correctly.
        
        Returns validation result with recommendations.
        """
        boundary = self.get_boundary(feature)
        if not boundary:
            return {
                "valid": False,
                "error": f"No boundary defined for feature: {feature}",
                "recommendations": ["Define boundary for this TerminusDB feature"]
            }
        
        # Basic validation - in practice would analyze the actual operation
        recommendations = []
        
        if boundary.strategy == IntegrationStrategy.DELEGATE:
            recommendations.append(
                f"Ensure minimal wrapper around TerminusDB {feature.value}"
            )
        elif boundary.strategy == IntegrationStrategy.ENHANCE:
            recommendations.append(
                f"Use TerminusDB {feature.value} as foundation, add business logic"
            )
        elif boundary.strategy == IntegrationStrategy.COORDINATE:
            recommendations.append(
                f"Coordinate with TerminusDB {feature.value}, resolve conflicts per policy"
            )
        
        return {
            "valid": True,
            "strategy": boundary.strategy,
            "our_responsibility": boundary.our_layer_responsibility,
            "terminus_responsibility": boundary.terminus_responsibility,
            "recommendations": recommendations,
            "performance_notes": boundary.performance_notes
        }
    
    def get_integration_summary(self) -> Dict[str, Any]:
        """Get complete summary of all TerminusDB integrations"""
        summary = {
            "total_features": len(self.boundaries),
            "strategies": {},
            "integration_points": [],
            "performance_characteristics": {}
        }
        
        for feature, boundary in self.boundaries.items():
            # Count strategies
            strategy = boundary.strategy
            if strategy not in summary["strategies"]:
                summary["strategies"][strategy] = []
            summary["strategies"][strategy].append(feature.value)
            
            # Collect integration points
            summary["integration_points"].extend(boundary.integration_points)
            
            # Performance info
            summary["performance_characteristics"][feature.value] = boundary.performance_notes
        
        # Deduplicate integration points
        summary["integration_points"] = list(set(summary["integration_points"]))
        
        return summary
    
    def generate_boundary_documentation(self) -> str:
        """Generate documentation for all boundary definitions"""
        doc = [
            "# TerminusDB Integration Boundary Documentation",
            "",
            "This document defines how the OMS Validation system integrates with TerminusDB native features.",
            "",
            "## Integration Principles",
            "",
            "1. **No Duplication**: Never replicate TerminusDB native functionality",
            "2. **Clear Responsibility**: Each layer has distinct responsibilities", 
            "3. **Performance Aware**: Use TerminusDB strengths, add value efficiently",
            "4. **Conflict Resolution**: Clear precedence and coordination rules",
            "",
            "## Feature Boundaries",
            ""
        ]
        
        for feature, boundary in self.boundaries.items():
            doc.extend([
                f"### {feature.value.replace('_', ' ').title()}",
                "",
                f"**Strategy**: {boundary.strategy.value}",
                "",
                f"**TerminusDB Responsibility**:",
                f"{boundary.terminus_responsibility}",
                "",
                f"**Our Layer Responsibility**:",
                f"{boundary.our_layer_responsibility}",
                "",
                f"**Integration Points**:",
            ])
            
            for point in boundary.integration_points:
                doc.append(f"- {point}")
            
            doc.extend([
                "",
                f"**Conflict Resolution**:",
                f"{boundary.conflict_resolution}",
                "",
                f"**Performance Notes**:",
                f"{boundary.performance_notes}",
                "",
                "---",
                ""
            ])
        
        return "\n".join(doc)


# Global boundary manager instance
_boundary_manager: Optional[TerminusBoundaryManager] = None


def get_boundary_manager() -> TerminusBoundaryManager:
    """Get singleton boundary manager instance"""
    global _boundary_manager
    if _boundary_manager is None:
        _boundary_manager = TerminusBoundaryManager()
    return _boundary_manager


def validate_terminus_integration(feature: TerminusFeature, operation: str) -> Dict[str, Any]:
    """Convenience function to validate TerminusDB integration"""
    return get_boundary_manager().validate_integration(feature, operation)


# Export key components
__all__ = [
    "TerminusFeature",
    "IntegrationStrategy", 
    "BoundaryDefinition",
    "TerminusBoundaryManager",
    "get_boundary_manager",
    "validate_terminus_integration"
]