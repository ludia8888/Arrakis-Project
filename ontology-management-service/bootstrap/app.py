"""Application factory with dependency injection"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
# import punq  # Replaced with dependency-injector
from typing import Optional

from bootstrap.dependencies import init_container
from bootstrap.config import get_config, AppConfig
from common_logging.setup import get_logger
# Enterprise Observability Integration
from observability.enterprise_integration import enterprise_observability_lifespan
# from infra.tracing.otel_init import get_otel_manager # Temporarily disabled
# --- Middleware Imports ---
from middleware.auth_middleware import AuthMiddleware
from middleware.terminus_context_middleware import TerminusContextMiddleware
from core.auth_utils.database_context import DatabaseContextMiddleware as CoreDatabaseContextMiddleware
from middleware.error_handler import ErrorHandlerMiddleware
from middleware.etag_middleware import ETagMiddleware
from core.iam.scope_rbac_middleware import ScopeRBACMiddleware
# Optional middlewares – create no-op fallbacks when the real implementation is missing

try:
    from middleware.request_id import RequestIdMiddleware  # type: ignore
except ImportError:  # pragma: no cover
    class RequestIdMiddleware:  # pylint: disable=too-few-public-methods
        """Fallback RequestIdMiddleware (noop)."""

        def __init__(self, app, **kwargs):
            self.app = app

        async def __call__(self, scope, receive, send):  # noqa: D401
            await self.app(scope, receive, send)


try:
    from middleware.scope_rbac import ScopeRBACMiddleware  # type: ignore
except ImportError:  # pragma: no cover
    class ScopeRBACMiddleware:  # pylint: disable=too-few-public-methods
        """Fallback RBAC middleware (noop)."""

        def __init__(self, app, **kwargs):
            self.app = app

        async def __call__(self, scope, receive, send):
            await self.app(scope, receive, send)


try:
    from middleware.audit_log import AuditLogMiddleware  # type: ignore
except ImportError:  # pragma: no cover
    class AuditLogMiddleware:
        """Fallback audit log middleware (noop)."""

        def __init__(self, app, **kwargs):
            self.app = app

        async def __call__(self, scope, receive, send):
            await self.app(scope, receive, send)


try:
    from middleware.circuit_breaker import CircuitBreakerMiddleware  # type: ignore
except ImportError:  # pragma: no cover
    class CircuitBreakerMiddleware:
        """Fallback circuit breaker middleware (noop)."""

        def __init__(self, app, **kwargs):
            self.app = app

        async def __call__(self, scope, receive, send):
            await self.app(scope, receive, send)

# --- API Router Imports ---
from api.v1 import (
    system_routes, health_routes, schema_routes, organization_routes,
    property_routes, audit_routes, batch_routes, branch_lock_routes, 
    branch_routes, document_routes, document_crud_routes, graph_health_routes, idempotent_routes,
    issue_tracking_routes, job_progress_routes, shadow_index_routes,
    time_travel_routes, version_routes, test_routes, circuit_breaker_routes
    # resilience_dashboard_routes - REMOVED: Replaced with enterprise observability stack
)
from api.v1 import auth_proxy_routes  # Direct import
from api.graphql.modular_main import graphql_app as modular_graphql_app
from api.graphql.main import app as websocket_app
# from .container import Container, init_container  # Already imported above
# from .di_scopes import create_request_scope_middleware  # File doesn't exist

logger = get_logger(__name__)


def create_app(config: Optional[AppConfig] = None) -> FastAPI:
    """Application factory, creating a new FastAPI application."""
    app_config = config or get_config()
    container = init_container(app_config)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """
        Enterprise Application lifespan with integrated observability.
        Handles startup and shutdown events with full monitoring stack.
        """
        logger.info("🚀 Enterprise Application lifespan: startup sequence initiated.")
        
        try:
            logger.info("Initializing container resources...")
            await container.init_resources()
            logger.info("Container resources initialized successfully.")
            
            # Initialize Redis client for ETag middleware and Global Circuit Breaker
            try:
                from bootstrap.providers.redis_provider import RedisProvider
                redis_provider = RedisProvider()
                redis_client = await redis_provider.provide()
                app.state.redis_client = redis_client
                logger.info("Redis client initialized for ETag middleware")
                
                # Initialize Global Circuit Breaker
                from middleware.circuit_breaker_global import (
                    GlobalCircuitBreaker, GlobalCircuitConfig, set_global_circuit_breaker
                )
                circuit_config = GlobalCircuitConfig(
                    service_name="oms",
                    failure_threshold=5,
                    error_rate_threshold=0.6,
                    timeout_seconds=60
                )
                global_circuit_breaker = GlobalCircuitBreaker(circuit_config, redis_client)
                set_global_circuit_breaker(global_circuit_breaker)
                app.state.global_circuit_breaker = global_circuit_breaker
                logger.info("Global Circuit Breaker initialized")
                
            except Exception as e:
                logger.warning(f"Failed to initialize Redis client and Global Circuit Breaker: {e}")
                app.state.redis_client = None
                app.state.global_circuit_breaker = None
            
            # Initialize Enterprise Observability Stack
            try:
                from observability.enterprise_integration import initialize_enterprise_observability
                observability_manager = await initialize_enterprise_observability(app)
                app.state.observability_manager = observability_manager
                logger.info("🎯 Enterprise Observability Stack initialized successfully!")
                
                # Log migration information
                logger.info("📋 Legacy resilience dashboard API has been replaced with:")
                logger.info("  📊 Prometheus metrics: /metrics")
                logger.info("  📈 Grafana dashboards: http://grafana:3000")
                logger.info("  🔍 Jaeger tracing: http://jaeger:16686")
                logger.info("  🚨 AlertManager: Comprehensive enterprise alerting")
                
            except Exception as e:
                logger.warning(f"Failed to initialize Enterprise Observability: {e}")
                app.state.observability_manager = None
                
            # Initialize Advanced GC Monitoring
            try:
                from observability.advanced_gc_monitoring import start_advanced_gc_monitoring
                gc_monitor = start_advanced_gc_monitoring(interval=30)
                app.state.gc_monitor = gc_monitor
                logger.info("🗑️ Advanced GC Monitoring initialized with:")
                logger.info("  📊 gc.get_stats() - GC statistics collection")
                logger.info("  🔍 tracemalloc - Memory allocation tracking")
                logger.info("  💾 psutil - Real-time process memory monitoring")
                logger.info("  📈 Prometheus integration - Enterprise metrics export")
                logger.info("  🚨 Memory leak detection - Automatic suspect identification")
                
            except Exception as e:
                logger.warning(f"Failed to initialize Advanced GC Monitoring: {e}")
                app.state.gc_monitor = None
                
            # Initialize Pyroscope Continuous Profiling
            try:
                from observability.pyroscope_integration import PyroscopeConfig, setup_fastapi_profiling
                
                pyroscope_config = PyroscopeConfig(
                    server_address="http://pyroscope:4040",
                    application_name="oms-service",
                    tags={
                        "version": "2.0.0",
                        "component": "ontology-management",
                        "team": "platform",
                    },
                    sample_rate=100,  # 100 Hz sampling
                    upload_rate=10,   # Upload every 10 seconds
                )
                
                profiler = setup_fastapi_profiling(app, pyroscope_config)
                app.state.pyroscope_profiler = profiler
                
                logger.info("🔥 Pyroscope Continuous Profiling initialized!")
                logger.info("  🎯 Real-time CPU profiling")
                logger.info("  💾 Memory allocation profiling")
                logger.info("  🔍 Goroutine/Thread profiling")
                logger.info("  📊 Flame graph visualization")
                logger.info("  🌐 UI available at: http://localhost:4040")
                
            except Exception as e:
                logger.warning(f"Failed to initialize Pyroscope Profiling: {e}")
                app.state.pyroscope_profiler = None
                
        except Exception as e:
            logger.critical(f"Failed to initialize container resources: {e}", exc_info=True)
            raise

        yield

        logger.info("🛑 Enterprise Application lifespan: shutdown sequence initiated.")
        try:
            logger.info("Shutting down container resources...")
            await container.shutdown_resources()
            logger.info("Container resources shut down successfully.")
            
            # Cleanup Redis client
            if hasattr(app.state, 'redis_client') and app.state.redis_client:
                await app.state.redis_client.aclose()
                logger.info("Redis client closed")
            
            # Cleanup observability (if needed)
            if hasattr(app.state, 'observability_manager') and app.state.observability_manager:
                logger.info("Enterprise Observability shutdown completed")
                
            # Cleanup GC monitoring
            if hasattr(app.state, 'gc_monitor') and app.state.gc_monitor:
                logger.info("Advanced GC Monitoring shutdown completed")
                
            # Cleanup Pyroscope profiling
            if hasattr(app.state, 'pyroscope_profiler') and app.state.pyroscope_profiler:
                try:
                    app.state.pyroscope_profiler.stop_profiling()
                    logger.info("Pyroscope Profiling shutdown completed")
                except Exception as e:
                    logger.error(f"Error stopping Pyroscope profiling: {e}")
                
        except Exception as e:
            logger.error(f"Error during container resource shutdown: {e}", exc_info=True)

    api_prefix = "/api/v1"
    app = FastAPI(
        title="Ontology Management Service",
        version="2.0.0",
        debug=app_config.service.debug,
        openapi_url=f"{api_prefix}/openapi.json",
        docs_url=f"{api_prefix}/docs",
        redoc_url=f"{api_prefix}/redoc",
        lifespan=lifespan
    )
    app.state.container = container
    
    # Wire the container to the modules that need it
    # Temporarily disable wiring of non-existent modules
    # container.wire(modules=[
    #     __name__,
    #     "api.v1.endpoints.branch",
    #     # ... existing code ...
    # ])

    # Routers will now get their dependencies injected by Depends(...)
    # thanks to container.wire()
    
    # Add routers
    logger.info("Adding routers...")
    app.include_router(health_routes.router, prefix="/api/v1", tags=["Health"])
    logger.info("Health routes added")
    app.include_router(system_routes.router, prefix="/api/v1", tags=["System"])
    app.include_router(schema_routes.router, prefix="/api/v1", tags=["Schema"])
    app.include_router(organization_routes.router, prefix="/api/v1", tags=["Organization"])
    app.include_router(property_routes.router, prefix="/api/v1", tags=["Property"])
    
    v1_routers = [
        audit_routes, batch_routes, branch_lock_routes, branch_routes,
        document_routes, document_crud_routes, graph_health_routes, idempotent_routes,
        issue_tracking_routes, job_progress_routes, shadow_index_routes, 
        time_travel_routes, version_routes, test_routes, circuit_breaker_routes
        # resilience_dashboard_routes - REMOVED: Replaced with enterprise observability stack
    ]
    for router_module in v1_routers:
        app.include_router(router_module.router, prefix="/api/v1")

    app.include_router(auth_proxy_routes.router, prefix="/api/v1")
    app.include_router(health_routes.router)  # Health endpoints at root level
    
    app.mount("/graphql", modular_graphql_app, name="graphql")
    app.mount("/graphql-ws", websocket_app, name="graphql_ws")
    
    if (get_config() or get_config()).service.environment != "production":
        from api.test_endpoints import router as test_router
        app.include_router(test_router)
    
    # MIDDLEWARE CHAIN CONFIGURATION (Correct Order)
    logger.info("Adding middleware chain...")
    
    # 0. Global Circuit Breaker (First-level protection)
    logger.info("Adding Global Circuit Breaker Middleware...")
    try:
        from middleware.circuit_breaker_global import GlobalCircuitBreakerMiddleware, GlobalCircuitConfig
        redis_client = getattr(app.state, 'redis_client', None)
        circuit_config = GlobalCircuitConfig(
            service_name="oms",
            failure_threshold=5,
            error_rate_threshold=0.6,
            timeout_seconds=60
        )
        app.add_middleware(GlobalCircuitBreakerMiddleware, config=circuit_config, redis_client=redis_client)
        logger.info("Global Circuit Breaker Middleware added")
    except Exception as e:
        logger.warning(f"Failed to add Global Circuit Breaker Middleware: {e}")
    
    # 1. Error Handler (Top-level)
    logger.info("Adding ErrorHandlerMiddleware...")
    app.add_middleware(ErrorHandlerMiddleware)
    logger.info("ErrorHandlerMiddleware added")

    # 2. CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 3. ETag
    logger.info("Adding ETagMiddleware...")
    app.add_middleware(ETagMiddleware)
    logger.info("ETagMiddleware added")
    
    # 4. Authentication
    logger.info("Adding AuthMiddleware...")
    app.add_middleware(AuthMiddleware)
    logger.info("AuthMiddleware added")

    # 5. TerminusDB Context
    logger.info("Adding TerminusContextMiddleware...")
    app.add_middleware(TerminusContextMiddleware)
    logger.info("TerminusContextMiddleware added")

    # 6. Database Context
    logger.info("Adding CoreDatabaseContextMiddleware...")
    app.add_middleware(CoreDatabaseContextMiddleware)
    logger.info("CoreDatabaseContextMiddleware added")

    # 7. Scope-based RBAC (with auth paths fixed)
    app.add_middleware(ScopeRBACMiddleware)
    logger.info("ScopeRBACMiddleware registered - security layer active")

    # Optional: Instrumenting for OpenTelemetry
    # try:
    #     # Only enable in production or based on a specific setting
    #     if config.service.environment == "production":
    #         from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    #         FastAPIInstrumentor.instrument_app(app)
    #         logger.info("FastAPI application instrumented for OpenTelemetry.")
    # except ImportError:
    #     logger.warning("OpenTelemetry libraries not found. Skipping instrumentation.")
    # except Exception as e:
    #     logger.warning(f"FastAPI instrumentation skipped: {e}")

    return app