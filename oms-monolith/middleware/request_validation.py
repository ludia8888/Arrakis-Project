"""
Request Validation Middleware
Validates all incoming requests against OMS schema definitions
"""
import json
import logging
from typing import Dict, Any, Optional, Set
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse

from core.validation.input_sanitization import get_input_sanitizer, SanitizationLevel

logger = logging.getLogger(__name__)


class RequestValidationMiddleware:
    """Middleware to validate requests against OMS schema"""
    
    # Paths that require schema validation
    SCHEMA_PATHS = {
        "/api/v1/schemas/{branch}/object-types",
        "/api/v1/schemas/{branch}/object-types/{type_id}/properties",
        "/api/v1/schemas/{branch}/shared-properties",
        "/api/v1/schemas/{branch}/link-types",
        "/api/v1/schemas/{branch}/action-types",
        "/api/v1/schemas/{branch}/interfaces",
        "/api/v1/schemas/{branch}/semantic-types",
        "/api/v1/schemas/{branch}/struct-types"
    }
    
    def __init__(self):
        self.sanitizer = get_input_sanitizer(SanitizationLevel.STRICT)
    
    async def __call__(self, request: Request, call_next):
        """Process request with validation"""
        
        # Skip validation for non-schema endpoints
        if not self._is_schema_endpoint(request.url.path):
            return await call_next(request)
        
        # Skip validation for GET requests
        if request.method == "GET":
            return await call_next(request)
        
        try:
            # Read request body
            body = await request.body()
            if body:
                # Store original body for downstream use
                request._body = body
                
                # Parse JSON
                try:
                    data = json.loads(body)
                except json.JSONDecodeError:
                    return JSONResponse(
                        status_code=400,
                        content={"detail": "Invalid JSON in request body"}
                    )
                
                # Validate against OMS schema
                validation_result = await self._validate_against_schema(
                    request.url.path,
                    request.method,
                    data,
                    request
                )
                
                if not validation_result["valid"]:
                    return JSONResponse(
                        status_code=400,
                        content={
                            "detail": "Schema validation failed",
                            "errors": validation_result["errors"]
                        }
                    )
                
                # Sanitize all string fields
                sanitized_data = await self._sanitize_data(data)
                
                # Store sanitized data for downstream use
                request.state.validated_data = sanitized_data
        
        except Exception as e:
            logger.error(f"Request validation error: {e}")
            # Let the request through on validation errors
            # The actual endpoint will handle validation
        
        # Continue with request
        response = await call_next(request)
        return response
    
    def _is_schema_endpoint(self, path: str) -> bool:
        """Check if path is a schema endpoint"""
        # Simple check - could be improved with regex
        return path.startswith("/api/v1/schemas/")
    
    async def _validate_against_schema(
        self,
        path: str,
        method: str,
        data: Dict[str, Any],
        request: Request
    ) -> Dict[str, Any]:
        """Validate data against OMS schema definition"""
        
        # Extract entity type from path
        path_parts = path.split("/")
        
        # Basic validation result
        result = {"valid": True, "errors": []}
        
        # Check for required fields based on entity type
        if "object-types" in path and method == "POST":
            required = ["name", "displayName"]
            for field in required:
                if field not in data:
                    result["valid"] = False
                    result["errors"].append(f"Missing required field: {field}")
        
        elif "properties" in path and method == "POST":
            required = ["name", "displayName", "dataType"]
            for field in required:
                if field not in data:
                    result["valid"] = False
                    result["errors"].append(f"Missing required field: {field}")
        
        elif "link-types" in path and method == "POST":
            required = ["name", "displayName", "sourceObjectType", "targetObjectType"]
            for field in required:
                if field not in data:
                    result["valid"] = False
                    result["errors"].append(f"Missing required field: {field}")
        
        elif "action-types" in path and method == "POST":
            required = ["name", "displayName", "targetTypes", "operations"]
            for field in required:
                if field not in data:
                    result["valid"] = False
                    result["errors"].append(f"Missing required field: {field}")
        
        # Check for unknown fields
        if hasattr(request.app.state, "services") and request.app.state.services.schema_service:
            # In production, check against actual schema
            # For now, we'll allow all fields
            pass
        
        return result
    
    async def _sanitize_data(self, data: Any) -> Any:
        """Recursively sanitize all string fields in data"""
        if isinstance(data, str):
            result = self.sanitizer.sanitize(data, SanitizationLevel.STRICT)
            return result.sanitized_value
        elif isinstance(data, dict):
            return {k: await self._sanitize_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [await self._sanitize_data(item) for item in data]
        else:
            return data


def configure_request_validation(app):
    """Configure request validation middleware"""
    import os
    
    # Check if validation is enabled
    if os.getenv("REQUEST_VALIDATION_ENABLED", "true").lower() == "false":
        logger.info("Request validation middleware DISABLED")
        return
    
    middleware = RequestValidationMiddleware()
    
    @app.middleware("http")
    async def validation_middleware(request: Request, call_next):
        return await middleware(request, call_next)
    
    logger.info("Request validation middleware configured")
