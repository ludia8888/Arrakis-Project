"""
Enterprise Business Validation Rules

This module contains enterprise-specific validation rules that cannot be handled
by TerminusDB's native validation. It focuses on:
- Multi-level validation modes (MINIMAL, STANDARD, STRICT, PARANOID)
- Business context validation (user roles, permissions)
- Audit trail requirements
- Compliance checks
- Enterprise-specific business rules

All structural validations (types, constraints) are handled by TerminusDB.
"""

import logging
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class ValidationLevel(str, Enum):
    """Enterprise validation strictness levels"""
    MINIMAL = "minimal"      # Basic business rules only
    STANDARD = "standard"    # Standard business rules + audit
    STRICT = "strict"        # All business rules + compliance
    PARANOID = "paranoid"    # Maximum validation with deep inspection


class ComplianceType(str, Enum):
    """Types of compliance requirements"""
    GDPR = "gdpr"
    HIPAA = "hipaa"
    SOX = "sox"
    PCI_DSS = "pci_dss"
    INTERNAL = "internal"


@dataclass
class BusinessContext:
    """Business context for validation"""
    user_id: str
    user_roles: Set[str]
    organization_id: str
    request_id: str
    source_system: str
    validation_level: ValidationLevel
    compliance_requirements: Set[ComplianceType] = field(default_factory=set)
    is_privileged_operation: bool = False
    requires_audit: bool = True


@dataclass
class AuditRequirement:
    """Audit trail requirements for an operation"""
    operation_type: str
    entity_type: str
    entity_id: str
    changes: Dict[str, Any]
    risk_level: str  # low, medium, high, critical
    requires_approval: bool
    approval_roles: Set[str]
    retention_days: int


@dataclass
class ComplianceValidation:
    """Compliance validation result"""
    compliance_type: ComplianceType
    is_compliant: bool
    violations: List[str]
    remediation_steps: List[str]
    blocking: bool  # Whether this blocks the operation


class EnterpriseBusinessValidator:
    """Enterprise-specific business validation rules"""
    
    # Business-critical entity patterns
    CRITICAL_ENTITIES = {
        'billing', 'payment', 'invoice', 'subscription',
        'customer', 'contract', 'pricing', 'revenue'
    }
    
    # Sensitive data patterns
    SENSITIVE_DATA_PATTERNS = {
        'ssn', 'credit_card', 'bank_account', 'tax_id',
        'medical_record', 'passport', 'driver_license'
    }
    
    # High-risk operations
    HIGH_RISK_OPERATIONS = {
        'delete', 'bulk_update', 'schema_migration',
        'permission_change', 'audit_modification'
    }
    
    def validate_business_context(
        self,
        context: BusinessContext,
        operation: str,
        entity_type: str,
        data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Validate operation based on business context"""
        violations = []
        
        # Level-based validation
        if context.validation_level == ValidationLevel.MINIMAL:
            # Only critical business rules
            violations.extend(self._validate_critical_business_rules(
                context, operation, entity_type, data
            ))
        
        elif context.validation_level == ValidationLevel.STANDARD:
            # Standard business rules + audit
            violations.extend(self._validate_critical_business_rules(
                context, operation, entity_type, data
            ))
            violations.extend(self._validate_standard_business_rules(
                context, operation, entity_type, data
            ))
            
        elif context.validation_level == ValidationLevel.STRICT:
            # All business rules + compliance
            violations.extend(self._validate_critical_business_rules(
                context, operation, entity_type, data
            ))
            violations.extend(self._validate_standard_business_rules(
                context, operation, entity_type, data
            ))
            violations.extend(self._validate_compliance_rules(
                context, operation, entity_type, data
            ))
            
        elif context.validation_level == ValidationLevel.PARANOID:
            # Maximum validation
            violations.extend(self._validate_critical_business_rules(
                context, operation, entity_type, data
            ))
            violations.extend(self._validate_standard_business_rules(
                context, operation, entity_type, data
            ))
            violations.extend(self._validate_compliance_rules(
                context, operation, entity_type, data
            ))
            violations.extend(self._validate_paranoid_rules(
                context, operation, entity_type, data
            ))
        
        return violations
    
    def _validate_critical_business_rules(
        self,
        context: BusinessContext,
        operation: str,
        entity_type: str,
        data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Critical business rules that always apply"""
        violations = []
        
        # Rule 1: Prevent deletion of critical entities without approval
        if operation == 'delete' and any(
            pattern in entity_type.lower() 
            for pattern in self.CRITICAL_ENTITIES
        ):
            if 'admin' not in context.user_roles and not context.is_privileged_operation:
                violations.append({
                    'rule': 'critical_entity_deletion',
                    'message': f'Deletion of {entity_type} requires admin approval',
                    'severity': 'critical',
                    'required_role': 'admin'
                })
        
        # Rule 2: Revenue-impacting changes require finance approval
        if self._is_revenue_impacting(entity_type, data):
            if 'finance' not in context.user_roles:
                violations.append({
                    'rule': 'revenue_impact_approval',
                    'message': 'Revenue-impacting changes require finance approval',
                    'severity': 'high',
                    'required_role': 'finance'
                })
        
        # Rule 3: Bulk operations on critical entities
        if operation == 'bulk_update' and any(
            pattern in entity_type.lower() 
            for pattern in self.CRITICAL_ENTITIES
        ):
            affected_count = data.get('affected_count', 0)
            if affected_count > 100:
                violations.append({
                    'rule': 'bulk_operation_limit',
                    'message': f'Bulk operation affecting {affected_count} records exceeds limit',
                    'severity': 'high',
                    'max_allowed': 100
                })
        
        return violations
    
    def _validate_standard_business_rules(
        self,
        context: BusinessContext,
        operation: str,
        entity_type: str,
        data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Standard business rules for normal operations"""
        violations = []
        
        # Rule 1: Business hours restriction for certain operations
        if self._is_outside_business_hours() and operation in self.HIGH_RISK_OPERATIONS:
            if 'operations' not in context.user_roles:
                violations.append({
                    'rule': 'business_hours_restriction',
                    'message': f'{operation} operations restricted to business hours',
                    'severity': 'medium',
                    'business_hours': '09:00-18:00 UTC'
                })
        
        # Rule 2: Cross-service data consistency
        if entity_type == 'customer' and operation in ['update', 'delete']:
            # Check for active subscriptions, open invoices, etc.
            if self._has_active_dependencies(entity_type, data.get('id')):
                violations.append({
                    'rule': 'active_dependencies',
                    'message': 'Cannot modify customer with active subscriptions',
                    'severity': 'high',
                    'dependencies': ['subscription', 'invoice']
                })
        
        # Rule 3: Data retention policies
        if operation == 'delete':
            retention_days = self._get_retention_requirement(entity_type)
            if retention_days > 0:
                violations.append({
                    'rule': 'data_retention_policy',
                    'message': f'{entity_type} must be retained for {retention_days} days',
                    'severity': 'high',
                    'retention_days': retention_days
                })
        
        return violations
    
    def _validate_compliance_rules(
        self,
        context: BusinessContext,
        operation: str,
        entity_type: str,
        data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Compliance-specific validation rules"""
        violations = []
        
        # GDPR compliance
        if ComplianceType.GDPR in context.compliance_requirements:
            if self._contains_personal_data(data):
                # Right to be forgotten
                if operation == 'delete' and entity_type == 'customer':
                    if not data.get('gdpr_deletion_request'):
                        violations.append({
                            'rule': 'gdpr_deletion_request',
                            'message': 'Customer deletion requires GDPR deletion request',
                            'severity': 'high',
                            'compliance': 'GDPR Article 17'
                        })
                
                # Data minimization
                if operation == 'create':
                    unnecessary_fields = self._check_data_minimization(entity_type, data)
                    if unnecessary_fields:
                        violations.append({
                            'rule': 'gdpr_data_minimization',
                            'message': 'Collecting unnecessary personal data',
                            'severity': 'medium',
                            'unnecessary_fields': unnecessary_fields
                        })
        
        # HIPAA compliance
        if ComplianceType.HIPAA in context.compliance_requirements:
            if self._contains_health_data(data):
                if not context.is_privileged_operation:
                    violations.append({
                        'rule': 'hipaa_access_control',
                        'message': 'Access to health data requires privileged operation flag',
                        'severity': 'critical',
                        'compliance': 'HIPAA Security Rule'
                    })
        
        # PCI DSS compliance
        if ComplianceType.PCI_DSS in context.compliance_requirements:
            if self._contains_payment_data(data):
                if not self._is_pci_compliant_operation(operation, data):
                    violations.append({
                        'rule': 'pci_dss_data_handling',
                        'message': 'Payment data must be tokenized',
                        'severity': 'critical',
                        'compliance': 'PCI DSS Requirement 3.4'
                    })
        
        return violations
    
    def _validate_paranoid_rules(
        self,
        context: BusinessContext,
        operation: str,
        entity_type: str,
        data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Paranoid-level validation for maximum security"""
        violations = []
        
        # Rule 1: Anomaly detection
        if self._detect_anomaly(context, operation, entity_type, data):
            violations.append({
                'rule': 'anomaly_detected',
                'message': 'Operation pattern deviates from normal behavior',
                'severity': 'medium',
                'anomaly_score': self._calculate_anomaly_score(context, operation, data)
            })
        
        # Rule 2: Rate limiting per user per entity type
        rate_limit = self._get_rate_limit(context.user_id, entity_type, operation)
        if rate_limit['exceeded']:
            violations.append({
                'rule': 'rate_limit_exceeded',
                'message': f'Rate limit exceeded: {rate_limit["current"]}/{rate_limit["limit"]}',
                'severity': 'medium',
                'reset_time': rate_limit['reset_time']
            })
        
        # Rule 3: Deep field inspection
        suspicious_patterns = self._deep_inspect_fields(data)
        if suspicious_patterns:
            violations.append({
                'rule': 'suspicious_content',
                'message': 'Suspicious patterns detected in data',
                'severity': 'high',
                'patterns': suspicious_patterns
            })
        
        return violations
    
    def generate_audit_requirements(
        self,
        context: BusinessContext,
        operation: str,
        entity_type: str,
        data: Dict[str, Any],
        changes: Optional[Dict[str, Any]] = None
    ) -> AuditRequirement:
        """Generate audit requirements for an operation"""
        risk_level = self._calculate_risk_level(
            context, operation, entity_type, data
        )
        
        requires_approval = (
            risk_level in ['high', 'critical'] or
            operation in self.HIGH_RISK_OPERATIONS or
            any(pattern in entity_type.lower() for pattern in self.CRITICAL_ENTITIES)
        )
        
        approval_roles = set()
        if requires_approval:
            if risk_level == 'critical':
                approval_roles.add('admin')
            if self._is_revenue_impacting(entity_type, data):
                approval_roles.add('finance')
            if self._contains_personal_data(data):
                approval_roles.add('privacy_officer')
        
        retention_days = self._get_audit_retention_days(
            entity_type, operation, risk_level
        )
        
        return AuditRequirement(
            operation_type=operation,
            entity_type=entity_type,
            entity_id=data.get('id', 'new'),
            changes=changes or {},
            risk_level=risk_level,
            requires_approval=requires_approval,
            approval_roles=approval_roles,
            retention_days=retention_days
        )
    
    def check_compliance(
        self,
        context: BusinessContext,
        operation: str,
        entity_type: str,
        data: Dict[str, Any]
    ) -> List[ComplianceValidation]:
        """Check compliance requirements"""
        validations = []
        
        for compliance_type in context.compliance_requirements:
            validation = self._validate_compliance_type(
                compliance_type, context, operation, entity_type, data
            )
            if validation:
                validations.append(validation)
        
        return validations
    
    # Helper methods
    def _is_revenue_impacting(self, entity_type: str, data: Dict[str, Any]) -> bool:
        """Check if operation impacts revenue"""
        revenue_entities = {'billing', 'payment', 'invoice', 'pricing', 'subscription'}
        return (
            any(entity in entity_type.lower() for entity in revenue_entities) or
            data.get('affects_billing', False) or
            data.get('price_change', False)
        )
    
    def _is_outside_business_hours(self) -> bool:
        """Check if current time is outside business hours"""
        now = datetime.now(timezone.utc)
        return now.hour < 9 or now.hour >= 18 or now.weekday() >= 5
    
    def _has_active_dependencies(self, entity_type: str, entity_id: str) -> bool:
        """Check for active dependencies (would query other services)"""
        # This would typically query other services
        # For now, return False as placeholder
        return False
    
    def _get_retention_requirement(self, entity_type: str) -> int:
        """Get data retention requirement in days"""
        retention_map = {
            'invoice': 2555,  # 7 years
            'payment': 2555,  # 7 years
            'contract': 3650,  # 10 years
            'audit_log': 2555,  # 7 years
            'customer': 1095,  # 3 years after last activity
        }
        return retention_map.get(entity_type.lower(), 0)
    
    def _contains_personal_data(self, data: Dict[str, Any]) -> bool:
        """Check if data contains personal information"""
        personal_fields = {
            'email', 'phone', 'address', 'ssn', 'date_of_birth',
            'first_name', 'last_name', 'full_name'
        }
        return any(field in data for field in personal_fields)
    
    def _contains_health_data(self, data: Dict[str, Any]) -> bool:
        """Check if data contains health information"""
        health_fields = {
            'diagnosis', 'prescription', 'medical_history',
            'health_condition', 'treatment'
        }
        return any(field in data for field in health_fields)
    
    def _contains_payment_data(self, data: Dict[str, Any]) -> bool:
        """Check if data contains payment information"""
        payment_fields = {
            'credit_card', 'card_number', 'cvv', 'expiry_date',
            'bank_account', 'routing_number'
        }
        return any(field in data for field in payment_fields)
    
    def _is_pci_compliant_operation(self, operation: str, data: Dict[str, Any]) -> bool:
        """Check if operation is PCI compliant"""
        if operation == 'create':
            # Must use tokenization
            return data.get('tokenized', False)
        return True
    
    def _check_data_minimization(
        self, entity_type: str, data: Dict[str, Any]
    ) -> List[str]:
        """Check for unnecessary data collection"""
        # Define minimal required fields per entity type
        required_fields = {
            'customer': {'id', 'email', 'consent'},
            'order': {'id', 'customer_id', 'items', 'total'},
        }
        
        minimal_fields = required_fields.get(entity_type, set())
        unnecessary = [
            field for field in data.keys()
            if field not in minimal_fields and self._is_personal_field(field)
        ]
        
        return unnecessary
    
    def _is_personal_field(self, field: str) -> bool:
        """Check if field contains personal data"""
        personal_patterns = [
            'name', 'email', 'phone', 'address', 'birth',
            'gender', 'race', 'religion', 'political'
        ]
        return any(pattern in field.lower() for pattern in personal_patterns)
    
    def _detect_anomaly(
        self,
        context: BusinessContext,
        operation: str,
        entity_type: str,
        data: Dict[str, Any]
    ) -> bool:
        """Detect anomalous behavior patterns"""
        # Simplified anomaly detection
        # In production, this would use ML models or statistical analysis
        
        # Check for unusual operation patterns
        if operation == 'bulk_delete' and entity_type in self.CRITICAL_ENTITIES:
            return True
        
        # Check for unusual data volumes
        if len(str(data)) > 1000000:  # 1MB of data
            return True
        
        return False
    
    def _calculate_anomaly_score(
        self,
        context: BusinessContext,
        operation: str,
        data: Dict[str, Any]
    ) -> float:
        """Calculate anomaly score (0-100)"""
        score = 0.0
        
        # Factor 1: Operation risk
        if operation in self.HIGH_RISK_OPERATIONS:
            score += 30
        
        # Factor 2: Data volume
        data_size = len(str(data))
        if data_size > 100000:
            score += min(30, data_size / 10000)
        
        # Factor 3: Time-based anomaly
        if self._is_outside_business_hours():
            score += 20
        
        # Factor 4: User behavior
        # (Would typically check against user's historical patterns)
        score += 10
        
        return min(100, score)
    
    def _get_rate_limit(
        self,
        user_id: str,
        entity_type: str,
        operation: str
    ) -> Dict[str, Any]:
        """Get rate limit status for user"""
        # Simplified rate limiting
        # In production, this would use Redis or similar
        
        limits = {
            'create': {'customer': 10, 'order': 100, 'default': 1000},
            'update': {'customer': 50, 'order': 200, 'default': 2000},
            'delete': {'customer': 5, 'order': 20, 'default': 100},
        }
        
        limit = limits.get(operation, {}).get(entity_type, 
                          limits.get(operation, {}).get('default', 1000))
        
        # Placeholder - would check actual usage
        return {
            'exceeded': False,
            'current': 0,
            'limit': limit,
            'reset_time': datetime.now(timezone.utc) + timedelta(hours=1)
        }
    
    def _deep_inspect_fields(self, data: Dict[str, Any]) -> List[str]:
        """Deep inspection of field contents"""
        suspicious_patterns = []
        
        # Check for SQL injection patterns
        sql_patterns = ['DROP TABLE', 'SELECT *', 'UNION SELECT', '--', '/*']
        
        # Check for script injection patterns
        script_patterns = ['<script', 'javascript:', 'onerror=', 'onclick=']
        
        # Check for command injection patterns
        command_patterns = ['&&', '||', ';', '`', '$(', '${']
        
        data_str = str(data).upper()
        
        for pattern in sql_patterns:
            if pattern in data_str:
                suspicious_patterns.append(f'SQL injection pattern: {pattern}')
        
        for pattern in script_patterns:
            if pattern.upper() in data_str:
                suspicious_patterns.append(f'Script injection pattern: {pattern}')
        
        for pattern in command_patterns:
            if pattern in str(data):
                suspicious_patterns.append(f'Command injection pattern: {pattern}')
        
        return suspicious_patterns
    
    def _calculate_risk_level(
        self,
        context: BusinessContext,
        operation: str,
        entity_type: str,
        data: Dict[str, Any]
    ) -> str:
        """Calculate risk level for an operation"""
        risk_score = 0
        
        # Operation risk
        operation_risks = {
            'delete': 30,
            'bulk_update': 40,
            'bulk_delete': 50,
            'schema_migration': 60,
            'permission_change': 50,
        }
        risk_score += operation_risks.get(operation, 10)
        
        # Entity criticality
        if any(pattern in entity_type.lower() for pattern in self.CRITICAL_ENTITIES):
            risk_score += 30
        
        # Data sensitivity
        if self._contains_personal_data(data):
            risk_score += 20
        if self._contains_payment_data(data):
            risk_score += 30
        if self._contains_health_data(data):
            risk_score += 40
        
        # Context factors
        if context.is_privileged_operation:
            risk_score += 20
        if self._is_outside_business_hours():
            risk_score += 10
        
        # Map score to risk level
        if risk_score >= 80:
            return 'critical'
        elif risk_score >= 60:
            return 'high'
        elif risk_score >= 40:
            return 'medium'
        else:
            return 'low'
    
    def _get_audit_retention_days(
        self,
        entity_type: str,
        operation: str,
        risk_level: str
    ) -> int:
        """Get audit retention period based on risk and compliance"""
        base_retention = {
            'critical': 2555,  # 7 years
            'high': 1095,      # 3 years
            'medium': 365,     # 1 year
            'low': 90          # 90 days
        }
        
        # Override for specific entity types
        entity_retention = {
            'payment': 2555,   # 7 years (PCI DSS)
            'invoice': 2555,   # 7 years (financial)
            'customer': 1095,  # 3 years (GDPR)
            'audit_log': 2555, # 7 years
        }
        
        return max(
            base_retention.get(risk_level, 90),
            entity_retention.get(entity_type.lower(), 90)
        )
    
    def _validate_compliance_type(
        self,
        compliance_type: ComplianceType,
        context: BusinessContext,
        operation: str,
        entity_type: str,
        data: Dict[str, Any]
    ) -> Optional[ComplianceValidation]:
        """Validate specific compliance type"""
        if compliance_type == ComplianceType.GDPR:
            return self._validate_gdpr_compliance(context, operation, entity_type, data)
        elif compliance_type == ComplianceType.HIPAA:
            return self._validate_hipaa_compliance(context, operation, entity_type, data)
        elif compliance_type == ComplianceType.PCI_DSS:
            return self._validate_pci_compliance(context, operation, entity_type, data)
        elif compliance_type == ComplianceType.SOX:
            return self._validate_sox_compliance(context, operation, entity_type, data)
        
        return None
    
    def _validate_gdpr_compliance(
        self,
        context: BusinessContext,
        operation: str,
        entity_type: str,
        data: Dict[str, Any]
    ) -> ComplianceValidation:
        """GDPR-specific compliance validation"""
        violations = []
        remediation = []
        
        if self._contains_personal_data(data):
            # Check for consent
            if operation == 'create' and not data.get('consent_given'):
                violations.append('Missing user consent for data processing')
                remediation.append('Obtain explicit consent before processing')
            
            # Check for purpose limitation
            if data.get('processing_purpose') not in ['service_delivery', 'legal_obligation']:
                violations.append('Processing purpose not aligned with GDPR')
                remediation.append('Define clear processing purpose')
        
        return ComplianceValidation(
            compliance_type=ComplianceType.GDPR,
            is_compliant=len(violations) == 0,
            violations=violations,
            remediation_steps=remediation,
            blocking=len(violations) > 0
        )
    
    def _validate_hipaa_compliance(
        self,
        context: BusinessContext,
        operation: str,
        entity_type: str,
        data: Dict[str, Any]
    ) -> ComplianceValidation:
        """HIPAA-specific compliance validation"""
        violations = []
        remediation = []
        
        if self._contains_health_data(data):
            # Check for encryption
            if not data.get('encrypted_at_rest'):
                violations.append('Health data not encrypted at rest')
                remediation.append('Enable encryption for health data')
            
            # Check for access controls
            if 'healthcare_provider' not in context.user_roles:
                violations.append('Unauthorized access to health data')
                remediation.append('Ensure proper role-based access')
        
        return ComplianceValidation(
            compliance_type=ComplianceType.HIPAA,
            is_compliant=len(violations) == 0,
            violations=violations,
            remediation_steps=remediation,
            blocking=True  # HIPAA violations always block
        )
    
    def _validate_pci_compliance(
        self,
        context: BusinessContext,
        operation: str,
        entity_type: str,
        data: Dict[str, Any]
    ) -> ComplianceValidation:
        """PCI DSS compliance validation"""
        violations = []
        remediation = []
        
        if self._contains_payment_data(data):
            # Check for tokenization
            if 'card_number' in data and not data.get('tokenized'):
                violations.append('Card data not tokenized')
                remediation.append('Use payment tokenization service')
            
            # Check for PCI scope
            if not context.is_privileged_operation:
                violations.append('Payment data access outside PCI scope')
                remediation.append('Restrict access to PCI-compliant systems')
        
        return ComplianceValidation(
            compliance_type=ComplianceType.PCI_DSS,
            is_compliant=len(violations) == 0,
            violations=violations,
            remediation_steps=remediation,
            blocking=True  # PCI violations always block
        )
    
    def _validate_sox_compliance(
        self,
        context: BusinessContext,
        operation: str,
        entity_type: str,
        data: Dict[str, Any]
    ) -> ComplianceValidation:
        """SOX compliance validation for financial data"""
        violations = []
        remediation = []
        
        financial_entities = {'invoice', 'payment', 'revenue', 'financial_report'}
        
        if any(entity in entity_type.lower() for entity in financial_entities):
            # Check for audit trail
            if not context.requires_audit:
                violations.append('Financial operation without audit trail')
                remediation.append('Enable audit logging for financial operations')
            
            # Check for segregation of duties
            if operation in ['create', 'approve'] and 'finance' in context.user_roles:
                violations.append('Violation of segregation of duties')
                remediation.append('Separate creation and approval roles')
        
        return ComplianceValidation(
            compliance_type=ComplianceType.SOX,
            is_compliant=len(violations) == 0,
            violations=violations,
            remediation_steps=remediation,
            blocking=len(violations) > 0
        )


# Singleton instance
_enterprise_validator = None


def get_enterprise_business_validator() -> EnterpriseBusinessValidator:
    """Get singleton instance of enterprise business validator"""
    global _enterprise_validator
    if _enterprise_validator is None:
        _enterprise_validator = EnterpriseBusinessValidator()
    return _enterprise_validator