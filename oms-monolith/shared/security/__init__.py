"""
Shared Security Layer - Single Source of Truth
통합 보안 인터페이스: 인증, 인가, Rate Limiting, Circuit Breaking
"""

from .auth_facade import (
    AuthenticationFacade, 
    UserContextValidator,
    SecurityContext,
    SecurityViolation,
    get_auth_facade
)

from .protection_facade import (
    ProtectionFacade,
    CircuitBreakerConfig,
    RateLimiterConfig,
    ProtectionViolation,
    get_protection_facade
)

from .exception_handler import (
    SecurityExceptionHandler,
    SecurityErrorCode,
    get_security_exception_handler,
    security_violation_handler,
    protection_violation_handler,
    general_exception_handler
)

# Keep existing MTLS for backward compatibility
from .mtls_config import MTLSConfig, get_mtls_config

__all__ = [
    # Authentication
    "AuthenticationFacade",
    "UserContextValidator", 
    "SecurityContext",
    "SecurityViolation",
    "get_auth_facade",
    
    # Protection
    "ProtectionFacade",
    "CircuitBreakerConfig",
    "RateLimiterConfig", 
    "ProtectionViolation",
    "get_protection_facade",
    
    # Exception Handling
    "SecurityExceptionHandler",
    "SecurityErrorCode",
    "get_security_exception_handler",
    "security_violation_handler",
    "protection_violation_handler", 
    "general_exception_handler",
    
    # Legacy MTLS
    "MTLSConfig",
    "get_mtls_config"
]