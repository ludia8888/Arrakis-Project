#!/usr/bin/env python3
"""
Refactor enterprise_validation.py to be a thin integration layer
Remove duplicate validation logic that exists in core/validation
"""

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

def create_refactored_middleware():
    """Create a cleaner enterprise_validation middleware"""
    
    new_content = '''"""
Enterprise Validation Middleware

This is a thin integration layer that delegates all validation logic to core/validation.
All duplicate validation logic has been removed in favor of the core validation service.
"""

import logging
from typing import Any, Dict, Optional
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse

from core.validation.enterprise_service import (
    get_enterprise_validation_service,
    ValidationLevel,
    ValidationScope
)
from shared.cache.smart_cache import get_smart_cache_manager
from shared.events import get_event_publisher

logger = logging.getLogger(__name__)


class EnterpriseValidationMiddleware:
    """
    Enterprise validation middleware - integration layer only
    All validation logic is delegated to core validation service
    """
    
    def __init__(self, app):
        self.app = app
        self.validation_service = get_enterprise_validation_service(
            cache_manager=get_smart_cache_manager(),
            event_publisher=get_event_publisher(),
            default_level=ValidationLevel.STANDARD
        )
        
        # Entity type mapping from URL paths
        self.path_to_entity_type = {
            "/api/v1/object-types": "object_type",
            "/api/v1/properties": "property",
            "/api/v1/link-types": "link_type",
            "/api/v1/action-types": "action_type",
            "/api/v1/interfaces": "interface",
            "/api/v1/semantic-types": "semantic_type",
            "/api/v1/struct-types": "struct_type"
        }
    
    async def __call__(self, request: Request, call_next):
        """
        Middleware handler - validates requests using core service
        """
        # Skip validation for non-API paths
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        
        # Skip validation for GET requests
        if request.method == "GET":
            return await call_next(request)
        
        try:
            # Determine entity type from path
            entity_type = self._get_entity_type(request.url.path)
            if not entity_type:
                return await call_next(request)
            
            # Get request body
            body = await request.body()
            if not body:
                return await call_next(request)
            
            # Parse JSON
            import json
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Invalid JSON in request body"}
                )
            
            # Determine operation type
            operation = self._get_operation(request.method)
            
            # Get validation level from headers
            validation_level = self._get_validation_level(request.headers)
            
            # Create validation context
            context = {
                "request_id": request.headers.get("X-Request-ID", ""),
                "user_id": request.headers.get("X-User-ID", ""),
                "path": request.url.path,
                "method": request.method
            }
            
            # Validate using core service
            validation_result = await self.validation_service.validate(
                data=data,
                entity_type=entity_type,
                operation=operation,
                level=validation_level,
                context=context,
                use_cache=True
            )
            
            # Handle validation results
            if not validation_result.is_valid:
                # Convert validation errors to API response
                error_details = [
                    {
                        "field": error.field,
                        "message": error.message,
                        "code": error.code,
                        "severity": error.severity
                    }
                    for error in validation_result.errors
                    if error.severity in ["critical", "high"]
                ]
                
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "Validation failed",
                        "details": error_details,
                        "request_id": validation_result.request_id
                    }
                )
            
            # Add validation warnings to response headers if any
            if validation_result.warnings:
                request.state.validation_warnings = [
                    {"field": w.field, "message": w.message}
                    for w in validation_result.warnings
                ]
            
            # Add validation metrics to request state
            request.state.validation_metrics = {
                "duration_ms": validation_result.performance_impact_ms,
                "security_score": validation_result.security_score,
                "cache_used": validation_result.cache_used
            }
            
            # Continue with sanitized data
            if validation_result.sanitized_data:
                # Update request body with sanitized data
                request._body = json.dumps(validation_result.sanitized_data).encode()
            
            # Process request
            response = await call_next(request)
            
            # Add validation warnings to response headers
            if hasattr(request.state, "validation_warnings"):
                import json
                response.headers["X-Validation-Warnings"] = json.dumps(
                    request.state.validation_warnings
                )
            
            return response
            
        except Exception as e:
            logger.error(f"Enterprise validation middleware error: {e}")
            # Don't block request on validation errors
            return await call_next(request)
    
    def _get_entity_type(self, path: str) -> Optional[str]:
        """Map URL path to entity type"""
        for path_prefix, entity_type in self.path_to_entity_type.items():
            if path.startswith(path_prefix):
                return entity_type
        return None
    
    def _get_operation(self, method: str) -> str:
        """Map HTTP method to operation type"""
        operation_map = {
            "POST": "create",
            "PUT": "update",
            "PATCH": "update",
            "DELETE": "delete"
        }
        return operation_map.get(method, "unknown")
    
    def _get_validation_level(self, headers: Dict[str, str]) -> ValidationLevel:
        """Get validation level from request headers"""
        level_header = headers.get("X-Validation-Level", "").lower()
        
        if level_header == "minimal":
            return ValidationLevel.MINIMAL
        elif level_header == "strict":
            return ValidationLevel.STRICT
        elif level_header == "paranoid":
            return ValidationLevel.PARANOID
        else:
            return ValidationLevel.STANDARD
'''
    
    return new_content

def main():
    """Main refactoring function"""
    print("🔧 Enterprise Validation Refactoring")
    print("=" * 50)
    
    middleware_path = PROJECT_ROOT / "middleware/enterprise_validation.py"
    
    # Create new content
    new_content = create_refactored_middleware()
    
    # Write the refactored file
    with open(middleware_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("✓ Created thin integration layer middleware")
    print("✓ Removed all duplicate validation logic")
    print("✓ Now delegates to core/validation/enterprise_service")
    print("\n✅ Refactoring complete!")

if __name__ == "__main__":
    main()