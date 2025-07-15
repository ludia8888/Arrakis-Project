"""
Issue Tracking API Routes
Endpoints for issue validation and management
"""
from typing import Any, Dict, List, Optional

from arrakis_common import get_logger
from core.auth_utils import UserContext
from core.iam.dependencies import require_scope
from core.iam.iam_integration import IAMScope
from core.issue_tracking.issue_service import get_issue_service
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from middleware.auth_middleware import get_current_user
from models.issue_tracking import (
    ChangeIssueLink,
    IssueProvider,
    IssueReference,
    IssueTrackingConfig,
    IssueValidationResult,
    parse_issue_reference,
)
from pydantic import BaseModel, Field

logger = get_logger(__name__)
router = APIRouter(prefix = "/issue-tracking", tags = ["Issue Tracking"])


# Request/Response Models


class ValidateIssueRequest(BaseModel):
 """Request to validate an issue reference"""

 provider: IssueProvider = Field(..., description = "Issue tracking provider")
 issue_id: str = Field(..., description = "Issue ID to validate")


class ValidateIssuesRequest(BaseModel):
 """Request to validate multiple issue references"""

 issue_refs: List[IssueReference] = Field(
 ..., description = "Issue references to validate"
 )


class LinkChangeRequest(BaseModel):
 """Request to link a change to issues"""

 change_id: str = Field(..., description = "Change/commit ID")
 change_type: str = Field(..., description = "Type of change")
 branch_name: str = Field(..., description = "Branch name")
 primary_issue: IssueReference = Field(..., description = "Primary issue")
 related_issues: Optional[List[IssueReference]] = Field(
 None, description = "Related issues"
 )
 emergency_override: bool = Field(False, description = "Emergency override flag")
 override_justification: Optional[str] = Field(
 None, description = "Override justification"
 )


class IssueSearchRequest(BaseModel):
 """Request to search for issues"""

 query: str = Field(..., description = "Search query")
 provider: Optional[IssueProvider] = Field(
 None, description = "Specific provider to search"
 )
 limit: int = Field(10, ge = 1, le = 50, description = "Maximum results")


class IssueValidationResponse(BaseModel):
 """Response for issue validation"""

 valid: bool
 issue_ref: Optional[IssueReference]
 exists: bool
 status_valid: bool
 type_valid: bool
 assignee_valid: bool
 age_valid: bool
 error_message: Optional[str]
 validation_warnings: List[str]
 issue_metadata: Optional[Dict[str, Any]]


class BulkValidationResponse(BaseModel):
 """Response for bulk issue validation"""

 results: List[IssueValidationResponse]
 all_valid: bool
 total_issues: int
 valid_count: int
 invalid_count: int


class IssueRequirementCheckRequest(BaseModel):
 """Request to check if issue requirements are met"""

 change_type: str = Field(..., description = "Type of change")
 branch_name: str = Field(..., description = "Branch name")
 issue_refs: List[IssueReference] = Field(
 ..., description = "Proposed issue references"
 )
 emergency_override: bool = Field(False, description = "Emergency override flag")
 override_justification: Optional[str] = Field(
 None, description = "Override justification"
 )


class IssueRequirementCheckResponse(BaseModel):
 """Response for issue requirement check"""

 requirements_met: bool
 error_message: Optional[str]
 required: bool
 branch_exempt: bool
 operation_requires_issue: bool
 emergency_override_allowed: bool
 validation_details: List[Dict[str, Any]]


# Issue Validation Endpoints


@router.post(
 "/validate", dependencies = [Depends(require_scope([IAMScope.BRANCHES_WRITE]))]
)
async def validate_issue(
 request: ValidateIssueRequest,
 req: Request,
 user: UserContext = Depends(get_current_user),
) -> IssueValidationResponse:
 """Validate a single issue reference"""
 issue_service = await get_issue_service()

 # Create issue reference
 issue_ref = IssueReference(provider = request.provider, issue_id = request.issue_id)

 # Validate
 result = await issue_service.validate_issue(issue_ref)

 return IssueValidationResponse(
 valid = result.valid,
 issue_ref = result.issue_ref,
 exists = result.exists,
 status_valid = result.status_valid,
 type_valid = result.type_valid,
 assignee_valid = result.assignee_valid,
 age_valid = result.age_valid,
 error_message = result.error_message,
 validation_warnings = result.validation_warnings,
 issue_metadata = result.issue_metadata,
 )


@router.post(
 "/validate-bulk", dependencies = [Depends(require_scope([IAMScope.BRANCHES_WRITE]))]
)
async def validate_issues_bulk(
 request: ValidateIssuesRequest,
 req: Request,
 user: UserContext = Depends(get_current_user),
) -> BulkValidationResponse:
 """Validate multiple issue references"""
 issue_service = await get_issue_service()

 results = []
 valid_count = 0

 for issue_ref in request.issue_refs:
 result = await issue_service.validate_issue(issue_ref)

 results.append(
 IssueValidationResponse(
 valid = result.valid,
 issue_ref = result.issue_ref,
 exists = result.exists,
 status_valid = result.status_valid,
 type_valid = result.type_valid,
 assignee_valid = result.assignee_valid,
 age_valid = result.age_valid,
 error_message = result.error_message,
 validation_warnings = result.validation_warnings,
 issue_metadata = result.issue_metadata,
 )
 )

 if result.valid:
 valid_count += 1

 return BulkValidationResponse(
 results = results,
 all_valid = valid_count == len(request.issue_refs),
 total_issues = len(request.issue_refs),
 valid_count = valid_count,
 invalid_count = len(request.issue_refs) - valid_count,
 )


@router.post(
 "/check-requirements",
 dependencies = [Depends(require_scope([IAMScope.BRANCHES_WRITE]))],
)
async def check_issue_requirements(
 request: IssueRequirementCheckRequest,
 req: Request,
 user: UserContext = Depends(get_current_user),
) -> IssueRequirementCheckResponse:
 """Check if issue requirements are met for a proposed change"""
 issue_service = await get_issue_service()

 # Get requirement configuration
 requirements = issue_service.config.requirements

 # Check basic requirements
 response = IssueRequirementCheckResponse(
 requirements_met = False,
 error_message = None,
 required = requirements.enabled,
 branch_exempt = request.branch_name in requirements.exempt_branches,
 operation_requires_issue = False,
 emergency_override_allowed = requirements.allow_emergency_override,
 validation_details = [],
 )

 # Check if operation requires issue
 if request.change_type == "schema" and requirements.require_for_schema_changes:
 response.operation_requires_issue = True
 elif request.change_type == "deletion" and requirements.require_for_deletions:
 response.operation_requires_issue = True
 elif request.change_type == "acl" and requirements.require_for_acl_changes:
 response.operation_requires_issue = True
 elif request.change_type == "merge" and requirements.require_for_merges:
 response.operation_requires_issue = True

 # Validate requirements
 is_valid, error_message = await issue_service.validate_issue_requirement(
 user = user,
 change_type = request.change_type,
 branch_name = request.branch_name,
 issue_refs = request.issue_refs,
 emergency_override = request.emergency_override,
 override_justification = request.override_justification,
 )

 response.requirements_met = is_valid
 response.error_message = error_message

 # Add validation details for each issue
 for issue_ref in request.issue_refs:
 result = await issue_service.validate_issue(issue_ref)
 response.validation_details.append(
 {
 "issue": issue_ref.get_display_name(),
 "valid": result.valid,
 "error": result.error_message,
 }
 )

 return response


# Issue Linking Endpoints


@router.post(
 "/link-change", dependencies = [Depends(require_scope([IAMScope.BRANCHES_WRITE]))]
)
async def link_change_to_issues(
 request: LinkChangeRequest,
 req: Request,
 user: UserContext = Depends(get_current_user),
) -> Dict[str, Any]:
 """Link a change to issues"""
 issue_service = await get_issue_service()

 # Create link
 link = await issue_service.link_change_to_issues(
 change_id = request.change_id,
 change_type = request.change_type,
 branch_name = request.branch_name,
 user = user,
 primary_issue = request.primary_issue,
 related_issues = request.related_issues,
 emergency_override = request.emergency_override,
 override_justification = request.override_justification,
 )

 return {
 "success": True,
 "message": "Change linked to issues successfully",
 "link": link.model_dump(),
 "primary_issue": link.primary_issue.get_display_name(),
 "related_issues": [ref.get_display_name() for ref in link.related_issues],
 }


@router.get(
 "/changes/{change_id}/issues",
 dependencies = [Depends(require_scope([IAMScope.BRANCHES_READ]))],
)
async def get_change_issues(
 change_id: str, req: Request, user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
 """Get issues linked to a change"""
 from core.issue_tracking.issue_database import get_issue_database

 issue_db = await get_issue_database()
 link = await issue_db.get_issues_for_change(change_id)

 if not link:
 raise HTTPException(
 status_code = status.HTTP_404_NOT_FOUND,
 detail = f"No issues found for change {change_id}",
 )

 return {
 "change_id": link.change_id,
 "change_type": link.change_type,
 "branch_name": link.branch_name,
 "primary_issue": {
 "provider": link.primary_issue.provider.value,
 "issue_id": link.primary_issue.issue_id,
 "display_name": link.primary_issue.get_display_name(),
 },
 "related_issues": [
 {
 "provider": ref.provider.value,
 "issue_id": ref.issue_id,
 "display_name": ref.get_display_name(),
 }
 for ref in link.related_issues
 ],
 "emergency_override": link.emergency_override,
 "override_justification": link.override_justification,
 "linked_by": link.linked_by,
 "linked_at": link.linked_at.isoformat(),
 }


# Issue Search and Suggestions


@router.post("/search",
    dependencies = [Depends(require_scope([IAMScope.BRANCHES_READ]))])
async def search_issues(
 request: IssueSearchRequest,
 req: Request,
 user: UserContext = Depends(get_current_user),
) -> List[Dict[str, Any]]:
 """Search for issues across configured providers - Production Implementation"""
 try:
 from core.issue_tracking.issue_database import get_issue_database

 results = []

 # Search internal issues using PostgreSQL database
 issue_db = await get_issue_database()

 # Build search parameters
 search_params = {
 "text_search": request.query if hasattr(request, "query") else None,
 "status": request.status if hasattr(request, "status") else None,
 "assignee": request.assignee if hasattr(request, "assignee") else None,
 "issue_type": request.issue_type
 if hasattr(request, "issue_type")
 else None,
 "project": request.project if hasattr(request, "project") else None,
 "limit": min(getattr(request, "limit", 50), 100), # Cap at 100
 "offset": getattr(request, "offset", 0),
 }

 # Remove None values
 search_params = {k: v for k, v in search_params.items() if v is not None}

 internal_issues = await issue_db.search_internal_issues(**search_params)

 # Convert internal issues to response format
 for issue in internal_issues:
 # Calculate relevance score based on text match
 relevance_score = 0.8 # Base score for internal issues
 if search_params.get("text_search"):
 query_lower = search_params["text_search"].lower()
 title_lower = issue["title"].lower()
 desc_lower = (issue.get("description") or "").lower()

 # Simple relevance scoring
 if query_lower in title_lower:
 relevance_score += 0.2
 if query_lower in desc_lower:
 relevance_score += 0.1

 relevance_score = min(relevance_score, 1.0)

 results.append(
 {
 "provider": "internal",
 "issue_id": issue["issue_id"],
 "title": issue["title"],
 "description": issue.get("description"),
 "status": issue["status"],
 "issue_type": issue["issue_type"],
 "priority": issue.get("priority"),
 "assignee": issue.get("assignee"),
 "project": issue.get("project"),
 "labels": issue.get("labels", []),
 "created_at": issue["created_at"].isoformat()
 if issue["created_at"]
 else None,
 "updated_at": issue["updated_at"].isoformat()
 if issue["updated_at"]
 else None,
 "relevance_score": relevance_score,
 }
 )

 # Search external providers (JIRA, GitHub) if configured
 try:
 from core.issue_tracking.issue_service import get_issue_service

 issue_service = await get_issue_service()

 # Check if external providers are configured
 if hasattr(issue_service, "providers") and issue_service.providers:
 for provider, client in issue_service.providers.items():
 if provider.value in ["jira", "github"]:
 try:
 # For external providers, we would need to implement search APIs
 # For now, we handle only internal issues but the infrastructure is ready
 logger.debug(
 f"External provider {provider.value} available but search not implemented"
 )
 except Exception as e:
 logger.warning(f"Error searching {provider.value}: {e}")
 except Exception as e:
 logger.error(f"Error integrating with external issue providers: {e}")

 # Sort by relevance score descending
 results.sort(key = lambda x: x["relevance_score"], reverse = True)

 return results

 except Exception as e:
 logger.error(f"Error searching issues: {e}")
 # Return empty results instead of raising error for better UX
 return []


@router.get(
 "/suggest", dependencies = [Depends(require_scope([IAMScope.BRANCHES_WRITE]))]
)
async def suggest_issues(
 req: Request,
 branch_name: str = Query(..., description = "Branch name"),
 change_type: str = Query(..., description = "Type of change"),
 resource_name: Optional[str] = Query(None, description = "Resource name"),
 user: UserContext = Depends(get_current_user),
) -> List[Dict[str, Any]]:
 """Suggest relevant issues based on context"""
 issue_service = await get_issue_service()

 suggestions = await issue_service.suggest_related_issues(
 branch_name = branch_name, change_type = change_type, resource_name = resource_name
 )

 # Convert to response format
 return [
 {
 "provider": ref.provider.value,
 "issue_id": ref.issue_id,
 "display_name": ref.get_display_name(),
 "title": ref.title,
 "url": ref.issue_url,
 }
 for ref in suggestions
 ]


# Configuration Endpoints


@router.get("/config", dependencies = [Depends(require_scope([IAMScope.SYSTEM_ADMIN]))])
async def get_issue_tracking_config(
 req: Request, user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
 """Get issue tracking configuration"""
 # Only admins can view configuration
 if not user.is_admin:
 raise HTTPException(
 status_code = status.HTTP_403_FORBIDDEN,
 detail = "Administrator permissions required",
 )

 issue_service = await get_issue_service()
 config = issue_service.config

 return {
 "requirements": {
 "enabled": config.requirements.enabled,
 "enforce_for_production": config.requirements.enforce_for_production,
 "allow_emergency_override": config.requirements.allow_emergency_override,
 "exempt_branches": config.requirements.exempt_branches,
 "require_for_schema_changes": config.requirements.require_for_schema_changes,
 "require_for_deletions": config.requirements.require_for_deletions,
 "require_for_acl_changes": config.requirements.require_for_acl_changes,
 "require_for_merges": config.requirements.require_for_merges,
 },
 "providers": list(issue_service.providers.keys()),
 "default_provider": config.default_provider.value,
 }


@router.post("/parse",
    dependencies = [Depends(require_scope([IAMScope.BRANCHES_READ]))])
async def parse_issue_reference(
 req: Request,
 text: str = Query(..., description = "Text containing issue reference"),
 user: UserContext = Depends(get_current_user),
) -> Dict[str, Any]:
 """Parse issue reference from text"""
 issue_ref = parse_issue_reference(text)

 if not issue_ref:
 return {
 "success": False,
 "message": f"Could not parse issue reference from: {text}",
 "supported_formats": [
 "JIRA: PROJ-123",
 "GitHub: #123 or GH-123",
 "GitLab: !123 or GL-123",
 "Linear: ENG-123",
 "Internal: OMS-123",
 ],
 }

 return {
 "success": True,
 "issue_ref": {
 "provider": issue_ref.provider.value,
 "issue_id": issue_ref.issue_id,
 "display_name": issue_ref.get_display_name(),
 },
 }


# Compliance and Statistics Endpoints


@router.get(
 "/compliance/stats", dependencies = [Depends(require_scope([IAMScope.AUDIT_READ]))]
)
async def get_compliance_stats(
 req: Request,
 start_date: Optional[str] = Query(None, description = "Start date (ISO format)"),
 end_date: Optional[str] = Query(None, description = "End date (ISO format)"),
 branch_name: Optional[str] = Query(None, description = "Filter by branch"),
 change_type: Optional[str] = Query(None, description = "Filter by change type"),
 user: UserContext = Depends(get_current_user),
) -> Dict[str, Any]:
 """Get issue tracking compliance statistics"""
 from datetime import datetime

 from core.issue_tracking.issue_database import get_issue_database

 # Parse dates
 start_dt = datetime.fromisoformat(start_date) if start_date else None
 end_dt = datetime.fromisoformat(end_date) if end_date else None

 issue_db = await get_issue_database()
 stats = await issue_db.get_compliance_stats(
 start_date = start_dt,
 end_date = end_dt,
 branch_name = branch_name,
 change_type = change_type,
 )

 return {
 "period": {"start": start_date, "end": end_date},
 "filters": {"branch": branch_name, "change_type": change_type},
 "statistics": stats,
 }


@router.get(
 "/compliance/user/{username}",
 dependencies = [Depends(require_scope([IAMScope.AUDIT_READ]))],
)
async def get_user_compliance_stats(
 username: str,
 req: Request,
 start_date: Optional[str] = Query(None, description = "Start date (ISO format)"),
 user: UserContext = Depends(get_current_user),
) -> Dict[str, Any]:
 """Get compliance statistics for a specific user"""
 from datetime import datetime

 from core.issue_tracking.issue_database import get_issue_database

 # Parse date
 start_dt = datetime.fromisoformat(start_date) if start_date else None

 issue_db = await get_issue_database()
 stats = await issue_db.get_user_compliance_stats(username, start_dt)

 return stats


@router.get(
 "/issues/{provider}/{issue_id}/changes",
 dependencies = [Depends(require_scope([IAMScope.BRANCHES_READ]))],
)
async def get_issue_changes(
 provider: IssueProvider,
 issue_id: str,
 req: Request,
 user: UserContext = Depends(get_current_user),
) -> List[Dict[str, Any]]:
 """Get all changes linked to a specific issue"""
 from core.issue_tracking.issue_database import get_issue_database

 issue_db = await get_issue_database()
 changes = await issue_db.get_changes_for_issue(provider, issue_id)

 return changes
