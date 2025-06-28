# Core Integrations Package
"""
Unified Integration Interface
- Reduces IAM client duplication by providing single entry point
- Supports fallback, basic, and advanced JWKS integration modes
- Uses factory pattern for appropriate client selection
"""

from .iam_service_client_with_fallback import IAMServiceClientWithFallback
from .iam_service_client import IAMServiceClient
from ..iam.iam_integration import IAMIntegration
import os

# 통합 IAM 클라이언트 인스턴스 (중복 제거)
_UNIFIED_IAM_CLIENT = None

def get_iam_client():
    """
    통합 IAM 클라이언트 - 중복 제거된 단일 인터페이스
    
    우선순위:
    1. IAMServiceClientWithFallback (production 권장)
    2. IAMIntegration (JWKS 고급 기능 필요시)
    3. IAMServiceClient (basic fallback)
    
    Returns:
        Unified IAM client instance
    """
    global _UNIFIED_IAM_CLIENT
    if _UNIFIED_IAM_CLIENT is None:
        # Use with_fallback as default (most robust)
        if os.getenv("IAM_ENABLE_FALLBACK", "true").lower() == "true":
            _UNIFIED_IAM_CLIENT = IAMServiceClientWithFallback()
        elif os.getenv("IAM_JWKS_ENABLED", "false").lower() == "true":
            _UNIFIED_IAM_CLIENT = IAMIntegration()
        else:
            _UNIFIED_IAM_CLIENT = IAMServiceClient()
    return _UNIFIED_IAM_CLIENT

# DEPRECATED functions for backward compatibility
def get_legacy_iam_client():
    """DEPRECATED: Use get_iam_client() instead"""
    import warnings
    warnings.warn("get_legacy_iam_client() is deprecated, use get_iam_client()", 
                  DeprecationWarning, stacklevel=2)
    return get_iam_client()

# Export unified interface (reduces confusion from multiple options)
__all__ = [
    'get_iam_client',  # Primary interface
    # Legacy exports for backward compatibility  
    'IAMServiceClient',
    'IAMServiceClientWithFallback', 
    'IAMIntegration'
]