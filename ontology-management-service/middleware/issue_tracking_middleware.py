"""
Issue Tracking Middleware V3 - Production Ready
엔터프라이즈급 이슈 추적, 감사, 승인 통합 미들웨어

주요 기능:
- 이슈 ID 요구사항 검증
- 사전 승인된 오버라이드 지원
- 포괄적인 감사 로깅
- FastAPI 공식 API만 사용 (내부 구조 의존성 제거)
"""
from typing import Optional, List, Dict, Any, Callable
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
import json
import os
from datetime import datetime

from core.auth import UserContext
from core.issue_tracking.issue_service import get_issue_service
from models.issue_tracking import IssueReference, parse_issue_reference, extract_issue_references
from arrakis_common import get_logger
from core.override_approval_service import override_approval_service, OverrideType

logger = get_logger(__name__)


class IssueTrackingMiddleware:
 """
 Middleware to enforce issue tracking requirements
 """

 # Operations that require issue tracking
 TRACKED_OPERATIONS = {
 # Schema operations (fixed paths - note the 's' in schemas)
 ("POST", "/api/v1/schemas/{branch_name}/object-types"): "schema",
 ("PUT", "/api/v1/schemas/{branch_name}/object-types/{type_id}"): "schema",
 ("DELETE", "/api/v1/schemas/{branch_name}/object-types/{type_id}"): "deletion",
 ("POST", "/api/v1/schemas/{branch_name}/link-types"): "schema",
 ("PUT", "/api/v1/schemas/{branch_name}/link-types/{type_id}"): "schema",
 ("DELETE", "/api/v1/schemas/{branch_name}/link-types/{type_id}"): "deletion",
 ("POST", "/api/v1/schemas/{branch_name}/action-types"): "schema",
 ("PUT", "/api/v1/schemas/{branch_name}/action-types/{type_id}"): "schema",
 ("DELETE", "/api/v1/schemas/{branch_name}/action-types/{type_id}"): "deletion",
 ("POST", "/api/v1/schemas/{branch_name}/function-types"): "schema",
 ("PUT", "/api/v1/schemas/{branch_name}/function-types/{type_id}"): "schema",
 ("DELETE", "/api/v1/schemas/{branch_name}/function-types/{type_id}"): "deletion",

 # ACL operations
 ("POST", "/api/v1/acl/policies"): "acl",
 ("PUT", "/api/v1/acl/policies/{policy_id}"): "acl",
 ("DELETE", "/api/v1/acl/policies/{policy_id}"): "acl",

 # Branch operations
 ("POST", "/api/v1/branches/{branch_name}/merge"): "merge",
 ("DELETE", "/api/v1/branches/{branch_name}"): "deletion",

 # Proposal operations
 ("POST", "/api/v1/proposals/{proposal_id}/merge"): "merge",
 }

 def __init__(self):
 self.issue_service = None

 async def dispatch(self, request: Request, call_next: Callable) -> Response:
 """FastAPI middleware dispatch method"""
 return await self.__call__(request, call_next)

 async def __call__(self, request: Request, call_next: Callable) -> Response:
 """Process request and enforce issue tracking"""
 # Skip if not a tracked operation
 operation_key = (request.method, request.url.path)
 change_type = None

 # Check if this is a tracked operation
 for tracked_key, tracked_type in self.TRACKED_OPERATIONS.items():
 method, path_pattern = tracked_key
 if method == request.method and self._matches_path_pattern(request.url.path, path_pattern):
 change_type = tracked_type
 break

 if not change_type:
 # Not a tracked operation, pass through
 return await call_next(request)

 # Initialize issue service if needed
 if not self.issue_service:
 self.issue_service = await get_issue_service()

 # Extract user context
 user = getattr(request.state, "user", None)
 if not user:
 # No user context, pass through (auth middleware should handle this)
 return await call_next(request)

 # Extract issue references from request
 issue_refs = await self._extract_issue_references(request)

 # Extract branch name from path
 branch_name = self._extract_branch_name(request.url.path)

 # Check for emergency override
 emergency_override = False
 override_justification = None

 if request.headers.get("X-Emergency-Override") == "true":
 # Check for pre-approved override
 override_request_id = request.headers.get("X-Override-Request-ID")

 if override_request_id:
 # Try to use pre-approved override
 try:
 valid = await override_approval_service.use_override(
 request_id = override_request_id,
 user = user
 )
 if valid:
 emergency_override = True
 override_justification = "Pre-approved override used"
 logger.info(f"Using pre-approved override {override_request_id} for {request.method} {request.url.path}")
 except Exception as e:
 logger.error(f"Failed to use pre-approved override: {e}")
 return JSONResponse(
 status_code = status.HTTP_403_FORBIDDEN,
 content={
 "error": "Invalid override request",
 "message": str(e)
 }
 )
 else:
 # Legacy path: Check authorization for immediate override
 if not user or not await self._is_authorized_for_emergency_override(user):
 # User not authorized for immediate override - suggest approval process
 logger.warning(
 f"Unauthorized emergency override attempt by {user.username if user else 'unknown'} "
 f"for {request.method} {request.url.path}"
 )
 return JSONResponse(
 status_code = status.HTTP_403_FORBIDDEN,
 content={
 "error": "Unauthorized for emergency override",
 "message": "Emergency override requires pre-approval. Use the override approval API to request permission.",
 "help": "POST /api/v1/override-approvals to request override approval"
 }
 )

 emergency_override = True
 override_justification = request.headers.get("X-Override-Justification", "")

 # Validate justification is provided and meaningful
 if not override_justification or len(override_justification.strip()) < 50:
 return JSONResponse(
 status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
 content={
 "error": "Invalid emergency override",
 "message": "Emergency override requires detailed justification (minimum 50 characters)"
 }
 )

 # Create retroactive approval request for audit
 try:
 approval_request = await override_approval_service.request_override(
 user = user,
 override_type = OverrideType.EMERGENCY_ISSUE_BYPASS,
 justification = override_justification + " [RETROACTIVE - Direct override used]",
 resource_path = request.url.path,
 operation = request.method,
 metadata={
 "change_type": change_type,
 "branch_name": branch_name,
 "retroactive": True
 }
 )
 logger.warning(f"Created retroactive override approval request: {approval_request.id}")
 except Exception as e:
 logger.error(f"Failed to create retroactive approval request: {e}")

 # Log emergency override with full context
 await self._log_emergency_override(
 user = user,
 method = request.method,
 path = request.url.path,
 change_type = change_type,
 branch_name = branch_name,
 justification = override_justification,
 request_headers = dict(request.headers),
 client_ip = getattr(request.client, "host", "unknown") if request.client else "unknown",
 override_request_id = override_request_id
 )

 # Validate issue requirements
 is_valid, error_message = await self.issue_service.validate_issue_requirement(
 user = user,
 change_type = change_type,
 branch_name = branch_name,
 issue_refs = issue_refs,
 emergency_override = emergency_override,
 override_justification = override_justification
 )

 if not is_valid:
 logger.warning(
 f"Issue validation failed for {request.method} {request.url.path} "
 f"by {user.username}: {error_message}"
 )

 return JSONResponse(
 status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
 content={
 "error": "Issue tracking requirement not met",
 "message": error_message,
 "change_type": change_type,
 "branch": branch_name,
 "help": "Include issue reference in X-Issue-ID header or request body",
 "examples": {
 "header": "X-Issue-ID: JIRA-123",
 "body_field": "issue_id: 'JIRA-123'",
 "multiple": "X-Issue-IDs: JIRA-123,GH-456",
 "emergency": {
 "header": "X-Emergency-Override: true",
 "justification": "X-Override-Justification: Critical production fix for data loss"
 }
 }
 }
 )

 # Store validated issues in request state for downstream use
 request.state.issue_refs = issue_refs
 request.state.emergency_override = emergency_override
 request.state.override_justification = override_justification

 # Continue with request
 response = await call_next(request)

 # If successful, log the change-issue link
 if 200 <= response.status_code < 300 and issue_refs:
 try:
 # Extract change ID from response if available
 change_id = await self._extract_change_id(response)

 if change_id and issue_refs:
 # Create change-issue link
 link = await self.issue_service.link_change_to_issues(
 change_id = change_id,
 change_type = change_type,
 branch_name = branch_name,
 user = user,
 primary_issue = issue_refs[0],
 related_issues = issue_refs[1:] if len(issue_refs) > 1 else None,
 emergency_override = emergency_override,
 override_justification = override_justification
 )

 logger.info(
 f"Linked change {change_id} to issues: "
 f"{[ref.get_display_name() for ref in issue_refs]}"
 )

 except Exception as e:
 logger.error(f"Failed to create change-issue link: {e}")

 return response

 async def _extract_issue_references(self, request: Request) -> List[IssueReference]:
 """Extract issue references from request headers and body"""
 issue_refs = []

 # Check headers (using safe access methods)
 # Single issue: X-Issue-ID: JIRA-123
 issue_id_header = request.headers.get("X-Issue-ID")
 if issue_id_header:
 ref = parse_issue_reference(issue_id_header)
 if ref:
 issue_refs.append(ref)

 # Multiple issues: X-Issue-IDs: JIRA-123,GH-456
 issue_ids_header = request.headers.get("X-Issue-IDs")
 if issue_ids_header:
 issue_ids = issue_ids_header.split(",")
 for issue_id in issue_ids:
 ref = parse_issue_reference(issue_id.strip())
 if ref:
 issue_refs.append(ref)

 # Check request body
 try:
 if request.method in ["POST", "PUT", "PATCH"]:
 # Read request body safely (handle multiple middleware scenario)
 # Check if body was already read by another middleware
 if hasattr(request.state, 'body'):
 body = request.state.body
 else:
 body = await request.body()
 # Store in request.state for downstream use (official API)
 request.state.body = body

 try:
 data = json.loads(body)

 # Check for issue_id field
 if isinstance(data, dict):
 if "issue_id" in data:
 ref = parse_issue_reference(str(data["issue_id"]))
 if ref and ref not in issue_refs:
 issue_refs.append(ref)

 # Check for issue_ids field
 if "issue_ids" in data and isinstance(data["issue_ids"], list):
 for issue_id in data["issue_ids"]:
 ref = parse_issue_reference(str(issue_id))
 if ref and ref not in issue_refs:
 issue_refs.append(ref)

 # Check commit message or description fields
 for field in ["commit_message", "description", "message", "comment"]:
 if field in data and isinstance(data[field], str):
 extracted = extract_issue_references(data[field])
 for ref in extracted:
 if ref not in issue_refs:
 issue_refs.append(ref)

 except json.JSONDecodeError:
 pass

 except Exception as e:
 logger.debug(f"Error extracting issues from body: {e}")

 return issue_refs

 def _matches_path_pattern(self, path: str, pattern: str) -> bool:
 """Check if path matches pattern with placeholders"""
 # Convert pattern to regex-like matching
 # e.g., /api/v1/schema/{branch_name}/object-types -> /api/v1/schema/.*/object-types

 pattern_parts = pattern.split("/")
 path_parts = path.split("/")

 if len(pattern_parts) != len(path_parts):
 return False

 for pattern_part, path_part in zip(pattern_parts, path_parts):
 if pattern_part.startswith("{") and pattern_part.endswith("}"):
 # This is a placeholder, any value matches
 continue
 elif pattern_part != path_part:
 return False

 return True

 def _extract_branch_name(self, path: str) -> str:
 """Extract branch name from path"""
 parts = path.split("/")

 # Look for common patterns
 for i, part in enumerate(parts):
 if part == "schemas" and i + 1 < len(parts): # Fixed: schemas not schema
 return parts[i + 1]
 elif part == "branches" and i + 1 < len(parts):
 return parts[i + 1]

 return "unknown"

 async def _extract_change_id(self, response: Response) -> Optional[str]:
 """Extract change ID from response headers (recommended approach)"""
 try:
 # Best practice: Get from response headers
 # Downstream services should set X-Change-ID header
 if "X-Change-ID" in response.headers:
 return response.headers["X-Change-ID"]

 # Alternative: Check other standard headers
 for header_name in ["X-Operation-ID", "X-Commit-ID", "X-Request-ID"]:
 if header_name in response.headers:
 return response.headers[header_name]

 # Note: Reading response body in middleware is not recommended
 # as it requires internal API access and may break with streaming responses
 # Instead, encourage downstream services to set appropriate headers

 except Exception as e:
 logger.debug(f"Could not extract change ID from headers: {e}")

 return None

 async def _is_authorized_for_emergency_override(self, user: UserContext) -> bool:
 """Check if user is authorized for emergency override"""
 # Only specific roles can use emergency override
 authorized_roles = {"admin", "security_officer", "incident_response"}
 user_roles = set(user.roles) if user.roles else set()

 # Check if user has any authorized role
 has_authorized_role = bool(authorized_roles.intersection(user_roles))

 # Additional check: user must not be suspended or locked
 # This would require integration with user service, for now we check metadata
 user_status = user.metadata.get("status", "active") if user.metadata else "active"
 is_active = user_status == "active"

 return has_authorized_role and is_active

 async def _log_emergency_override(self, **kwargs) -> None:
 """Log emergency override with comprehensive audit trail"""
 try:
 # Create detailed audit event
 audit_event = {
 "event_type": "EMERGENCY_OVERRIDE",
 "event_category": "SECURITY",
 "severity": "CRITICAL",
 "timestamp": datetime.utcnow().isoformat(),
 "user_id": kwargs.get("user").user_id,
 "username": kwargs.get("user").username,
 "method": kwargs.get("method"),
 "path": kwargs.get("path"),
 "change_type": kwargs.get("change_type"),
 "branch_name": kwargs.get("branch_name"),
 "justification": kwargs.get("justification"),
 "client_ip": kwargs.get("client_ip"),
 "override_request_id": kwargs.get("override_request_id"),
 "metadata": {
 "roles": kwargs.get("user").roles,
 "request_headers": self._sanitize_headers(kwargs.get("request_headers", {})),
 "pre_approved": bool(kwargs.get("override_request_id"))
 }
 }

 # Log to multiple destinations for critical events
 # 1. Application logs
 logger.critical(f"EMERGENCY_OVERRIDE: {json.dumps(audit_event)}")

 # 2. Try to send to audit service
 if hasattr(self, '_audit_client') and self._audit_client:
 try:
 await self._audit_client.log_event(audit_event)
 except Exception as audit_error:
 logger.error(f"Failed to send emergency override to audit service: {audit_error}")

 # 3. Write to local audit file as backup
 try:
 audit_file_path = "/var/log/oms/emergency_overrides.log"
 os.makedirs(os.path.dirname(audit_file_path), exist_ok = True)
 with open(audit_file_path, "a") as f:
 f.write(json.dumps(audit_event) + "\n")
 except Exception as file_error:
 logger.error(f"Failed to write emergency override to audit file: {file_error}")

 except Exception as e:
 logger.error(f"Critical error logging emergency override: {e}")
 # Don't fail the request due to logging errors, but ensure it's recorded
 logger.critical(f"EMERGENCY_OVERRIDE_LOG_FAILURE: user={kwargs.get('user', {}).get('username', 'unknown')} path={kwargs.get('path', 'unknown')}")

 def _sanitize_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
 """Sanitize headers to remove sensitive information before logging"""
 sensitive_headers = {"authorization", "cookie", "x-api-key", "x-auth-token"}
 sanitized = {}

 for key, value in headers.items():
 if key.lower() in sensitive_headers:
 sanitized[key] = "[REDACTED]"
 else:
 sanitized[key] = value

 return sanitized


def configure_issue_tracking(app):
 """Configure issue tracking middleware for the application"""
 middleware = IssueTrackingMiddleware()

 @app.middleware("http")
 async def issue_tracking_middleware(request: Request, call_next: Callable) -> Response:
 return await middleware(request, call_next)

 logger.info("Issue tracking middleware configured")
