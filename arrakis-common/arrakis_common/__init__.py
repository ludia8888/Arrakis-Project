"""
Arrakis Common Library
MSA 서비스 간 공유되는 공통 기능
"""

__version__ = "0.1.0"

# JWT 관련
from .auth.jwt_handler import (
    JWTHandler,
    create_access_token,
    decode_token,
    verify_token,
    get_current_user
)

# 감사 로깅
from .audit.client import (
    AuditClient,
    audit_log,
    log_event,
    create_audit_trail
)

# 유틸리티
from .utils.validators import (
    validate_email,
    validate_password,
    validate_phone
)

from .utils.security import (
    hash_password,
    verify_password,
    generate_token,
    generate_api_key
)

# 설정
from .config import (
    BaseSettings,
    get_settings,
    JWTSettings,
    DatabaseSettings
)

# 모델
from .models.base import (
    BaseModel,
    TimestampMixin,
    AuditMixin
)

from .models.user import (
    UserBase,
    UserCreate,
    UserResponse,
    TokenData
)

from .models.audit import (
    AuditEvent,
    AuditLog,
    AuditLevel
)

__all__ = [
    # JWT
    "JWTHandler",
    "create_access_token",
    "decode_token",
    "verify_token",
    "get_current_user",
    
    # Audit
    "AuditClient",
    "audit_log",
    "log_event",
    "create_audit_trail",
    
    # Utils
    "validate_email",
    "validate_password",
    "validate_phone",
    "hash_password",
    "verify_password",
    "generate_token",
    "generate_api_key",
    
    # Config
    "BaseSettings",
    "get_settings",
    "JWTSettings",
    "DatabaseSettings",
    
    # Models
    "BaseModel",
    "TimestampMixin",
    "AuditMixin",
    "UserBase",
    "UserCreate",
    "UserResponse",
    "TokenData",
    "AuditEvent",
    "AuditLog",
    "AuditLevel",
]