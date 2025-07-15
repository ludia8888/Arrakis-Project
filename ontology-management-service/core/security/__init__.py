"""
Security Module for OMS
보안 관련 기능 모듈
"""

# Re-export arrakis_common security functions for backward compatibility
from arrakis_common.utils.security import calculate_hmac
from arrakis_common.utils.security import decrypt_data as decrypt
from arrakis_common.utils.security import encrypt_data as encrypt
from arrakis_common.utils.security import (
    generate_rsa_keypair,
    generate_signing_key,
    hash_data,
    sign,
    verify_hmac,
    verify_signature,
)

from .pii_handler import (
    PIIHandler,
    PIIHandlingStrategy,
    PIIMatch,
    PIIType,
    create_pii_handler,
)

__all__ = [
    "PIIHandler",
    "PIIType",
    "PIIMatch",
    "PIIHandlingStrategy",
    "create_pii_handler",
    # Common security functions
    "encrypt",
    "decrypt",
    "sign",
    "verify_signature",
    "generate_signing_key",
    "calculate_hmac",
    "verify_hmac",
    "hash_data",
    "generate_rsa_keypair",
]
