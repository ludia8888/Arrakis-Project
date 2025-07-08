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

router = APIRouter(
    prefix="/properties", 
    tags=["Property Management"]
)

@router.get(
    "/",
    dependencies=[Depends(require_scope([IAMScope.ONTOLOGIES_READ]))]
)
@inject
async def list_properties(
    request: Request,
    branch: Optional[str] = Query(None, description="Branch to filter properties"),
    object_type: Optional[str] = Query(None, description="Object type to filter properties"),
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of items to return"),
    current_user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
    """List all properties with optional filtering"""
    
    # TODO: Implement actual property listing from database
    sample_properties = [
        {
            "id": "prop-1",
            "name": "name",
            "type": "string",
            "object_type": "Person",
            "branch": "main",
            "required": True,
            "description": "The name of the person",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z"
        },
        {
            "id": "prop-2",
            "name": "age",
            "type": "integer",
            "object_type": "Person", 
            "branch": "main",
            "required": False,
            "description": "The age of the person",
            "min_value": 0,
            "max_value": 150,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z"
        },
        {
            "id": "prop-3",
            "name": "email",
            "type": "string",
            "object_type": "Person",
            "branch": "main",
            "required": True,
            "description": "Email address",
            "format": "email",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z"
        }
    ]
    
    # Apply filters
    filtered_properties = sample_properties
    if branch:
        filtered_properties = [p for p in filtered_properties if p.get("branch") == branch]
    if object_type:
        filtered_properties = [p for p in filtered_properties if p.get("object_type") == object_type]
    
    # Apply pagination
    total = len(filtered_properties)
    filtered_properties = filtered_properties[skip:skip + limit]
    
    return {
        "items": filtered_properties,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@router.get(
    "/{property_id}",
    dependencies=[Depends(require_scope([IAMScope.ONTOLOGIES_READ]))]
)
@inject
async def get_property(
    property_id: str,
    request: Request,
    current_user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get a specific property by ID"""
    
    # TODO: Implement actual property retrieval
    properties_db = {
        "prop-1": {
            "id": "prop-1",
            "name": "name",
            "type": "string",
            "object_type": "Person",
            "branch": "main",
            "required": True,
            "description": "The name of the person",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z"
        },
        "prop-2": {
            "id": "prop-2",
            "name": "age",
            "type": "integer",
            "object_type": "Person",
            "branch": "main",
            "required": False,
            "description": "The age of the person",
            "min_value": 0,
            "max_value": 150,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z"
        }
    }
    
    if property_id in properties_db:
        return properties_db[property_id]
    
    raise HTTPException(
        status_code=404,
        detail=f"Property '{property_id}' not found"
    )

@router.post(
    "/",
    dependencies=[Depends(require_scope([IAMScope.ONTOLOGIES_WRITE]))]
)
@inject
async def create_property(
    property_def: Dict[str, Any],
    request: Request,
    current_user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
    """Create a new property"""
    
    # Input validation
    required_fields = ["name", "type", "object_type"]
    for field in required_fields:
        if not property_def.get(field):
            raise HTTPException(
                status_code=400,
                detail=f"Property {field} is required"
            )
    
    # Validate property type
    valid_types = ["string", "integer", "number", "boolean", "date", "datetime", "object", "array"]
    if property_def.get("type") not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid property type. Must be one of: {', '.join(valid_types)}"
        )
    
    # TODO: Implement actual property creation
    created_property = {
        "id": f"prop-{datetime.utcnow().timestamp()}",
        "name": property_def.get("name"),
        "type": property_def.get("type"),
        "object_type": property_def.get("object_type"),
        "branch": property_def.get("branch", "main"),
        "required": property_def.get("required", False),
        "description": property_def.get("description", ""),
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "created_by": current_user.user_id
    }
    
    # Add type-specific attributes
    if property_def.get("type") in ["integer", "number"]:
        if "min_value" in property_def:
            created_property["min_value"] = property_def["min_value"]
        if "max_value" in property_def:
            created_property["max_value"] = property_def["max_value"]
    elif property_def.get("type") == "string":
        if "format" in property_def:
            created_property["format"] = property_def["format"]
        if "pattern" in property_def:
            created_property["pattern"] = property_def["pattern"]
        if "min_length" in property_def:
            created_property["min_length"] = property_def["min_length"]
        if "max_length" in property_def:
            created_property["max_length"] = property_def["max_length"]
    
    return {
        "message": "Property created successfully",
        "property": created_property
    }

@router.put(
    "/{property_id}",
    dependencies=[Depends(require_scope([IAMScope.ONTOLOGIES_WRITE]))]
)
@inject
async def update_property(
    property_id: str,
    property_def: Dict[str, Any],
    request: Request,
    current_user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
    """Update a property"""
    
    # TODO: Implement actual property update
    if property_id not in ["prop-1", "prop-2"]:
        raise HTTPException(
            status_code=404,
            detail=f"Property '{property_id}' not found"
        )
    
    updated_property = {
        "id": property_id,
        "name": property_def.get("name", "name"),
        "type": property_def.get("type", "string"),
        "object_type": property_def.get("object_type", "Person"),
        "branch": property_def.get("branch", "main"),
        "required": property_def.get("required", False),
        "description": property_def.get("description", ""),
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": datetime.utcnow().isoformat(),
        "updated_by": current_user.user_id
    }
    
    return {
        "message": "Property updated successfully",
        "property": updated_property
    }

@router.delete(
    "/{property_id}",
    dependencies=[Depends(require_scope([IAMScope.ONTOLOGIES_WRITE]))]
)
@inject
async def delete_property(
    property_id: str,
    request: Request,
    current_user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
    """Delete a property"""
    
    # TODO: Implement actual property deletion
    if property_id not in ["prop-1", "prop-2", "prop-3"]:
        raise HTTPException(
            status_code=404,
            detail=f"Property '{property_id}' not found"
        )
    
    return {
        "message": "Property deleted successfully",
        "deleted_id": property_id
    }

@router.post(
    "/validate",
    dependencies=[Depends(require_scope([IAMScope.ONTOLOGIES_READ]))]
)
@inject
async def validate_property(
    property_def: Dict[str, Any],
    request: Request,
    current_user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
    """Validate a property definition without creating it"""
    
    errors = []
    warnings = []
    
    # Check required fields
    required_fields = ["name", "type", "object_type"]
    for field in required_fields:
        if not property_def.get(field):
            errors.append(f"Property {field} is required")
    
    # Validate property type
    valid_types = ["string", "integer", "number", "boolean", "date", "datetime", "object", "array"]
    if property_def.get("type") and property_def.get("type") not in valid_types:
        errors.append(f"Invalid property type. Must be one of: {', '.join(valid_types)}")
    
    # Type-specific validations
    if property_def.get("type") in ["integer", "number"]:
        if "min_value" in property_def and "max_value" in property_def:
            if property_def["min_value"] > property_def["max_value"]:
                errors.append("min_value cannot be greater than max_value")
    
    # Check property name format
    if property_def.get("name"):
        import re
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', property_def["name"]):
            errors.append("Property name must start with a letter and contain only letters, numbers, and underscores")
    
    # Warnings
    if not property_def.get("description"):
        warnings.append("Property has no description")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }