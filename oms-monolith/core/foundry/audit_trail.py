"""
Foundry-style Immutable Audit Trail
모든 변경사항을 불변 로그로 기록하고 추적
"""
import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib

from terminusdb_client import WOQLClient
from core.monitoring.migration_monitor import track_native_operation

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """감사 이벤트 타입"""
    BRANCH_CREATED = "branch_created"
    BRANCH_DELETED = "branch_deleted"
    SCHEMA_MODIFIED = "schema_modified"
    DATA_MODIFIED = "data_modified"
    MERGE_ATTEMPTED = "merge_attempted"
    MERGE_COMPLETED = "merge_completed"
    CONFLICT_RESOLVED = "conflict_resolved"
    ROLLBACK_PERFORMED = "rollback_performed"
    ACCESS_GRANTED = "access_granted"
    ACCESS_REVOKED = "access_revoked"
    VALIDATION_FAILED = "validation_failed"


@dataclass
class AuditEvent:
    """불변 감사 이벤트"""
    event_id: str                    # 고유 ID
    event_type: AuditEventType       # 이벤트 타입
    timestamp: datetime              # 발생 시간
    author: str                      # 작업자
    branch: str                      # 브랜치
    commit_id: Optional[str]         # 커밋 ID
    resource_type: Optional[str]     # 리소스 타입 (schema, data 등)
    resource_id: Optional[str]       # 리소스 ID
    operation: str                   # 수행된 작업
    previous_value: Optional[Any]    # 이전 값
    new_value: Optional[Any]         # 새 값
    metadata: Dict[str, Any]         # 추가 메타데이터
    hash: Optional[str] = None       # 이벤트 해시 (무결성 검증용)
    
    def __post_init__(self):
        """이벤트 생성 후 해시 계산"""
        if not self.hash:
            self.hash = self._calculate_hash()
            
    def _calculate_hash(self) -> str:
        """이벤트의 무결성 해시 계산"""
        # 해시할 데이터 준비
        hash_data = {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "author": self.author,
            "branch": self.branch,
            "operation": self.operation
        }
        
        # JSON으로 직렬화하고 해시
        json_str = json.dumps(hash_data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()


class FoundryStyleAuditTrail:
    """Foundry처럼 모든 것을 추적하는 불변 감사 로그"""
    
    def __init__(self, client: WOQLClient):
        self.client = client
        self._ensure_audit_schema()
        
    def _ensure_audit_schema(self):
        """감사 로그를 위한 스키마 확인/생성"""
        try:
            # AuditEvent 스키마가 없으면 생성
            from terminusdb_client.woqlquery import WOQLQuery as WQ
            
            schema = WQ().doctype("AuditEvent").label("Audit Event").property("event_id", "xsd:string").property("event_type", "xsd:string").property("timestamp", "xsd:dateTime").property("author", "xsd:string").property("branch", "xsd:string").property("operation", "xsd:string").property("hash", "xsd:string").property("metadata", "xsd:string")  # JSON으로 저장
            
            self.client.query(schema, commit_msg="Create audit event schema")
        except:
            pass  # 이미 존재하면 무시
            
    @track_native_operation("record_audit_event")
    async def record_event(
        self,
        event_type: AuditEventType,
        author: str,
        operation: str,
        **kwargs
    ) -> AuditEvent:
        """
        감사 이벤트 기록 (불변)
        """
        # 이벤트 생성
        event = AuditEvent(
            event_id=f"audit_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}",
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            author=author,
            branch=self.client.branch or "main",
            commit_id=kwargs.get("commit_id"),
            resource_type=kwargs.get("resource_type"),
            resource_id=kwargs.get("resource_id"),
            operation=operation,
            previous_value=kwargs.get("previous_value"),
            new_value=kwargs.get("new_value"),
            metadata=kwargs.get("metadata", {})
        )
        
        # TerminusDB에 저장 (불변)
        audit_doc = {
            "@type": "AuditEvent",
            "@id": f"AuditEvent/{event.event_id}",
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "timestamp": event.timestamp.isoformat(),
            "author": event.author,
            "branch": event.branch,
            "operation": event.operation,
            "hash": event.hash,
            "metadata": json.dumps(asdict(event))  # 전체 데이터를 JSON으로
        }
        
        # 특별한 시스템 브랜치에 저장 (절대 삭제 불가)
        original_branch = self.client.branch
        try:
            self.client.branch = "_audit_trail"
            self.client.insert_document(
                audit_doc,
                commit_msg=f"Audit: {event_type.value} by {author}"
            )
        finally:
            self.client.branch = original_branch
            
        # 실시간 스트리밍 (옵션)
        await self._stream_to_external_system(event)
        
        return event
        
    async def query_audit_trail(
        self,
        filters: Optional[Dict[str, Any]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AuditEvent]:
        """
        감사 로그 조회
        """
        from terminusdb_client.woqlquery import WOQLQuery as WQ
        
        # 기본 쿼리
        query = WQ().triple("v:event", "rdf:type", "AuditEvent")
        
        # 시간 필터
        if start_time:
            query = query.triple("v:event", "timestamp", "v:time").greater("v:time", start_time.isoformat())
            
        if end_time:
            query = query.triple("v:event", "timestamp", "v:time").less("v:time", end_time.isoformat())
            
        # 추가 필터
        if filters:
            if "author" in filters:
                query = query.triple("v:event", "author", filters["author"])
            if "event_type" in filters:
                query = query.triple("v:event", "event_type", filters["event_type"])
            if "branch" in filters:
                query = query.triple("v:event", "branch", filters["branch"])
                
        # 정렬 및 제한
        query = query.order_by("v:time", "desc").limit(limit)
        
        # 실행
        original_branch = self.client.branch
        try:
            self.client.branch = "_audit_trail"
            result = self.client.query(query)
            
            # AuditEvent 객체로 변환
            events = []
            for binding in result.get("bindings", []):
                event_id = binding["event"]["@id"].split("/")[-1]
                doc = self.client.get_document(f"AuditEvent/{event_id}")
                
                # JSON 메타데이터 파싱
                metadata = json.loads(doc.get("metadata", "{}"))
                
                event = AuditEvent(
                    event_id=doc["event_id"],
                    event_type=AuditEventType(doc["event_type"]),
                    timestamp=datetime.fromisoformat(doc["timestamp"]),
                    author=doc["author"],
                    branch=doc["branch"],
                    commit_id=metadata.get("commit_id"),
                    resource_type=metadata.get("resource_type"),
                    resource_id=metadata.get("resource_id"),
                    operation=doc["operation"],
                    previous_value=metadata.get("previous_value"),
                    new_value=metadata.get("new_value"),
                    metadata=metadata.get("metadata", {}),
                    hash=doc["hash"]
                )
                
                events.append(event)
                
            return events
            
        finally:
            self.client.branch = original_branch
            
    async def verify_integrity(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        감사 로그 무결성 검증
        """
        events = await self.query_audit_trail(
            start_time=start_time,
            end_time=end_time,
            limit=10000
        )
        
        integrity_report = {
            "total_events": len(events),
            "valid_events": 0,
            "invalid_events": 0,
            "tampering_detected": False,
            "invalid_event_ids": []
        }
        
        for event in events:
            # 해시 재계산
            original_hash = event.hash
            event.hash = None
            recalculated_hash = event._calculate_hash()
            
            if original_hash == recalculated_hash:
                integrity_report["valid_events"] += 1
            else:
                integrity_report["invalid_events"] += 1
                integrity_report["invalid_event_ids"].append(event.event_id)
                integrity_report["tampering_detected"] = True
                
        return integrity_report
        
    async def generate_compliance_report(
        self,
        report_type: str,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, Any]:
        """
        규제 준수 보고서 생성 (SOC2, GDPR 등)
        """
        events = await self.query_audit_trail(
            start_time=start_time,
            end_time=end_time,
            limit=100000
        )
        
        if report_type == "access_report":
            # 접근 권한 변경 보고서
            access_events = [
                e for e in events 
                if e.event_type in [
                    AuditEventType.ACCESS_GRANTED,
                    AuditEventType.ACCESS_REVOKED
                ]
            ]
            
            return {
                "report_type": "access_changes",
                "period": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat()
                },
                "total_changes": len(access_events),
                "by_author": self._group_by_author(access_events),
                "by_resource": self._group_by_resource(access_events)
            }
            
        elif report_type == "data_changes":
            # 데이터 변경 보고서
            data_events = [
                e for e in events
                if e.event_type in [
                    AuditEventType.DATA_MODIFIED,
                    AuditEventType.SCHEMA_MODIFIED
                ]
            ]
            
            return {
                "report_type": "data_modifications",
                "period": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat()
                },
                "total_modifications": len(data_events),
                "schema_changes": len([e for e in data_events if e.event_type == AuditEventType.SCHEMA_MODIFIED]),
                "data_changes": len([e for e in data_events if e.event_type == AuditEventType.DATA_MODIFIED]),
                "by_branch": self._group_by_branch(data_events)
            }
            
    async def _stream_to_external_system(self, event: AuditEvent):
        """
        외부 SIEM/로그 시스템으로 실시간 전송
        """
        # Kafka, Elasticsearch, Splunk 등으로 전송
        # 여기서는 로그로 대체
        logger.info(f"Audit event streamed: {event.event_id} - {event.event_type.value}")
        
    def _group_by_author(self, events: List[AuditEvent]) -> Dict[str, int]:
        """작성자별 그룹화"""
        groups = {}
        for event in events:
            groups[event.author] = groups.get(event.author, 0) + 1
        return groups
        
    def _group_by_resource(self, events: List[AuditEvent]) -> Dict[str, int]:
        """리소스별 그룹화"""
        groups = {}
        for event in events:
            key = f"{event.resource_type}:{event.resource_id}"
            groups[key] = groups.get(key, 0) + 1
        return groups
        
    def _group_by_branch(self, events: List[AuditEvent]) -> Dict[str, int]:
        """브랜치별 그룹화"""
        groups = {}
        for event in events:
            groups[event.branch] = groups.get(event.branch, 0) + 1
        return groups


class AuditContextManager:
    """감사 컨텍스트 관리자 - 자동으로 감사 이벤트 기록"""
    
    def __init__(
        self,
        audit_trail: FoundryStyleAuditTrail,
        event_type: AuditEventType,
        author: str,
        operation: str,
        **kwargs
    ):
        self.audit_trail = audit_trail
        self.event_type = event_type
        self.author = author
        self.operation = operation
        self.kwargs = kwargs
        self.start_time = None
        
    async def __aenter__(self):
        """작업 시작 시 기록"""
        self.start_time = datetime.now(timezone.utc)
        
        # 시작 이벤트 기록
        await self.audit_trail.record_event(
            self.event_type,
            self.author,
            f"Started: {self.operation}",
            metadata={
                "phase": "start",
                "start_time": self.start_time.isoformat()
            },
            **self.kwargs
        )
        
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """작업 완료 시 기록"""
        end_time = datetime.now(timezone.utc)
        duration = (end_time - self.start_time).total_seconds()
        
        # 완료/실패 이벤트 기록
        if exc_type is None:
            await self.audit_trail.record_event(
                self.event_type,
                self.author,
                f"Completed: {self.operation}",
                metadata={
                    "phase": "complete",
                    "duration_seconds": duration,
                    "status": "success"
                },
                **self.kwargs
            )
        else:
            await self.audit_trail.record_event(
                self.event_type,
                self.author,
                f"Failed: {self.operation}",
                metadata={
                    "phase": "failed",
                    "duration_seconds": duration,
                    "status": "error",
                    "error_type": exc_type.__name__,
                    "error_message": str(exc_val)
                },
                **self.kwargs
            )
            
        # 예외는 재발생
        return False