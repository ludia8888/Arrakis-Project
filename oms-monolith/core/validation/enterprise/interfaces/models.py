"""
Enterprise validation data models and enumerations
"""

from typing import Dict, Any, List, Optional
from enum import Enum
from pydantic import BaseModel, Field


class ValidationLevel(str, Enum):
    """Validation strictness levels"""
    MINIMAL = "minimal"      # Basic type checking only
    STANDARD = "standard"    # Standard validation with business rules
    STRICT = "strict"        # All validations including custom rules
    PARANOID = "paranoid"    # Maximum security with deep inspection


class ValidationScope(str, Enum):
    """Validation scope types"""
    REQUEST = "request"      # Incoming request validation
    RESPONSE = "response"    # Outgoing response validation
    SCHEMA = "schema"        # Schema change validation
    DATA = "data"           # Data integrity validation
    SECURITY = "security"   # Security-focused validation


class ValidationCategory(str, Enum):
    """Validation error categories"""
    SYNTAX = "syntax"
    SEMANTIC = "semantic"
    SECURITY = "security"
    BUSINESS = "business"
    PERFORMANCE = "performance"


class ValidationError(BaseModel):
    """Structured validation error"""
    field: str
    message: str
    category: ValidationCategory
    severity: str  # critical, high, medium, low
    code: str
    context: Dict[str, Any] = {}
    suggested_fix: Optional[str] = None


class ValidationMetrics(BaseModel):
    """Validation performance metrics"""
    total_validations: int = 0
    successful_validations: int = 0
    failed_validations: int = 0
    security_threats_detected: int = 0
    average_validation_time_ms: float = 0
    cache_hits: int = 0
    cache_misses: int = 0
    validation_by_type: Dict[str, int] = {}
    errors_by_category: Dict[str, int] = {}


class ValidationResult(BaseModel):
    """Comprehensive validation result"""
    request_id: str
    is_valid: bool
    validation_level: ValidationLevel
    errors: List[ValidationError] = []
    warnings: List[ValidationError] = []
    sanitized_data: Optional[Dict[str, Any]] = None
    security_score: int = 100  # 0-100, lower is worse
    performance_impact_ms: float = 0
    cache_used: bool = False
    metadata: Dict[str, Any] = {}


class ValidationConfig(BaseModel):
    """Validation service configuration"""
    # Security settings
    max_security_score_threshold: int = 70
    enable_input_sanitization: bool = True
    enable_security_validation: bool = True
    
    # Performance settings
    enable_caching: bool = True
    cache_ttl_seconds: int = 300
    max_cache_size: int = 10000
    
    # Validation settings
    default_validation_level: ValidationLevel = ValidationLevel.STANDARD
    enable_schema_validation: bool = True
    enable_business_rules: bool = True
    
    # Rate limiting
    enable_rate_limiting: bool = True
    rate_limit_per_minute: int = 1000
    
    # Monitoring
    enable_metrics: bool = True
    metrics_flush_interval_seconds: int = 60