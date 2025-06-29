# GraphQL Resolvers Structure

This directory contains the modularized GraphQL resolvers for the OMS monolith application. The resolvers have been split into smaller, more manageable files based on their functionality and domain.

## File Structure

### Core Files
- `__init__.py` - Package initialization and exports
- `service_client.py` - ServiceClient class for microservice communication
- `query.py` - Main Query class that aggregates all query resolvers
- `mutation.py` - Main Mutation class that aggregates all mutation resolvers

### Domain-Specific Resolvers

#### Schema Management
- `object_type_resolvers.py` - ObjectType queries and mutations
- `property_resolvers.py` - Property and SharedProperty queries
- `link_type_resolvers.py` - LinkType queries
- `interface_resolvers.py` - Interface queries

#### Type System
- `action_type_resolvers.py` - ActionType queries and mutations
- `function_type_resolvers.py` - FunctionType queries and mutations
- `data_type_resolvers.py` - DataType queries and mutations

#### Branch and Utility
- `branch_resolvers.py` - Branch queries
- `utility_resolvers.py` - History, validation, and search queries

## Architecture

Each resolver file follows a consistent pattern:

1. **Query Resolvers**: Classes ending with `QueryResolvers` contain GraphQL query fields
2. **Mutation Resolvers**: Classes ending with `MutationResolvers` contain GraphQL mutation fields
3. **Helper Methods**: Private methods (starting with `_`) for data transformation

## Usage

The main `Query` and `Mutation` classes use multiple inheritance to combine all resolver classes:

```python
@strawberry.type
class Query(
    ObjectTypeQueryResolvers,
    PropertyQueryResolvers,
    # ... other query resolvers
):
    pass
```

This approach provides:
- Better code organization
- Easier maintenance and testing
- Clear separation of concerns
- Reduced file size and complexity

## Dependencies

All resolvers depend on:
- `service_client` - For communication with backend microservices
- Schema types from `..schema` - For GraphQL type definitions
- `strawberry` - For GraphQL decorators and functionality