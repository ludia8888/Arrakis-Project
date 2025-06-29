"""
DataType Query and Mutation Resolvers
"""
import logging
from typing import List, Optional

import strawberry

from ..schema import (
    DataType,
    DataTypeCategoryEnum,
    DataTypeFormatEnum,
    DataTypeInput,
    DataTypeUpdateInput,
    TypeConstraint,
)
from .service_client import service_client

logger = logging.getLogger(__name__)


class DataTypeQueryResolvers:
    """DataType Query Resolvers"""

    @strawberry.field
    async def data_types(
        self,
        info: strawberry.Info,
        branch: str = "main",
        category: Optional[DataTypeCategoryEnum] = None,
        format: Optional[DataTypeFormatEnum] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[DataType]:
        """Data Type 목록 조회"""
        user = info.context.get("user")

        params = {
            "category": category.value if category else None,
            "format": format.value if format else None,
            "tags": ",".join(tags) if tags else None,
            "limit": limit,
            "offset": offset
        }

        # None 값 제거
        params = {k: v for k, v in params.items() if v is not None}

        url = f"{service_client.schema_service_url}/api/v1/schemas/{branch}/data-types"
        result = await service_client.call_service(url, "GET", params, user)

        data_types = []
        for dt in result:
            data_types.append(self._convert_to_data_type(dt))

        return data_types

    @strawberry.field
    async def data_type(
        self,
        info: strawberry.Info,
        id: str,
        branch: str = "main"
    ) -> Optional[DataType]:
        """특정 Data Type 조회"""
        user = info.context.get("user")

        url = f"{service_client.schema_service_url}/api/v1/schemas/{branch}/data-types/{id}"
        try:
            result = await service_client.call_service(url, "GET", None, user)
            return self._convert_to_data_type(result)
        except Exception as e:
            if "404" in str(e):
                return None
            raise

    def _convert_to_data_type(self, result: dict) -> DataType:
        """DataType 변환"""
        # Constraints 변환
        constraints = []
        for constraint in result.get('constraints', []):
            constraints.append(TypeConstraint(
                constraintType=constraint.get('constraintType', ''),
                value=constraint.get('value'),
                message=constraint.get('message')
            ))

        return DataType(
            id=result.get('id', ''),
            name=result.get('name', ''),
            displayName=result.get('displayName', ''),
            description=result.get('description'),
            category=DataTypeCategoryEnum(result.get('category', 'primitive')),
            format=DataTypeFormatEnum(result.get('format', 'xsd:string')),
            constraints=constraints,
            defaultValue=result.get('defaultValue'),
            isNullable=result.get('isNullable', True),
            isArrayType=result.get('isArrayType', False),
            arrayItemType=result.get('arrayItemType'),
            mapKeyType=result.get('mapKeyType'),
            mapValueType=result.get('mapValueType'),
            metadata=result.get('metadata'),
            supportedOperations=result.get('supportedOperations', []),
            compatibleTypes=result.get('compatibleTypes', []),
            isSystem=result.get('isSystem', False),
            isDeprecated=result.get('isDeprecated', False),
            deprecationMessage=result.get('deprecationMessage'),
            tags=result.get('tags', []),
            version=result.get('version', '1.0.0'),
            versionHash=result.get('versionHash', ''),
            previousVersionId=result.get('previousVersionId'),
            createdBy=result.get('createdBy', ''),
            createdAt=result.get('createdAt'),
            modifiedBy=result.get('modifiedBy', ''),
            modifiedAt=result.get('modifiedAt'),
            branchId=result.get('branchId'),
            isBranchSpecific=result.get('isBranchSpecific', False),
            isPublic=result.get('isPublic', True),
            allowedRoles=result.get('allowedRoles', []),
            allowedUsers=result.get('allowedUsers', [])
        )


class DataTypeMutationResolvers:
    """DataType Mutation Resolvers"""

    @strawberry.field
    async def create_data_type(
        self,
        info: strawberry.Info,
        input: DataTypeInput,
        branch: str = "main"
    ) -> DataType:
        """Data Type 생성"""
        user = info.context.get("user")

        url = f"{service_client.schema_service_url}/api/v1/schemas/{branch}/data-types"
        result = await service_client.call_service(url, "POST", input, user)

        return self._convert_to_data_type(result)

    @strawberry.field
    async def update_data_type(
        self,
        info: strawberry.Info,
        id: str,
        input: DataTypeUpdateInput,
        branch: str = "main"
    ) -> DataType:
        """Data Type 수정"""
        user = info.context.get("user")

        url = f"{service_client.schema_service_url}/api/v1/schemas/{branch}/data-types/{id}"
        result = await service_client.call_service(url, "PUT", input, user)

        return self._convert_to_data_type(result)

    @strawberry.field
    async def delete_data_type(
        self,
        info: strawberry.Info,
        id: str,
        branch: str = "main"
    ) -> bool:
        """Data Type 삭제"""
        user = info.context.get("user")

        url = f"{service_client.schema_service_url}/api/v1/schemas/{branch}/data-types/{id}"

        await service_client.call_service(url, "DELETE", None, user)
        return True

    def _convert_to_data_type(self, result: dict) -> DataType:
        """API 응답을 GraphQL DataType으로 변환"""
        # Constraints 변환
        constraints = []
        for constraint in result.get('constraints', []):
            constraints.append(TypeConstraint(
                constraintType=constraint.get('constraintType', ''),
                value=constraint.get('value'),
                message=constraint.get('message')
            ))

        return DataType(
            id=result.get('id', ''),
            name=result.get('name', ''),
            displayName=result.get('displayName', ''),
            description=result.get('description'),
            category=DataTypeCategoryEnum(result.get('category', 'primitive')),
            format=DataTypeFormatEnum(result.get('format', 'xsd:string')),
            constraints=constraints,
            defaultValue=result.get('defaultValue'),
            isNullable=result.get('isNullable', True),
            isArrayType=result.get('isArrayType', False),
            arrayItemType=result.get('arrayItemType'),
            mapKeyType=result.get('mapKeyType'),
            mapValueType=result.get('mapValueType'),
            metadata=result.get('metadata'),
            supportedOperations=result.get('supportedOperations', []),
            compatibleTypes=result.get('compatibleTypes', []),
            isSystem=result.get('isSystem', False),
            isDeprecated=result.get('isDeprecated', False),
            deprecationMessage=result.get('deprecationMessage'),
            tags=result.get('tags', []),
            version=result.get('version', '1.0.0'),
            versionHash=result.get('versionHash', ''),
            previousVersionId=result.get('previousVersionId'),
            createdBy=result.get('createdBy', ''),
            createdAt=result.get('createdAt'),
            modifiedBy=result.get('modifiedBy', ''),
            modifiedAt=result.get('modifiedAt'),
            branchId=result.get('branchId'),
            isBranchSpecific=result.get('isBranchSpecific', False),
            isPublic=result.get('isPublic', True),
            allowedRoles=result.get('allowedRoles', []),
            allowedUsers=result.get('allowedUsers', [])
        )