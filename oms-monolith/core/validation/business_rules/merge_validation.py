"""
Consolidated Business Rule Merge Validation

This module consolidates business-specific merge validation logic that TerminusDB
cannot handle natively. It focuses on conflict resolution strategies, impact analysis,
risk assessment, and business-specific merge rules.

All schema-level validations (type constraints, cardinality, domain/range) are
handled by TerminusDB and should use core.validation.rules.terminus_native_schema_rule.

This consolidation extracts business logic from:
- core/validation/merge_validation_service.py
- core/traversal/merge_validator.py (deprecated)
- core/traversal/semantic_validator.py (partially deprecated)
"""

import logging
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from core.validation.interfaces import BreakingChange, Severity, MigrationStrategy

logger = logging.getLogger(__name__)


class MergeDecision(str, Enum):
    """Business-level merge decision outcomes"""
    AUTO_MERGE = "auto_merge"
    MANUAL_RESOLUTION = "manual_resolution" 
    REJECT_MERGE = "reject_merge"
    DEFER_MERGE = "defer_merge"


class ConflictResolutionStrategy(str, Enum):
    """Business-specific conflict resolution strategies"""
    AUTOMATIC = "automatic"
    SEMI_AUTOMATIC = "semi_automatic"
    MANUAL = "manual"
    DEFER = "defer"
    REJECT = "reject"


@dataclass
class BusinessConflictResolution:
    """Business-specific resolution for merge conflicts"""
    conflict: BreakingChange
    strategy: ConflictResolutionStrategy
    resolution_action: str
    confidence: float
    business_rationale: str
    estimated_effort_hours: float = 0.0
    requires_approval: bool = False
    approver_roles: List[str] = field(default_factory=list)


@dataclass
class BusinessImpactAnalysis:
    """Business impact analysis for merge operations"""
    affected_services: List[str]
    critical_services: List[str]
    business_processes: List[str]
    revenue_impact_risk: str  # high, medium, low
    customer_impact_risk: str  # high, medium, low
    regulatory_compliance_risk: str  # high, medium, low
    estimated_downtime_minutes: float
    rollback_complexity: str  # simple, moderate, complex
    testing_requirements: List[str]
    business_continuity_score: float  # 0.0 to 1.0


@dataclass
class MergeRiskAssessment:
    """Business risk assessment for merge operations"""
    overall_risk_level: str  # critical, high, medium, low
    data_integrity_risk: str
    performance_risk: str
    business_continuity_risk: str
    security_risk: str
    compliance_risk: str
    risk_mitigation_steps: List[str]
    recommended_merge_window: Optional[str] = None
    requires_stakeholder_approval: bool = False
    stakeholders: List[str] = field(default_factory=list)


class BusinessMergeValidator:
    """
    Business rule validator for merge operations.
    
    Handles validation logic that TerminusDB cannot process:
    - Business-specific conflict resolution
    - Impact analysis on business processes
    - Risk assessment from business perspective
    - Custom merge rules based on business requirements
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._default_config()
        self._resolution_strategies = self._initialize_resolution_strategies()
        self._business_rules = self._initialize_business_rules()
        
    def _default_config(self) -> Dict[str, Any]:
        """Default configuration for business validation"""
        return {
            "auto_merge_confidence_threshold": 0.8,
            "max_critical_conflicts_for_auto_merge": 0,
            "max_high_conflicts_for_auto_merge": 2,
            "business_hours_merge_only": True,
            "merge_window_start": "02:00",
            "merge_window_end": "06:00",
            "require_approval_for_critical_services": True,
            "critical_services": ["payment", "order", "customer", "inventory"],
            "revenue_impacting_entities": ["Order", "Payment", "Invoice", "Subscription"],
            "compliance_sensitive_entities": ["Customer", "PersonalData", "AuditLog"],
        }
    
    def generate_conflict_resolutions(
        self, 
        conflicts: List[BreakingChange]
    ) -> List[BusinessConflictResolution]:
        """
        Generate business-specific resolution strategies for conflicts.
        
        This applies business rules to determine how conflicts should be resolved,
        considering factors like business impact, compliance, and revenue.
        """
        resolutions = []
        
        for conflict in conflicts:
            resolution_strategy = self._determine_resolution_strategy(conflict)
            resolution = self._create_business_resolution(conflict, resolution_strategy)
            resolutions.append(resolution)
        
        return resolutions
    
    def _determine_resolution_strategy(self, conflict: BreakingChange) -> ConflictResolutionStrategy:
        """Determine resolution strategy based on business rules"""
        # Critical conflicts require manual resolution
        if conflict.severity == Severity.CRITICAL:
            return ConflictResolutionStrategy.MANUAL
        
        # Check if conflict affects revenue-impacting entities
        if self._affects_revenue_entities(conflict):
            return ConflictResolutionStrategy.MANUAL
        
        # Check if conflict affects compliance-sensitive entities
        if self._affects_compliance_entities(conflict):
            return ConflictResolutionStrategy.SEMI_AUTOMATIC
        
        # High severity conflicts with migration strategies can be semi-automatic
        if conflict.severity == Severity.HIGH and conflict.suggested_strategies:
            return ConflictResolutionStrategy.SEMI_AUTOMATIC
        
        # Medium severity can often be automated
        if conflict.severity == Severity.MEDIUM:
            return ConflictResolutionStrategy.AUTOMATIC
        
        # Low severity should be automated
        if conflict.severity == Severity.LOW:
            return ConflictResolutionStrategy.AUTOMATIC
        
        # Default to manual for safety
        return ConflictResolutionStrategy.MANUAL
    
    def _affects_revenue_entities(self, conflict: BreakingChange) -> bool:
        """Check if conflict affects revenue-impacting entities"""
        revenue_entities = self.config.get("revenue_impacting_entities", [])
        
        if conflict.object_type in revenue_entities:
            return True
        
        # Check field name for revenue-related terms
        if conflict.field_name:
            revenue_terms = ["price", "cost", "payment", "billing", "invoice", "revenue"]
            return any(term in conflict.field_name.lower() for term in revenue_terms)
        
        return False
    
    def _affects_compliance_entities(self, conflict: BreakingChange) -> bool:
        """Check if conflict affects compliance-sensitive entities"""
        compliance_entities = self.config.get("compliance_sensitive_entities", [])
        
        if conflict.object_type in compliance_entities:
            return True
        
        # Check field name for compliance-related terms
        if conflict.field_name:
            compliance_terms = ["personal", "private", "sensitive", "pii", "gdpr", "audit"]
            return any(term in conflict.field_name.lower() for term in compliance_terms)
        
        return False
    
    def _create_business_resolution(
        self, 
        conflict: BreakingChange,
        strategy: ConflictResolutionStrategy
    ) -> BusinessConflictResolution:
        """Create business-specific resolution for a conflict"""
        resolution_action, confidence, effort = self._get_resolution_details(conflict, strategy)
        
        requires_approval = strategy in [
            ConflictResolutionStrategy.MANUAL,
            ConflictResolutionStrategy.SEMI_AUTOMATIC
        ] or self._affects_critical_service(conflict)
        
        approver_roles = []
        if requires_approval:
            approver_roles = self._determine_approver_roles(conflict)
        
        return BusinessConflictResolution(
            conflict=conflict,
            strategy=strategy,
            resolution_action=resolution_action,
            confidence=confidence,
            business_rationale=self._generate_business_rationale(conflict, strategy),
            estimated_effort_hours=effort,
            requires_approval=requires_approval,
            approver_roles=approver_roles
        )
    
    def _get_resolution_details(
        self, 
        conflict: BreakingChange,
        strategy: ConflictResolutionStrategy
    ) -> Tuple[str, float, float]:
        """Get resolution action, confidence, and effort estimate"""
        if strategy == ConflictResolutionStrategy.AUTOMATIC:
            return (
                "Apply automated migration with backward compatibility",
                0.9,
                0.5  # 30 minutes
            )
        elif strategy == ConflictResolutionStrategy.SEMI_AUTOMATIC:
            return (
                "Apply migration strategy with manual validation",
                0.7,
                2.0  # 2 hours
            )
        elif strategy == ConflictResolutionStrategy.MANUAL:
            return (
                "Requires manual analysis and custom resolution",
                0.3,
                4.0  # 4 hours
            )
        else:
            return (
                "Defer resolution pending further analysis",
                0.1,
                8.0  # 8 hours
            )
    
    def _generate_business_rationale(
        self, 
        conflict: BreakingChange,
        strategy: ConflictResolutionStrategy
    ) -> str:
        """Generate business rationale for resolution strategy"""
        rationales = []
        
        if self._affects_revenue_entities(conflict):
            rationales.append("Affects revenue-critical entities")
        
        if self._affects_compliance_entities(conflict):
            rationales.append("Involves compliance-sensitive data")
        
        if conflict.severity == Severity.CRITICAL:
            rationales.append("Critical severity requires careful handling")
        
        if strategy == ConflictResolutionStrategy.AUTOMATIC:
            rationales.append("Low risk change suitable for automation")
        elif strategy == ConflictResolutionStrategy.SEMI_AUTOMATIC:
            rationales.append("Moderate risk requires validation")
        else:
            rationales.append("High business impact requires manual review")
        
        return "; ".join(rationales)
    
    def _affects_critical_service(self, conflict: BreakingChange) -> bool:
        """Check if conflict affects critical services"""
        critical_services = self.config.get("critical_services", [])
        
        # Check impact scope for service references
        if isinstance(conflict.impact, dict):
            affected_services = conflict.impact.get("services", [])
            return any(svc in critical_services for svc in affected_services)
        
        return False
    
    def _determine_approver_roles(self, conflict: BreakingChange) -> List[str]:
        """Determine which roles need to approve the resolution"""
        approvers = []
        
        if conflict.severity == Severity.CRITICAL:
            approvers.append("engineering_lead")
            approvers.append("product_owner")
        
        if self._affects_revenue_entities(conflict):
            approvers.append("finance_lead")
        
        if self._affects_compliance_entities(conflict):
            approvers.append("compliance_officer")
        
        if self._affects_critical_service(conflict):
            approvers.append("service_owner")
        
        return list(set(approvers))  # Remove duplicates
    
    def analyze_business_impact(
        self,
        conflicts: List[BreakingChange],
        source_branch: str,
        target_branch: str
    ) -> BusinessImpactAnalysis:
        """
        Analyze business impact of merge conflicts.
        
        This goes beyond technical impact to assess business consequences.
        """
        affected_services = self._identify_affected_services(conflicts)
        critical_services = [svc for svc in affected_services 
                           if svc in self.config.get("critical_services", [])]
        
        business_processes = self._identify_affected_processes(conflicts)
        
        revenue_risk = self._assess_revenue_risk(conflicts)
        customer_risk = self._assess_customer_risk(conflicts)
        compliance_risk = self._assess_compliance_risk(conflicts)
        
        downtime = self._estimate_downtime(conflicts)
        rollback_complexity = self._assess_rollback_complexity(conflicts)
        
        testing_requirements = self._generate_testing_requirements(
            conflicts, business_processes
        )
        
        continuity_score = self._calculate_business_continuity_score(
            conflicts, critical_services
        )
        
        return BusinessImpactAnalysis(
            affected_services=affected_services,
            critical_services=critical_services,
            business_processes=business_processes,
            revenue_impact_risk=revenue_risk,
            customer_impact_risk=customer_risk,
            regulatory_compliance_risk=compliance_risk,
            estimated_downtime_minutes=downtime,
            rollback_complexity=rollback_complexity,
            testing_requirements=testing_requirements,
            business_continuity_score=continuity_score
        )
    
    def _identify_affected_services(self, conflicts: List[BreakingChange]) -> List[str]:
        """Identify services affected by conflicts"""
        services = set()
        
        for conflict in conflicts:
            # Extract from impact data
            if isinstance(conflict.impact, dict):
                services.update(conflict.impact.get("services", []))
            
            # Infer from object type
            service_mapping = {
                "Order": "order-service",
                "Payment": "payment-service",
                "Customer": "customer-service",
                "Product": "catalog-service",
                "Inventory": "inventory-service"
            }
            
            if conflict.object_type in service_mapping:
                services.add(service_mapping[conflict.object_type])
        
        return sorted(list(services))
    
    def _identify_affected_processes(self, conflicts: List[BreakingChange]) -> List[str]:
        """Identify business processes affected by conflicts"""
        processes = set()
        
        process_mapping = {
            "Order": ["order_placement", "order_fulfillment"],
            "Payment": ["payment_processing", "refund_processing"],
            "Customer": ["customer_onboarding", "customer_support"],
            "Product": ["catalog_management", "pricing_updates"],
            "Inventory": ["stock_management", "reorder_processing"]
        }
        
        for conflict in conflicts:
            if conflict.object_type in process_mapping:
                processes.update(process_mapping[conflict.object_type])
        
        return sorted(list(processes))
    
    def _assess_revenue_risk(self, conflicts: List[BreakingChange]) -> str:
        """Assess revenue impact risk"""
        revenue_conflicts = [c for c in conflicts if self._affects_revenue_entities(c)]
        
        if any(c.severity == Severity.CRITICAL for c in revenue_conflicts):
            return "high"
        elif len(revenue_conflicts) > 3 or any(c.severity == Severity.HIGH for c in revenue_conflicts):
            return "medium"
        elif revenue_conflicts:
            return "low"
        else:
            return "low"
    
    def _assess_customer_risk(self, conflicts: List[BreakingChange]) -> str:
        """Assess customer impact risk"""
        customer_facing = ["Order", "Payment", "Customer", "Product"]
        customer_conflicts = [c for c in conflicts if c.object_type in customer_facing]
        
        if any(c.severity == Severity.CRITICAL for c in customer_conflicts):
            return "high"
        elif len(customer_conflicts) > 5:
            return "medium"
        else:
            return "low"
    
    def _assess_compliance_risk(self, conflicts: List[BreakingChange]) -> str:
        """Assess compliance risk"""
        compliance_conflicts = [c for c in conflicts if self._affects_compliance_entities(c)]
        
        if compliance_conflicts:
            if any(c.severity in [Severity.CRITICAL, Severity.HIGH] for c in compliance_conflicts):
                return "high"
            else:
                return "medium"
        else:
            return "low"
    
    def _estimate_downtime(self, conflicts: List[BreakingChange]) -> float:
        """Estimate potential downtime in minutes"""
        base_downtime = 0.0
        
        for conflict in conflicts:
            if conflict.severity == Severity.CRITICAL:
                base_downtime += 30.0  # 30 minutes per critical
            elif conflict.severity == Severity.HIGH:
                base_downtime += 15.0  # 15 minutes per high
            else:
                base_downtime += 5.0   # 5 minutes per other
        
        # Add overhead for coordination
        if len(conflicts) > 10:
            base_downtime *= 1.5
        
        return base_downtime
    
    def _assess_rollback_complexity(self, conflicts: List[BreakingChange]) -> str:
        """Assess complexity of rollback if needed"""
        if any(c.severity == Severity.CRITICAL for c in conflicts):
            return "complex"
        elif len(conflicts) > 10 or any(c.severity == Severity.HIGH for c in conflicts):
            return "moderate"
        else:
            return "simple"
    
    def _generate_testing_requirements(
        self, 
        conflicts: List[BreakingChange],
        processes: List[str]
    ) -> List[str]:
        """Generate business-focused testing requirements"""
        requirements = ["Unit tests for affected entities"]
        
        if any(c.severity in [Severity.CRITICAL, Severity.HIGH] for c in conflicts):
            requirements.append("Integration tests for dependent services")
            requirements.append("End-to-end business process validation")
        
        if "payment_processing" in processes:
            requirements.append("Payment gateway integration tests")
            requirements.append("Transaction rollback scenarios")
        
        if "order_placement" in processes:
            requirements.append("Order workflow validation")
            requirements.append("Inventory synchronization tests")
        
        if self._has_compliance_impact(conflicts):
            requirements.append("Data privacy compliance validation")
            requirements.append("Audit trail verification")
        
        if len(conflicts) > 5:
            requirements.append("Performance regression testing")
            requirements.append("Load testing for affected endpoints")
        
        return requirements
    
    def _has_compliance_impact(self, conflicts: List[BreakingChange]) -> bool:
        """Check if any conflicts have compliance impact"""
        return any(self._affects_compliance_entities(c) for c in conflicts)
    
    def _calculate_business_continuity_score(
        self,
        conflicts: List[BreakingChange],
        critical_services: List[str]
    ) -> float:
        """Calculate business continuity score (0.0 to 1.0)"""
        score = 1.0
        
        # Reduce score based on critical service impact
        score -= len(critical_services) * 0.1
        
        # Reduce score based on conflict severity
        critical_count = sum(1 for c in conflicts if c.severity == Severity.CRITICAL)
        high_count = sum(1 for c in conflicts if c.severity == Severity.HIGH)
        
        score -= critical_count * 0.2
        score -= high_count * 0.1
        
        # Ensure score stays in valid range
        return max(0.0, min(1.0, score))
    
    def assess_merge_risks(
        self,
        conflicts: List[BreakingChange],
        impact_analysis: BusinessImpactAnalysis
    ) -> MergeRiskAssessment:
        """
        Assess business risks of the merge operation.
        
        This provides a comprehensive risk assessment from business perspective.
        """
        # Assess individual risk categories
        data_integrity_risk = self._assess_data_integrity_risk(conflicts)
        performance_risk = self._assess_performance_risk(conflicts, impact_analysis)
        continuity_risk = self._assess_business_continuity_risk(impact_analysis)
        security_risk = self._assess_security_risk(conflicts)
        compliance_risk = impact_analysis.regulatory_compliance_risk
        
        # Determine overall risk level
        risk_levels = [
            data_integrity_risk,
            performance_risk,
            continuity_risk,
            security_risk,
            compliance_risk
        ]
        
        if "critical" in risk_levels:
            overall_risk = "critical"
        elif risk_levels.count("high") >= 2:
            overall_risk = "high"
        elif "high" in risk_levels:
            overall_risk = "medium"
        else:
            overall_risk = "low"
        
        # Generate mitigation steps
        mitigation_steps = self._generate_mitigation_steps(
            conflicts, impact_analysis, risk_levels
        )
        
        # Determine merge window
        merge_window = self._recommend_merge_window(overall_risk, impact_analysis)
        
        # Determine stakeholder approval needs
        requires_approval = overall_risk in ["critical", "high"]
        stakeholders = self._identify_stakeholders(conflicts, impact_analysis) if requires_approval else []
        
        return MergeRiskAssessment(
            overall_risk_level=overall_risk,
            data_integrity_risk=data_integrity_risk,
            performance_risk=performance_risk,
            business_continuity_risk=continuity_risk,
            security_risk=security_risk,
            compliance_risk=compliance_risk,
            risk_mitigation_steps=mitigation_steps,
            recommended_merge_window=merge_window,
            requires_stakeholder_approval=requires_approval,
            stakeholders=stakeholders
        )
    
    def _assess_data_integrity_risk(self, conflicts: List[BreakingChange]) -> str:
        """Assess data integrity risk"""
        critical_conflicts = [c for c in conflicts if c.severity == Severity.CRITICAL]
        
        if critical_conflicts:
            return "high"
        elif len(conflicts) > 10:
            return "medium"
        else:
            return "low"
    
    def _assess_performance_risk(
        self,
        conflicts: List[BreakingChange],
        impact: BusinessImpactAnalysis
    ) -> str:
        """Assess performance risk"""
        if len(impact.affected_services) > 5:
            return "high"
        elif len(conflicts) > 20:
            return "high"
        elif impact.critical_services:
            return "medium"
        else:
            return "low"
    
    def _assess_business_continuity_risk(self, impact: BusinessImpactAnalysis) -> str:
        """Assess business continuity risk"""
        if impact.business_continuity_score < 0.5:
            return "critical"
        elif impact.business_continuity_score < 0.7:
            return "high"
        elif impact.business_continuity_score < 0.9:
            return "medium"
        else:
            return "low"
    
    def _assess_security_risk(self, conflicts: List[BreakingChange]) -> str:
        """Assess security risk"""
        security_terms = ["auth", "permission", "access", "security", "token", "credential"]
        
        security_conflicts = [
            c for c in conflicts
            if any(term in str(c.field_name).lower() for term in security_terms)
        ]
        
        if security_conflicts:
            if any(c.severity in [Severity.CRITICAL, Severity.HIGH] for c in security_conflicts):
                return "high"
            else:
                return "medium"
        else:
            return "low"
    
    def _generate_mitigation_steps(
        self,
        conflicts: List[BreakingChange],
        impact: BusinessImpactAnalysis,
        risk_levels: List[str]
    ) -> List[str]:
        """Generate risk mitigation steps"""
        steps = []
        
        if "high" in risk_levels or "critical" in risk_levels:
            steps.append("Schedule merge during maintenance window")
            steps.append("Prepare rollback plan and test rollback procedure")
            steps.append("Notify stakeholders and support teams")
        
        if impact.critical_services:
            steps.append("Implement feature flags for critical service changes")
            steps.append("Plan phased rollout starting with non-critical services")
        
        if impact.regulatory_compliance_risk in ["high", "medium"]:
            steps.append("Conduct compliance review before merge")
            steps.append("Document all data handling changes")
        
        if len(conflicts) > 10:
            steps.append("Break merge into smaller, manageable chunks")
            steps.append("Test each chunk independently")
        
        steps.extend([
            "Execute comprehensive test suite",
            "Monitor system metrics during and after merge",
            "Have incident response team on standby"
        ])
        
        return steps
    
    def _recommend_merge_window(
        self,
        risk_level: str,
        impact: BusinessImpactAnalysis
    ) -> Optional[str]:
        """Recommend optimal merge window"""
        if risk_level == "critical":
            return "Weekend maintenance window with full team availability"
        elif risk_level == "high":
            return "Off-peak hours (2 AM - 6 AM) with on-call support"
        elif impact.critical_services:
            return "Low-traffic period with monitoring"
        else:
            return None  # Can merge anytime
    
    def _identify_stakeholders(
        self,
        conflicts: List[BreakingChange],
        impact: BusinessImpactAnalysis
    ) -> List[str]:
        """Identify stakeholders who need to approve"""
        stakeholders = set()
        
        # Add service owners
        for service in impact.critical_services:
            stakeholders.add(f"{service}_owner")
        
        # Add business stakeholders
        if impact.revenue_impact_risk == "high":
            stakeholders.add("revenue_operations_lead")
            stakeholders.add("finance_director")
        
        if impact.customer_impact_risk == "high":
            stakeholders.add("customer_success_lead")
            stakeholders.add("support_director")
        
        if impact.regulatory_compliance_risk == "high":
            stakeholders.add("compliance_officer")
            stakeholders.add("legal_counsel")
        
        # Add technical stakeholders
        stakeholders.add("engineering_lead")
        if len(conflicts) > 20:
            stakeholders.add("cto")
        
        return sorted(list(stakeholders))
    
    def determine_merge_decision(
        self,
        conflicts: List[BreakingChange],
        resolutions: List[BusinessConflictResolution],
        risk_assessment: MergeRiskAssessment
    ) -> MergeDecision:
        """
        Make final merge decision based on business rules.
        
        This is the business logic for determining if a merge can proceed.
        """
        # Reject if risk is too high
        if risk_assessment.overall_risk_level == "critical":
            return MergeDecision.REJECT_MERGE
        
        # Check for critical conflicts
        critical_conflicts = [c for c in conflicts if c.severity == Severity.CRITICAL]
        max_critical = self.config.get("max_critical_conflicts_for_auto_merge", 0)
        
        if len(critical_conflicts) > max_critical:
            return MergeDecision.MANUAL_RESOLUTION
        
        # Check confidence in resolutions
        confidence_threshold = self.config.get("auto_merge_confidence_threshold", 0.8)
        high_confidence_resolutions = [
            r for r in resolutions 
            if r.confidence >= confidence_threshold
        ]
        
        # Can auto-merge if all conflicts have high-confidence resolutions
        if len(high_confidence_resolutions) == len(conflicts) and not risk_assessment.requires_stakeholder_approval:
            return MergeDecision.AUTO_MERGE
        
        # Defer if too complex
        if len(conflicts) > 50 or risk_assessment.overall_risk_level == "high":
            return MergeDecision.DEFER_MERGE
        
        # Default to manual resolution
        return MergeDecision.MANUAL_RESOLUTION
    
    def _initialize_resolution_strategies(self) -> Dict[Severity, ConflictResolutionStrategy]:
        """Initialize default resolution strategies by severity"""
        return {
            Severity.CRITICAL: ConflictResolutionStrategy.MANUAL,
            Severity.HIGH: ConflictResolutionStrategy.SEMI_AUTOMATIC,
            Severity.MEDIUM: ConflictResolutionStrategy.AUTOMATIC,
            Severity.LOW: ConflictResolutionStrategy.AUTOMATIC
        }
    
    def _initialize_business_rules(self) -> Dict[str, Any]:
        """Initialize business-specific validation rules"""
        return {
            "merge_blackout_dates": [],  # Dates when merges are not allowed
            "require_two_approvals_for_critical": True,
            "auto_rollback_on_metric_degradation": True,
            "metric_degradation_thresholds": {
                "error_rate_increase": 0.05,  # 5% increase triggers rollback
                "latency_increase": 0.20,      # 20% increase triggers rollback
                "success_rate_decrease": 0.02  # 2% decrease triggers rollback
            }
        }


def estimate_merge_time(conflicts: List[BreakingChange], resolutions: List[BusinessConflictResolution]) -> float:
    """
    Estimate time required for merge completion in hours.
    
    This is a business-level estimation considering manual work needed.
    """
    base_time = 0.5  # 30 minutes base
    
    # Add time for each resolution based on effort
    for resolution in resolutions:
        base_time += resolution.estimated_effort_hours
    
    # Add overhead for coordination if many conflicts
    if len(conflicts) > 10:
        base_time *= 1.2  # 20% overhead
    
    if len(conflicts) > 20:
        base_time *= 1.5  # 50% overhead for complex merges
    
    return base_time