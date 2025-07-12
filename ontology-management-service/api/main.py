from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(title="Ontology Management Service", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "ontology-management-service",
        "version": "2.0.0"
    }


# Import routes with fallback approach
routes_imported = []

# Try to import schema routes
try:
    from api.simple_schema_routes import router as schema_router
    app.include_router(schema_router, prefix="/api/v1")
    routes_imported.append("schema_routes")
    print("✅ Simple Schema routes imported and registered")
except ImportError as e:
    print(f"❌ Failed to import schema routes: {e}")

# Try to import time travel routes
try:
    from api.v1 import time_travel_routes
    app.include_router(time_travel_routes.router, prefix="/api/v1")
    routes_imported.append("time_travel_routes")
    print("✅ Time travel routes imported and registered")
except ImportError as e:
    print(f"❌ Failed to import time travel routes: {e}")

# Try to import document routes
try:
    from api.v1 import document_routes
    app.include_router(document_routes.router, prefix="/api/v1")
    routes_imported.append("document_routes")
    print("✅ Document routes imported and registered")
except ImportError as e:
    print(f"❌ Failed to import document routes: {e}")

# Try to import override approval routes
try:
    from api.v1 import override_approval_routes
    app.include_router(override_approval_routes.router)
    routes_imported.append("override_approval_routes")
    print("✅ Override approval routes imported and registered")
except ImportError as e:
    print(f"❌ Failed to import override approval routes: {e}")

print(f"📊 Routes successfully imported: {len(routes_imported)}/4 - {routes_imported}")

# Create minimal schema endpoint if main routes fail
if "schema_routes" not in routes_imported:
    print("🔧 Creating fallback schema endpoints...")
    
    @app.get("/api/v1/schemas/status")
    def schema_service_status():
        return {
            "status": "fallback_mode",
            "message": "Schema service running in fallback mode",
            "available_endpoints": ["/api/v1/schemas/status"],
            "missing_dependencies": "Full schema service requires additional dependencies"
        }
    
    print("✅ Fallback schema endpoint created: /api/v1/schemas/status")
