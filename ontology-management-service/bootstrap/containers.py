"""Dependency Injection Containers"""
from dependency_injector import containers, providers

from bootstrap.config import get_config
from bootstrap.providers.redis_provider import RedisProvider
from bootstrap.providers.circuit_breaker import CircuitBreakerProvider
from bootstrap.providers.unified_provider import get_unified_db_client
from bootstrap.providers.event import get_event_gateway
from core.branch.service_refactored import BranchService
from core.branch.diff_engine import DiffEngine
from core.branch.conflict_resolver import ConflictResolver
from core.schema.service import SchemaService
from core.schema.repository import SchemaRepository
from services.job_service import JobService
from core.property.service import PropertyService
from core.document.service import DocumentService

class Container(containers.DeclarativeContainer):
    """
    DI Container for managing application dependencies.
    """
    config = providers.Singleton(get_config)

    # Core Infrastructure Providers
    redis_provider = providers.Singleton(RedisProvider)
    circuit_breaker_provider = providers.Singleton(
        CircuitBreakerProvider,
        redis_provider=redis_provider,
    )
    db_client_provider = providers.Resource(get_unified_db_client)

    # Event Gateway
    event_gateway_provider = providers.Factory(get_event_gateway)

    # Branch Service Dependencies
    # First create the dependencies that BranchService needs
    diff_engine_provider = providers.Factory(
        DiffEngine,
        tdb_endpoint=config.provided.terminusdb.endpoint,
    )
    
    conflict_resolver_provider = providers.Factory(
        ConflictResolver,
    )
    
    # Now create BranchService with all its dependencies
    branch_service_provider = providers.Factory(
        BranchService,
        db_client=db_client_provider,
        event_gateway=event_gateway_provider,
        diff_engine=diff_engine_provider,
        conflict_resolver=conflict_resolver_provider,
    )

    # Schema Service Dependencies
    schema_repository_provider = providers.Factory(
        SchemaRepository,
        db=db_client_provider,
    )
    schema_service_provider = providers.Factory(
        SchemaService,
        repository=schema_repository_provider,
        branch_service=branch_service_provider,
        event_publisher=event_gateway_provider,
    )
    
    # Job Service Dependencies
    job_service_provider = providers.Singleton(
        JobService,
    )
    
    # Property Service Dependencies
    property_service = providers.Factory(
        PropertyService,
        terminus_client=providers.Factory(
            lambda unified_client: unified_client.terminus_client,
            unified_client=db_client_provider
        ),
    )
    
    # Document Service Dependencies
    document_service_provider = providers.Factory(
        DocumentService,
        db_client=db_client_provider,
        event_publisher=event_gateway_provider,
    ) 