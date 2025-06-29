"""
Main Mutation Class - Aggregates all mutation resolvers
"""
import strawberry

from .object_type_resolvers import ObjectTypeMutationResolvers
from .action_type_resolvers import ActionTypeMutationResolvers
from .function_type_resolvers import FunctionTypeMutationResolvers
from .data_type_resolvers import DataTypeMutationResolvers


@strawberry.type
class Mutation(
    ObjectTypeMutationResolvers,
    ActionTypeMutationResolvers,
    FunctionTypeMutationResolvers,
    DataTypeMutationResolvers
):
    """GraphQL Mutation 루트"""
    pass