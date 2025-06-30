"""
Unified Audit Logger - Single Audit Trail
모든 감사 로그의 단일 경로 통합으로 추적 일관성 보장
"""

import time
import json
import uuid
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timezone

from shared.infrastructure.unified_nats_client import get_unified_nats_client, MessageDelivery
from shared.monitoring.unified_metrics import get_metrics_collector
from shared.utils.logger import get_logger

logger = get_logger(__name__)


class AuditEventType(str, Enum):
    """감사 이벤트 타입"""
    # 인증/인가
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    LOGIN = "login"
    LOGOUT = "logout"
    TOKEN_REFRESH = "token_refresh"
    
    # 보안
    SECURITY_VIOLATION = "security_violation"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    CIRCUIT_BREAKER_OPENED = "circuit_breaker_opened"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    
    # 데이터 접근
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    DATA_DELETION = "data_deletion"
    DATA_EXPORT = "data_export"
    
    # 시스템
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    CONFIGURATION_CHANGE = "configuration_change"
    
    # API
    API_REQUEST = "api_request"
    API_ERROR = "api_error"
    
    # 비즈니스
    ONTOLOGY_CHANGE = "ontology_change"
    SCHEMA_VALIDATION = "schema_validation"
    MERGE_OPERATION = "merge_operation"


class AuditSeverity(str, Enum):
    """감사 심각도"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditOutcome(str, Enum):
    """감사 결과"""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    ERROR = "error"


@dataclass
class AuditContext:
    """감사 컨텍스트"""
    # 요청 정보
    request_id: str = ""
    session_id: str = ""
    correlation_id: str = ""
    
    # 사용자 정보
    user_id: str = ""
    user_type: str = "user"  # user, service, admin
    user_roles: List[str] = field(default_factory=list)
    
    # 네트워크 정보
    client_ip: str = ""
    user_agent: str = ""
    forwarded_for: str = ""
    
    # 애플리케이션 정보
    service_name: str = "oms"
    service_version: str = ""
    environment: str = "unknown"
    
    # 비즈니스 컨텍스트
    tenant_id: str = ""
    organization_id: str = ""


@dataclass
class AuditEvent:
    """통합 감사 이벤트"""
    # 기본 정보
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # 이벤트 분류
    event_type: AuditEventType = AuditEventType.API_REQUEST
    category: str = "system"  # security, business, system, compliance
    severity: AuditSeverity = AuditSeverity.LOW
    outcome: AuditOutcome = AuditOutcome.SUCCESS
    
    # 액션 정보
    action: str = ""  # create, read, update, delete, execute
    resource: str = ""  # 리소스 식별자
    resource_type: str = ""  # ontology, schema, user, etc.
    
    # 메시지
    message: str = ""
    description: str = ""
    
    # 데이터
    before_data: Optional[Dict[str, Any]] = None
    after_data: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 컨텍스트
    context: AuditContext = field(default_factory=AuditContext)
    
    # 추가 정보
    duration_ms: Optional[float] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        data = asdict(self)
        
        # CloudEvents 표준 필드 추가
        data["specversion"] = "1.0"
        data["source"] = f"oms/{self.context.service_name}"
        data["type"] = f"com.oms.audit.{self.event_type}"
        data["datacontenttype"] = "application/json"
        
        return data


class UnifiedAuditLogger:
    """
    통합 감사 로거
    
    모든 감사 로그를 단일 경로로 통합하여
    CloudEvents 표준으로 NATS JetStream에 전송
    """
    
    def __init__(self):
        self.nats_client = get_unified_nats_client()
        self.metrics = get_metrics_collector()
        
        # 설정
        self.audit_subject_prefix = "audit"
        self.security_subject_prefix = "security"
        self.compliance_subject_prefix = "compliance"
        
        # 로컬 백업 (NATS 실패 시)
        self._local_buffer: List[AuditEvent] = []
        self._buffer_max_size = 1000
        
        # 필터링 설정
        self._severity_filter = AuditSeverity.LOW  # 최소 기록 심각도
        self._excluded_events: List[AuditEventType] = []
    
    async def log_event(
        self,
        event_type: AuditEventType,
        action: str,
        resource: str,
        outcome: AuditOutcome = AuditOutcome.SUCCESS,
        message: str = "",
        context: Optional[AuditContext] = None,
        **kwargs
    ) -> bool:
        """감사 이벤트 로깅"""
        
        try:
            # 감사 이벤트 생성
            audit_event = AuditEvent(
                event_type=event_type,
                action=action,
                resource=resource,
                outcome=outcome,
                message=message,
                context=context or AuditContext(),
                **kwargs
            )
            
            # 필터링 검사
            if not self._should_log_event(audit_event):
                return True
            
            # Subject 결정
            subject = self._get_audit_subject(audit_event)
            
            # 메트릭 기록
            self.metrics.record_event_published(
                event_type=f"audit_{audit_event.event_type}",
                publisher="unified_audit_logger",
                result="attempted"
            )
            
            # NATS 전송 (JetStream with persistence)
            success = await self.nats_client.publish(
                subject=subject,
                data=audit_event.to_dict(),
                delivery=MessageDelivery.AT_LEAST_ONCE,
                headers={
                    "audit_event_type": audit_event.event_type,
                    "audit_severity": audit_event.severity,
                    "audit_category": audit_event.category
                }
            )
            
            if success:
                logger.debug(f"Audit event logged: {audit_event.event_id}")
                self.metrics.record_event_published(
                    event_type=f"audit_{audit_event.event_type}",
                    publisher="unified_audit_logger",
                    result="success"
                )
            else:
                # NATS 실패 시 로컬 버퍼에 저장
                self._buffer_to_local(audit_event)
                self.metrics.record_event_published(
                    event_type=f"audit_{audit_event.event_type}",
                    publisher="unified_audit_logger",
                    result="buffered"
                )
            
            # 고심각도 이벤트는 추가 로깅
            if audit_event.severity in [AuditSeverity.HIGH, AuditSeverity.CRITICAL]:
                logger.warning(
                    f"HIGH SEVERITY AUDIT: {audit_event.event_type} - "
                    f"User: {audit_event.context.user_id} - "
                    f"Action: {audit_event.action} - "
                    f"Resource: {audit_event.resource} - "
                    f"Outcome: {audit_event.outcome}"
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")
            self.metrics.record_event_published(
                event_type="audit_error",
                publisher="unified_audit_logger",
                result="failure"
            )
            return False
    
    # 특화된 로깅 메서드들
    async def log_authentication(
        self,
        user_id: str,
        action: str,  # login, logout, token_refresh
        outcome: AuditOutcome,
        client_ip: str = "",
        user_agent: str = "",
        error_message: str = "",
        **kwargs
    ) -> bool:
        """인증 이벤트 로깅"""
        
        context = AuditContext(
            user_id=user_id,
            client_ip=client_ip,
            user_agent=user_agent
        )
        
        severity = AuditSeverity.HIGH if outcome == AuditOutcome.FAILURE else AuditSeverity.MEDIUM
        
        return await self.log_event(
            event_type=AuditEventType.AUTHENTICATION,
            action=action,
            resource=f"user:{user_id}",
            outcome=outcome,
            severity=severity,
            category="security",
            message=f"Authentication {action} for user {user_id}",
            error_message=error_message,
            context=context,
            **kwargs
        )
    
    async def log_security_violation(
        self,
        violation_type: str,
        user_id: str,
        resource: str,
        client_ip: str = "",
        details: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> bool:
        """보안 위반 로깅"""
        
        context = AuditContext(
            user_id=user_id,
            client_ip=client_ip
        )
        
        return await self.log_event(
            event_type=AuditEventType.SECURITY_VIOLATION,
            action="violate",
            resource=resource,
            outcome=AuditOutcome.BLOCKED,
            severity=AuditSeverity.HIGH,
            category="security",
            message=f"Security violation: {violation_type}",
            metadata=details or {},
            context=context,
            **kwargs
        )
    
    async def log_data_access(
        self,
        user_id: str,
        action: str,  # read, write, delete, export
        resource: str,
        resource_type: str = "data",
        before_data: Optional[Dict[str, Any]] = None,
        after_data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> bool:
        """데이터 접근 로깅"""
        
        context = AuditContext(user_id=user_id)
        
        # 액션별 이벤트 타입 결정
        event_type_map = {
            "read": AuditEventType.DATA_ACCESS,
            "write": AuditEventType.DATA_MODIFICATION,
            "update": AuditEventType.DATA_MODIFICATION,
            "delete": AuditEventType.DATA_DELETION,
            "export": AuditEventType.DATA_EXPORT
        }
        
        event_type = event_type_map.get(action, AuditEventType.DATA_ACCESS)
        severity = AuditSeverity.HIGH if action in ["delete", "export"] else AuditSeverity.MEDIUM
        
        return await self.log_event(
            event_type=event_type,
            action=action,
            resource=resource,
            resource_type=resource_type,
            outcome=AuditOutcome.SUCCESS,
            severity=severity,
            category="business",
            message=f"Data {action} on {resource_type}",
            before_data=before_data,
            after_data=after_data,
            context=context,
            **kwargs
        )
    
    async def log_api_request(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        user_id: str = "",
        client_ip: str = "",
        duration_ms: float = 0,
        request_id: str = "",
        **kwargs
    ) -> bool:
        """API 요청 로깅"""
        
        context = AuditContext(
            user_id=user_id,
            client_ip=client_ip,
            request_id=request_id
        )
        
        outcome = AuditOutcome.SUCCESS if status_code < 400 else AuditOutcome.FAILURE
        severity = AuditSeverity.LOW if status_code < 400 else AuditSeverity.MEDIUM
        
        return await self.log_event(
            event_type=AuditEventType.API_REQUEST,
            action=method.lower(),
            resource=endpoint,
            resource_type="api_endpoint",
            outcome=outcome,
            severity=severity,
            category="system",
            message=f"{method} {endpoint} -> {status_code}",
            duration_ms=duration_ms,
            metadata={"status_code": status_code},
            context=context,
            **kwargs
        )
    
    def _should_log_event(self, event: AuditEvent) -> bool:
        """이벤트 로깅 여부 결정"""
        
        # 심각도 필터
        severity_levels = {
            AuditSeverity.LOW: 0,
            AuditSeverity.MEDIUM: 1,
            AuditSeverity.HIGH: 2,
            AuditSeverity.CRITICAL: 3
        }
        
        if severity_levels[event.severity] < severity_levels[self._severity_filter]:
            return False
        
        # 제외 이벤트 확인
        if event.event_type in self._excluded_events:
            return False
        
        return True
    
    def _get_audit_subject(self, event: AuditEvent) -> str:
        """감사 이벤트의 NATS Subject 결정"""
        
        if event.category == "security":
            return f"{self.security_subject_prefix}.{event.event_type}"
        elif event.category == "compliance":
            return f"{self.compliance_subject_prefix}.{event.event_type}"
        else:
            return f"{self.audit_subject_prefix}.{event.category}.{event.event_type}"
    
    def _buffer_to_local(self, event: AuditEvent):
        """로컬 버퍼에 이벤트 저장"""
        
        if len(self._local_buffer) >= self._buffer_max_size:
            # 가장 오래된 이벤트 제거
            self._local_buffer.pop(0)
        
        self._local_buffer.append(event)
        logger.warning(f"Audit event buffered locally: {event.event_id}")
    
    async def flush_local_buffer(self) -> int:
        """로컬 버퍼의 이벤트들을 NATS로 전송"""
        
        if not self._local_buffer:
            return 0
        
        flushed_count = 0
        failed_events = []
        
        for event in self._local_buffer:
            subject = self._get_audit_subject(event)
            success = await self.nats_client.publish(
                subject=subject,
                data=event.to_dict(),
                delivery=MessageDelivery.AT_LEAST_ONCE
            )
            
            if success:
                flushed_count += 1
            else:
                failed_events.append(event)
        
        # 실패한 이벤트들만 버퍼에 유지
        self._local_buffer = failed_events
        
        if flushed_count > 0:
            logger.info(f"Flushed {flushed_count} audit events from local buffer")
        
        return flushed_count
    
    def get_buffer_status(self) -> Dict[str, Any]:
        """버퍼 상태 반환"""
        return {
            "buffered_events": len(self._local_buffer),
            "buffer_max_size": self._buffer_max_size,
            "severity_filter": self._severity_filter,
            "excluded_events": self._excluded_events
        }


# 글로벌 인스턴스
_unified_audit_logger: Optional[UnifiedAuditLogger] = None


def get_unified_audit_logger() -> UnifiedAuditLogger:
    """통합 감사 로거 반환"""
    global _unified_audit_logger
    if _unified_audit_logger is None:
        _unified_audit_logger = UnifiedAuditLogger()
    return _unified_audit_logger


# 편의 함수들
async def log_authentication(
    user_id: str,
    action: str,
    outcome: AuditOutcome,
    client_ip: str = "",
    **kwargs
) -> bool:
    """인증 로깅 편의 함수"""
    logger_instance = get_unified_audit_logger()
    return await logger_instance.log_authentication(
        user_id, action, outcome, client_ip, **kwargs
    )


async def log_security_violation(
    violation_type: str,
    user_id: str,
    resource: str,
    client_ip: str = "",
    **kwargs
) -> bool:
    """보안 위반 로깅 편의 함수"""
    logger_instance = get_unified_audit_logger()
    return await logger_instance.log_security_violation(
        violation_type, user_id, resource, client_ip, **kwargs
    )


async def log_api_request(
    method: str,
    endpoint: str,
    status_code: int,
    user_id: str = "",
    client_ip: str = "",
    duration_ms: float = 0,
    **kwargs
) -> bool:
    """API 요청 로깅 편의 함수"""
    logger_instance = get_unified_audit_logger()
    return await logger_instance.log_api_request(
        method, endpoint, status_code, user_id, client_ip, duration_ms, **kwargs
    )