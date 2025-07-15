"""
Auth Integration Examples
API endpoint example with permission checks applied
"""

from typing import List, Optional

from core.auth import Action, ResourceType, UserContext, get_permission_checker
from fastapi import APIRouter, Depends, HTTPException, Request
from middleware.auth_middleware import get_current_user, require_permission
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1", tags=["auth-examples"])


class SchemaCreate(BaseModel):
    name: str
    description: str


class SchemaResponse(BaseModel):
    id: str
    name: str
    description: str
    created_by: str


# Example 1: Endpoint requiring only authentication
@router.get("/me")
async def get_current_user_info(user: UserContext = Depends(get_current_user)):
    """Get current user information"""
    return {
        "user_id": user.user_id,
        "username": user.username,
        "email": user.email,
        "roles": user.roles,
        "teams": user.teams,
    }


# Example 2: Endpoint requiring specific permission
@router.post("/schemas", response_model=SchemaResponse)
async def create_schema(
    schema: SchemaCreate,
    request: Request,
    user: UserContext = Depends(get_current_user),
):
    """Create schema (requires CREATE permission)"""
    # Permission check
    checker = get_permission_checker()
    if not checker.check_permission(user, ResourceType.SCHEMA, "*", Action.CREATE):
        raise HTTPException(status_code=403, detail="Permission denied")

    # Actual schema creation logic
    new_schema = SchemaResponse(
        id="schema-123",
        name=schema.name,
        description=schema.description,
        created_by=user.username,
    )

    return new_schema


# Example 3: Resource-specific permission check
@router.get("/schemas/{schema_id}")
async def get_schema(schema_id: str, user: UserContext = Depends(get_current_user)):
    """Get specific schema (requires READ permission)"""
    # Permission check
    checker = get_permission_checker()
    if not checker.check_permission(user, ResourceType.SCHEMA, schema_id, Action.READ):
        raise HTTPException(status_code=403, detail="Permission denied")

    # Actual schema retrieval logic
    return {
        "id": schema_id,
        "name": "Example Schema",
        "description": "Example description",
    }


# Example 4: List of resources accessible by user
@router.get("/my-schemas")
async def get_my_schemas(user: UserContext = Depends(get_current_user)):
    """List of schemas readable by user"""
    checker = get_permission_checker()
    allowed_schemas = checker.get_user_resources(user, ResourceType.SCHEMA, Action.READ)

    if "*" in allowed_schemas:
        # All schemas accessible
        return {
            "schemas": [
                {"id": "schema-1", "name": "Schema 1"},
                {"id": "schema-2", "name": "Schema 2"},
                {"id": "schema-3", "name": "Schema 3"},
            ],
            "total": 3,
        }
    else:
        # Only specific schemas accessible
        return {
            "schemas": [
                {"id": sid, "name": f"Schema {sid}"} for sid in allowed_schemas
            ],
            "total": len(allowed_schemas),
        }


# Example 5: Complex permission check (branch merge)
@router.post("/branches/{branch_id}/merge")
async def merge_branch(
    branch_id: str, target_branch: str, user: UserContext = Depends(get_current_user)
):
    """Merge branch (requires MERGE permission + APPROVE permission)"""
    checker = get_permission_checker()

    # Check merge permission
    can_merge = checker.check_permission(
        user, ResourceType.BRANCH, branch_id, Action.MERGE
    )

    # Check approve permission (reviewer or higher)
    can_approve = checker.check_permission(
        user, ResourceType.BRANCH, branch_id, Action.APPROVE
    )

    if not can_merge:
        raise HTTPException(status_code=403, detail="Merge permission denied")

    # Auto-approve if user has approve permission
    auto_approved = can_approve

    return {
        "branch_id": branch_id,
        "target_branch": target_branch,
        "merged_by": user.username,
        "auto_approved": auto_approved,
        "status": "merged" if auto_approved else "pending_approval",
    }


# Example 6: Team-based permissions
@router.get("/teams/{team_id}/resources")
async def get_team_resources(
    team_id: str, user: UserContext = Depends(get_current_user)
):
    """Get team resources (team members only)"""
    if team_id not in user.teams and "admin" not in user.roles:
        raise HTTPException(status_code=403, detail=f"Not a member of team {team_id}")

    return {
        "team_id": team_id,
        "resources": [
            {"type": "schema", "id": "team-schema-1"},
            {"type": "branch", "id": "team-branch-1"},
        ],
    }
