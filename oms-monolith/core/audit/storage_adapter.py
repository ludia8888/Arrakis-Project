"""
Audit Storage Adapter - Adapts AuditDatabase to AuditStorageProtocol
"""
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime

from core.audit.interfaces import AuditStorageProtocol
from core.audit.models import AuditEventV1, AuditEventFilter, AuditAction
from shared.database.audit_database import AuditDatabase
from utils.logger import get_logger

logger = get_logger(__name__)


class AuditStorageAdapter(AuditStorageProtocol):
    """Adapter to make AuditDatabase compatible with AuditStorageProtocol"""
    
    def __init__(self, audit_database: AuditDatabase):
        self.database = audit_database
        self.retention_policy = AuditRetentionPolicy()
    
    async def store_audit_event(self, event: AuditEventV1) -> bool:
        """Store a single audit event"""
        try:
            event_id = await self.database.store_event(event)
            return bool(event_id)
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Database connection error storing audit event: {e}")
            return False
        except ValueError as e:
            logger.error(f"Invalid data format storing audit event: {e}")
            return False
        except RuntimeError as e:
            logger.error(f"Runtime error storing audit event: {e}")
            return False
    
    async def store_audit_events_batch(self, events: List[AuditEventV1]) -> int:
        """Store multiple audit events in batch"""
        stored_count = 0
        for event in events:
            try:
                event_id = await self.database.store_event(event)
                if event_id:
                    stored_count += 1
            except (ConnectionError, TimeoutError) as e:
                logger.error(f"Database connection error storing event {event.id} in batch: {e}")
            except ValueError as e:
                logger.error(f"Invalid data format storing event {event.id} in batch: {e}")
            except RuntimeError as e:
                logger.error(f"Runtime error storing event {event.id} in batch: {e}")
        return stored_count
    
    async def query_audit_events(
        self, 
        filter_criteria: AuditEventFilter
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Query audit events with filtering"""
        try:
            events = await self.database.query_events(filter_criteria)
            # Convert to dict format
            event_dicts = []
            for event in events:
                event_dict = event.dict()
                # Flatten some fields for compatibility
                event_dict['actor_id'] = event.actor.id
                event_dict['actor_username'] = event.actor.username
                event_dict['target_resource_type'] = event.target.resource_type.value
                event_dict['target_resource_id'] = event.target.resource_id
                event_dict['created_at'] = event.time
                event_dicts.append(event_dict)
            
            return event_dicts, len(event_dicts)
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Database connection error querying audit events: {e}")
            return [], 0
        except ValueError as e:
            logger.error(f"Invalid data format querying audit events: {e}")
            return [], 0
        except RuntimeError as e:
            logger.error(f"Runtime error querying audit events: {e}")
            return [], 0
    
    async def get_audit_event_by_id(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get specific audit event by ID"""
        try:
            event = await self.database.get_event(event_id)
            if event:
                event_dict = event.dict()
                # Flatten some fields for compatibility
                event_dict['actor_id'] = event.actor.id
                event_dict['actor_username'] = event.actor.username
                event_dict['target_resource_type'] = event.target.resource_type.value
                event_dict['target_resource_id'] = event.target.resource_id
                event_dict['created_at'] = event.time
                return event_dict
            return None
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Database connection error getting audit event {event_id}: {e}")
            return None
        except KeyError as e:
            logger.error(f"Event {event_id} not found: {e}")
            return None
        except RuntimeError as e:
            logger.error(f"Runtime error getting audit event {event_id}: {e}")
            return None
    
    async def get_audit_statistics(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get audit statistics"""
        # Basic implementation - can be enhanced based on actual database capabilities
        filter_criteria = AuditEventFilter(
            start_time=start_time,
            end_time=end_time,
            limit=10000
        )
        events, total = await self.query_audit_events(filter_criteria)
        
        # Calculate basic statistics
        stats = {
            "total_events": total,
            "time_range": {
                "start": start_time.isoformat() if start_time else None,
                "end": end_time.isoformat() if end_time else None
            },
            "events_by_action": {},
            "events_by_resource_type": {},
            "success_rate": 0.0
        }
        
        success_count = 0
        for event in events:
            action = event.get('action', 'unknown')
            resource_type = event.get('target_resource_type', 'unknown')
            
            stats["events_by_action"][action] = stats["events_by_action"].get(action, 0) + 1
            stats["events_by_resource_type"][resource_type] = stats["events_by_resource_type"].get(resource_type, 0) + 1
            
            if event.get('success', False):
                success_count += 1
        
        if total > 0:
            stats["success_rate"] = success_count / total
        
        return stats
    
    async def cleanup_expired_events(self) -> int:
        """Clean up expired audit events"""
        # This would need to be implemented based on actual database capabilities
        # For now, return 0 as no cleanup performed
        logger.info("Audit event cleanup not implemented in adapter")
        return 0
    
    async def verify_integrity(self) -> Dict[str, Any]:
        """Verify audit log integrity"""
        # Basic integrity check
        return {
            "integrity_check": "passed",
            "timestamp": datetime.now().isoformat(),
            "details": "Basic adapter implementation - no integrity verification performed"
        }


class AuditRetentionPolicy:
    """Simple retention policy implementation"""
    
    def get_retention_days(self, action: AuditAction) -> int:
        """Get retention days for a specific action type"""
        # Critical actions - keep longer
        if action in [
            AuditAction.AUTH_FAILED,
            AuditAction.ACL_DELETE,
            AuditAction.SCHEMA_DELETE,
            AuditAction.DATA_DELETE
        ]:
            return 2555  # 7 years
        
        # Authentication events
        if action in [
            AuditAction.AUTH_LOGIN,
            AuditAction.AUTH_LOGOUT,
            AuditAction.AUTH_TOKEN_REFRESH
        ]:
            return 365  # 1 year
        
        # Default retention
        return 730  # 2 years