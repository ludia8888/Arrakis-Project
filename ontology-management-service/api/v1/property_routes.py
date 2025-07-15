"""Property management routes"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query, Path, Body, Request
from dependency_injector.wiring import inject, Provide

from bootstrap.dependencies import Container
from middleware.auth_middleware import get_current_user
from core.auth_utils import UserContext
from middleware.etag_middleware import enable_etag
from core.iam.dependencies import require_scope
from core.iam.iam_integration import IAMScope
from core.interfaces.property import PropertyServiceProtocol
from models.domain import PropertyCreate, PropertyUpdate
from models.exceptions import ResourceNotFoundError, ValidationError
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
 prefix = "/properties",
 tags = ["Property Management"]
)

@router.get(
 "/",
 dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_READ]))]
)
@inject
async def list_properties(
 request: Request,
 branch: Optional[str] = Query("main", description = "Branch to filter properties"),
 object_type: Optional[str] = Query(None, description = "Object type to filter properties"),
 skip: int = Query(0, ge = 0, description = "Number of items to skip"),
 limit: int = Query(100, ge = 1, le = 1000, description = "Number of items to return"),
 current_user: UserContext = Depends(get_current_user),
 property_service: PropertyServiceProtocol = Depends(Provide[Container.property_service])
) -> Dict[str, Any]:
 """List all properties with optional filtering"""

 try:
 properties = await property_service.list_properties(
 branch = branch,
 object_type = object_type,
 skip = skip,
 limit = limit
 )

 # Convert to dict for response
 items = [prop.dict() for prop in properties]

 return {
 "items": items,
 "total": len(items), # Note: This should ideally come from a count query
 "skip": skip,
 "limit": limit
 }
 except Exception as e:
 logger.error(f"Failed to list properties: {str(e)}")
 raise HTTPException(status_code = 500, detail = "Failed to list properties")

@router.get(
 "/{property_id}",
 dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_READ]))]
)
@inject
async def get_property(
 property_id: str,
 request: Request,
 branch: str = Query("main", description = "Branch name"),
 current_user: UserContext = Depends(get_current_user),
 property_service: PropertyServiceProtocol = Depends(Provide[Container.property_service])
) -> Dict[str, Any]:
 """Get a specific property by ID"""

 try:
 property = await property_service.get_property(
 branch = branch,
 property_id = property_id
 )

 if not property:
 raise HTTPException(
 status_code = 404,
 detail = f"Property '{property_id}' not found"
 )

 return property.dict()
 except HTTPException:
 raise
 except Exception as e:
 logger.error(f"Failed to get property {property_id}: {str(e)}")
 raise HTTPException(status_code = 500, detail = "Failed to retrieve property")

@router.post(
 "/",
 dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_WRITE]))]
)
@inject
async def create_property(
 property_data: PropertyCreate,
 request: Request,
 branch: str = Query("main", description = "Branch name"),
 current_user: UserContext = Depends(get_current_user),
 property_service: PropertyServiceProtocol = Depends(Provide[Container.property_service])
) -> Dict[str, Any]:
 """Create a new property"""

 try:
 # Map type to data_type_id if needed
 if hasattr(property_data, 'type') and not property_data.data_type_id:
 property_data.data_type_id = f"DataType/{property_data.type}"

 created_property = await property_service.create_property(
 branch = branch,
 property_data = property_data,
 created_by = current_user.user_id
 )

 return {
 "message": "Property created successfully",
 "property": created_property.dict()
 }
 except ValidationError as e:
 raise HTTPException(status_code = 400, detail = str(e))
 except Exception as e:
 logger.error(f"Failed to create property: {str(e)}")
 raise HTTPException(status_code = 500, detail = "Failed to create property")

@router.put(
 "/{property_id}",
 dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_WRITE]))]
)
@inject
async def update_property(
 property_id: str,
 property_data: PropertyUpdate,
 request: Request,
 branch: str = Query("main", description = "Branch name"),
 current_user: UserContext = Depends(get_current_user),
 property_service: PropertyServiceProtocol = Depends(Provide[Container.property_service])
) -> Dict[str, Any]:
 """Update a property"""

 try:
 updated_property = await property_service.update_property(
 branch = branch,
 property_id = property_id,
 property_data = property_data,
 updated_by = current_user.user_id
 )

 return {
 "message": "Property updated successfully",
 "property": updated_property.dict()
 }
 except NotFoundException as e:
 raise HTTPException(status_code = 404, detail = str(e))
 except ValidationError as e:
 raise HTTPException(status_code = 400, detail = str(e))
 except Exception as e:
 logger.error(f"Failed to update property {property_id}: {str(e)}")
 raise HTTPException(status_code = 500, detail = "Failed to update property")

@router.delete(
 "/{property_id}",
 dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_WRITE]))]
)
@inject
async def delete_property(
 property_id: str,
 request: Request,
 branch: str = Query("main", description = "Branch name"),
 current_user: UserContext = Depends(get_current_user),
 property_service: PropertyServiceProtocol = Depends(Provide[Container.property_service])
) -> Dict[str, Any]:
 """Delete a property"""

 try:
 success = await property_service.delete_property(
 branch = branch,
 property_id = property_id,
 deleted_by = current_user.user_id
 )

 if success:
 return {
 "message": "Property deleted successfully",
 "deleted_id": property_id
 }
 else:
 raise HTTPException(status_code = 500, detail = "Failed to delete property")
 except NotFoundException as e:
 raise HTTPException(status_code = 404, detail = str(e))
 except Exception as e:
 logger.error(f"Failed to delete property {property_id}: {str(e)}")
 raise HTTPException(status_code = 500, detail = "Failed to delete property")

@router.post(
 "/validate",
 dependencies = [Depends(require_scope([IAMScope.ONTOLOGIES_READ]))]
)
@inject
async def validate_property(
 property_def: Dict[str, Any],
 request: Request,
 current_user: UserContext = Depends(get_current_user),
 property_service: PropertyServiceProtocol = Depends(Provide[Container.property_service])
) -> Dict[str, Any]:
 """Validate a property definition without creating it"""

 try:
 validation_result = await property_service.validate_property(property_def)
 return validation_result
 except Exception as e:
 logger.error(f"Failed to validate property: {str(e)}")
 raise HTTPException(status_code = 500, detail = "Failed to validate property")
