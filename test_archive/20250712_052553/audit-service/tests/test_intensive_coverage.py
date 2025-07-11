"""
집중적인 커버리지 향상 테스트
누락된 라인들을 체계적으로 커버하여 90% 달성
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, timezone, timedelta
import json
import uuid
import io
import os


class TestHistoryRepositoryIntensive:
    """HistoryRepository 집중 테스트 - 33% -> 90%"""
    
    @pytest.mark.asyncio
    async def test_search_history_comprehensive(self):
        """히스토리 검색 포괄적 테스트"""
        from core.repositories.history_repository import HistoryRepository
        from models.history import HistoryQuery
        
        repo = HistoryRepository()
        
        # 기본 검색
        query = HistoryQuery(limit=10)
        entries, total, has_more, cursor = await repo.search_history(query)
        
        assert isinstance(entries, list)
        assert isinstance(total, int)
        assert isinstance(has_more, bool)
        
        # 필터링된 검색
        filtered_query = HistoryQuery(
            branch="main",
            author="test_user",
            resource_type="objectType",
            resource_id="TestResource",
            operation="update",
            breaking_changes_only=True,
            limit=5
        )
        entries, total, has_more, cursor = await repo.search_history(filtered_query)
        assert len(entries) <= 5
    
    @pytest.mark.asyncio
    async def test_get_commit_by_hash_comprehensive(self):
        """커밋 해시로 조회 포괄적 테스트"""
        from core.repositories.history_repository import HistoryRepository
        
        repo = HistoryRepository()
        
        # 존재하는 커밋
        commit_detail = await repo.get_commit_by_hash("test_commit_123", "main")
        assert commit_detail is not None
        assert commit_detail.commit_hash == "test_commit_123"
        assert commit_detail.branch == "main"
        
        # 다른 브랜치
        commit_detail = await repo.get_commit_by_hash("test_commit_456", "develop")
        assert commit_detail is not None
        assert commit_detail.branch == "develop"
    
    @pytest.mark.asyncio
    async def test_get_commit_changes_comprehensive(self):
        """커밋 변경사항 조회 포괄적 테스트"""
        from core.repositories.history_repository import HistoryRepository
        
        repo = HistoryRepository()
        
        changes = await repo.get_commit_changes("test_commit_with_changes", "main")
        assert isinstance(changes, list)
        assert len(changes) > 0
        
        for change in changes:
            assert hasattr(change, 'field')
            assert hasattr(change, 'operation')
            assert hasattr(change, 'breaking_change')
            assert hasattr(change, 'path')
    
    @pytest.mark.asyncio
    async def test_get_affected_resources_comprehensive(self):
        """영향받은 리소스 조회 포괄적 테스트"""
        from core.repositories.history_repository import HistoryRepository
        
        repo = HistoryRepository()
        
        resources = await repo.get_affected_resources("test_commit_with_resources", "main")
        assert isinstance(resources, list)
        assert len(resources) > 0
        
        for resource in resources:
            assert hasattr(resource, 'resource_type')
            assert hasattr(resource, 'resource_id')
            assert hasattr(resource, 'impact_type')
            assert hasattr(resource, 'impact_severity')
    
    @pytest.mark.asyncio
    async def test_get_schema_snapshot_comprehensive(self):
        """스키마 스냅샷 조회 포괄적 테스트"""
        from core.repositories.history_repository import HistoryRepository
        
        repo = HistoryRepository()
        
        snapshot = await repo.get_schema_snapshot("test_commit_snapshot", "main")
        assert isinstance(snapshot, dict)
        assert "version" in snapshot
        assert "commit_hash" in snapshot
        assert "branch" in snapshot
        assert "timestamp" in snapshot
        assert "object_types" in snapshot
        assert snapshot["commit_hash"] == "test_commit_snapshot"
        assert snapshot["branch"] == "main"
    
    @pytest.mark.asyncio
    async def test_get_previous_commit_comprehensive(self):
        """이전 커밋 조회 포괄적 테스트"""
        from core.repositories.history_repository import HistoryRepository
        
        repo = HistoryRepository()
        
        previous = await repo.get_previous_commit("current_commit_abc", "main")
        assert previous is not None
        assert isinstance(previous, str)
        assert previous.startswith("prev_")
        assert "current_commit_abc"[:8] in previous
    
    @pytest.mark.asyncio
    async def test_get_statistics_comprehensive(self):
        """통계 조회 포괄적 테스트"""
        from core.repositories.history_repository import HistoryRepository
        
        repo = HistoryRepository()
        
        # 기본 통계
        stats = await repo.get_statistics()
        assert isinstance(stats, dict)
        assert "total_commits" in stats
        assert "commits_by_author" in stats
        assert "recent_activity" in stats
        
        # 브랜치별 통계
        stats_branch = await repo.get_statistics(branch="main")
        assert isinstance(stats_branch, dict)
        
        # 기간별 통계
        from_date = "2024-01-01T00:00:00Z"
        to_date = "2024-01-31T23:59:59Z"
        stats_period = await repo.get_statistics(
            from_date=from_date, 
            to_date=to_date
        )
        assert isinstance(stats_period, dict)
    
    def test_generate_timeline_data_comprehensive(self):
        """타임라인 데이터 생성 포괄적 테스트"""
        from core.repositories.history_repository import HistoryRepository
        
        repo = HistoryRepository()
        
        # 일별 그룹화
        timeline_day = repo._generate_timeline_data("day")
        assert isinstance(timeline_day, list)
        assert len(timeline_day) <= 30
        
        # 시간별 그룹화
        timeline_hour = repo._generate_timeline_data("hour")
        assert isinstance(timeline_hour, list)
        assert len(timeline_hour) <= 24
        
        # 월별 그룹화
        timeline_month = repo._generate_timeline_data("month")
        assert isinstance(timeline_month, list)
        assert len(timeline_month) <= 12
        
        # 알 수 없는 그룹화
        timeline_unknown = repo._generate_timeline_data("unknown")
        assert isinstance(timeline_unknown, list)
    
    @pytest.mark.asyncio
    async def test_search_history_mock_comprehensive(self):
        """Mock 히스토리 검색 포괄적 테스트"""
        from core.repositories.history_repository import HistoryRepository
        from models.history import HistoryQuery
        
        repo = HistoryRepository()
        
        # 다양한 쿼리 패턴
        queries = [
            HistoryQuery(limit=5),
            HistoryQuery(branch="main", limit=10),
            HistoryQuery(author="test_user", limit=15),
            HistoryQuery(resource_type="objectType", limit=20),
            HistoryQuery(operation="update", limit=25),
            HistoryQuery(breaking_changes_only=True, limit=30),
            HistoryQuery(
                branch="main",
                author="test_user",
                resource_type="objectType",
                operation="update",
                breaking_changes_only=True,
                limit=50
            )
        ]
        
        for query in queries:
            entries, total, has_more, cursor = await repo._search_history_mock(query)
            assert isinstance(entries, list)
            assert isinstance(total, int)
            assert isinstance(has_more, bool)
            assert len(entries) <= query.limit


class TestHistoryServiceIntensive:
    """HistoryService 집중 테스트 - 14% -> 90%"""
    
    @pytest.mark.asyncio
    async def test_list_history_comprehensive(self):
        """히스토리 목록 조회 포괄적 테스트"""
        from core.services.history_service import HistoryService
        from models.history import HistoryQuery
        
        service = HistoryService()
        user_context = {"user_id": "test_user", "permissions": ["history:read"]}
        
        query = HistoryQuery(limit=10)
        response = await service.list_history(query, user_context)
        
        assert response is not None
        assert hasattr(response, 'entries')
        assert hasattr(response, 'total_count')
        assert hasattr(response, 'has_more')
        assert hasattr(response, 'query_time_ms')
        assert hasattr(response, 'applied_filters')
        assert hasattr(response, 'summary')
    
    @pytest.mark.asyncio
    async def test_get_commit_detail_comprehensive(self):
        """커밋 상세 정보 조회 포괄적 테스트"""
        from core.services.history_service import HistoryService
        
        service = HistoryService()
        user_context = {"user_id": "test_user", "accessible_branches": ["main", "develop"]}
        
        # 기본 조회
        detail = await service.get_commit_detail("test_commit_123", "main", user_context)
        assert detail is not None
        assert detail.commit_hash == "test_commit_123"
        assert detail.branch == "main"
        
        # 변경사항 포함
        detail_with_changes = await service.get_commit_detail(
            "test_commit_456", "main", user_context, include_changes=True
        )
        assert detail_with_changes is not None
        assert hasattr(detail_with_changes, 'detailed_changes')
        
        # 영향받은 리소스 포함
        detail_with_affected = await service.get_commit_detail(
            "test_commit_789", "main", user_context, include_affected=True
        )
        assert detail_with_affected is not None
        assert hasattr(detail_with_affected, 'affected_resources')
        assert hasattr(detail_with_affected, 'impact_analysis')
        
        # 스냅샷 포함
        detail_with_snapshot = await service.get_commit_detail(
            "test_commit_abc", "main", user_context, include_snapshot=True
        )
        assert detail_with_snapshot is not None
        assert hasattr(detail_with_snapshot, 'snapshot')
        assert hasattr(detail_with_snapshot, 'snapshot_size_bytes')
    
    @pytest.mark.asyncio
    async def test_get_commit_diff_comprehensive(self):
        """커밋 차이점 조회 포괄적 테스트"""
        from core.services.history_service import HistoryService
        
        service = HistoryService()
        user_context = {"user_id": "test_user", "accessible_branches": ["main"]}
        
        # 기본 diff (이전 커밋과 비교)
        diff = await service.get_commit_diff("test_commit_123", user_context)
        assert isinstance(diff, dict)
        assert "commit_hash" in diff
        assert "compare_with" in diff
        assert "diff" in diff
        
        # 특정 커밋과 비교
        diff_specific = await service.get_commit_diff(
            "test_commit_456", user_context, compare_with="test_commit_123"
        )
        assert diff_specific["compare_with"] == "test_commit_123"
        
        # 다른 형식들
        for fmt in ["json", "text", "unified"]:
            diff_fmt = await service.get_commit_diff(
                "test_commit_789", user_context, format=fmt
            )
            assert diff_fmt["format"] == fmt
    
    @pytest.mark.asyncio
    async def test_get_statistics_comprehensive(self):
        """통계 조회 포괄적 테스트"""
        from core.services.history_service import HistoryService
        
        service = HistoryService()
        user_context = {"user_id": "test_user"}
        
        # 기본 통계
        stats = await service.get_statistics(user_context)
        assert isinstance(stats, dict)
        
        # 브랜치별 통계
        stats_branch = await service.get_statistics(user_context, branch="main")
        assert isinstance(stats_branch, dict)
        
        # 기간별 통계
        stats_period = await service.get_statistics(
            user_context, 
            from_date="2024-01-01T00:00:00Z",
            to_date="2024-01-31T23:59:59Z"
        )
        assert isinstance(stats_period, dict)
        
        # 그룹화별 통계
        for group_by in ["day", "hour", "month"]:
            stats_group = await service.get_statistics(
                user_context, group_by=group_by
            )
            assert isinstance(stats_group, dict)
    
    @pytest.mark.asyncio
    async def test_export_history_comprehensive(self):
        """히스토리 내보내기 포괄적 테스트"""
        from core.services.history_service import HistoryService
        
        service = HistoryService()
        user_context = {"user_id": "test_user", "permissions": ["history:export"]}
        
        # CSV 내보내기
        csv_data, filename, content_type = await service.export_history(
            user_context, format="csv"
        )
        assert isinstance(csv_data, io.BytesIO)
        assert filename.endswith(".csv")
        assert content_type == "text/csv"
        
        # JSON 내보내기
        json_data, filename, content_type = await service.export_history(
            user_context, format="json"
        )
        assert isinstance(json_data, io.BytesIO)
        assert filename.endswith(".json")
        assert content_type == "application/json"
        
        # Excel 내보내기
        excel_data, filename, content_type = await service.export_history(
            user_context, format="xlsx"
        )
        assert isinstance(excel_data, io.BytesIO)
        
        # 변경사항 포함 내보내기
        csv_with_changes, _, _ = await service.export_history(
            user_context, format="csv", include_changes=True
        )
        assert isinstance(csv_with_changes, io.BytesIO)
    
    @pytest.mark.asyncio
    async def test_apply_access_filters_comprehensive(self):
        """접근 필터 적용 포괄적 테스트"""
        from core.services.history_service import HistoryService
        from models.history import HistoryQuery
        
        service = HistoryService()
        
        # Admin 사용자
        admin_context = {"user_id": "admin", "roles": ["admin"]}
        admin_query = HistoryQuery(limit=100)
        filtered_admin = await service._apply_access_filters(admin_query, admin_context)
        assert filtered_admin.limit == 100  # 제한 없음
        
        # 일반 사용자
        user_context = {"user_id": "user", "permissions": ["history:read"]}
        user_query = HistoryQuery(limit=100)
        filtered_user = await service._apply_access_filters(user_query, user_context)
        assert filtered_user.from_date is not None  # 최근 30일로 제한
        
        # 제한된 사용자
        limited_context = {"user_id": "limited"}
        limited_query = HistoryQuery(limit=100)
        filtered_limited = await service._apply_access_filters(limited_query, limited_context)
        assert filtered_limited.limit == 5  # 최대 5개로 제한
    
    @pytest.mark.asyncio
    async def test_has_access_to_branch_comprehensive(self):
        """브랜치 접근 권한 확인 포괄적 테스트"""
        from core.services.history_service import HistoryService
        
        service = HistoryService()
        
        # 접근 가능한 브랜치
        user_context = {"accessible_branches": ["main", "develop"]}
        assert await service._has_access_to_branch("main", user_context) is True
        assert await service._has_access_to_branch("develop", user_context) is True
        assert await service._has_access_to_branch("feature", user_context) is False
        
        # 기본 접근 권한
        default_context = {}
        assert await service._has_access_to_branch("main", default_context) is True
        assert await service._has_access_to_branch("develop", default_context) is False
    
    @pytest.mark.asyncio
    async def test_has_export_permission_comprehensive(self):
        """내보내기 권한 확인 포괄적 테스트"""
        from core.services.history_service import HistoryService
        
        service = HistoryService()
        
        # 히스토리 내보내기 권한
        history_context = {"permissions": ["history:export"]}
        assert await service._has_export_permission(history_context) is True
        
        # 감사 내보내기 권한
        audit_context = {"permissions": ["audit:export"]}
        assert await service._has_export_permission(audit_context) is True
        
        # 권한 없음
        no_permission_context = {"permissions": ["history:read"]}
        assert await service._has_export_permission(no_permission_context) is False
    
    @pytest.mark.asyncio
    async def test_generate_summary_statistics_comprehensive(self):
        """요약 통계 생성 포괄적 테스트"""
        from core.services.history_service import HistoryService
        from models.history import HistoryEntry, HistoryQuery, ResourceType, ChangeOperation
        
        service = HistoryService()
        
        # 빈 엔트리
        empty_summary = await service._generate_summary_statistics([], HistoryQuery())
        assert empty_summary == {}
        
        # 실제 엔트리들
        entries = [
            HistoryEntry(
                commit_hash=f"commit_{i}",
                branch="main",
                timestamp=datetime.now(timezone.utc),
                author="test_user",
                message=f"Test commit {i}",
                operation=ChangeOperation.UPDATE if i % 2 == 0 else ChangeOperation.CREATE,
                resource_type=ResourceType.OBJECT_TYPE,
                resource_id=f"resource_{i}",
                changes=[],
                total_changes=i,
                breaking_changes=1 if i % 3 == 0 else 0,
                metadata={}
            )
            for i in range(10)
        ]
        
        query = HistoryQuery(
            from_date=datetime.now(timezone.utc) - timedelta(days=30),
            to_date=datetime.now(timezone.utc)
        )
        
        summary = await service._generate_summary_statistics(entries, query)
        assert summary["total_entries"] == 10
        assert "operations" in summary
        assert "resource_types" in summary
        assert "breaking_changes" in summary
        assert "time_range" in summary
    
    def test_get_applied_filters_comprehensive(self):
        """적용된 필터 정보 포괄적 테스트"""
        from core.services.history_service import HistoryService
        from models.history import HistoryQuery, ResourceType, ChangeOperation
        
        service = HistoryService()
        
        # 모든 필터 적용
        query = HistoryQuery(
            branch="main",
            author="test_user",
            resource_type=ResourceType.OBJECT_TYPE,
            resource_id="test_resource",
            operation=ChangeOperation.UPDATE,
            from_date=datetime.now(timezone.utc) - timedelta(days=30),
            to_date=datetime.now(timezone.utc)
        )
        
        filters = service._get_applied_filters(query)
        assert "branch" in filters
        assert "author" in filters
        assert "resource_type" in filters
        assert "resource_id" in filters
        assert "operation" in filters
        assert "from_date" in filters
        assert "to_date" in filters
        
        # 필터 없음
        empty_query = HistoryQuery()
        empty_filters = service._get_applied_filters(empty_query)
        assert len(empty_filters) == 0
    
    @pytest.mark.asyncio
    async def test_analyze_impact_comprehensive(self):
        """영향 분석 포괄적 테스트"""
        from core.services.history_service import HistoryService
        from models.history import AffectedResource, ChangeDetail, ResourceType, ChangeOperation
        
        service = HistoryService()
        
        # 빈 리소스
        empty_analysis = await service._analyze_impact([], [])
        assert empty_analysis == {}
        
        # 실제 리소스와 변경사항
        resources = [
            AffectedResource(
                resource_type=ResourceType.OBJECT_TYPE,
                resource_id="resource_1",
                resource_name="Resource 1",
                impact_type="direct",
                impact_severity="high"
            ),
            AffectedResource(
                resource_type=ResourceType.PROPERTY,
                resource_id="resource_2",
                resource_name="Resource 2",
                impact_type="indirect",
                impact_severity="medium"
            )
        ]
        
        changes = [
            ChangeDetail(
                field="field_1",
                operation=ChangeOperation.UPDATE,
                old_value="old",
                new_value="new",
                path="path.1",
                breaking_change=True
            ),
            ChangeDetail(
                field="field_2",
                operation=ChangeOperation.CREATE,
                old_value=None,
                new_value="new",
                path="path.2",
                breaking_change=False
            )
        ]
        
        analysis = await service._analyze_impact(resources, changes)
        assert analysis["total_affected"] == 2
        assert "impact_by_severity" in analysis
        assert "impact_by_type" in analysis
        assert "breaking_changes_count" in analysis
        assert "risk_assessment" in analysis
    
    def test_assess_risk_level_comprehensive(self):
        """위험 수준 평가 포괄적 테스트"""
        from core.services.history_service import HistoryService
        
        service = HistoryService()
        
        # Critical 위험
        critical_impact = {"critical": 1}
        assert service._assess_risk_level(critical_impact, 0) == "critical"
        
        # Breaking changes로 인한 Critical
        assert service._assess_risk_level({}, 1) == "critical"
        
        # High 위험
        high_impact = {"high": 1}
        assert service._assess_risk_level(high_impact, 0) == "high"
        
        # Medium 위험
        medium_impact = {"medium": 1}
        assert service._assess_risk_level(medium_impact, 0) == "medium"
        
        # Low 위험
        low_impact = {"low": 1}
        assert service._assess_risk_level(low_impact, 0) == "low"
    
    @pytest.mark.asyncio
    async def test_compute_schema_diff_comprehensive(self):
        """스키마 차이점 계산 포괄적 테스트"""
        from core.services.history_service import HistoryService
        
        service = HistoryService()
        
        previous = {"key1": "value1", "key2": "value2"}
        current = {"key1": "value1_updated", "key3": "value3"}
        
        # JSON 형식
        json_diff = await service._compute_schema_diff(previous, current, "json")
        assert isinstance(json_diff, dict)
        assert "added" in json_diff
        assert "removed" in json_diff
        assert "modified" in json_diff
        
        # Text 형식
        text_diff = await service._compute_schema_diff(previous, current, "text")
        assert isinstance(text_diff, str)
        assert "+" in text_diff or "-" in text_diff
        
        # Unified 형식
        unified_diff = await service._compute_schema_diff(previous, current, "unified")
        assert isinstance(unified_diff, str)
    
    def test_compute_json_diff_comprehensive(self):
        """JSON 차이점 계산 포괄적 테스트"""
        from core.services.history_service import HistoryService
        
        service = HistoryService()
        
        previous = {"key1": "value1", "key2": "value2", "shared": "same"}
        current = {"key1": "value1_updated", "key3": "value3", "shared": "same"}
        
        diff = service._compute_json_diff(previous, current)
        assert "key3" in diff["added"]
        assert "key2" in diff["removed"]
        assert "key1" in diff["modified"]
        assert "shared" not in diff["modified"]
    
    def test_compute_text_diff_comprehensive(self):
        """텍스트 차이점 계산 포괄적 테스트"""
        from core.services.history_service import HistoryService
        
        service = HistoryService()
        
        previous = {"key1": "value1", "key2": "value2"}
        current = {"key1": "value1_updated", "key3": "value3"}
        
        diff = service._compute_text_diff(previous, current)
        assert isinstance(diff, str)
        lines = diff.split("\\n")
        assert any("+" in line for line in lines)
        assert any("-" in line for line in lines)
    
    def test_compute_unified_diff_comprehensive(self):
        """Unified diff 계산 포괄적 테스트"""
        from core.services.history_service import HistoryService
        
        service = HistoryService()
        
        previous = {"key1": "value1", "key2": "value2"}
        current = {"key1": "value1_updated", "key3": "value3"}
        
        diff = service._compute_unified_diff(previous, current)
        assert isinstance(diff, str)
    
    @pytest.mark.asyncio
    async def test_export_to_csv_comprehensive(self):
        """CSV 내보내기 포괄적 테스트"""
        from core.services.history_service import HistoryService
        from models.history import HistoryEntry, ChangeDetail, ResourceType, ChangeOperation
        
        service = HistoryService()
        
        entries = [
            HistoryEntry(
                commit_hash="commit_1",
                branch="main",
                timestamp=datetime.now(timezone.utc),
                author="test_user",
                message="Test commit 1",
                operation=ChangeOperation.UPDATE,
                resource_type=ResourceType.OBJECT_TYPE,
                resource_id="resource_1",
                changes=[
                    ChangeDetail(
                        field="field_1",
                        operation=ChangeOperation.UPDATE,
                        old_value="old",
                        new_value="new",
                        path="path.1",
                        breaking_change=False
                    )
                ],
                total_changes=1,
                breaking_changes=0,
                metadata={}
            )
        ]
        
        # 변경사항 포함하지 않음
        csv_data, filename, content_type = await service._export_to_csv(entries, False)
        assert isinstance(csv_data, io.BytesIO)
        assert filename.endswith(".csv")
        assert content_type == "text/csv"
        
        # 변경사항 포함
        csv_with_changes, _, _ = await service._export_to_csv(entries, True)
        assert isinstance(csv_with_changes, io.BytesIO)
    
    @pytest.mark.asyncio
    async def test_export_to_json_comprehensive(self):
        """JSON 내보내기 포괄적 테스트"""
        from core.services.history_service import HistoryService
        from models.history import HistoryEntry, ResourceType, ChangeOperation
        
        service = HistoryService()
        
        entries = [
            HistoryEntry(
                commit_hash="commit_1",
                branch="main",
                timestamp=datetime.now(timezone.utc),
                author="test_user",
                message="Test commit 1",
                operation=ChangeOperation.UPDATE,
                resource_type=ResourceType.OBJECT_TYPE,
                resource_id="resource_1",
                changes=[],
                total_changes=0,
                breaking_changes=0,
                metadata={}
            )
        ]
        
        json_data, filename, content_type = await service._export_to_json(entries)
        assert isinstance(json_data, io.BytesIO)
        assert filename.endswith(".json")
        assert content_type == "application/json"
        
        # 내용 검증
        json_content = json_data.getvalue().decode('utf-8')
        data = json.loads(json_content)
        assert "exported_at" in data
        assert "total_entries" in data
        assert "entries" in data
        assert data["total_entries"] == 1
    
    @pytest.mark.asyncio
    async def test_export_to_excel_comprehensive(self):
        """Excel 내보내기 포괄적 테스트"""
        from core.services.history_service import HistoryService
        from models.history import HistoryEntry, ResourceType, ChangeOperation
        
        service = HistoryService()
        
        entries = [
            HistoryEntry(
                commit_hash="commit_1",
                branch="main",
                timestamp=datetime.now(timezone.utc),
                author="test_user",
                message="Test commit 1",
                operation=ChangeOperation.UPDATE,
                resource_type=ResourceType.OBJECT_TYPE,
                resource_id="resource_1",
                changes=[],
                total_changes=0,
                breaking_changes=0,
                metadata={}
            )
        ]
        
        excel_data, filename, content_type = await service._export_to_excel(entries, False)
        assert isinstance(excel_data, io.BytesIO)


class TestAuditServiceIntensive:
    """AuditService 집중 테스트 - 68% -> 90%"""
    
    @pytest.mark.asyncio
    async def test_search_logs_comprehensive(self):
        """로그 검색 포괄적 테스트"""
        from core.services.audit_service import AuditService
        from models.audit import AuditSearchQuery, AuditEventType, SeverityLevel
        
        service = AuditService()
        user_context = {"user_id": "test_user", "permissions": ["audit:read"]}
        
        # 기본 검색
        query = AuditSearchQuery(limit=10)
        response = await service.search_logs(query, user_context)
        assert response is not None
        assert hasattr(response, 'entries')
        assert hasattr(response, 'total_count')
        
        # 필터링된 검색
        filtered_query = AuditSearchQuery(
            user_id="test_user",
            event_type=AuditEventType.SCHEMA_CHANGE,
            severity=SeverityLevel.WARNING,
            limit=5
        )
        filtered_response = await service.search_logs(filtered_query, user_context)
        assert filtered_response is not None
        assert len(filtered_response.entries) <= 5
        
        # 집계 포함 검색
        aggregated_query = AuditSearchQuery(
            limit=10,
            include_aggregations=True,
            aggregation_fields=["event_type", "severity"]
        )
        aggregated_response = await service.search_logs(aggregated_query, user_context)
        assert aggregated_response is not None
        assert hasattr(aggregated_response, 'aggregations')
    
    @pytest.mark.asyncio
    async def test_get_log_details_comprehensive(self):
        """로그 상세 조회 포괄적 테스트"""
        from core.services.audit_service import AuditService
        
        service = AuditService()
        user_context = {"user_id": "test_user", "permissions": ["audit:read"]}
        
        # 기본 상세 조회
        detail = await service.get_log_details("test_log_123", user_context)
        assert detail is not None
        assert detail.log_id == "test_log_123"
        
        # 메타데이터 포함 조회
        detail_with_meta = await service.get_log_details(
            "test_log_456", user_context, include_metadata=True
        )
        assert detail_with_meta is not None
        assert hasattr(detail_with_meta, 'metadata')
        
        # 상태 정보 포함 조회
        detail_with_states = await service.get_log_details(
            "test_log_789", user_context, include_states=True
        )
        assert detail_with_states is not None
        assert hasattr(detail_with_states, 'states')
    
    @pytest.mark.asyncio
    async def test_start_export_comprehensive(self):
        """내보내기 시작 포괄적 테스트"""
        from core.services.audit_service import AuditService
        from models.audit import AuditExportRequest, AuditSearchQuery
        
        service = AuditService()
        user_context = {"user_id": "test_user", "permissions": ["audit:export"]}
        
        # CSV 내보내기 요청
        csv_request = AuditExportRequest(
            query=AuditSearchQuery(limit=100),
            format="csv",
            audit_purpose="compliance_review",
            requestor_id="test_user"
        )
        csv_response = await service.start_export(csv_request, user_context)
        assert csv_response is not None
        assert csv_response.export_id is not None
        assert csv_response.status == "started"
        
        # JSON 내보내기 요청
        json_request = AuditExportRequest(
            query=AuditSearchQuery(limit=50),
            format="json",
            audit_purpose="investigation",
            requestor_id="test_user"
        )
        json_response = await service.start_export(json_request, user_context)
        assert json_response is not None
        assert json_response.format == "json"
        
        # 배송 방법 포함 요청
        delivery_request = AuditExportRequest(
            query=AuditSearchQuery(limit=25),
            format="xlsx",
            delivery_method="email",
            delivery_address="test@example.com",
            audit_purpose="audit_review",
            requestor_id="test_user"
        )
        delivery_response = await service.start_export(delivery_request, user_context)
        assert delivery_response is not None
        assert delivery_response.delivery_method == "email"
    
    @pytest.mark.asyncio
    async def test_get_export_status_comprehensive(self):
        """내보내기 상태 조회 포괄적 테스트"""
        from core.services.audit_service import AuditService
        
        service = AuditService()
        user_context = {"user_id": "test_user", "permissions": ["audit:export"]}
        
        # 다양한 상태 조회
        export_ids = ["export_started", "export_processing", "export_completed", "export_failed"]
        
        for export_id in export_ids:
            status = await service.get_export_status(export_id, user_context)
            assert status is not None
            assert status.export_id == export_id
            assert status.status in ["started", "processing", "completed", "failed"]
    
    @pytest.mark.asyncio
    async def test_download_export_comprehensive(self):
        """내보내기 다운로드 포괄적 테스트"""
        from core.services.audit_service import AuditService
        
        service = AuditService()
        user_context = {"user_id": "test_user", "permissions": ["audit:export"]}
        
        # 완료된 내보내기 다운로드
        export_data = await service.download_export("export_completed", user_context)
        assert export_data is not None
        assert isinstance(export_data, io.BytesIO)
        
        # 다른 내보내기 다운로드
        export_data_2 = await service.download_export("export_csv_ready", user_context)
        assert export_data_2 is not None
        assert isinstance(export_data_2, io.BytesIO)
    
    @pytest.mark.asyncio
    async def test_get_dashboard_statistics_comprehensive(self):
        """대시보드 통계 포괄적 테스트"""
        from core.services.audit_service import AuditService
        
        service = AuditService()
        user_context = {"user_id": "test_user", "permissions": ["audit:read"]}
        
        # 기본 통계
        stats = await service.get_dashboard_statistics(user_context)
        assert isinstance(stats, dict)
        assert "summary" in stats
        assert "event_distribution" in stats
        assert "severity_distribution" in stats
        
        # 시간 범위별 통계
        time_ranges = ["1h", "24h", "7d", "30d"]
        for time_range in time_ranges:
            stats_time = await service.get_dashboard_statistics(
                user_context, time_range=time_range
            )
            assert isinstance(stats_time, dict)
            assert "summary" in stats_time
        
        # 상세 통계 (모든 옵션 포함)
        detailed_stats = await service.get_dashboard_statistics(
            user_context,
            time_range="24h",
            include_trends=True,
            include_top_users=True,
            include_top_actions=True
        )
        assert "trends" in detailed_stats
        assert "top_users" in detailed_stats
        assert "top_actions" in detailed_stats
        
        # 최소 통계 (트렌드 제외)
        minimal_stats = await service.get_dashboard_statistics(
            user_context,
            time_range="1h",
            include_trends=False,
            include_top_users=False,
            include_top_actions=False
        )
        assert "trends" not in minimal_stats
        assert "top_users" not in minimal_stats
        assert "top_actions" not in minimal_stats
    
    @pytest.mark.asyncio
    async def test_get_retention_status_comprehensive(self):
        """보존 상태 조회 포괄적 테스트"""
        from core.services.audit_service import AuditService
        
        service = AuditService()
        user_context = {"user_id": "test_user", "permissions": ["audit:admin"]}
        
        # 기본 보존 상태
        retention_status = await service.get_retention_status(user_context)
        assert isinstance(retention_status, dict)
        assert "total_logs" in retention_status
        assert "retention_policy" in retention_status
        assert "storage_usage" in retention_status
        assert "cleanup_schedule" in retention_status
        
        # 상세 보존 상태 (시간대별)
        detailed_retention = await service.get_retention_status(
            user_context, include_breakdown=True
        )
        assert isinstance(detailed_retention, dict)
        assert "by_time_period" in detailed_retention
        assert "by_severity" in detailed_retention
    
    @pytest.mark.asyncio
    async def test_process_export_comprehensive(self):
        """내보내기 처리 포괄적 테스트"""
        from core.services.audit_service import AuditService
        from models.audit import AuditExportRequest, AuditSearchQuery
        
        service = AuditService()
        user_context = {"user_id": "test_user"}
        
        # CSV 처리
        csv_request = AuditExportRequest(
            query=AuditSearchQuery(limit=10),
            format="csv",
            audit_purpose="test",
            requestor_id="test_user"
        )
        
        with patch('asyncio.sleep', return_value=None):
            await service._process_export("export_csv_test", csv_request, user_context)
        
        # JSON 처리
        json_request = AuditExportRequest(
            query=AuditSearchQuery(limit=5),
            format="json",
            audit_purpose="test",
            requestor_id="test_user"
        )
        
        with patch('asyncio.sleep', return_value=None):
            await service._process_export("export_json_test", json_request, user_context)
        
        # XLSX 처리
        xlsx_request = AuditExportRequest(
            query=AuditSearchQuery(limit=15),
            format="xlsx",
            audit_purpose="test",
            requestor_id="test_user"
        )
        
        with patch('asyncio.sleep', return_value=None):
            await service._process_export("export_xlsx_test", xlsx_request, user_context)
    
    def test_generate_summary_comprehensive(self):
        """요약 생성 포괄적 테스트"""
        from core.services.audit_service import AuditService
        from models.audit import AuditSearchQuery, AuditLogEntry, AuditEventType, SeverityLevel
        
        service = AuditService()
        
        # 빈 엔트리
        empty_summary = service._generate_summary([], AuditSearchQuery())
        assert empty_summary == {}
        
        # 실제 엔트리들
        entries = [
            AuditLogEntry(
                log_id=f"log_{i}",
                timestamp=datetime.now(timezone.utc),
                event_type=AuditEventType.SCHEMA_CHANGE if i % 2 == 0 else AuditEventType.SCHEMA_REVERT,
                severity=SeverityLevel.INFO if i % 3 == 0 else SeverityLevel.WARNING,
                user_id=f"user_{i % 3}",
                action="test_action",
                resource_type="test_resource",
                resource_id=f"resource_{i}"
            )
            for i in range(20)
        ]
        
        query = AuditSearchQuery(limit=20)
        summary = service._generate_summary(entries, query)
        assert isinstance(summary, dict)
        assert len(summary) > 0
    
    def test_get_applied_filters_comprehensive(self):
        """적용된 필터 정보 포괄적 테스트"""
        from core.services.audit_service import AuditService
        from models.audit import AuditSearchQuery, AuditEventType, SeverityLevel
        
        service = AuditService()
        
        # 모든 필터 적용
        query = AuditSearchQuery(
            user_id="test_user",
            event_type=AuditEventType.SCHEMA_CHANGE,
            severity=SeverityLevel.WARNING,
            from_date=datetime.now(timezone.utc) - timedelta(days=30),
            to_date=datetime.now(timezone.utc),
            resource_type="test_resource",
            resource_id="test_123",
            action="test_action",
            result="success"
        )
        
        filters = service._get_applied_filters(query)
        assert "user_id" in filters
        assert "event_type" in filters
        assert "severity" in filters
        assert "from_date" in filters
        assert "to_date" in filters
        assert "resource_type" in filters
        assert "resource_id" in filters
        assert "action" in filters
        assert "result" in filters
        
        # 필터 없음
        empty_query = AuditSearchQuery(limit=10)
        empty_filters = service._get_applied_filters(empty_query)
        assert len(empty_filters) == 1  # limit만 있음
        assert "limit" in empty_filters
    
    @pytest.mark.asyncio
    async def test_generate_aggregations_comprehensive(self):
        """집계 생성 포괄적 테스트"""
        from core.services.audit_service import AuditService
        from models.audit import AuditSearchQuery, AuditLogEntry, AuditEventType, SeverityLevel
        
        service = AuditService()
        
        # 빈 엔트리
        empty_aggregations = await service._generate_aggregations([], AuditSearchQuery())
        assert empty_aggregations == {}
        
        # 집계 필드 없음
        entries = [
            AuditLogEntry(
                log_id="log_1",
                timestamp=datetime.now(timezone.utc),
                event_type=AuditEventType.SCHEMA_CHANGE,
                severity=SeverityLevel.INFO,
                user_id="user_1",
                action="test_action",
                resource_type="test_resource",
                resource_id="resource_1"
            )
        ]
        
        query_no_agg = AuditSearchQuery(limit=10)
        no_aggregations = await service._generate_aggregations(entries, query_no_agg)
        assert no_aggregations == {}
        
        # 실제 집계
        entries = [
            AuditLogEntry(
                log_id=f"log_{i}",
                timestamp=datetime.now(timezone.utc),
                event_type=AuditEventType.SCHEMA_CHANGE if i % 2 == 0 else AuditEventType.SCHEMA_REVERT,
                severity=SeverityLevel.INFO if i % 3 == 0 else SeverityLevel.WARNING,
                user_id=f"user_{i % 3}",
                action="test_action",
                resource_type="test_resource",
                resource_id=f"resource_{i}"
            )
            for i in range(15)
        ]
        
        query_with_agg = AuditSearchQuery(
            limit=15,
            aggregation_fields=["event_type", "severity", "user_id"]
        )
        
        aggregations = await service._generate_aggregations(entries, query_with_agg)
        assert "by_event_type" in aggregations
        assert "by_severity" in aggregations
        assert "by_user" in aggregations
        
        # 개별 집계 필드 검증
        assert aggregations["by_event_type"]["schema_change"] > 0
        assert aggregations["by_event_type"]["schema_revert"] > 0
        assert len(aggregations["by_user"]) <= 3  # 3명의 사용자


class TestEventProcessorIntensive:
    """EventProcessor 집중 테스트 - 44% -> 90%"""
    
    @pytest.mark.asyncio
    async def test_process_event_comprehensive(self):
        """이벤트 처리 포괄적 테스트"""
        from core.subscribers.event_processor import EventProcessor
        
        processor = EventProcessor()
        
        # 스키마 변경 이벤트
        schema_change_event = {
            "id": "test-schema-change-123",
            "type": "com.oms.schema.changed",
            "time": "2024-01-01T12:00:00Z",
            "data": {
                "branch": "main",
                "author": "test_user",
                "commit_hash": "abc123def456",
                "changes": [
                    {
                        "field": "price",
                        "operation": "update",
                        "old_value": {"type": "string"},
                        "new_value": {"type": "number"},
                        "path": "object_types.Product.properties.price",
                        "breaking_change": True
                    }
                ]
            }
        }
        
        await processor.process_event(schema_change_event)
        
        # 스키마 검증 이벤트
        schema_validation_event = {
            "id": "test-schema-validation-456",
            "type": "com.oms.schema.validated",
            "time": "2024-01-01T12:05:00Z",
            "data": {
                "branch": "main",
                "validation_result": "passed",
                "errors": [],
                "warnings": ["deprecated_field_usage"]
            }
        }
        
        await processor.process_event(schema_validation_event)
        
        # 스키마 복원 이벤트
        schema_revert_event = {
            "id": "test-schema-revert-789",
            "type": "com.oms.schema.reverted",
            "time": "2024-01-01T12:10:00Z",
            "data": {
                "branch": "main",
                "author": "admin_user",
                "new_commit_hash": "revert_789abc",
                "reverted_from": "bad_commit_123",
                "reverted_to": "good_commit_456",
                "reason": "Breaking change rollback"
            }
        }
        
        await processor.process_event(schema_revert_event)
    
    @pytest.mark.asyncio
    async def test_create_schema_change_history_entry_comprehensive(self):
        """스키마 변경 히스토리 엔트리 생성 포괄적 테스트"""
        from core.subscribers.event_processor import EventProcessor
        
        processor = EventProcessor()
        
        # 단순 변경 이벤트
        simple_event = {
            "id": "simple-change-123",
            "type": "com.oms.schema.changed",
            "time": "2024-01-01T12:00:00Z",
            "data": {
                "branch": "main",
                "author": "test_user",
                "commit_hash": "simple_abc123",
                "message": "Simple schema change",
                "changes": [
                    {
                        "field": "name",
                        "operation": "update",
                        "old_value": "string",
                        "new_value": "text",
                        "path": "object_types.User.properties.name",
                        "breaking_change": False
                    }
                ]
            }
        }
        
        simple_entry = await processor.create_schema_change_history_entry(simple_event)
        assert simple_entry.commit_hash == "simple_abc123"
        assert simple_entry.branch == "main"
        assert simple_entry.operation.value == "update"
        assert len(simple_entry.changes) == 1
        assert simple_entry.breaking_changes == 0
        
        # 복합 변경 이벤트
        complex_event = {
            "id": "complex-change-456",
            "type": "com.oms.schema.changed",
            "time": "2024-01-01T12:30:00Z",
            "data": {
                "branch": "develop",
                "author": "dev_user",
                "author_email": "dev@example.com",
                "commit_hash": "complex_def456",
                "message": "Complex schema changes with breaking changes",
                "changes": [
                    {
                        "field": "price",
                        "operation": "update",
                        "old_value": {"type": "string", "format": "currency"},
                        "new_value": {"type": "number", "minimum": 0},
                        "path": "object_types.Product.properties.price",
                        "breaking_change": True
                    },
                    {
                        "field": "description",
                        "operation": "create",
                        "old_value": None,
                        "new_value": {"type": "string", "maxLength": 1000},
                        "path": "object_types.Product.properties.description",
                        "breaking_change": False
                    },
                    {
                        "field": "legacy_field",
                        "operation": "delete",
                        "old_value": {"type": "string"},
                        "new_value": None,
                        "path": "object_types.Product.properties.legacy_field",
                        "breaking_change": True
                    }
                ],
                "affected_resources": [
                    {
                        "resource_type": "object_type",
                        "resource_id": "Product",
                        "resource_name": "Product Schema",
                        "impact_type": "direct",
                        "impact_severity": "high"
                    },
                    {
                        "resource_type": "property",
                        "resource_id": "Product.price",
                        "resource_name": "Product Price",
                        "impact_type": "direct",
                        "impact_severity": "critical"
                    }
                ]
            }
        }
        
        complex_entry = await processor.create_schema_change_history_entry(complex_event)
        assert complex_entry.commit_hash == "complex_def456"
        assert complex_entry.branch == "develop"
        assert complex_entry.author == "dev_user"
        assert complex_entry.author_email == "dev@example.com"
        assert len(complex_entry.changes) == 3
        assert complex_entry.breaking_changes == 2
        assert len(complex_entry.affected_resources) == 2
    
    @pytest.mark.asyncio
    async def test_create_audit_log_comprehensive(self):
        """감사 로그 생성 포괄적 테스트"""
        from core.subscribers.event_processor import EventProcessor
        
        processor = EventProcessor()
        
        # 스키마 변경 감사 로그
        schema_change_event = {
            "id": "audit-schema-change-123",
            "type": "com.oms.schema.changed",
            "time": "2024-01-01T12:00:00Z",
            "data": {
                "branch": "main",
                "author": "test_user",
                "commit_hash": "audit_abc123",
                "changes": [
                    {
                        "field": "price",
                        "operation": "update",
                        "breaking_change": True
                    }
                ]
            }
        }
        
        audit_log = await processor.create_audit_log(schema_change_event)
        assert audit_log.log_id == "audit-schema-change-123"
        assert audit_log.event_type.value == "schema_change"
        assert audit_log.user_id == "test_user"
        assert audit_log.action == "schema_update"
        assert audit_log.resource_type == "schema"
        assert audit_log.resource_id == "audit_abc123"
        assert audit_log.severity.value == "warning"  # Breaking change
        
        # 스키마 검증 감사 로그
        schema_validation_event = {
            "id": "audit-schema-validation-456",
            "type": "com.oms.schema.validated",
            "time": "2024-01-01T12:05:00Z",
            "data": {
                "branch": "main",
                "validation_result": "failed",
                "errors": ["invalid_format", "missing_required_field"],
                "warnings": ["deprecated_usage"]
            }
        }
        
        validation_audit_log = await processor.create_audit_log(schema_validation_event)
        assert validation_audit_log.event_type.value == "schema_validation"
        assert validation_audit_log.action == "schema_validation"
        assert validation_audit_log.result == "failed"
        assert validation_audit_log.severity.value == "error"  # Validation failed
        
        # 스키마 복원 감사 로그
        schema_revert_event = {
            "id": "audit-schema-revert-789",
            "type": "com.oms.schema.reverted",
            "time": "2024-01-01T12:10:00Z",
            "data": {
                "branch": "main",
                "author": "admin_user",
                "new_commit_hash": "revert_789abc",
                "reverted_from": "bad_commit_123",
                "reason": "Emergency rollback"
            }
        }
        
        revert_audit_log = await processor.create_audit_log(schema_revert_event)
        assert revert_audit_log.event_type.value == "schema_revert"
        assert revert_audit_log.action == "schema_revert"
        assert revert_audit_log.user_id == "admin_user"
        assert revert_audit_log.severity.value == "critical"  # Revert operation
    
    @pytest.mark.asyncio
    async def test_create_revert_history_entry_comprehensive(self):
        """복원 히스토리 엔트리 생성 포괄적 테스트"""
        from core.subscribers.event_processor import EventProcessor
        
        processor = EventProcessor()
        
        # 단순 복원 이벤트
        simple_revert_event = {
            "id": "simple-revert-123",
            "type": "com.oms.schema.reverted",
            "time": "2024-01-01T12:00:00Z",
            "data": {
                "branch": "main",
                "author": "admin_user",
                "new_commit_hash": "revert_simple_123",
                "reverted_from": "bad_commit_456",
                "reverted_to": "good_commit_789",
                "reason": "Simple rollback"
            }
        }
        
        simple_revert_entry = await processor.create_revert_history_entry(simple_revert_event)
        assert simple_revert_entry.commit_hash == "revert_simple_123"
        assert simple_revert_entry.operation.value == "revert"
        assert simple_revert_entry.breaking_changes == 0  # Reverts are not breaking
        assert "good_commit_789" in simple_revert_entry.message
        assert simple_revert_entry.metadata["reverted_from"] == "bad_commit_456"
        assert simple_revert_entry.metadata["reason"] == "Simple rollback"
        
        # 복합 복원 이벤트 (변경사항 포함)
        complex_revert_event = {
            "id": "complex-revert-456",
            "type": "com.oms.schema.reverted",
            "time": "2024-01-01T12:30:00Z",
            "data": {
                "branch": "develop",
                "author": "senior_admin",
                "author_email": "admin@example.com",
                "new_commit_hash": "revert_complex_456",
                "reverted_from": "breaking_commit_789",
                "reverted_to": "stable_commit_abc",
                "reason": "Critical breaking changes detected",
                "revert_type": "hard",
                "reverted_changes": [
                    {
                        "field": "price_field",
                        "operation": "delete",
                        "old_value": {"type": "number", "required": True},
                        "new_value": None,
                        "path": "object_types.Product.properties.price",
                        "breaking_change": True
                    },
                    {
                        "field": "name_field",
                        "operation": "update",
                        "old_value": {"type": "string", "maxLength": 100},
                        "new_value": {"type": "string", "maxLength": 50},
                        "path": "object_types.Product.properties.name",
                        "breaking_change": False
                    }
                ]
            }
        }
        
        complex_revert_entry = await processor.create_revert_history_entry(complex_revert_event)
        assert complex_revert_entry.commit_hash == "revert_complex_456"
        assert complex_revert_entry.branch == "develop"
        assert complex_revert_entry.author == "senior_admin"
        assert complex_revert_entry.author_email == "admin@example.com"
        assert len(complex_revert_entry.changes) == 2
        assert complex_revert_entry.breaking_changes == 0  # Reverts are not breaking themselves
        assert complex_revert_entry.metadata["revert_type"] == "hard"
        assert "stable_commit_abc" in complex_revert_entry.message
    
    def test_determine_data_classification_comprehensive(self):
        """데이터 분류 결정 포괄적 테스트"""
        from core.subscribers.event_processor import EventProcessor
        from models.audit import AuditLogEntry, AuditEventType, SeverityLevel
        
        processor = EventProcessor()
        
        # 제한된 데이터 (결제 관련)
        payment_entry = AuditLogEntry(
            log_id="payment_test",
            timestamp=datetime.now(timezone.utc),
            event_type=AuditEventType.SCHEMA_CHANGE,
            severity=SeverityLevel.INFO,
            user_id="test_user",
            action="update",
            resource_type="payment_method",
            resource_id="payment_123"
        )
        assert processor._determine_data_classification(payment_entry) == "restricted"
        
        # 기밀 데이터 (사용자 관련)
        user_entry = AuditLogEntry(
            log_id="user_test",
            timestamp=datetime.now(timezone.utc),
            event_type=AuditEventType.SCHEMA_CHANGE,
            severity=SeverityLevel.INFO,
            user_id="test_user",
            action="update",
            resource_type="user_profile",
            resource_id="user_456"
        )
        assert processor._determine_data_classification(user_entry) == "confidential"
        
        # 내부 데이터 (시스템 관련)
        system_entry = AuditLogEntry(
            log_id="system_test",
            timestamp=datetime.now(timezone.utc),
            event_type=AuditEventType.SCHEMA_CHANGE,
            severity=SeverityLevel.INFO,
            user_id="test_user",
            action="update",
            resource_type="system_config",
            resource_id="config_789"
        )
        assert processor._determine_data_classification(system_entry) == "internal"
        
        # 공개 데이터 (기타)
        public_entry = AuditLogEntry(
            log_id="public_test",
            timestamp=datetime.now(timezone.utc),
            event_type=AuditEventType.SCHEMA_CHANGE,
            severity=SeverityLevel.INFO,
            user_id="test_user",
            action="update",
            resource_type="public_info",
            resource_id="info_123"
        )
        assert processor._determine_data_classification(public_entry) == "public"
    
    def test_extract_details_comprehensive(self):
        """상세 정보 추출 포괄적 테스트"""
        from core.subscribers.event_processor import EventProcessor
        
        processor = EventProcessor()
        
        # 기본 데이터
        basic_data = {
            "branch": "main",
            "commit_hash": "abc123",
            "author": "test_user"
        }
        
        basic_details = processor._extract_details(basic_data)
        assert basic_details["branch"] == "main"
        assert basic_details["commit_hash"] == "abc123"
        assert basic_details["author"] == "test_user"
        assert basic_details["changes_count"] == 0
        assert basic_details["breaking_changes"] == 0
        
        # 변경사항 포함 데이터
        changes_data = {
            "branch": "develop",
            "commit_hash": "def456",
            "changes": [
                {"breaking_change": True},
                {"breaking_change": False},
                {"breaking_change": True},
                {"breaking_change": False}
            ]
        }
        
        changes_details = processor._extract_details(changes_data)
        assert changes_details["changes_count"] == 4
        assert changes_details["breaking_changes"] == 2
        
        # 복합 데이터
        complex_data = {
            "branch": "feature/new-api",
            "commit_hash": "ghi789",
            "author": "dev_user",
            "author_email": "dev@example.com",
            "message": "Complex feature implementation",
            "changes": [
                {"breaking_change": True},
                {"breaking_change": False},
                {"breaking_change": True}
            ],
            "validation_result": "passed",
            "extra_field": "should_be_ignored"
        }
        
        complex_details = processor._extract_details(complex_data)
        assert complex_details["branch"] == "feature/new-api"
        assert complex_details["commit_hash"] == "ghi789"
        assert complex_details["author"] == "dev_user"
        assert complex_details["author_email"] == "dev@example.com"
        assert complex_details["message"] == "Complex feature implementation"
        assert complex_details["changes_count"] == 3
        assert complex_details["breaking_changes"] == 2
        assert complex_details["validation_result"] == "passed"
        assert "extra_field" not in complex_details
    
    @pytest.mark.asyncio
    async def test_send_to_configured_siem_comprehensive(self):
        """설정된 SIEM으로 전송 포괄적 테스트"""
        from core.subscribers.event_processor import EventProcessor
        
        processor = EventProcessor()
        
        test_event = {
            "timestamp": "2024-01-01T12:00:00Z",
            "event_type": "com.oms.schema.changed",
            "user_id": "test_user",
            "action": "schema_update"
        }
        
        # Elasticsearch 전송
        with patch.dict(os.environ, {'SIEM_TYPE': 'elasticsearch'}):
            with patch.object(processor, '_send_to_elasticsearch') as mock_es:
                await processor._send_to_configured_siem(test_event)
                mock_es.assert_called_once_with(test_event)
        
        # Splunk 전송
        with patch.dict(os.environ, {'SIEM_TYPE': 'splunk'}):
            with patch.object(processor, '_send_to_splunk') as mock_splunk:
                await processor._send_to_configured_siem(test_event)
                mock_splunk.assert_called_once_with(test_event)
        
        # Webhook 전송
        with patch.dict(os.environ, {'SIEM_TYPE': 'webhook'}):
            with patch.object(processor, '_send_to_webhook') as mock_webhook:
                await processor._send_to_configured_siem(test_event)
                mock_webhook.assert_called_once_with(test_event)
        
        # 알 수 없는 타입
        with patch.dict(os.environ, {'SIEM_TYPE': 'unknown'}):
            with patch.object(processor.logger, 'warning') as mock_warning:
                await processor._send_to_configured_siem(test_event)
                mock_warning.assert_called_once()
        
        # SIEM 타입 설정 없음
        with patch.dict(os.environ, {}, clear=True):
            # 설정이 없으면 전송하지 않음
            await processor._send_to_configured_siem(test_event)
    
    @pytest.mark.asyncio
    async def test_send_to_elasticsearch_comprehensive(self):
        """Elasticsearch 전송 포괄적 테스트"""
        from core.subscribers.event_processor import EventProcessor
        
        processor = EventProcessor()
        
        test_event = {
            "timestamp": "2024-01-01T12:00:00Z",
            "event_type": "test_event",
            "user_id": "test_user"
        }
        
        # 인증 없는 Elasticsearch
        with patch.dict(os.environ, {
            'ELASTICSEARCH_HOST': 'localhost:9200',
            'ELASTICSEARCH_INDEX': 'test-index'
        }):
            with patch('elasticsearch.AsyncElasticsearch') as mock_es_class:
                mock_es = AsyncMock()
                mock_es_class.return_value = mock_es
                
                await processor._send_to_elasticsearch(test_event)
                
                mock_es_class.assert_called_with(
                    ['localhost:9200'],
                    verify_certs=False
                )
                mock_es.index.assert_called_once()
                mock_es.close.assert_called_once()
        
        # 인증 있는 Elasticsearch
        with patch.dict(os.environ, {
            'ELASTICSEARCH_HOST': 'secure.elastic.com:9200',
            'ELASTICSEARCH_USERNAME': 'elastic_user',
            'ELASTICSEARCH_PASSWORD': 'elastic_pass',
            'ELASTICSEARCH_INDEX': 'secure-index'
        }):
            with patch('elasticsearch.AsyncElasticsearch') as mock_es_class:
                mock_es = AsyncMock()
                mock_es_class.return_value = mock_es
                
                await processor._send_to_elasticsearch(test_event)
                
                mock_es_class.assert_called_with(
                    ['secure.elastic.com:9200'],
                    basic_auth=('elastic_user', 'elastic_pass'),
                    verify_certs=False
                )
        
        # 설정 누락
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(processor.logger, 'warning') as mock_warning:
                await processor._send_to_elasticsearch(test_event)
                mock_warning.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_to_splunk_comprehensive(self):
        """Splunk 전송 포괄적 테스트"""
        from core.subscribers.event_processor import EventProcessor
        
        processor = EventProcessor()
        
        test_event = {
            "timestamp": "2024-01-01T12:00:00Z",
            "event_type": "test_event",
            "user_id": "test_user"
        }
        
        # 성공적인 Splunk 전송
        with patch.dict(os.environ, {
            'SPLUNK_HOST': 'https://splunk.example.com:8088',
            'SPLUNK_HEC_TOKEN': 'splunk-token-123',
            'SPLUNK_INDEX': 'audit-logs'
        }):
            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_response = AsyncMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"text": "Success", "code": 0}
                mock_client.post.return_value = mock_response
                mock_client_class.return_value.__aenter__.return_value = mock_client
                
                await processor._send_to_splunk(test_event)
                
                mock_client.post.assert_called_once()
                call_args = mock_client.post.call_args
                assert 'https://splunk.example.com:8088/services/collector/event' in call_args[1]['url']
                assert 'Splunk splunk-token-123' in call_args[1]['headers']['Authorization']
        
        # 에러 응답
        with patch.dict(os.environ, {
            'SPLUNK_HOST': 'https://splunk.example.com:8088',
            'SPLUNK_HEC_TOKEN': 'splunk-token-456',
            'SPLUNK_INDEX': 'audit-logs'
        }):
            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_response = AsyncMock()
                mock_response.status_code = 400
                mock_response.text = "Bad Request"
                mock_client.post.return_value = mock_response
                mock_client_class.return_value.__aenter__.return_value = mock_client
                
                with patch.object(processor.logger, 'error') as mock_error:
                    await processor._send_to_splunk(test_event)
                    mock_error.assert_called_once()
        
        # 설정 누락
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(processor.logger, 'warning') as mock_warning:
                await processor._send_to_splunk(test_event)
                mock_warning.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_to_webhook_comprehensive(self):
        """Webhook 전송 포괄적 테스트"""
        from core.subscribers.event_processor import EventProcessor
        
        processor = EventProcessor()
        
        test_event = {
            "timestamp": "2024-01-01T12:00:00Z",
            "event_type": "test_event",
            "user_id": "test_user"
        }
        
        # 성공적인 Webhook 전송
        with patch.dict(os.environ, {
            'SIEM_WEBHOOK_URL': 'https://webhook.example.com/siem',
            'SIEM_WEBHOOK_SECRET': 'webhook-secret-123'
        }):
            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_response = AsyncMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"status": "received"}
                mock_client.post.return_value = mock_response
                mock_client_class.return_value.__aenter__.return_value = mock_client
                
                await processor._send_to_webhook(test_event)
                
                mock_client.post.assert_called_once()
                call_args = mock_client.post.call_args
                assert call_args[1]['url'] == 'https://webhook.example.com/siem'
                assert call_args[1]['headers']['X-SIEM-Secret'] == 'webhook-secret-123'
        
        # Secret 없는 Webhook
        with patch.dict(os.environ, {
            'SIEM_WEBHOOK_URL': 'https://webhook.example.com/siem'
        }):
            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_response = AsyncMock()
                mock_response.status_code = 200
                mock_client.post.return_value = mock_response
                mock_client_class.return_value.__aenter__.return_value = mock_client
                
                await processor._send_to_webhook(test_event)
                
                call_args = mock_client.post.call_args
                assert 'X-SIEM-Secret' not in call_args[1]['headers']
        
        # 에러 응답
        with patch.dict(os.environ, {
            'SIEM_WEBHOOK_URL': 'https://webhook.example.com/siem'
        }):
            with patch('httpx.AsyncClient') as mock_client_class:
                mock_client = AsyncMock()
                mock_response = AsyncMock()
                mock_response.status_code = 500
                mock_response.text = "Internal Server Error"
                mock_client.post.return_value = mock_response
                mock_client_class.return_value.__aenter__.return_value = mock_client
                
                with patch.object(processor.logger, 'error') as mock_error:
                    await processor._send_to_webhook(test_event)
                    mock_error.assert_called_once()
        
        # URL 누락
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(processor.logger, 'warning') as mock_warning:
                await processor._send_to_webhook(test_event)
                mock_warning.assert_called_once()