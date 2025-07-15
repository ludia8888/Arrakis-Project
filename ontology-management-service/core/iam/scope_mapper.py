"""
Scope Mapper - Unified mapping between IAM scopes and OMS permissions
Centralizes all permission transformation logic
"""
from typing import List, Dict, Set, Optional
from enum import Enum
from dataclasses import dataclass
import re

from shared.iam_contracts import IAMScope
from models.permissions import ResourceType, Action, Role
from arrakis_common import get_logger

logger = get_logger(__name__)


@dataclass
class PermissionMapping:
 """Bidirectional mapping between scopes and permissions"""
 scope: str
 permission_pattern: str
 resource_type: Optional[ResourceType] = None
 actions: Optional[List[Action]] = None


class ScopeMapper:
 """
 Unified scope/permission mapper
 Handles all transformations between IAM scopes and OMS permissions
 """

 def __init__(self):
 # Direct mappings: scope -> permission pattern
 self.scope_to_permission_map = {
 # Ontology scopes
 IAMScope.ONTOLOGIES_READ: "ontology:*:read",
 IAMScope.ONTOLOGIES_WRITE: "ontology:*:write",
 IAMScope.ONTOLOGIES_ADMIN: "ontology:*:admin",

 # Schema scopes
 IAMScope.SCHEMAS_READ: "schema:*:read",
 IAMScope.SCHEMAS_WRITE: "schema:*:write",

 # Branch scopes
 IAMScope.BRANCHES_READ: "branch:*:read",
 IAMScope.BRANCHES_WRITE: "branch:*:write",

 # Proposal scopes
 IAMScope.PROPOSALS_READ: "proposal:*:read",
 IAMScope.PROPOSALS_WRITE: "proposal:*:write",
 IAMScope.PROPOSALS_APPROVE: "proposal:*:approve",

 # Audit scopes
 IAMScope.AUDIT_READ: "audit:*:read",

 # System scopes
 IAMScope.SYSTEM_ADMIN: "system:*:admin",
 IAMScope.SERVICE_ACCOUNT: "service:*:account",
 IAMScope.WEBHOOK_EXECUTE: "webhook:*:execute",
 }

 # Reverse mappings: permission pattern -> scope
 self.permission_to_scope_map = {
 v: k for k, v in self.scope_to_permission_map.items()
 }

 # Extended mappings for complex permissions
 self.extended_mappings = [
 # Object types are part of ontologies
 PermissionMapping("api:ontologies:read", "object_type:*:read", ResourceType.OBJECT_TYPE, [Action.READ]),
 PermissionMapping("api:ontologies:write", "object_type:*:write", ResourceType.OBJECT_TYPE, [Action.CREATE, Action.UPDATE]),
 PermissionMapping("api:ontologies:write", "object_type:*:delete", ResourceType.OBJECT_TYPE, [Action.DELETE]),

 # Link types are part of ontologies
 PermissionMapping("api:ontologies:read", "link_type:*:read", ResourceType.LINK_TYPE, [Action.READ]),
 PermissionMapping("api:ontologies:write", "link_type:*:write", ResourceType.LINK_TYPE, [Action.CREATE, Action.UPDATE]),
 PermissionMapping("api:ontologies:write", "link_type:*:delete", ResourceType.LINK_TYPE, [Action.DELETE]),

 # Action types are part of ontologies
 PermissionMapping("api:ontologies:read", "action_type:*:read", ResourceType.ACTION_TYPE, [Action.READ]),
 PermissionMapping("api:ontologies:write", "action_type:*:write", ResourceType.ACTION_TYPE, [Action.CREATE, Action.UPDATE]),
 PermissionMapping("api:ontologies:write", "action_type:*:delete", ResourceType.ACTION_TYPE, [Action.DELETE]),

 # Function types are part of ontologies
 PermissionMapping("api:ontologies:read", "function_type:*:read", ResourceType.FUNCTION_TYPE, [Action.READ]),
 PermissionMapping("api:ontologies:write", "function_type:*:write", ResourceType.FUNCTION_TYPE, [Action.CREATE, Action.UPDATE]),
 PermissionMapping("api:ontologies:write", "function_type:*:delete", ResourceType.FUNCTION_TYPE, [Action.DELETE]),
 ]

 # Scope hierarchy (parent -> children)
 self.scope_hierarchy = {
 IAMScope.SYSTEM_ADMIN: [
 IAMScope.ONTOLOGIES_ADMIN,
 IAMScope.SCHEMAS_WRITE,
 IAMScope.BRANCHES_WRITE,
 IAMScope.PROPOSALS_APPROVE,
 IAMScope.AUDIT_READ,
 IAMScope.WEBHOOK_EXECUTE
 ],
 IAMScope.ONTOLOGIES_ADMIN: [
 IAMScope.ONTOLOGIES_WRITE,
 IAMScope.ONTOLOGIES_READ
 ],
 IAMScope.ONTOLOGIES_WRITE: [
 IAMScope.ONTOLOGIES_READ
 ],
 IAMScope.SCHEMAS_WRITE: [
 IAMScope.SCHEMAS_READ
 ],
 IAMScope.BRANCHES_WRITE: [
 IAMScope.BRANCHES_READ
 ],
 IAMScope.PROPOSALS_WRITE: [
 IAMScope.PROPOSALS_READ
 ],
 IAMScope.PROPOSALS_APPROVE: [
 IAMScope.PROPOSALS_READ
 ]
 }

 def scope_to_permission(self, scope: str) -> List[str]:
 """
 Convert a single IAM scope to OMS permissions

 Args:
 scope: IAM scope string (e.g., "api:ontologies:read")

 Returns:
 List of OMS permission patterns
 """
 # Handle enum values
 if hasattr(scope, 'value'):
 scope = scope.value

 # Direct mapping
 if scope in self.scope_to_permission_map:
 base_permission = self.scope_to_permission_map[scope]
 permissions = [base_permission]

 # Add extended permissions
 for mapping in self.extended_mappings:
 if mapping.scope == scope:
 permissions.append(mapping.permission_pattern)

 return permissions

 # Handle unknown scopes with pattern matching
 if scope.startswith("api:") and ":" in scope[4:]:
 # Pattern: api:resource:action -> resource:*:action
 parts = scope.split(":")
 if len(parts) == 3:
 resource = parts[1]
 action = parts[2]
 return [f"{resource}:*:{action}"]

 logger.warning(f"Unknown scope: {scope}")
 return []

 def permission_to_scope(self, permission: str) -> Optional[str]:
 """
 Convert an OMS permission to IAM scope

 Args:
 permission: OMS permission pattern (e.g., "ontology:*:read")

 Returns:
 IAM scope string or None if no mapping exists
 """
 # Direct mapping
 if permission in self.permission_to_scope_map:
 return self.permission_to_scope_map[permission]

 # Check extended mappings
 for mapping in self.extended_mappings:
 if mapping.permission_pattern == permission:
 return mapping.scope

 # Pattern-based conversion
 match = re.match(r"^(\w+):(\*|\w+):(\w+)$", permission)
 if match:
 resource_type, resource_id, action = match.groups()

 # Map common resource types
 resource_mapping = {
 "object_type": "ontologies",
 "link_type": "ontologies",
 "action_type": "ontologies",
 "function_type": "ontologies",
 "ontology": "ontologies",
 "schema": "schemas",
 "branch": "branches",
 "proposal": "proposals",
 "audit": "audit",
 "system": "system",
 "service": "service",
 "webhook": "webhook"
 }

 if resource_type in resource_mapping:
 mapped_resource = resource_mapping[resource_type]
 return f"api:{mapped_resource}:{action}"

 logger.warning(f"No scope mapping for permission: {permission}")
 return None

 def transform_scopes(self, scopes: List[str]) -> List[str]:
 """
 Transform a list of IAM scopes to OMS permissions
 Handles scope hierarchy expansion

 Args:
 scopes: List of IAM scopes

 Returns:
 List of OMS permissions (deduplicated)
 """
 all_scopes = set()

 # Expand scope hierarchy
 for scope in scopes:
 all_scopes.add(scope)
 if scope in self.scope_hierarchy:
 all_scopes.update(self.scope_hierarchy[scope])

 # Convert to permissions
 permissions = set()
 for scope in all_scopes:
 permissions.update(self.scope_to_permission(scope))

 return sorted(list(permissions))

 def transform_permissions(self, permissions: List[str]) -> List[str]:
 """
 Transform a list of OMS permissions to IAM scopes

 Args:
 permissions: List of OMS permissions

 Returns:
 List of IAM scopes (deduplicated)
 """
 scopes = set()

 for permission in permissions:
 scope = self.permission_to_scope(permission)
 if scope:
 scopes.add(scope)

 return sorted(list(scopes))

 def check_permission_match(self, user_permissions: List[str], required_permission: str) -> bool:
 """
 Check if user permissions match a required permission
 Handles wildcards and hierarchical permissions

 Args:
 user_permissions: List of user's permissions
 required_permission: Required permission pattern

 Returns:
 True if user has the required permission
 """
 # Parse required permission
 match = re.match(r"^(\w+):(\*|\w+):(\w+)$", required_permission)
 if not match:
 return False

 req_resource_type, req_resource_id, req_action = match.groups()

 for user_perm in user_permissions:
 # Parse user permission
 user_match = re.match(r"^(\w+):(\*|\w+):(\w+)$", user_perm)
 if not user_match:
 continue

 user_resource_type, user_resource_id, user_action = user_match.groups()

 # Check resource type match
 if user_resource_type != req_resource_type:
 continue

 # Check resource ID match (wildcard support)
 if user_resource_id != "*" and user_resource_id != req_resource_id and req_resource_id != "*":
 continue

 # Check action match
 if user_action == "*" or user_action == req_action:
 return True

 # Check hierarchical actions
 action_hierarchy = {
 "admin": ["write", "read", "delete", "approve", "reject", "execute"],
 "write": ["read", "create", "update"],
 "approve": ["read"],
 "execute": ["read"]
 }

 if user_action in action_hierarchy and req_action in action_hierarchy[user_action]:
 return True

 return False

 def get_resource_permissions(self, scope: str) -> Dict[ResourceType, List[Action]]:
 """
 Get detailed resource permissions for a scope

 Args:
 scope: IAM scope

 Returns:
 Dictionary mapping resource types to allowed actions
 """
 permissions = {}

 # Handle direct mappings
 if scope == IAMScope.ONTOLOGIES_READ:
 permissions[ResourceType.OBJECT_TYPE] = [Action.READ]
 permissions[ResourceType.LINK_TYPE] = [Action.READ]
 permissions[ResourceType.ACTION_TYPE] = [Action.READ]
 permissions[ResourceType.FUNCTION_TYPE] = [Action.READ]
 elif scope == IAMScope.ONTOLOGIES_WRITE:
 permissions[ResourceType.OBJECT_TYPE] = [Action.CREATE, Action.READ, Action.UPDATE]
 permissions[ResourceType.LINK_TYPE] = [Action.CREATE, Action.READ, Action.UPDATE]
 permissions[ResourceType.ACTION_TYPE] = [Action.CREATE, Action.READ, Action.UPDATE]
 permissions[ResourceType.FUNCTION_TYPE] = [Action.CREATE, Action.READ, Action.UPDATE]
 elif scope == IAMScope.ONTOLOGIES_ADMIN:
 permissions[ResourceType.OBJECT_TYPE] = [Action.CREATE, Action.READ, Action.UPDATE, Action.DELETE]
 permissions[ResourceType.LINK_TYPE] = [Action.CREATE, Action.READ, Action.UPDATE, Action.DELETE]
 permissions[ResourceType.ACTION_TYPE] = [Action.CREATE, Action.READ, Action.UPDATE, Action.DELETE]
 permissions[ResourceType.FUNCTION_TYPE] = [Action.CREATE, Action.READ, Action.UPDATE, Action.DELETE]
 elif scope == IAMScope.SCHEMAS_READ:
 permissions[ResourceType.SCHEMA] = [Action.READ]
 elif scope == IAMScope.SCHEMAS_WRITE:
 permissions[ResourceType.SCHEMA] = [Action.CREATE, Action.READ, Action.UPDATE]
 elif scope == IAMScope.BRANCHES_READ:
 permissions[ResourceType.BRANCH] = [Action.READ]
 elif scope == IAMScope.BRANCHES_WRITE:
 permissions[ResourceType.BRANCH] = [Action.CREATE, Action.READ, Action.UPDATE, Action.DELETE, Action.MERGE]
 elif scope == IAMScope.PROPOSALS_READ:
 permissions[ResourceType.PROPOSAL] = [Action.READ]
 elif scope == IAMScope.PROPOSALS_WRITE:
 permissions[ResourceType.PROPOSAL] = [Action.CREATE, Action.READ, Action.UPDATE]
 elif scope == IAMScope.PROPOSALS_APPROVE:
 permissions[ResourceType.PROPOSAL] = [Action.READ, Action.APPROVE, Action.REJECT]
 elif scope == IAMScope.AUDIT_READ:
 permissions[ResourceType.AUDIT] = [Action.READ]
 elif scope == IAMScope.WEBHOOK_EXECUTE:
 permissions[ResourceType.WEBHOOK] = [Action.READ, Action.EXECUTE]
 elif scope == IAMScope.SYSTEM_ADMIN:
 # Admin has all permissions
 for resource_type in ResourceType:
 permissions[resource_type] = list(Action)

 return permissions


# Global instance
_scope_mapper: Optional[ScopeMapper] = None


def get_scope_mapper() -> ScopeMapper:
 """Get global scope mapper instance"""
 global _scope_mapper
 if _scope_mapper is None:
 _scope_mapper = ScopeMapper()
 return _scope_mapper
