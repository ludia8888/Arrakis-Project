from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
        "version": "2.0.0",
    }


# Production routes import - all routes must be available
from api.simple_schema_routes import router as schema_router
from api.v1 import document_routes, override_approval_routes, time_travel_routes

# Register all routes
app.include_router(schema_router, prefix="/api/v1")
app.include_router(time_travel_routes.router, prefix="/api/v1")
app.include_router(document_routes.router, prefix="/api/v1")
app.include_router(override_approval_routes.router)
