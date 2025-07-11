"""
사용자 관련 공통 모델
모든 서비스에서 사용하는 사용자 관련 스키마
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import Field, EmailStr, validator
from .base import BaseModel, BaseEntity


class UserBase(BaseModel):
    """사용자 기본 모델"""
    username: str = Field(..., min_length=3, max_length=30)
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool = Field(default=True)
    is_verified: bool = Field(default=False)
    
    @validator('username')
    def username_alphanumeric(cls, v):
        """사용자명 검증"""
        import re
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('Username must be alphanumeric with underscores only')
        return v


class UserCreate(UserBase):
    """사용자 생성 모델"""
    password: str = Field(..., min_length=8)
    confirm_password: Optional[str] = None
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        """패스워드 일치 검증"""
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v
    
    @validator('password')
    def password_strength(cls, v):
        """패스워드 강도 검증"""
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one digit')
        if not any(char.isupper() for char in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(char.islower() for char in v):
            raise ValueError('Password must contain at least one lowercase letter')
        return v


class UserUpdate(BaseModel):
    """사용자 업데이트 모델"""
    username: Optional[str] = Field(None, min_length=3, max_length=30)
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8)


class UserResponse(UserBase):
    """사용자 응답 모델"""
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    roles: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    
    class Config:
        orm_mode = True


class UserInDB(UserResponse):
    """데이터베이스 사용자 모델"""
    hashed_password: str
    email_verification_token: Optional[str] = None
    password_reset_token: Optional[str] = None
    password_reset_expires: Optional[datetime] = None
    failed_login_attempts: int = Field(default=0)
    locked_until: Optional[datetime] = None


class UserProfile(BaseModel):
    """사용자 프로필 모델"""
    user_id: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = Field(None, max_length=500)
    location: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    preferences: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TokenData(BaseModel):
    """토큰 데이터 모델"""
    user_id: str
    username: str
    email: Optional[str] = None
    roles: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    session_id: Optional[str] = None
    is_service_account: bool = Field(default=False)
    service_name: Optional[str] = None
    client_id: Optional[str] = None
    scopes: List[str] = Field(default_factory=list)


class TokenResponse(BaseModel):
    """토큰 응답 모델"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None
    scope: Optional[str] = None


class LoginRequest(BaseModel):
    """로그인 요청 모델"""
    username: str
    password: str
    remember_me: bool = Field(default=False)
    device_info: Optional[Dict[str, Any]] = None


class LoginResponse(TokenResponse):
    """로그인 응답 모델"""
    user: UserResponse
    requires_mfa: bool = Field(default=False)
    challenge_token: Optional[str] = None


class PasswordResetRequest(BaseModel):
    """패스워드 재설정 요청"""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """패스워드 재설정 확인"""
    token: str
    new_password: str = Field(..., min_length=8)
    confirm_password: str
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        """패스워드 일치 검증"""
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v


class ChangePasswordRequest(BaseModel):
    """패스워드 변경 요청"""
    current_password: str
    new_password: str = Field(..., min_length=8)
    confirm_password: str
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        """패스워드 일치 검증"""
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v


class MFASetupRequest(BaseModel):
    """MFA 설정 요청"""
    mfa_type: str = Field(..., pattern="^(totp|sms|email)$")
    phone_number: Optional[str] = None
    backup_email: Optional[str] = None


class MFAVerifyRequest(BaseModel):
    """MFA 검증 요청"""
    challenge_token: str
    mfa_code: str
    trust_device: bool = Field(default=False)


class UserSession(BaseModel):
    """사용자 세션 모델"""
    session_id: str
    user_id: str
    ip_address: str
    user_agent: str
    device_info: Optional[Dict[str, Any]] = None
    created_at: datetime
    last_activity: datetime
    expires_at: datetime
    is_active: bool = Field(default=True)
    
    def is_expired(self) -> bool:
        """세션 만료 확인"""
        return datetime.utcnow() > self.expires_at