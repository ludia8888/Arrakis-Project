"""Schema management routes"""

from datetime import datetime
from typing import Annotated, Any, Dict, List

from arrakis_common import get_logger
from bootstrap.dependencies import Container
from core.auth_utils import UserContext
from core.iam.dependencies import require_scope
from core.iam.iam_integration import IAMScope
from core.interfaces import SchemaServiceProtocol
from database.clients.secure_database_adapter import SecureDatabaseAdapter
from database.dependencies import get_secure_database
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Body, Depends, HTTPException, Path, Request
from middleware.auth_middleware import get_current_user
from middleware.circuit_breaker_http import http_circuit_breaker
from middleware.etag_middleware import enable_etag

logger = get_logger(__name__)

router = APIRouter(prefix="/schemas", tags=["Schema Management"])


@router.get(
    "/{branch}/object-types",
    dependencies=[Depends(require_scope([IAMScope.ONTOLOGIES_READ]))],
)
@inject
@enable_etag(
    resource_type_func=lambda params: "object_types_collection",
    resource_id_func=lambda params: f"{params['branch']}_object_types",
    branch_func=lambda params: params["branch"],
)
async def list_object_types(
    branch: str,
    request: Request,
    schema_service: SchemaServiceProtocol = Depends(
        Provide[Container.schema_service_provider]
    ),
    current_user: UserContext = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """List all object types in a branch"""
    result = await schema_service.list_schemas(
        filters={"branch": branch, "type": "object"}
    )
    return result.get("items", [])


@router.get(
    "/{branch}/object-types/{type_name}",
    dependencies=[Depends(require_scope([IAMScope.ONTOLOGIES_READ]))],
)
@inject
@http_circuit_breaker(
    name="schema_route_get_object_type",
    failure_threshold=5,  # 라우트 레벨에서는 더 민감하게 설정
    timeout_seconds=30,
    error_status_codes={404, 500, 502, 503, 504},
)
@enable_etag(
    resource_type_func=lambda params: "object_type",
    resource_id_func=lambda params: params["type_name"],
    branch_func=lambda params: params["branch"],
)
async def get_object_type(
    branch: str,
    type_name: str,
    request: Request,
    schema_service: SchemaServiceProtocol = Depends(
        Provide[Container.schema_service_provider]
    ),
    current_user: UserContext = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get a specific object type by name."""
    schema = await schema_service.get_schema_by_name(name=type_name, branch=branch)
    if not schema:
        raise HTTPException(
            status_code=404,
            detail=f"Object type '{type_name}' not found in branch '{branch}'",
        )
    return schema


@router.post(
    "/{branch}/object-types",
    dependencies=[Depends(require_scope([IAMScope.ONTOLOGIES_WRITE]))],
)
@inject
async def create_object_type(
    branch: str,
    object_type: Dict[str, Any],
    request: Request,
    schema_service: SchemaServiceProtocol = Depends(
        Provide[Container.schema_service_provider]
    ),
    current_user: UserContext = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create a new object type in a branch"""

    # 입력 데이터 검증
    if not object_type.get("name"):
        raise HTTPException(status_code=400, detail="Object type name is required")

    try:
        # 스키마 유효성 검증
        validation_result = await schema_service.validate_schema(object_type)
        if not validation_result.get("valid"):
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Schema validation failed",
                    "errors": validation_result.get("errors", []),
                    "warnings": validation_result.get("warnings", []),
                },
            )

        # 스키마 생성
        created_schema = await schema_service.create_schema(
            name=object_type.get("name", ""),
            schema_def={**object_type, "branch": branch},
            created_by=current_user.user_id,
        )

        return {
            "message": "Object type created successfully",
            "object_type": created_schema,
            "created_at": datetime.utcnow().isoformat(),
        }

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback

        error_detail = f"Failed to create object type: {str(e)}"
        tb = traceback.format_exc()
        logger.error(f"ERROR in create_object_type: {error_detail}")
        logger.error(f"Traceback:\n{tb}")
        raise HTTPException(status_code=500, detail=error_detail)
