"""
FastAPI Dependencies for IAM (Identity and Access Management)
"""
from typing import List, Optional, Union
from fastapi import Request, HTTPException, Depends, status

from ..auth_utils import UserContext
from .iam_integration import get_iam_integration, IAMScope
from .scope_mapper import get_scope_mapper
from models.permissions import ResourceType, Action

iam_integration = get_iam_integration()
scope_mapper = get_scope_mapper()

def require_scope(required_scopes: Union[List[IAMScope], IAMScope]):
 """
 Factory for creating a FastAPI dependency that checks for required scopes.
 This should be used in endpoint definitions to enforce permission checks.

 Args:
 required_scopes: A single IAMScope or list of IAMScope enums that are required to access the endpoint.
 The user must have AT LEAST ONE of these scopes.

 Returns:
 A FastAPI dependency function.
 """
 # Normalize to list
 if not isinstance(required_scopes, list):
 required_scopes = [required_scopes]

 async def scope_checker(request: Request) -> UserContext:
 """
 The actual dependency function that will be executed by FastAPI.
 It checks if the user context has any of the required scopes.
 Returns the user context for downstream use.
 """
 # User context should have been set by the AuthMiddleware
 user: Optional[UserContext] = getattr(request.state, "user", None)

 if not user:
 # This should technically never be reached if AuthMiddleware is active
 raise HTTPException(
 status_code = status.HTTP_401_UNAUTHORIZED,
 detail = "Authentication required",
 )

 # System Admin has universal access
 if iam_integration.check_scope(user, IAMScope.SYSTEM_ADMIN):
 return user

 # Check if the user has any of the required scopes
 if not iam_integration.check_any_scope(user, required_scopes):
 # Get user's actual scopes for better error message
 user_scopes = user.metadata.get("scopes", [])

 raise HTTPException(
 status_code = status.HTTP_403_FORBIDDEN,
 detail={
 "error": "Insufficient permissions",
 "required_scopes": [s.value for s in required_scopes],
 "user_scopes": user_scopes,
 "message": f"This action requires one of: {', '.join([s.value for s in required_scopes])}"
 },
 headers={
 "X-Required-Scopes": ",".join([s.value for s in required_scopes])
 },
 )

 return user

 return scope_checker


def require_permission(resource_type: ResourceType, action: Action):
 """
 Factory for creating a FastAPI dependency that checks for specific resource permissions.
 This provides a more granular permission check than scopes.

 Args:
 resource_type: The type of resource being accessed
 action: The action being performed on the resource

 Returns:
 A FastAPI dependency function
 """
 async def permission_checker(request: Request) -> UserContext:
 """
 Check if user has permission for specific resource/action combination
 """
 user: Optional[UserContext] = getattr(request.state, "user", None)

 if not user:
 raise HTTPException(
 status_code = status.HTTP_401_UNAUTHORIZED,
 detail = "Authentication required",
 )

 # Get user permissions (should be cached from middleware)
 user_permissions = user.metadata.get("permissions", [])
 if not user_permissions and hasattr(request.state, "permissions"):
 user_permissions = request.state.permissions

 # Check permission using scope mapper
 required_permission = f"{resource_type.value}:*:{action.value}"

 if not scope_mapper.check_permission_match(user_permissions, required_permission):
 raise HTTPException(
 status_code = status.HTTP_403_FORBIDDEN,
 detail={
 "error": "Insufficient permissions",
 "required_permission": required_permission,
 "resource_type": resource_type.value,
 "action": action.value,
 "message": f"You don't have permission to {action.value} {resource_type.value}"
 }
 )

 return user

 return permission_checker


def get_current_user(request: Request) -> UserContext:
 """
 Get current authenticated user from request
 This is a simple dependency that can be used when you just need the user context
 """
 user = getattr(request.state, "user", None)
 if not user:
 raise HTTPException(
 status_code = status.HTTP_401_UNAUTHORIZED,
 detail = "Authentication required"
 )
 return user


def get_current_user_optional(request: Request) -> Optional[UserContext]:
 """
 Get current authenticated user from request, or None if not authenticated
 Use this for endpoints that have different behavior for authenticated vs anonymous users
 """
 return getattr(request.state, "user", None)
