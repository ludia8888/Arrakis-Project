"""
GraphQL Resolvers - 섹션 10.2의 GraphQL API 구현
Split into modular resolver files for better organization
"""
import strawberry

# Import from split resolver modules
from .resolvers import Query, Mutation, service_client

# Import subscriptions
from .subscriptions import Subscription

# Create the schema with subscriptions
schema = strawberry.Schema(query=Query, mutation=Mutation, subscription=Subscription)