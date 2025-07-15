"""
Validator implementations for commit hook pipeline
"""
import logging
import os
import re
from typing import Any, Dict, List, Optional

from core.schema.service import SchemaService
from core.validation.input_sanitization import InputSanitizer

# Import existing validation services
from core.validation.service import ValidationService
from core.validation.tampering_detection import TamperingDetector

from .base import BaseValidator, DiffContext, ValidationError
from .validation_config import get_default_schema, validation_config

logger = logging.getLogger(__name__)


class RuleValidator(BaseValidator):
    """Adapter for existing ValidationService"""

    def __init__(self):
        self.validation_service = None

    @property
    def name(self) -> str:
        return "RuleValidator"

 async def initialize(self):
 """Initialize validation service"""
 try:
 # Initialize validation service with fallback for missing dependencies
 from core.validation.service import ValidationService

 # Create validation service instance
 self.validation_service = ValidationService()

 # Try to initialize - use fallback if database unavailable
 try:
 await self.validation_service.initialize()
 logger.info("ValidationService initialized successfully")
 except Exception as init_error:
 logger.warning(
 f"ValidationService initialization failed, using basic validation: {init_error}"
 )
 # Create a simple fallback validator
 self.validation_service = BasicValidationService()

 except ImportError as e:
 logger.warning(
 f"ValidationService not available, using basic validation: {e}"
 )
 # Create a simple fallback validator
 self.validation_service = BasicValidationService()

 async def validate(self, context: DiffContext) -> None:
 """Validate using existing rule engine"""
 if not self.validation_service:
 logger.warning(
 "ValidationService not initialized, skipping rule validation"
 )
 return

 try:
 # Extract relevant data from diff
 if context.after:
 result = await self.validation_service.validate_data(
 context.after,
 context_data={
 "user": context.meta.author,
 "branch": context.meta.branch,
 "trace_id": context.meta.trace_id,
 },
 )

 if not result.is_valid:
 raise ValidationError(
 f"Rule validation failed: {result.errors}", errors = result.errors
 )
 except Exception as e:
 logger.error(f"Rule validation error: {e}")
 strict_mode = os.getenv("STRICT_VALIDATION", "false").lower() == "true"
 if not strict_mode:
 # Validation bypass - log critical security event
 logger.critical(
 "VALIDATION_BYPASS: Rule validation error bypassed in non-strict mode. "
 f"Error: {str(e)}, Context: author={context.meta.author}, "
 f"branch={context.meta.branch}, trace_id={context.meta.trace_id}"
 )
 # Try to send to audit service
 await self._audit_validation_bypass(
 bypass_type = "rule_validation", error = str(e), context = context
 )
 else:
 raise


class TamperValidator(BaseValidator):
 """Adapter for tampering detection"""

 def __init__(self):
 self.detector = TamperingDetector()

 @property
 def name(self) -> str:
 return "TamperValidator"

 async def validate(self, context: DiffContext) -> None:
 """Check for tampering attempts"""
 try:
 # Check if protected fields are being modified
 if context.before and context.after:
 protected_fields = ["created_by", "created_at", "_id", "_rev"]

 for field in protected_fields:
 if field in context.before and field in context.after:
 if context.before[field] != context.after[field]:
 # Allow system users to modify protected fields
 if not context.meta.author.startswith("system@"):
 raise ValidationError(
 f"Tampering detected: attempt to modify protected field '{field}'",
 errors = [
 {
 "field": field,
 "error": "Protected field modification not allowed",
 }
 ],
 )

 # Use existing tampering detector for deeper checks
 suspicious_patterns = [
 r"<script[^>]*>.*?</script > ", # XSS attempts
 r"'; DROP TABLE", # SQL injection
 r"__proto__", # Prototype pollution
 r"\.\./\.\./", # Path traversal
 ]

 # Check diff content for suspicious patterns
 diff_str = str(context.diff)
 for pattern in suspicious_patterns:
 if pattern in diff_str.lower():
 logger.warning(f"Suspicious pattern detected: {pattern}")
 strict_security = (
 os.getenv("STRICT_SECURITY", "false").lower() == "true"
 )
 if strict_security:
 raise ValidationError(
 "Security validation failed: suspicious pattern detected",
 errors = [
 {"pattern": pattern, "error": "Suspicious content"}
 ],
 )
 else:
 # Security bypass - log critical security event
 logger.critical(
 f"SECURITY_BYPASS: Suspicious pattern '{pattern}' detected but not blocked in non-strict mode. "
 f"Author: {context.meta.author}, Branch: {context.meta.branch}"
 )
 # Try to send to audit service
 await self._audit_validation_bypass(
 bypass_type = "security_validation",
 error = f"Suspicious pattern: {pattern}",
 context = context,
 )

 except ValidationError:
 raise
 except Exception as e:
 logger.error(f"Tamper validation error: {e}")


class SchemaValidator(BaseValidator):
 """Validate against TerminusDB schema"""

 def __init__(self):
 self.schema_cache = {}

 @property
 def name(self) -> str:
 return "SchemaValidator"

 async def validate(self, context: DiffContext) -> None:
 """Validate document against schema"""
 if not context.after:
 return

 try:
 # Extract document type
 doc_type = context.after.get("@type")
 if not doc_type:
 logger.debug("No @type field found, skipping schema validation")
 return

 # Implement comprehensive schema validation
 try:
 await self._validate_against_schema(context.after, doc_type)
 except ValidationError:
 raise
 except Exception as e:
 logger.error(f"Schema validation error: {e}")
 raise ValidationError(f"Schema validation failed: {str(e)}")
 except Exception as e:
 logger.error(f"Unexpected error in schema validation: {e}")
 raise

 async def _validate_against_schema(self, document: Dict[str, Any], doc_type: str):
 """Comprehensive schema validation against TerminusDB schema"""

 # Get schema definition for this document type
 schema_def = await self._get_schema_definition(doc_type)

 if not schema_def:
 # Fallback to basic validation for known types
 await self._basic_type_validation(document, doc_type)
 return

 # Validate required fields
 required_fields = schema_def.get("required", [])
 missing_fields = []
 for field in required_fields:
 if field not in document:
 missing_fields.append(field)

 if missing_fields:
 raise ValidationError(
 f"Missing required fields for {doc_type}: {missing_fields}"
 )

 # Validate field types and constraints
 properties = schema_def.get("properties", {})
 for field_name, field_value in document.items():
 if field_name.startswith("@"):
 continue # Skip JSON-LD metadata

 field_schema = properties.get(field_name)
 if field_schema:
 await self._validate_field(field_name, field_value, field_schema)

 # Validate business rules
 await self._validate_business_rules(document, doc_type)

 async def _get_schema_definition(self, doc_type: str) -> Optional[Dict[str, Any]]:
 """Get schema definition from TerminusDB or cache"""
 try:
 # Try to get from TerminusDB schema endpoint
 if hasattr(self, "_terminus_client") and self._terminus_client:
 schema_query = {
 "@type": "woql:Triple",
 "subject": {"@type": "woql:Variable", "variable": "Schema"},
 "predicate": {"@type": "woql:Node", "node": "rdf:type"},
 "object": {"@type": "woql:Node", "node": f"oms:{doc_type}"},
 }

 result = await self._terminus_client.query("schema", schema_query)
 if result and result.get("bindings"):
 return self._parse_schema_from_bindings(result["bindings"])

 # Fallback to hardcoded schemas
 return self._get_default_schema(doc_type)

 except Exception as e:
 logger.warning(f"Failed to get schema for {doc_type}: {e}")
 return self._get_default_schema(doc_type)

 def _get_default_schema(self, doc_type: str) -> Optional[Dict[str, Any]]:
 """Get schema definitions from configuration (no longer hardcoded)"""
 return validation_config.get_schema(doc_type)

 async def _validate_field(
 self, field_name: str, field_value: Any, field_schema: Dict[str, Any]
 ):
 """Validate individual field against its schema"""
 field_type = field_schema.get("type")

 # Type validation
 if field_type == "string" and not isinstance(field_value, str):
 raise ValidationError(
 f"Field '{field_name}' must be a string, got {type(field_value).__name__}"
 )
 elif field_type == "number" and not isinstance(field_value, (int, float)):
 raise ValidationError(
 f"Field '{field_name}' must be a number, got {type(field_value).__name__}"
 )
 elif field_type == "boolean" and not isinstance(field_value, bool):
 raise ValidationError(
 f"Field '{field_name}' must be a boolean, got {type(field_value).__name__}"
 )
 elif field_type == "array" and not isinstance(field_value, list):
 raise ValidationError(
 f"Field '{field_name}' must be an array, got {type(field_value).__name__}"
 )
 elif field_type == "object" and not isinstance(field_value, dict):
 raise ValidationError(
 f"Field '{field_name}' must be an object, got {type(field_value).__name__}"
 )

 # String constraints
 if field_type == "string" and isinstance(field_value, str):
 min_length = field_schema.get("minLength")
 max_length = field_schema.get("maxLength")
 pattern = field_schema.get("pattern")

 if min_length and len(field_value) < min_length:
 raise ValidationError(
 f"Field '{field_name}' must be at least {min_length} characters"
 )
 if max_length and len(field_value) > max_length:
 raise ValidationError(
 f"Field '{field_name}' must be at most {max_length} characters"
 )
 if pattern:
 import re

 if not re.match(pattern, field_value):
 raise ValidationError(
 f"Field '{field_name}' does not match required pattern"
 )

 # Enum validation
 enum_values = field_schema.get("enum")
 if enum_values and field_value not in enum_values:
 raise ValidationError(
 f"Field '{field_name}' must be one of {enum_values}, got '{field_value}'"
 )

 # Format validation
 field_format = field_schema.get("format")
 if field_format == "datetime" and isinstance(field_value, str):
 try:
 from datetime import datetime

 datetime.fromisoformat(field_value.replace("Z", "+00:00"))
 except ValueError:
 raise ValidationError(
 f"Field '{field_name}' must be a valid ISO datetime"
 )

 async def _validate_business_rules(self, document: Dict[str, Any], doc_type: str):
 """Validate business-specific rules"""

 if doc_type == "ObjectType":
 # ObjectType specific rules
 name = document.get("name", "")

 # Name must not start with system prefixes
 if name.startswith(("sys:", "woql:", "rdf:", "owl:")):
 raise ValidationError(
 f"ObjectType name cannot start with reserved prefix: {name}"
 )

 # Check for naming conventions
 if not re.match(r"^[A-Z][a-zA-Z0-9_]*$", name):
 raise ValidationError(
 f"ObjectType name must follow PascalCase convention: {name}"
 )

 elif doc_type == "Branch":
 # Branch specific rules
 name = document.get("name", "")

 # Protected branch names
 if name in ["main", "master", "production", "staging"]:
 if not document.get("is_protected", False):
 raise ValidationError(
 f"Branch '{name}' must be marked as protected"
 )

 # Branch name conventions
 if not re.match(r"^[a-z0-9/_-]+$", name):
 raise ValidationError(
 f"Branch name must use lowercase with hyphens/underscores: {name}"
 )

 elif doc_type == "ValidationRule":
 # ValidationRule specific rules
 condition = document.get("condition", {})
 rule_type = document.get("rule_type", "")

 # Condition must have required fields based on rule type
 if rule_type == "schema" and "schema_path" not in condition:
 raise ValidationError(
 "Schema validation rule must have 'schema_path' in condition"
 )
 elif rule_type == "business" and "expression" not in condition:
 raise ValidationError(
 "Business validation rule must have 'expression' in condition"
 )

 async def _basic_type_validation(self, document: Dict[str, Any], doc_type: str):
 """Basic validation when no schema is available"""
 try:
 required_fields = {
 "ObjectType": ["name", "created_by", "created_at"],
 "Branch": ["name", "created_by", "created_at"],
 "ValidationRule": ["name", "rule_type", "condition"],
 }

 if doc_type in required_fields:
 missing_fields = []
 for field in required_fields[doc_type]:
 if field not in document:
 missing_fields.append(field)

 if missing_fields:
 raise ValidationError(
 f"Schema validation failed for {doc_type}",
 errors = [{"type": doc_type, "missing_fields": missing_fields}],
 )
 except ValidationError:
 raise
 except Exception as e:
 logger.error(f"Schema validation error: {e}")
 raise

 async def _audit_validation_bypass(
 self, bypass_type: str, error: str, context: DiffContext
 ):
 """Send validation bypass event to audit service"""
 try:
 # Create audit event
 audit_event = {
 "event_type": "VALIDATION_BYPASS",
 "event_category": "SECURITY",
 "severity": "WARNING",
 "bypass_type": bypass_type,
 "error": error,
 "author": context.meta.author,
 "branch": context.meta.branch,
 "trace_id": context.meta.trace_id,
 "timestamp": context.meta.timestamp.isoformat()
 if context.meta.timestamp
 else None,
 "environment": {
 "STRICT_VALIDATION": os.getenv("STRICT_VALIDATION", "false"),
 "STRICT_SECURITY": os.getenv("STRICT_SECURITY", "false"),
 },
 }

 # Log locally as backup
 logger.warning(f"VALIDATION_BYPASS_AUDIT: {audit_event}")

 # Send to audit service
 try:
 import asyncio

 import aiohttp

 audit_service_url = os.getenv(
 "AUDIT_SERVICE_URL", "http://audit-service:8000"
 )

 async with aiohttp.ClientSession() as session:
 async with session.post(
 f"{audit_service_url}/api/v2/events",
 json = audit_event,
 timeout = aiohttp.ClientTimeout(total = 5.0),
 ) as response:
 if response.status == 201:
 logger.info(
 f"Validation bypass event logged to audit service: {bypass_type}"
 )
 else:
 logger.warning(
 f"Failed to log audit event: HTTP {response.status}"
 )

 except Exception as audit_error:
 logger.error(f"Failed to send audit event to service: {audit_error}")
 # Fallback: log to local audit file
 audit_file = os.getenv(
 "LOCAL_AUDIT_FILE", "/var/log/data-kernel-audit.log"
 )
 try:
 import json

 with open(audit_file, "a") as f:
 f.write(f"{json.dumps(audit_event)}\n")
 except Exception as file_error:
 logger.error(f"Failed to write to local audit file: {file_error}")

 except Exception as e:
 logger.error(f"Failed to audit validation bypass: {e}")


class PIIValidator(BaseValidator):
 """Check for PII data in non-allowed fields"""

 def __init__(self):
 self.pii_patterns = {
 "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
 "credit_card": r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
 "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
 "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
 }
 self.allowed_fields = ["email", "contact_email", "user_email", "owner_email"]

 @property
 def name(self) -> str:
 return "PIIValidator"

 @property
 def enabled(self) -> bool:
 return os.getenv("ENABLE_PII_VALIDATION", "true").lower() == "true"

 async def validate(self, context: DiffContext) -> None:
 """Check for PII in non-allowed fields"""
 if not context.after:
 return

 try:
 import re

 errors = []

 def check_value(value: Any, field_path: str):
 if not isinstance(value, str):
 return

 # Skip allowed fields
 field_name = field_path.split(".")[-1]
 if field_name in self.allowed_fields:
 return

 # Check for PII patterns
 for pii_type, pattern in self.pii_patterns.items():
 if re.search(pattern, value, re.IGNORECASE):
 errors.append(
 {
 "field": field_path,
 "type": pii_type,
 "error": f"Potential {pii_type} detected in non-allowed field",
 }
 )

 def traverse(obj: Any, path: str = ""):
 if isinstance(obj, dict):
 for key, value in obj.items():
 new_path = f"{path}.{key}" if path else key
 traverse(value, new_path)
 elif isinstance(obj, list):
 for i, item in enumerate(obj):
 traverse(item, f"{path}[{i}]")
 else:
 check_value(obj, path)

 traverse(context.after)

 if errors:
 raise ValidationError("PII validation failed", errors = errors)

 except ValidationError:
 raise
 except Exception as e:
 logger.error(f"PII validation error: {e}")


class BasicValidationService:
 """
 Fallback validation service when full ValidationService is not available
 """

 def __init__(self):
 self.initialized = True

 async def initialize(self):
 """Initialize - no-op for basic service"""
 pass

 async def validate_data(
 self, data: Any, context_data: dict = None
 ) -> "ValidationResult":
 """Basic validation with hardcoded rules"""
 errors = []

 # Basic validation rules
 if isinstance(data, dict):
 # Check for required fields based on type
 doc_type = data.get("@type")

 required_fields_map = {
 "ObjectType": ["name", "@id"],
 "Branch": ["name", "source_branch"],
 "Property": ["name", "type", "object_type"],
 "ValidationRule": ["name", "rule_type"],
 }

 if doc_type in required_fields_map:
 required_fields = required_fields_map[doc_type]
 missing_fields = [
 field for field in required_fields if field not in data
 ]

 if missing_fields:
 errors.append(
 {
 "field": "required_fields",
 "error": f"Missing required fields: {missing_fields}",
 "code": "MISSING_REQUIRED_FIELDS",
 }
 )

 # Basic data type validation
 if "name" in data and not isinstance(data["name"], str):
 errors.append(
 {
 "field": "name",
 "error": "Name must be a string",
 "code": "INVALID_TYPE",
 }
 )

 # Basic format validation
 if "email" in data:
 import re

 email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
 if not re.match(email_pattern, str(data["email"])):
 errors.append(
 {
 "field": "email",
 "error": "Invalid email format",
 "code": "INVALID_FORMAT",
 }
 )

 # Return validation result
 return BasicValidationResult(errors)


class BasicValidationResult:
 """Basic validation result"""

 def __init__(self, errors: List[Dict[str, Any]]):
 self.errors = errors
 self.is_valid = len(errors) == 0

 def to_dict(self):
 return {"is_valid": self.is_valid, "errors": self.errors}
