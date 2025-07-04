"""Schema management routes"""

from typing import Dict, Any, List, Annotated
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Path, Body

from bootstrap.dependencies import get_schema_service
from core.interfaces import SchemaServiceProtocol
from middleware.auth_middleware import get_current_user
from database.dependencies import get_secure_database
from database.clients.secure_database_adapter import SecureDatabaseAdapter
from core.auth_utils import UserContext

router = APIRouter(prefix="/schemas", tags=["Schema Management"])

@router.get("/{branch}/object-types")
async def list_object_types(
    branch: str,
    schema_service: Annotated[SchemaServiceProtocol, Depends(get_schema_service)],
    current_user: Annotated[UserContext, Depends(get_current_user)]
) -> List[Dict[str, Any]]:
    """List all object types in a branch"""
    # For now, using main branch (will implement branch support later)
    result = await schema_service.list_schemas(
        filters={"branch": branch}
    )
    return result.get("schemas", [])

@router.post("/{branch}/object-types")
async def create_object_type(
    branch: str,
    object_type: Dict[str, Any],
    schema_service: Annotated[SchemaServiceProtocol, Depends(get_schema_service)],
    current_user: Annotated[UserContext, Depends(get_current_user)]
) -> Dict[str, Any]:
    """Create a new object type in a branch"""
    try:
        created_schema = await schema_service.create_schema(
            name=object_type.get("name", ""),
            schema_def=object_type,
            created_by=current_user
        )
        return {
            "message": "Object type created successfully",
            "object_type": created_schema,
            "created_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to create object type: {str(e)}"
        )