"""
Enterprise Validation Integration
Provides seamless integration of the enterprise validation service
with the existing OMS infrastructure.
"""
import logging
import os
from typing import Optional

from fastapi import FastAPI
import redis.asyncio as redis

from core.validation.enterprise_service import (
    EnterpriseValidationService, ValidationLevel,
    get_enterprise_validation_service
)
from core.validation.oms_rules import register_oms_validation_rules
from middleware.enterprise_validation import configure_enterprise_validation
# Removed layer violation: validation routes should be initialized in api layer
from shared.cache.smart_cache import SmartCacheManager
from shared.events import EventPublisher


logger = logging.getLogger(__name__)


async def initialize_enterprise_validation(
    app: FastAPI,
    cache_manager: Optional[SmartCacheManager] = None,
    event_publisher: Optional[EventPublisher] = None,
    redis_url: Optional[str] = None
) -> EnterpriseValidationService:
    """
    Initialize and configure enterprise validation for the application
    
    Args:
        app: FastAPI application instance
        cache_manager: Optional cache manager instance
        event_publisher: Optional event publisher instance
        redis_url: Optional Redis URL for validation cache
    
    Returns:
        Configured EnterpriseValidationService instance
    """
    logger.info("Initializing enterprise validation service...")
    
    # Create Redis client if URL provided
    redis_client = None
    if redis_url:
        try:
            redis_client = await redis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await redis_client.ping()
            logger.info("Connected to Redis for validation cache")
        except (ConnectionError, TimeoutError) as e:
            logger.warning(f"Failed to connect to Redis: {e}. Continuing without Redis cache.")
            redis_client = None
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to connect to Redis: {e}. Continuing without Redis cache.")
            redis_client = None
        except RuntimeError as e:
            logger.warning(f"Failed to connect to Redis: {e}. Continuing without Redis cache.")
            redis_client = None
    
    # Get validation level from environment
    default_level = ValidationLevel(
        os.getenv("DEFAULT_VALIDATION_LEVEL", ValidationLevel.STANDARD.value)
    )
    
    # Create validation service
    validation_service = get_enterprise_validation_service(
        cache_manager=cache_manager,
        event_publisher=event_publisher,
        redis_client=redis_client,
        default_level=default_level
    )
    
    # Register OMS-specific validation rules
    register_oms_validation_rules(validation_service)
    # Get rule count from the service
    rule_count = len(validation_service._custom_rules) if hasattr(validation_service, '_custom_rules') else 0
    logger.info(f"Registered {rule_count} validation rules")
    
    # Configure middleware
    configure_enterprise_validation(
        app,
        validation_service=validation_service,
        default_level=default_level,
        enable_response_validation=os.getenv("VALIDATE_RESPONSES", "true").lower() == "true",
        enable_metrics=os.getenv("VALIDATION_METRICS", "true").lower() == "true",
        log_validation_errors=os.getenv("LOG_VALIDATION_ERRORS", "true").lower() == "true",
        prevent_info_disclosure=os.getenv("PREVENT_INFO_DISCLOSURE", "true").lower() == "true"
    )
    
    # API routes should be initialized in the API layer to avoid layer violation
    # The validation_service is stored in app.state for access by API routes
    
    # Store validation service in app state
    if not hasattr(app.state, "services"):
        app.state.services = type('Services', (), {})()
    
    app.state.services.validation_service = validation_service
    
    logger.info(f"Enterprise validation service initialized with level: {default_level.value}")
    
    return validation_service


def update_existing_routes_for_validation(app: FastAPI):
    """
    Update existing routes to use enterprise validation
    
    This function modifies existing route handlers to leverage
    the enterprise validation service.
    """
    logger.info("Updating existing routes for enterprise validation...")
    
    # The middleware will automatically handle validation for all routes
    # But we can add specific integrations here if needed
    
    # Example: Add validation hints to OpenAPI schema
    if hasattr(app, "openapi"):
        original_openapi = app.openapi
        
        def custom_openapi():
            if app.openapi_schema:
                return app.openapi_schema
            
            openapi_schema = original_openapi()
            
            # Add validation information to schema
            if "components" not in openapi_schema:
                openapi_schema["components"] = {}
            
            if "schemas" not in openapi_schema["components"]:
                openapi_schema["components"]["schemas"] = {}
            
            # Add validation error schema
            openapi_schema["components"]["schemas"]["ValidationError"] = {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},
                    "message": {"type": "string"},
                    "code": {"type": "string"},
                    "category": {"type": "string"},
                    "severity": {"type": "string"}
                },
                "required": ["field", "message", "code"]
            }
            
            # Add validation response schema
            openapi_schema["components"]["schemas"]["ValidationErrorResponse"] = {
                "type": "object",
                "properties": {
                    "error": {"type": "string"},
                    "request_id": {"type": "string"},
                    "errors": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/ValidationError"}
                    }
                }
            }
            
            # Update paths to include validation error responses
            for path, methods in openapi_schema.get("paths", {}).items():
                for method, operation in methods.items():
                    if method in ["post", "put", "patch"]:
                        if "responses" not in operation:
                            operation["responses"] = {}
                        
                        # Add 400 response for validation errors
                        operation["responses"]["400"] = {
                            "description": "Validation Error",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ValidationErrorResponse"}
                                }
                            }
                        }
            
            app.openapi_schema = openapi_schema
            return app.openapi_schema
        
        app.openapi = custom_openapi
    
    logger.info("Route updates completed")


async def shutdown_validation_service(app: FastAPI):
    """
    Cleanup validation service resources on shutdown
    """
    logger.info("Shutting down enterprise validation service...")
    
    if hasattr(app.state, "services") and hasattr(app.state.services, "validation_service"):
        validation_service = app.state.services.validation_service
        
        # Close Redis connection if exists
        if validation_service.validation_cache.redis_client:
            try:
                await validation_service.validation_cache.redis_client.close()
                logger.info("Closed Redis connection")
            except (ConnectionError, TimeoutError) as e:
                logger.error(f"Error closing Redis connection: {e}")
            except (ValueError, TypeError) as e:
                logger.error(f"Error closing Redis connection: {e}")
            except RuntimeError as e:
                logger.error(f"Error closing Redis connection: {e}")
        
        # Log final metrics
        metrics = validation_service.get_metrics()
        logger.info(
            f"Validation service shutdown - Total validations: {metrics.total_validations}, "
            f"Success rate: {(metrics.successful_validations / max(metrics.total_validations, 1)) * 100:.2f}%"
        )


# Example usage in main.py:
"""
from core.validation.integration import (
    initialize_enterprise_validation,
    update_existing_routes_for_validation,
    shutdown_validation_service
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await initialize_enterprise_validation(
        app,
        cache_manager=cache_manager,
        event_publisher=event_publisher,
        redis_url=config.get_redis_url() + "/1"
    )
    update_existing_routes_for_validation(app)
    
    yield
    
    # Shutdown
    await shutdown_validation_service(app)

app = FastAPI(lifespan=lifespan)
"""