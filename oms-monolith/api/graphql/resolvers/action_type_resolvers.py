"""
ActionType Query and Mutation Resolvers
"""
import logging
from typing import List, Optional

import httpx
import strawberry

from ..schema import (
    ActionCategoryEnum,
    ActionType,
    ActionTypeInput,
    ActionTypeReference,
    ActionTypeUpdateInput,
    ApplicableObjectType,
    ParameterSchema,
    TransformationTypeEnum,
)
from .service_client import service_client

logger = logging.getLogger(__name__)


class ActionTypeQueryResolvers:
    """ActionType Query Resolvers"""

    @strawberry.field
    async def action_types(
        self,
        info: strawberry.Info,
        branch: str = "main",
        category: Optional[ActionCategoryEnum] = None,
        transformation_type: Optional[TransformationTypeEnum] = None,
        applicable_object_type: Optional[str] = None
    ) -> List[ActionType]:
        """ActionType 목록 조회"""
        user = info.context.get("user")

        url = f"{service_client.schema_service_url}/api/v1/schemas/{branch}/action-types"
        params = {}
        if category:
            params['category'] = category.value
        if transformation_type:
            params['transformation_type'] = transformation_type.value
        if applicable_object_type:
            params['applicable_object_type'] = applicable_object_type

        result = await service_client.call_service(url, "GET", params, user)

        # 데이터 변환
        action_types = []
        for at in result:
            # ApplicableObjectType 변환
            applicable_object_types = []
            for obj in at.get('applicableObjectTypes', []):
                applicable_object_types.append(ApplicableObjectType(
                    objectTypeId=obj.get('objectTypeId', ''),
                    role=obj.get('role', 'primary'),
                    required=obj.get('required', True),
                    description=obj.get('description')
                ))

            # ParameterSchema 변환
            parameter_schema = None
            if at.get('parameterSchema'):
                ps = at['parameterSchema']
                parameter_schema = ParameterSchema(
                    schema=ps.get('schema', {}),
                    examples=ps.get('examples', []),
                    uiHints=ps.get('uiHints')
                )

            # ActionTypeReference 변환
            referenced_actions = []
            for ref in at.get('referencedActions', []):
                referenced_actions.append(ActionTypeReference(
                    actionTypeId=ref.get('actionTypeId', ''),
                    version=ref.get('version'),
                    description=ref.get('description')
                ))

            action_type = ActionType(
                id=at.get('id', ''),
                name=at.get('name', ''),
                displayName=at.get('displayName', ''),
                description=at.get('description'),
                category=ActionCategoryEnum(at.get('category', 'custom')),
                transformationType=TransformationTypeEnum(at.get('transformationType', 'custom')),
                transformationTypeRef=at.get('transformationTypeRef'),
                applicableObjectTypes=applicable_object_types,
                parameterSchema=parameter_schema,
                configuration=at.get('configuration', {}),
                referencedActions=referenced_actions,
                requiredPermissions=at.get('requiredPermissions', []),
                tags=at.get('tags', []),
                metadata=at.get('metadata', {}),
                isSystem=at.get('isSystem', False),
                isDeprecated=at.get('isDeprecated', False),
                version=at.get('version', 1),
                versionHash=at.get('versionHash', ''),
                createdBy=at.get('createdBy', ''),
                createdAt=at.get('createdAt'),
                modifiedBy=at.get('modifiedBy', ''),
                modifiedAt=at.get('modifiedAt')
            )
            action_types.append(action_type)

        return action_types

    @strawberry.field
    async def action_type(
        self,
        info: strawberry.Info,
        id: str,
        branch: str = "main"
    ) -> Optional[ActionType]:
        """ActionType 상세 조회"""
        user = info.context.get("user")

        url = f"{service_client.schema_service_url}/api/v1/schemas/{branch}/action-types/{id}"
        try:
            result = await service_client.call_service(url, "GET", None, user)

            # ApplicableObjectType 변환
            applicable_object_types = []
            for obj in result.get('applicableObjectTypes', []):
                applicable_object_types.append(ApplicableObjectType(
                    objectTypeId=obj.get('objectTypeId', ''),
                    role=obj.get('role', 'primary'),
                    required=obj.get('required', True),
                    description=obj.get('description')
                ))

            # ParameterSchema 변환
            parameter_schema = None
            if result.get('parameterSchema'):
                ps = result['parameterSchema']
                parameter_schema = ParameterSchema(
                    schema=ps.get('schema', {}),
                    examples=ps.get('examples', []),
                    uiHints=ps.get('uiHints')
                )

            # ActionTypeReference 변환
            referenced_actions = []
            for ref in result.get('referencedActions', []):
                referenced_actions.append(ActionTypeReference(
                    actionTypeId=ref.get('actionTypeId', ''),
                    version=ref.get('version'),
                    description=ref.get('description')
                ))

            return ActionType(
                id=result.get('id', ''),
                name=result.get('name', ''),
                displayName=result.get('displayName', ''),
                description=result.get('description'),
                category=ActionCategoryEnum(result.get('category', 'custom')),
                transformationType=TransformationTypeEnum(result.get('transformationType', 'custom')),
                transformationTypeRef=result.get('transformationTypeRef'),
                applicableObjectTypes=applicable_object_types,
                parameterSchema=parameter_schema,
                configuration=result.get('configuration', {}),
                referencedActions=referenced_actions,
                requiredPermissions=result.get('requiredPermissions', []),
                tags=result.get('tags', []),
                metadata=result.get('metadata', {}),
                isSystem=result.get('isSystem', False),
                isDeprecated=result.get('isDeprecated', False),
                version=result.get('version', 1),
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


class ActionTypeMutationResolvers:
    """ActionType Mutation Resolvers"""

    @strawberry.field
    async def create_action_type(
        self,
        info: strawberry.Info,
        input: ActionTypeInput,
        branch: str = "main"
    ) -> ActionType:
        """ActionType 생성"""
        user = info.context.get("user")

        url = f"{service_client.schema_service_url}/api/v1/schemas/{branch}/action-types"

        # Input 데이터 변환
        data = {
            "name": input.name,
            "displayName": input.displayName,
            "description": input.description,
            "category": input.category.value,
            "transformationType": input.transformation_type.value,
            "transformationTypeRef": input.transformation_type_ref,
            "applicableObjectTypes": [
                {
                    "objectTypeId": obj.object_type_id,
                    "role": obj.role,
                    "required": obj.required,
                    "description": obj.description
                }
                for obj in input.applicable_object_types
            ],
            "parameterSchema": {
                "schema": input.parameter_schema.schema,
                "examples": input.parameter_schema.examples,
                "uiHints": input.parameter_schema.ui_hints
            } if input.parameter_schema else None,
            "configuration": input.configuration or {},
            "referencedActions": [
                {
                    "actionTypeId": ref.action_type_id,
                    "version": ref.version,
                    "description": ref.description
                }
                for ref in (input.referenced_actions or [])
            ],
            "requiredPermissions": input.required_permissions or [],
            "tags": input.tags or [],
            "metadata": input.metadata or {}
        }

        result = await service_client.call_service(url, "POST", data, user)

        # 결과 변환
        # ApplicableObjectType 변환
        applicable_object_types = []
        for obj in result.get('applicableObjectTypes', []):
            applicable_object_types.append(ApplicableObjectType(
                objectTypeId=obj.get('objectTypeId', ''),
                role=obj.get('role', 'primary'),
                required=obj.get('required', True),
                description=obj.get('description')
            ))

        # ParameterSchema 변환
        parameter_schema = None
        if result.get('parameterSchema'):
            ps = result['parameterSchema']
            parameter_schema = ParameterSchema(
                schema=ps.get('schema', {}),
                examples=ps.get('examples', []),
                uiHints=ps.get('uiHints')
            )

        # ActionTypeReference 변환
        referenced_actions = []
        for ref in result.get('referencedActions', []):
            referenced_actions.append(ActionTypeReference(
                actionTypeId=ref.get('actionTypeId', ''),
                version=ref.get('version'),
                description=ref.get('description')
            ))

        return ActionType(
            id=result.get('id', ''),
            name=result.get('name', ''),
            displayName=result.get('displayName', ''),
            description=result.get('description'),
            category=ActionCategoryEnum(result.get('category', 'custom')),
            transformationType=TransformationTypeEnum(result.get('transformationType', 'custom')),
            transformationTypeRef=result.get('transformationTypeRef'),
            applicableObjectTypes=applicable_object_types,
            parameterSchema=parameter_schema,
            configuration=result.get('configuration', {}),
            referencedActions=referenced_actions,
            requiredPermissions=result.get('requiredPermissions', []),
            tags=result.get('tags', []),
            metadata=result.get('metadata', {}),
            isSystem=result.get('isSystem', False),
            isDeprecated=result.get('isDeprecated', False),
            version=result.get('version', 1),
            versionHash=result.get('versionHash', ''),
            createdBy=result.get('createdBy', ''),
            createdAt=result.get('createdAt'),
            modifiedBy=result.get('modifiedBy', ''),
            modifiedAt=result.get('modifiedAt')
        )

    @strawberry.field
    async def update_action_type(
        self,
        info: strawberry.Info,
        id: str,
        input: ActionTypeUpdateInput,
        branch: str = "main"
    ) -> ActionType:
        """ActionType 업데이트"""
        user = info.context.get("user")

        url = f"{service_client.schema_service_url}/api/v1/schemas/{branch}/action-types/{id}"

        # Update input 데이터 변환
        data = {}
        if input.display_name:
            data["displayName"] = input.display_name
        if input.description is not None:
            data["description"] = input.description
        if input.transformation_type:
            data["transformationType"] = input.transformation_type.value
        if input.transformation_type_ref is not None:
            data["transformationTypeRef"] = input.transformation_type_ref
        if input.applicable_object_types:
            data["applicableObjectTypes"] = [
                {
                    "objectTypeId": obj.object_type_id,
                    "role": obj.role,
                    "required": obj.required,
                    "description": obj.description
                }
                for obj in input.applicable_object_types
            ]
        if input.parameter_schema:
            data["parameterSchema"] = {
                "schema": input.parameter_schema.schema,
                "examples": input.parameter_schema.examples,
                "uiHints": input.parameter_schema.ui_hints
            }
        if input.configuration is not None:
            data["configuration"] = input.configuration
        if input.referenced_actions is not None:
            data["referencedActions"] = [
                {
                    "actionTypeId": ref.action_type_id,
                    "version": ref.version,
                    "description": ref.description
                }
                for ref in input.referenced_actions
            ]
        if input.required_permissions is not None:
            data["requiredPermissions"] = input.required_permissions
        if input.tags is not None:
            data["tags"] = input.tags
        if input.metadata is not None:
            data["metadata"] = input.metadata
        if input.is_deprecated is not None:
            data["isDeprecated"] = input.is_deprecated

        result = await service_client.call_service(url, "PUT", data, user)

        # 결과 변환 (생성과 동일한 로직)
        # ApplicableObjectType 변환
        applicable_object_types = []
        for obj in result.get('applicableObjectTypes', []):
            applicable_object_types.append(ApplicableObjectType(
                objectTypeId=obj.get('objectTypeId', ''),
                role=obj.get('role', 'primary'),
                required=obj.get('required', True),
                description=obj.get('description')
            ))

        # ParameterSchema 변환
        parameter_schema = None
        if result.get('parameterSchema'):
            ps = result['parameterSchema']
            parameter_schema = ParameterSchema(
                schema=ps.get('schema', {}),
                examples=ps.get('examples', []),
                uiHints=ps.get('uiHints')
            )

        # ActionTypeReference 변환
        referenced_actions = []
        for ref in result.get('referencedActions', []):
            referenced_actions.append(ActionTypeReference(
                actionTypeId=ref.get('actionTypeId', ''),
                version=ref.get('version'),
                description=ref.get('description')
            ))

        return ActionType(
            id=result.get('id', ''),
            name=result.get('name', ''),
            displayName=result.get('displayName', ''),
            description=result.get('description'),
            category=ActionCategoryEnum(result.get('category', 'custom')),
            transformationType=TransformationTypeEnum(result.get('transformationType', 'custom')),
            transformationTypeRef=result.get('transformationTypeRef'),
            applicableObjectTypes=applicable_object_types,
            parameterSchema=parameter_schema,
            configuration=result.get('configuration', {}),
            referencedActions=referenced_actions,
            requiredPermissions=result.get('requiredPermissions', []),
            tags=result.get('tags', []),
            metadata=result.get('metadata', {}),
            isSystem=result.get('isSystem', False),
            isDeprecated=result.get('isDeprecated', False),
            version=result.get('version', 1),
            versionHash=result.get('versionHash', ''),
            createdBy=result.get('createdBy', ''),
            createdAt=result.get('createdAt'),
            modifiedBy=result.get('modifiedBy', ''),
            modifiedAt=result.get('modifiedAt')
        )

    @strawberry.field
    async def delete_action_type(
        self,
        info: strawberry.Info,
        id: str,
        branch: str = "main"
    ) -> bool:
        """ActionType 삭제"""
        user = info.context.get("user")

        url = f"{service_client.schema_service_url}/api/v1/schemas/{branch}/action-types/{id}"

        await service_client.call_service(url, "DELETE", None, user)
        return True