"""
ETag Middleware
Handles ETag generation and validation for efficient caching using a decorator-based approach
and resilience patterns.
"""
from typing import Callable, Optional, Dict, Any
from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from starlette.responses import JSONResponse
import json
import hashlib
from datetime import datetime, timezone
import time
import asyncio
import os
from functools import wraps
from prometheus_client import Counter, Histogram, Gauge

from core.versioning.version_service import get_version_service
from models.etag import DeltaRequest
from core.auth import UserContext
from common_logging.setup import get_logger
from middleware.etag_analytics import get_etag_analytics
from bootstrap.config import get_config
from core.resilience.version_service_wrapper import get_resilient_version_service

logger = get_logger(__name__)

# --- Resilience Configuration ---
ETAG_SERVICE_TIMEOUT = 0.5  # 500ms timeout for version_service calls

# --- Prometheus Metrics ---
# (Metrics definitions remain unchanged)
etag_requests_total = Counter(
    'etag_requests_total', 'Total number of ETag requests', ['method', 'resource_type', 'result']
)
etag_cache_hits = Counter(
    'etag_cache_hits_total', 'Number of ETag cache hits (304 responses)', ['resource_type']
)
etag_cache_misses = Counter(
    'etag_cache_misses_total', 'Number of ETag cache misses (200 responses with ETag)', ['resource_type']
)
etag_validation_duration = Histogram(
    'etag_validation_duration_seconds', 'Time spent validating ETags', ['resource_type']
)
etag_generation_duration = Histogram(
    'etag_generation_duration_seconds', 'Time spent generating ETags', ['resource_type']
)
etag_cache_effectiveness = Gauge(
    'etag_cache_effectiveness_ratio', 'Cache hit ratio (hits / total requests)', ['resource_type']
)

# --- Decorator for enabling ETag on routes ---

def enable_etag(resource_type_func: Callable[[Dict], str], resource_id_func: Callable[[Dict], str], branch_func: Callable[[Dict], str]):
    """
    Decorator to enable ETag handling for a specific FastAPI route.
    Instead of static strings, this now accepts functions that extract
    the necessary info from path parameters, allowing for more flexible
    and complex URL structures.

    Args:
        resource_type_func: A function that takes path_params and returns the resource type.
        resource_id_func: A function that takes path_params and returns the resource ID.
        branch_func: A function that takes path_params and returns the branch name.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        
        # Attach metadata to the endpoint function for the middleware to find
        wrapper._etag_info = {
            "resource_type_func": resource_type_func,
            "resource_id_func": resource_id_func,
            "branch_func": branch_func,
        }
        return wrapper
    return decorator


class ETagMiddleware(BaseHTTPMiddleware):
    """
    Middleware for handling ETags and conditional requests.
    This version uses a decorator-based approach for safety and maintainability
    and includes resilience patterns (timeout, fallback) for service calls.
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.config = get_config()
        self.timeout = self.config.service.resilience_timeout
        self.version_service = None
        self.analytics = get_etag_analytics()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with ETag handling"""
        # Check if E-Tag caching is enabled
        if not os.getenv('ENABLE_ETAG_CACHING', 'false').lower() == 'true':
            return await call_next(request)

        # Initialize version service if needed (lazy initialization)
        if not self.version_service:
            # Get redis client from app state
            redis_client = getattr(request.app.state, 'redis_client', None)
            if redis_client:
                self.version_service = await get_resilient_version_service(redis_client)
            else:
                # Skip ETag functionality if redis is not available
                logger.warning("Redis client not available, skipping ETag functionality")
                return await call_next(request)

        # Process the request normally first
        response = await call_next(request)
        
        # For GET requests with conditional headers, check if we can return 304
        if request.method == "GET":
            if_none_match = request.headers.get("If-None-Match")
            if if_none_match:
                # Check if the endpoint has ETag enabled (after routing)
                etag_info = self._get_etag_info_from_request(request)
                if etag_info:
                    # Extract resource context using functions provided by the decorator
                    resource_ctx = self._build_resource_context(request.path_params, etag_info)
                    if resource_ctx:
                        # --- Resilience Pattern: Timeout and Fallback ---
                        try:
                            start_time = time.time()
                            # Validate ETag with a strict timeout
                            is_valid, _ = await asyncio.wait_for(
                                self.version_service.validate_etag(
                                    resource_type=resource_ctx["type"],
                                    resource_id=resource_ctx["id"],
                                    branch=resource_ctx["branch"],
                                    client_etag=if_none_match
                                ),
                                timeout=self.timeout
                            )
                            validation_time = time.time() - start_time
                            etag_validation_duration.labels(resource_type=resource_ctx["type"]).observe(validation_time)

                            if is_valid:
                                # Cache hit - return 304 Not Modified
                                etag_cache_hits.labels(resource_type=resource_ctx["type"]).inc()
                                etag_requests_total.labels(method='GET', resource_type=resource_ctx["type"], result="cache_hit").inc()
                                logger.info("ETag cache hit", extra={"resource_ctx": resource_ctx, "etag": if_none_match})
                                self.analytics.record_request(resource_type=resource_ctx["type"], is_cache_hit=True, etag=if_none_match)
                                return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": if_none_match})

                        except asyncio.TimeoutError:
                            # Fallback: ETag 검사를 포기하고 실제 응답 반환
                            logger.warning(
                                "ETag version service timed out, bypassing ETag check",
                                timeout=self.timeout
                            )
                            self.analytics.record_timeout()
                        except Exception as e:
                            logger.error(f"ETag validation failed with an unexpected error: {e}", extra={"resource_ctx": resource_ctx})
            
        # Now check if the endpoint has ETag enabled (after routing)
        etag_info = self._get_etag_info_from_request(request)
        if not etag_info:
            return response

        # Extract resource context using functions provided by the decorator
        resource_ctx = self._build_resource_context(request.path_params, etag_info)
        if not resource_ctx:
            logger.warning(f"ETag: Could not build resource context for {request.url.path}")
            return response
        
        # Add ETag to successful GET responses
        if response.status_code == 200 and request.method == "GET":
            # --- Resilience Pattern: Timeout and Fallback ---
            try:
                start_time = time.time()
                # Get resource version with a strict timeout
                version = await asyncio.wait_for(
                    self.version_service.get_resource_version(
                        resource_type=resource_ctx["type"],
                        resource_id=resource_ctx["id"],
                        branch=resource_ctx["branch"]
                    ),
                    timeout=self.timeout
                )
                generation_time = time.time() - start_time
                etag_generation_duration.labels(resource_type=resource_ctx["type"]).observe(generation_time)

                if version:
                    response.headers["ETag"] = version.current_version.etag
                    response.headers["X-Version"] = str(version.current_version.version)
                    etag_cache_misses.labels(resource_type=resource_ctx["type"]).inc()
                    etag_requests_total.labels(method='GET', resource_type=resource_ctx["type"], result="cache_miss").inc()
                    logger.info("ETag cache miss - generated new ETag", extra={"resource_ctx": resource_ctx, "etag": version.current_version.etag})
                    self.analytics.record_request(resource_type=resource_ctx["type"], is_cache_hit=False, etag=version.current_version.etag)
                    self._update_cache_effectiveness(resource_ctx["type"])
                else:
                    # No version found, create initial version based on response content
                    try:
                        from core.auth_utils import UserContext
                        
                        # Get response content for hashing
                        response_body = b""
                        if hasattr(response, 'body'):
                            response_body = response.body
                        elif hasattr(response, 'content'):
                            response_body = response.content
                            
                        # Create a user context for version creation
                        user_context = UserContext(
                            user_id="system",
                            username="system",
                            email="system@oms.local",
                            roles=["system"],
                            tenant_id="default"
                        )
                        
                        # Create initial version
                        import json
                        content_dict = {}
                        try:
                            content_str = response_body.decode('utf-8') if response_body else "{}"
                            content_dict = json.loads(content_str) if content_str != "{}" else {}
                        except:
                            content_dict = {"raw_content": response_body.decode('utf-8', errors='ignore')}
                            
                        initial_version = await self.version_service.track_change(
                            resource_type=resource_ctx["type"],
                            resource_id=resource_ctx["id"],
                            branch=resource_ctx["branch"],
                            content=content_dict,
                            change_type="initial_version",
                            user=user_context,
                            change_summary="Initial version created by ETag middleware"
                        )
                        
                        if initial_version:
                            response.headers["ETag"] = initial_version.current_version.etag
                            response.headers["X-Version"] = str(initial_version.current_version.version)
                            logger.info("ETag - created initial version", extra={
                                "resource_ctx": resource_ctx, 
                                "etag": initial_version.current_version.etag
                            })
                        
                    except Exception as e:
                        logger.error(f"Failed to create initial ETag version: {e}", extra={"resource_ctx": resource_ctx})

            except asyncio.TimeoutError:
                # Fallback: ETag 검사를 포기하고 실제 응답 반환
                logger.warning(
                    "ETag version service timed out, bypassing ETag check",
                    timeout=self.timeout
                )
                self.analytics.record_timeout()
                return await call_next(request)
            except Exception as e:
                logger.error(f"ETag generation failed with an unexpected error: {e}", extra={"resource_ctx": resource_ctx})

        return response

    def _get_etag_info_from_request(self, request: Request) -> Optional[Dict[str, Any]]:
        """Check if the matched route's endpoint has ETag info attached by the decorator."""
        # Try multiple ways to get the endpoint
        endpoint = request.scope.get("endpoint")
        route = request.scope.get("route")
        path = request.scope.get("path")
        
        logger.debug(f"Request scope keys: {list(request.scope.keys())}")
        logger.debug(f"Endpoint: {endpoint}, Route: {route}, Path: {path}")
        
        # If endpoint is not directly available, try to extract from route
        if not endpoint and route:
            endpoint = getattr(route, "endpoint", None)
            logger.debug(f"Got endpoint from route: {endpoint}")
        
        # Check various ways the ETag info might be attached
        if endpoint:
            # Direct attachment
            if hasattr(endpoint, "_etag_info"):
                logger.debug(f"Found ETag info directly on endpoint")
                return endpoint._etag_info
            
            # Check wrapped function (common with @inject decorator)
            if hasattr(endpoint, "__wrapped__"):
                wrapped = endpoint.__wrapped__
                logger.debug(f"Checking wrapped function: {wrapped}")
                if hasattr(wrapped, "_etag_info"):
                    logger.debug(f"Found ETag info on wrapped endpoint")
                    return wrapped._etag_info
                
                # Check double wrapped (when multiple decorators are used)
                if hasattr(wrapped, "__wrapped__") and hasattr(wrapped.__wrapped__, "_etag_info"):
                    logger.debug(f"Found ETag info on double-wrapped endpoint")
                    return wrapped.__wrapped__._etag_info
            
            # Check if it's a dependency_injector wrapped function
            if hasattr(endpoint, "func") and hasattr(endpoint.func, "_etag_info"):
                logger.debug(f"Found ETag info on DI wrapped function")
                return endpoint.func._etag_info
            
            # Last resort: check all attributes
            for attr_name in dir(endpoint):
                if not attr_name.startswith('_'):
                    attr = getattr(endpoint, attr_name, None)
                    if attr and hasattr(attr, "_etag_info"):
                        logger.debug(f"Found ETag info on attribute {attr_name}")
                        return attr._etag_info
        
        logger.debug(f"No ETag info found for {request.url.path}")
        return None

    def _build_resource_context(self, path_params: Dict, etag_info: Dict[str, Callable]) -> Optional[Dict[str, str]]:
        """Build the resource context using the extractor functions from the decorator."""
        try:
            return {
                "type": etag_info["resource_type_func"](path_params),
                "id": etag_info["resource_id_func"](path_params),
                "branch": etag_info["branch_func"](path_params),
            }
        except (KeyError, Exception) as e:
            logger.error(f"Failed to build resource context from path_params: {path_params} and etag_info. Error: {e}")
            return None

    def _update_cache_effectiveness(self, resource_type: str):
        """Updates the Prometheus Gauge for cache effectiveness."""
        # This function can be simplified as Prometheus can compute ratios with `rate()`
        pass

# (The function to add the middleware to the app remains the same)
def configure_etag_middleware(app):
    """Adds the ETagMiddleware to the FastAPI application."""
    app.add_middleware(ETagMiddleware)
    logger.info("ETag middleware configured")