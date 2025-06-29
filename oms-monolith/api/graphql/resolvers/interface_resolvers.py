"""
Interface Query Resolvers
"""
import logging
from typing import List, Optional

import httpx
import strawberry

from ..schema import (
    Interface,
    Property,
    StatusEnum,
)
from .service_client import service_client

logger = logging.getLogger(__name__)


class InterfaceQueryResolvers:
    """Interface Query Resolvers"""

    @strawberry.field
    async def interfaces(
        self,
        info: strawberry.Info,
        branch: str = "main",
        search: Optional[str] = None
    ) -> List[Interface]:
        """Interface 목록 조회"""
        user = info.context.get("user")

        url = f"{service_client.schema_service_url}/api/v1/schemas/{branch}/interfaces"
        params = {}
        if search:
            params['search'] = search

        result = await service_client.call_service(url, "GET", params, user)

        # 데이터 변환
        interfaces = []
        for iface in result.get('data', []):
            interface = Interface(
                id=iface.get('id', ''),
                name=iface.get('name', ''),
                displayName=iface.get('displayName', ''),
                description=iface.get('description'),
                status=StatusEnum(iface.get('status', 'active')),
                versionHash=iface.get('versionHash', ''),
                createdBy=iface.get('createdBy', ''),
                createdAt=iface.get('createdAt'),
                modifiedBy=iface.get('modifiedBy', ''),
                modifiedAt=iface.get('modifiedAt')
            )

            # Properties 포함
            if iface.get('properties'):
                interface.properties = [
                    Property(
                        id=prop.get('id', ''),
                        objectTypeId=prop.get('objectTypeId', ''),
                        name=prop.get('name', ''),
                        displayName=prop.get('displayName', ''),
                        dataType=prop.get('dataType', ''),
                        isRequired=prop.get('isRequired', False),
                        isUnique=prop.get('isUnique', False),
                        isPrimaryKey=prop.get('isPrimaryKey', False),
                        isSearchable=prop.get('isSearchable', False),
                        isIndexed=prop.get('isIndexed', False),
                        defaultValue=prop.get('defaultValue'),
                        description=prop.get('description'),
                        enumValues=prop.get('enumValues', []),
                        linkedObjectType=prop.get('linkedObjectType'),
                        status=StatusEnum(prop.get('status', 'active')),
                        versionHash=prop.get('versionHash', ''),
                        createdBy=prop.get('createdBy', ''),
                        createdAt=prop.get('createdAt'),
                        modifiedBy=prop.get('modifiedBy', ''),
                        modifiedAt=prop.get('modifiedAt')
                    ) for prop in iface.get('properties', [])
                ]

            interfaces.append(interface)

        return interfaces

    @strawberry.field
    async def interface(
        self,
        info: strawberry.Info,
        id: str,
        branch: str = "main"
    ) -> Optional[Interface]:
        """Interface 상세 조회"""
        user = info.context.get("user")

        url = f"{service_client.schema_service_url}/api/v1/schemas/{branch}/interfaces/{id}"
        try:
            # TODO: 실제 데이터 변환 로직 구현
            _ = await service_client.call_service(url, "GET", None, user)
            return None
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise