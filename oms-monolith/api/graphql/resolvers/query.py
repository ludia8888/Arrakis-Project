"""
Main Query Class - Aggregates all query resolvers
"""
import strawberry

from .object_type_resolvers import ObjectTypeQueryResolvers
from .property_resolvers import PropertyQueryResolvers
from .link_type_resolvers import LinkTypeQueryResolvers
from .interface_resolvers import InterfaceQueryResolvers
from .action_type_resolvers import ActionTypeQueryResolvers
from .function_type_resolvers import FunctionTypeQueryResolvers
from .data_type_resolvers import DataTypeQueryResolvers
from .branch_resolvers import BranchQueryResolvers
from .utility_resolvers import UtilityQueryResolvers


@strawberry.type
class Query(
    ObjectTypeQueryResolvers,
    PropertyQueryResolvers,
    LinkTypeQueryResolvers,
    InterfaceQueryResolvers,
    ActionTypeQueryResolvers,
    FunctionTypeQueryResolvers,
    DataTypeQueryResolvers,
    BranchQueryResolvers,
    UtilityQueryResolvers
):
    """GraphQL Query 루트"""
    pass