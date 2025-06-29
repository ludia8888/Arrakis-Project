"""
Consolidated Merge Validation Business Rules

Contains only the business logic that cannot be replaced by TerminusDB:
- Conflict resolution strategies
- Impact analysis
- Risk assessment
- Semantic consistency checks

All structural validation is delegated to TerminusDB's native capabilities.
"""

import logging
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class MergeDecision(str, Enum):
    """Merge decision outcomes based on business rules"""
    AUTO_MERGE = "auto_merge"
    MANUAL_RESOLUTION = "manual_resolution" 
    REJECT_MERGE = "reject_merge"
    DEFER_MERGE = "defer_merge"


class MergeStrategy(str, Enum):
    """Merge strategy options"""
    FAST_FORWARD = "fast_forward"
    THREE_WAY = "three_way"
    SQUASH = "squash"
    REBASE = "rebase"


class Severity(str, Enum):
    """Conflict severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ConflictType(str, Enum):
    """Types of merge conflicts"""
    TYPE_MISMATCH = "type_mismatch"
    CIRCULAR_DEPENDENCY = "circular_dependency"
    ORPHANED_NODE = "orphaned_node"
    CARDINALITY_VIOLATION = "cardinality_violation"
    DANGLING_REFERENCE = "dangling_reference"
    BUSINESS_RULE_VIOLATION = "business_rule_violation"
    MERGE_CONFLICT = "merge_conflict"


@dataclass
class MergeConflict:
    """Represents a merge conflict detected by business rules"""
    conflict_type: ConflictType
    severity: Severity
    affected_entities: List[str]
    description: str
    source_branch: str
    target_branch: str
    detected_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ConflictResolution:
    """Resolution strategy for a specific merge conflict"""
    conflict: MergeConflict
    resolution_type: str
    resolution_action: str
    confidence: float
    rationale: str
    automated: bool = False


@dataclass
class MergeValidationResult:
    """Result of merge validation containing business logic decisions"""
    can_auto_merge: bool = False
    merge_decision: MergeDecision = MergeDecision.MANUAL_RESOLUTION
    conflicts: List[MergeConflict] = field(default_factory=list)
    resolutions: List[ConflictResolution] = field(default_factory=list)
    impact_analysis: Dict[str, Any] = field(default_factory=dict)
    risk_assessment: Dict[str, str] = field(default_factory=dict)
    recommended_strategy: MergeStrategy = MergeStrategy.THREE_WAY
    validation_timestamp: datetime = field(default_factory=datetime.utcnow)
    estimated_resolution_time: float = 0.0


class MergeValidationBusinessRules:
    """
    Business rule validation for merge operations.
    
    This class contains only the logic that cannot be handled by TerminusDB:
    - Complex conflict resolution strategies
    - Business impact analysis
    - Risk assessment based on organizational policies
    - Semantic consistency checks beyond structural validation
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.auto_resolve_threshold = self.config.get('auto_resolve_threshold', 0.8)
        self.max_auto_merge_conflicts = self.config.get('max_auto_merge_conflicts', 5)
        self.critical_entity_patterns = self.config.get('critical_entities', [
            'billing', 'payment', 'invoice', 'customer', 'order'
        ])
        
    def apply_business_rules(
        self,
        structural_conflicts: List[Dict[str, Any]],
        source_branch: str,
        target_branch: str,
        branch_metadata: Optional[Dict[str, Any]] = None
    ) -> MergeValidationResult:
        """
        Apply business rules to structural conflicts detected by TerminusDB.
        
        Args:
            structural_conflicts: Conflicts detected by TerminusDB structural validation
            source_branch: Source branch name
            target_branch: Target branch name
            branch_metadata: Additional metadata about branches
            
        Returns:
            MergeValidationResult with business decisions
        """
        result = MergeValidationResult()
        
        # Convert structural conflicts to business conflicts
        business_conflicts = self._analyze_business_impact(
            structural_conflicts, source_branch, target_branch
        )
        result.conflicts = business_conflicts
        
        # Generate resolution strategies based on business rules
        result.resolutions = self._generate_resolution_strategies(business_conflicts)
        
        # Perform comprehensive impact analysis
        result.impact_analysis = self._comprehensive_impact_analysis(
            business_conflicts, branch_metadata
        )
        
        # Assess risks based on business policies
        result.risk_assessment = self._assess_business_risks(
            business_conflicts, result.impact_analysis
        )
        
        # Make merge decision based on business rules
        result.merge_decision = self._determine_merge_decision(
            business_conflicts, result.resolutions, result.risk_assessment
        )
        result.can_auto_merge = (result.merge_decision == MergeDecision.AUTO_MERGE)
        
        # Estimate resolution time based on historical data
        result.estimated_resolution_time = self._estimate_resolution_time(
            business_conflicts, result.resolutions
        )
        
        return result
    
    def _analyze_business_impact(
        self,
        structural_conflicts: List[Dict[str, Any]],
        source_branch: str,
        target_branch: str
    ) -> List[MergeConflict]:
        """Convert structural conflicts to business-aware conflicts"""
        business_conflicts = []
        
        for conflict in structural_conflicts:
            # Determine business severity based on affected entities
            severity = self._determine_business_severity(conflict)
            
            # Check if conflict violates business rules
            conflict_type = self._categorize_business_conflict(conflict)
            
            business_conflict = MergeConflict(
                conflict_type=conflict_type,
                severity=severity,
                affected_entities=conflict.get('affected_entities', []),
                description=self._enhance_conflict_description(conflict),
                source_branch=source_branch,
                target_branch=target_branch
            )
            
            business_conflicts.append(business_conflict)
        
        return business_conflicts
    
    def _determine_business_severity(self, conflict: Dict[str, Any]) -> Severity:
        """Determine severity based on business impact"""
        affected_entities = conflict.get('affected_entities', [])
        
        # Check if any critical entities are affected
        for entity in affected_entities:
            entity_lower = entity.lower()
            if any(pattern in entity_lower for pattern in self.critical_entity_patterns):
                return Severity.CRITICAL
        
        # Check conflict type
        conflict_type = conflict.get('type', '')
        if conflict_type in ['data_loss', 'circular_dependency']:
            return Severity.HIGH
        elif conflict_type in ['type_mismatch', 'cardinality_violation']:
            return Severity.MEDIUM
        
        return Severity.LOW
    
    def _categorize_business_conflict(self, conflict: Dict[str, Any]) -> ConflictType:
        """Categorize conflict based on business rules"""
        conflict_type = conflict.get('type', '')
        
        # Map structural conflicts to business conflict types
        if 'circular' in conflict_type.lower():
            return ConflictType.CIRCULAR_DEPENDENCY
        elif 'orphan' in conflict_type.lower():
            return ConflictType.ORPHANED_NODE
        elif 'cardinality' in conflict_type.lower():
            return ConflictType.CARDINALITY_VIOLATION
        elif 'reference' in conflict_type.lower():
            return ConflictType.DANGLING_REFERENCE
        elif self._is_business_rule_violation(conflict):
            return ConflictType.BUSINESS_RULE_VIOLATION
        elif 'merge' in conflict_type.lower():
            return ConflictType.MERGE_CONFLICT
        
        return ConflictType.TYPE_MISMATCH
    
    def _is_business_rule_violation(self, conflict: Dict[str, Any]) -> bool:
        """Check if conflict violates specific business rules"""
        # Example business rules
        affected_entities = conflict.get('affected_entities', [])
        
        # Rule: Billing entities cannot have conflicting states
        billing_entities = [e for e in affected_entities if 'billing' in e.lower()]
        if billing_entities and conflict.get('type') == 'state_conflict':
            return True
        
        # Rule: Customer data must maintain referential integrity
        customer_entities = [e for e in affected_entities if 'customer' in e.lower()]
        if customer_entities and conflict.get('type') in ['dangling_reference', 'orphaned_node']:
            return True
        
        return False
    
    def _enhance_conflict_description(self, conflict: Dict[str, Any]) -> str:
        """Enhance conflict description with business context"""
        base_description = conflict.get('description', 'Conflict detected')
        
        # Add business context
        affected_entities = conflict.get('affected_entities', [])
        critical_entities = [
            e for e in affected_entities 
            if any(p in e.lower() for p in self.critical_entity_patterns)
        ]
        
        if critical_entities:
            return f"{base_description} - CRITICAL: Affects {', '.join(critical_entities)}"
        
        return base_description
    
    def _generate_resolution_strategies(
        self, 
        conflicts: List[MergeConflict]
    ) -> List[ConflictResolution]:
        """Generate resolution strategies based on business rules"""
        resolutions = []
        
        for conflict in conflicts:
            resolution = self._create_resolution_strategy(conflict)
            resolutions.append(resolution)
        
        return resolutions
    
    def _create_resolution_strategy(self, conflict: MergeConflict) -> ConflictResolution:
        """Create resolution strategy for a specific conflict"""
        
        # Critical conflicts require manual review
        if conflict.severity == Severity.CRITICAL:
            return ConflictResolution(
                conflict=conflict,
                resolution_type="manual",
                resolution_action="Requires manual review by senior developer or architect",
                confidence=0.1,
                rationale="Critical business entities require careful manual analysis",
                automated=False
            )
        
        # High severity conflicts may have semi-automated resolution
        elif conflict.severity == Severity.HIGH:
            if conflict.conflict_type == ConflictType.CIRCULAR_DEPENDENCY:
                return ConflictResolution(
                    conflict=conflict,
                    resolution_type="semi_automatic",
                    resolution_action="Break circular dependency by extracting shared interface",
                    confidence=0.6,
                    rationale="Circular dependencies can be resolved through refactoring",
                    automated=False
                )
            else:
                return ConflictResolution(
                    conflict=conflict,
                    resolution_type="semi_automatic",
                    resolution_action="Apply migration strategy with validation",
                    confidence=0.5,
                    rationale="High severity conflicts need validation after resolution",
                    automated=False
                )
        
        # Medium severity conflicts can often be automated
        elif conflict.severity == Severity.MEDIUM:
            if conflict.conflict_type == ConflictType.TYPE_MISMATCH:
                return ConflictResolution(
                    conflict=conflict,
                    resolution_type="automatic",
                    resolution_action="Apply type coercion with compatibility check",
                    confidence=0.8,
                    rationale="Type mismatches can be resolved with proper coercion",
                    automated=True
                )
            else:
                return ConflictResolution(
                    conflict=conflict,
                    resolution_type="automatic",
                    resolution_action="Apply default resolution strategy",
                    confidence=0.7,
                    rationale="Medium severity conflicts have established patterns",
                    automated=True
                )
        
        # Low severity conflicts are automatically resolved
        else:
            return ConflictResolution(
                conflict=conflict,
                resolution_type="automatic",
                resolution_action="Auto-resolve with backward compatibility",
                confidence=0.9,
                rationale="Low severity conflicts can be safely auto-resolved",
                automated=True
            )
    
    def _comprehensive_impact_analysis(
        self,
        conflicts: List[MergeConflict],
        branch_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Analyze comprehensive business impact of conflicts"""
        
        # Count affected critical entities
        all_affected = set()
        critical_affected = set()
        
        for conflict in conflicts:
            all_affected.update(conflict.affected_entities)
            critical_affected.update([
                e for e in conflict.affected_entities
                if any(p in e.lower() for p in self.critical_entity_patterns)
            ])
        
        # Analyze by severity
        severity_counts = {}
        for conflict in conflicts:
            severity = conflict.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        # Analyze service impact
        service_impact = self._analyze_service_impact(list(all_affected))
        
        # Business continuity assessment
        business_continuity_risk = self._assess_business_continuity(
            conflicts, critical_affected
        )
        
        return {
            "total_affected_entities": len(all_affected),
            "critical_entities_affected": len(critical_affected),
            "conflicts_by_severity": severity_counts,
            "service_impact": service_impact,
            "business_continuity_risk": business_continuity_risk,
            "estimated_downtime_minutes": self._estimate_downtime(conflicts),
            "rollback_complexity": self._assess_rollback_complexity(conflicts),
            "testing_requirements": self._generate_testing_requirements(conflicts)
        }
    
    def _analyze_service_impact(self, affected_entities: List[str]) -> Dict[str, Any]:
        """Analyze impact on business services"""
        impacted_services = {
            "billing": False,
            "ordering": False,
            "customer": False,
            "inventory": False,
            "reporting": False
        }
        
        for entity in affected_entities:
            entity_lower = entity.lower()
            if 'billing' in entity_lower or 'payment' in entity_lower:
                impacted_services["billing"] = True
            if 'order' in entity_lower:
                impacted_services["ordering"] = True
            if 'customer' in entity_lower:
                impacted_services["customer"] = True
            if 'inventory' in entity_lower or 'product' in entity_lower:
                impacted_services["inventory"] = True
            if 'report' in entity_lower or 'analytics' in entity_lower:
                impacted_services["reporting"] = True
        
        critical_services_affected = [
            service for service, affected in impacted_services.items()
            if affected and service in ["billing", "ordering", "customer"]
        ]
        
        return {
            "affected_services": [s for s, a in impacted_services.items() if a],
            "critical_services": critical_services_affected,
            "impact_score": len(critical_services_affected) * 0.3 + 
                           sum(1 for a in impacted_services.values() if a) * 0.1
        }
    
    def _assess_business_continuity(
        self,
        conflicts: List[MergeConflict],
        critical_entities: Set[str]
    ) -> str:
        """Assess risk to business continuity"""
        critical_conflict_count = sum(
            1 for c in conflicts if c.severity == Severity.CRITICAL
        )
        
        if critical_conflict_count > 2 or len(critical_entities) > 5:
            return "high"
        elif critical_conflict_count > 0 or len(critical_entities) > 2:
            return "medium"
        else:
            return "low"
    
    def _estimate_downtime(self, conflicts: List[MergeConflict]) -> float:
        """Estimate potential downtime in minutes"""
        base_downtime = 0.0
        
        for conflict in conflicts:
            if conflict.severity == Severity.CRITICAL:
                base_downtime += 30.0  # 30 minutes per critical conflict
            elif conflict.severity == Severity.HIGH:
                base_downtime += 15.0  # 15 minutes per high conflict
            elif conflict.severity == Severity.MEDIUM:
                base_downtime += 5.0   # 5 minutes per medium conflict
            else:
                base_downtime += 2.0   # 2 minutes per low conflict
        
        # Add overhead for coordination and testing
        if base_downtime > 0:
            base_downtime += 15.0  # Base overhead
        
        return base_downtime
    
    def _assess_rollback_complexity(self, conflicts: List[MergeConflict]) -> str:
        """Assess complexity of potential rollback"""
        # Check for conflicts that make rollback complex
        complex_conflicts = [
            c for c in conflicts 
            if c.conflict_type in [
                ConflictType.CIRCULAR_DEPENDENCY,
                ConflictType.BUSINESS_RULE_VIOLATION
            ]
        ]
        
        if len(complex_conflicts) > 2:
            return "high"
        elif len(complex_conflicts) > 0:
            return "medium"
        else:
            return "low"
    
    def _generate_testing_requirements(self, conflicts: List[MergeConflict]) -> List[str]:
        """Generate testing requirements based on conflicts"""
        requirements = ["Unit tests for affected entities"]
        
        # Add requirements based on severity
        if any(c.severity == Severity.CRITICAL for c in conflicts):
            requirements.extend([
                "Integration tests for critical business flows",
                "End-to-end testing of billing and payment systems",
                "Performance testing under load",
                "Disaster recovery validation"
            ])
        
        if any(c.severity == Severity.HIGH for c in conflicts):
            requirements.extend([
                "Integration tests for dependent services",
                "Regression testing for affected workflows",
                "Data integrity validation"
            ])
        
        # Add requirements based on affected entities
        affected_services = set()
        for conflict in conflicts:
            for entity in conflict.affected_entities:
                if 'billing' in entity.lower():
                    affected_services.add('billing')
                elif 'customer' in entity.lower():
                    affected_services.add('customer')
                elif 'order' in entity.lower():
                    affected_services.add('ordering')
        
        for service in affected_services:
            requirements.append(f"Service-specific tests for {service} service")
        
        return list(set(requirements))  # Remove duplicates
    
    def _assess_business_risks(
        self,
        conflicts: List[MergeConflict],
        impact_analysis: Dict[str, Any]
    ) -> Dict[str, str]:
        """Assess business risks based on conflicts and impact"""
        risks = {}
        
        # Data integrity risk
        critical_conflicts = len([c for c in conflicts if c.severity == Severity.CRITICAL])
        if critical_conflicts > 0:
            risks["data_integrity"] = "high"
        elif len(conflicts) > 10:
            risks["data_integrity"] = "medium"
        else:
            risks["data_integrity"] = "low"
        
        # Financial risk
        billing_affected = any(
            'billing' in str(impact_analysis.get('service_impact', {}).get('affected_services', []))
        )
        if billing_affected and critical_conflicts > 0:
            risks["financial"] = "high"
        elif billing_affected:
            risks["financial"] = "medium"
        else:
            risks["financial"] = "low"
        
        # Operational risk
        critical_services = impact_analysis.get('service_impact', {}).get('critical_services', [])
        if len(critical_services) > 2:
            risks["operational"] = "high"
        elif len(critical_services) > 0:
            risks["operational"] = "medium"
        else:
            risks["operational"] = "low"
        
        # Compliance risk
        customer_affected = any(
            'customer' in e.lower() for c in conflicts for e in c.affected_entities
        )
        if customer_affected and critical_conflicts > 0:
            risks["compliance"] = "high"
        elif customer_affected:
            risks["compliance"] = "medium"
        else:
            risks["compliance"] = "low"
        
        # Reputation risk
        business_continuity = impact_analysis.get('business_continuity_risk', 'low')
        if business_continuity == 'high':
            risks["reputation"] = "high"
        elif business_continuity == 'medium' or len(critical_services) > 1:
            risks["reputation"] = "medium"
        else:
            risks["reputation"] = "low"
        
        return risks
    
    def _determine_merge_decision(
        self,
        conflicts: List[MergeConflict],
        resolutions: List[ConflictResolution],
        risk_assessment: Dict[str, str]
    ) -> MergeDecision:
        """Determine merge decision based on business rules"""
        
        # Reject if any critical risk is high
        critical_risks = ['data_integrity', 'financial', 'compliance']
        if any(risk_assessment.get(risk, 'low') == 'high' for risk in critical_risks):
            return MergeDecision.REJECT_MERGE
        
        # Reject if too many critical conflicts
        critical_conflicts = [c for c in conflicts if c.severity == Severity.CRITICAL]
        if len(critical_conflicts) > 2:
            return MergeDecision.REJECT_MERGE
        
        # Check if all conflicts can be auto-resolved
        auto_resolvable = [
            r for r in resolutions 
            if r.confidence >= self.auto_resolve_threshold and r.automated
        ]
        
        if len(auto_resolvable) == len(conflicts) and len(conflicts) <= self.max_auto_merge_conflicts:
            return MergeDecision.AUTO_MERGE
        
        # Defer if too complex
        if len(conflicts) > 20 or len(critical_conflicts) > 1:
            return MergeDecision.DEFER_MERGE
        
        # Default to manual resolution
        return MergeDecision.MANUAL_RESOLUTION
    
    def _estimate_resolution_time(
        self,
        conflicts: List[MergeConflict],
        resolutions: List[ConflictResolution]
    ) -> float:
        """Estimate time to resolve conflicts in minutes"""
        base_time = 30.0  # 30 minutes base time
        
        for conflict, resolution in zip(conflicts, resolutions):
            if not resolution.automated:
                if conflict.severity == Severity.CRITICAL:
                    base_time += 120.0  # 2 hours per critical
                elif conflict.severity == Severity.HIGH:
                    base_time += 60.0   # 1 hour per high
                elif conflict.severity == Severity.MEDIUM:
                    base_time += 30.0   # 30 minutes per medium
                else:
                    base_time += 15.0   # 15 minutes per low
            else:
                # Automated resolutions are faster
                base_time += 5.0  # 5 minutes per automated resolution
        
        return base_time


def validate_merge(
    structural_conflicts: List[Dict[str, Any]],
    source_branch: str,
    target_branch: str,
    config: Optional[Dict[str, Any]] = None,
    branch_metadata: Optional[Dict[str, Any]] = None
) -> MergeValidationResult:
    """
    Main entry point for merge validation business rules.
    
    This function should be called after TerminusDB has performed
    structural validation to apply business-specific rules.
    """
    validator = MergeValidationBusinessRules(config)
    return validator.apply_business_rules(
        structural_conflicts,
        source_branch,
        target_branch,
        branch_metadata
    )