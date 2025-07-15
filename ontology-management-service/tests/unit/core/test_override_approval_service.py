"""Production Override Approval Service tests - 100% Real Implementation
This test suite uses the actual OverrideApprovalService, not mocks.
Zero Mock patterns - tests real business logic for security approval workflows.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import pytest
import pytest_asyncio
from core.auth import UserContext

# Import real service and models
from core.override_approval_service import (
    ApprovalStatus,
    OverrideApprovalRequest,
    OverrideApprovalService,
    OverrideType,
)


@pytest.fixture
def admin_user():
 """Create admin user context"""
 return UserContext(
 user_id = "admin_123",
 username = "admin_user",
 email = "admin@example.com",
 roles = ["admin", "schema_admin"],
 permissions = ["override.approve", "schema.admin"],
 metadata={"teams": ["platform"]},
 )


@pytest.fixture
def regular_user():
 """Create regular user context"""
 return UserContext(
 user_id = "user_456",
 username = "regular_user",
 email = "user@example.com",
 roles = ["developer"],
 permissions = ["schema.read", "schema.write"],
 metadata={"teams": ["development"]},
 )


@pytest.fixture
def security_officer():
 """Create security officer context"""
 return UserContext(
 user_id = "sec_789",
 username = "security_officer",
 email = "security@example.com",
 roles = ["security_officer", "admin"],
 permissions = ["override.approve", "security.admin"],
 metadata={"teams": ["security"]},
 )


@pytest.fixture
def lead_developer():
 """Create lead developer context"""
 return UserContext(
 user_id = "lead_101",
 username = "lead_developer",
 email = "lead@example.com",
 roles = ["lead_developer", "developer"],
 permissions = ["schema.admin", "override.request"],
 metadata={"teams": ["development", "architecture"]},
 )


@pytest.fixture
def override_service():
 """Create real OverrideApprovalService instance"""
 return OverrideApprovalService()


class TestOverrideApprovalServiceInitialization:
 """Test suite for OverrideApprovalService initialization."""

 def test_service_initialization(self, override_service):
 """Test that service initializes correctly."""
 assert isinstance(override_service._requests, dict)
 assert len(override_service._requests) == 0
 assert isinstance(override_service._approval_rules, dict)
 assert len(override_service._approval_rules) == 5 # 5 override types

 # Verify all override types have rules
 for override_type in OverrideType:
 assert override_type in override_service._approval_rules
 rules = override_service._approval_rules[override_type]
 assert "min_justification_length" in rules
 assert "required_roles" in rules
 assert "expires_in_hours" in rules
 assert "risk_level" in rules


class TestEmergencyOverrideWorkflow:
 """Test suite for emergency override approval workflow."""

 @pytest.mark.asyncio
 async def test_emergency_override_request_validation(
 self, override_service, admin_user
 ):
 """Test emergency override request with validation."""
 # Short justification should fail
 with pytest.raises(ValueError, match = "at least 50 characters"):
 await override_service.request_override(
 user = admin_user,
 override_type = OverrideType.EMERGENCY_ISSUE_BYPASS,
 justification = "Need to fix urgent issue", # Too short
 )

 # Valid justification should succeed
 valid_justification = (
 "Production incident IN-2025-001 requires immediate schema bypass "
 "to restore service functionality. Customer impact: 500+ users affected."
 )

 request = await override_service.request_override(
 user = admin_user,
 override_type = OverrideType.EMERGENCY_ISSUE_BYPASS,
 justification = valid_justification,
 resource_path = "/schemas/critical/user_data",
 operation = "emergency_patch",
 metadata={"incident_id": "IN-2025-001", "severity": "P1"},
 )

 assert request.id is not None
 assert request.override_type == OverrideType.EMERGENCY_ISSUE_BYPASS
 assert request.requested_by == admin_user.user_id
 assert request.status == ApprovalStatus.PENDING
 assert request.risk_level == "HIGH"
 assert request.expires_at > datetime.utcnow()

 @pytest.mark.asyncio
 async def test_emergency_override_approval(
 self, override_service, admin_user, security_officer
 ):
 """Test emergency override approval process."""
 # Request emergency override
 request = await override_service.request_override(
 user = admin_user,
 override_type = OverrideType.EMERGENCY_ISSUE_BYPASS,
 justification=(
 "Critical production incident requires immediate schema bypass. "
 "Service is down and affecting 1000+ users. Incident ID: INC-123."
 ),
 resource_path = "/schemas/production/critical",
 metadata={"incident_id": "INC-123", "severity": "P1"},
 )

 # Approve the override
 approved_request = await override_service.approve_override(
 request_id = request.id,
 approver = security_officer,
 comments = "Approved for emergency production fix",
 )

 assert approved_request.status == ApprovalStatus.APPROVED
 assert approved_request.approved_by == security_officer.user_id
 assert len(approved_request.current_approvals) == 1
 assert (
 approved_request.current_approvals[0]["approver_id"]
 == security_officer.user_id
 )

 @pytest.mark.asyncio
 async def test_emergency_override_expiration(self, override_service, admin_user):
 """Test emergency override expiration handling."""
 # Create a request
 request = await override_service.request_override(
 user = admin_user,
 override_type = OverrideType.EMERGENCY_ISSUE_BYPASS,
 justification = "Emergency fix for production issue - testing expiration handling",
 metadata={"test": "expiration"},
 )

 # Manually expire the request for testing
 request.expires_at = datetime.utcnow() - timedelta(minutes = 1)

 # Attempt to approve expired request
 with pytest.raises(ValueError, match = "Request has expired"):
 await override_service.approve_override(
 request_id = request.id, approver = admin_user, comments = "Too late"
 )

 # Verify status was updated to expired
 assert override_service._requests[request.id].status == ApprovalStatus.EXPIRED

 @pytest.mark.asyncio
 async def test_emergency_override_check(
 self, override_service, admin_user, security_officer
 ):
 """Test emergency override check functionality."""
 # Create and approve an emergency override
 request = await override_service.request_override(
 user = admin_user,
 override_type = OverrideType.EMERGENCY_ISSUE_BYPASS,
 justification = "Emergency production fix - testing override check functionality",
 resource_path = "/schemas/production/api",
 )

 await override_service.approve_override(
 request_id = request.id,
 approver = security_officer,
 comments = "Approved for testing",
 )

 # Check if override exists
 override_id = await override_service.check_override(
 user = admin_user,
 override_type = OverrideType.EMERGENCY_ISSUE_BYPASS,
 resource_path = "/schemas/production/api",
 )

 assert override_id == request.id

 # Check for non-matching resource
 override_id = await override_service.check_override(
 user = admin_user,
 override_type = OverrideType.EMERGENCY_ISSUE_BYPASS,
 resource_path = "/schemas/different/path",
 )

 assert override_id is None


class TestValidationBypassWorkflow:
 """Test suite for validation bypass approval workflow."""

 @pytest.mark.asyncio
 async def test_validation_bypass_request(self, override_service, admin_user):
 """Test validation bypass request creation."""
 # Short justification should fail
 with pytest.raises(ValueError, match = "at least 30 characters"):
 await override_service.request_override(
 user = admin_user,
 override_type = OverrideType.VALIDATION_SIZE_BYPASS,
 justification = "Need larger size", # Too short
 )

 # Valid request
 request = await override_service.request_override(
 user = admin_user,
 override_type = OverrideType.VALIDATION_SIZE_BYPASS,
 justification = "Large dataset import requires temporary size limit bypass for migration",


 resource_path = "/data/imports/large_dataset",
 metadata={
 "estimated_size_gb": 100,
 "risk_assessment": "low",
 "data_sensitivity": "internal",
 },
 )

 assert request.override_type == OverrideType.VALIDATION_SIZE_BYPASS
 assert request.status == ApprovalStatus.PENDING
 assert request.risk_level == "MEDIUM"
 assert request.requires_multi_approval is False

 @pytest.mark.asyncio
 async def test_validation_bypass_approval_longer_expiry(
 self, override_service, admin_user
 ):
 """Test validation bypass has longer expiry than emergency override."""
 # Request validation bypass
 request = await override_service.request_override(
 user = admin_user,
 override_type = OverrideType.VALIDATION_SIZE_BYPASS,
 justification = "Complex migration requires extended validation bypass for bulk import",


 )

 # Validation bypass should have 4-hour expiry
 time_diff = (request.expires_at - request.requested_at).total_seconds()
 assert 3.5 * 3600 < time_diff < 4.5 * 3600 # Around 4 hours

 # Compare with emergency override (2 hours)
 emergency_request = await override_service.request_override(
 user = admin_user,
 override_type = OverrideType.EMERGENCY_ISSUE_BYPASS,
 justification = "Emergency fix - comparing expiration times with validation bypass",
 )

 emergency_time_diff = (
 emergency_request.expires_at - emergency_request.requested_at
 ).total_seconds()
 assert 1.5 * 3600 < emergency_time_diff < 2.5 * 3600 # Around 2 hours
 assert time_diff > emergency_time_diff # Validation has longer expiry

 @pytest.mark.asyncio
 async def test_multiple_approval_types_coexist(self, override_service, admin_user):
 """Test that different override types can coexist."""
 # Request emergency override
 emergency_request = await override_service.request_override(
 user = admin_user,
 override_type = OverrideType.EMERGENCY_ISSUE_BYPASS,
 justification = "Critical incident requires immediate action to restore service",
 )

 # Request validation bypass
 validation_request = await override_service.request_override(
 user = admin_user,
 override_type = OverrideType.VALIDATION_SIZE_BYPASS,
 justification = "Large data import requires size validation bypass for migration",
 )

 # Request schema validation bypass
 schema_request = await override_service.request_override(
 user = admin_user,
 override_type = OverrideType.SCHEMA_VALIDATION_BYPASS,
 justification=(
 "Schema validation rules are preventing legitimate changes due to a known bug. "
 "This bypass is needed temporarily while the bug is being fixed in JIRA-1234."
 ),
 )

 # All should exist independently
 assert len(override_service._requests) >= 3
 assert emergency_request.id in override_service._requests
 assert validation_request.id in override_service._requests
 assert schema_request.id in override_service._requests

 # Verify different properties
 assert emergency_request.risk_level == "HIGH"
 assert validation_request.risk_level == "MEDIUM"
 assert schema_request.risk_level == "CRITICAL"
 assert schema_request.requires_multi_approval is True


class TestOverrideAuditingAndLogging:
 """Test suite for override approval auditing and logging."""

 @pytest.mark.asyncio
 async def test_get_request_audit_trail(
 self, override_service, admin_user, security_officer
 ):
 """Test that audit trail is properly tracked."""
 # Create override request
 request = await override_service.request_override(
 user = admin_user,
 override_type = OverrideType.EMERGENCY_ISSUE_BYPASS,
 justification = "Scheduled maintenance window requires temporary bypass for deployment",


 metadata={"deployment_id": "DEPLOY-123"},
 )

 # Approve the request
 await override_service.approve_override(
 request_id = request.id,
 approver = security_officer,
 comments = "Approved for scheduled maintenance",
 )

 # Use the override
 await override_service.use_override(request_id = request.id, user = admin_user)

 # Get audit trail
 audit_trail = override_service.get_request_audit_trail(request.id)

 assert "request" in audit_trail
 assert "timeline" in audit_trail

 timeline = audit_trail["timeline"]
 assert len(timeline) >= 3 # requested, approved, used

 # Check events
 events = [event["event"] for event in timeline]
 assert "requested" in events
 assert "approved" in events
 assert "used" in events


class TestOverrideSecurityValidation:
 """Test suite for override approval security validation."""

 @pytest.mark.asyncio
 async def test_invalid_approval_id_rejection(self, override_service, admin_user):
 """Test rejection of invalid approval IDs."""
 with pytest.raises(ValueError, match = "not found"):
 await override_service.approve_override(
 request_id = "invalid_id_12345",
 approver = admin_user,
 comments = "Trying to approve non-existent request",
 )

 @pytest.mark.asyncio
 async def test_already_approved_override_rejection(
 self, override_service, admin_user, security_officer
 ):
 """Test rejection of already approved overrides."""
 # Create and approve an override
 request = await override_service.request_override(
 user = admin_user,
 override_type = OverrideType.EMERGENCY_ISSUE_BYPASS,
 justification = "Testing double approval rejection - production incident requires fix",
 )

 # First approval
 await override_service.approve_override(
 request_id = request.id, approver = security_officer, comments = "First approval"
 )

 # Try to approve again
 with pytest.raises(ValueError, match = "not pending"):
 await override_service.approve_override(
 request_id = request.id,
 approver = admin_user,
 comments = "Second approval attempt",
 )


class TestOverrideConfigurationIntegration:
 """Test suite for override approval configuration integration."""

 def test_approval_rules_configuration(self, override_service):
 """Test that approval rules are properly configured."""
 rules = override_service._approval_rules

 # Test emergency override configuration
 emergency_rules = rules[OverrideType.EMERGENCY_ISSUE_BYPASS]
 assert emergency_rules["min_justification_length"] == 50
 assert emergency_rules["expires_in_hours"] == 2
 assert emergency_rules["risk_level"] == "HIGH"
 assert emergency_rules["requires_multi_approval"] is False

 # Test security bypass configuration
 security_rules = rules[OverrideType.SECURITY_CHECK_BYPASS]
 assert security_rules["min_justification_length"] == 200
 assert security_rules["expires_in_hours"] == 0.5 # 30 minutes
 assert security_rules["risk_level"] == "CRITICAL"
 assert security_rules["requires_multi_approval"] is True
 assert security_rules["approvers_required"] == 2

 @pytest.mark.asyncio
 async def test_multi_approval_requirement(
 self, override_service, admin_user, security_officer, lead_developer
 ):
 """Test multi-approval requirements for critical overrides."""
 # Schema validation bypass requires 2 approvals
 request = await override_service.request_override(
 user = lead_developer,
 override_type = OverrideType.SCHEMA_VALIDATION_BYPASS,
 justification=(
 "Critical schema update blocked by validator bug. This affects the main product "
 "schema and needs immediate attention to deploy security patches. The validator "
 "is incorrectly flagging valid changes. Ticket: PROD-911"
 ),
 )

 assert request.requires_multi_approval is True
 assert request.approvers_required == 2

 # First approval
 request = await override_service.approve_override(
 request_id = request.id,
 approver = admin_user,
 comments = "Verified the validator bug",
 )

 # Should still be pending
 assert request.status == ApprovalStatus.PENDING
 assert len(request.current_approvals) == 1

 # Second approval completes it
 request = await override_service.approve_override(
 request_id = request.id,
 approver = security_officer,
 comments = "Security review completed",
 )

 assert request.status == ApprovalStatus.APPROVED
 assert len(request.current_approvals) == 2


class TestRoleBasedApproval:
 """Test role-based approval requirements."""

 @pytest.mark.asyncio
 async def test_role_requirements_for_approval(
 self, override_service, regular_user, admin_user, security_officer
 ):
 """Test that only users with required roles can approve."""
 # Create a security check bypass request
 request = await override_service.request_override(
 user = admin_user,
 override_type = OverrideType.SECURITY_CHECK_BYPASS,
 justification=(
 "Emergency security patch deployment requires temporary bypass of security checks. "
 "The security vulnerability CVE-2025-001 needs immediate patching. Security team "
 "has reviewed and approved this temporary bypass. All changes will be audited and "
 "reviewed post-deployment. Risk assessment completed and documented in SEC-2025-001."
 ),
 )

 # Regular user should not be able to approve (lacks required roles)
 with pytest.raises(ValueError, match = "lacks required roles"):
 await override_service.approve_override(
 request_id = request.id,
 approver = regular_user,
 comments = "Trying to approve",
 )

 # Security officer has the required role
 approved = await override_service.approve_override(
 request_id = request.id,
 approver = security_officer,
 comments = "Security review completed",
 )

 assert approved.current_approvals[0]["approver_id"] == security_officer.user_id

 @pytest.mark.asyncio
 async def test_self_approval_prevention(self, override_service, admin_user):
 """Test that users cannot approve their own requests."""
 # Create request
 request = await override_service.request_override(
 user = admin_user,
 override_type = OverrideType.EMERGENCY_ISSUE_BYPASS,
 justification = "Testing self-approval prevention - urgent fix needed for production",
 )

 # Try to self-approve
 with pytest.raises(
 ValueError, match = "Cannot approve your own override request"
 ):
 await override_service.approve_override(
 request_id = request.id,
 approver = admin_user,
 comments = "Approving my own request",
 )


class TestPendingRequestsManagement:
 """Test pending requests management functionality."""

 @pytest.mark.asyncio
 async def test_get_pending_requests(
 self, override_service, admin_user, regular_user
 ):
 """Test retrieving pending requests."""
 # Create multiple requests
 requests = []
 for i in range(3):
 request = await override_service.request_override(
 user = admin_user if i % 2 == 0 else regular_user,
 override_type = OverrideType.VALIDATION_SIZE_BYPASS,
 justification = f"Test request {i} - need to bypass validation for large import job",
 )
 requests.append(request)

 # Get all pending requests
 pending = override_service.get_pending_requests()
 assert len(pending) == 3

 # Filter by approver roles
 pending_for_admin = override_service.get_pending_requests(["admin"])
 assert len(pending_for_admin) == 3 # Admin can approve validation bypasses

 pending_for_security = override_service.get_pending_requests(
 ["security_officer"]
 )
 assert (
 len(pending_for_security) == 0
 ) # Security officer not required for validation bypass
