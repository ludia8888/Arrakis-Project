"""
감사 로그 관련 공통 모델
모든 서비스에서 사용하는 감사 로그 스키마
"""
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import Field
from .base import BaseModel, BaseEntity


class AuditLevel(str, Enum):
 """감사 로그 레벨"""
 INFO = "info"
 WARNING = "warning"
 ERROR = "error"
 CRITICAL = "critical"
 DEBUG = "debug"


class AuditEventType(str, Enum):
 """감사 이벤트 타입"""
 # 인증 관련
 USER_LOGIN = "user.login"
 USER_LOGOUT = "user.logout"
 USER_REGISTER = "user.register"
 PASSWORD_CHANGED = "user.password_changed"
 PASSWORD_RESET = "user.password_reset"
 MFA_ENABLED = "user.mfa_enabled"
 MFA_DISABLED = "user.mfa_disabled"

 # 권한 관련
 PERMISSION_GRANTED = "permission.granted"
 PERMISSION_REVOKED = "permission.revoked"
 ROLE_ASSIGNED = "role.assigned"
 ROLE_REMOVED = "role.removed"

 # 데이터 관련
 DATA_CREATED = "data.created"
 DATA_READ = "data.read"
 DATA_UPDATED = "data.updated"
 DATA_DELETED = "data.deleted"
 DATA_EXPORTED = "data.exported"
 DATA_IMPORTED = "data.imported"

 # 시스템 관련
 SYSTEM_START = "system.start"
 SYSTEM_STOP = "system.stop"
 CONFIG_CHANGED = "system.config_changed"
 SERVICE_ERROR = "system.service_error"

 # 보안 관련
 SECURITY_ALERT = "security.alert"
 ACCESS_DENIED = "security.access_denied"
 SUSPICIOUS_ACTIVITY = "security.suspicious_activity"
 RATE_LIMIT_EXCEEDED = "security.rate_limit_exceeded"


class AuditEvent(BaseModel):
 """감사 이벤트 모델"""
 event_id: str = Field(default_factory = lambda: str(uuid.uuid4()))
 timestamp: datetime = Field(default_factory = datetime.utcnow)
 event_type: str
 level: AuditLevel = Field(default = AuditLevel.INFO)

 # 사용자 정보
 user_id: Optional[str] = None
 username: Optional[str] = None
 service_account: Optional[str] = None

 # 세션 정보
 session_id: Optional[str] = None
 ip_address: Optional[str] = None
 user_agent: Optional[str] = None

 # 리소스 정보
 resource_type: Optional[str] = None
 resource_id: Optional[str] = None
 resource_name: Optional[str] = None

 # 액션 정보
 action: str
 result: str = Field(default = "success", pattern = "^(success|failure|partial)$")
 error_code: Optional[str] = None
 error_message: Optional[str] = None

 # 서비스 정보
 service: str
 component: Optional[str] = None
 version: Optional[str] = None

 # 추적 정보
 correlation_id: Optional[str] = None
 parent_event_id: Optional[str] = None
 trace_id: Optional[str] = None
 span_id: Optional[str] = None

 # 성능 정보
 duration_ms: Optional[int] = None

 # 상세 정보
 details: Dict[str, Any] = Field(default_factory = dict)
 tags: List[str] = Field(default_factory = list)

 # 규정 준수
 compliance_tags: List[str] = Field(default_factory = list)
 data_classification: str = Field(default = "internal")
 retention_days: Optional[int] = None

 # 보안 정보
 risk_score: Optional[float] = Field(None, ge = 0.0, le = 1.0)
 threat_indicators: List[str] = Field(default_factory = list)

 class Config:
 use_enum_values = True


class AuditLog(BaseEntity):
 """감사 로그 데이터베이스 모델"""
 event: AuditEvent

 # 추가 메타데이터
 indexed_at: datetime = Field(default_factory = datetime.utcnow)
 processed: bool = Field(default = False)
 archived: bool = Field(default = False)

 # 검색 최적화 필드
 search_text: Optional[str] = None

 def generate_search_text(self):
 """검색 텍스트 생성"""
 parts = [
 self.event.event_type,
 self.event.user_id,
 self.event.username,
 self.event.resource_type,
 self.event.resource_id,
 self.event.action,
 self.event.service
 ]
 self.search_text = " ".join(filter(None, parts))


class AuditLogFilter(BaseModel):
 """감사 로그 필터"""
 start_date: Optional[datetime] = None
 end_date: Optional[datetime] = None
 event_types: Optional[List[str]] = None
 levels: Optional[List[AuditLevel]] = None
 user_ids: Optional[List[str]] = None
 services: Optional[List[str]] = None
 resource_types: Optional[List[str]] = None
 resource_ids: Optional[List[str]] = None
 actions: Optional[List[str]] = None
 results: Optional[List[str]] = None
 ip_addresses: Optional[List[str]] = None
 tags: Optional[List[str]] = None
 compliance_tags: Optional[List[str]] = None
 search_query: Optional[str] = None

 # 페이지네이션
 page: int = Field(default = 1, ge = 1)
 page_size: int = Field(default = 50, ge = 1, le = 1000)
 sort_by: str = Field(default = "timestamp")
 sort_order: str = Field(default = "desc", pattern = "^(asc|desc)$")


class AuditStatistics(BaseModel):
 """감사 통계 모델"""
 period_start: datetime
 period_end: datetime
 total_events: int

 # 이벤트 타입별 통계
 events_by_type: Dict[str, int]
 events_by_level: Dict[str, int]
 events_by_service: Dict[str, int]
 events_by_result: Dict[str, int]

 # 사용자 통계
 unique_users: int
 top_users: List[Dict[str, Any]]

 # 리소스 통계
 resources_accessed: Dict[str, int]

 # 보안 통계
 failed_attempts: int
 security_alerts: int
 average_risk_score: float

 # 시계열 데이터
 timeline: List[Dict[str, Any]]


class ComplianceReport(BaseModel):
 """규정 준수 보고서 모델"""
 report_id: str
 generated_at: datetime
 period_start: datetime
 period_end: datetime

 # 규정 준수 요약
 compliance_status: str = Field(pattern = "^(compliant|non_compliant|partial)$")
 compliance_score: float = Field(ge = 0.0, le = 100.0)

 # 규정별 상태
 regulations: Dict[str, Dict[str, Any]]

 # 위반 사항
 violations: List[Dict[str, Any]]

 # 권장 사항
 recommendations: List[str]

 # 상세 데이터
 audit_coverage: Dict[str, Any]
 data_retention_compliance: Dict[str, Any]
 access_control_compliance: Dict[str, Any]


class AuditAlert(BaseModel):
 """감사 알림 모델"""
 alert_id: str
 created_at: datetime
 alert_type: str
 severity: str = Field(pattern = "^(low|medium|high|critical)$")

 # 알림 내용
 title: str
 description: str
 affected_resources: List[Dict[str, Any]]

 # 관련 이벤트
 related_events: List[str]
 event_count: int

 # 상태
 status: str = Field(default = "open", pattern = "^(open|acknowledged|resolved|false_positive)$")
 acknowledged_by: Optional[str] = None
 acknowledged_at: Optional[datetime] = None
 resolved_by: Optional[str] = None
 resolved_at: Optional[datetime] = None

 # 액션
 recommended_actions: List[str]
 automated_response: Optional[Dict[str, Any]] = None
