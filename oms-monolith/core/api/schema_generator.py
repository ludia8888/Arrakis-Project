"""
Enhanced API Schema Generator for OMS - Backward Compatibility Module

This module provides backward compatibility for existing imports.
The actual implementation has been split into separate modules:
- core.api.schema.base: Base classes and common utilities
- core.api.schema.graphql: GraphQL schema generation
- core.api.schema.openapi: OpenAPI schema generation

DEPRECATED: Please update your imports to use the new module structure.
"""

import warnings

# Issue deprecation warning
warnings.warn(
    "Importing from core.api.schema_generator is deprecated. "
    "Please update your imports:\n"
    "  - GraphQLSchemaGenerator, graphql_generator -> from core.api.schema.graphql\n"
    "  - OpenAPISchemaGenerator, openapi_generator -> from core.api.schema.openapi\n"
    "  - LinkFieldMetadata -> from core.api.schema.base",
    DeprecationWarning,
    stacklevel=2
)

# Re-export everything for backward compatibility
from core.api.schema.base import LinkFieldMetadata
from core.api.schema.graphql import GraphQLSchemaGenerator, graphql_generator
from core.api.schema.openapi import OpenAPISchemaGenerator, openapi_generator

__all__ = [
    'LinkFieldMetadata',
    'GraphQLSchemaGenerator',
    'graphql_generator',
    'OpenAPISchemaGenerator',
    'openapi_generator'
]