# Mock common_security package for development/testing
import hashlib
import base64
import json
import os
from typing import Any, Dict, Optional, List, Union
from datetime import datetime, timedelta
import time

class SecurityConfig:
    """Security configuration class"""
    def __init__(self):
        self.encryption_key = os.getenv("ENCRYPTION_KEY", "default-dev-key")
        self.hash_algorithm = "sha256"
        self.token_expiry = 3600  # 1 hour

# Encryption/Decryption functions (simplified for development)
def encrypt(data: bytes) -> bytes:
    """Mock encryption - just base64 encode for development"""
    return base64.b64encode(data)

def decrypt(data: bytes) -> bytes:
    """Mock decryption - just base64 decode for development"""
    return base64.b64decode(data)

def encrypt_text(text: str) -> str:
    """Encrypt text data"""
    return base64.b64encode(text.encode()).decode()

def decrypt_text(encrypted_text: str) -> str:
    """Decrypt text data"""
    return base64.b64decode(encrypted_text.encode()).decode()

# Hashing functions
def hash_data(data: Union[str, bytes]) -> str:
    """Hash data using SHA256"""
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()

# Validation functions
def validate_input(data: Any) -> Any:
    """Validate input data"""
    # Simple validation - in production would do more
    if isinstance(data, str):
        # Remove potentially dangerous characters
        return data.replace("<", "&lt;").replace(">", "&gt;")
    return data

def validate_email(email: str) -> bool:
    """Validate email format"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password: str) -> Dict[str, Any]:
    """Validate password strength"""
    issues = []
    if len(password) < 8:
        issues.append("Password must be at least 8 characters")
    if not any(c.isupper() for c in password):
        issues.append("Password must contain uppercase letters")
    if not any(c.islower() for c in password):
        issues.append("Password must contain lowercase letters")
    if not any(c.isdigit() for c in password):
        issues.append("Password must contain numbers")
    
    return {
        "valid": len(issues) == 0,
        "issues": issues
    }

# Token functions
def generate_token(payload: Dict[str, Any], expiry_seconds: int = 3600) -> str:
    """Generate a simple token"""
    payload["exp"] = time.time() + expiry_seconds
    token_data = json.dumps(payload)
    return encrypt_text(token_data)

def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify and decode token"""
    try:
        token_data = decrypt_text(token)
        payload = json.loads(token_data)
        
        if payload.get("exp", 0) < time.time():
            return None  # Token expired
            
        return payload
    except:
        return None

# Signature functions
def sign_data(data: Union[str, bytes], key: Optional[str] = None) -> str:
    """Sign data with HMAC"""
    import hmac
    if isinstance(data, str):
        data = data.encode()
    if key is None:
        key = os.getenv("SIGNING_KEY", "default-signing-key")
    
    signature = hmac.new(key.encode(), data, hashlib.sha256)
    return signature.hexdigest()

def calculate_hmac(data: Union[str, bytes], key: Optional[str] = None) -> str:
    """Calculate HMAC for data - alias for sign_data"""
    return sign_data(data, key)

def verify_signature(data: Union[str, bytes], signature: str, key: Optional[str] = None) -> bool:
    """Verify HMAC signature"""
    expected_signature = sign_data(data, key)
    return expected_signature == signature

def verify_hmac(data: Union[str, bytes], signature: str, key: Optional[str] = None) -> bool:
    """Verify HMAC - alias for verify_signature"""
    return verify_signature(data, signature, key)

def sign(data: Union[str, bytes], key: Optional[str] = None) -> str:
    """Sign data - alias for sign_data"""
    return sign_data(data, key)

def verify(data: Union[str, bytes], signature: str, key: Optional[str] = None) -> bool:
    """Verify signature - alias for verify_signature"""
    return verify_signature(data, signature, key)

# Key management
def generate_key(length: int = 32) -> str:
    """Generate random key"""
    import secrets
    return secrets.token_hex(length)

def generate_signing_key(length: int = 32) -> str:
    """Generate signing key - alias for generate_key"""
    return generate_key(length)

def derive_key(master_key: str, context: str) -> str:
    """Derive a key from master key and context"""
    return hash_data(f"{master_key}:{context}")

# Sanitization functions
def sanitize_html(html: str) -> str:
    """Remove potentially dangerous HTML"""
    # Simple implementation - in production use bleach or similar
    dangerous_tags = ['script', 'iframe', 'object', 'embed']
    result = html
    for tag in dangerous_tags:
        result = result.replace(f"<{tag}", f"&lt;{tag}")
        result = result.replace(f"</{tag}>", f"&lt;/{tag}&gt;")
    return result

def sanitize_sql(query: str) -> str:
    """Basic SQL injection prevention"""
    # In production, use parameterized queries instead
    dangerous_chars = ["'", '"', ";", "--", "/*", "*/"]
    result = query
    for char in dangerous_chars:
        result = result.replace(char, "")
    return result

# Rate limiting
_rate_limit_cache = {}

def check_rate_limit(key: str, max_requests: int = 100, window_seconds: int = 60) -> bool:
    """Simple rate limiting check"""
    now = time.time()
    window_start = now - window_seconds
    
    if key not in _rate_limit_cache:
        _rate_limit_cache[key] = []
    
    # Clean old entries
    _rate_limit_cache[key] = [t for t in _rate_limit_cache[key] if t > window_start]
    
    # Check limit
    if len(_rate_limit_cache[key]) >= max_requests:
        return False
    
    # Add current request
    _rate_limit_cache[key].append(now)
    return True

# Audit functions
def audit_log(event: str, user_id: Optional[str] = None, details: Optional[Dict] = None):
    """Log security audit event"""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event": event,
        "user_id": user_id,
        "details": details or {}
    }
    # In production, send to audit service
    print(f"AUDIT: {json.dumps(log_entry)}")

# Export additional commonly used functions
def mask_sensitive_data(data: str, visible_chars: int = 4) -> str:
    """Mask sensitive data showing only last N characters"""
    if len(data) <= visible_chars:
        return "*" * len(data)
    return "*" * (len(data) - visible_chars) + data[-visible_chars:]

def is_safe_url(url: str, allowed_hosts: Optional[List[str]] = None) -> bool:
    """Check if URL is safe for redirection"""
    from urllib.parse import urlparse
    
    if not url:
        return False
        
    parsed = urlparse(url)
    
    # Check for javascript: or data: URLs
    if parsed.scheme in ['javascript', 'data']:
        return False
    
    # If allowed_hosts is specified, check against it
    if allowed_hosts and parsed.netloc not in allowed_hosts:
        return False
    
    return True
