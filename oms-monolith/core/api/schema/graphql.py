"""
GraphQL Schema Generator for OMS

Generates GraphQL schema definitions for object types with link fields.
This generator creates the schema METADATA only. It does not implement
resolvers - those are handled by the Object Set Service and other runtime services.
"""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timezone
import json
from textwrap import dedent

from models.domain import (
    ObjectType, LinkType, Property, 
    Cardinality, Directionality, Status
)
from models.struct_types import struct_type_registry
from core.api.schema.base import (
    BaseSchemaGenerator, LinkFieldMetadata, 
    GRAPHQL_TYPE_MAPPING
)
from utils.logger import get_logger

logger = get_logger(__name__)


class GraphQLSchemaGenerator(BaseSchemaGenerator):
    """
    Generates GraphQL schema definitions for object types with link fields.
    
    This generator creates the schema METADATA only. It does not implement
    resolvers - those are handled by the Object Set Service and other runtime services.
    """
    
    def __init__(self):
        self.generated_types: Dict[str, str] = {}
        self.link_fields: Dict[str, List[LinkFieldMetadata]] = {}
        
    def generate_object_type_schema(
        self, 
        object_type: ObjectType,
        link_types: List[LinkType]
    ) -> str:
        """
        Generate GraphQL type definition for an object type including link fields.
        
        Returns GraphQL SDL (Schema Definition Language) as a string.
        """
        # Start with type definition
        sdl = f"type {object_type.name} {{\n"
        sdl += f"  id: ID!\n"
        
        # Add properties
        for prop in object_type.properties:
            sdl += self._generate_property_field(prop)
        
        # Add link fields
        link_fields = self._generate_link_fields(object_type, link_types)
        self.link_fields[object_type.id] = link_fields
        
        for field in link_fields:
            sdl += self._generate_link_field_sdl(field)
        
        # Add metadata fields
        sdl += "  _metadata: ObjectMetadata!\n"
        sdl += "}\n\n"
        
        # Generate input types
        sdl += self._generate_input_types(object_type, link_fields)
        
        self.generated_types[object_type.id] = sdl
        return sdl
    
    def _generate_property_field(self, prop: Property) -> str:
        """Generate GraphQL field for a property"""
        field_type = self._map_data_type_to_graphql(prop.data_type_id)
        
        if prop.is_array:
            field_type = f"[{field_type}]"
        
        if prop.is_required:
            field_type = f"{field_type}!"
        
        return f'  {prop.name}: {field_type}\n'
    
    def _generate_link_field_sdl(self, field: LinkFieldMetadata) -> str:
        """Generate GraphQL SDL for a link field"""
        field_type = field.target_type
        
        if field.field_type == "LinkSet":
            field_type = f"[{field_type}!]"
            
        if field.is_required:
            field_type = f"{field_type}!"
            
        # Add resolver directive hint (for Object Set Service)
        resolver_hint = json.dumps(field.resolver_hints)
        directive = f'@link(metadata: """{resolver_hint}""")'
        
        description = f'"{field.description}"' if field.description else '""'
        
        return f'  {field.field_name}: {field_type} {directive}\n'
    
    def _map_data_type_to_graphql(self, data_type_id: str) -> str:
        """Map OMS data type to GraphQL type"""
        # Check if it's a struct type
        if struct_type_registry.exists(data_type_id):
            return data_type_id.title().replace("_", "")
            
        return GRAPHQL_TYPE_MAPPING.get(data_type_id, "String")
    
    def _generate_input_types(
        self, 
        object_type: ObjectType,
        link_fields: List[LinkFieldMetadata]
    ) -> str:
        """Generate input types for mutations"""
        # Create input type
        sdl = f"input {object_type.name}CreateInput {{\n"
        
        # Add property fields
        for prop in object_type.properties:
            if not prop.is_primary_key:  # Skip ID fields
                field_type = self._map_data_type_to_graphql(prop.data_type_id)
                if prop.is_array:
                    field_type = f"[{field_type}]"
                if prop.is_required:
                    field_type = f"{field_type}!"
                sdl += f"  {prop.name}: {field_type}\n"
        
        # Add link connection inputs
        for field in link_fields:
            if field.field_type == "SingleLink":
                sdl += f"  {field.field_name}Id: ID\n"
            else:
                sdl += f"  {field.field_name}Ids: [ID!]\n"
        
        sdl += "}\n\n"
        
        # Update input type
        sdl += f"input {object_type.name}UpdateInput {{\n"
        
        # All fields optional for updates
        for prop in object_type.properties:
            if not prop.is_primary_key:
                field_type = self._map_data_type_to_graphql(prop.data_type_id)
                if prop.is_array:
                    field_type = f"[{field_type}]"
                sdl += f"  {prop.name}: {field_type}\n"
        
        # Link updates
        for field in link_fields:
            if field.field_type == "SingleLink":
                sdl += f"  {field.field_name}Id: ID\n"
            else:
                sdl += f"  {field.field_name}Ids: [ID!]\n"
                sdl += f"  add{field.field_name.title()}Ids: [ID!]\n"
                sdl += f"  remove{field.field_name.title()}Ids: [ID!]\n"
        
        sdl += "}\n\n"
        
        return sdl
    
    def generate_complete_schema(
        self,
        object_types: List[ObjectType],
        link_types: List[LinkType]
    ) -> str:
        """Generate complete GraphQL schema for all types"""
        sdl = """
# Auto-generated GraphQL Schema by OMS
# This schema defines the structure only. Resolvers are implemented by external services.

scalar DateTime
scalar Date
scalar Time
scalar Decimal
scalar BigInt
scalar Binary
scalar JSON

# Directives for metadata
directive @link(metadata: String) on FIELD_DEFINITION

# Common metadata type
type ObjectMetadata {
  id: ID!
  versionHash: String!
  createdAt: DateTime!
  createdBy: String!
  modifiedAt: DateTime!
  modifiedBy: String!
}

"""
        
        # Generate types
        for object_type in object_types:
            if object_type.status == Status.ACTIVE:
                sdl += self.generate_object_type_schema(object_type, link_types)
                sdl += "\n"
        
        # Add queries
        sdl += self._generate_queries(object_types)
        
        # Add mutations
        sdl += self._generate_mutations(object_types)
        
        return sdl
    
    def _generate_queries(self, object_types: List[ObjectType]) -> str:
        """Generate query type"""
        sdl = "type Query {\n"
        
        for obj_type in object_types:
            if obj_type.status == Status.ACTIVE:
                # Single object query
                sdl += f"  {obj_type.name.lower()}(id: ID!): {obj_type.name}\n"
                
                # List query with pagination
                sdl += f"  {obj_type.name.lower()}s(first: Int, after: String, filter: {obj_type.name}Filter): {obj_type.name}Connection!\n"
        
        sdl += "}\n\n"
        
        # Generate filter and connection types
        for obj_type in object_types:
            if obj_type.status == Status.ACTIVE:
                sdl += self._generate_filter_type(obj_type)
                sdl += self._generate_connection_type(obj_type)
        
        return sdl
    
    def _generate_mutations(self, object_types: List[ObjectType]) -> str:
        """Generate mutation type"""
        sdl = "type Mutation {\n"
        
        for obj_type in object_types:
            if obj_type.status == Status.ACTIVE:
                sdl += f"  create{obj_type.name}(input: {obj_type.name}CreateInput!): {obj_type.name}!\n"
                sdl += f"  update{obj_type.name}(id: ID!, input: {obj_type.name}UpdateInput!): {obj_type.name}!\n"
                sdl += f"  delete{obj_type.name}(id: ID!): Boolean!\n"
        
        sdl += "}\n\n"
        return sdl
    
    def _generate_filter_type(self, object_type: ObjectType) -> str:
        """Generate filter input type for queries"""
        sdl = f"input {object_type.name}Filter {{\n"
        
        # Add filters for each property
        for prop in object_type.properties:
            base_type = self._map_data_type_to_graphql(prop.data_type_id)
            
            if base_type in ["String", "Int", "Float", "DateTime"]:
                sdl += f"  {prop.name}: {base_type}\n"
                sdl += f"  {prop.name}_not: {base_type}\n"
                sdl += f"  {prop.name}_in: [{base_type}!]\n"
                sdl += f"  {prop.name}_not_in: [{base_type}!]\n"
                
                if base_type in ["Int", "Float", "DateTime"]:
                    sdl += f"  {prop.name}_lt: {base_type}\n"
                    sdl += f"  {prop.name}_lte: {base_type}\n"
                    sdl += f"  {prop.name}_gt: {base_type}\n"
                    sdl += f"  {prop.name}_gte: {base_type}\n"
                    
                if base_type == "String":
                    sdl += f"  {prop.name}_contains: String\n"
                    sdl += f"  {prop.name}_starts_with: String\n"
                    sdl += f"  {prop.name}_ends_with: String\n"
        
        # Logical operators
        sdl += f"  AND: [{object_type.name}Filter!]\n"
        sdl += f"  OR: [{object_type.name}Filter!]\n"
        sdl += f"  NOT: {object_type.name}Filter\n"
        
        sdl += "}\n\n"
        return sdl
    
    def _generate_connection_type(self, object_type: ObjectType) -> str:
        """Generate connection type for pagination"""
        sdl = f"""type {object_type.name}Connection {{
  edges: [{object_type.name}Edge!]!
  pageInfo: PageInfo!
  totalCount: Int!
}}

type {object_type.name}Edge {{
  node: {object_type.name}!
  cursor: String!
}}

"""
        return sdl
    
    def export_schema_metadata(self) -> Dict[str, Any]:
        """
        Export metadata about the generated schema.
        This is used by Object Set Service and other services to understand
        the link structure and implement resolvers.
        """
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "version": "1.0",
            "link_fields": {
                type_id: [field.dict() for field in fields]
                for type_id, fields in self.link_fields.items()
            },
            "generator": "OMS GraphQL Schema Generator"
        }


# Global instance
graphql_generator = GraphQLSchemaGenerator()