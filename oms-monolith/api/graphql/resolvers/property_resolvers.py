"""
Property and SharedProperty Query Resolvers
"""
import logging
from typing import List, Optional

import strawberry

from ..schema import (
    Property,
    SharedProperty,
    StatusEnum,
)
from .service_client import service_client

logger = logging.getLogger(__name__)


class PropertyQueryResolvers:
    """Property Query Resolvers"""

    @strawberry.field
    async def properties(
        self,
        info: strawberry.Info,
        object_type_id: str,
        branch: str = "main",
        include_inherited: bool = False
    ) -> List[Property]:
        """Property 목록 조회"""
        user = info.context.get("user")

        url = f"{service_client.schema_service_url}/api/v1/schemas/{branch}/object-types/{object_type_id}/properties"
        result = await service_client.call_service(url, "GET", None, user)

        # 데이터 변환
        properties = []
        for prop in result.get('data', []):
            property_obj = Property(
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
            )
            properties.append(property_obj)

        return properties

    @strawberry.field
    async def shared_properties(
        self,
        info: strawberry.Info,
        branch: str = "main",
        data_type: Optional[str] = None,
        semantic_type: Optional[str] = None
    ) -> List[SharedProperty]:
        """SharedProperty 목록 조회"""
        user = info.context.get("user")

        url = f"{service_client.schema_service_url}/api/v1/schemas/{branch}/shared-properties"
        params = {}
        if data_type:
            params['data_type'] = data_type
        if semantic_type:
            params['semantic_type'] = semantic_type

        result = await service_client.call_service(url, "GET", params, user)

        # 데이터 변환
        shared_properties = []
        for sp in result.get('data', []):
            shared_prop = SharedProperty(
                id=sp.get('id', ''),
                name=sp.get('name', ''),
                displayName=sp.get('displayName', ''),
                description=sp.get('description'),
                dataType=sp.get('dataType', ''),
                semanticType=sp.get('semanticType'),
                defaultValue=sp.get('defaultValue'),
                enumValues=sp.get('enumValues', []),
                status=StatusEnum(sp.get('status', 'active')),
                versionHash=sp.get('versionHash', ''),
                createdBy=sp.get('createdBy', ''),
                createdAt=sp.get('createdAt'),
                modifiedBy=sp.get('modifiedBy', ''),
                modifiedAt=sp.get('modifiedAt')
            )
            shared_properties.append(shared_prop)

        return shared_properties