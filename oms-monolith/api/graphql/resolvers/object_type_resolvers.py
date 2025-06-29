"""
ObjectType Query and Mutation Resolvers
"""
import logging
from typing import List, Optional

import httpx
import strawberry

from ..schema import (
    ObjectType,
    ObjectTypeConnection,
    ObjectTypeInput,
    ObjectTypeUpdateInput,
    Property,
    StatusEnum,
    TypeClassEnum,
)
from .service_client import service_client

logger = logging.getLogger(__name__)


class ObjectTypeQueryResolvers:
    """ObjectType Query Resolvers"""

    @strawberry.field
    async def object_types(
        self,
        info: strawberry.Info,
        branch: str = "main",
        status: Optional[StatusEnum] = None,
        type_class: Optional[TypeClassEnum] = None,
        interface: Optional[str] = None,
        search: Optional[str] = None,
        include_properties: bool = True,
        include_deprecated: bool = False,
        limit: int = 100,
        offset: int = 0
    ) -> ObjectTypeConnection:
        """ObjectType 목록 조회"""
        user = info.context.get("user")

        params = {
            "status": status.value if status else None,
            "type_class": type_class.value if type_class else None,
            "limit": limit,
            "offset": offset
        }

        url = f"{service_client.schema_service_url}/api/v1/schemas/{branch}/object-types"
        result = await service_client.call_service(url, "GET", params, user)

        # 데이터 변환
        object_types = []
        for item in result.get('data', []):
            object_type = ObjectType(
                id=item.get('id', ''),
                name=item.get('name', ''),
                displayName=item.get('displayName', ''),
                pluralDisplayName=item.get('pluralDisplayName'),
                description=item.get('description'),
                status=StatusEnum(item.get('status', 'active')),
                typeClass=TypeClassEnum(item.get('typeClass', 'object')),
                versionHash=item.get('versionHash', ''),
                createdBy=item.get('createdBy', ''),
                createdAt=item.get('createdAt'),
                modifiedBy=item.get('modifiedBy', ''),
                modifiedAt=item.get('modifiedAt'),
                parentTypes=item.get('parentTypes', []),
                interfaces=item.get('interfaces', []),
                isAbstract=item.get('isAbstract', False),
                icon=item.get('icon'),
                color=item.get('color')
            )

            # Properties 포함
            if include_properties and item.get('properties'):
                object_type.properties = [
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
                    ) for prop in item.get('properties', [])
                ]

            object_types.append(object_type)

        total_count = result.get('totalCount', len(object_types))
        has_next = offset + limit < total_count
        has_prev = offset > 0

        return ObjectTypeConnection(
            data=object_types,
            totalCount=total_count,
            hasNextPage=has_next,
            hasPreviousPage=has_prev
        )

    @strawberry.field
    async def object_type(
        self,
        info: strawberry.Info,
        id: str,
        branch: str = "main",
        include_properties: bool = True,
        include_actions: bool = False,
        include_metrics: bool = False
    ) -> Optional[ObjectType]:
        """ObjectType 상세 조회"""
        user = info.context.get("user")

        url = f"{service_client.schema_service_url}/api/v1/schemas/{branch}/object-types/{id}"
        try:
            result = await service_client.call_service(url, "GET", None, user)

            # 데이터 변환
            object_type = ObjectType(
                id=result.get('id', ''),
                name=result.get('name', ''),
                displayName=result.get('displayName', ''),
                pluralDisplayName=result.get('pluralDisplayName'),
                description=result.get('description'),
                status=StatusEnum(result.get('status', 'active')),
                typeClass=TypeClassEnum(result.get('typeClass', 'object')),
                versionHash=result.get('versionHash', ''),
                createdBy=result.get('createdBy', ''),
                createdAt=result.get('createdAt'),
                modifiedBy=result.get('modifiedBy', ''),
                modifiedAt=result.get('modifiedAt'),
                parentTypes=result.get('parentTypes', []),
                interfaces=result.get('interfaces', []),
                isAbstract=result.get('isAbstract', False),
                icon=result.get('icon'),
                color=result.get('color')
            )

            # Properties 포함
            if include_properties and result.get('properties'):
                object_type.properties = [
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
                    ) for prop in result.get('properties', [])
                ]

            return object_type

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise


class ObjectTypeMutationResolvers:
    """ObjectType Mutation Resolvers"""

    @strawberry.field
    async def create_object_type(
        self,
        info: strawberry.Info,
        input: ObjectTypeInput,
        branch: str = "main"
    ) -> ObjectType:
        """ObjectType 생성"""
        user = info.context.get("user")

        url = f"{service_client.schema_service_url}/api/v1/schemas/{branch}/object-types"
        data = {
            "name": input.name,
            "displayName": input.displayName,
            "pluralDisplayName": input.pluralDisplayName,
            "description": input.description,
            "status": input.status.value if input.status else None,
            "typeClass": input.typeClass.value if input.typeClass else None,
            "parentTypes": input.parentTypes,
            "interfaces": input.interfaces,
            "isAbstract": input.isAbstract,
            "icon": input.icon,
            "color": input.color
        }

        result = await service_client.call_service(url, "POST", data, user)

        # 데이터 변환
        return ObjectType(
            id=result.get('id', ''),
            name=result.get('name', ''),
            displayName=result.get('displayName', ''),
            pluralDisplayName=result.get('pluralDisplayName'),
            description=result.get('description'),
            status=StatusEnum(result.get('status', 'active')),
            typeClass=TypeClassEnum(result.get('typeClass', 'object')),
            versionHash=result.get('versionHash', ''),
            createdBy=result.get('createdBy', ''),
            createdAt=result.get('createdAt'),
            modifiedBy=result.get('modifiedBy', ''),
            modifiedAt=result.get('modifiedAt'),
            parentTypes=result.get('parentTypes', []),
            interfaces=result.get('interfaces', []),
            isAbstract=result.get('isAbstract', False),
            icon=result.get('icon'),
            color=result.get('color')
        )

    @strawberry.field
    async def update_object_type(
        self,
        info: strawberry.Info,
        id: str,
        input: ObjectTypeUpdateInput,
        branch: str = "main"
    ) -> ObjectType:
        """ObjectType 업데이트"""
        user = info.context.get("user")

        url = f"{service_client.schema_service_url}/api/v1/schemas/{branch}/object-types/{id}"
        data = {
            "displayName": input.displayName,
            "pluralDisplayName": input.pluralDisplayName,
            "description": input.description,
            "status": input.status.value if input.status else None,
            "parentTypes": input.parentTypes,
            "interfaces": input.interfaces,
            "isAbstract": input.isAbstract,
            "icon": input.icon,
            "color": input.color
        }

        result = await service_client.call_service(url, "PUT", data, user)

        # 데이터 변환
        return ObjectType(
            id=result.get('id', ''),
            name=result.get('name', ''),
            displayName=result.get('displayName', ''),
            pluralDisplayName=result.get('pluralDisplayName'),
            description=result.get('description'),
            status=StatusEnum(result.get('status', 'active')),
            typeClass=TypeClassEnum(result.get('typeClass', 'object')),
            versionHash=result.get('versionHash', ''),
            createdBy=result.get('createdBy', ''),
            createdAt=result.get('createdAt'),
            modifiedBy=result.get('modifiedBy', ''),
            modifiedAt=result.get('modifiedAt'),
            parentTypes=result.get('parentTypes', []),
            interfaces=result.get('interfaces', []),
            isAbstract=result.get('isAbstract', False),
            icon=result.get('icon'),
            color=result.get('color')
        )

    @strawberry.field
    async def delete_object_type(
        self,
        info: strawberry.Info,
        id: str,
        branch: str = "main",
        force: bool = False
    ) -> bool:
        """ObjectType 삭제"""
        user = info.context.get("user")

        url = f"{service_client.schema_service_url}/api/v1/schemas/{branch}/object-types/{id}"
        params = {"force": force}

        await service_client.call_service(url, "DELETE", params, user)
        return True