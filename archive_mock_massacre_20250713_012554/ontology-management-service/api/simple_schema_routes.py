"""
Simple Schema CRUD API - 실제 작동하는 구현
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json
import os
from datetime import datetime

router = APIRouter(prefix="/schemas", tags=["Schema Management"])

# 임시 인메모리 저장소 (실제 DB 연결 전까지)
schemas_storage: Dict[str, Dict] = {}

class SchemaCreate(BaseModel):
    name: str
    description: Optional[str] = None
    properties: List[Dict[str, Any]] = []

class SchemaResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    properties: List[Dict[str, Any]] = []
    created_at: str
    updated_at: str

@router.post("/", response_model=SchemaResponse)
async def create_schema(schema: SchemaCreate):
    """스키마 생성"""
    schema_id = f"schema_{len(schemas_storage) + 1}"
    timestamp = datetime.now().isoformat()
    
    schema_data = {
        "id": schema_id,
        "name": schema.name,
        "description": schema.description,
        "properties": schema.properties,
        "created_at": timestamp,
        "updated_at": timestamp
    }
    
    schemas_storage[schema_id] = schema_data
    return SchemaResponse(**schema_data)

@router.get("/", response_model=List[SchemaResponse])
async def list_schemas():
    """스키마 목록 조회"""
    return [SchemaResponse(**schema) for schema in schemas_storage.values()]

@router.get("/{schema_id}", response_model=SchemaResponse)
async def get_schema(schema_id: str):
    """특정 스키마 조회"""
    if schema_id not in schemas_storage:
        raise HTTPException(status_code=404, detail="Schema not found")
    
    return SchemaResponse(**schemas_storage[schema_id])

@router.put("/{schema_id}", response_model=SchemaResponse)
async def update_schema(schema_id: str, schema: SchemaCreate):
    """스키마 업데이트"""
    if schema_id not in schemas_storage:
        raise HTTPException(status_code=404, detail="Schema not found")
    
    timestamp = datetime.now().isoformat()
    
    updated_data = {
        "id": schema_id,
        "name": schema.name,
        "description": schema.description,
        "properties": schema.properties,
        "created_at": schemas_storage[schema_id]["created_at"],
        "updated_at": timestamp
    }
    
    schemas_storage[schema_id] = updated_data
    return SchemaResponse(**updated_data)

@router.delete("/{schema_id}")
async def delete_schema(schema_id: str):
    """스키마 삭제"""
    if schema_id not in schemas_storage:
        raise HTTPException(status_code=404, detail="Schema not found")
    
    del schemas_storage[schema_id]
    return {"message": "Schema deleted successfully"}

@router.get("/status/working")
async def schema_working_status():
    """Schema API 작동 상태 확인"""
    return {
        "status": "working",
        "message": "Schema CRUD API is fully operational",
        "total_schemas": len(schemas_storage),
        "available_endpoints": [
            "POST /api/v1/schemas/",
            "GET /api/v1/schemas/",
            "GET /api/v1/schemas/{id}",
            "PUT /api/v1/schemas/{id}",
            "DELETE /api/v1/schemas/{id}"
        ]
    }