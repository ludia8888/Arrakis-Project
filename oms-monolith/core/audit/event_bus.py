"""
Audit Event Bus - Interface and implementation for event publishing
"""
from typing import Optional, Protocol
from abc import abstractmethod

from core.audit.models import AuditEventV1
from core.event_publisher.outbox_service import OutboxService, get_outbox_service
from utils.logger import get_logger

logger = get_logger(__name__)


class AuditEventBusInterface(Protocol):
    """Interface for audit event publishing"""
    
    @abstractmethod
    async def publish_event(self, event: AuditEventV1) -> bool:
        """Publish an audit event to the event stream"""
        ...


class AuditEventBus(AuditEventBusInterface):
    """
    Concrete implementation of audit event bus
    Publishes events to NATS via Outbox pattern
    """
    
    def __init__(self, outbox_service: Optional[OutboxService] = None):
        self.outbox_service = outbox_service
        self.enabled = True
    
    async def publish_event(self, event: AuditEventV1) -> bool:
        """Publish an audit event to the event stream"""
        if not self.enabled:
            return False
        
        try:
            if not self.outbox_service:
                self.outbox_service = await get_outbox_service()
            
            # Convert to CloudEvent format
            cloudevent = event.to_cloudevent()
            
            # Publish via Outbox
            await self.outbox_service.publish_event(
                event_type="audit.activity.v1",
                event_data=cloudevent,
                source="/oms",
                subject=f"{event.target.resource_type.value}/{event.target.resource_id}",
                correlation_id=event.request_id
            )
            
            logger.debug(f"Published audit event to stream: {event.id}")
            return True
            
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Network error publishing audit event {event.id} to stream: {e}")
            return False
        except RuntimeError as e:
            logger.error(f"Runtime error publishing audit event {event.id} to stream: {e}")
            return False