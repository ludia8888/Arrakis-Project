"""
LinkType Query Resolvers
"""
import logging
from typing import List, Optional

import httpx
import strawberry

from ..schema import (
    LinkType,
    StatusEnum,
)
from .service_client import service_client

logger = logging.getLogger(__name__)


class LinkTypeQueryResolvers:
    """LinkType Query Resolvers"""

    @strawberry.field
    async def link_types(
        self,
        info: strawberry.Info,
        branch: str = "main",
        from_type: Optional[str] = None,
        to_type: Optional[str] = None,
        status: Optional[StatusEnum] = None
    ) -> List[LinkType]:
        """LinkType 목록 조회"""
        user = info.context.get("user")

        url = f"{service_client.schema_service_url}/api/v1/schemas/{branch}/link-types"
        params = {}
        if from_type:
            params['from_type'] = from_type
        if to_type:
            params['to_type'] = to_type
        if status:
            params['status'] = status.value

        result = await service_client.call_service(url, "GET", params, user)

        # 데이터 변환
        link_types = []
        for lt in result.get('data', []):
            link_type = LinkType(
                id=lt.get('id', ''),
                name=lt.get('name', ''),
                displayName=lt.get('displayName', ''),
                description=lt.get('description'),
                fromObjectType=lt.get('fromObjectType', ''),
                toObjectType=lt.get('toObjectType', ''),
                directionality=lt.get('directionality', 'directional'),
                fromCardinality=lt.get('fromCardinality', 'many'),
                toCardinality=lt.get('toCardinality', 'many'),
                status=StatusEnum(lt.get('status', 'active')),
                versionHash=lt.get('versionHash', ''),
                createdBy=lt.get('createdBy', ''),
                createdAt=lt.get('createdAt'),
                modifiedBy=lt.get('modifiedBy', ''),
                modifiedAt=lt.get('modifiedAt')
            )
            link_types.append(link_type)

        return link_types

    @strawberry.field
    async def link_type(
        self,
        info: strawberry.Info,
        id: str,
        branch: str = "main"
    ) -> Optional[LinkType]:
        """LinkType 상세 조회"""
        user = info.context.get("user")

        url = f"{service_client.schema_service_url}/api/v1/schemas/{branch}/link-types/{id}"
        try:
            result = await service_client.call_service(url, "GET", None, user)

            # 데이터 변환
            return LinkType(
                id=result.get('id', ''),
                name=result.get('name', ''),
                displayName=result.get('displayName', ''),
                description=result.get('description'),
                fromObjectType=result.get('fromObjectType', ''),
                toObjectType=result.get('toObjectType', ''),
                directionality=result.get('directionality', 'directional'),
                fromCardinality=result.get('fromCardinality', 'many'),
                toCardinality=result.get('toCardinality', 'many'),
                status=StatusEnum(result.get('status', 'active')),
                versionHash=result.get('versionHash', ''),
                createdBy=result.get('createdBy', ''),
                createdAt=result.get('createdAt'),
                modifiedBy=result.get('modifiedBy', ''),
                modifiedAt=result.get('modifiedAt')
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise