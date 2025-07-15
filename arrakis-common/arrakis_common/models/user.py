"""
사용자 관련 공통 모델
모든 서비스에서 사용하는 사용자 관련 스키마
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import EmailStr, Field, validator

from .base import BaseEntity, BaseModel


class UserBase(BaseModel):
    """User base model"""

    username: str = Field(..., min_length=3, max_length=30)
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool = Field(default=True)
    is_verified: bool = Field(default=False)

    @validator("username")
    def username_alphanumeric(cls, v):
        """Username validation"""
        import re

        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("Username must be alphanumeric with underscores only")
        return v


class UserCreate(UserBase):
    """User creation model"""

    password: str = Field(..., min_length=8)
    confirm_password: Optional[str] = None

    @validator("confirm_password")
    def passwords_match(cls, v, values):
        """Password matching validation"""
        if "password" in values and v != values["password"]:
            raise ValueError("Passwords do not match")
        return v

    @validator("password")
    def password_strength(cls, v):
        """Password strength validation"""
        if not any(char.isdigit() for char in v):
            raise ValueError("Password must contain at least one digit")
        if not any(char.isupper() for char in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(char.islower() for char in v):
            raise ValueError("Password must contain at least one lowercase letter")
        return v


class UserUpdate(BaseModel):
    """User update model"""

    username: Optional[str] = Field(None, min_length=3, max_length=30)
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8)


class UserResponse(UserBase):
    """User response model"""

    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    roles: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)

    class Config:
        orm_mode = True


class UserInDB(UserResponse):
    """Database user model"""

    hashed_password: str
    email_verification_token: Optional[str] = None
    password_reset_token: Optional[str] = None
    password_reset_expires: Optional[datetime] = None
    failed_login_attempts: int = Field(default=0)
    locked_until: Optional[datetime] = None


class UserProfile(BaseModel):
    """User profile model"""

    user_id: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = Field(None, max_length=500)
    location: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    preferences: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TokenData(BaseModel):
    """Token data model"""

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
    """Token response model"""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None
    scope: Optional[str] = None


class LoginRequest(BaseModel):
    """Login request model"""

    username: str
    password: str
    remember_me: bool = Field(default=False)
    device_info: Optional[Dict[str, Any]] = None


class LoginResponse(TokenResponse):
    """Login response model"""

    user: UserResponse
    requires_mfa: bool = Field(default=False)
    challenge_token: Optional[str] = None


class PasswordResetRequest(BaseModel):
    """Password reset request"""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation"""

    token: str
    new_password: str = Field(..., min_length=8)
    confirm_password: str

    @validator("confirm_password")
    def passwords_match(cls, v, values):
        """Password matching validation"""
        if "new_password" in values and v != values["new_password"]:
            raise ValueError("Passwords do not match")
        return v


class ChangePasswordRequest(BaseModel):
    """Change password request"""

    current_password: str
    new_password: str = Field(..., min_length=8)
    confirm_password: str

    @validator("confirm_password")
    def passwords_match(cls, v, values):
        """Password matching validation"""
        if "new_password" in values and v != values["new_password"]:
            raise ValueError("Passwords do not match")
        return v


class MFASetupRequest(BaseModel):
    """MFA setup request"""

    mfa_type: str = Field(..., pattern="^(totp|sms|email)$")
    phone_number: Optional[str] = None
    backup_email: Optional[str] = None


class MFAVerifyRequest(BaseModel):
    """MFA verify request"""

    challenge_token: str
    mfa_code: str
    trust_device: bool = Field(default=False)


class UserSession(BaseModel):
    """User session model"""

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
        """Check if session is expired"""
        return datetime.utcnow() > self.expires_at
