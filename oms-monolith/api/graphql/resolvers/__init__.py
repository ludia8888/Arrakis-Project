"""
GraphQL Resolvers Package
Split resolvers for better organization and maintainability
"""

from .query import Query
from .mutation import Mutation
from .service_client import ServiceClient, service_client

__all__ = ["Query", "Mutation", "ServiceClient", "service_client"]