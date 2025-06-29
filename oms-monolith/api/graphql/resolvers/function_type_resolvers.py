"""
FunctionType Query and Mutation Resolvers
"""
import logging
from typing import List, Optional

import strawberry

from ..schema import (
    FunctionBehavior,
    FunctionCategoryEnum,
    FunctionExample,
    FunctionParameter,
    FunctionRuntimeEnum,
    FunctionType,
    FunctionTypeInput,
    FunctionTypeUpdateInput,
    ParameterDirectionEnum,
    ReturnType,
    RuntimeConfig,
)
from .service_client import service_client

logger = logging.getLogger(__name__)


class FunctionTypeQueryResolvers:
    """FunctionType Query Resolvers"""

    @strawberry.field
    async def function_types(
        self,
        info: strawberry.Info,
        branch: str = "main",
        category: Optional[FunctionCategoryEnum] = None,
        runtime: Optional[FunctionRuntimeEnum] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[FunctionType]:
        """Function Type 목록 조회"""
        user = info.context.get("user")

        params = {
            "category": category.value if category else None,
            "runtime": runtime.value if runtime else None,
            "tags": ",".join(tags) if tags else None,
            "limit": limit,
            "offset": offset
        }

        # None 값 제거
        params = {k: v for k, v in params.items() if v is not None}

        url = f"{service_client.schema_service_url}/api/v1/schemas/{branch}/function-types"
        result = await service_client.call_service(url, "GET", params, user)

        function_types = []
        for ft in result:
            function_types.append(self._convert_to_function_type(ft))

        return function_types

    @strawberry.field
    async def function_type(
        self,
        info: strawberry.Info,
        id: str,
        branch: str = "main"
    ) -> Optional[FunctionType]:
        """특정 Function Type 조회"""
        user = info.context.get("user")

        url = f"{service_client.schema_service_url}/api/v1/schemas/{branch}/function-types/{id}"
        try:
            result = await service_client.call_service(url, "GET", None, user)
            return self._convert_to_function_type(result)
        except Exception as e:
            if "404" in str(e):
                return None
            raise

    def _convert_to_function_type(self, result: dict) -> FunctionType:
        """FunctionType 변환"""
        # Parameters 변환
        parameters = []
        for param in result.get('parameters', []):
            parameters.append(FunctionParameter(
                name=param.get('name', ''),
                displayName=param.get('displayName', ''),
                description=param.get('description'),
                direction=ParameterDirectionEnum(param.get('direction', 'input')),
                dataTypeId=param.get('dataTypeId', ''),
                semanticTypeId=param.get('semanticTypeId'),
                structTypeId=param.get('structTypeId'),
                isRequired=param.get('isRequired', True),
                isArray=param.get('isArray', False),
                defaultValue=param.get('defaultValue'),
                validationRules=param.get('validationRules'),
                metadata=param.get('metadata'),
                sortOrder=param.get('sortOrder', 0)
            ))

        # Return type 변환
        rt = result.get('returnType', {})
        return_type = ReturnType(
            dataTypeId=rt.get('dataTypeId', ''),
            semanticTypeId=rt.get('semanticTypeId'),
            structTypeId=rt.get('structTypeId'),
            isArray=rt.get('isArray', False),
            isNullable=rt.get('isNullable', True),
            description=rt.get('description'),
            metadata=rt.get('metadata')
        )

        # Runtime config 변환
        rc = result.get('runtimeConfig', {})
        runtime_config = RuntimeConfig(
            runtime=FunctionRuntimeEnum(rc.get('runtime', 'python')),
            version=rc.get('version'),
            timeoutMs=rc.get('timeoutMs', 30000),
            memoryMb=rc.get('memoryMb', 512),
            cpuCores=rc.get('cpuCores', 1.0),
            maxRetries=rc.get('maxRetries', 3),
            retryDelayMs=rc.get('retryDelayMs', 1000),
            environmentVars=rc.get('environmentVars'),
            dependencies=rc.get('dependencies', []),
            resourceLimits=rc.get('resourceLimits')
        )

        # Behavior 변환
        bh = result.get('behavior', {})
        behavior = FunctionBehavior(
            isDeterministic=bh.get('isDeterministic', True),
            isStateless=bh.get('isStateless', True),
            isCacheable=bh.get('isCacheable', True),
            isParallelizable=bh.get('isParallelizable', True),
            hasSideEffects=bh.get('hasSideEffects', False),
            isExpensive=bh.get('isExpensive', False),
            cacheTtlSeconds=bh.get('cacheTtlSeconds')
        )

        # Examples 변환
        examples = []
        for ex in result.get('examples', []):
            examples.append(FunctionExample(
                name=ex.get('name', ''),
                description=ex.get('description'),
                inputValues=ex.get('inputValues', {}),
                expectedOutput=ex.get('expectedOutput'),
                explanation=ex.get('explanation')
            ))

        return FunctionType(
            id=result.get('id', ''),
            name=result.get('name', ''),
            displayName=result.get('displayName', ''),
            description=result.get('description'),
            category=FunctionCategoryEnum(result.get('category', 'custom')),
            parameters=parameters,
            returnType=return_type,
            runtimeConfig=runtime_config,
            behavior=behavior,
            implementationRef=result.get('implementationRef'),
            functionBody=result.get('functionBody'),
            examples=examples,
            tags=result.get('tags', []),
            isPublic=result.get('isPublic', True),
            allowedRoles=result.get('allowedRoles', []),
            allowedUsers=result.get('allowedUsers', []),
            metadata=result.get('metadata'),
            isSystem=result.get('isSystem', False),
            isDeprecated=result.get('isDeprecated', False),
            version=result.get('version', '1.0.0'),
            versionHash=result.get('versionHash', ''),
            previousVersionId=result.get('previousVersionId'),
            createdBy=result.get('createdBy', ''),
            createdAt=result.get('createdAt'),
            modifiedBy=result.get('modifiedBy', ''),
            modifiedAt=result.get('modifiedAt'),
            branchId=result.get('branchId'),
            isBranchSpecific=result.get('isBranchSpecific', False)
        )


class FunctionTypeMutationResolvers:
    """FunctionType Mutation Resolvers"""

    @strawberry.field
    async def create_function_type(
        self,
        info: strawberry.Info,
        input: FunctionTypeInput,
        branch: str = "main"
    ) -> FunctionType:
        """Function Type 생성"""
        user = info.context.get("user")

        url = f"{service_client.schema_service_url}/api/v1/schemas/{branch}/function-types"
        result = await service_client.call_service(url, "POST", input, user)

        return self._convert_to_function_type(result)

    @strawberry.field
    async def update_function_type(
        self,
        info: strawberry.Info,
        id: str,
        input: FunctionTypeUpdateInput,
        branch: str = "main"
    ) -> FunctionType:
        """Function Type 수정"""
        user = info.context.get("user")

        url = f"{service_client.schema_service_url}/api/v1/schemas/{branch}/function-types/{id}"
        result = await service_client.call_service(url, "PUT", input, user)

        return self._convert_to_function_type(result)

    @strawberry.field
    async def delete_function_type(
        self,
        info: strawberry.Info,
        id: str,
        branch: str = "main"
    ) -> bool:
        """Function Type 삭제"""
        user = info.context.get("user")

        url = f"{service_client.schema_service_url}/api/v1/schemas/{branch}/function-types/{id}"

        await service_client.call_service(url, "DELETE", None, user)
        return True

    def _convert_to_function_type(self, result: dict) -> FunctionType:
        """API 응답을 GraphQL FunctionType으로 변환"""
        # Parameters 변환
        parameters = []
        for param in result.get('parameters', []):
            parameters.append(FunctionParameter(
                name=param.get('name', ''),
                displayName=param.get('displayName', ''),
                description=param.get('description'),
                direction=ParameterDirectionEnum(param.get('direction', 'input')),
                dataTypeId=param.get('dataTypeId', ''),
                semanticTypeId=param.get('semanticTypeId'),
                structTypeId=param.get('structTypeId'),
                isRequired=param.get('isRequired', True),
                isArray=param.get('isArray', False),
                defaultValue=param.get('defaultValue'),
                validationRules=param.get('validationRules'),
                metadata=param.get('metadata'),
                sortOrder=param.get('sortOrder', 0)
            ))

        # Return type 변환
        rt = result.get('returnType', {})
        return_type = ReturnType(
            dataTypeId=rt.get('dataTypeId', ''),
            semanticTypeId=rt.get('semanticTypeId'),
            structTypeId=rt.get('structTypeId'),
            isArray=rt.get('isArray', False),
            isNullable=rt.get('isNullable', True),
            description=rt.get('description'),
            metadata=rt.get('metadata')
        )

        # Runtime config 변환
        rc = result.get('runtimeConfig', {})
        runtime_config = RuntimeConfig(
            runtime=FunctionRuntimeEnum(rc.get('runtime', 'python')),
            version=rc.get('version'),
            timeoutMs=rc.get('timeoutMs', 30000),
            memoryMb=rc.get('memoryMb', 512),
            cpuCores=rc.get('cpuCores', 1.0),
            maxRetries=rc.get('maxRetries', 3),
            retryDelayMs=rc.get('retryDelayMs', 1000),
            environmentVars=rc.get('environmentVars'),
            dependencies=rc.get('dependencies', []),
            resourceLimits=rc.get('resourceLimits')
        )

        # Behavior 변환
        bh = result.get('behavior', {})
        behavior = FunctionBehavior(
            isDeterministic=bh.get('isDeterministic', True),
            isStateless=bh.get('isStateless', True),
            isCacheable=bh.get('isCacheable', True),
            isParallelizable=bh.get('isParallelizable', True),
            hasSideEffects=bh.get('hasSideEffects', False),
            isExpensive=bh.get('isExpensive', False),
            cacheTtlSeconds=bh.get('cacheTtlSeconds')
        )

        # Examples 변환
        examples = []
        for ex in result.get('examples', []):
            examples.append(FunctionExample(
                name=ex.get('name', ''),
                description=ex.get('description'),
                inputValues=ex.get('inputValues', {}),
                expectedOutput=ex.get('expectedOutput'),
                explanation=ex.get('explanation')
            ))

        return FunctionType(
            id=result.get('id', ''),
            name=result.get('name', ''),
            displayName=result.get('displayName', ''),
            description=result.get('description'),
            category=FunctionCategoryEnum(result.get('category', 'custom')),
            parameters=parameters,
            returnType=return_type,
            runtimeConfig=runtime_config,
            behavior=behavior,
            implementationRef=result.get('implementationRef'),
            functionBody=result.get('functionBody'),
            examples=examples,
            tags=result.get('tags', []),
            isPublic=result.get('isPublic', True),
            allowedRoles=result.get('allowedRoles', []),
            allowedUsers=result.get('allowedUsers', []),
            metadata=result.get('metadata'),
            isSystem=result.get('isSystem', False),
            isDeprecated=result.get('isDeprecated', False),
            version=result.get('version', '1.0.0'),
            versionHash=result.get('versionHash', ''),
            previousVersionId=result.get('previousVersionId'),
            createdBy=result.get('createdBy', ''),
            createdAt=result.get('createdAt'),
            modifiedBy=result.get('modifiedBy', ''),
            modifiedAt=result.get('modifiedAt'),
            branchId=result.get('branchId'),
            isBranchSpecific=result.get('isBranchSpecific', False)
        )