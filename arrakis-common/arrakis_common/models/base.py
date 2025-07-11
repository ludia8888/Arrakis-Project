"""
기본 모델 클래스들
모든 MSA 서비스에서 상속받아 사용하는 기본 모델
"""
from datetime import datetime
from typing import Optional, Any, Dict
from pydantic import BaseModel as PydanticBaseModel, Field
import uuid


class BaseModel(PydanticBaseModel):
    """기본 Pydantic 모델"""
    
    class Config:
        # JSON 인코더 설정
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            uuid.UUID: lambda v: str(v),
        }
        # 필드 검증
        validate_assignment = True
        # 알 수 없는 필드 무시
        extra = "forbid"
        # 스키마 예시 사용
        schema_extra = {
            "example": {}
        }
        # ORM 모드 활성화
        orm_mode = True


class TimestampMixin(BaseModel):
    """타임스탬프 믹스인"""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    
    def update_timestamp(self):
        """업데이트 타임스탬프 갱신"""
        self.updated_at = datetime.utcnow()


class AuditMixin(TimestampMixin):
    """감사 추적 믹스인"""
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    version: int = Field(default=1)
    is_deleted: bool = Field(default=False)
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None
    
    def soft_delete(self, user_id: str):
        """소프트 삭제"""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        self.deleted_by = user_id
        
    def increment_version(self):
        """버전 증가"""
        self.version += 1
        self.update_timestamp()


class ResponseModel(BaseModel):
    """API 응답 기본 모델"""
    success: bool = Field(default=True)
    message: Optional[str] = None
    data: Optional[Any] = None
    errors: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = None
    
    @classmethod
    def success_response(cls, data: Any = None, message: str = "Success", **kwargs):
        """성공 응답 생성"""
        return cls(
            success=True,
            message=message,
            data=data,
            **kwargs
        )
    
    @classmethod
    def error_response(cls, message: str, errors: Dict[str, Any] = None, **kwargs):
        """에러 응답 생성"""
        return cls(
            success=False,
            message=message,
            errors=errors,
            **kwargs
        )


class PaginatedResponse(ResponseModel):
    """페이지네이션 응답 모델"""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    total_count: int = Field(default=0, ge=0)
    total_pages: int = Field(default=0, ge=0)
    has_next: bool = Field(default=False)
    has_prev: bool = Field(default=False)
    
    def calculate_pagination(self):
        """페이지네이션 계산"""
        self.total_pages = (self.total_count + self.page_size - 1) // self.page_size
        self.has_next = self.page < self.total_pages
        self.has_prev = self.page > 1


class ErrorDetail(BaseModel):
    """에러 상세 모델"""
    code: str
    message: str
    field: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ValidationError(BaseModel):
    """검증 에러 모델"""
    errors: list[ErrorDetail]
    
    @classmethod
    def from_pydantic_errors(cls, errors):
        """Pydantic 검증 에러에서 변환"""
        error_details = []
        for error in errors:
            error_details.append(
                ErrorDetail(
                    code="validation_error",
                    message=error["msg"],
                    field=".".join(str(loc) for loc in error["loc"]),
                    details=error
                )
            )
        return cls(errors=error_details)


class BaseEntity(AuditMixin):
    """데이터베이스 엔티티 기본 모델"""
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return self.dict(exclude_unset=True)
    
    def to_json(self) -> str:
        """JSON 변환"""
        return self.json(exclude_unset=True)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """딕셔너리에서 생성"""
        return cls(**data)


class SearchParams(BaseModel):
    """검색 파라미터 모델"""
    query: Optional[str] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_by: Optional[str] = None
    sort_order: str = Field(default="asc", pattern="^(asc|desc)$")
    filters: Optional[Dict[str, Any]] = None
    
    def get_offset(self) -> int:
        """오프셋 계산"""
        return (self.page - 1) * self.page_size
    
    def get_limit(self) -> int:
        """리밋 반환"""
        return self.page_size