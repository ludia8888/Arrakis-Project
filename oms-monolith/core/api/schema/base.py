"""
Base classes and common utilities for schema generation.

Contains shared functionality between GraphQL and OpenAPI generators.
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from models.domain import (
    ObjectType, LinkType, Property, 
    Cardinality, Directionality, Status
)
from models.semantic_types import semantic_type_registry
from models.struct_types import struct_type_registry
from utils.logger import get_logger

logger = get_logger(__name__)


class LinkFieldMetadata(BaseModel):
    """Metadata for a generated link field"""
    field_name: str
    field_type: str  # "SingleLink" or "LinkSet"
    target_type: str
    link_type_id: str
    is_required: bool = False
    is_bidirectional: bool = False
    description: Optional[str] = None
    
    # Metadata hints for resolvers
    resolver_hints: Dict[str, Any] = Field(default_factory=dict)


class BaseSchemaGenerator:
    """Base class for schema generators with common functionality"""
    
    def _is_many(self, cardinality: Cardinality) -> bool:
        """Check if cardinality represents multiple items"""
        if cardinality is None:
            return True  # Default to many for safety
        return cardinality in [Cardinality.ONE_TO_MANY, Cardinality.MANY_TO_MANY]
    
    def _generate_field_name(self, link: LinkType, direction: str) -> str:
        """Generate field name for a link"""
        if direction == "forward":
            # Use link name or generate from target type
            if link.name:
                return link.name.lower().replace(" ", "_")
            else:
                # Generate from target type if name is empty
                target_name = link.toTypeId.lower()
                return f"{target_name}s" if self._is_many(link.cardinality) else target_name
        else:
            # Reverse link naming
            if link.name:
                return f"inverse_{link.name.lower().replace(' ', '_')}"
            else:
                # Generate from source type if name is empty
                return f"inverse_{link.fromTypeId.lower()}"
    
    def _determine_field_type(self, cardinality: Cardinality) -> str:
        """Determine if field should be SingleLink or LinkSet"""
        if cardinality is None:
            # Default to LinkSet for safety
            return "LinkSet"
        elif cardinality == Cardinality.ONE_TO_ONE:
            return "SingleLink"
        else:
            return "LinkSet"
    
    def _determine_reverse_field_type(self, cardinality: Cardinality) -> str:
        """Determine reverse field type based on cardinality"""
        if cardinality is None:
            # Default to LinkSet for safety
            return "LinkSet"
        # Reverse cardinality logic
        elif cardinality == Cardinality.ONE_TO_ONE:
            return "SingleLink"
        elif cardinality == Cardinality.ONE_TO_MANY:
            return "SingleLink"  # Reverse of one-to-many is many-to-one
        else:
            return "LinkSet"
    
    def _generate_link_fields(
        self, 
        object_type: ObjectType,
        link_types: List[LinkType]
    ) -> List[LinkFieldMetadata]:
        """Generate link field metadata for an object type"""
        fields = []
        
        # Forward links (this object is the source)
        forward_links = [
            lt for lt in link_types 
            if lt.fromTypeId == object_type.id
        ]
        
        for link in forward_links:
            field = LinkFieldMetadata(
                field_name=self._generate_field_name(link, "forward"),
                field_type=self._determine_field_type(link.cardinality),
                target_type=link.toTypeId,
                link_type_id=link.id,
                is_required=link.isRequired,
                is_bidirectional=link.directionality == Directionality.BIDIRECTIONAL,
                description=link.description,
                resolver_hints={
                    "direction": "forward",
                    "cardinality": link.cardinality.value if link.cardinality else "unknown",
                    "cascade_delete": link.cascadeDelete
                }
            )
            fields.append(field)
        
        # Reverse links (this object is the target)
        reverse_links = [
            lt for lt in link_types 
            if lt.toTypeId == object_type.id and 
            lt.directionality == Directionality.BIDIRECTIONAL
        ]
        
        for link in reverse_links:
            field = LinkFieldMetadata(
                field_name=self._generate_field_name(link, "reverse"),
                field_type=self._determine_reverse_field_type(link.cardinality),
                target_type=link.fromTypeId,
                link_type_id=link.id,
                is_required=False,  # Reverse links are never required
                is_bidirectional=True,
                description=f"Reverse link: {link.description}",
                resolver_hints={
                    "direction": "reverse",
                    "cardinality": link.cardinality.value if link.cardinality else "unknown"
                }
            )
            fields.append(field)
        
        return fields


# Common data type mappings
GRAPHQL_TYPE_MAPPING = {
    "string": "String",
    "integer": "Int",
    "long": "BigInt",
    "float": "Float",
    "double": "Float",
    "boolean": "Boolean",
    "date": "Date",
    "datetime": "DateTime",
    "time": "Time",
    "decimal": "Decimal",
    "binary": "Binary",
    "json": "JSON"
}

OPENAPI_TYPE_MAPPING = {
    "string": {"type": "string"},
    "integer": {"type": "integer", "format": "int32"},
    "long": {"type": "integer", "format": "int64"},
    "float": {"type": "number", "format": "float"},
    "double": {"type": "number", "format": "double"},
    "boolean": {"type": "boolean"},
    "date": {"type": "string", "format": "date"},
    "datetime": {"type": "string", "format": "date-time"},
    "time": {"type": "string", "format": "time"},
    "decimal": {"type": "string", "format": "decimal"},
    "binary": {"type": "string", "format": "binary"},
    "json": {"type": "object"}
}