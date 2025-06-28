"""
Ontology Management System Enterprise - TerminusDB Native Migration Complete
Using production TerminusDBClient with native features
"""
import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette import status
from datetime import datetime, timezone

# 수정된 Schema Service 사용
from core.schema.service import SchemaService
from core.validation import ValidationService
from core.branch import get_branch_service
from core.history import HistoryService

# Enterprise Validation
from core.validation.enterprise_service import EnterpriseValidationService, ValidationLevel
from core.validation.oms_rules import register_oms_validation_rules

# Database
from database.clients.terminus_db import TerminusDBClient

# Event System
from core.event_publisher import get_event_publisher, EnhancedEventService
from shared.events import EventPublisher

# Cache
from shared.cache.smart_cache import SmartCacheManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ServiceContainer:
    """모든 서비스 인스턴스를 관리하는 컨테이너"""
    
    def __init__(self):
        self.db_client = None
        self.cache = None
        self.event_publisher = None
        
        # Core Services
        self.schema_service = None
        self.extended_schema_service = None
        self.validation_service = None
        self.branch_service = None
        self.history_service = None
        self.event_service = None
        
    async def initialize(self):
        """모든 서비스 초기화"""
        logger.info("Initializing services with fixed DB connection...")
        
        try:
            # Production TerminusDBClient 사용 (ValidationConfig 기반)
            self.db_client = TerminusDBClient(
                username="admin",
                password="root"
            )
            
            # DB 연결 - official pattern: connect(team, key, user, db)
            connected = await self.db_client.connect(
                team="admin",
                key="root", 
                user="admin",
                db="oms",
                timeout=30
            )
            if not connected:
                logger.error("Failed to connect to TerminusDB")
            else:
                logger.info("✅ Connected to TerminusDB successfully")
            
            # Initialize event publisher
            self.event_publisher = get_event_publisher()
            if hasattr(self.event_publisher, 'connect'):
                await self.event_publisher.connect(timeout=30)
                logger.info("✅ Event publisher connected")
            
            # 수정된 Schema Service 사용 (ValidationConfig 기반)
            from core.validation.config import get_validation_config
            config = get_validation_config()
            self.schema_service = SchemaService(
                tdb_endpoint=config.terminus_db_url,
                event_publisher=self.event_publisher
            )
            await self.schema_service.initialize()
            logger.info("✅ Schema Service initialized with real DB connection")
            
            # Extended Schema Service for all other types
            from core.schema.extended_service import ExtendedSchemaService
            self.extended_schema_service = ExtendedSchemaService(
                tdb_endpoint=config.terminus_db_url,
                event_publisher=self.event_publisher
            )
            await self.extended_schema_service.initialize()
            logger.info("✅ Extended Schema Service initialized")
            
            # Initialize Validation Service
            from core.validation.service_refactored import ValidationServiceRefactored
            from core.validation.adapters import (
                SmartCacheAdapter,
                TerminusDBAdapter,
                EventPublisherAdapter
            )
            
            # Create adapters for validation service
            cache_adapter = SmartCacheAdapter(self.cache) if self.cache else None
            tdb_adapter = TerminusDBAdapter(self.db_client) if self.db_client else None
            event_adapter = EventPublisherAdapter(self.event_publisher)
            
            self.validation_service = ValidationServiceRefactored(
                cache=cache_adapter,
                tdb=tdb_adapter,
                events=event_adapter
            )
            logger.info("✅ Validation Service initialized")
            
            # 다른 서비스들은 일단 None으로
            self.branch_service = None
            self.history_service = None
            self.event_service = EnhancedEventService()
            
            logger.info("All services initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            raise
    
    async def shutdown(self):
        """모든 서비스 정리"""
        logger.info("Shutting down services...")
        
        if self.event_publisher and hasattr(self.event_publisher, 'close'):
            await self.event_publisher.close()
            
        if self.db_client:
            await self.db_client.disconnect()
        
        if self.event_publisher:
            self.event_publisher.close()
        
        logger.info("All services shut down")


# 전역 서비스 컨테이너
services = ServiceContainer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    logger.info("OMS Enterprise (Fixed) starting up...")
    
    # 서비스 초기화
    await services.initialize()
    
    # Enterprise Validation Service 초기화
    validation_service = EnterpriseValidationService(
        cache_manager=None,  # Using ValidationConfig cache settings
        event_publisher=services.event_publisher,
        redis_client=None,  # Using ValidationConfig cache backend
        default_level=ValidationLevel.STANDARD
    )
    register_oms_validation_rules(validation_service)
    app.state.validation_service = validation_service
    logger.info("✅ Enterprise Validation Service initialized")

    # 모든 서비스를 app.state에 저장하여 일관된 접근 보장
    app.state.services = services
    logger.info(f"✅ Services container attached to app.state (id: {id(services)})")

    # Enterprise Validation Service is now available in app.state
    logger.info("✅ Enterprise Validation Service available for middleware")

    yield
    
    # Shutdown
    logger.info("OMS Enterprise (Fixed) shutting down...")
    if hasattr(app.state, 'validation_service') and hasattr(app.state.validation_service, 'shutdown'):
        await app.state.validation_service.shutdown()
    await services.shutdown()


# FastAPI 앱 생성 - 보안 강화
app = FastAPI(
    title="OMS Enterprise (Fixed)",
    version="2.0.1",
    description="Ontology Management System - DB Connection Fixed",
    lifespan=lifespan,
    # 자동 문서화 비활성화 (프로덕션)
    docs_url="/docs" if os.getenv("ENVIRONMENT", "development") == "development" else None,
    redoc_url="/redoc" if os.getenv("ENVIRONMENT", "development") == "development" else None,
    openapi_url="/openapi.json" if os.getenv("ENVIRONMENT", "development") == "development" else None,
)

# 보안 예외 처리 시스템 등록 - 가장 먼저!
from core.security.exception_handler import register_exception_handlers
register_exception_handlers(app)

# Middleware 설정
# IMPORTANT: Middleware runs in LIFO order for requests (last added = first to run)
# For responses, it's FIFO (first added = first to run)

# 1. CORS (가장 먼저 추가, 가장 나중에 실행)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. ETag Middleware (Auth 이전에 추가해야 Auth 이후에 실행됨)
# MUST be added BEFORE auth so it runs AFTER auth in request flow
from middleware.etag_middleware import configure_etag_middleware
configure_etag_middleware(app)

# 3. Issue Tracking Middleware
from middleware.issue_tracking_middleware import configure_issue_tracking
configure_issue_tracking(app)

# 4. Audit Middleware (Removed - legacy)

# 5. Schema Freeze Middleware
from middleware.schema_freeze_middleware import SchemaFreezeMiddleware
app.add_middleware(SchemaFreezeMiddleware)

# 6. Scope-based RBAC Middleware
from core.iam.scope_rbac_middleware import ScopeRBACMiddleware
app.add_middleware(ScopeRBACMiddleware)

# 7. RBAC Middleware
from middleware.rbac_middleware import RBACMiddleware
app.add_middleware(RBACMiddleware)

# 8. Enterprise Validation Middleware
# Note: validation_service will be set in lifespan
from middleware.enterprise_validation import EnterpriseValidationMiddleware
app.add_middleware(EnterpriseValidationMiddleware)

# 9. Authentication Middleware (마지막에 추가, 가장 먼저 실행)
# MUST run first to set request.state.user

# Check if bypass auth is enabled for testing
BYPASS_AUTH = os.getenv("BYPASS_AUTH", "false").lower() == "true"
if BYPASS_AUTH:
    from middleware.mock_auth_middleware import MockAuthMiddleware
    logger.info("⚠️  BYPASS AUTH ENABLED - Using mock authentication for testing")
    app.add_middleware(MockAuthMiddleware)
else:
    # Use MSA authentication if configured
    USE_MSA_AUTH = os.getenv("USE_MSA_AUTH", "false").lower() == "true"
    if USE_MSA_AUTH:
        from middleware.auth_middleware_msa import MSAAuthMiddleware
        logger.info("Using MSA Authentication via IAM Service")
        app.add_middleware(MSAAuthMiddleware)
    else:
        from middleware.auth_middleware import AuthMiddleware
        logger.info("Using legacy authentication")
        app.add_middleware(AuthMiddleware)


# === Health & Status ===
from core.health import get_health_checker, HealthStatus

@app.get("/health")
async def health_check():
    """Real system health check - no lies, only verified facts"""
    health_checker = get_health_checker()
    result = await health_checker.get_health(detailed=False)
    
    # Return appropriate HTTP status based on health
    if result["status"] == HealthStatus.UNHEALTHY.value:
        # Return 503 Service Unavailable for unhealthy
        return JSONResponse(content=result, status_code=503)
    elif result["status"] == HealthStatus.DEGRADED.value:
        # Return 200 but with degraded status (allows partial service)
        return JSONResponse(content=result, status_code=200)
    else:
        # Healthy - return 200
        return result

@app.get("/health/detailed")
async def health_check_detailed(request: Request):
    """Detailed health check with auth required"""
    # Check if user is authenticated (you may want to restrict to admins)
    if not hasattr(request.state, "user"):
        raise HTTPException(status_code=401, detail="Authentication required for detailed health check")
    
    health_checker = get_health_checker()
    return await health_checker.get_health(detailed=True)

@app.get("/health/live")
async def liveness_probe():
    """Kubernetes liveness probe - basic check if service is running"""
    return {"status": "alive", "timestamp": datetime.now(timezone.utc).isoformat()}

@app.get("/health/ready")
async def readiness_probe():
    """Kubernetes readiness probe - check if ready to serve traffic"""
    health_checker = get_health_checker()
    result = await health_checker.get_health(detailed=False)
    
    # Only ready if healthy or degraded (not unhealthy)
    ready = result["status"] != HealthStatus.UNHEALTHY.value
    
    if not ready:
        return JSONResponse(
            content={"ready": False, "reason": "Critical services unavailable"},
            status_code=503
        )
    
    return {"ready": True, "status": result["status"]}


@app.get("/")
async def root():
    """API 정보"""
    return {
        "name": "OMS Enterprise API (Fixed)",
        "version": "2.0.1",
        "status": "DB Connection Fixed - Real Data",
        "docs": "/docs",
        "health": "/health"
    }


# === Metrics Endpoint ===
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint with graceful fallback"""
    try:
        from prometheus_client import generate_latest  # type: ignore
        prometheus_available = True
    except ImportError:
        prometheus_available = False

    from middleware.etag_analytics import get_etag_analytics

    # Get ETag analytics safely
    try:
        analytics = get_etag_analytics()
        summary = analytics.get_performance_summary()
    except Exception as e:
        logger.warning(f"Failed to gather ETag analytics: {e}")
        summary = {
            "total_requests": 0,
            "cache_hit_rate": 0.0,
            "avg_response_time_ms": 0.0,
            "p95_response_time_ms": 0.0,
            "p99_response_time_ms": 0.0,
        }

    # Build ETag summary block
    etag_summary = (
        "# ETag Analytics Summary\n" \
        f"# Total Requests: {summary['total_requests']}\n" \
        f"# Cache Hit Rate: {summary['cache_hit_rate']:.2%}\n" \
        f"# Avg Response Time: {summary['avg_response_time_ms']:.2f}ms\n" \
        f"# P95 Response Time: {summary['p95_response_time_ms']:.2f}ms\n" \
        f"# P99 Response Time: {summary['p99_response_time_ms']:.2f}ms\n"
    )

    if prometheus_available:
        try:
            metrics_content = generate_latest().decode("utf-8")
        except Exception as e:
            logger.error(f"Prometheus generate_latest failed: {e}")
            metrics_content = ""
    else:
        # Fallback: dump internal MetricsCollector values as JSON
        from shared.monitoring.metrics import metrics_collector
        import json
        metrics_snapshot = json.dumps(metrics_collector.get_metrics(), ensure_ascii=False, indent=2)
        metrics_content = "# Prometheus client not installed or failed.\n" + metrics_snapshot

    return Response(
        content=etag_summary + metrics_content,
        media_type="text/plain; version=0.0.4; charset=utf-8"
    )


# === Enterprise Validation Service ===
# EnterpriseValidationService와 관련 imports는 파일 상단에 이미 있음

# === Schema Management API (Fixed) ===
@app.get("/api/v1/schemas/{branch}/object-types")
async def list_object_types(branch: str):
    """ObjectType 목록 조회 - 실제 DB에서"""
    if not services.schema_service:
        raise HTTPException(status_code=503, detail="Schema service not available")
    
    try:
        # 수정된 서비스 사용 - 실제 DB 데이터 반환
        result = await services.schema_service.list_object_types(branch=branch)
        return {
            "objectTypes": result, 
            "branch": branch,
            "source": "real_database"  # Mock이 아님을 표시
        }
    except Exception as e:
        logger.error(f"Failed to list object types: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/schemas/{branch}/object-types")
async def create_object_type(branch: str, request: Dict[str, Any]):
    """ObjectType 생성 - 실제 DB에"""
    if not services.schema_service:
        raise HTTPException(status_code=503, detail="Schema service not available")
    
    try:
        from models.domain import ObjectTypeCreate
        
        # Request를 모델로 변환
        data = ObjectTypeCreate(
            name=request.get("name"),
            display_name=request.get("displayName"),
            description=request.get("description")
        )
        
        # 실제 DB에 생성
        result = await services.schema_service.create_object_type(branch, data)
        return {
            "objectType": result.model_dump() if hasattr(result, 'model_dump') else result,
            "source": "real_database"
        }
    except Exception as e:
        logger.error(f"Failed to create object type: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# Include Branch Lock Management routes
from api.v1.branch_lock_routes import router as branch_lock_router
app.include_router(branch_lock_router)

# Include Audit routes
from api.v1.audit_routes import router as audit_router
app.include_router(audit_router)

# Include Issue Tracking routes
from api.v1.issue_tracking_routes import router as issue_tracking_router
app.include_router(issue_tracking_router)

# Include Version Tracking routes
from api.v1.version_routes import router as version_router
app.include_router(version_router)

# Include Idempotent Consumer routes
from api.v1.idempotent_routes import router as idempotent_router
app.include_router(idempotent_router)

# Include Batch routes for GraphQL DataLoader support
from api.v1.batch_routes import router as batch_router
app.include_router(batch_router)

# Include Schema Management routes
from api.v1.schema_routes import router as schema_router
app.include_router(schema_router)

# Include Validation routes
from api.v1.validation_routes import router as validation_router
app.include_router(validation_router)


# === GraphQL Integration ===
# Mount enhanced GraphQL with enterprise features
import os
GRAPHQL_ENABLED = os.getenv("GRAPHQL_ENABLED", "true").lower() == "true"

if GRAPHQL_ENABLED:
    try:
        # Import enhanced GraphQL app with all enterprise features
        from api.graphql.enhanced_main import app as enhanced_graphql_app
        
        # Mount GraphQL at /graphql endpoint
        app.mount("/graphql", enhanced_graphql_app)
        logger.info("✅ GraphQL endpoint mounted at /graphql with enterprise features")
        
        # Also mount the regular GraphQL for WebSocket support
        from api.graphql.main import app as graphql_ws_app
        app.mount("/graphql-ws", graphql_ws_app)
        logger.info("✅ GraphQL WebSocket endpoint mounted at /graphql-ws")
        
    except Exception as e:
        logger.error(f"Failed to mount GraphQL endpoints: {e}")
        # Don't fail the entire app if GraphQL fails to load
        GRAPHQL_ENABLED = False
else:
    logger.info("GraphQL endpoints disabled by configuration")


# === Test Routes (Non-Production Only) ===
# Register test routes only in non-production environments
from core.config.environment import get_environment
env_config = get_environment()
env_config.log_environment()

if env_config.allows_test_routes:
    try:
        from tests.fixtures.test_routes import register_test_routes
        register_test_routes(app)
    except ImportError as e:
        logger.info(f"Test routes not available: {e}")
else:
    logger.info("Test routes disabled per environment configuration")


# === Custom Exception Handlers ===
# Exception handler is already registered in app creation


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8002,  # 다른 포트 사용
        reload=True,
        log_level="info"
    )

# STARTUP TIMEOUT DISABLED FOR DEVELOPMENT
# Note: Re-enable for production deployments
