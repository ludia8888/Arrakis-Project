"""
Auth Utils Module
This package exports the core authentication/authorization models and utilities.
"""
import os
from typing import Callable, Dict, Optional, Set

from arrakis_common import get_logger
from core.auth.models import UserContext

logger = get_logger(__name__)

# Permission definitions
PERMISSIONS = {
 # Schema management
 "schema:read": "Read schema definitions",
 "schema:write": "Modify schema definitions",
 "schema:delete": "Delete schema definitions",
 "schema:validate": "Validate schema changes",
 # Branch management
 "branch:read": "Read branch information",
 "branch:create": "Create new branches",
 "branch:delete": "Delete branches",
 "branch:merge": "Merge branches",
 "branch:protect": "Modify branch protection settings",
 # Proposal management
 "proposal:read": "Read change proposals",
 "proposal:create": "Create change proposals",
 "proposal:review": "Review change proposals",
 "proposal:approve": "Approve change proposals",
 "proposal:merge": "Merge approved proposals",
 # Job management
 "job:read": "Read job information",
 "job:create": "Create jobs",
 "job:cancel": "Cancel jobs",
 "job:retry": "Retry failed jobs",
 # System administration
 "admin:users": "Manage users",
 "admin:roles": "Manage roles and permissions",
 "admin:config": "Modify system configuration",
 "admin:monitoring": "Access system monitoring",
 # Audit and compliance
 "audit:read": "Read audit logs",
 "audit:export": "Export audit data",
}

# Role-based permission mappings
ROLE_PERMISSIONS: Dict[str, Set[str]] = {
 "admin": set(PERMISSIONS.keys()), # Admin has all permissions
 "schema_manager": {
 "schema:read",
 "schema:write",
 "schema:delete",
 "schema:validate",
 "branch:read",
 "branch:create",
 "branch:delete",
 "branch:merge",
 "proposal:read",
 "proposal:create",
 "proposal:review",
 "proposal:approve",
 "proposal:merge",
 "job:read",
 "job:create",
 "job:cancel",
 "job:retry",
 "audit:read",
 },
 "developer": {
 "schema:read",
 "schema:write",
 "schema:validate",
 "branch:read",
 "branch:create",
 "branch:merge",
 "proposal:read",
 "proposal:create",
 "proposal:review",
 "job:read",
 "job:create",
 "job:cancel",
 },
 "reviewer": {
 "schema:read",
 "schema:validate",
 "branch:read",
 "proposal:read",
 "proposal:review",
 "proposal:approve",
 "job:read",
 },
 "read_only": {"schema:read", "branch:read", "proposal:read", "job:read"},
}


class PermissionChecker:
 """Production-ready permission checking system"""

 def __init__(self):
 self.bypass_permissions = (
 os.getenv("BYPASS_PERMISSIONS", "false").lower() == "true"
 )
 if self.bypass_permissions:
 logger.warning(
 "🚨 SECURITY WARNING: Permission checking is BYPASSED! Only use in development."
 )

 def check_permission(self, user: Optional[UserContext], permission: str) -> bool:
 """
 Check if user has the specified permission

 Args:
 user: User context with roles and permissions
 permission: Permission string (e.g., "schema:write")

 Returns:
 bool: True if user has permission, False otherwise
 """
 if self.bypass_permissions:
 logger.debug(f"Permission check bypassed for: {permission}")
 return True

 if not user:
 logger.warning(f"Permission denied: No user context for {permission}")
 return False

 if not permission:
 logger.warning("Permission denied: Empty permission string")
 return False

 # Check if permission exists
 if permission not in PERMISSIONS:
 logger.error(f"Unknown permission requested: {permission}")
 return False

 # Super admin bypass
 if hasattr(user, "is_super_admin") and user.is_super_admin:
 logger.debug(f"Super admin access granted for: {permission}")
 return True

 # Check role-based permissions
 user_roles = getattr(user, "roles", [])
 if not user_roles:
 logger.warning(
 f"Permission denied: User {user.user_id} has no roles for {permission}"
 )
 return False

 # Check if any of user's roles have the required permission
 for role in user_roles:
 role_permissions = ROLE_PERMISSIONS.get(role, set())
 if permission in role_permissions:
 logger.debug(
 f"Permission granted: User {user.user_id} role '{role}' has {permission}"
 )
 return True

 # Check direct user permissions if available
 user_permissions = getattr(user, "permissions", set())
 if permission in user_permissions:
 logger.debug(
 f"Permission granted: User {user.user_id} has direct permission {permission}"
 )
 return True

 logger.info(
 f"Permission denied: User {user.user_id} (roles: {user_roles}) lacks {permission}"
 )
 return False

 def check_resource_permission(
 self, user: Optional[UserContext], permission: str, resource_owner: str
 ) -> bool:
 """
 Check permission with resource ownership consideration

 Args:
 user: User context
 permission: Permission string
 resource_owner: User ID of resource owner

 Returns:
 bool: True if user has permission or owns the resource
 """
 # Check standard permission first
 if self.check_permission(user, permission):
 return True

 # Allow resource owners to access their own resources
 if user and hasattr(user, "user_id") and user.user_id == resource_owner:
 # Resource owners get read access to their own resources
 if permission.endswith(":read"):
 logger.debug(
 f"Resource owner access granted: {user.user_id} accessing own resource"
 )
 return True

 return False

 def require_permission(self, permission: str) -> Callable:
 """
 Decorator to require specific permission for function execution

 Args:
 permission: Required permission string

 Returns:
 Decorator function
 """

 def decorator(func):
 def wrapper(*args, **kwargs):
 # Extract user from context (assuming first arg or 'user' kwarg)
 user = None
 if args and hasattr(args[0], "user_id"):
 user = args[0]
 elif "user" in kwargs:
 user = kwargs["user"]
 elif "context" in kwargs and hasattr(kwargs["context"], "user"):
 user = kwargs["context"].user

 if not self.check_permission(user, permission):
 raise PermissionError(f"Permission '{permission}' required")

 return func(*args, **kwargs)

 return wrapper

 return decorator


# Global permission checker instance
_permission_checker = PermissionChecker()


def get_permission_checker() -> PermissionChecker:
 """Get the global permission checker instance"""
 return _permission_checker


def check_permission(user: Optional[UserContext], permission: str) -> bool:
 """Convenient function to check permissions"""
 return _permission_checker.check_permission(user, permission)


def require_permission(permission: str):
 """Convenient decorator to require permissions"""
 return _permission_checker.require_permission(permission)


__all__ = [
 "UserContext",
 "PermissionChecker",
 "get_permission_checker",
 "check_permission",
 "require_permission",
 "PERMISSIONS",
 "ROLE_PERMISSIONS",
]
