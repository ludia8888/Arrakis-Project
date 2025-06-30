"""
Audit Module Dependencies for FastAPI Dependency Injection
"""
from typing import Annotated
from fastapi import Depends

from core.audit.audit_service import AuditService
from core.audit.audit_publisher import AuditPublisher
from core.audit.audit_repository import AuditRepository
from core.audit.event_bus import AuditEventBus
from shared.utils.dependency_container import get_container


async def get_audit_repository() -> AuditRepository:
    """Get or create audit repository instance"""
    container = get_container()
    
    repository = await container.get("audit_repository")
    if repository is None:
        repository = AuditRepository()
        await repository.initialize()
        await container.set("audit_repository", repository)
    
    return repository


async def get_audit_event_bus() -> AuditEventBus:
    """Get or create audit event bus instance"""
    container = get_container()
    
    event_bus = await container.get("audit_event_bus")
    if event_bus is None:
        event_bus = AuditEventBus()
        await container.set("audit_event_bus", event_bus)
    
    return event_bus


async def get_audit_service(
    repository: Annotated[AuditRepository, Depends(get_audit_repository)],
    event_bus: Annotated[AuditEventBus, Depends(get_audit_event_bus)]
) -> AuditService:
    """Get or create audit service instance with dependencies"""
    container = get_container()
    
    service = await container.get("audit_service")
    if service is None:
        service = AuditService(repository=repository, event_bus=event_bus)
        await service.initialize()
        await container.set("audit_service", service)
    
    return service


async def get_audit_publisher(
    repository: Annotated[AuditRepository, Depends(get_audit_repository)],
    event_bus: Annotated[AuditEventBus, Depends(get_audit_event_bus)]
) -> AuditPublisher:
    """Get or create audit publisher instance with dependencies"""
    container = get_container()
    
    publisher = await container.get("audit_publisher")
    if publisher is None:
        publisher = AuditPublisher(repository=repository, event_bus=event_bus)
        await container.set("audit_publisher", publisher)
    
    return publisher