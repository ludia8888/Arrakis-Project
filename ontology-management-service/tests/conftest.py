import os
import sys

# Add project root to the Python path to resolve module imports during tests
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

"""
Production-ready configuration for pytest tests.
This file sets up fixtures and application context for REAL service integration tests.
Zero Mock patterns - 100% Real implementations for production readiness.
"""
import asyncio
from typing import AsyncGenerator, Generator

import aioredis
import httpx
import pytest
from bootstrap.app import create_app
from bootstrap.config import AppConfig, PostgresConfig, RedisConfig, TerminusDBConfig
from bootstrap.dependencies import get_branch_service, get_db_client, get_redis_client
from database.clients.postgres_client_secure import PostgresClientSecure
from database.clients.terminus_db import TerminusDBClient
from database.clients.unified_database_client import UnifiedDatabaseClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient


@pytest.fixture(scope = "session")
def production_config() -> AppConfig:
 """Provides a production-ready AppConfig instance."""
 return AppConfig(
 postgres = PostgresConfig(
 host = os.getenv("POSTGRES_HOST", "postgres"),
 port = int(os.getenv("POSTGRES_PORT", "5432")),
 database = os.getenv("POSTGRES_DB", "oms"),
 username = os.getenv("POSTGRES_USER", "postgres"),
 password = os.getenv("POSTGRES_PASSWORD", "password"),
 schema = os.getenv("POSTGRES_SCHEMA", "public"),
 ),
 sqlite = None,
 redis = RedisConfig(
 host = os.getenv("REDIS_HOST", "redis"),
 port = int(os.getenv("REDIS_PORT", "6379")),
 db = int(os.getenv("REDIS_DB", "0")),
 ),
 terminusdb = TerminusDBConfig(
 url = os.getenv("TERMINUSDB_URL", "http://terminusdb:6363"),
 team = os.getenv("TERMINUSDB_TEAM", "admin"),
 user = os.getenv("TERMINUSDB_USER", "admin"),
 database = os.getenv("TERMINUSDB_DB", "oms"),
 key = os.getenv("TERMINUSDB_ADMIN_PASS", "changeme-admin-pass"),
 ),
 )


@pytest.fixture(scope = "session")
async def production_app(production_config: AppConfig) -> TestClient:
 """
 Creates and configures a production FastAPI app instance for testing,
 using REAL service connections - no mocks!
 """
 app = create_app(production_config)

 # --- REAL PRODUCTION SERVICES - ZERO MOCKS ---
 print("🚀 Initializing production app with REAL services...")

 # Initialize real Redis client
 try:
 redis_url = f"redis://{production_config.redis.host}:{production_config.redis.port}/{production_config.redis.db}"
 real_redis = await aioredis.from_url(redis_url, decode_responses = True)
 await real_redis.ping()
 print(f"✅ Real Redis connected: {redis_url}")

 # Override with real Redis client
 app.dependency_overrides[get_redis_client] = lambda: real_redis
 except Exception as e:
 print(f"❌ Redis connection failed: {e}")
 raise

 # Initialize real database clients
 try:
 # Real PostgreSQL client
 real_postgres = PostgresClientSecure(production_config.postgres.model_dump())
 await real_postgres.connect()
 print("✅ Real PostgreSQL connected")

 # Real TerminusDB client
 real_terminusdb = TerminusDBClient(
 config = production_config.terminusdb, service_name = "oms-production-test"
 )
 await real_terminusdb._initialize_client()
 print("✅ Real TerminusDB connected")

 # Real unified database client
 real_db_client = UnifiedDatabaseClient(
 postgres_client = real_postgres, terminus_client = real_terminusdb
 )
 await real_db_client.connect()
 print("✅ Real UnifiedDatabaseClient initialized")

 # Override with real database client
 app.dependency_overrides[get_db_client] = lambda: real_db_client
 except Exception as e:
 print(f"❌ Database connection failed: {e}")
 raise

 # Initialize real branch service (no mocks!)
 try:
 from core.services.branch_service import BranchService

 real_branch_service = BranchService(
 db_client = real_db_client, redis_client = real_redis, config = production_config
 )
 print("✅ Real BranchService initialized")

 # Override with real branch service
 async def get_real_branch_service():
 return real_branch_service

 app.dependency_overrides[get_branch_service] = get_real_branch_service
 except Exception as e:
 print(f"⚠️ BranchService initialization warning: {e}")
 # Continue without branch service override if it fails

 print("🎉 Production app with 100% REAL services ready!")

 with TestClient(app) as client:
 yield client

 # Cleanup real connections
 try:
 await real_redis.close()
 await real_postgres.close()
 await real_terminusdb.close()
 print("✅ All real connections closed cleanly")
 except Exception as e:
 print(f"⚠️ Cleanup warning: {e}")


@pytest.fixture
def real_udc(production_app: TestClient) -> UnifiedDatabaseClient:
 """
 Provides access to the REAL UnifiedDatabaseClient instance
 used in the production_app fixture.
 """
 return production_app.app.dependency_overrides[get_db_client]()


@pytest.fixture(scope = "session")
def event_loop():
 """Create an instance of the default event loop for the test session."""
 loop = asyncio.get_event_loop_policy().new_event_loop()
 yield loop
 loop.close()


@pytest.fixture
def production_app_instance():
 """Create production FastAPI app instance for testing."""
 from bootstrap.app import create_app
 from bootstrap.config import AppConfig, PostgresConfig, RedisConfig, TerminusDBConfig

 config = AppConfig(
 postgres = PostgresConfig(
 host = os.getenv("POSTGRES_HOST", "postgres"),
 port = int(os.getenv("POSTGRES_PORT", "5432")),
 database = os.getenv("POSTGRES_DB", "oms"),
 username = os.getenv("POSTGRES_USER", "postgres"),
 password = os.getenv("POSTGRES_PASSWORD", "password"),
 schema = os.getenv("POSTGRES_SCHEMA", "public"),
 ),
 redis = RedisConfig(
 host = os.getenv("REDIS_HOST", "redis"),
 port = int(os.getenv("REDIS_PORT", "6379")),
 db = int(os.getenv("REDIS_DB", "0")),
 ),
 terminusdb = TerminusDBConfig(
 url = os.getenv("TERMINUSDB_URL", "http://terminusdb:6363"),
 team = os.getenv("TERMINUSDB_TEAM", "admin"),
 user = os.getenv("TERMINUSDB_USER", "admin"),
 database = os.getenv("TERMINUSDB_DB", "oms"),
 key = os.getenv("TERMINUSDB_ADMIN_PASS", "changeme-admin-pass"),
 ),
 )
 return create_app(config)


@pytest.fixture
async def production_client(
 production_app_instance,
) -> Generator[TestClient, None, None]:
 """Create production test client with REAL dependencies."""
 print("🚀 Initializing production client with REAL services...")

 # Initialize real Redis client
 try:
 redis_host = os.getenv("REDIS_HOST", "redis")
 redis_port = int(os.getenv("REDIS_PORT", "6379"))
 redis_db = int(os.getenv("REDIS_DB", "0"))
 redis_url = f"redis://{redis_host}:{redis_port}/{redis_db}"

 real_redis = await aioredis.from_url(redis_url, decode_responses = True)
 await real_redis.ping()
 print(f"✅ Real Redis connected: {redis_url}")

 # Override with real Redis client
 production_app_instance.dependency_overrides[
 get_redis_client
 ] = lambda: real_redis
 except Exception as e:
 print(f"❌ Redis connection failed: {e}")
 raise

 # Initialize real database clients
 try:
 # Real PostgreSQL connection
 postgres_config = {
 "host": os.getenv("POSTGRES_HOST", "postgres"),
 "port": int(os.getenv("POSTGRES_PORT", "5432")),
 "database": os.getenv("POSTGRES_DB", "oms"),
 "username": os.getenv("POSTGRES_USER", "postgres"),
 "password": os.getenv("POSTGRES_PASSWORD", "password"),
 "schema": os.getenv("POSTGRES_SCHEMA", "public"),
 }

 real_postgres = PostgresClientSecure(postgres_config)
 await real_postgres.connect()
 print("✅ Real PostgreSQL connected")

 # Real TerminusDB connection
 terminusdb_config = TerminusDBConfig(
 url = os.getenv("TERMINUSDB_URL", "http://terminusdb:6363"),
 team = os.getenv("TERMINUSDB_TEAM", "admin"),
 user = os.getenv("TERMINUSDB_USER", "admin"),
 database = os.getenv("TERMINUSDB_DB", "oms"),
 key = os.getenv("TERMINUSDB_ADMIN_PASS", "changeme-admin-pass"),
 )

 real_terminusdb = TerminusDBClient(
 config = terminusdb_config, service_name = "oms-production-client-test"
 )
 await real_terminusdb._initialize_client()
 print("✅ Real TerminusDB connected")

 # Real unified database client
 real_db_client = UnifiedDatabaseClient(
 postgres_client = real_postgres, terminus_client = real_terminusdb
 )
 await real_db_client.connect()
 print("✅ Real UnifiedDatabaseClient initialized")

 # Override with real database client
 production_app_instance.dependency_overrides[
 get_db_client
 ] = lambda: real_db_client
 except Exception as e:
 print(f"❌ Database connection failed: {e}")
 raise

 # Initialize real branch service
 try:
 from core.services.branch_service import BranchService

 real_branch_service = BranchService(
 db_client = real_db_client, redis_client = real_redis
 )
 print("✅ Real BranchService initialized")

 async def get_real_branch_service():
 return real_branch_service

 production_app_instance.dependency_overrides[
 get_branch_service
 ] = get_real_branch_service
 except Exception as e:
 print(f"⚠️ BranchService initialization warning: {e}")

 print("🎉 Production client with 100% REAL services ready!")

 with TestClient(production_app_instance) as test_client:
 yield test_client

 # Cleanup real connections
 try:
 await real_redis.close()
 await real_postgres.close()
 await real_terminusdb.close()
 print("✅ All real connections closed cleanly")
 except Exception as e:
 print(f"⚠️ Cleanup warning: {e}")

 # Clear overrides
 production_app_instance.dependency_overrides.clear()


@pytest.fixture
async def production_async_client(
 production_app_instance,
) -> AsyncGenerator[AsyncClient, None]:
 """Create production async test client for async tests."""
 print("🚀 Initializing production async client...")
 async with AsyncClient(app = production_app_instance, base_url = "http://test") as ac:
 print("✅ Production async client ready")
 yield ac


@pytest.fixture
def production_user_context():
 """Create production user context for authentication."""
 from datetime import datetime, timezone

 from core.auth_utils import UserContext

 return UserContext(
 user_id = os.getenv("TEST_USER_ID", "prod-user-001"),
 username = os.getenv("TEST_USERNAME", "production_test_user"),
 email = os.getenv("TEST_USER_EMAIL", "production.test@arrakis.dev"),
 roles = ["user", "admin", "schema_editor", "production_tester"],
 tenant_id = os.getenv("TEST_TENANT_ID", "arrakis-production"),
 metadata={
 "scopes": [
 "api:ontologies:read",
 "api:ontologies:write",
 "api:branches:create",
 "api:schemas:modify",
 "api:admin:all",
 ],
 "auth_time": int(datetime.now(timezone.utc).timestamp()),
 "auth_method": "production_test",
 "session_id": f"prod-session-{datetime.now().strftime('%Y%m%d_%H%M%S')}",
 },
 )


@pytest.fixture
def production_auth_headers(production_user_context):
 """Create production authentication headers with valid JWT token."""
 from datetime import datetime, timedelta

 import jwt

 # Production JWT configuration
 jwt_secret = os.getenv("JWT_SECRET", "production-test-secret-key")
 jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")
 jwt_issuer = os.getenv("JWT_ISSUER", "arrakis.iam")
 jwt_audience = os.getenv("JWT_AUDIENCE", "oms")

 # Create production JWT token
 now = datetime.utcnow()
 payload = {
 "sub": production_user_context.user_id,
 "username": production_user_context.username,
 "email": production_user_context.email,
 "roles": production_user_context.roles,
 "tenant_id": production_user_context.tenant_id,
 "scope": " ".join(production_user_context.metadata.get("scopes", [])),
 "exp": now + timedelta(hours = 1), # Longer expiry for production tests
 "iat": now,
 "nb": now,
 "iss": jwt_issuer,
 "aud": jwt_audience,
 "jti": f"prod-jwt-{int(now.timestamp())}",
 "auth_time": production_user_context.metadata.get("auth_time"),
 "session_id": production_user_context.metadata.get("session_id"),
 }

 token = jwt.encode(payload, jwt_secret, algorithm = jwt_algorithm)

 return {
 "Authorization": f"Bearer {token}",
 "X-User-ID": production_user_context.user_id,
 "X-Tenant-ID": production_user_context.tenant_id,
 "X-Test-Mode": "production",
 "X-Session-ID": production_user_context.metadata.get("session_id"),
 }


@pytest.fixture
def production_schema_data():
 """Production-ready schema data for testing."""
 from datetime import datetime, timezone

 return {
 "name": "ProductionTestEntity",
 "type": "object",
 "description": "Production-ready test entity for comprehensive validation",
 "version": "1.0.0",
 "properties": {
 "id": {
 "type": "string",
 "required": True,
 "description": "Unique identifier",
 "pattern": "^[a-zA-Z0-9_-]+$",
 "minLength": 1,
 "maxLength": 255,
 },
 "name": {
 "type": "string",
 "required": True,
 "description": "Human-readable name",
 "minLength": 1,
 "maxLength": 500,
 },
 "status": {
 "type": "string",
 "required": True,
 "enum": ["draft", "active", "deprecated", "archived"],
 "default": "draft",
 "description": "Current status of the entity",
 },
 "created_at": {
 "type": "datetime",
 "required": False,
 "description": "Creation timestamp",
 "default": datetime.now(timezone.utc).isoformat(),
 },
 "updated_at": {
 "type": "datetime",
 "required": False,
 "description": "Last update timestamp",
 },
 "created_by": {
 "type": "string",
 "required": True,
 "description": "User who created this entity",
 "default": "production_test_user",
 },
 "metadata": {
 "type": "object",
 "required": False,
 "description": "Additional metadata",
 "properties": {
 "tags": {
 "type": "array",
 "items": {"type": "string"},
 "description": "Classification tags",
 },
 "source": {
 "type": "string",
 "description": "Data source identifier",
 },
 },
 },
 },
 "branch": os.getenv("TEST_BRANCH", "production-test"),
 "tenant_id": os.getenv("TEST_TENANT_ID", "arrakis-production"),
 "schema_version": "2024.1.0",
 "validation_rules": {
 "strict_mode": True,
 "require_description": True,
 "enforce_naming_convention": True,
 },
 "audit": {
 "created_by": "production_test_user",
 "created_at": datetime.now(timezone.utc).isoformat(),
 "test_mode": True,
 "source": "automated_production_test",
 },
 }


@pytest.fixture
def production_environment_setup():
 """Set up production environment variables for tests."""
 env_vars = {
 "ENVIRONMENT": "production-test",
 "LOG_LEVEL": "INFO",
 "POSTGRES_HOST": os.getenv("POSTGRES_HOST", "postgres"),
 "POSTGRES_PORT": os.getenv("POSTGRES_PORT", "5432"),
 "POSTGRES_DB": os.getenv("POSTGRES_DB", "oms"),
 "POSTGRES_USER": os.getenv("POSTGRES_USER", "postgres"),
 "POSTGRES_PASSWORD": os.getenv("POSTGRES_PASSWORD", "password"),
 "REDIS_HOST": os.getenv("REDIS_HOST", "redis"),
 "REDIS_PORT": os.getenv("REDIS_PORT", "6379"),
 "REDIS_DB": os.getenv("REDIS_DB", "0"),
 "TERMINUSDB_URL": os.getenv("TERMINUSDB_URL", "http://terminusdb:6363"),
 "TERMINUSDB_TEAM": os.getenv("TERMINUSDB_TEAM", "admin"),
 "TERMINUSDB_USER": os.getenv("TERMINUSDB_USER", "admin"),
 "TERMINUSDB_DB": os.getenv("TERMINUSDB_DB", "oms"),
 "TERMINUSDB_ADMIN_PASS": os.getenv(
 "TERMINUSDB_ADMIN_PASS", "changeme-admin-pass"
 ),
 "JWT_SECRET": os.getenv("JWT_SECRET", "production-test-secret-key"),
 "JWT_ALGORITHM": os.getenv("JWT_ALGORITHM", "HS256"),
 "JWT_ISSUER": os.getenv("JWT_ISSUER", "arrakis.iam"),
 "JWT_AUDIENCE": os.getenv("JWT_AUDIENCE", "oms"),
 }

 # Set environment variables for the test session
 for key, value in env_vars.items():
 os.environ[key] = value

 print("✅ Production environment variables configured")
 return env_vars
