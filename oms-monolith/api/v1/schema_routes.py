"""
Schema Management API Routes
Implements all schema type endpoints for OMS
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Body
from pydantic import BaseModel, Field, validator
import re
import logging

from core.auth import UserContext
from middleware.auth_secure import get_current_user
from core.schema.service import SchemaService
from core.schema.extended_service import ExtendedSchemaService
from core.validation.input_sanitization import (
    get_secure_processor, SanitizationLevel, get_input_sanitizer
)
from models.domain import (
    ObjectType, ObjectTypeCreate, ObjectTypeUpdate,
    Property, PropertyCreate, PropertyUpdate,
    Status
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/schemas",
    tags=["schemas"]
)

def validate_branch_name(branch: str) -> str:
    """
    Branch name validation with multi-layer security
    """
    # Layer 1: Input sanitization with PARANOID level
    sanitizer = get_input_sanitizer()
    result = sanitizer.sanitize(branch, SanitizationLevel.PARANOID)
    
    if not result.is_safe:
        logger.warning(f"Branch validation failed: {branch} - threats: {result.detected_threats}")
        raise HTTPException(status_code=400, detail="Invalid branch name")
    
    # Layer 2: Branch-specific pattern validation
    if not re.match(r'^[a-zA-Z0-9_-]+$', result.sanitized_value):
        logger.warning(f"Invalid branch format: {branch}")
        raise HTTPException(status_code=400, detail="Invalid branch format")
    
    # Layer 3: Length validation
    if len(result.sanitized_value) > 50:
        logger.warning(f"Branch name too long: {len(result.sanitized_value)} chars")
        raise HTTPException(status_code=400, detail="Attack blocked")
    
    return branch

def validate_all_inputs(**inputs) -> None:
    """Validate all inputs using multi-layer security approach"""
    sanitizer = get_input_sanitizer()
    
    for name, value in inputs.items():
        if value is not None and isinstance(value, str):
            result = sanitizer.sanitize(value, SanitizationLevel.PARANOID)
            if not result.is_safe:
                logger.warning(f"Input validation failed for {name}: threats={result.detected_threats}")
                raise HTTPException(status_code=400, detail=f"Invalid input: {name}")

# ==================== Object Types ====================

@router.get("/{branch}/object-types", response_model=Dict[str, Any])
async def list_object_types(
    branch: str,
    status: Optional[Status] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search in name/displayName"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user: UserContext = Depends(get_current_user),
    request: Request = None
):
    """List all object types with comprehensive security validation"""
    # Multi-layer input validation
    validate_all_inputs(
        branch=branch,
        status=status.value if status else None,
        search=search,
        limit=str(limit),
        offset=str(offset)
    )
    
    # Additional branch validation
    validate_branch_name(branch)
    
    # 서비스 접근 방식 통일
    if hasattr(request.app.state, 'services'):
        schema_service: SchemaService = request.app.state.services.schema_service
    else:
        raise HTTPException(status_code=503, detail="Service container not initialized")
    
    result = await schema_service.list_object_types(branch=branch)
    
    # Apply filters
    filtered = result
    if status:
        filtered = [ot for ot in filtered if ot.get('status') == status.value]
    if search:
        search_lower = search.lower()
        filtered = [
            ot for ot in filtered 
            if search_lower in ot.get('name', '').lower() 
            or search_lower in ot.get('displayName', '').lower()
        ]
    
    # Apply pagination
    total = len(filtered)
    paginated = filtered[offset:offset + limit]
    
    return {
        "objectTypes": paginated,
        "total": total,
        "limit": limit,
        "offset": offset,
        "branch": branch
    }

@router.post("/{branch}/object-types", response_model=Dict[str, Any])
async def create_object_type(
    branch: str,
    data: ObjectTypeCreate,
    user: UserContext = Depends(get_current_user),
    request: Request = None
):
    """ Create object type - ULTIMATE ATTACK KILLER """
    # Step 1: ULTIMATE KILLER - 모든 공격 즉시 차단
    validate_all_inputs(
        branch=branch,
        name=data.name,
        display_name=data.display_name,
        description=data.description
    )
    
    # Step 2: 브랜치 검증
    validate_branch_name(branch)
    
    # 서비스 접근 방식 통일
    if hasattr(request.app.state, 'services'):
        schema_service: SchemaService = request.app.state.services.schema_service
    else:
        raise HTTPException(status_code=503, detail="Service container not initialized")
    
    # Step 3: 추가 보안 검증
    processor = get_secure_processor()
    
    # Sanitize name with additional security
    sanitized_name, was_modified, issues = processor.process_entity_name(data.name, auto_fix=False)
    if issues:
        logger.critical(f"🔥 OBJECT TYPE NAME ATTACK BLOCKED: {data.name} - {issues}")
        raise HTTPException(status_code=400, detail="Attack blocked")
    
    data.name = sanitized_name
    
    # Sanitize display name
    if data.display_name:
        sanitized_display, _, _ = processor.process_entity_name(data.display_name, auto_fix=True)
        data.display_name = sanitized_display
    
    result = await schema_service.create_object_type(branch, data)
    return {
        "objectType": result.model_dump() if hasattr(result, 'model_dump') else result,
        "branch": branch
    }

@router.get("/{branch}/object-types/{type_id}", response_model=Dict[str, Any])
async def get_object_type(
    branch: str,
    type_id: str,
    user: UserContext = Depends(get_current_user),
    request: Request = None
):
    """Get a specific object type"""
    # 서비스 접근 방식 통일
    if hasattr(request.app.state, 'services'):
        schema_service: SchemaService = request.app.state.services.schema_service
    else:
        raise HTTPException(status_code=503, detail="Service container not initialized")
    
    # Get all types and find the specific one
    types = await schema_service.list_object_types(branch=branch)
    for ot in types:
        if ot.get('name') == type_id or ot.get('@id', '').endswith(f'/{type_id}'):
            return {"objectType": ot, "branch": branch}
    
    raise HTTPException(status_code=404, detail=f"ObjectType {type_id} not found")

@router.put("/{branch}/object-types/{type_id}", response_model=Dict[str, Any])
async def update_object_type(
    branch: str,
    type_id: str,
    data: ObjectTypeUpdate,
    user: UserContext = Depends(get_current_user),
    request: Request = None
):
    """Update an object type"""
    raise HTTPException(status_code=501, detail="Update not yet implemented")

@router.delete("/{branch}/object-types/{type_id}")
async def delete_object_type(
    branch: str,
    type_id: str,
    user: UserContext = Depends(get_current_user),
    request: Request = None
):
    """Delete an object type"""
    raise HTTPException(status_code=501, detail="Delete not yet implemented")

# ==================== Properties ====================

class PropertyCreateRequest(BaseModel):
    """Property creation request"""
    name: str = Field(..., pattern="^[a-zA-Z][a-zA-Z0-9_]*$")
    displayName: str
    description: Optional[str] = None
    dataType: str
    required: bool = False
    indexed: bool = False
    unique: bool = False
    defaultValue: Optional[Any] = None
    
    @validator('dataType')
    def validate_data_type(cls, v):
        """Validate data type against allowed types"""
        allowed_types = [
            'xsd:string', 'xsd:integer', 'xsd:decimal', 'xsd:boolean',
            'xsd:date', 'xsd:dateTime', 'xsd:double', 'xsd:float'
        ]
        if v not in allowed_types:
            raise ValueError(f"Invalid dataType. Must be one of: {', '.join(allowed_types)}")
        return v

@router.get("/{branch}/object-types/{type_id}/properties", response_model=Dict[str, Any])
async def list_properties(
    branch: str,
    type_id: str,
    user: UserContext = Depends(get_current_user),
    request: Request = None
):
    """List all properties of an object type"""
    # 서비스 접근 방식 통일
    if hasattr(request.app.state, 'services'):
        extended_service: ExtendedSchemaService = request.app.state.services.extended_schema_service
    else:
        raise HTTPException(status_code=503, detail="Service container not initialized")
    
    properties = await extended_service.list_properties(branch, type_id)
    return {
        "properties": properties,
        "objectType": type_id,
        "branch": branch
    }

@router.post("/{branch}/object-types/{type_id}/properties", response_model=Dict[str, Any])
async def create_property(
    branch: str,
    type_id: str,
    data: PropertyCreateRequest,
    user: UserContext = Depends(get_current_user),
    request: Request = None
):
    """Create a new property for an object type"""
    # 서비스 접근 방식 통일
    if hasattr(request.app.state, 'services'):
        extended_service: ExtendedSchemaService = request.app.state.services.extended_schema_service
    else:
        raise HTTPException(status_code=503, detail="Service container not initialized")
    
    # Input sanitization
    processor = get_secure_processor()
    
    # Sanitize property name
    sanitized_name, was_modified, issues = processor.process_entity_name(data.name)
    if issues:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid property name: {', '.join(issues)}"
        )
    
    # Validate property doesn't already exist
    existing_props = await extended_service.list_properties(branch, type_id)
    if any(p.get('name') == sanitized_name for p in existing_props):
        raise HTTPException(
            status_code=409,
            detail=f"Property '{sanitized_name}' already exists on ObjectType '{type_id}'"
        )
    
    # Convert to PropertyCreate model
    property_create = PropertyCreate(
        name=sanitized_name,
        display_name=data.displayName,
        description=data.description,
        data_type_id=data.dataType,
        is_required=data.required,
        is_indexed=data.indexed,
        is_unique=data.unique,
        default_value=data.defaultValue
    )
    
    result = await extended_service.create_property(branch, type_id, property_create)
    return {
        "property": result.model_dump() if hasattr(result, 'model_dump') else result,
        "objectType": type_id,
        "branch": branch
    }

# ==================== Shared Properties ====================

class SharedPropertyCreateRequest(BaseModel):
    """Shared property creation request"""
    name: str
    displayName: str
    description: Optional[str] = None
    dataType: str
    constraints: Optional[str] = None
    defaultValue: Optional[str] = None

@router.get("/{branch}/shared-properties", response_model=Dict[str, Any])
async def list_shared_properties(
    branch: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user: UserContext = Depends(get_current_user),
    request: Request = None
):
    """List all shared properties"""
    # 서비스 접근 방식 통일
    if hasattr(request.app.state, 'services'):
        extended_service: ExtendedSchemaService = request.app.state.services.extended_schema_service
    else:
        raise HTTPException(status_code=503, detail="Service container not initialized")
    
    properties = await extended_service.list_shared_properties(branch)
    
    # Apply pagination
    total = len(properties)
    paginated = properties[offset:offset + limit]
    
    return {
        "sharedProperties": paginated,
        "total": total,
        "limit": limit,
        "offset": offset,
        "branch": branch
    }

@router.post("/{branch}/shared-properties", response_model=Dict[str, Any])
async def create_shared_property(
    branch: str,
    data: SharedPropertyCreateRequest,
    user: UserContext = Depends(get_current_user),
    request: Request = None
):
    """Create a new shared property"""
    # 서비스 접근 방식 통일
    if hasattr(request.app.state, 'services'):
        extended_service: ExtendedSchemaService = request.app.state.services.extended_schema_service
    else:
        raise HTTPException(status_code=503, detail="Service container not initialized")
    
    # Input sanitization
    processor = get_secure_processor()
    
    # Sanitize name
    sanitized_name, was_modified, issues = processor.process_entity_name(data.name)
    if issues:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid shared property name: {', '.join(issues)}"
        )
    data.name = sanitized_name
    
    # Check if shared property already exists
    existing = await extended_service.list_shared_properties(branch)
    if any(sp.get('name') == sanitized_name for sp in existing):
        raise HTTPException(
            status_code=409,
            detail=f"SharedProperty '{sanitized_name}' already exists"
        )
    
    result = await extended_service.create_shared_property(branch, data.model_dump())
    return {
        "sharedProperty": result,
        "branch": branch
    }

# ==================== Link Types ====================

class LinkTypeCreateRequest(BaseModel):
    """Link type creation request"""
    name: str
    displayName: str
    description: Optional[str] = None
    sourceObjectType: str
    targetObjectType: str
    cardinality: str = "one-to-many"
    bidirectional: bool = False

@router.get("/{branch}/link-types", response_model=Dict[str, Any])
async def list_link_types(
    branch: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user: UserContext = Depends(get_current_user),
    request: Request = None
):
    """List all link types"""
    # 서비스 접근 방식 통일
    if hasattr(request.app.state, 'services'):
        extended_service: ExtendedSchemaService = request.app.state.services.extended_schema_service
    else:
        raise HTTPException(status_code=503, detail="Service container not initialized")
    
    links = await extended_service.list_link_types(branch)
    
    # Apply pagination
    total = len(links)
    paginated = links[offset:offset + limit]
    
    return {
        "linkTypes": paginated,
        "total": total,
        "limit": limit,
        "offset": offset,
        "branch": branch
    }

@router.post("/{branch}/link-types", response_model=Dict[str, Any])
async def create_link_type(
    branch: str,
    data: LinkTypeCreateRequest,
    user: UserContext = Depends(get_current_user),
    request: Request = None
):
    """Create a new link type"""
    # 서비스 접근 방식 통일
    if hasattr(request.app.state, 'services'):
        extended_service: ExtendedSchemaService = request.app.state.services.extended_schema_service
    else:
        raise HTTPException(status_code=503, detail="Service container not initialized")
    # 서비스 접근 방식 통일
    if hasattr(request.app.state, 'services'):
        schema_service: SchemaService = request.app.state.services.schema_service
    else:
        raise HTTPException(status_code=503, detail="Service container not initialized")
    
    # Input sanitization
    processor = get_secure_processor()
    
    # Sanitize link type name
    sanitized_name, was_modified, issues = processor.process_entity_name(data.name)
    if issues:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid link type name: {', '.join(issues)}"
        )
    data.name = sanitized_name
    
    # Validate source and target object types exist
    object_types = await schema_service.list_object_types(branch)
    ot_names = [ot.get('name') for ot in object_types]
    
    if data.sourceObjectType not in ot_names:
        raise HTTPException(
            status_code=400,
            detail=f"Source ObjectType '{data.sourceObjectType}' does not exist"
        )
    
    if data.targetObjectType not in ot_names:
        raise HTTPException(
            status_code=400,
            detail=f"Target ObjectType '{data.targetObjectType}' does not exist"
        )
    
    # Validate cardinality
    valid_cardinalities = ["one-to-one", "one-to-many", "many-to-many"]
    if data.cardinality not in valid_cardinalities:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid cardinality. Must be one of: {', '.join(valid_cardinalities)}"
        )
    
    result = await extended_service.create_link_type(branch, data.model_dump())
    return {
        "linkType": result,
        "branch": branch
    }

# ==================== Action Types ====================

class ActionTypeCreateRequest(BaseModel):
    """Action type creation request"""
    name: str
    displayName: str
    description: Optional[str] = None
    targetTypes: List[str]
    operations: List[str]
    sideEffects: Optional[str] = None
    permissions: Optional[str] = None

@router.get("/{branch}/action-types", response_model=Dict[str, Any])
async def list_action_types(
    branch: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user: UserContext = Depends(get_current_user),
    request: Request = None
):
    """List all action types"""
    # 서비스 접근 방식 통일
    if hasattr(request.app.state, 'services'):
        extended_service: ExtendedSchemaService = request.app.state.services.extended_schema_service
    else:
        raise HTTPException(status_code=503, detail="Service container not initialized")
    
    actions = await extended_service.list_action_types(branch)
    
    # Apply pagination
    total = len(actions)
    paginated = actions[offset:offset + limit]
    
    return {
        "actionTypes": paginated,
        "total": total,
        "limit": limit,
        "offset": offset,
        "branch": branch
    }

@router.post("/{branch}/action-types", response_model=Dict[str, Any])
async def create_action_type(
    branch: str,
    data: ActionTypeCreateRequest,
    user: UserContext = Depends(get_current_user),
    request: Request = None
):
    """Create a new action type"""
    # 서비스 접근 방식 통일
    if hasattr(request.app.state, 'services'):
        extended_service: ExtendedSchemaService = request.app.state.services.extended_schema_service
    else:
        raise HTTPException(status_code=503, detail="Service container not initialized")
    # 서비스 접근 방식 통일
    if hasattr(request.app.state, 'services'):
        schema_service: SchemaService = request.app.state.services.schema_service
    else:
        raise HTTPException(status_code=503, detail="Service container not initialized")
    
    # Input sanitization
    processor = get_secure_processor()
    
    # Sanitize action type name
    sanitized_name, was_modified, issues = processor.process_entity_name(data.name)
    if issues:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action type name: {', '.join(issues)}"
        )
    data.name = sanitized_name
    
    # Validate target object types exist
    object_types = await schema_service.list_object_types(branch)
    ot_names = [ot.get('name') for ot in object_types]
    
    for target in data.targetTypes:
        if target not in ot_names:
            raise HTTPException(
                status_code=400,
                detail=f"Target ObjectType '{target}' does not exist"
            )
    
    # Validate operations format
    for op in data.operations:
        if ':' not in op:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid operation format '{op}'. Expected format: 'action:value'"
            )
    
    result = await extended_service.create_action_type(branch, data.model_dump())
    return {
        "actionType": result,
        "branch": branch
    }

# ==================== Interfaces ====================

class InterfaceCreateRequest(BaseModel):
    """Interface creation request"""
    name: str
    displayName: str
    description: Optional[str] = None
    properties: List[str] = Field(default_factory=list)
    sharedProperties: List[str] = Field(default_factory=list)
    actions: List[str] = Field(default_factory=list)

@router.get("/{branch}/interfaces", response_model=Dict[str, Any])
async def list_interfaces(
    branch: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user: UserContext = Depends(get_current_user),
    request: Request = None
):
    """List all interfaces"""
    # 서비스 접근 방식 통일
    if hasattr(request.app.state, 'services'):
        extended_service: ExtendedSchemaService = request.app.state.services.extended_schema_service
    else:
        raise HTTPException(status_code=503, detail="Service container not initialized")
    
    interfaces = await extended_service.list_interfaces(branch)
    
    # Apply pagination
    total = len(interfaces)
    paginated = interfaces[offset:offset + limit]
    
    return {
        "interfaces": paginated,
        "total": total,
        "limit": limit,
        "offset": offset,
        "branch": branch
    }

@router.post("/{branch}/interfaces", response_model=Dict[str, Any])
async def create_interface(
    branch: str,
    data: InterfaceCreateRequest,
    user: UserContext = Depends(get_current_user),
    request: Request = None
):
    """Create a new interface"""
    # 서비스 접근 방식 통일
    if hasattr(request.app.state, 'services'):
        extended_service: ExtendedSchemaService = request.app.state.services.extended_schema_service
    else:
        raise HTTPException(status_code=503, detail="Service container not initialized")
    
    result = await extended_service.create_interface(branch, data.model_dump())
    return {
        "interface": result,
        "branch": branch
    }

# ==================== Semantic Types ====================

class SemanticTypeCreateRequest(BaseModel):
    """Semantic type creation request"""
    name: str
    displayName: str
    description: Optional[str] = None
    baseType: str
    constraints: Optional[str] = None
    validationRules: List[str] = Field(default_factory=list)
    examples: List[str] = Field(default_factory=list)
    
    @validator('baseType')
    def validate_base_type(cls, v):
        """Validate base type"""
        allowed_base_types = [
            'xsd:string', 'xsd:integer', 'xsd:decimal', 'xsd:boolean',
            'xsd:date', 'xsd:dateTime', 'xsd:double', 'xsd:float',
            'xsd:anyURI', 'xsd:base64Binary'
        ]
        if v not in allowed_base_types:
            raise ValueError(f"Invalid baseType. Must be one of: {', '.join(allowed_base_types)}")
        return v

@router.get("/{branch}/semantic-types", response_model=Dict[str, Any])
async def list_semantic_types(
    branch: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user: UserContext = Depends(get_current_user),
    request: Request = None
):
    """List all semantic types"""
    # 서비스 접근 방식 통일
    if hasattr(request.app.state, 'services'):
        extended_service: ExtendedSchemaService = request.app.state.services.extended_schema_service
    else:
        raise HTTPException(status_code=503, detail="Service container not initialized")
    
    types = await extended_service.list_semantic_types(branch)
    
    # Apply pagination
    total = len(types)
    paginated = types[offset:offset + limit]
    
    return {
        "semanticTypes": paginated,
        "total": total,
        "limit": limit,
        "offset": offset,
        "branch": branch
    }

@router.post("/{branch}/semantic-types", response_model=Dict[str, Any])
async def create_semantic_type(
    branch: str,
    data: SemanticTypeCreateRequest,
    user: UserContext = Depends(get_current_user),
    request: Request = None
):
    """Create a new semantic type with complete security validation"""
    # 🔒 CRITICAL SECURITY: Validate branch name
    validate_branch_name(branch)
    
    # 🔒 CRITICAL SECURITY: Complete input validation
    from core.security.critical_security_framework import get_critical_security_validator
    
    security_validator = get_critical_security_validator()
    request_info = {
        'client_ip': request.client.host if request.client else 'unknown',
        'path': request.url.path,
        'user_id': getattr(user, 'user_id', 'unknown')
    }
    
    # Validate all input fields
    validation_fields = [
        ('name', data.name),
        ('displayName', data.displayName),
        ('description', data.description),
        ('baseType', data.baseType),
        ('constraints', data.constraints)
    ]
    
    for field_name, field_value in validation_fields:
        if field_value is not None:
            is_safe, threats = security_validator.validate_input(
                field_value, field_name, request_info
            )
            if not is_safe:
                logger.critical(f"🚨 SECURITY THREAT in SemanticType.{field_name}: {threats}")
                raise HTTPException(
                    status_code=400,
                    detail="Security threat detected"
                )
    
    # Validate validation rules
    for i, rule in enumerate(data.validationRules):
        is_safe, threats = security_validator.validate_input(
            rule, f'validationRules[{i}]', request_info
        )
        if not is_safe:
            logger.critical(f"🚨 SECURITY THREAT in validation rule {i}: {threats}")
            raise HTTPException(
                status_code=400,
                detail="Security threat detected"
            )
    
    # Validate examples
    for i, example in enumerate(data.examples):
        is_safe, threats = security_validator.validate_input(
            example, f'examples[{i}]', request_info
        )
        if not is_safe:
            logger.critical(f"🚨 SECURITY THREAT in example {i}: {threats}")
            raise HTTPException(
                status_code=400,
                detail="Security threat detected"
            )
    
    # 서비스 접근 방식 통일
    if hasattr(request.app.state, 'services'):
        extended_service: ExtendedSchemaService = request.app.state.services.extended_schema_service
    else:
        raise HTTPException(status_code=503, detail="Service container not initialized")
    
    # Additional input sanitization
    processor = get_secure_processor()
    
    # Sanitize name
    sanitized_name, was_modified, issues = processor.process_entity_name(data.name)
    if issues:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid semantic type name: {', '.join(issues)}"
        )
    data.name = sanitized_name
    
    # Ensure description is not None for TerminusDB schema requirement
    if data.description is None:
        data.description = ""
    
    try:
        result = await extended_service.create_semantic_type(branch, data.model_dump())
        
        # Log successful creation for audit
        logger.info(f"✅ SemanticType created: {data.name} by user {getattr(user, 'user_id', 'unknown')}")
        
        return {
            "semanticType": result,
            "branch": branch
        }
    except ConnectionError as e:
        logger.error(f"❌ Database connection error creating SemanticType: {e}")
        raise HTTPException(
            status_code=503,
            detail="Database service temporarily unavailable"
        )
    except TimeoutError as e:
        logger.error(f"❌ Timeout creating SemanticType: {e}")
        raise HTTPException(
            status_code=504,
            detail="Operation timed out"
        )
    except ValueError as e:
        logger.error(f"❌ Invalid data for SemanticType creation: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid semantic type data: {str(e)}"
        )
    except KeyError as e:
        logger.error(f"❌ Missing required field for SemanticType: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Missing required field: {str(e)}"
        )
    except RuntimeError as e:
        logger.error(f"❌ Unexpected error creating SemanticType: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )

# ==================== Struct Types ====================

class StructFieldDef(BaseModel):
    """Struct field definition"""
    name: str
    displayName: str
    fieldType: str
    required: bool = False

class StructTypeCreateRequest(BaseModel):
    """Struct type creation request"""
    name: str
    displayName: str
    description: Optional[str] = None
    fields: List[StructFieldDef]

@router.get("/{branch}/struct-types", response_model=Dict[str, Any])
async def list_struct_types(
    branch: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user: UserContext = Depends(get_current_user),
    request: Request = None
):
    """List all struct types"""
    # 서비스 접근 방식 통일
    if hasattr(request.app.state, 'services'):
        extended_service: ExtendedSchemaService = request.app.state.services.extended_schema_service
    else:
        raise HTTPException(status_code=503, detail="Service container not initialized")
    
    types = await extended_service.list_struct_types(branch)
    
    # Apply pagination
    total = len(types)
    paginated = types[offset:offset + limit]
    
    return {
        "structTypes": paginated,
        "total": total,
        "limit": limit,
        "offset": offset,
        "branch": branch
    }

@router.post("/{branch}/struct-types", response_model=Dict[str, Any])
async def create_struct_type(
    branch: str,
    data: StructTypeCreateRequest,
    user: UserContext = Depends(get_current_user),
    request: Request = None
):
    """Create a new struct type"""
    # 서비스 접근 방식 통일
    if hasattr(request.app.state, 'services'):
        extended_service: ExtendedSchemaService = request.app.state.services.extended_schema_service
    else:
        raise HTTPException(status_code=503, detail="Service container not initialized")
    
    result = await extended_service.create_struct_type(branch, data.model_dump())
    return {
        "structType": result,
        "branch": branch
    }
