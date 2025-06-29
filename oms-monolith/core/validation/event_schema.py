"""
P2 Phase: Event Schema Standardization
이벤트 타입/필드 중앙 정의 - Quiver → OMS 이벤트 매핑 표준화

REQ-P2-1: Event schema standardization for Quiver → JetStream → OMS flow
"""

from enum import Enum
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from datetime import datetime

# Event Schema Constants - 중앙 정의
EVENT_SCHEMA_VERSION = "1.0.0"
EVENT_NAMESPACE = "quiver.events"

class QuiverEventType(str, Enum):
    """Quiver MSA에서 발생하는 이벤트 타입"""
    # Sensor data events
    SENSOR_DATA_RECEIVED = "sensor.data.received"
    SENSOR_DATA_PROCESSED = "sensor.data.processed"
    SENSOR_ANOMALY_DETECTED = "sensor.anomaly.detected"
    
    # Time series analysis events
    TIMESERIES_PATTERN_DETECTED = "timeseries.pattern.detected"
    TIMESERIES_THRESHOLD_EXCEEDED = "timeseries.threshold.exceeded"
    TIMESERIES_CORRELATION_FOUND = "timeseries.correlation.found"
    
    # Data quality events
    DATA_QUALITY_CHECK_FAILED = "data.quality.check.failed"
    DATA_QUALITY_CHECK_PASSED = "data.quality.check.passed"
    DATA_DRIFT_DETECTED = "data.drift.detected"
    
    # Pipeline events
    PIPELINE_STARTED = "pipeline.started"
    PIPELINE_COMPLETED = "pipeline.completed"
    PIPELINE_FAILED = "pipeline.failed"
    
    # Model events
    MODEL_TRAINING_COMPLETED = "model.training.completed"
    MODEL_PREDICTION_GENERATED = "model.prediction.generated"
    MODEL_PERFORMANCE_DEGRADED = "model.performance.degraded"


class OMSMappingAction(str, Enum):
    """OMS에서 수행할 매핑 액션"""
    UPDATE_ENTITY_STATE = "update_entity_state"
    CREATE_EVENT_LOG = "create_event_log"  
    TRIGGER_VALIDATION = "trigger_validation"
    UPDATE_METADATA = "update_metadata"
    SEND_ALERT = "send_alert"
    NO_ACTION = "no_action"


class EventSeverity(str, Enum):
    """이벤트 심각도 수준"""
    CRITICAL = "critical"  # 즉시 액션 필요
    HIGH = "high"         # 신속한 처리 필요  
    MEDIUM = "medium"     # 정상적인 처리
    LOW = "low"          # 로깅만
    INFO = "info"        # 정보성


@dataclass
class EventFieldSpec:
    """이벤트 필드 스펙 정의"""
    name: str
    field_type: str  # "string", "number", "timestamp", "array", "object"
#     required: bool = True
    description: str = ""
    default_value: Any = None
    validation_pattern: Optional[str] = None  # regex for string validation


@dataclass  
class EventSchema:
    """표준 이벤트 스키마 정의"""
    event_type: QuiverEventType
    oms_action: OMSMappingAction
    severity: EventSeverity
    fields: List[EventFieldSpec] = field(default_factory=list)
    ontology_target: Optional[str] = None  # Target ontology class
    description: str = ""
    
    # Processing configuration
    enable_deduplication: bool = True
    idempotency_key_fields: List[str] = field(default_factory=list)
    ttl_seconds: int = 300
    retry_max_attempts: int = 3


# 표준 이벤트 스키마 정의 레지스트리
STANDARD_EVENT_SCHEMAS: Dict[QuiverEventType, EventSchema] = {
    
    # Sensor data events
    QuiverEventType.SENSOR_DATA_RECEIVED: EventSchema(
        event_type=QuiverEventType.SENSOR_DATA_RECEIVED,
        oms_action=OMSMappingAction.UPDATE_ENTITY_STATE,
        severity=EventSeverity.INFO,
        ontology_target="SensorReading",
        description="Sensor data received and ready for processing",
        idempotency_key_fields=["sensor_id", "timestamp", "reading_id"],
        fields=[
            EventFieldSpec("sensor_id", "string", required=True, description="Unique sensor identifier"),
            EventFieldSpec("location", "object", required=False, description="GPS coordinates"),
            EventFieldSpec("metadata", "object", required=False, description="Additional sensor metadata")
        ]
    ),
    
    QuiverEventType.SENSOR_ANOMALY_DETECTED: EventSchema(
        event_type=QuiverEventType.SENSOR_ANOMALY_DETECTED,
        oms_action=OMSMappingAction.SEND_ALERT,
        severity=EventSeverity.HIGH,
        ontology_target="AnomalyEvent",
        description="Anomaly detected in sensor readings",
        idempotency_key_fields=["sensor_id", "anomaly_id", "detection_timestamp"],
        fields=[
            EventFieldSpec("baseline_value", "number", required=False),
            EventFieldSpec("deviation_percentage", "number", required=False)
        ]
    ),
    
    # Time series analysis events  
    QuiverEventType.TIMESERIES_PATTERN_DETECTED: EventSchema(
        event_type=QuiverEventType.TIMESERIES_PATTERN_DETECTED,
        oms_action=OMSMappingAction.UPDATE_METADATA,
        severity=EventSeverity.MEDIUM,
        ontology_target="TimeSeriesPattern",
        description="Pattern detected in time series data",
        idempotency_key_fields=["pattern_id", "dataset_id", "detection_timestamp"],
        fields=[
            EventFieldSpec("affected_metrics", "array", required=False)
        ]
    ),
    
    QuiverEventType.TIMESERIES_THRESHOLD_EXCEEDED: EventSchema(
        event_type=QuiverEventType.TIMESERIES_THRESHOLD_EXCEEDED,
        oms_action=OMSMappingAction.SEND_ALERT,
        severity=EventSeverity.HIGH,
        ontology_target="ThresholdViolation",
        description="Time series threshold exceeded",
        idempotency_key_fields=["metric_id", "threshold_id", "violation_timestamp"],
        fields=[
            EventFieldSpec("duration_seconds", "number", required=False)
        ]
    ),
    
    # Data quality events
    QuiverEventType.DATA_QUALITY_CHECK_FAILED: EventSchema(
        event_type=QuiverEventType.DATA_QUALITY_CHECK_FAILED,
        oms_action=OMSMappingAction.TRIGGER_VALIDATION,
        severity=EventSeverity.HIGH,
        ontology_target="DataQualityIssue",
        description="Data quality check failed",
        idempotency_key_fields=["dataset_id", "check_id", "failure_timestamp"],
        fields=[
            EventFieldSpec("sample_failures", "array", required=False, description="Sample of failed records")
        ]
    ),
    
    # Pipeline events
    QuiverEventType.PIPELINE_FAILED: EventSchema(
        event_type=QuiverEventType.PIPELINE_FAILED,
        oms_action=OMSMappingAction.CREATE_EVENT_LOG,
        severity=EventSeverity.CRITICAL,
        ontology_target="PipelineFailure",
        description="Data pipeline execution failed",
        idempotency_key_fields=["pipeline_id", "execution_id", "failure_timestamp"],
        fields=[
            EventFieldSpec("error_code", "string", required=False),
            EventFieldSpec("stack_trace", "string", required=False),
            EventFieldSpec("affected_datasets", "array", required=False)
        ]
    )
}


@dataclass
class QuiverEvent:
    """표준 Quiver 이벤트 구조"""
    # Standard envelope fields
    event_id: str
    event_type: QuiverEventType
    timestamp: datetime
    source_service: str = "quiver"
    schema_version: str = EVENT_SCHEMA_VERSION
    
    # Event payload
    data: Dict[str, Any] = field(default_factory=dict)
    
    # Processing metadata
    correlation_id: Optional[str] = None
    trace_id: Optional[str] = None
    retry_count: int = 0
    
    def get_idempotency_key(self) -> str:
        """생성 idempotency key for deduplication"""
        schema = STANDARD_EVENT_SCHEMAS.get(self.event_type)
        if not schema or not schema.idempotency_key_fields:
            return f"{self.event_type}:{self.event_id}"
        
        key_parts = [str(self.event_type.value)]
        for field_name in schema.idempotency_key_fields:
            value = self.data.get(field_name, "")
            key_parts.append(str(value))
        
        return ":".join(key_parts)
    
    def validate_schema(self) -> List[str]:
        """Validate event against schema"""
        errors = []
        schema = STANDARD_EVENT_SCHEMAS.get(self.event_type)
        
        if not schema:
            return [f"Unknown event type: {self.event_type}"]
        
        # Check required fields
        for field_spec in schema.fields:
            if field_spec.required and field_spec.name not in self.data:
                errors.append(f"Missing required field: {field_spec.name}")
            
            # Type validation (basic)
            if field_spec.name in self.data:
                value = self.data[field_spec.name]
                if field_spec.field_type == "number" and not isinstance(value, (int, float)):
                    errors.append(f"Field {field_spec.name} must be a number")
                elif field_spec.field_type == "string" and not isinstance(value, str):
                    errors.append(f"Field {field_spec.name} must be a string")
                elif field_spec.field_type == "array" and not isinstance(value, list):
                    errors.append(f"Field {field_spec.name} must be an array")
        
        return errors


# JetStream Subject Mapping
class JetStreamSubjects:
    """JetStream subject patterns for Quiver events"""
    
    # Base subjects
    SENSOR_DATA = f"{EVENT_NAMESPACE}.sensor"
    TIMESERIES = f"{EVENT_NAMESPACE}.timeseries"  
    DATA_QUALITY = f"{EVENT_NAMESPACE}.data_quality"
    PIPELINE = f"{EVENT_NAMESPACE}.pipeline"
    MODEL = f"{EVENT_NAMESPACE}.model"
    
    # Subject mapping for event types
    SUBJECT_MAPPING: Dict[QuiverEventType, str] = {
        # Sensor events
        QuiverEventType.SENSOR_DATA_RECEIVED: f"{SENSOR_DATA}.received",
        QuiverEventType.SENSOR_DATA_PROCESSED: f"{SENSOR_DATA}.processed", 
        QuiverEventType.SENSOR_ANOMALY_DETECTED: f"{SENSOR_DATA}.anomaly",
        
        # Timeseries events
        QuiverEventType.TIMESERIES_PATTERN_DETECTED: f"{TIMESERIES}.pattern",
        QuiverEventType.TIMESERIES_THRESHOLD_EXCEEDED: f"{TIMESERIES}.threshold",
        QuiverEventType.TIMESERIES_CORRELATION_FOUND: f"{TIMESERIES}.correlation",
        
        # Data quality events
        QuiverEventType.DATA_QUALITY_CHECK_FAILED: f"{DATA_QUALITY}.failed",
        QuiverEventType.DATA_QUALITY_CHECK_PASSED: f"{DATA_QUALITY}.passed",
        QuiverEventType.DATA_DRIFT_DETECTED: f"{DATA_QUALITY}.drift",
        
        # Pipeline events
        QuiverEventType.PIPELINE_STARTED: f"{PIPELINE}.started",
        QuiverEventType.PIPELINE_COMPLETED: f"{PIPELINE}.completed",
        QuiverEventType.PIPELINE_FAILED: f"{PIPELINE}.failed",
        
        # Model events
        QuiverEventType.MODEL_TRAINING_COMPLETED: f"{MODEL}.training_completed",
        QuiverEventType.MODEL_PREDICTION_GENERATED: f"{MODEL}.prediction", 
        QuiverEventType.MODEL_PERFORMANCE_DEGRADED: f"{MODEL}.performance_degraded"
    }
    
    @classmethod
    def get_subject(cls, event_type: QuiverEventType) -> str:
        """Get JetStream subject for event type"""
        return cls.SUBJECT_MAPPING.get(event_type, f"{EVENT_NAMESPACE}.unknown")
    
    @classmethod
    def get_wildcard_subjects(cls) -> List[str]:
        """Get wildcard subjects for subscription"""
        return [
            f"{cls.SENSOR_DATA}.*",
            f"{cls.TIMESERIES}.*", 
            f"{cls.DATA_QUALITY}.*",
            f"{cls.PIPELINE}.*",
            f"{cls.MODEL}.*"
        ]


# Utility functions
def create_event_from_dict(event_dict: Dict[str, Any]) -> QuiverEvent:
    """Create QuiverEvent from dictionary (e.g., from JetStream message)"""
    return QuiverEvent(
        event_id=event_dict["event_id"],
        event_type=QuiverEventType(event_dict["event_type"]),
        timestamp=datetime.fromisoformat(event_dict["timestamp"]),
        source_service=event_dict.get("source_service", "quiver"),
        schema_version=event_dict.get("schema_version", EVENT_SCHEMA_VERSION),
        data=event_dict.get("data", {}),
        correlation_id=event_dict.get("correlation_id"),
        trace_id=event_dict.get("trace_id"),
        retry_count=event_dict.get("retry_count", 0)
    )


def get_event_schema(event_type: QuiverEventType) -> Optional[EventSchema]:
    """Get schema for event type"""
    return STANDARD_EVENT_SCHEMAS.get(event_type)


def validate_event_dict(event_dict: Dict[str, Any]) -> List[str]:
    """Validate event dictionary against schema"""
    try:
        event = create_event_from_dict(event_dict)
        return event.validate_schema()
    except Exception as e:
        return [f"Invalid event structure: {str(e)}"]