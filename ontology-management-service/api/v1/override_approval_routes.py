"""
Override Approval API Routes
Endpoints for managing override approval workflow
"""
from typing import List, Optional

from arrakis_common import get_logger
from core.auth import UserContext, get_current_user
from core.override_approval_service import (
    ApprovalStatus,
    OverrideApprovalRequest,
    OverrideType,
    override_approval_service,
)
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

logger = get_logger(__name__)

router = APIRouter(prefix = "/api/v1/override-approvals", tags = ["override-approvals"])


class OverrideRequestCreate(BaseModel):
    """Request model for creating override approval requests"""
 override_type: OverrideType
 justification: str = Field(..., min_length = 10, max_length = 2000)
 resource_path: Optional[str] = None
 operation: Optional[str] = None
 metadata: Optional[dict] = None


class OverrideApprovalAction(BaseModel):
    """Model for approval/rejection actions"""
 action: str = Field(..., pattern = "^(approve|reject)$")
 comments: Optional[str] = Field(None, max_length = 1000)
 reason: Optional[str] = Field(None, max_length = 1000) # For rejections


@router.post("", response_model = OverrideApprovalRequest)
async def request_override(
    request_data: OverrideRequestCreate,
    user: UserContext = Depends(get_current_user)
):
    """
    Request an override approval

    Required fields:
    - override_type: Type of override being requested
    - justification: Detailed justification (min 10 chars based on type)

    Optional fields:
    - resource_path: Specific resource being accessed
    - operation: Operation being performed
    - metadata: Additional context
    """
    try:
    approval_request = await override_approval_service.request_override(
    user = user,
    override_type = request_data.override_type,
    justification = request_data.justification,
    resource_path = request_data.resource_path,
    operation = request_data.operation,
    metadata = request_data.metadata
    )

    logger.info(
    f"Override request created: {approval_request.id} by {user.username} "
    f"for {request_data.override_type}"
    )

    return approval_request

    except ValueError as e:
    raise HTTPException(status_code = 400, detail = str(e))
    except Exception as e:
    logger.error(f"Failed to create override request: {e}")
    raise HTTPException(status_code = 500, detail = "Failed to create override request")


@router.get("/pending", response_model = List[OverrideApprovalRequest])
async def get_pending_requests(
    user: UserContext = Depends(get_current_user)
):
    """
    Get pending override requests that the current user can approve

    Returns only requests where the user has appropriate approval roles
    """
    try:
    # Get user's roles to filter requests
    user_roles = user.roles or []

    pending_requests = override_approval_service.get_pending_requests(
    approver_roles = user_roles
    )

    # Filter out user's own requests (separation of duties)
    filtered_requests = [
    req for req in pending_requests
    if req.requested_by != user.user_id
    ]

    return filtered_requests

    except Exception as e:
    logger.error(f"Failed to get pending requests: {e}")
    raise HTTPException(status_code = 500, detail = "Failed to retrieve pending requests")


@router.get("/my-requests", response_model = List[OverrideApprovalRequest])
async def get_my_requests(
    status: Optional[ApprovalStatus] = Query(None),
    user: UserContext = Depends(get_current_user)
):
    """
    Get override requests created by the current user

    Optional query parameter:
    - status: Filter by approval status
    """
    try:
    # Get all user's requests
    my_requests = [
    req for req in override_approval_service._requests.values()
    if req.requested_by == user.user_id
    ]

    # Filter by status if specified
    if status:
    my_requests = [req for req in my_requests if req.status == status]

    # Sort by creation time (newest first)
    my_requests.sort(key = lambda x: x.requested_at, reverse = True)

    return my_requests

    except Exception as e:
    logger.error(f"Failed to get user requests: {e}")
    raise HTTPException(status_code = 500, detail = "Failed to retrieve user requests")


@router.get("/{request_id}", response_model = OverrideApprovalRequest)
async def get_request_details(
    request_id: str,
    user: UserContext = Depends(get_current_user)
):
    """Get details of a specific override request"""
    request = override_approval_service._requests.get(request_id)

    if not request:
    raise HTTPException(status_code = 404, detail = "Override request not found")

    # Users can only view their own requests or requests they can approve
    user_roles = set(user.roles or [])
    rules = override_approval_service._approval_rules.get(request.override_type, {})
    required_roles = set(rules.get("required_roles", []))

    can_view = (
    request.requested_by == user.user_id or # Own request
    bool(required_roles.intersection(user_roles)) # Can approve
    )

    if not can_view:
    raise HTTPException(status_code = 403, detail = "Not authorized to view this request")

    return request


@router.post("/{request_id}/action")
async def process_approval_action(
    request_id: str,
    action_data: OverrideApprovalAction,
    user: UserContext = Depends(get_current_user)
):
    """
    Approve or reject an override request

    Action can be:
    - approve: Approve the request (with optional comments)
    - reject: Reject the request (with required reason)
    """
    try:
    if action_data.action == "approve":
    updated_request = await override_approval_service.approve_override(
    request_id = request_id,
    approver = user,
    comments = action_data.comments
    )

    logger.info(
    f"Override request {request_id} approved by {user.username}. "
    f"Status: {updated_request.status}"
    )

    return {
    "status": "success",
    "message": f"Request {'approved' if updated_request.status == ApprovalStatus.APPROVED else 'partially approved'}",


    "request": updated_request
    }

    else: # reject
    if not action_data.reason:
    raise HTTPException(
    status_code = 400,
    detail = "Rejection reason is required"
    )

    updated_request = await override_approval_service.reject_override(
    request_id = request_id,
    rejector = user,
    reason = action_data.reason
    )

    logger.info(
    f"Override request {request_id} rejected by {user.username}. "
    f"Reason: {action_data.reason}"
    )

    return {
    "status": "success",
    "message": "Request rejected",
    "request": updated_request
    }

    except ValueError as e:
    raise HTTPException(status_code = 400, detail = str(e))
    except Exception as e:
    logger.error(f"Failed to process approval action: {e}")
    raise HTTPException(status_code = 500, detail = "Failed to process approval action")


@router.get("/{request_id}/audit-trail")
async def get_request_audit_trail(
    request_id: str,
    user: UserContext = Depends(get_current_user)
):
    """Get complete audit trail for an override request"""
    # Check if request exists
    request = override_approval_service._requests.get(request_id)
    if not request:
    raise HTTPException(status_code = 404, detail = "Override request not found")

    # Check authorization
    user_roles = set(user.roles or [])
    is_admin = "admin" in user_roles or "security_officer" in user_roles
    is_requester = request.requested_by == user.user_id

    if not (is_admin or is_requester):
    raise HTTPException(
    status_code = 403,
    detail = "Only admins or the requester can view audit trails"
    )

    audit_trail = override_approval_service.get_request_audit_trail(request_id)

    return audit_trail


@router.post("/{request_id}/use")
async def use_override(
    request_id: str,
    user: UserContext = Depends(get_current_user)
):
    """
    Use an approved override

    This endpoint is typically not called directly - the override is used
    automatically when the request ID is provided in the X-Override-Request-ID header
    """
    try:
    success = await override_approval_service.use_override(
    request_id = request_id,
    user = user
    )

    if success:
    return {
    "status": "success",
    "message": "Override used successfully",
    "request_id": request_id
    }

    except ValueError as e:
    raise HTTPException(status_code = 400, detail = str(e))
    except Exception as e:
    logger.error(f"Failed to use override: {e}")
    raise HTTPException(status_code = 500, detail = "Failed to use override")
