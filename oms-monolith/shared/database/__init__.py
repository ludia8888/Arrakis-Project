"""
Shared Database Module

This module provides a unified interface for all database operations in OMS.
It consolidates database client management and provides consistent interfaces.
"""

from shared.database.interfaces import (
    IDocumentDatabase,
    ICacheDatabase,
    IMessageQueue,
    IExternalService,
    IVersionControl,
    IRelationalDatabase,
    ITransaction
)

from shared.database.client_factory import (
    DatabaseClientFactory,
    get_database_factory,
    get_terminus_client,
    get_redis_client,
    get_user_service_client
)

__all__ = [
    # Interfaces
    'IDocumentDatabase',
    'ICacheDatabase',
    'IMessageQueue',
    'IExternalService',
    'IVersionControl',
    'IRelationalDatabase',
    'ITransaction',
    
    # Factory
    'DatabaseClientFactory',
    'get_database_factory',
    
    # Convenience functions
    'get_terminus_client',
    'get_redis_client',
    'get_user_service_client'
]