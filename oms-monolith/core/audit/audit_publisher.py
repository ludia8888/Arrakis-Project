"""
Audit Event Publisher for Audit Trail Service Integration
Publishes audit events to NATS JetStream and stores in database for compliance
"""
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from uuid import uuid4

from core.audit.models import (
    AuditEventV1, AuditAction, ActorInfo, TargetInfo, 
    ChangeDetails, ResourceType, create_audit_event
)
from core.audit.audit_repository import AuditRepositoryInterface
from core.audit.event_bus import AuditEventBusInterface
from core.auth import UserContext
from shared.security.pii_utils import mask_pii_fields
from utils.logger import get_logger
from utils.safe_json_encoder import safe_dict_conversion

logger = get_logger(__name__)


class AuditPublisher:
    """
    Publishes audit events for all write operations
    Uses repository pattern for storage and event bus for streaming
    """
    
    def __init__(self, 
                 repository: AuditRepositoryInterface,
                 event_bus: AuditEventBusInterface):
        self.repository = repository
        self.event_bus = event_bus
        self.enabled = True  # Can be disabled for testing
        
    
    
    async def publish_audit_event(
        self,
        action: AuditAction,
        user: UserContext,
        target: TargetInfo,
        changes: Optional[ChangeDetails] = None,
        success: bool = True,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[int] = None
    ) -> Optional[str]:
        """
        Publish an audit event to the Outbox for delivery to Audit Trail Service
        
        Returns:
            Event ID if published successfully, None otherwise
        """
        if not self.enabled:
            return None
        
        try:
            # Create actor info from user context
            # Make metadata safe for JSON serialization
            safe_metadata = safe_dict_conversion(user.metadata) if hasattr(user, 'metadata') else {}
            
            actor = ActorInfo(
                id=user.user_id,
                username=user.username,
                email=user.email,
                roles=user.roles,
                tenant_id=user.tenant_id,
                service_account=user.is_service_account if hasattr(user, 'is_service_account') else False,
                auth_method="jwt",  # Default, can be overridden
                # IP and user agent should be extracted from request context
            )
            
            # Mask PII in changes if present
            if changes and changes.old_values:
                changes.old_values = mask_pii_fields(changes.old_values)
            if changes and changes.new_values:
                changes.new_values = mask_pii_fields(changes.new_values)
            
            # Create audit event with safe metadata
            safe_event_metadata = safe_dict_conversion(metadata) if metadata else {}
            
            audit_event = AuditEventV1(
                id=str(uuid4()),
                action=action,
                actor=actor,
                target=target,
                changes=changes,
                success=success,
                error_code=error_code,
                error_message=error_message,
                duration_ms=duration_ms,
                request_id=request_id,
                time=datetime.now(timezone.utc),
                metadata=safe_event_metadata
            )
            
            # Dual-write: Store in database and publish to event stream
            
            # 1. Store in audit database (primary storage for compliance)
            try:
                await self.repository.store_event(audit_event)
            except (ConnectionError, TimeoutError) as e:
                logger.error(f"Database connection error storing audit event: {e}")
                # Continue with event publishing - database failure shouldn't block operation
            except ValueError as e:
                logger.error(f"Invalid data format storing audit event: {e}")
                # Continue with event publishing - database failure shouldn't block operation
            except RuntimeError as e:
                logger.error(f"Runtime error storing audit event: {e}")
                # Continue with event publishing - database failure shouldn't block operation
            
            # 2. Publish to event stream (for real-time processing)
            try:
                await self.event_bus.publish_event(audit_event)
            except (ConnectionError, TimeoutError) as e:
                logger.error(f"Network error publishing audit event to stream: {e}")
                # Continue - event stream failure shouldn't block operation
            except RuntimeError as e:
                logger.error(f"Runtime error publishing audit event to stream: {e}")
                # Continue - event stream failure shouldn't block operation
            
            logger.info(
                f"Published audit event: {action.value} on {target.resource_type.value}/{target.resource_id} "
                f"by {actor.username} (success={success})"
            )
            
            return audit_event.id
            
        except (ValueError, KeyError) as e:
            logger.error(f"Data processing error in audit event: {e}")
            # Don't fail the main operation if audit fails
            return None
        except RuntimeError as e:
            logger.error(f"Runtime error publishing audit event: {e}")
            # Don't fail the main operation if audit fails
            return None
    
    async def publish_audit_event_direct(self, audit_event: AuditEventV1) -> bool:
        """
        Publish a pre-formed audit event directly
        
        Returns:
            True if published successfully to event stream
        """
        if not self.enabled:
            return False
        
        try:
            return await self.event_bus.publish_event(audit_event)
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Network error publishing audit event {audit_event.id}: {e}")
            return False
        except RuntimeError as e:
            logger.error(f"Runtime error publishing audit event {audit_event.id}: {e}")
            return False
    
    
    async def audit_schema_change(
        self,
        action: str,
        user: UserContext,
        branch: str,
        resource_type: str,
        resource_id: str,
        old_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        commit_hash: Optional[str] = None,
        request_id: Optional[str] = None
    ):
        """Convenience method for auditing schema changes"""
        # Map action to AuditAction
        action_map = {
            "create": {
                "object_type": AuditAction.OBJECT_TYPE_CREATE,
                "link_type": AuditAction.LINK_TYPE_CREATE,
                "action_type": AuditAction.ACTION_TYPE_CREATE,
                "function_type": AuditAction.FUNCTION_TYPE_CREATE,
            },
            "update": {
                "object_type": AuditAction.OBJECT_TYPE_UPDATE,
                "link_type": AuditAction.LINK_TYPE_UPDATE,
                "action_type": AuditAction.ACTION_TYPE_UPDATE,
                "function_type": AuditAction.FUNCTION_TYPE_UPDATE,
            },
            "delete": {
                "object_type": AuditAction.OBJECT_TYPE_DELETE,
                "link_type": AuditAction.LINK_TYPE_DELETE,
                "action_type": AuditAction.ACTION_TYPE_DELETE,
                "function_type": AuditAction.FUNCTION_TYPE_DELETE,
            }
        }
        
        audit_action = action_map.get(action, {}).get(resource_type)
        if not audit_action:
            logger.warning(f"Unknown audit action: {action} on {resource_type}")
            return
        
        # Create target info
        from core.audit.models import ResourceType
        target = TargetInfo(
            resource_type=ResourceType(resource_type),
            resource_id=resource_id,
            branch=branch,
            resource_name=new_value.get("name") if new_value else old_value.get("name") if old_value else None
        )
        
        # Create change details
        changes = None
        if old_value or new_value:
            changes = ChangeDetails(
                commit_hash=commit_hash,
                old_values=old_value,
                new_values=new_value,
                fields_changed=self._get_changed_fields(old_value, new_value)
            )
        
        await self.publish_audit_event(
            action=audit_action,
            user=user,
            target=target,
            changes=changes,
            request_id=request_id
        )
    
    def _get_changed_fields(self, old_value: Optional[Dict], new_value: Optional[Dict]) -> List[str]:
        """Get list of fields that changed between old and new values"""
        if not old_value:
            return list(new_value.keys()) if new_value else []
        if not new_value:
            return list(old_value.keys())
        
        changed_fields = []
        all_keys = set(old_value.keys()) | set(new_value.keys())
        
        for key in all_keys:
            old_val = old_value.get(key)
            new_val = new_value.get(key)
            if old_val != new_val:
                changed_fields.append(key)
        
        return changed_fields
    
    async def audit_branch_operation(
        self,
        action: str,
        user: UserContext,
        branch_name: str,
        parent_branch: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ):
        """Audit branch operations"""
        action_map = {
            "create": AuditAction.BRANCH_CREATE,
            "update": AuditAction.BRANCH_UPDATE,
            "delete": AuditAction.BRANCH_DELETE,
            "merge": AuditAction.BRANCH_MERGE,
        }
        
        audit_action = action_map.get(action)
        if not audit_action:
            return
        
        from core.audit.models import ResourceType
        target = TargetInfo(
            resource_type=ResourceType.BRANCH,
            resource_id=branch_name,
            resource_name=branch_name,
            parent_id=parent_branch
        )
        
        await self.publish_audit_event(
            action=audit_action,
            user=user,
            target=target,
            metadata=metadata,
            request_id=request_id
        )
    
    async def audit_proposal_operation(
        self,
        action: str,
        user: UserContext,
        proposal_id: str,
        branch: str,
        metadata: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ):
        """Audit proposal operations"""
        action_map = {
            "create": AuditAction.PROPOSAL_CREATE,
            "update": AuditAction.PROPOSAL_UPDATE,
            "approve": AuditAction.PROPOSAL_APPROVE,
            "reject": AuditAction.PROPOSAL_REJECT,
            "merge": AuditAction.PROPOSAL_MERGE,
        }
        
        audit_action = action_map.get(action)
        if not audit_action:
            return
        
        from core.audit.models import ResourceType
        target = TargetInfo(
            resource_type=ResourceType.PROPOSAL,
            resource_id=proposal_id,
            branch=branch
        )
        
        await self.publish_audit_event(
            action=audit_action,
            user=user,
            target=target,
            metadata=metadata,
            request_id=request_id
        )
    
    async def audit_auth_event(
        self,
        action: str,
        user_id: str,
        username: str,
        success: bool = True,
        error_message: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Audit authentication events"""
        action_map = {
            "login": AuditAction.AUTH_LOGIN,
            "logout": AuditAction.AUTH_LOGOUT,
            "token_refresh": AuditAction.AUTH_TOKEN_REFRESH,
            "failed": AuditAction.AUTH_FAILED,
        }
        
        audit_action = action_map.get(action)
        if not audit_action:
            return
        
        actor = ActorInfo(
            id=user_id,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        from core.audit.models import ResourceType
        target = TargetInfo(
            resource_type=ResourceType.USER,
            resource_id=user_id
        )
        
        await self.publish_audit_event(
            action=audit_action,
            user=UserContext(user_id=user_id, username=username),  # Minimal context for auth events
            target=target,
            success=success,
            error_message=error_message,
            metadata=metadata
        )


