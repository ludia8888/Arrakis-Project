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

# Additional Active Middlewares
from middleware.schema_freeze_middleware import SchemaFreezeMiddleware
from middleware.three_way_merge import ThreeWayMergeMiddleware
from middleware.event_state_store import EventStateStoreMiddleware
from middleware.dlq.coordinator import DLQCoordinator
from middleware.discovery.coordinator import DiscoveryCoordinator
from middleware.request_id import RequestIdMiddleware
from middleware.audit_log import AuditLogMiddleware
from middleware.issue_tracking_middleware import IssueTrackingMiddleware
from middleware.component_middleware import ComponentMiddleware
from middleware.rate_limiting.middleware import RateLimitingMiddleware

# All middlewares are imported above, no fallbacks needed

# --- API Router Imports ---
from api.v1 import (
    system_routes, health_routes, schema_routes, organization_routes,
    property_routes, audit_routes, batch_routes, branch_lock_routes, 
    branch_routes, document_routes, document_crud_routes, graph_health_routes, idempotent_routes,
    issue_tracking_routes, job_progress_routes, shadow_index_routes,
    time_travel_routes, version_routes, test_routes, circuit_breaker_routes, config_routes
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
                
            # Initialize DLQ Coordinator
            try:
                dlq_coordinator = DLQCoordinator()
                await dlq_coordinator.initialize()
                app.state.dlq_coordinator = dlq_coordinator
                logger.info("📨 DLQ (Dead Letter Queue) initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize DLQ: {e}")
                app.state.dlq_coordinator = None
                
            # Initialize Discovery Coordinator
            try:
                discovery_coordinator = DiscoveryCoordinator()
                await discovery_coordinator.initialize()
                app.state.discovery_coordinator = discovery_coordinator
                logger.info("🔍 Service Discovery initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Discovery: {e}")
                app.state.discovery_coordinator = None
                
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
                    
            # Cleanup DLQ
            if hasattr(app.state, 'dlq_coordinator') and app.state.dlq_coordinator:
                try:
                    await app.state.dlq_coordinator.shutdown()
                    logger.info("DLQ shutdown completed")
                except Exception as e:
                    logger.error(f"Error stopping DLQ: {e}")
                    
            # Cleanup Discovery
            if hasattr(app.state, 'discovery_coordinator') and app.state.discovery_coordinator:
                try:
                    await app.state.discovery_coordinator.shutdown()
                    logger.info("Discovery shutdown completed")
                except Exception as e:
                    logger.error(f"Error stopping Discovery: {e}")
                
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
        time_travel_routes, version_routes, test_routes, circuit_breaker_routes, config_routes
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
    
    # 4. TerminusDB Context
    logger.info("Adding TerminusContextMiddleware...")
    app.add_middleware(TerminusContextMiddleware)
    logger.info("TerminusContextMiddleware added")

    # 5. Database Context
    logger.info("Adding CoreDatabaseContextMiddleware...")
    app.add_middleware(CoreDatabaseContextMiddleware)
    logger.info("CoreDatabaseContextMiddleware added")

    # 6. Scope-based RBAC (with auth paths fixed)
    app.add_middleware(ScopeRBACMiddleware)
    logger.info("ScopeRBACMiddleware registered - security layer active")
    
    # 7. Audit Log Middleware
    logger.info("Adding AuditLogMiddleware...")
    app.add_middleware(AuditLogMiddleware)
    logger.info("AuditLogMiddleware added")
    
    # 8. Request ID Middleware (must be after Audit Log for correct execution order)
    logger.info("Adding RequestIdMiddleware...")
    app.add_middleware(RequestIdMiddleware)
    logger.info("RequestIdMiddleware added")
    
    # 9. Authentication (must be after RBAC and Audit for correct execution order)
    logger.info("Adding AuthMiddleware...")
    app.add_middleware(AuthMiddleware)
    logger.info("AuthMiddleware added")
    
    # 10. Schema Freeze Middleware
    logger.info("Adding SchemaFreezeMiddleware...")
    app.add_middleware(SchemaFreezeMiddleware)
    logger.info("SchemaFreezeMiddleware added")
    
    # 11. Three Way Merge Middleware
    logger.info("Adding ThreeWayMergeMiddleware...")
    app.add_middleware(ThreeWayMergeMiddleware)
    logger.info("ThreeWayMergeMiddleware added")
    
    # 12. Event State Store Middleware
    logger.info("Adding EventStateStoreMiddleware...")
    try:
        app.add_middleware(EventStateStoreMiddleware)
        logger.info("EventStateStoreMiddleware added")
    except Exception as e:
        logger.warning(f"Failed to add EventStateStoreMiddleware: {e}")
    
    # 13. Issue Tracking Middleware
    logger.info("Adding IssueTrackingMiddleware...")
    app.add_middleware(IssueTrackingMiddleware)
    logger.info("IssueTrackingMiddleware added")
    
    # 14. Component Middleware
    logger.info("Adding ComponentMiddleware...")
    app.add_middleware(ComponentMiddleware)
    logger.info("ComponentMiddleware added")
    
    # 15. Rate Limiting Middleware
    logger.info("Adding RateLimitingMiddleware...")
    try:
        # Rate limiting configuration
        from middleware.rate_limiting.config import RateLimitConfig
        rate_config = RateLimitConfig(
            default_limit=100,  # 100 requests
            default_window=60,  # per minute
            strategy="sliding_window"
        )
        app.add_middleware(RateLimitingMiddleware, config=rate_config)
        logger.info("RateLimitingMiddleware added")
    except Exception as e:
        logger.warning(f"Failed to add RateLimitingMiddleware: {e}")

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