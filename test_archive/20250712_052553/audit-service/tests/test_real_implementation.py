"""
실제 구현체를 사용한 실질적 테스트
기존 EventProcessor, AuditService, HistoryRepository를 사용
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import json
import uuid


class TestRealEventProcessor:
    """실제 EventProcessor 구현체 테스트"""
    
    @pytest.mark.asyncio
    async def test_real_create_audit_log(self, sample_audit_event):
        """실제 EventProcessor로 감사 로그 생성 테스트"""
        from core.subscribers.event_processor import EventProcessor
        
        # Mock session to avoid database dependency
        mock_session = AsyncMock()
        processor = EventProcessor(session=mock_session)
        
        # 실제 메서드 호출
        audit_log = await processor.create_audit_log(sample_audit_event)
        
        # 실제 구현체의 결과 검증
        assert audit_log is not None
        assert hasattr(audit_log, 'log_id')
        assert hasattr(audit_log, 'user_id')
        assert hasattr(audit_log, 'action')
        assert hasattr(audit_log, 'resource_type')
        assert hasattr(audit_log, 'resource_id')
        
        # CloudEvent의 데이터가 제대로 매핑되었는지 확인
        data = sample_audit_event.get("data", {})
        assert audit_log.user_id == data.get("author")
        assert audit_log.resource_type == data.get("resource_type")
        assert audit_log.resource_id == data.get("resource_id")
    
    @pytest.mark.asyncio
    async def test_real_create_history_entry(self, sample_audit_event):
        """실제 EventProcessor로 히스토리 엔트리 생성 테스트"""
        from core.subscribers.event_processor import EventProcessor
        
        processor = EventProcessor()
        
        # 실제 메서드 호출
        history_entry = await processor.create_history_entry(sample_audit_event)
        
        # 실제 구현체의 결과 검증
        assert history_entry is not None
        assert hasattr(history_entry, 'commit_hash')
        assert hasattr(history_entry, 'branch')
        assert hasattr(history_entry, 'author')
        assert hasattr(history_entry, 'changes')
        assert hasattr(history_entry, 'total_changes')
        assert hasattr(history_entry, 'breaking_changes')
        
        # CloudEvent의 데이터가 제대로 매핑되었는지 확인
        data = sample_audit_event.get("data", {})
        assert history_entry.branch == data.get("branch", "main")
        assert history_entry.author == data.get("author")
        assert history_entry.total_changes == len(data.get("changes", []))
    
    @pytest.mark.asyncio
    async def test_real_severity_determination(self):
        """실제 심각도 결정 로직 테스트"""
        from core.subscribers.event_processor import EventProcessor
        from models.audit import SeverityLevel
        
        processor = EventProcessor()
        
        # Breaking change 있는 경우
        data_with_breaking = {
            "changes": [
                {"breaking_change": True},
                {"breaking_change": False}
            ]
        }
        severity = processor._determine_severity(data_with_breaking)
        assert severity == SeverityLevel.WARNING
        
        # 삭제 작업
        data_delete = {"operation": "delete"}
        severity = processor._determine_severity(data_delete)
        assert severity == SeverityLevel.WARNING
        
        # 실패한 작업
        data_failure = {"result": "failure"}
        severity = processor._determine_severity(data_failure)
        assert severity == SeverityLevel.ERROR
        
        # 일반 작업
        data_normal = {"operation": "create", "result": "success"}
        severity = processor._determine_severity(data_normal)
        assert severity == SeverityLevel.INFO
    
    @pytest.mark.asyncio
    async def test_real_siem_event_mapping(self):
        """실제 SIEM 이벤트 매핑 테스트"""
        from core.subscribers.event_processor import EventProcessor
        
        processor = EventProcessor()
        
        test_event = {
            "id": "test-siem-event",
            "type": "com.oms.schema.changed",
            "time": "2024-01-01T12:00:00Z",
            "data": {
                "operation": "delete",
                "resource_type": "objectType",
                "resource_id": "TestObject",
                "author": "admin_user",
                "result": "success"
            }
        }
        
        # SIEM 심각도 매핑 테스트
        siem_severity = processor._map_to_siem_severity(test_event["data"])
        assert isinstance(siem_severity, int)
        assert 0 <= siem_severity <= 10
        
        # 삭제 작업은 중간 심각도여야 함
        assert siem_severity >= 3
    
    @pytest.mark.asyncio
    async def test_real_action_description_generation(self):
        """실제 액션 설명 생성 테스트"""
        from core.subscribers.event_processor import EventProcessor
        
        processor = EventProcessor()
        
        # 스키마 변경 이벤트
        event_type = "com.oms.schema.changed"
        data = {
            "operation": "update",
            "resource_type": "objectType"
        }
        
        action = processor._get_action_description(event_type, data)
        assert action == "update_objectType"
        
        # 스키마 복원 이벤트
        event_type = "com.oms.schema.reverted"
        action = processor._get_action_description(event_type, data)
        assert action == "revert_schema"
    
    @pytest.mark.asyncio
    async def test_real_compliance_tags_determination(self):
        """실제 규제 준수 태그 결정 테스트"""
        from core.subscribers.event_processor import EventProcessor
        from models.audit import AuditLogEntry, AuditEventType, SeverityLevel
        
        processor = EventProcessor()
        
        # 스키마 변경 - SOX 대상
        audit_entry = AuditLogEntry(
            log_id="test-log",
            timestamp=datetime.now(timezone.utc),
            event_type=AuditEventType.SCHEMA_CHANGE,
            severity=SeverityLevel.INFO,
            user_id="test_user",
            action="update_schema",
            resource_type="schema",
            resource_id="test_schema"
        )
        
        compliance_tags = processor._determine_compliance_tags(audit_entry)
        assert "SOX" in compliance_tags
        
        # 사용자 관련 - GDPR 대상
        audit_entry.resource_type = "user_profile"
        compliance_tags = processor._determine_compliance_tags(audit_entry)
        assert "GDPR" in compliance_tags
        
        # 결제 관련 - PCI-DSS 대상
        audit_entry.resource_id = "payment_method_123"
        compliance_tags = processor._determine_compliance_tags(audit_entry)
        assert "PCI-DSS" in compliance_tags


class TestRealAuditService:
    """실제 AuditService 구현체 테스트"""
    
    @pytest.mark.asyncio
    async def test_real_search_logs(self):
        """실제 AuditService로 로그 검색 테스트"""
        from core.services.audit_service import AuditService
        from models.audit import AuditSearchQuery
        
        service = AuditService()
        
        # 검색 쿼리 생성
        query = AuditSearchQuery(
            user_id="test_user",
            limit=10,
            include_aggregations=True
        )
        
        # Mock user context
        user_context = {
            "user_id": "test_user",
            "roles": ["audit_user"],
            "permissions": ["audit:read"]
        }
        
        # 실제 검색 수행
        response = await service.search_logs(query, user_context)
        
        # 응답 구조 검증
        assert hasattr(response, 'entries')
        assert hasattr(response, 'total_count')
        assert hasattr(response, 'has_more')
        assert hasattr(response, 'query_time_ms')
        assert hasattr(response, 'applied_filters')
        assert hasattr(response, 'aggregations')
        assert hasattr(response, 'summary')
        
        # 데이터 일관성 검증
        assert len(response.entries) <= query.limit
        assert response.total_count >= len(response.entries)
        assert isinstance(response.query_time_ms, int)
        assert response.query_time_ms >= 0
    
    @pytest.mark.asyncio
    async def test_real_access_control(self):
        """실제 접근 제어 로직 테스트"""
        from core.services.audit_service import AuditService
        from models.audit import AuditSearchQuery
        
        service = AuditService()
        
        original_query = AuditSearchQuery(limit=100)
        
        # Admin 사용자 - 모든 접근 가능
        admin_context = {
            "user_id": "admin",
            "roles": ["admin"],
            "permissions": ["audit:admin"]
        }
        
        filtered_query = await service._apply_access_filters(original_query, admin_context)
        assert filtered_query.limit == 100  # 제한 없음
        assert filtered_query.user_id is None  # 모든 사용자 로그 볼 수 있음
        
        # 일반 사용자 - 제한된 접근
        user_context = {
            "user_id": "regular_user",
            "roles": ["user"],
            "permissions": ["audit:read"]
        }
        
        filtered_query = await service._apply_access_filters(original_query, user_context)
        assert filtered_query.user_id == "regular_user"  # 자신의 로그만
        
        # 권한 없는 사용자 - 매우 제한된 접근
        limited_context = {
            "user_id": "limited_user",
            "roles": ["user"],
            "permissions": []
        }
        
        filtered_query = await service._apply_access_filters(original_query, limited_context)
        assert filtered_query.user_id == "limited_user"
        assert filtered_query.limit <= 10  # 제한된 결과
    
    @pytest.mark.asyncio
    async def test_real_dashboard_statistics(self):
        """실제 대시보드 통계 생성 테스트"""
        from core.services.audit_service import AuditService
        
        service = AuditService()
        
        user_context = {"user_id": "test_user", "roles": ["audit_user"]}
        
        # 기본 통계
        stats = await service.get_dashboard_statistics(
            user_context=user_context,
            time_range="24h",
            include_trends=True,
            include_top_users=True,
            include_top_actions=True
        )
        
        # 통계 구조 검증
        assert "summary" in stats
        assert "event_distribution" in stats
        assert "severity_distribution" in stats
        assert "trends" in stats
        assert "top_users" in stats
        assert "top_actions" in stats
        
        # 요약 통계 검증
        summary = stats["summary"]
        assert "total_events" in summary
        assert "unique_users" in summary
        assert "success_rate" in summary
        assert "critical_events" in summary
        assert summary["total_events"] > 0
        assert 0 <= summary["success_rate"] <= 1
    
    @pytest.mark.asyncio
    async def test_real_export_functionality(self):
        """실제 내보내기 기능 테스트"""
        from core.services.audit_service import AuditService
        from models.audit import AuditExportRequest
        
        service = AuditService()
        
        # 내보내기 요청
        from models.audit import AuditSearchQuery
        search_query = AuditSearchQuery(limit=100)
        
        export_request = AuditExportRequest(
            query=search_query,
            format="csv",
            include_metadata=True,
            audit_purpose="analysis",
            requestor_id="test_user"
        )
        
        user_context = {"user_id": "test_user", "roles": ["audit_user"]}
        
        # 내보내기 시작
        export_response = await service.start_export(export_request, user_context)
        
        # 응답 검증
        assert hasattr(export_response, 'export_id')
        assert hasattr(export_response, 'status')
        assert hasattr(export_response, 'created_at')
        assert export_response.status == "pending"
        assert export_response.export_id is not None
        
        # 상태 조회
        status_response = await service.get_export_status(export_response.export_id, user_context)
        assert status_response is not None
        assert hasattr(status_response, 'progress_percentage')
        
        # 다운로드 (시뮬레이션)
        file_stream, filename, media_type = await service.download_export(
            export_response.export_id, user_context
        )
        
        assert file_stream is not None
        assert filename.endswith('.csv')
        assert media_type == "text/csv"
        
        # 파일 내용 검증
        content = file_stream.read().decode('utf-8')
        assert len(content) > 0
        assert "log_id" in content  # CSV 헤더


class TestRealHistoryRepository:
    """실제 HistoryRepository 구현체 테스트"""
    
    @pytest.mark.asyncio
    async def test_real_search_history(self):
        """실제 HistoryRepository 검색 테스트"""
        from core.repositories.history_repository import HistoryRepository
        from models.history import HistoryQuery
        
        repo = HistoryRepository()  # session=None (mock mode)
        
        # 실제 쿼리 객체 생성
        query = HistoryQuery(
            branch="main",
            author="developer",
            limit=20,
            include_changes=True,
            include_metadata=True
        )
        
        # 실제 검색 수행
        entries, total_count, has_more, next_cursor = await repo.search_history(query)
        
        # 결과 검증
        assert isinstance(entries, list)
        assert isinstance(total_count, int)
        assert isinstance(has_more, bool)
        assert len(entries) <= query.limit
        
        # 엔트리 구조 검증
        if entries:
            entry = entries[0]
            assert hasattr(entry, 'commit_hash')
            assert hasattr(entry, 'branch')
            assert hasattr(entry, 'author')
            assert hasattr(entry, 'timestamp')
            assert hasattr(entry, 'changes')
            assert hasattr(entry, 'total_changes')
            assert hasattr(entry, 'breaking_changes')
            
            # 필터 적용 확인
            assert entry.branch == query.branch
    
    @pytest.mark.asyncio
    async def test_real_get_commit_details(self):
        """실제 커밋 상세 조회 테스트"""
        from core.repositories.history_repository import HistoryRepository
        
        repo = HistoryRepository()
        
        # 실제 메서드 호출
        commit_detail = await repo.get_commit_by_hash("test_commit_123", "main")
        
        # 결과 검증
        assert commit_detail is not None
        assert hasattr(commit_detail, 'commit_hash')
        assert hasattr(commit_detail, 'branch')
        assert hasattr(commit_detail, 'timestamp')
        assert hasattr(commit_detail, 'author')
        assert hasattr(commit_detail, 'total_changes')
        assert hasattr(commit_detail, 'additions')
        assert hasattr(commit_detail, 'modifications')
        assert hasattr(commit_detail, 'deletions')
        assert hasattr(commit_detail, 'breaking_changes')
        
        # 데이터 일관성 검증
        assert commit_detail.commit_hash == "test_commit_123"
        assert commit_detail.branch == "main"
        assert commit_detail.total_changes >= 0
        assert commit_detail.additions >= 0
        assert commit_detail.modifications >= 0
        assert commit_detail.deletions >= 0
    
    @pytest.mark.asyncio
    async def test_real_statistics_calculation(self):
        """실제 통계 계산 테스트"""
        from core.repositories.history_repository import HistoryRepository
        
        repo = HistoryRepository()
        
        # 실제 통계 생성
        stats = await repo.get_statistics(
            branch="main",
            group_by="day"
        )
        
        # 통계 구조 검증
        assert isinstance(stats, dict)
        assert "summary" in stats
        assert "operations" in stats
        assert "resource_types" in stats
        assert "contributors" in stats
        assert "timeline" in stats
        
        # 요약 통계 검증
        summary = stats["summary"]
        assert "total_commits" in summary
        assert "total_changes" in summary
        assert "breaking_changes" in summary
        assert "active_branches" in summary
        assert "active_contributors" in summary
        
        # 작업별 통계 검증
        operations = stats["operations"]
        expected_operations = ["create", "update", "delete", "rename", "merge"]
        for op in expected_operations:
            assert op in operations
            assert isinstance(operations[op], int)
            assert operations[op] >= 0
        
        # 리소스 타입별 통계 검증
        resource_types = stats["resource_types"]
        assert isinstance(resource_types, dict)
        
        # 기여자 통계 검증
        contributors = stats["contributors"]
        assert isinstance(contributors, list)
        if contributors:
            contributor = contributors[0]
            assert "author" in contributor
            assert "commits" in contributor
            assert "changes" in contributor
    
    @pytest.mark.asyncio
    async def test_real_timeline_generation(self):
        """실제 타임라인 생성 테스트"""
        from core.repositories.history_repository import HistoryRepository
        
        repo = HistoryRepository()
        
        # 다양한 그룹화 옵션 테스트
        for group_by in ["hour", "day"]:
            timeline = repo._generate_timeline_data(group_by)
            
            assert isinstance(timeline, list)
            assert len(timeline) <= 10  # 최근 10개만 반환
            
            if timeline:
                entry = timeline[0]
                assert "period" in entry
                assert "commits" in entry
                assert "changes" in entry
                assert "contributors" in entry
                
                # 데이터 타입 검증
                assert isinstance(entry["commits"], int)
                assert isinstance(entry["changes"], int)
                assert isinstance(entry["contributors"], int)
                assert entry["commits"] >= 0
                assert entry["changes"] >= 0
                assert entry["contributors"] >= 0


class TestIntegrationScenarios:
    """실제 구현체들 간의 통합 시나리오 테스트"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_event_processing(self, sample_audit_event):
        """End-to-End 이벤트 처리 테스트"""
        from core.subscribers.event_processor import EventProcessor
        
        processor = EventProcessor()
        
        # 1. 감사 로그 생성
        audit_log = await processor.create_audit_log(sample_audit_event)
        assert audit_log is not None
        
        # 2. 히스토리 엔트리 생성
        history_entry = await processor.create_history_entry(sample_audit_event)
        assert history_entry is not None
        
        # 3. 데이터 일관성 검증
        data = sample_audit_event.get("data", {})
        assert audit_log.user_id == history_entry.author
        assert audit_log.resource_type == data.get("resource_type")
        assert history_entry.resource_id == data.get("resource_id")
        
        # 4. SIEM 전송 시뮬레이션
        with patch.object(processor, '_send_to_configured_siem') as mock_siem:
            await processor.send_to_siem(sample_audit_event)
            # SIEM 호출 여부는 환경 설정에 따라 다름
    
    @pytest.mark.asyncio
    async def test_search_and_export_workflow(self):
        """검색 및 내보내기 워크플로우 테스트"""
        from core.services.audit_service import AuditService
        from models.audit import AuditSearchQuery, AuditExportRequest
        
        service = AuditService()
        user_context = {
            "user_id": "test_user",
            "roles": ["audit_user"],
            "permissions": ["audit:read", "audit:export"]
        }
        
        # 1. 검색 수행
        search_query = AuditSearchQuery(
            user_id="test_user",
            limit=50,
            include_aggregations=True
        )
        
        search_response = await service.search_logs(search_query, user_context)
        assert search_response.total_count >= 0
        
        # 2. 검색 결과를 기반으로 내보내기
        export_request = AuditExportRequest(
            query=search_query,
            format="csv",
            include_metadata=True,
            audit_purpose="compliance",
            requestor_id="test_user"
        )
        
        export_response = await service.start_export(export_request, user_context)
        assert export_response.export_id is not None
        
        # 3. 내보내기 완료 후 다운로드
        file_stream, filename, media_type = await service.download_export(
            export_response.export_id, user_context
        )
        
        assert filename.endswith('.csv')
        assert media_type == "text/csv"
    
    @pytest.mark.asyncio
    async def test_compliance_workflow(self):
        """규제 준수 워크플로우 테스트"""
        from core.subscribers.event_processor import EventProcessor
        from core.services.audit_service import AuditService
        
        # 1. 규제 준수 이벤트 생성
        compliance_event = {
            "id": str(uuid.uuid4()),
            "type": "com.oms.schema.changed",
            "time": datetime.now(timezone.utc).isoformat(),
            "data": {
                "operation": "update",
                "resource_type": "user_profile",
                "resource_id": "user_12345",
                "author": "admin_user",
                "changes": [
                    {
                        "field": "email",
                        "operation": "update",
                        "old_value": "old@example.com",
                        "new_value": "new@example.com",
                        "breaking_change": False
                    }
                ]
            }
        }
        
        # 2. 이벤트 처리
        processor = EventProcessor()
        audit_log = await processor.create_audit_log(compliance_event)
        
        # 3. GDPR 태그 확인
        assert "GDPR" in audit_log.compliance_tags
        
        # 4. 데이터 분류 확인
        assert audit_log.data_classification == "confidential"
        
        # 5. 보존 상태 확인
        service = AuditService()
        retention_status = await service.get_retention_status(
            user_context={"user_id": "admin_user"},
            compliance_standard="GDPR"
        )
        
        assert "retention_policies" in retention_status
        gdpr_policy = next(
            (p for p in retention_status["retention_policies"] if p["standard"] == "GDPR"),
            None
        )
        assert gdpr_policy is not None
        assert gdpr_policy["retention_days"] > 0