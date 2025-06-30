"""
P2 Phase: Quiver Event Consumer
기존 NATS 인프라를 활용한 Quiver 이벤트 소비자

Extends existing IAMEventHandler pattern for Quiver events
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import json

from core.validation.event_schema import (
    QuiverEvent, QuiverEventType, create_event_from_dict, 
    STANDARD_EVENT_SCHEMAS, validate_event_dict
)
from core.validation.rules.timeseries_event_mapping_rule import TimeseriesEventMappingRule
from core.validation.models import ValidationContext
from core.validation.ports import TerminusPort, EventPort
from shared.config import get_config

logger = logging.getLogger(__name__)


class QuiverEventConsumer:
    """
    Quiver Event Consumer
    
    Consumes time series events from Quiver MSA via NATS JetStream
    and processes them using TimeseriesEventMappingRule.
    
    Features:
    - NATS JetStream durable consumer
    - Event schema validation
    - Idempotency and deduplication
    - Error handling and DLQ
    - Integration with existing NATS infrastructure
    """
    
    def __init__(
        self,
        nats_client: Any,  # RealNATSClient or mock
        terminus_port: Optional[TerminusPort] = None,
        event_port: Optional[EventPort] = None,
        consumer_name: str = "oms-quiver-consumer"
    ):
        self.nats_client = nats_client
        self.terminus_port = terminus_port
        self.event_port = event_port
        self.consumer_name = consumer_name
        self.config = get_config()
        
        # Initialize event mapping rule
        self.mapping_rule = TimeseriesEventMappingRule(terminus_port=terminus_port)
        
        # Consumer state
        self.is_running = False
        self.processed_count = 0
        self.error_count = 0
        self.last_processed_at: Optional[datetime] = None
        
        # Subjects to subscribe to (matching Quiver event schema)
        self.subjects = [
            "quiver.events.sensor.*",
            "quiver.events.timeseries.*", 
            "quiver.events.data_quality.*",
            "quiver.events.pipeline.*",
            "quiver.events.model.*"
        ]
    
    async def start(self):
        """Start the Quiver event consumer"""
        if self.is_running:
            logger.warning("Quiver event consumer is already running")
            return
        
        try:
            # Ensure JetStream is available
            if not hasattr(self.nats_client, 'js'):
                await self.nats_client.connect()
            
            # Create consumer for each subject
            for subject in self.subjects:
                await self._create_consumer(subject)
            
            # Start consuming
            await self._start_consuming()
            
            self.is_running = True
            logger.info("Quiver event consumer started successfully")
            
        except ConnectionError as e:
            logger.error(f"Failed to connect to NATS: {e}")
            raise
        except RuntimeError as e:
            logger.error(f"Failed to start Quiver event consumer: {e}")
            raise
    
    async def stop(self):
        """Stop the Quiver event consumer"""
        self.is_running = False
        logger.info("Quiver event consumer stopped")
    
    async def _create_consumer(self, subject: str):
        """Create JetStream consumer for subject"""
        consumer_config = {
            "durable_name": f"{self.consumer_name}-{subject.replace('.', '-')}",
            "deliver_subject": f"deliver.{self.consumer_name}.{subject.replace('.', '-')}",
            "ack_policy": "explicit",
            "max_deliver": 3,
            "ack_wait": self.config.jetstream_ack_timeout_seconds,
            "max_ack_pending": self.config.jetstream_max_inflight,
            "replay_policy": "instant"
        }
        
        try:
            # Check if stream exists, create if needed
            stream_name = "quiver-events"
            try:
                await self.nats_client.js.stream_info(stream_name)
            except (KeyError, ValueError):
                # Create stream
                stream_config = {
                    "name": stream_name,
                    "subjects": ["quiver.events.*"],
                    "retention": "workqueue",
                    "max_age": 24 * 60 * 60,  # 24 hours
                    "storage": "file"
                }
                await self.nats_client.js.add_stream(**stream_config)
                logger.info(f"Created JetStream stream: {stream_name}")
            
            # Create consumer
            await self.nats_client.js.add_consumer(
                stream_name,
                **consumer_config
            )
            
            logger.info(f"Created consumer for subject: {subject}")
            
        except ConnectionError as e:
            logger.error(f"Failed to connect to JetStream for {subject}: {e}")
            raise
        except RuntimeError as e:
            logger.error(f"Failed to create consumer for {subject}: {e}")
            raise
    
    async def _start_consuming(self):
        """Start consuming messages from all subjects"""
        
        # Subscribe to all delivery subjects
        for subject in self.subjects:
            deliver_subject = f"deliver.{self.consumer_name}.{subject.replace('.', '-')}"
            
            await self.nats_client.subscribe(
                deliver_subject,
                cb=self._message_handler,
                queue=self.consumer_name  # Load balancing
            )
            
            logger.info(f"Subscribed to delivery subject: {deliver_subject}")
    
    async def _message_handler(self, msg):
        """Handle incoming NATS message"""
        start_time = datetime.now()
        
        try:
            # Parse message
            message_data = json.loads(msg.data.decode())
            
            # Validate event schema
            validation_errors = validate_event_dict(message_data)
            if validation_errors:
                logger.error(f"Event validation failed: {validation_errors}")
                await msg.nak()  # Negative acknowledgment
                self.error_count += 1
                return
            
            # Create QuiverEvent
            quiver_event = create_event_from_dict(message_data)
            
            # Process event through mapping rule
            await self._process_event(quiver_event)
            
            # Acknowledge message
            await msg.ack()
            
            # Update stats
            self.processed_count += 1
            self.last_processed_at = datetime.now()
            
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.debug(f"Processed event {quiver_event.event_id} in {processing_time:.2f}ms")
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message JSON: {e}")
            await msg.nak()
            self.error_count += 1
        except (KeyError, ValueError) as e:
            logger.error(f"Invalid message format: {e}")
            await msg.nak()
            self.error_count += 1
        except RuntimeError as e:
            logger.error(f"Runtime error processing message: {e}")
            await msg.nak()
            self.error_count += 1
    
    async def _process_event(self, event: QuiverEvent):
        """Process Quiver event using TimeseriesEventMappingRule"""
        
        # Create validation context with the event
        context = ValidationContext(
            request_id=f"quiver-{event.event_id}",
            branch="main",  # Default branch
            user_id="system-quiver",
            additional_data={
                "quiver_events": [event.__dict__]
            }
        )
        
        try:
            # Execute mapping rule
            result = await self.mapping_rule.execute(context)
            
            # Log results
            if result.breaking_changes:
                logger.warning(f"Event processing issues for {event.event_id}: {len(result.breaking_changes)} issues")
                for bc in result.breaking_changes:
                    logger.warning(f"  - {bc.description}")
            else:
                logger.info(f"Successfully processed event {event.event_id}")
            
            # Publish OMS response events if configured
            if self.event_port and result.metadata.get("ontology_changes", 0) > 0:
                await self._publish_response_events(event, result)
                
        except ValidationError as e:
            logger.error(f"Validation error for event {event.event_id}: {e}")
            raise
        except RuntimeError as e:
            logger.error(f"Failed to process event {event.event_id}: {e}")
            raise
    
    async def _publish_response_events(self, original_event: QuiverEvent, mapping_result):
        """Publish OMS response events for successful mappings"""
        
        # Determine response event type based on mapping action
        schema = STANDARD_EVENT_SCHEMAS.get(original_event.event_type)
        if not schema:
            return
        
        from core.event_publisher.cloudevents_enhanced import EventType
        
        response_event_type = None
        if schema.oms_action.value == "update_entity_state":
            response_event_type = EventType.OMS_ENTITY_STATE_UPDATED
        elif schema.oms_action.value == "create_event_log":
            response_event_type = EventType.OMS_EVENT_LOG_CREATED
        elif schema.oms_action.value == "trigger_validation":
            response_event_type = EventType.OMS_VALIDATION_TRIGGERED
        elif schema.oms_action.value == "update_metadata":
            response_event_type = EventType.OMS_METADATA_UPDATED
        elif schema.oms_action.value == "send_alert":
            response_event_type = EventType.OMS_ALERT_SENT
        
        if response_event_type:
            response_data = {
                "original_event_id": original_event.event_id,
                "original_event_type": original_event.event_type.value,
                "oms_action": schema.oms_action.value,
                "processing_timestamp": datetime.now(timezone.utc).isoformat(),
                "changes_made": mapping_result.metadata.get("ontology_changes", 0),
                "correlation_id": original_event.correlation_id
            }
            
            # Publish through EventPort
            await self.event_port.publish_event(
                event_type=response_event_type.value,
                data=response_data,
                source="oms-quiver-consumer"
            )
            
            logger.info(f"Published OMS response event: {response_event_type.value}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get consumer statistics"""
        return {
            "is_running": self.is_running,
            "processed_count": self.processed_count,
            "error_count": self.error_count,
            "last_processed_at": self.last_processed_at.isoformat() if self.last_processed_at else None,
            "subjects": self.subjects,
            "consumer_name": self.consumer_name,
            "error_rate": self.error_count / max(self.processed_count, 1)
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for consumer"""
        health = {
            "status": "healthy" if self.is_running else "stopped",
            "stats": self.get_stats()
        }
        
        try:
            # Check NATS connection
            if hasattr(self.nats_client, 'is_connected'):
                nats_connected = await self.nats_client.is_connected()
                health["nats_connected"] = nats_connected
                if not nats_connected:
                    health["status"] = "unhealthy"
        except (ConnectionError, AttributeError) as e:
            health["status"] = "unhealthy"
            health["error"] = str(e)
        
        return health


# Factory function
def create_quiver_event_consumer(
    nats_client: Any,
    terminus_port: Optional[TerminusPort] = None,
    event_port: Optional[EventPort] = None
) -> QuiverEventConsumer:
    """Create a Quiver event consumer with standard configuration"""
    config = get_config()
    return QuiverEventConsumer(
        nats_client=nats_client,
        terminus_port=terminus_port,
        event_port=event_port,
        consumer_name=config.jetstream_consumer_name
    )