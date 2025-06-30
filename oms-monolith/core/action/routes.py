"""
OMS Action Metadata API Routes
ActionType 메타데이터 관리만 담당
"""
from fastapi import APIRouter, HTTPException, Depends, Request, Response
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
import hashlib
import json

from core.action.metadata_service import ActionMetadataService
from .models import ActionTypeModel
from core.auth import UserContext
from middleware.auth_secure import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/action-types", tags=["action-types"])


class CreateActionTypeRequest(BaseModel):
    """ActionType 생성 요청"""
    name: str
    displayName: Optional[str] = None
    description: Optional[str] = None
    objectTypeId: str
    inputSchema: Dict[str, Any] = {}
    validationExpression: Optional[str] = None
    webhookUrl: Optional[str] = None
    isBatchable: bool = True
    isAsync: bool = False
    requiresApproval: bool = False
    approvalRoles: List[str] = []
    maxRetries: int = 3
    timeoutSeconds: int = 300
    implementation: str = "webhook"


class UpdateActionTypeRequest(BaseModel):
    """ActionType 업데이트 요청"""
    name: Optional[str] = None
    displayName: Optional[str] = None
    description: Optional[str] = None
    inputSchema: Optional[Dict[str, Any]] = None
    validationExpression: Optional[str] = None
    webhookUrl: Optional[str] = None
    isBatchable: Optional[bool] = None
    isAsync: Optional[bool] = None
    requiresApproval: Optional[bool] = None
    approvalRoles: Optional[List[str]] = None
    maxRetries: Optional[int] = None
    timeoutSeconds: Optional[int] = None
    status: Optional[str] = None


class ValidateActionInputRequest(BaseModel):
    """액션 입력 검증 요청"""
    parameters: Dict[str, Any]


# Action Metadata Service 인스턴스
action_metadata_service = ActionMetadataService()


def generate_etag(data: Any) -> str:
    """Generate ETag for response data"""
    data_str = json.dumps(data, sort_keys=True, default=str)
    return hashlib.md5(data_str.encode()).hexdigest()


def check_etag_match(request: Request, etag: str) -> bool:
    """Check if request ETag matches current ETag"""
    if_none_match = request.headers.get("If-None-Match")
    return if_none_match == etag if if_none_match else False


@router.post("", response_model=ActionTypeModel)
async def create_action_type(
    request: CreateActionTypeRequest,
    user: UserContext = Depends(get_current_user)
):
    """
    ActionType 정의 생성
    
    OMS의 핵심 기능: 액션 메타데이터 정의
    Requires: action:write scope
    """
    # Check user permissions
    if not user.has_scope("action:write"):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Requires 'action:write' scope"
        )
    
    try:
        # Add user context to the request
        request_data = request.model_dump()
        request_data["createdBy"] = user.user_id
        request_data["modifiedBy"] = user.user_id
        
        action_type = await action_metadata_service.create_action_type(request_data)
        return action_type
        
    except ValueError as e:
        logger.error(f"Invalid ActionType data: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except (RuntimeError, TypeError) as e:
        logger.error(f"Failed to create ActionType: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{action_type_id}", response_model=ActionTypeModel)
async def get_action_type(
    action_type_id: str,
    request: Request,
    response: Response,
    user: UserContext = Depends(get_current_user)
):
    """
    ActionType 조회
    
    Actions Service에서 메타데이터 조회 시 사용
    Requires: action:read scope
    """
    # Check user permissions
    if not user.has_scope("action:read"):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Requires 'action:read' scope"
        )
    
    try:
        action_type = await action_metadata_service.get_action_type(action_type_id)
        
        if not action_type:
            raise HTTPException(status_code=404, detail="ActionType not found")
        
        # Generate ETag for the response
        etag = generate_etag(action_type)
        
        # Check if client has matching ETag
        if check_etag_match(request, etag):
            response.status_code = 304
            response.headers["ETag"] = etag
            return Response(status_code=304)
        
        # Set ETag header for fresh response
        response.headers["ETag"] = etag
        return action_type
        
    except HTTPException:
        raise
    except ConnectionError as e:
        logger.error(f"Database connection error: {e}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
    except (ValueError, RuntimeError) as e:
        logger.error(f"Failed to get ActionType: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{action_type_id}", response_model=ActionTypeModel)
async def update_action_type(
    action_type_id: str, 
    request: UpdateActionTypeRequest,
    user: UserContext = Depends(get_current_user)
):
    """
    ActionType 업데이트
    Requires: action:write scope
    """
    # Check user permissions
    if not user.has_scope("action:write"):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Requires 'action:write' scope"
        )
    
    try:
        # None이 아닌 필드만 업데이트
        updates = {k: v for k, v in request.model_dump().items() if v is not None}
        updates["modifiedBy"] = user.user_id  # Track who modified it
        
        action_type = await action_metadata_service.update_action_type(
            action_type_id, updates
        )
        return action_type
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConnectionError as e:
        logger.error(f"Database connection error: {e}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
    except (RuntimeError, TypeError) as e:
        logger.error(f"Failed to update ActionType: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{action_type_id}")
async def delete_action_type(
    action_type_id: str,
    user: UserContext = Depends(get_current_user)
):
    """
    ActionType 삭제
    Requires: action:delete scope
    """
    # Check user permissions
    if not user.has_scope("action:delete"):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Requires 'action:delete' scope"
        )
    
    try:
        success = await action_metadata_service.delete_action_type(action_type_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="ActionType not found")
        
        return {"message": "ActionType deleted successfully"}
        
    except HTTPException:
        raise
    except ConnectionError as e:
        logger.error(f"Database connection error: {e}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
    except (RuntimeError, TypeError) as e:
        logger.error(f"Failed to delete ActionType: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("", response_model=List[ActionTypeModel])
async def list_action_types(
    object_type_id: Optional[str] = None,
    status: Optional[str] = None,
    user: UserContext = Depends(get_current_user)
):
    """
    ActionType 목록 조회
    Requires: action:read scope
    """
    # Check user permissions
    if not user.has_scope("action:read"):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Requires 'action:read' scope"
        )
    
    try:
        action_types = await action_metadata_service.list_action_types(
            object_type_id=object_type_id,
            status=status
        )
        return action_types
        
    except ConnectionError as e:
        logger.error(f"Database connection error: {e}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
    except (RuntimeError, TypeError) as e:
        logger.error(f"Failed to list ActionTypes: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{action_type_id}/validate")
async def validate_action_input(
    action_type_id: str, 
    request: ValidateActionInputRequest,
    user: UserContext = Depends(get_current_user)
):
    """
    액션 입력 검증
    
    Actions Service에서 실행 전 검증 시 사용
    Requires: action:read scope
    """
    # Check user permissions
    if not user.has_scope("action:read"):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Requires 'action:read' scope"
        )
    
    try:
        validation_result = await action_metadata_service.validate_action_input(
            action_type_id, request.parameters
        )
        return validation_result
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except (RuntimeError, TypeError) as e:
        logger.error(f"Failed to validate action input: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/by-object/{object_type_id}", response_model=List[ActionTypeModel])
async def get_actions_for_object_type(
    object_type_id: str,
    user: UserContext = Depends(get_current_user)
):
    """
    특정 ObjectType에 대한 액션 목록 조회
    
    Workshop UI에서 사용 가능한 액션 표시 시 사용
    Requires: action:read scope
    """
    # Check user permissions
    if not user.has_scope("action:read"):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Requires 'action:read' scope"
        )
    
    try:
        action_types = await action_metadata_service.list_action_types(
            object_type_id=object_type_id,
            status="active"
        )
        return action_types
        
    except ConnectionError as e:
        logger.error(f"Database connection error: {e}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
    except (RuntimeError, TypeError) as e:
        logger.error(f"Failed to get actions for object type: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")