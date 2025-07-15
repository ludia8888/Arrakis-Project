"""
Override Approval Service
Manages approval workflow for emergency overrides and validation bypasses
"""
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import aiohttp
from arrakis_common import get_logger
from core.auth import UserContext
from pydantic import BaseModel, Field

logger = get_logger(__name__)


class OverrideType(str, Enum):
 """Types of overrides that require approval"""

 EMERGENCY_ISSUE_BYPASS = "emergency_issue_bypass"
 VALIDATION_SIZE_BYPASS = "validation_size_bypass"
 SCHEMA_VALIDATION_BYPASS = "schema_validation_bypass"
 SECURITY_CHECK_BYPASS = "security_check_bypass"
 ADMIN_CRITICAL_OPERATION = "admin_critical_operation"


class ApprovalStatus(str, Enum):
 """Status of override approval requests"""

 PENDING = "pending"
 APPROVED = "approved"
 REJECTED = "rejected"
 EXPIRED = "expired"
 USED = "used"


class OverrideApprovalRequest(BaseModel):
 """Model for override approval requests"""

 id: str = Field(default_factory = lambda: str(uuid.uuid4()))
 override_type: OverrideType
 requested_by: str
 requested_at: datetime = Field(default_factory = datetime.utcnow)
 justification: str
 resource_path: Optional[str] = None
 operation: Optional[str] = None
 metadata: Dict[str, Any] = Field(default_factory = dict)

 # Approval details
 status: ApprovalStatus = ApprovalStatus.PENDING
 approved_by: Optional[str] = None
 approved_at: Optional[datetime] = None
 rejection_reason: Optional[str] = None

 # Expiration and usage
 expires_at: datetime = Field(
 default_factory = lambda: datetime.utcnow() + timedelta(hours = 1)
 )
 valid_for_single_use: bool = True
 use_count: int = 0
 used_at: Optional[datetime] = None

 # Risk assessment
 risk_level: str = "HIGH"
 requires_multi_approval: bool = False
 approvers_required: int = 1
 current_approvals: List[Dict[str, Any]] = Field(default_factory = list)


class NotificationService:
 """
 Production-ready notification service for override approval workflow
 Supports multiple notification channels: Slack, email, webhook
 """

 def __init__(self):
 self.slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
 self.email_service_url = os.getenv("EMAIL_SERVICE_URL")
 self.notification_webhook_url = os.getenv("NOTIFICATION_WEBHOOK_URL")

 async def notify_approvers(
 self, request: OverrideApprovalRequest, required_roles: List[str]
 ) -> None:
 """Send notifications to potential approvers"""
 try:
 message = self._format_approval_request_message(request, required_roles)

 # Send to multiple notification channels
 tasks = []

 if self.slack_webhook_url:
 tasks.append(self._send_slack_notification(message))

 if self.email_service_url:
 tasks.append(self._send_email_notification(request, required_roles))

 if self.notification_webhook_url:
 tasks.append(
 self._send_webhook_notification(request, "approval_required")
 )

 # Execute all notifications concurrently
 if tasks:
 import asyncio

 await asyncio.gather(*tasks, return_exceptions = True)
 else:
 # Fallback: log notification
 logger.warning(
 f"NOTIFICATION: Override request {request.id} requires approval from roles: {required_roles}"
 )

 except Exception as e:
 logger.error(f"Failed to send approval notifications: {e}")

 async def notify_rejection(
 self, request: OverrideApprovalRequest, rejector_username: str, reason: str
 ) -> None:
 """Notify requester of rejection"""
 try:
 message = self._format_rejection_message(request, rejector_username, reason)

 # Send rejection notification
 tasks = []

 if self.slack_webhook_url:
 tasks.append(self._send_slack_notification(message, color = "danger"))

 if self.notification_webhook_url:
 tasks.append(
 self._send_webhook_notification(
 request,
 "rejected",
 {"rejector": rejector_username, "reason": reason},
 )
 )

 if tasks:
 import asyncio

 await asyncio.gather(*tasks, return_exceptions = True)
 else:
 # Fallback: log notification
 logger.info(
 f"NOTIFICATION: Override request {request.id} rejected by {rejector_username}: {reason}"
 )

 except Exception as e:
 logger.error(f"Failed to send rejection notification: {e}")

 def _format_approval_request_message(
 self, request: OverrideApprovalRequest, required_roles: List[str]
 ) -> str:
 """Format approval request message"""
 return """
🚨 **Override Approval Required**

**Type**: {request.override_type.value}
**Requested by**: {request.requested_by}
**Justification**: {request.justification}
**Risk Level**: {request.risk_level}
**Required Roles**: {', '.join(required_roles)}
**Resource**: {request.resource_path or 'N/A'}
**Operation**: {request.operation or 'N/A'}

**Request ID**: {request.id}
**Time**: {request.requested_at.isoformat()}

Please review and approve/reject this override request.
 """.strip()

 def _format_rejection_message(
 self, request: OverrideApprovalRequest, rejector: str, reason: str
 ) -> str:
 """Format rejection message"""
 return """
❌ **Override Request Rejected**

**Request ID**: {request.id}
**Type**: {request.override_type.value}
**Requested by**: {request.requested_by}
**Rejected by**: {rejector}
**Reason**: {reason}
**Time**: {datetime.utcnow().isoformat()}

The override request has been denied.
 """.strip()

 async def _send_slack_notification(
 self, message: str, color: str = "warning"
 ) -> None:
 """Send notification to Slack"""
 if not self.slack_webhook_url:
 return

 try:
 payload = {
 "text": "Override Approval Notification",
 "attachments": [
 {"color": color, "text": message, "mrkdwn_in": ["text"]}
 ],
 }

 async with aiohttp.ClientSession() as session:
 async with session.post(
 self.slack_webhook_url,
 json = payload,
 timeout = aiohttp.ClientTimeout(total = 10),
 ) as response:
 if response.status == 200:
 logger.debug("Slack notification sent successfully")
 else:
 logger.error(
 f"Failed to send Slack notification: HTTP {response.status}"
 )

 except Exception as e:
 logger.error(f"Error sending Slack notification: {e}")

 async def _send_email_notification(
 self, request: OverrideApprovalRequest, required_roles: List[str]
 ) -> None:
 """Send email notification"""
 if not self.email_service_url:
 return

 try:
 payload = {
 "to": self._get_role_emails(required_roles),
 "subject": f"Override Approval Required - {request.override_type.value}",
 "body": self._format_approval_request_message(request, required_roles),
 "priority": "high" if request.risk_level == "HIGH" else "normal",
 }

 async with aiohttp.ClientSession() as session:
 async with session.post(
 f"{self.email_service_url}/send",
 json = payload,
 timeout = aiohttp.ClientTimeout(total = 15),
 ) as response:
 if response.status == 200:
 logger.debug("Email notification sent successfully")
 else:
 logger.error(
 f"Failed to send email notification: HTTP {response.status}"
 )

 except Exception as e:
 logger.error(f"Error sending email notification: {e}")

 async def _send_webhook_notification(
 self,
 request: OverrideApprovalRequest,
 event_type: str,
 extra_data: Optional[Dict] = None,
 ) -> None:
 """Send webhook notification"""
 if not self.notification_webhook_url:
 return

 try:
 payload = {
 "event_type": event_type,
 "request_id": request.id,
 "override_type": request.override_type.value,
 "requested_by": request.requested_by,
 "timestamp": datetime.utcnow().isoformat(),
 "data": request.dict(),
 **(extra_data or {}),
 }

 async with aiohttp.ClientSession() as session:
 async with session.post(
 self.notification_webhook_url,
 json = payload,
 timeout = aiohttp.ClientTimeout(total = 10),
 ) as response:
 if response.status in (200, 201, 202):
 logger.debug("Webhook notification sent successfully")
 else:
 logger.error(
 f"Failed to send webhook notification: HTTP {response.status}"
 )

 except Exception as e:
 logger.error(f"Error sending webhook notification: {e}")

 def _get_role_emails(self, required_roles: List[str]) -> List[str]:
 """Get email addresses for required roles"""
 # In production, this would query the user service for role members
 role_emails = {
 "admin": ["admin@company.com"],
 "security": ["security@company.com"],
 "operations": ["ops@company.com"],
 "developer": ["dev-leads@company.com"],
 }

 emails = []
 for role in required_roles:
 emails.extend(role_emails.get(role, []))

 return list(set(emails)) # Remove duplicates


class OverrideApprovalService:
 """
 Service for managing override approval workflow

 Key features:
 - Request creation with justification
 - Multi-level approval for high-risk operations
 - Time-limited approvals
 - Audit trail for all override requests
 - Integration with notification system
 """

 def __init__(self):
 # In-memory storage for demo (should be persisted in production)
 self._requests: Dict[str, OverrideApprovalRequest] = {}
 self._approval_rules = self._initialize_approval_rules()
 self._notification_service = NotificationService()

 def _initialize_approval_rules(self) -> Dict[OverrideType, Dict[str, Any]]:
 """Initialize approval rules for different override types"""
 return {
 OverrideType.EMERGENCY_ISSUE_BYPASS: {
 "min_justification_length": 50,
 "required_roles": ["admin", "lead_developer", "incident_response"],
 "expires_in_hours": 2,
 "risk_level": "HIGH",
 "requires_multi_approval": False,
 },
 OverrideType.VALIDATION_SIZE_BYPASS: {
 "min_justification_length": 30,
 "required_roles": ["admin", "data_admin"],
 "expires_in_hours": 4,
 "risk_level": "MEDIUM",
 "requires_multi_approval": False,
 },
 OverrideType.SCHEMA_VALIDATION_BYPASS: {
 "min_justification_length": 100,
 "required_roles": ["admin", "schema_admin"],
 "expires_in_hours": 1,
 "risk_level": "CRITICAL",
 "requires_multi_approval": True,
 "approvers_required": 2,
 },
 OverrideType.SECURITY_CHECK_BYPASS: {
 "min_justification_length": 200,
 "required_roles": ["security_officer", "admin"],
 "expires_in_hours": 0.5, # 30 minutes
 "risk_level": "CRITICAL",
 "requires_multi_approval": True,
 "approvers_required": 2,
 },
 OverrideType.ADMIN_CRITICAL_OPERATION: {
 "min_justification_length": 50,
 "required_roles": ["super_admin"],
 "expires_in_hours": 1,
 "risk_level": "HIGH",
 "requires_multi_approval": True,
 "approvers_required": 2,
 },
 }

 async def request_override(
 self,
 user: UserContext,
 override_type: OverrideType,
 justification: str,
 resource_path: Optional[str] = None,
 operation: Optional[str] = None,
 metadata: Optional[Dict[str, Any]] = None,
 ) -> OverrideApprovalRequest:
 """
 Request an override approval

 Args:
 user: User requesting the override
 override_type: Type of override being requested
 justification: Detailed justification for the override
 resource_path: Resource being accessed (if applicable)
 operation: Operation being performed (if applicable)
 metadata: Additional context

 Returns:
 OverrideApprovalRequest object

 Raises:
 ValueError: If request is invalid
 """
 # Validate request
 rules = self._approval_rules.get(override_type, {})

 # Check justification length
 min_length = rules.get("min_justification_length", 50)
 if len(justification.strip()) < min_length:
 raise ValueError(f"Justification must be at least {min_length} characters")

 # Create request
 request = OverrideApprovalRequest(
 override_type = override_type,
 requested_by = user.user_id,
 justification = justification,
 resource_path = resource_path,
 operation = operation,
 metadata = metadata or {},
 expires_at = datetime.utcnow()
 + timedelta(hours = rules.get("expires_in_hours", 1)),
 risk_level = rules.get("risk_level", "HIGH"),
 requires_multi_approval = rules.get("requires_multi_approval", False),
 approvers_required = rules.get("approvers_required", 1),
 )

 # Store request
 self._requests[request.id] = request

 # Log request creation
 logger.warning(
 f"OVERRIDE_REQUEST_CREATED: Type={override_type}, User={user.username}, "
 f"ID={request.id}, Risk={request.risk_level}"
 )

 # Send notifications to approvers
 await self._notification_service.notify_approvers(
 request, rules.get("required_roles", [])
 )

 return request

 async def approve_override(
 self, request_id: str, approver: UserContext, comments: Optional[str] = None
 ) -> OverrideApprovalRequest:
 """
 Approve an override request

 Args:
 request_id: ID of the request to approve
 approver: User approving the request
 comments: Optional approval comments

 Returns:
 Updated OverrideApprovalRequest

 Raises:
 ValueError: If approval is invalid
 """
 request = self._requests.get(request_id)
 if not request:
 raise ValueError(f"Override request {request_id} not found")

 # Check if already processed
 if request.status != ApprovalStatus.PENDING:
 raise ValueError(f"Request is not pending (status: {request.status})")

 # Check if expired
 if datetime.utcnow() > request.expires_at:
 request.status = ApprovalStatus.EXPIRED
 raise ValueError("Request has expired")

 # Check approver authorization
 rules = self._approval_rules.get(request.override_type, {})
 required_roles = set(rules.get("required_roles", []))
 approver_roles = set(approver.roles or [])

 if not required_roles.intersection(approver_roles):
 raise ValueError(f"Approver lacks required roles: {required_roles}")

 # Check if approver is not the requester (separation of duties)
 if approver.user_id == request.requested_by:
 raise ValueError("Cannot approve your own override request")

 # Add approval
 approval = {
 "approver_id": approver.user_id,
 "approver_username": approver.username,
 "approved_at": datetime.utcnow().isoformat(),
 "comments": comments,
 }
 request.current_approvals.append(approval)

 # Check if enough approvals
 if len(request.current_approvals) >= request.approvers_required:
 request.status = ApprovalStatus.APPROVED
 request.approved_by = approver.user_id
 request.approved_at = datetime.utcnow()

 logger.warning(
 f"OVERRIDE_APPROVED: ID={request_id}, Type={request.override_type}, "
 f"Approver={approver.username}, Total approvals={len(request.current_approvals)}"
 )
 else:
 logger.info(
 f"OVERRIDE_PARTIAL_APPROVAL: ID={request_id}, "
 f"Approvals={len(request.current_approvals)}/{request.approvers_required}"
 )

 return request

 async def reject_override(
 self, request_id: str, rejector: UserContext, reason: str
 ) -> OverrideApprovalRequest:
 """
 Reject an override request

 Args:
 request_id: ID of the request to reject
 rejector: User rejecting the request
 reason: Reason for rejection

 Returns:
 Updated OverrideApprovalRequest
 """
 request = self._requests.get(request_id)
 if not request:
 raise ValueError(f"Override request {request_id} not found")

 if request.status != ApprovalStatus.PENDING:
 raise ValueError(f"Request is not pending (status: {request.status})")

 # Check rejector authorization
 rules = self._approval_rules.get(request.override_type, {})
 required_roles = set(rules.get("required_roles", []))
 rejector_roles = set(rejector.roles or [])

 if not required_roles.intersection(rejector_roles):
 raise ValueError(f"Rejector lacks required roles: {required_roles}")

 # Reject request
 request.status = ApprovalStatus.REJECTED
 request.rejection_reason = reason

 logger.warning(
 f"OVERRIDE_REJECTED: ID={request_id}, Type={request.override_type}, "
 f"Rejector={rejector.username}, Reason={reason}"
 )

 # Notify requester of rejection
 await self._notification_service.notify_rejection(
 request, rejector.username, reason
 )

 return request

 async def use_override(self, request_id: str, user: UserContext) -> bool:
 """
 Use an approved override

 Args:
 request_id: ID of the approved override
 user: User using the override

 Returns:
 True if override was successfully used

 Raises:
 ValueError: If override cannot be used
 """
 request = self._requests.get(request_id)
 if not request:
 raise ValueError(f"Override request {request_id} not found")

 # Check if approved
 if request.status != ApprovalStatus.APPROVED:
 raise ValueError(f"Override not approved (status: {request.status})")

 # Check if expired
 if datetime.utcnow() > request.expires_at:
 request.status = ApprovalStatus.EXPIRED
 raise ValueError("Override has expired")

 # Check if already used (for single-use overrides)
 if request.valid_for_single_use and request.use_count > 0:
 request.status = ApprovalStatus.USED
 raise ValueError("Override has already been used")

 # Check if correct user
 if user.user_id != request.requested_by:
 raise ValueError("Override can only be used by the requester")

 # Mark as used
 request.use_count += 1
 request.used_at = datetime.utcnow()

 if request.valid_for_single_use:
 request.status = ApprovalStatus.USED

 logger.critical(
 f"OVERRIDE_USED: ID={request_id}, Type={request.override_type}, "
 f"User={user.username}, Resource={request.resource_path}"
 )

 return True

 async def check_override(
 self,
 user: UserContext,
 override_type: OverrideType,
 resource_path: Optional[str] = None,
 ) -> Optional[str]:
 """
 Check if user has a valid override approval

 Args:
 user: User to check
 override_type: Type of override needed
 resource_path: Resource being accessed

 Returns:
 Request ID if valid override exists, None otherwise
 """
 for request_id, request in self._requests.items():
 if (
 request.requested_by == user.user_id
 and request.override_type == override_type
 and request.status == ApprovalStatus.APPROVED
 and datetime.utcnow() <= request.expires_at
 ):
 # Check resource match if specified
 if resource_path and request.resource_path:
 if request.resource_path != resource_path:
 continue

 # Check if not already used
 if request.valid_for_single_use and request.use_count > 0:
 continue

 return request_id

 return None

 def get_pending_requests(
 self, approver_roles: Optional[List[str]] = None
 ) -> List[OverrideApprovalRequest]:
 """Get all pending override requests, optionally filtered by approver roles"""
 pending = []

 for request in self._requests.values():
 if request.status != ApprovalStatus.PENDING:
 continue

 if datetime.utcnow() > request.expires_at:
 request.status = ApprovalStatus.EXPIRED
 continue

 # Filter by approver roles if specified
 if approver_roles:
 rules = self._approval_rules.get(request.override_type, {})
 required_roles = set(rules.get("required_roles", []))
 if not required_roles.intersection(set(approver_roles)):
 continue

 pending.append(request)

 return pending

 def get_request_audit_trail(self, request_id: str) -> Dict[str, Any]:
 """Get complete audit trail for an override request"""
 request = self._requests.get(request_id)
 if not request:
 return {}

 return {
 "request": request.dict(),
 "timeline": [
 {
 "event": "requested",
 "timestamp": request.requested_at.isoformat(),
 "user": request.requested_by,
 },
 *[
 {
 "event": "approved",
 "timestamp": approval["approved_at"],
 "user": approval["approver_username"],
 "comments": approval.get("comments"),
 }
 for approval in request.current_approvals
 ],
 *(
 [
 {
 "event": "used",
 "timestamp": request.used_at.isoformat(),
 "user": request.requested_by,
 }
 ]
 if request.used_at
 else []
 ),
 ],
 }


# Global instance for easy access
override_approval_service = OverrideApprovalService()
