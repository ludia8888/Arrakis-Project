#!/usr/bin/env python3
"""
🔥 ENHANCED MSA SERVICES WITH PROMETHEUS METRICS
간단한 서비스 실행 스크립트 + 프로덕션급 메트릭
실제 MSA 서비스들을 mock으로 대체하여 통합 테스트를 위한 환경 구성
"""
import asyncio
import json
import time
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
import uvicorn

# Prometheus 메트릭 라이브러리
try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
    METRICS_AVAILABLE = True
    
    # 메트릭 정의
    http_requests_total = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
    http_request_duration_seconds = Histogram('http_request_duration_seconds', 'HTTP request duration', ['method', 'endpoint'])
    service_health = Gauge('service_health', 'Service health status', ['service'])
    user_registrations_total = Counter('user_registrations_total', 'Total user registrations')
    user_logins_total = Counter('user_logins_total', 'Total user logins')
    schemas_created_total = Counter('schemas_created_total', 'Total schemas created')
    branches_created_total = Counter('branches_created_total', 'Total branches created')
    audit_events_total = Counter('audit_events_total', 'Total audit events', ['event_type'])
    
    print("📊 Prometheus 메트릭 활성화됨")
except ImportError:
    METRICS_AVAILABLE = False
    print("⚠️ Prometheus 메트릭 라이브러리 없음 - 메트릭 비활성화")


def create_mock_user_service():
    """Enhanced Mock User Service with Metrics"""
    app = FastAPI(title="Enhanced Mock User Service", version="2.0.0", description="Production-ready User Service with Metrics")
    
    if METRICS_AVAILABLE:
        service_health.labels(service='user-service').set(1)
        
        @app.get("/metrics")
        async def metrics():
            """Prometheus 메트릭 엔드포인트"""
            return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
    
    @app.get("/health")
    async def health():
        if METRICS_AVAILABLE:
            service_health.labels(service='user-service').set(1)
        return {
            "status": "healthy", 
            "service": "user-service", 
            "timestamp": datetime.utcnow().isoformat(),
            "metrics_enabled": METRICS_AVAILABLE,
            "version": "2.0.0"
        }
    
    @app.get("/.well-known/jwks.json")
    async def jwks():
        # Mock JWKS 응답
        return {
            "keys": [{
                "kty": "RSA",
                "kid": "test-key-1",
                "use": "sig",
                "alg": "RS256",
                "n": "test-modulus",
                "e": "AQAB"
            }]
        }
    
    @app.post("/api/v1/auth/register")
    async def register(request: Request):
        data = await request.json()
        
        # 메트릭 업데이트
        if METRICS_AVAILABLE:
            user_registrations_total.inc()
            http_requests_total.labels(method="POST", endpoint="/api/v1/auth/register", status="201").inc()
        
        return JSONResponse(
            status_code=201,
            content={
                "status": "success",
                "user_id": f"user_{data.get('username', 'test')}_123",
                "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ0ZXN0LXVzZXItMTIzIiwidXNlcm5hbWUiOiJ0ZXN0X2ludGVncmF0aW9uX3VzZXIiLCJyb2xlcyI6WyJ1c2VyIiwiYWRtaW4iXSwicGVybWlzc2lvbnMiOlsicmVhZCIsIndyaXRlIiwiYWRtaW4iXSwiZXhwIjo5OTk5OTk5OTk5LCJpYXQiOjE3MDczNDgwMDAsImlzcyI6InVzZXItc2VydmljZSIsImF1ZCI6Im9tcyJ9",
                "metrics_enabled": METRICS_AVAILABLE
            }
        )
    
    @app.post("/api/v1/auth/login")
    async def login(request: Request):
        data = await request.json()
        mock_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ0ZXN0LXVzZXItMTIzIiwidXNlcm5hbWUiOiJ0ZXN0X2ludGVncmF0aW9uX3VzZXIiLCJyb2xlcyI6WyJ1c2VyIiwiYWRtaW4iXSwicGVybWlzc2lvbnMiOlsicmVhZCIsIndyaXRlIiwiYWRtaW4iXSwiZXhwIjo5OTk5OTk5OTk5LCJpYXQiOjE3MDczNDgwMDAsImlzcyI6InVzZXItc2VydmljZSIsImF1ZCI6Im9tcyJ9"
        
        return {
            "access_token": mock_token,
            "token_type": "bearer",
            "expires_in": 3600,
            "user": {
                "id": "test-user-123",
                "username": data.get("username", "test_integration_user"),
                "email": "test@integration.com",
                "roles": ["user", "admin"],
                "permissions": ["read", "write", "admin"]
            }
        }
    
    @app.get("/api/v1/auth/profile")
    async def get_profile(request: Request):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Authentication required"})
        
        return {
            "id": "test-user-123",
            "username": "test_integration_user",
            "email": "test@integration.com",
            "roles": ["user", "admin"],
            "permissions": ["read", "write", "admin"],
            "created_at": datetime.utcnow().isoformat()
        }
    
    @app.get("/api/v1/admin/users")
    async def get_admin_users(request: Request):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Authentication required"})
        
        return {
            "users": [
                {
                    "id": "admin-123",
                    "username": "admin",
                    "email": "admin@company.com",
                    "roles": ["admin"],
                    "status": "active"
                },
                {
                    "id": "user-456",
                    "username": "test_user",
                    "email": "user@company.com", 
                    "roles": ["user"],
                    "status": "active"
                }
            ],
            "total": 2,
            "page": 1,
            "page_size": 10
        }
    
    @app.get("/api/v1/admin/config")
    async def get_admin_config(request: Request):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Authentication required"})
        
        return {
            "system_config": {
                "max_users": 1000,
                "session_timeout": 3600,
                "security_level": "high",
                "audit_enabled": True
            },
            "updated_at": datetime.utcnow().isoformat()
        }
    
    return app


def create_mock_audit_service():
    """Enhanced Mock Audit Service with Metrics"""
    app = FastAPI(title="Enhanced Mock Audit Service", version="2.0.0", description="Production-ready Audit Service with Metrics")
    
    if METRICS_AVAILABLE:
        service_health.labels(service='audit-service').set(1)
        
        @app.get("/metrics")
        async def metrics():
            """Prometheus 메트릭 엔드포인트"""
            return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
    
    @app.get("/health")
    async def health():
        if METRICS_AVAILABLE:
            service_health.labels(service='audit-service').set(1)
        return {
            "status": "healthy", 
            "service": "audit-service", 
            "timestamp": datetime.utcnow().isoformat(),
            "metrics_enabled": METRICS_AVAILABLE,
            "version": "2.0.0"
        }
    
    @app.post("/api/v1/audit/logs")
    async def create_audit_log(request: Request):
        data = await request.json()
        return {
            "success": True,
            "log_id": "audit-log-123",
            "message": "Audit log created successfully"
        }
    
    @app.get("/api/v1/logs")
    async def get_audit_logs(request: Request):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Authentication required"})
        
        # Mock 감사 로그 응답 - 실제 활동 로그 시뮬레이션
        return [
            {
                "log_id": "audit-log-001",
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": "alice_schema_designer",
                "action": "user_registration",
                "resource_type": "user",
                "resource_id": "alice_schema_designer",
                "result": "success",
                "details": "Schema designer registered successfully"
            },
            {
                "log_id": "audit-log-002",
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": "bob_data_manager",
                "action": "schema_creation",
                "resource_type": "schema",
                "resource_id": "ProductCatalog",
                "result": "success",
                "details": "New ontology schema created"
            },
            {
                "log_id": "audit-log-003",
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": "charlie_system_admin",
                "action": "system_monitoring",
                "resource_type": "system",
                "resource_id": "health_check",
                "result": "success",
                "details": "System health monitoring performed"
            }
        ]
    
    @app.post("/api/v2/events")
    async def create_event(request: Request):
        data = await request.json()
        return {
            "success": True,
            "event_id": "event-123",
            "message": "Event processed successfully"
        }
    
    return app


def create_mock_oms():
    """Enhanced Mock OMS with Metrics"""
    app = FastAPI(title="Enhanced Mock OMS", version="2.0.0", description="Production-ready OMS with Metrics")
    
    if METRICS_AVAILABLE:
        service_health.labels(service='oms-service').set(1)
        
        @app.get("/metrics")
        async def metrics():
            """Prometheus 메트릭 엔드포인트"""
            return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
    
    @app.get("/health")
    async def health():
        if METRICS_AVAILABLE:
            service_health.labels(service='oms-service').set(1)
        return {
            "status": "healthy", 
            "service": "oms", 
            "timestamp": datetime.utcnow().isoformat(),
            "metrics_enabled": METRICS_AVAILABLE,
            "version": "2.0.0"
        }
    
    @app.get("/api/v1/schemas")
    async def get_schemas(request: Request):
        # 토큰 검증 시뮬레이션 (실제로는 해야 함)
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"}
            )
        
        return {
            "schemas": [
                {"id": "schema-1", "name": "test_schema", "description": "Test schema"}
            ],
            "total": 1
        }
    
    @app.post("/api/v1/schemas")
    async def create_schema(request: Request):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"}
            )
        
        data = await request.json()
        return JSONResponse(
            status_code=201,
            content={
                "id": f"schema_{data.get('name', 'test')}_123",
                "name": data.get("name", "test_schema"),
                "definition": data.get("definition", {}),
                "version": data.get("version", "1.0.0"),
                "description": data.get("description", "Test schema"),
                "created_at": datetime.utcnow().isoformat()
            }
        )
    
    @app.put("/api/v1/schemas/{schema_name}")
    async def update_schema(schema_name: str, request: Request):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"}
            )
        
        data = await request.json()
        return {
            "id": f"schema_{schema_name}_123",
            "name": schema_name,
            "definition": data.get("definition", {}),
            "version": data.get("version", "1.1.0"),
            "updated_at": datetime.utcnow().isoformat()
        }
    
    @app.post("/api/v1/schemas/{schema_name}/permissions")
    async def set_schema_permissions(schema_name: str, request: Request):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"}
            )
        
        data = await request.json()
        return {
            "schema": schema_name,
            "permissions": data.get("permissions", {}),
            "updated_at": datetime.utcnow().isoformat()
        }
    
    @app.post("/api/v1/documents")
    async def create_document(request: Request):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"}
            )
        
        data = await request.json()
        return JSONResponse(
            status_code=201,
            content={
                "id": f"doc_{data.get('schema', 'test')}_123",
                "schema": data.get("schema", "test_schema"),
                "data": data.get("data", {}),
                "metadata": data.get("metadata", {}),
                "created_at": datetime.utcnow().isoformat()
            }
        )
    
    @app.get("/api/v1/documents")
    async def get_documents(request: Request):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"}
            )
        
        schema = request.query_params.get("schema")
        return [
            {
                "id": f"doc_{schema}_123" if schema else "doc_test_123",
                "schema": schema or "test_schema",
                "data": {
                    "product_id": "PROD-001",
                    "name": "고급 노트북",
                    "category": "Electronics",
                    "price": 1500000
                },
                "created_at": datetime.utcnow().isoformat()
            }
        ]
    
    @app.get("/api/v1/documents/{doc_id}")
    async def get_document(doc_id: str, request: Request):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"}
            )
        
        return {
            "id": doc_id,
            "schema": "ProductCatalog",
            "data": {
                "product_id": "PROD-001",
                "name": "고급 노트북 (업데이트됨)",
                "category": "Electronics",
                "price": 1400000,
                "description": "고성능 개발자용 노트북"
            },
            "updated_at": datetime.utcnow().isoformat()
        }
    
    @app.put("/api/v1/documents/{doc_id}")
    async def update_document(doc_id: str, request: Request):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"}
            )
        
        data = await request.json()
        return {
            "id": doc_id,
            "data": data.get("data", {}),
            "updated_at": datetime.utcnow().isoformat()
        }
    
    @app.post("/api/v1/branches")
    async def create_branch(request: Request):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"}
            )
        
        data = await request.json()
        return JSONResponse(
            status_code=201,
            content={
                "id": f"branch_{data.get('name', 'test')}_123",
                "name": data.get("name", "test_branch"),
                "source": data.get("source", "main"),
                "description": data.get("description", "Test branch"),
                "created_at": datetime.utcnow().isoformat()
            }
        )
    
    @app.get("/api/v1/status")
    async def get_status(request: Request):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"}
            )
        
        return {
            "status": "healthy",
            "service": "ontology-management-service",
            "version": "2.0.0",
            "uptime": "24h 15m 30s",
            "database": "connected",
            "memory_usage": "45%",
            "cpu_usage": "12%",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @app.get("/api/v1/audit/events")
    async def get_audit_events(request: Request):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"}
            )
        
        return {
            "events": [
                {
                    "event_id": "event-123",
                    "timestamp": datetime.utcnow().isoformat(),
                    "event_type": "branch.create",
                    "user_id": "test-user-123",
                    "resource_type": "branch",
                    "action": "create",
                    "result": "success"
                }
            ],
            "total": 1
        }
    
    @app.get("/api/v1/nonexistent")
    async def nonexistent():
        return JSONResponse(
            status_code=404,
            content={"detail": "Not found"}
        )
    
    return app


async def run_service(app, port, name):
    """서비스 실행"""
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info")
    server = uvicorn.Server(config)
    print(f"🚀 {name} starting on port {port}")
    await server.serve()


async def main():
    """모든 서비스 실행"""
    print("🚀 Mock MSA 서비스들을 시작합니다...")
    print("="*60)
    
    # 서비스 생성
    user_service = create_mock_user_service()
    audit_service = create_mock_audit_service()
    oms_service = create_mock_oms()
    
    # 병렬 실행 - 포트 변경
    await asyncio.gather(
        run_service(user_service, 8012, "User Service"),
        run_service(audit_service, 8011, "Audit Service"),
        run_service(oms_service, 8010, "OMS"),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 서비스 종료 중...")
        print("✅ 모든 서비스가 종료되었습니다.")