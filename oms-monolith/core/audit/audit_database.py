"""
Audit Database - Minimal implementation for system startup
Provides interface for audit storage with external audit service integration
"""
import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from abc import ABC, abstractmethod

from models.audit_events import AuditEventV1, AuditEventFilter

logger = logging.getLogger(__name__)


class AuditDatabase(ABC):
    """Abstract audit database interface"""
    
    @abstractmethod
    async def store_event(self, event: AuditEventV1) -> str:
        """Store audit event and return event ID"""
        pass
    
    @abstractmethod
    async def query_events(self, filter: AuditEventFilter) -> List[AuditEventV1]:
        """Query audit events with filter"""
        pass
    
    @abstractmethod
    async def get_event(self, event_id: str) -> Optional[AuditEventV1]:
        """Get specific audit event by ID"""
        pass


class ExternalAuditDatabase(AuditDatabase):
    """
    External audit service integration
    Routes audit events to external audit service via message queue
    """
    
    def __init__(self, publisher_service=None):
        self.publisher_service = publisher_service
        self.local_cache = {}  # Minimal local cache for immediate queries
        
    async def store_event(self, event: AuditEventV1) -> str:
        """Store event by publishing to external audit service"""
        try:
            # Store in local cache for immediate queries
            self.local_cache[event.event_id] = event
            
            # Publish to external audit service (non-blocking)
            if self.publisher_service:
                await self._publish_to_external_service(event)
            
            logger.debug(f"Audit event stored: {event.event_id}")
            return event.event_id
            
        except Exception as e:
            logger.error(f"Failed to store audit event: {e}")
            raise
    
    async def _publish_to_external_service(self, event: AuditEventV1):
        """Publish event to external audit service"""
        try:
            # Transform event to external format
            external_payload = self._transform_for_external_service(event)
            
            # Publish via message queue or HTTP
            await self.publisher_service.publish_audit_event(external_payload)
            
        except Exception as e:
            logger.warning(f"Failed to publish to external audit service: {e}")
            # Don't fail the main operation - audit is supplementary
    
    def _transform_for_external_service(self, event: AuditEventV1) -> Dict[str, Any]:
        """Transform internal audit event to external service format"""
        return {
            "event_id": event.event_id,
            "actor": event.actor.user_id if event.actor else "system",
            "action": event.action.value if event.action else "unknown",
            "resource": event.target.resource_type if event.target else "unknown",
            "resource_id": event.target.resource_id if event.target else None,
            "timestamp": event.timestamp.isoformat(),
            "before": event.changes.before if event.changes else None,
            "after": event.changes.after if event.changes else None,
            "reason": event.changes.reason if event.changes else None,
            "app": "OMS",
            "compliance_level": event.compliance.level if event.compliance else "standard"
        }
    
    async def query_events(self, filter: AuditEventFilter) -> List[AuditEventV1]:
        """Query events - returns from local cache (limited)"""
        # In production, this would query the external audit service
        # For now, return from local cache
        results = []
        for event in self.local_cache.values():
            if self._matches_filter(event, filter):
                results.append(event)
        
        return results
    
    def _matches_filter(self, event: AuditEventV1, filter: AuditEventFilter) -> bool:
        """Simple filter matching for local cache"""
        if filter.actor_id and event.actor and event.actor.user_id != filter.actor_id:
            return False
        if filter.action and event.action != filter.action:
            return False
        if filter.resource_type and event.target and event.target.resource_type != filter.resource_type:
            return False
        return True
    
    async def get_event(self, event_id: str) -> Optional[AuditEventV1]:
        """Get event by ID from local cache"""
        return self.local_cache.get(event_id)


# Global instance - will be initialized with proper external service integration
_audit_database: Optional[AuditDatabase] = None


async def get_audit_database() -> AuditDatabase:
    """Get audit database instance"""
    global _audit_database
    
    if _audit_database is None:
        # Initialize with external audit service integration
        try:
            # Try to get external publisher service
            from core.event_publisher.nats_publisher import NATSEventPublisher
            publisher = NATSEventPublisher()
            
            # In production, connect to external audit service
            # For now, create with None publisher for basic functionality
            _audit_database = ExternalAuditDatabase(publisher_service=None)
            
        except Exception as e:
            logger.warning(f"Failed to initialize external audit integration: {e}")
            _audit_database = ExternalAuditDatabase(publisher_service=None)
    
    return _audit_database


def reset_audit_database():
    """Reset audit database instance (for testing)"""
    global _audit_database
    _audit_database = None