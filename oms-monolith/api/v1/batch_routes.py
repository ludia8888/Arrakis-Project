"""
Batch API Routes for GraphQL DataLoader Support
Provides efficient batch loading endpoints to prevent N+1 queries
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
import asyncio
from datetime import datetime, timezone

from core.auth import UserContext
from middleware.auth_secure import get_current_user
from core.schema.service import SchemaService
from core.branch import get_branch_service, IBranchService
from database.clients.terminus_db import TerminusDBClient
from utils.logger import get_logger
from shared.cache.smart_cache import SmartCacheManager
from shared.exceptions import NotFoundError, ValidationError, ServiceException
from shared.exceptions.domain_exceptions import SchemaException, SchemaValidationError

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/batch", tags=["Batch Operations"])


# Request/Response Models
class BatchRequest(BaseModel):
    """Base batch request model"""
    ids: List[str] = Field(..., description="List of IDs to batch load")
    options: Optional[Dict[str, Any]] = Field(None, description="Additional options")


class BatchObjectTypesRequest(BatchRequest):
    """Request for batch loading object types"""
    include_properties: bool = Field(False, description="Include properties in response")
    include_links: bool = Field(False, description="Include link types in response")


class BatchPropertiesRequest(BaseModel):
    """Request for batch loading properties by object type IDs"""
    object_type_ids: List[str] = Field(..., description="Object type IDs to load properties for")
    include_metadata: bool = Field(False, description="Include property metadata")


class BatchLinkTypesRequest(BatchRequest):
    """Request for batch loading link types"""
    include_endpoints: bool = Field(False, description="Include source/target object types")


class BatchBranchesRequest(BatchRequest):
    """Request for batch loading branches"""
    include_state: bool = Field(False, description="Include branch state information")


# Dependency injection for services
async def get_schema_service() -> SchemaService:
    """Get schema service instance"""
    from shared.config.environment import get_config
    config = get_config()
    
    db_client = TerminusDBClient(
        endpoint=config.get_terminus_db_url(),
        username=config.get("TERMINUS_USERNAME", "admin"), 
        password=config.get("TERMINUS_PASSWORD", "root")
    )
    
    service = SchemaService(
        tdb_endpoint=config.get_terminus_db_url(),
        event_publisher=None  # We don't need events for batch reads
    )
    await service.initialize()
    return service


async def get_branch_service_instance() -> IBranchService:
    """Get branch service instance"""
    # In production, this would come from the service container
    return get_branch_service()


# Schema Batch Endpoints
@router.post("/object-types", response_model=Dict[str, Any])
async def batch_get_object_types(
    request: BatchObjectTypesRequest,
    current_user: UserContext = Depends(get_current_user),
    schema_service: SchemaService = Depends(get_schema_service)
):
    """
    Batch load multiple object types by IDs.
    Optimized for GraphQL DataLoader to prevent N+1 queries.
    """
    try:
        logger.info(f"Batch loading {len(request.ids)} object types for user {current_user.user_id}")
        
        # Parallel load all object types
        tasks = []
        for object_id in request.ids:
            # Extract branch from ID format: branch:type_name
            parts = object_id.split(":", 1)
            if len(parts) == 2:
                branch, type_name = parts
                tasks.append(schema_service.get_object_type(branch, type_name))
            else:
                # Invalid ID format, append None
                tasks.append(asyncio.create_task(asyncio.sleep(0)))
        
        # Execute all tasks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Build response mapping IDs to results
        data = {}
        for idx, (object_id, result) in enumerate(zip(request.ids, results)):
            if isinstance(result, Exception):
                logger.warning(f"Failed to load object type {object_id}: {result}")
                data[object_id] = None
            elif result is None:
                data[object_id] = None
            else:
                # Convert result to dict if needed
                obj_data = result.model_dump() if hasattr(result, 'model_dump') else result
                
                # Optionally include related data
                if request.include_properties and isinstance(obj_data, dict):
                    obj_data['properties'] = []  # Would load properties here
                if request.include_links and isinstance(obj_data, dict):
                    obj_data['link_types'] = []  # Would load links here
                    
                data[object_id] = obj_data
        
        return {
            "data": data,
            "count": len(data),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except ValidationError as e:
        logger.warning(f"Batch validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: {str(e)}"
        )
    except NotFoundError as e:
        logger.warning(f"Resource not found in batch operation: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except SchemaException as e:
        logger.error(f"Schema error in batch operation: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Schema error: {str(e)}"
        )
    except ServiceException as e:
        logger.error(f"Service error in batch operation: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service temporarily unavailable: {str(e)}"
        )
    except ConnectionError as e:
        logger.error(f"Database connection error in batch object types loading: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service temporarily unavailable"
        )
    except TimeoutError as e:
        logger.error(f"Timeout error in batch object types loading: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Request timeout while loading object types"
        )
    except KeyError as e:
        logger.error(f"Missing required field in batch request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required field: {str(e)}"
        )
    except RuntimeError as e:
        logger.error(f"Unexpected error in batch object types loading: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal server error occurred"
        )


@router.post("/properties", response_model=Dict[str, Any])
async def batch_get_properties(
    request: BatchPropertiesRequest,
    current_user: UserContext = Depends(get_current_user),
    schema_service: SchemaService = Depends(get_schema_service)
):
    """
    Batch load properties for multiple object types.
    Returns a mapping of object_type_id -> list of properties.
    """
    try:
        logger.info(f"Batch loading properties for {len(request.object_type_ids)} object types")
        
        # Parallel load properties for all object types
        tasks = []
        for object_type_id in request.object_type_ids:
            # Extract branch and type name
            parts = object_type_id.split(":", 1)
            if len(parts) == 2:
                branch, type_name = parts
                tasks.append(schema_service.list_properties(branch, type_name))
            else:
                tasks.append(asyncio.create_task(asyncio.sleep(0)))
        
        # Execute all tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Build response
        data = {}
        for object_type_id, result in zip(request.object_type_ids, results):
            if isinstance(result, Exception):
                logger.warning(f"Failed to load properties for {object_type_id}: {result}")
                data[object_type_id] = []
            elif result is None:
                data[object_type_id] = []
            else:
                # Convert properties to list of dicts
                properties = []
                if isinstance(result, list):
                    for prop in result:
                        prop_data = prop.model_dump() if hasattr(prop, 'model_dump') else prop
                        if request.include_metadata and isinstance(prop_data, dict):
                            # Add metadata if requested
                            prop_data['metadata'] = {
                                'created_at': datetime.now(timezone.utc).isoformat(),
                                'indexed': False,
                                'required': False
                            }
                        properties.append(prop_data)
                data[object_type_id] = properties
        
        return {
            "data": data,
            "count": sum(len(props) for props in data.values()),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except ConnectionError as e:
        logger.error(f"Database connection error in batch properties loading: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service temporarily unavailable"
        )
    except TimeoutError as e:
        logger.error(f"Timeout error in batch properties loading: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Request timeout while loading properties"
        )
    except KeyError as e:
        logger.error(f"Missing required field in properties request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required field: {str(e)}"
        )
    except RuntimeError as e:
        logger.error(f"Unexpected error in batch properties loading: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to batch load properties"
        )


@router.post("/link-types", response_model=Dict[str, Any])
async def batch_get_link_types(
    request: BatchLinkTypesRequest,
    current_user: UserContext = Depends(get_current_user),
    schema_service: SchemaService = Depends(get_schema_service)
):
    """
    Batch load multiple link types by IDs.
    """
    try:
        logger.info(f"Batch loading {len(request.ids)} link types")
        
        # Parallel load all link types
        tasks = []
        for link_id in request.ids:
            # Extract branch and link name
            parts = link_id.split(":", 1)
            if len(parts) == 2:
                branch, link_name = parts
                tasks.append(schema_service.get_link_type(branch, link_name))
            else:
                tasks.append(asyncio.create_task(asyncio.sleep(0)))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Build response
        data = {}
        for link_id, result in zip(request.ids, results):
            if isinstance(result, Exception):
                logger.warning(f"Failed to load link type {link_id}: {result}")
                data[link_id] = None
            elif result is None:
                data[link_id] = None
            else:
                link_data = result.model_dump() if hasattr(result, 'model_dump') else result
                
                if request.include_endpoints and isinstance(link_data, dict):
                    # Add source/target object type info
                    link_data['source_object_type'] = None  # Would load here
                    link_data['target_object_type'] = None  # Would load here
                    
                data[link_id] = link_data
        
        return {
            "data": data,
            "count": len(data),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except ConnectionError as e:
        logger.error(f"Database connection error in batch link types loading: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service temporarily unavailable"
        )
    except TimeoutError as e:
        logger.error(f"Timeout error in batch link types loading: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Request timeout while loading link types"
        )
    except KeyError as e:
        logger.error(f"Missing required field in link types request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required field: {str(e)}"
        )
    except RuntimeError as e:
        logger.error(f"Unexpected error in batch link types loading: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to batch load link types"
        )


# Branch Batch Endpoints
@router.post("/branches", response_model=Dict[str, Any])
async def batch_get_branches(
    request: BatchBranchesRequest,
    current_user: UserContext = Depends(get_current_user),
    branch_service: IBranchService = Depends(get_branch_service_instance)
):
    """
    Batch load multiple branches by IDs.
    """
    try:
        logger.info(f"Batch loading {len(request.ids)} branches")
        
        # For now, return mock data since IBranchService isn't fully implemented
        # In production, this would call actual branch service methods
        data = {}
        for branch_id in request.ids:
            data[branch_id] = {
                "id": branch_id,
                "name": branch_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": "system",
                "parent_branch": "main" if branch_id != "main" else None,
                "is_locked": False
            }
            
            if request.include_state:
                data[branch_id]["state"] = {
                    "commit_hash": "abc123",
                    "last_modified": datetime.now(timezone.utc).isoformat(),
                    "object_count": 42,
                    "is_dirty": False
                }
        
        return {
            "data": data,
            "count": len(data),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except ConnectionError as e:
        logger.error(f"Service connection error in batch branches loading: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Branch service temporarily unavailable"
        )
    except TimeoutError as e:
        logger.error(f"Timeout error in batch branches loading: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Request timeout while loading branches"
        )
    except RuntimeError as e:
        logger.error(f"Unexpected error in batch branches loading: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to batch load branches"
        )


@router.post("/branch-states", response_model=Dict[str, Any])
async def batch_get_branch_states(
    request: BatchRequest,
    current_user: UserContext = Depends(get_current_user),
    branch_service: IBranchService = Depends(get_branch_service_instance)
):
    """
    Batch load branch states for multiple branches.
    """
    try:
        logger.info(f"Batch loading states for {len(request.ids)} branches")
        
        # Mock implementation
        data = {}
        for branch_id in request.ids:
            data[branch_id] = {
                "branch_id": branch_id,
                "commit_hash": f"hash_{branch_id}_123",
                "last_modified": datetime.now(timezone.utc).isoformat(),
                "object_count": 42,
                "property_count": 128,
                "link_count": 64,
                "is_dirty": False,
                "locked_by": None,
                "lock_expires_at": None
            }
        
        return {
            "data": data,
            "count": len(data),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except ConnectionError as e:
        logger.error(f"Service connection error in batch branch states loading: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Branch service temporarily unavailable"
        )
    except TimeoutError as e:
        logger.error(f"Timeout error in batch branch states loading: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Request timeout while loading branch states"
        )
    except RuntimeError as e:
        logger.error(f"Unexpected error in batch branch states loading: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to batch load branch states"
        )


# Performance monitoring endpoint
@router.get("/metrics", response_model=Dict[str, Any])
async def get_batch_metrics(
    current_user: UserContext = Depends(get_current_user)
):
    """
    Get performance metrics for batch operations.
    Useful for monitoring DataLoader efficiency.
    """
    # In production, this would return real metrics from monitoring system
    return {
        "batch_operations": {
            "total_requests": 1234,
            "avg_batch_size": 25.5,
            "max_batch_size": 100,
            "avg_response_time_ms": 45.2,
            "cache_hit_rate": 0.75
        },
        "by_endpoint": {
            "/batch/object-types": {
                "requests": 456,
                "avg_batch_size": 30,
                "avg_response_time_ms": 50.1
            },
            "/batch/properties": {
                "requests": 778,
                "avg_batch_size": 20,
                "avg_response_time_ms": 40.3
            }
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }