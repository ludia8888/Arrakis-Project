"""
Foundry Dataset Alerting Rule

Implements Foundry-style dataset filtering and alerting mechanisms using EventPort.
Provides enterprise-grade monitoring for schema changes and data quality issues.
"""

import logging
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from core.validation.rules.base import BaseRule, RuleResult
from core.validation.models import BreakingChange, Severity, ValidationContext, MigrationStrategy
from core.validation.interfaces import BreakingChangeRule
from core.validation.ports import EventPort, TerminusPort

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels for Foundry alerting"""
    CRITICAL = "critical"
    HIGH = "high" 
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertType(str, Enum):
    """Types of alerts that can be generated"""
    SCHEMA_CHANGE = "schema_change"
    DATA_QUALITY = "data_quality"
    PERFORMANCE = "performance"
    COMPLIANCE = "compliance"
    SECURITY = "security"


@dataclass
class AlertConfig:
    """Configuration for alert generation"""
    enabled: bool = True
    severity_threshold: AlertSeverity = AlertSeverity.MEDIUM
    cooldown_period_minutes: int = 60
    max_alerts_per_hour: int = 10
    notification_channels: List[str] = None
    escalation_rules: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.notification_channels is None:
            self.notification_channels = ["email", "slack"]
        if self.escalation_rules is None:
            self.escalation_rules = {}


@dataclass 
class FoundryAlert:
    """Foundry-style alert structure"""
    alert_id: str
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    description: str
    affected_entities: List[str]
    metadata: Dict[str, Any]
    created_at: datetime
    escalated: bool = False
    acknowledged: bool = False
    resolved: bool = False


class FoundryDatasetAlertingRule(BaseRule):
    """
    Foundry Dataset Alerting Rule
    
    Monitors schema changes and data quality issues, generating alerts
    through EventPort when conditions are met. Implements enterprise-grade
    alerting with cooldown, escalation, and notification capabilities.
    """
    
    def __init__(
        self, 
        event_port: EventPort,
        terminus_port: Optional[TerminusPort] = None,
        alert_config: Optional[AlertConfig] = None
    ):
        super().__init__(
            rule_id="foundry_dataset_alerting",
            name="Foundry Dataset Alerting",
            description="Enterprise alerting for schema changes and data quality issues"
        )
        self.event_port = event_port
        self.terminus_port = terminus_port
        self.alert_config = alert_config or AlertConfig()
        self.priority = 25  # Run after native validation but before detailed analysis
        
        # Alert state tracking
        self._alert_history: Dict[str, datetime] = {}
        self._alert_counts: Dict[str, int] = {}
        self._escalated_alerts: Set[str] = set()
    
    async def execute(self, context: ValidationContext) -> RuleResult:
        """Execute Foundry alerting rule"""
        result = RuleResult()
        
        if not self.alert_config.enabled:
            return result
        
        try:
            # Generate alerts for different categories
            await self._check_schema_change_alerts(context, result)
            await self._check_data_quality_alerts(context, result)
            await self._check_performance_alerts(context, result)
            await self._check_compliance_alerts(context, result)
            
            # Process and send alerts
            alerts_sent = await self._process_and_send_alerts(result)
            
            result.metadata.update({
                "foundry_alerting_enabled": True,
                "alerts_generated": len(alerts_sent),
                "alert_types": [alert.alert_type for alert in alerts_sent],
                "notification_channels": self.alert_config.notification_channels
            })
            
            logger.info(f"Foundry alerting generated {len(alerts_sent)} alerts")
            
        except Exception as e:
            logger.error(f"Foundry alerting rule failed: {e}")
            # Generate system error alert
            await self._send_system_error_alert(str(e))
        
        return result
    
    async def _check_schema_change_alerts(self, context: ValidationContext, result: RuleResult):
        """Check for schema change alerts"""
        schema_changes = context.schema_changes
        if not schema_changes:
            return
        
        # High-impact schema changes
        high_impact_changes = [
            "ObjectType", "LinkType", "Property", "required_field_removal",
            "primary_key_change", "type_incompatibility"
        ]
        
        for change_type, changes in schema_changes.items():
            if change_type in high_impact_changes and changes:
                alert = FoundryAlert(
                    alert_id=f"schema_change_{change_type}_{datetime.utcnow().timestamp()}",
                    alert_type=AlertType.SCHEMA_CHANGE,
                    severity=self._assess_schema_change_severity(change_type, changes),
                    title=f"High-Impact Schema Change Detected: {change_type}",
                    description=f"Schema change of type '{change_type}' affecting {len(changes)} entities",
                    affected_entities=[str(change.get('entity_id', change)) for change in changes],
                    metadata={
                        "change_type": change_type,
                        "change_count": len(changes),
                        "details": changes,
                        "context": context.context
                    },
                    created_at=datetime.utcnow()
                )
                result.metadata.setdefault("alerts", []).append(alert)
    
    async def _check_data_quality_alerts(self, context: ValidationContext, result: RuleResult):
        """Check for data quality issues using WOQL queries"""
        if not self.terminus_port:
            return
        
        try:
            # Check for data inconsistencies using WOQL
            inconsistency_query = """
            SELECT ?entity ?property ?issue
            WHERE {
                ?entity ?property ?value .
                FILTER(
                    # Check for null values in required fields
                    (!BOUND(?value)) ||
                    # Check for invalid data types
                    (DATATYPE(?value) != xsd:string && REGEX(STR(?value), "^[0-9]"))
                )
                BIND("data_quality_issue" AS ?issue)
            }
            LIMIT 100
            """
            
            quality_issues = await self.terminus_port.query(inconsistency_query)
            
            if quality_issues:
                alert = FoundryAlert(
                    alert_id=f"data_quality_{datetime.utcnow().timestamp()}",
                    alert_type=AlertType.DATA_QUALITY,
                    severity=AlertSeverity.MEDIUM,
                    title=f"Data Quality Issues Detected",
                    description=f"Found {len(quality_issues)} data quality issues in the dataset",
                    affected_entities=[issue.get('entity', '') for issue in quality_issues],
                    metadata={
                        "quality_issues": quality_issues,
                        "issue_count": len(quality_issues),
                        "check_timestamp": datetime.utcnow().isoformat()
                    },
                    created_at=datetime.utcnow()
                )
                result.metadata.setdefault("alerts", []).append(alert)
        
        except Exception as e:
            logger.error(f"Data quality check failed: {e}")
    
    async def _check_performance_alerts(self, context: ValidationContext, result: RuleResult):
        """Check for performance-impacting changes"""
        if not self.terminus_port:
            return
        
        try:
            # Check for large dataset operations
            large_dataset_query = """
            SELECT ?type (COUNT(?instance) AS ?count)
            WHERE {
                ?instance a ?type .
            }
            GROUP BY ?type
            HAVING (?count > 10000)
            """
            
            large_datasets = await self.terminus_port.query(large_dataset_query)
            
            # Alert if schema changes affect large datasets
            if large_datasets and context.schema_changes:
                affected_types = [ds.get('type', '') for ds in large_datasets]
                schema_entities = []
                for changes in context.schema_changes.values():
                    schema_entities.extend([str(change) for change in changes])
                
                overlap = set(affected_types) & set(schema_entities)
                if overlap:
                    alert = FoundryAlert(
                        alert_id=f"performance_{datetime.utcnow().timestamp()}",
                        alert_type=AlertType.PERFORMANCE,
                        severity=AlertSeverity.HIGH,
                        title="Schema Changes Affecting Large Datasets",
                        description=f"Schema changes will impact {len(overlap)} large datasets",
                        affected_entities=list(overlap),
                        metadata={
                            "large_datasets": large_datasets,
                            "affected_types": list(overlap),
                            "potential_impact": "high_performance_impact"
                        },
                        created_at=datetime.utcnow()
                    )
                    result.metadata.setdefault("alerts", []).append(alert)
        
        except Exception as e:
            logger.error(f"Performance check failed: {e}")
    
    async def _check_compliance_alerts(self, context: ValidationContext, result: RuleResult):
        """Check for compliance-related issues"""
        # Check for Foundry compliance requirements
        foundry_required_fields = [
            "@id", "@type", "created_at", "updated_at", "version"
        ]
        
        schema_changes = context.schema_changes
        compliance_issues = []
        
        # Check if required Foundry fields are being removed
        for change_type, changes in schema_changes.items():
            if "removal" in change_type.lower():
                for change in changes:
                    if isinstance(change, dict):
                        field_name = change.get('field_name', change.get('name', str(change)))
                        if field_name in foundry_required_fields:
                            compliance_issues.append({
                                "type": "foundry_field_removal",
                                "field": field_name,
                                "change": change
                            })
        
        if compliance_issues:
            alert = FoundryAlert(
                alert_id=f"compliance_{datetime.utcnow().timestamp()}",
                alert_type=AlertType.COMPLIANCE,
                severity=AlertSeverity.CRITICAL,
                title="Foundry Compliance Violation Detected",
                description=f"Removal of {len(compliance_issues)} required Foundry fields detected",
                affected_entities=[issue['field'] for issue in compliance_issues],
                metadata={
                    "compliance_issues": compliance_issues,
                    "foundry_requirements": foundry_required_fields,
                    "violation_type": "required_field_removal"
                },
                created_at=datetime.utcnow()
            )
            result.metadata.setdefault("alerts", []).append(alert)
    
    async def _process_and_send_alerts(self, result: RuleResult) -> List[FoundryAlert]:
        """Process alerts and send through EventPort"""
        alerts = result.metadata.get("alerts", [])
        sent_alerts = []
        
        for alert in alerts:
            # Check cooldown period
            if self._is_alert_in_cooldown(alert):
                continue
            
            # Check rate limiting
            if self._is_rate_limited(alert):
                continue
            
            # Apply severity filtering
            if not self._meets_severity_threshold(alert):
                continue
            
            # Send alert through EventPort
            try:
                await self._send_alert(alert)
                sent_alerts.append(alert)
                
                # Update tracking
                self._update_alert_tracking(alert)
                
                # Check for escalation
                await self._check_escalation(alert)
                
            except Exception as e:
                logger.error(f"Failed to send alert {alert.alert_id}: {e}")
        
        return sent_alerts
    
    async def _send_alert(self, alert: FoundryAlert):
        """Send alert through EventPort"""
        event_data = {
            "alert_id": alert.alert_id,
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "title": alert.title,
            "description": alert.description,
            "affected_entities": alert.affected_entities,
            "metadata": alert.metadata,
            "created_at": alert.created_at.isoformat(),
            "notification_channels": self.alert_config.notification_channels,
            "escalation_required": alert.severity in [AlertSeverity.CRITICAL, AlertSeverity.HIGH]
        }
        
        # Send through EventPort
        await self.event_port.publish(
            event_type="foundry.alert.generated",
            data=event_data,
            correlation_id=alert.alert_id
        )
        
        logger.info(f"Sent Foundry alert: {alert.alert_id} ({alert.severity})")
    
    async def _send_system_error_alert(self, error_message: str):
        """Send system error alert"""
        error_alert = FoundryAlert(
            alert_id=f"system_error_{datetime.utcnow().timestamp()}",
            alert_type=AlertType.SECURITY,  # System errors are security-relevant
            severity=AlertSeverity.HIGH,
            title="Foundry Alerting System Error",
            description=f"Foundry alerting system encountered an error: {error_message}",
            affected_entities=["foundry_alerting_system"],
            metadata={
                "error": error_message,
                "system_component": "foundry_alerting_rule",
                "timestamp": datetime.utcnow().isoformat()
            },
            created_at=datetime.utcnow()
        )
        
        try:
            await self._send_alert(error_alert)
        except Exception as e:
            logger.critical(f"Failed to send system error alert: {e}")
    
    def _assess_schema_change_severity(self, change_type: str, changes: List) -> AlertSeverity:
        """Assess severity of schema changes"""
        if "primary_key" in change_type.lower() or "type_incompatibility" in change_type.lower():
            return AlertSeverity.CRITICAL
        elif "required_field" in change_type.lower():
            return AlertSeverity.HIGH
        elif len(changes) > 10:  # Many changes
            return AlertSeverity.HIGH
        else:
            return AlertSeverity.MEDIUM
    
    def _is_alert_in_cooldown(self, alert: FoundryAlert) -> bool:
        """Check if alert is in cooldown period"""
        alert_key = f"{alert.alert_type}_{hash(alert.title)}"
        last_sent = self._alert_history.get(alert_key)
        
        if last_sent:
            cooldown_end = last_sent + timedelta(minutes=self.alert_config.cooldown_period_minutes)
            if datetime.utcnow() < cooldown_end:
                return True
        
        return False
    
    def _is_rate_limited(self, alert: FoundryAlert) -> bool:
        """Check if alert hits rate limiting"""
        alert_key = f"{alert.alert_type}_{datetime.utcnow().hour}"
        current_count = self._alert_counts.get(alert_key, 0)
        
        return current_count >= self.alert_config.max_alerts_per_hour
    
    def _meets_severity_threshold(self, alert: FoundryAlert) -> bool:
        """Check if alert meets severity threshold"""
        severity_levels = {
            AlertSeverity.INFO: 0,
            AlertSeverity.LOW: 1,
            AlertSeverity.MEDIUM: 2,
            AlertSeverity.HIGH: 3,
            AlertSeverity.CRITICAL: 4
        }
        
        alert_level = severity_levels.get(alert.severity, 0)
        threshold_level = severity_levels.get(self.alert_config.severity_threshold, 2)
        
        return alert_level >= threshold_level
    
    def _update_alert_tracking(self, alert: FoundryAlert):
        """Update alert tracking state"""
        alert_key = f"{alert.alert_type}_{hash(alert.title)}"
        hour_key = f"{alert.alert_type}_{datetime.utcnow().hour}"
        
        self._alert_history[alert_key] = datetime.utcnow()
        self._alert_counts[hour_key] = self._alert_counts.get(hour_key, 0) + 1
    
    async def _check_escalation(self, alert: FoundryAlert):
        """Check if alert needs escalation"""
        if alert.severity == AlertSeverity.CRITICAL and alert.alert_id not in self._escalated_alerts:
            escalation_data = {
                "original_alert_id": alert.alert_id,
                "escalation_reason": "critical_severity",
                "escalation_time": datetime.utcnow().isoformat(),
                "escalation_level": "immediate",
                "notification_channels": ["pagerduty", "phone", "email"]
            }
            
            await self.event_port.publish(
                event_type="foundry.alert.escalated",
                data=escalation_data,
                correlation_id=f"escalation_{alert.alert_id}"
            )
            
            self._escalated_alerts.add(alert.alert_id)
            logger.warning(f"Escalated critical alert: {alert.alert_id}")


# Factory function for easy creation
def create_foundry_alerting_rule(
    event_port: EventPort,
    terminus_port: Optional[TerminusPort] = None,
    alert_config: Optional[AlertConfig] = None
) -> FoundryDatasetAlertingRule:
    """Create Foundry alerting rule with proper configuration"""
    return FoundryDatasetAlertingRule(
        event_port=event_port,
        terminus_port=terminus_port,
        alert_config=alert_config
    )