"""
Arrakis Common Library
MSA 서비스 간 공유되는 공통 기능
"""

__version__ = "0.1.0"

# 감사 로깅
from .audit.client import AuditClient, audit_log, create_audit_trail, log_event

# JWT 관련
from .auth.jwt_handler import (
    JWTHandler,
    create_access_token,
    decode_token,
    get_current_user,
    verify_token,
)

# 설정
from .config import BaseSettings, DatabaseSettings, JWTSettings, get_settings

# 로깅
from .logging import (
    get_logger,
    setup_development_logging,
    setup_logging,
    setup_production_logging,
)
from .models.audit import AuditEvent, AuditLevel, AuditLog

# 모델
from .models.base import AuditMixin, BaseModel, TimestampMixin
from .models.user import TokenData, UserBase, UserCreate, UserResponse
from .utils.security import (
    decrypt_text,
    encrypt_text,
    generate_api_key,
    generate_token,
    hash_data,
    hash_password,
    verify_password,
)

# 유틸리티
from .utils.validators import validate_email, validate_password, validate_phone

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
    # Logging
    "get_logger",
    "setup_logging",
    "setup_development_logging",
    "setup_production_logging",
    # Utils
    "validate_email",
    "validate_password",
    "validate_phone",
    "hash_password",
    "verify_password",
    "generate_token",
    "generate_api_key",
    "hash_data",
    "encrypt_text",
    "decrypt_text",
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
