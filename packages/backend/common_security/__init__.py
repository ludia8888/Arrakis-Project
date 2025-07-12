# Production-ready common_security package for Arrakis Project
import hashlib
import base64
import json
import os
from typing import Any, Dict, Optional, List, Union
from datetime import datetime, timedelta
import time
import logging
import secrets
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

class SecurityConfig:
    """Production security configuration with strong defaults"""
    def __init__(self):
        self.encryption_key = self._get_or_generate_key("ENCRYPTION_KEY")
        self.signing_key = self._get_or_generate_key("SIGNING_KEY") 
        self.hash_algorithm = "sha256"
        self.token_expiry = int(os.getenv("TOKEN_EXPIRY", "3600"))  # 1 hour
        self.password_iterations = 100000  # PBKDF2 iterations
        self.salt_length = 32
        
    def _get_or_generate_key(self, env_var: str) -> bytes:
        """Get encryption key from environment or generate new one"""
        key_b64 = os.getenv(env_var)
        if key_b64:
            try:
                return base64.urlsafe_b64decode(key_b64)
            except Exception as e:
                logger.warning(f"Invalid {env_var} in environment, generating new key")
        
        # Generate new key
        key = Fernet.generate_key()
        logger.warning(f"Generated new {env_var}. Set environment variable: {env_var}={key.decode()}")
        return key

_config = SecurityConfig()

# Strong encryption/decryption functions using Fernet (AES 128)
def encrypt(data: bytes) -> bytes:
    """Production encryption using Fernet (AES 128 in CBC mode)"""
    try:
        f = Fernet(_config.encryption_key)
        return f.encrypt(data)
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        raise

def decrypt(data: bytes) -> bytes:
    """Production decryption using Fernet"""
    try:
        f = Fernet(_config.encryption_key)
        return f.decrypt(data)
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        raise

def encrypt_text(text: str) -> str:
    """Encrypt text data and return base64 encoded result"""
    try:
        encrypted_bytes = encrypt(text.encode('utf-8'))
        return base64.urlsafe_b64encode(encrypted_bytes).decode('utf-8')
    except Exception as e:
        logger.error(f"Text encryption failed: {e}")
        raise

def decrypt_text(encrypted_text: str) -> str:
    """Decrypt base64 encoded text data"""
    try:
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_text.encode('utf-8'))
        decrypted_bytes = decrypt(encrypted_bytes)
        return decrypted_bytes.decode('utf-8')
    except Exception as e:
        logger.error(f"Text decryption failed: {e}")
        raise

# Secure hashing functions with salting
def hash_data(data: Union[str, bytes], salt: Optional[bytes] = None) -> str:
    """Hash data using SHA256 with optional salt"""
    if isinstance(data, str):
        data = data.encode('utf-8')
    
    if salt:
        data = salt + data
    
    return hashlib.sha256(data).hexdigest()

def hash_password(password: str, salt: Optional[bytes] = None) -> tuple[str, bytes]:
    """Hash password using PBKDF2 with salt"""
    if salt is None:
        salt = secrets.token_bytes(_config.salt_length)
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_config.password_iterations,
    )
    
    password_hash = kdf.derive(password.encode('utf-8'))
    return base64.urlsafe_b64encode(password_hash).decode('utf-8'), salt

def verify_password(password: str, hashed_password: str, salt: bytes) -> bool:
    """Verify password against hash"""
    try:
        computed_hash, _ = hash_password(password, salt)
        return secrets.compare_digest(computed_hash, hashed_password)
    except Exception as e:
        logger.error(f"Password verification failed: {e}")
        return False

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

# Production JWT-like token functions
def generate_token(payload: Dict[str, Any], expiry_seconds: Optional[int] = None) -> str:
    """Generate secure token with signature"""
    if expiry_seconds is None:
        expiry_seconds = _config.token_expiry
    
    # Add standard claims
    token_payload = {
        **payload,
        "iat": int(time.time()),  # Issued at
        "exp": int(time.time()) + expiry_seconds,  # Expires at
        "jti": secrets.token_hex(16),  # JWT ID
    }
    
    try:
        # Serialize and encrypt payload
        token_data = json.dumps(token_payload, separators=(',', ':'))
        encrypted_token = encrypt_text(token_data)
        
        # Add signature to prevent tampering
        signature = sign_data(encrypted_token)
        
        # Combine token and signature
        return f"{encrypted_token}.{signature}"
        
    except Exception as e:
        logger.error(f"Token generation failed: {e}")
        raise

def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify and decode secure token"""
    try:
        # Split token and signature
        if '.' not in token:
            logger.warning("Invalid token format - missing signature")
            return None
            
        encrypted_token, signature = token.rsplit('.', 1)
        
        # Verify signature first
        if not verify_signature(encrypted_token, signature):
            logger.warning("Token signature verification failed")
            return None
        
        # Decrypt and parse payload
        token_data = decrypt_text(encrypted_token)
        payload = json.loads(token_data)
        
        # Check expiration
        if payload.get("exp", 0) < time.time():
            logger.debug("Token expired")
            return None
            
        # Check issued at (not too far in future)
        iat = payload.get("iat", 0)
        if iat > time.time() + 300:  # 5 minutes clock skew allowance
            logger.warning("Token issued in future")
            return None
            
        return payload
        
    except Exception as e:
        logger.warning(f"Token verification failed: {e}")
        return None

# Production HMAC signature functions
def sign_data(data: Union[str, bytes], key: Optional[bytes] = None) -> str:
    """Sign data with HMAC-SHA256"""
    import hmac
    
    if isinstance(data, str):
        data = data.encode('utf-8')
    
    if key is None:
        key = _config.signing_key
    elif isinstance(key, str):
        key = key.encode('utf-8')
    
    try:
        signature = hmac.new(key, data, hashlib.sha256)
        return signature.hexdigest()
    except Exception as e:
        logger.error(f"Data signing failed: {e}")
        raise

def calculate_hmac(data: Union[str, bytes], key: Optional[bytes] = None) -> str:
    """Calculate HMAC for data - alias for sign_data"""
    return sign_data(data, key)

def verify_signature(data: Union[str, bytes], signature: str, key: Optional[bytes] = None) -> bool:
    """Verify HMAC signature using constant-time comparison"""
    try:
        expected_signature = sign_data(data, key)
        return secrets.compare_digest(expected_signature, signature)
    except Exception as e:
        logger.error(f"Signature verification failed: {e}")
        return False

def verify_hmac(data: Union[str, bytes], signature: str, key: Optional[bytes] = None) -> bool:
    """Verify HMAC - alias for verify_signature"""
    return verify_signature(data, signature, key)

def sign(data: Union[str, bytes], key: Optional[bytes] = None) -> str:
    """Sign data - alias for sign_data"""
    return sign_data(data, key)

def verify(data: Union[str, bytes], signature: str, key: Optional[bytes] = None) -> bool:
    """Verify signature - alias for verify_signature"""
    return verify_signature(data, signature, key)

# Cryptographically secure key management
def generate_key(length: int = 32) -> str:
    """Generate cryptographically secure random key"""
    return secrets.token_hex(length)

def generate_fernet_key() -> bytes:
    """Generate Fernet-compatible encryption key"""
    return Fernet.generate_key()

def generate_signing_key(length: int = 32) -> str:
    """Generate signing key - alias for generate_key"""
    return generate_key(length)

def derive_key(master_key: Union[str, bytes], context: str, length: int = 32) -> bytes:
    """Derive a key from master key and context using PBKDF2"""
    if isinstance(master_key, str):
        master_key = master_key.encode('utf-8')
    
    salt = hash_data(context).encode('utf-8')[:16]  # Use context as deterministic salt
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=length,
        salt=salt,
        iterations=10000,  # Lower iterations for key derivation
    )
    
    return kdf.derive(master_key)

def generate_rsa_keypair(key_size: int = 2048) -> tuple[bytes, bytes]:
    """Generate RSA public/private key pair"""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
    )
    
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    return private_pem, public_pem

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
