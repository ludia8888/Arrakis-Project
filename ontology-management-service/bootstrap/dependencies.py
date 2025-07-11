"""Dependency Injection setup"""

from typing import Optional

from dependency_injector.wiring import inject, Provide

from .containers import Container 
from bootstrap.config import AppConfig
from core.branch.service_refactored import BranchService
from core.schema.service import SchemaService
from database.clients.unified_database_client import UnifiedDatabaseClient
from bootstrap.providers.redis_provider import RedisProvider

# Global container instance
_container: Optional[Container] = None

def init_container(config: Optional[AppConfig] = None) -> Container:
    """Initialize and return the dependency injection container."""
    global _container
    container = Container()
    if config:
        container.config.override(config)
    
    # Wire the container to modules where dependencies will be injected.
    container.wire(modules=[
        "api.v1.schema_routes",
        "api.v1.branch_routes",
        "api.v1.batch_routes",
        "api.v1.job_progress_routes",
        "api.v1.schema_generation.endpoints",
        "api.v1.property_routes",
        # Add other modules that use `Depends(Provide[...])` here
    ])
    
    _container = container
    return container

# Dependency injection functions for FastAPI
def get_branch_service():
    """Get branch service instance through DI."""
    if not _container:
        raise RuntimeError("Container not initialized")
    return _container.branch_service_provider()

def get_schema_service() -> SchemaService:
    """Get schema service instance."""
    if not _container:
        raise RuntimeError("Container not initialized")
    return _container.schema_service_provider()

def get_redis_client() -> RedisProvider:
    """Get Redis client instance."""
    if not _container:
        raise RuntimeError("Container not initialized")
    return _container.redis_provider()

async def get_db_client() -> UnifiedDatabaseClient:
    """Get database client instance."""
    # Use the singleton pattern from unified_provider directly
    from bootstrap.providers.unified_provider import get_unified_db_client
    return await get_unified_db_client()

def get_job_service():
    """Get job service instance."""
    if not _container:
        raise RuntimeError("Container not initialized")
    return _container.job_service_provider()

def get_event_gateway():
    """Get event gateway instance."""
    if not _container:
        raise RuntimeError("Container not initialized")
    return _container.event_gateway_provider()