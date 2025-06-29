"""
Utility Query Resolvers (History, Validation, Search)
"""
import logging
from typing import List, Optional

import httpx
import strawberry

from ..schema import (
    BreakingChange,
    HistoryEntry,
    ImpactAnalysis,
    ResourceTypeEnum,
    SearchItem,
    SearchResult,
    SuggestedMigration,
    ValidationResult,
    ValidationWarning,
)
from .service_client import service_client

logger = logging.getLogger(__name__)


class UtilityQueryResolvers:
    """Utility Query Resolvers"""

    @strawberry.field
    async def history(
        self,
        info: strawberry.Info,
        branch: str = "main",
        resource_type: Optional[ResourceTypeEnum] = None,
        resource_id: Optional[str] = None,
        limit: int = 50
    ) -> List[HistoryEntry]:
        """버전 히스토리 조회"""
        user = info.context.get("user")

        # 히스토리 서비스 호출
        url = f"{service_client.branch_service_url}/api/v1/branches/{branch}/history"
        params = {
            'limit': limit
        }
        if resource_type:
            params['resource_type'] = resource_type.value
        if resource_id:
            params['resource_id'] = resource_id

        try:
            result = await service_client.call_service(url, "GET", params, user)

            # 데이터 변환
            history_entries = []
            for entry in result.get('data', []):
                history_entry = HistoryEntry(
                    id=entry.get('id', ''),
                    hash=entry.get('hash', ''),
                    message=entry.get('message', ''),
                    author=entry.get('author', ''),
                    timestamp=entry.get('timestamp'),
                    resourceType=ResourceTypeEnum(entry.get('resourceType', 'object_type')),
                    resourceId=entry.get('resourceId'),
                    operation=entry.get('operation', 'update'),
                    changes=entry.get('changes', {})
                )
                history_entries.append(history_entry)

            return history_entries

        except httpx.HTTPStatusError:
            # 히스토리 서비스가 사용할 수 없으면 빈 리스트 반환
            return []

    @strawberry.field
    async def validate_changes(
        self,
        info: strawberry.Info,
        source_branch: str,
        target_branch: str = "main"
    ) -> ValidationResult:
        """변경사항 검증"""
        user = info.context.get("user")

        url = f"{service_client.validation_service_url}/api/v1/validate"
        data = {
            "source_branch": source_branch,
            "target_branch": target_branch
        }
        result = await service_client.call_service(url, "POST", data, user)

        # 데이터 변환
        breaking_changes = []
        for bc in result.get('breakingChanges', []):
            breaking_changes.append(BreakingChange(
                type=bc.get('type', ''),
                description=bc.get('description', ''),
                resourceType=ResourceTypeEnum(bc.get('resourceType', 'object_type')),
                resourceId=bc.get('resourceId', ''),
                severity=bc.get('severity', 'high'),
                mitigation=bc.get('mitigation')
            ))

        warnings = []
        for warning in result.get('warnings', []):
            warnings.append(ValidationWarning(
                type=warning.get('type', ''),
                message=warning.get('message', ''),
                resourceType=ResourceTypeEnum(warning.get('resourceType', 'object_type')),
                resourceId=warning.get('resourceId', ''),
                recommendation=warning.get('recommendation')
            ))

        suggested_migrations = []
        for migration in result.get('suggestedMigrations', []):
            suggested_migrations.append(SuggestedMigration(
                type=migration.get('type', ''),
                description=migration.get('description', ''),
                script=migration.get('script', ''),
                reversible=migration.get('reversible', False),
                estimatedTime=migration.get('estimatedTime')
            ))

        impact_analysis = None
        if result.get('impactAnalysis'):
            ia = result['impactAnalysis']
            impact_analysis = ImpactAnalysis(
                affectedObjectTypes=ia.get('affectedObjectTypes', []),
                affectedProperties=ia.get('affectedProperties', []),
                affectedLinkTypes=ia.get('affectedLinkTypes', []),
                estimatedDowntime=ia.get('estimatedDowntime'),
                migrationComplexity=ia.get('migrationComplexity', 'low'),
                riskLevel=ia.get('riskLevel', 'low')
            )

        return ValidationResult(
            isValid=result.get('isValid', True),
            breakingChanges=breaking_changes,
            warnings=warnings,
            impactAnalysis=impact_analysis,
            suggestedMigrations=suggested_migrations,
            validationTime=result.get('validationTime')
        )

    @strawberry.field
    async def search(
        self,
        info: strawberry.Info,
        query: str,
        branch: str = "main",
        types: Optional[List[ResourceTypeEnum]] = None,
        limit: int = 20
    ) -> SearchResult:
        """통합 검색"""
        user = info.context.get("user")

        # 검색 서비스 호출 (가용한 경우)
        try:
            # 스키마 서비스에서 검색 기능 사용
            url = f"{service_client.schema_service_url}/api/v1/schemas/{branch}/search"
            params = {
                'query': query,
                'limit': limit
            }
            if types:
                params['types'] = [t.value for t in types]

            result = await service_client.call_service(url, "GET", params, user)

            # 데이터 변환
            search_items = []
            for item in result.get('items', []):
                search_item = SearchItem(
                    id=item.get('id', ''),
                    type=ResourceTypeEnum(item.get('type', 'object_type')),
                    name=item.get('name', ''),
                    displayName=item.get('displayName', ''),
                    description=item.get('description'),
                    score=item.get('score', 0.0),
                    branch=item.get('branch', branch),
                    path=item.get('path', ''),
                    highlights=item.get('highlights', {})
                )
                search_items.append(search_item)

            return SearchResult(
                items=search_items,
                totalCount=result.get('totalCount', len(search_items)),
                facets=result.get('facets', {})
            )

        except httpx.HTTPStatusError:
            # 검색 서비스가 사용할 수 없으면 빈 결과 반환
            return SearchResult(
                items=[],
                totalCount=0,
                facets={}
            )