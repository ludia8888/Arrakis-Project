"""
PII Masking Utilities - Shared module for consistent PII handling
"""
from typing import Dict, Any, List, Optional, Set
from core.security.pii_handler import PIIHandler, PIIHandlingStrategy
from utils.logger import get_logger
from shared.config.unified_env import unified_env

logger = get_logger(__name__)

# Global PII handler instance
_pii_handler: Optional[PIIHandler] = None


def get_pii_handler() -> PIIHandler:
    """Get or create global PII handler instance"""
    global _pii_handler
    if _pii_handler is None:
        environment = unified_env.get("ENVIRONMENT").value
        
        # For audit logging, we always anonymize
        _pii_handler = PIIHandler(strategy=PIIHandlingStrategy.ANONYMIZE)
    
    return _pii_handler


def mask_pii_fields(data: Dict[str, Any], 
                   additional_fields: Optional[List[str]] = None,
                   _seen: Optional[Set[int]] = None) -> Dict[str, Any]:
    """
    Mask PII fields in data for audit logging
    
    Args:
        data: Data to mask
        additional_fields: Additional field names to mask
        _seen: Internal parameter for circular reference handling
        
    Returns:
        Masked data
    """
    if _seen is None:
        _seen = set()
    
    # Handle circular references
    data_id = id(data)
    if data_id in _seen:
        return {"***CIRCULAR_REFERENCE***": True}
    _seen.add(data_id)
    
    try:
        # Get PII handler
        handler = get_pii_handler()
        
        # Use handler's anonymize functionality
        masked_data = handler.handle_pii(data, strategy=PIIHandlingStrategy.ANONYMIZE)
        
        # Handle additional fields if specified
        if additional_fields:
            for field in additional_fields:
                if field in masked_data:
                    masked_data[field] = "***MASKED***"
        
        return masked_data
        
    except Exception as e:
        logger.warning(f"Error masking PII fields: {e}")
        # Return original data on error to not break audit logging
        return data
    finally:
        _seen.discard(data_id)


def is_field_sensitive(field_name: str) -> bool:
    """
    Check if a field name indicates sensitive data
    
    Args:
        field_name: Field name to check
        
    Returns:
        True if field appears to contain sensitive data
    """
    handler = get_pii_handler()
    return field_name.lower() in handler.SENSITIVE_FIELD_NAMES


def get_default_pii_fields() -> List[str]:
    """
    Get default list of PII field names
    
    Returns:
        List of common PII field names
    """
    return [
        "email", "phone", "ssn", "credit_card", 
        "bank_account", "passport", "driver_license",
        "personal_address", "date_of_birth", "password",
        "api_key", "access_token", "refresh_token",
        "private_key", "secret", "rrn", "jumin"
    ]