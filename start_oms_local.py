#!/usr/bin/env python3
"""
Start OMS locally for testing all middleware activation
"""

import os
import sys
import subprocess

# Add the ontology-management-service directory to Python path
oms_path = "/Users/isihyeon/Desktop/Arrakis-Project/ontology-management-service"
sys.path.insert(0, oms_path)
os.chdir(oms_path)

# Set environment variables
os.environ.update({
    "JWT_SECRET": "test-secret-key",
    "ENVIRONMENT": "development",
    "DEBUG": "true",
    "DATABASE_URL": "postgresql://oms_user:oms_password@localhost:5432/oms_db",
    "REDIS_URL": "redis://localhost:6379",
    "TERMINUSDB_ENDPOINT": "http://localhost:6363",
    "TERMINUSDB_USER": "admin",
    "TERMINUSDB_PASS": "root",
    "TERMINUSDB_KEY": "root",
    "USER_SERVICE_URL": "http://localhost:8001",
    "AUDIT_SERVICE_URL": "http://localhost:8004",
    "NATS_URL": "nats://localhost:4222",
    "ENABLE_DEBUG_ROUTES": "true",
    "ENABLE_TEST_ENDPOINTS": "true",
})

# Start the application
print("🚀 Starting OMS with all middlewares activated...")
print("=" * 60)
print("Middlewares to be activated:")
print("  ✅ GlobalCircuitBreakerMiddleware")
print("  ✅ ErrorHandlerMiddleware")
print("  ✅ CORSMiddleware")
print("  ✅ ETagMiddleware")
print("  ✅ AuthMiddleware")
print("  ✅ TerminusContextMiddleware")
print("  ✅ CoreDatabaseContextMiddleware")
print("  ✅ ScopeRBACMiddleware")
print("  ✅ RequestIdMiddleware")
print("  ✅ AuditLogMiddleware")
print("  ✅ SchemaFreezeMiddleware")
print("  ✅ ThreeWayMergeMiddleware")
print("  ✅ EventStateStoreMiddleware")
print("=" * 60)

# Run uvicorn
subprocess.run([
    sys.executable, "-m", "uvicorn",
    "main:app",
    "--host", "0.0.0.0",
    "--port", "8000",
    "--reload"
])