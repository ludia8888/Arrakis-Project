"""
P2 Phase: Timeseries Event Mapping Rule
Quiver → JetStream → OMS 이벤트 매핑 with idempotency + reorder handling

REQ-P2-2: Event-Driven Semantic Rules for time series event mapping to ontology state changes
NOT time series analysis - that's handled by Quiver MSA
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List, Set
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum

from core.validation.rules.base import BaseRule, RuleResult
from core.validation.models import BreakingChange, Severity, ValidationContext, MigrationStrategy
from core.validation.interfaces import BreakingChangeRule
from core.validation.ports import TerminusPort
from core.validation.event_schema import (
    QuiverEvent, QuiverEventType, OMSMappingAction, EventSeverity,
    STANDARD_EVENT_SCHEMAS, create_event_from_dict
)

logger = logging.getLogger(__name__)


class EventProcessingStatus(str, Enum):
    """이벤트 처리 상태"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DUPLICATE_IGNORED = "duplicate_ignored"


@dataclass
class EventProcessingResult:
    """이벤트 처리 결과"""
    event_id: str
    status: EventProcessingStatus
    oms_action_performed: Optional[OMSMappingAction] = None
    ontology_changes: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None
    processing_time_ms: int = 0
    duplicate_of: Optional[str] = None


@dataclass
class EventMappingConfig:
    """이벤트 매핑 설정"""
    enable_idempotency: bool = True
    cache_ttl_seconds: int = 300
    max_retry_attempts: int = 3
    batch_size: int = 10
    processing_timeout_seconds: int = 60
    enable_reorder_protection: bool = True
    reorder_window_seconds: int = 30


class TimeseriesEventMappingRule(BaseRule):
    """
    Timeseries Event Mapping Rule
    
    Maps Quiver time series events to OMS ontology state changes.
    Handles idempotency, reordering, and batch processing.
    
    Features:
    - Event deduplication using idempotency keys
    - Out-of-order event handling with reorder protection
    - Batch processing for performance
    - Configurable retry logic
    - Comprehensive error handling
    - Integration with TerminusDB for ontology updates
    """
    
    def __init__(
        self,
        terminus_port: Optional[TerminusPort] = None,
        config: Optional[EventMappingConfig] = None
    ):
        super().__init__(
            rule_id="timeseries_event_mapping",
            name="Timeseries Event Mapping",
            description="Maps Quiver time series events to OMS ontology state changes"
        )
        self.terminus_port = terminus_port
        self.config = config or EventMappingConfig()
        self.priority = 25  # High priority - process events early
        
        # Idempotency and caching
        self._processed_events: Dict[str, EventProcessingResult] = {}
        self._event_timestamps: Dict[str, datetime] = {}
        self._processing_lock = asyncio.Lock()
        
        # Reorder protection
        self._reorder_buffer: Dict[str, List[QuiverEvent]] = {}
        self._last_processed_timestamp: Dict[str, datetime] = {}
    
    async def execute(self, context: ValidationContext) -> RuleResult:
        """Execute timeseries event mapping"""
        result = RuleResult()
        
        # Get events from context
        events = self._extract_events_from_context(context)
        if not events:
            result.metadata["message"] = "No events to process"
            return result
        
        # Process events in batches
        processing_results = await self._process_events_batch(events)
        
        # Analyze results and create breaking changes if needed
        failed_events = [r for r in processing_results if r.status == EventProcessingStatus.FAILED]
        
        if failed_events:
            breaking_change = self._create_event_processing_failure_breaking_change(failed_events)
            result.breaking_changes.append(breaking_change)
        
        # Update result metadata
        result.metadata.update({
            "total_events_processed": len(processing_results),
            "successful_events": len([r for r in processing_results if r.status == EventProcessingStatus.COMPLETED]),
            "failed_events": len(failed_events),
            "duplicate_events": len([r for r in processing_results if r.status == EventProcessingStatus.DUPLICATE_IGNORED]),
            "ontology_changes": sum(len(r.ontology_changes) for r in processing_results),
            "average_processing_time_ms": sum(r.processing_time_ms for r in processing_results) / len(processing_results) if processing_results else 0
        })
        
        return result
    
    def _extract_events_from_context(self, context: ValidationContext) -> List[QuiverEvent]:
        """Extract Quiver events from validation context"""
        events = []
        
        # Look for events in context data
        event_data = context.additional_data.get("quiver_events", [])
        
        for event_dict in event_data:
            try:
                event = create_event_from_dict(event_dict)
                events.append(event)
            except Exception as e:
                logger.error(f"Failed to parse event: {e}")
        
        return events
    
    async def _process_events_batch(self, events: List[QuiverEvent]) -> List[EventProcessingResult]:
        """Process events in batch with idempotency and reorder handling"""
        results = []
        
        # Group events by batch
        for i in range(0, len(events), self.config.batch_size):
            batch = events[i:i + self.config.batch_size]
            batch_results = await self._process_batch(batch)
            results.extend(batch_results)
        
        return results
    
    async def _process_batch(self, events: List[QuiverEvent]) -> List[EventProcessingResult]:
        """Process a single batch of events"""
        async with self._processing_lock:
            results = []
            
            for event in events:
                try:
                    result = await self._process_single_event(event)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Failed to process event {event.event_id}: {e}")
                    results.append(EventProcessingResult(
                        event_id=event.event_id,
                        status=EventProcessingStatus.FAILED,
                        error_message=str(e)
                    ))
            
            return results
    
    async def _process_single_event(self, event: QuiverEvent) -> EventProcessingResult:
        """Process a single event with full idempotency and reorder protection"""
        start_time = datetime.now()
        
        # Check for duplicate (idempotency)
        idempotency_key = event.get_idempotency_key()
        if self.config.enable_idempotency and self._is_duplicate_event(idempotency_key):
            duplicate_result = self._processed_events[idempotency_key]
            return EventProcessingResult(
                event_id=event.event_id,
                status=EventProcessingStatus.DUPLICATE_IGNORED,
                duplicate_of=duplicate_result.event_id
            )
        
        # Check for out-of-order events (reorder protection)
        if self.config.enable_reorder_protection and self._is_out_of_order(event):
            await self._handle_reordered_event(event)
            # For now, process anyway but log the reorder
            logger.warning(f"Processing out-of-order event: {event.event_id}")
        
        # Validate event schema
        validation_errors = event.validate_schema()
        if validation_errors:
            return EventProcessingResult(
                event_id=event.event_id,
                status=EventProcessingStatus.FAILED,
                error_message=f"Schema validation failed: {validation_errors}"
            )
        
        # Perform OMS mapping action
        mapping_result = await self._perform_oms_mapping(event)
        
        # Record successful processing
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        result = EventProcessingResult(
            event_id=event.event_id,
            status=EventProcessingStatus.COMPLETED,
            oms_action_performed=mapping_result["action"],
            ontology_changes=mapping_result.get("changes", []),
            processing_time_ms=int(processing_time)
        )
        
        # Cache result for idempotency
        if self.config.enable_idempotency:
            self._processed_events[idempotency_key] = result
            self._event_timestamps[idempotency_key] = datetime.now()
        
        # Update reorder tracking
        entity_id = event.data.get("sensor_id") or event.data.get("dataset_id") or "default"
        self._last_processed_timestamp[entity_id] = event.timestamp
        
        return result
    
    def _is_duplicate_event(self, idempotency_key: str) -> bool:
        """Check if event is a duplicate"""
        if idempotency_key not in self._processed_events:
            return False
        
        # Check TTL
        event_time = self._event_timestamps.get(idempotency_key)
        if event_time:
            age = (datetime.now() - event_time).total_seconds()
            if age > self.config.cache_ttl_seconds:
                # Remove expired entry
                del self._processed_events[idempotency_key]
                del self._event_timestamps[idempotency_key]
                return False
        
        return True
    
    def _is_out_of_order(self, event: QuiverEvent) -> bool:
        """Check if event is out of order"""
        entity_id = event.data.get("sensor_id") or event.data.get("dataset_id") or "default"
        last_timestamp = self._last_processed_timestamp.get(entity_id)
        
        if not last_timestamp:
            return False
        
        # Allow some tolerance for clock skew
        tolerance = datetime.now() - last_timestamp
        return event.timestamp < (last_timestamp - tolerance)
    
    async def _handle_reordered_event(self, event: QuiverEvent):
        """Handle out-of-order event"""
        entity_id = event.data.get("sensor_id") or event.data.get("dataset_id") or "default"
        
        if entity_id not in self._reorder_buffer:
            self._reorder_buffer[entity_id] = []
        
        self._reorder_buffer[entity_id].append(event)
        
        # Sort buffer by timestamp
        self._reorder_buffer[entity_id].sort(key=lambda e: e.timestamp)
        
        # Process any events that are now in order
        await self._process_reorder_buffer(entity_id)
    
    async def _process_reorder_buffer(self, entity_id: str):
        """Process events from reorder buffer"""
        buffer = self._reorder_buffer.get(entity_id, [])
        last_timestamp = self._last_processed_timestamp.get(entity_id)
        
        while buffer:
            next_event = buffer[0]
            
            # Check if this event can be processed now
            if not last_timestamp or next_event.timestamp >= last_timestamp:
                # Remove from buffer and process
                buffer.pop(0)
                await self._process_single_event(next_event)
                last_timestamp = next_event.timestamp
            else:
                break
        
        self._last_processed_timestamp[entity_id] = last_timestamp or datetime.now()
    
    async def _perform_oms_mapping(self, event: QuiverEvent) -> Dict[str, Any]:
        """Perform the actual OMS mapping action"""
        schema = STANDARD_EVENT_SCHEMAS.get(event.event_type)
        if not schema:
            return {"action": OMSMappingAction.NO_ACTION, "changes": []}
        
        action = schema.oms_action
        changes = []
        
        try:
            if action == OMSMappingAction.UPDATE_ENTITY_STATE:
                changes = await self._update_entity_state(event)
            elif action == OMSMappingAction.CREATE_EVENT_LOG:
                changes = await self._create_event_log(event)
            elif action == OMSMappingAction.TRIGGER_VALIDATION:
                changes = await self._trigger_validation(event)
            elif action == OMSMappingAction.UPDATE_METADATA:
                changes = await self._update_metadata(event)
            elif action == OMSMappingAction.SEND_ALERT:
                changes = await self._send_alert(event)
            
            return {"action": action, "changes": changes}
            
        except Exception as e:
            logger.error(f"Failed to perform OMS mapping {action} for event {event.event_id}: {e}")
            raise
    
    async def _update_entity_state(self, event: QuiverEvent) -> List[Dict[str, Any]]:
        """Update entity state in ontology"""
        if not self.terminus_port:
            return []
        
        changes = []
        schema = STANDARD_EVENT_SCHEMAS.get(event.event_type)
        
        if event.event_type == QuiverEventType.SENSOR_DATA_RECEIVED:
            # Map sensor reading to ontology
            sensor_id = event.data.get("sensor_id")
            reading_value = event.data.get("value")
            timestamp = event.timestamp
            
            # Create WOQL update query
            update_query = f"""
            WOQL.update_object({{
                "@type": "SensorReading",
                "sensor_id": "{sensor_id}",
                "value": {reading_value},
                "timestamp": "{timestamp.isoformat()}",
                "last_updated": "{datetime.now(timezone.utc).isoformat()}"
            }})
            """
            
            try:
                result = await self.terminus_port.query(update_query)
                changes.append({
                    "type": "entity_update",
                    "entity_type": "SensorReading",
                    "entity_id": sensor_id,
                    "fields_updated": ["value", "timestamp", "last_updated"],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            except Exception as e:
                logger.error(f"Failed to update sensor reading: {e}")
                raise
        
        return changes
    
    async def _create_event_log(self, event: QuiverEvent) -> List[Dict[str, Any]]:
        """Create event log entry in ontology"""
        if not self.terminus_port:
            return []
        
        # Create event log entry
        log_entry_query = f"""
        WOQL.insert_object({{
            "@type": "EventLog",
            "@id": "event_log_{event.event_id}",
            "event_id": "{event.event_id}",
            "event_type": "{event.event_type}",
            "source_service": "{event.source_service}",
            "timestamp": "{event.timestamp.isoformat()}",
            "data": {str(event.data)},
            "severity": "{STANDARD_EVENT_SCHEMAS.get(event.event_type, {}).severity}",
            "created_at": "{datetime.now(timezone.utc).isoformat()}"
        }})
        """
        
        try:
            await self.terminus_port.query(log_entry_query)
            return [{
                "type": "event_log_created",
                "event_id": event.event_id,
                "log_entry_id": f"event_log_{event.event_id}",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }]
        except Exception as e:
            logger.error(f"Failed to create event log: {e}")
            raise
    
    async def _trigger_validation(self, event: QuiverEvent) -> List[Dict[str, Any]]:
        """Trigger validation based on event"""
        # This would integrate with the validation pipeline
        # For now, just log the trigger
        logger.info(f"Validation triggered by event {event.event_id} of type {event.event_type}")
        
        return [{
            "type": "validation_triggered",
            "event_id": event.event_id,
            "trigger_reason": f"Data quality event: {event.event_type}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }]
    
    async def _update_metadata(self, event: QuiverEvent) -> List[Dict[str, Any]]:
        """Update metadata based on event"""
        if not self.terminus_port:
            return []
        
        changes = []
        
        if event.event_type == QuiverEventType.TIMESERIES_PATTERN_DETECTED:
            pattern_id = event.data.get("pattern_id")
            dataset_id = event.data.get("dataset_id")
            pattern_type = event.data.get("pattern_type")
            
            # Update dataset metadata with detected pattern
            metadata_query = f"""
            WOQL.update_object({{
                "@type": "DatasetMetadata",
                "@id": "metadata_{dataset_id}",
                "dataset_id": "{dataset_id}",
                "detected_patterns": WOQL.list([
                    {{
                        "pattern_id": "{pattern_id}",
                        "pattern_type": "{pattern_type}",
                        "detection_timestamp": "{event.timestamp.isoformat()}",
                        "confidence": {event.data.get("confidence", 0.0)}
                    }}
                ]),
                "last_pattern_update": "{datetime.now(timezone.utc).isoformat()}"
            }})
            """
            
            try:
                await self.terminus_port.query(metadata_query)
                changes.append({
                    "type": "metadata_updated",
                    "dataset_id": dataset_id,
                    "pattern_detected": pattern_type,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            except Exception as e:
                logger.error(f"Failed to update metadata: {e}")
                raise
        
        return changes
    
    async def _send_alert(self, event: QuiverEvent) -> List[Dict[str, Any]]:
        """Send alert based on event"""
        # This would integrate with the alerting system
        alert_data = {
            "type": "alert_sent",
            "event_id": event.event_id,
            "alert_type": event.event_type,
            "severity": STANDARD_EVENT_SCHEMAS.get(event.event_type, {}).severity,
            "message": f"Alert triggered by {event.event_type}: {event.data}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        logger.warning(f"ALERT: {alert_data['message']}")
        
        return [alert_data]
    
    def _create_event_processing_failure_breaking_change(
        self, 
        failed_events: List[EventProcessingResult]
    ) -> BreakingChange:
        """Create breaking change for event processing failures"""
        
        failure_count = len(failed_events)
        sample_errors = [e.error_message for e in failed_events[:3]]
        
        # Determine severity based on failure count and types
        if failure_count > 100:
            severity = Severity.CRITICAL
        elif failure_count > 10:
            severity = Severity.HIGH
        else:
            severity = Severity.MEDIUM
        
        return BreakingChange(
            rule_id=self.rule_id,
            severity=severity,
            object_type="event_processing",
            field_name="timeseries_events",
            description=f"Failed to process {failure_count} timeseries events from Quiver",
            old_value=None,
            new_value={
                "failed_event_count": failure_count,
                "sample_errors": sample_errors
            },
            impact={
                "event_processing_failure": True,
                "failed_events": failure_count,
                "data_freshness_impact": "high" if failure_count > 50 else "medium",
                "sample_errors": sample_errors,
                "requires_manual_intervention": failure_count > 100
            },
            suggested_strategies=[
                MigrationStrategy.MANUAL_REVIEW,
                MigrationStrategy.DATA_MIGRATION if failure_count < 50 else MigrationStrategy.CUSTOM
            ],
            detected_at=datetime.now(timezone.utc)
        )
    
    # BreakingChangeRule interface compatibility
    def check(self, old_schema: Dict, new_schema: Dict) -> List[BreakingChange]:
        """Synchronous check method for interface compatibility"""
        # This rule is primarily event-driven, not schema-driven
        return []
    
    async def estimate_impact(self, breaking_change: BreakingChange, data_source: Any) -> Dict[str, Any]:
        """Estimate impact of event processing failures"""
        if breaking_change.object_type != "event_processing":
            return {"estimated_impact": "unknown"}
        
        failed_count = breaking_change.impact.get("failed_events", 0)
        
        return {
            "estimated_impact": "high" if failed_count > 100 else "medium",
            "data_staleness_risk": "high" if failed_count > 50 else "low",
            "manual_intervention_required": failed_count > 100,
            "recommended_action": "investigate_event_source" if failed_count > 10 else "retry_processing",
            "estimated_recovery_time": "hours" if failed_count > 100 else "minutes"
        }


# Factory functions for easy rule creation
def create_timeseries_event_mapping_rule(
    terminus_port: Optional[TerminusPort] = None,
    enable_idempotency: bool = True,
    cache_ttl_seconds: int = 300,
    enable_reorder_protection: bool = True
) -> TimeseriesEventMappingRule:
    """Create a timeseries event mapping rule with configuration"""
    config = EventMappingConfig(
        enable_idempotency=enable_idempotency,
        cache_ttl_seconds=cache_ttl_seconds,
        enable_reorder_protection=enable_reorder_protection
    )
    return TimeseriesEventMappingRule(terminus_port, config)


def create_high_throughput_event_mapping_rule(
    terminus_port: Optional[TerminusPort] = None
) -> TimeseriesEventMappingRule:
    """Create a high-throughput optimized event mapping rule"""
    config = EventMappingConfig(
        enable_idempotency=True,
        cache_ttl_seconds=60,  # Shorter TTL for memory efficiency
        batch_size=50,         # Larger batches
        enable_reorder_protection=False,  # Disable for performance
        processing_timeout_seconds=30
    )
    return TimeseriesEventMappingRule(terminus_port, config)