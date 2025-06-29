"""
OpenAPI Schema Generator for OMS

Generates OpenAPI 3.0 schemas for REST endpoints.
Focuses on generating schemas that include link relationships
as nested resources or HAL-style links.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from models.domain import (
    ObjectType, LinkType, Property, 
    Cardinality, Directionality, Status
)
from models.semantic_types import semantic_type_registry
from models.struct_types import struct_type_registry
from core.api.schema.base import (
    BaseSchemaGenerator, LinkFieldMetadata,
    OPENAPI_TYPE_MAPPING
)
from utils.logger import get_logger

logger = get_logger(__name__)


class OpenAPISchemaGenerator(BaseSchemaGenerator):
    """
    Generates OpenAPI 3.0 schemas for REST endpoints.
    
    Focuses on generating schemas that include link relationships
    as nested resources or HAL-style links.
    """
    
    def __init__(self):
        self.components: Dict[str, Any] = {
            "schemas": {},
            "parameters": {},
            "responses": {}
        }
    
    def generate_object_schema(
        self,
        object_type: ObjectType,
        link_types: List[LinkType]
    ) -> Dict[str, Any]:
        """Generate OpenAPI schema for an object type"""
        schema = {
            "type": "object",
            "title": object_type.display_name,
            "description": object_type.description,
            "properties": {
                "id": {
                    "type": "string",
                    "format": "uuid",
                    "readOnly": True
                }
            },
            "required": ["id"]
        }
        
        # Add properties
        for prop in object_type.properties:
            prop_schema = self._generate_property_schema(prop)
            schema["properties"][prop.name] = prop_schema
            
            if prop.is_required:
                schema["required"].append(prop.name)
        
        # Add link fields as _links (HAL style)
        links_schema = self._generate_links_schema(object_type, link_types)
        if links_schema:
            schema["properties"]["_links"] = links_schema
        
        # Add embedded resources
        embedded_schema = self._generate_embedded_schema(object_type, link_types)
        if embedded_schema:
            schema["properties"]["_embedded"] = embedded_schema
        
        # Add metadata
        schema["properties"]["_metadata"] = {
            "type": "object",
            "properties": {
                "versionHash": {"type": "string"},
                "createdAt": {"type": "string", "format": "date-time"},
                "createdBy": {"type": "string"},
                "modifiedAt": {"type": "string", "format": "date-time"},
                "modifiedBy": {"type": "string"}
            },
            "readOnly": True
        }
        
        self.components["schemas"][object_type.name] = schema
        return schema
    
    def _generate_property_schema(self, prop: Property) -> Dict[str, Any]:
        """Generate OpenAPI schema for a property"""
        schema = {
            "description": prop.description
        }
        
        # Map data type
        base_schema = self._map_data_type_to_openapi(prop.data_type_id)
        
        if prop.is_array:
            schema["type"] = "array"
            schema["items"] = base_schema
        else:
            schema.update(base_schema)
        
        # Add constraints from semantic type
        if prop.semantic_type_id:
            semantic_type = semantic_type_registry.get(prop.semantic_type_id)
            if semantic_type:
                for rule in semantic_type.validation_rules:
                    if rule.type == "pattern":
                        schema["pattern"] = rule.value
                    elif rule.type == "min_value":
                        schema["minimum"] = rule.value
                    elif rule.type == "max_value":
                        schema["maximum"] = rule.value
                    elif rule.type == "enum":
                        schema["enum"] = rule.value
        
        # Add default value
        if prop.default_value is not None:
            schema["default"] = prop.default_value
        
        return schema
    
    def _generate_links_schema(
        self,
        object_type: ObjectType,
        link_types: List[LinkType]
    ) -> Optional[Dict[str, Any]]:
        """Generate HAL-style _links schema"""
        links = {}
        
        # Self link
        links["self"] = {
            "type": "object",
            "properties": {
                "href": {"type": "string", "format": "uri"}
            }
        }
        
        # Add links for relationships
        forward_links = [
            lt for lt in link_types 
            if lt.fromTypeId == object_type.id
        ]
        
        for link in forward_links:
            link_name = link.name.lower().replace(" ", "_")
            if self._is_many(link.cardinality):
                links[link_name] = {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "href": {"type": "string", "format": "uri"},
                            "title": {"type": "string"}
                        }
                    }
                }
            else:
                links[link_name] = {
                    "type": "object",
                    "properties": {
                        "href": {"type": "string", "format": "uri"},
                        "title": {"type": "string"}
                    }
                }
        
        if len(links) > 1:  # More than just self link
            return {
                "type": "object",
                "properties": links,
                "readOnly": True
            }
        
        return None
    
    def _generate_embedded_schema(
        self,
        object_type: ObjectType,
        link_types: List[LinkType]
    ) -> Optional[Dict[str, Any]]:
        """Generate _embedded schema for expandable resources"""
        embedded = {}
        
        # Forward links that might be embedded
        forward_links = [
            lt for lt in link_types 
            if lt.fromTypeId == object_type.id
        ]
        
        for link in forward_links:
            link_name = link.name.lower().replace(" ", "_")
            target_ref = f"#/components/schemas/{link.toTypeId}"
            
            if self._is_many(link.cardinality):
                embedded[link_name] = {
                    "type": "array",
                    "items": {"$ref": target_ref}
                }
            else:
                embedded[link_name] = {"$ref": target_ref}
        
        if embedded:
            return {
                "type": "object",
                "properties": embedded,
                "readOnly": True
            }
        
        return None
    
    def _map_data_type_to_openapi(self, data_type_id: str) -> Dict[str, Any]:
        """Map OMS data type to OpenAPI type"""
        # Check if it's a struct type
        if struct_type_registry.exists(data_type_id):
            struct_type = struct_type_registry.get(data_type_id)
            return {"$ref": f"#/components/schemas/{struct_type.name}"}
        
        return OPENAPI_TYPE_MAPPING.get(data_type_id, {"type": "string"})
    
    def generate_paths(
        self,
        object_types: List[ObjectType],
        link_types: List[LinkType]
    ) -> Dict[str, Any]:
        """Generate OpenAPI paths for all object types"""
        paths = {}
        
        for obj_type in object_types:
            if obj_type.status == Status.ACTIVE:
                base_path = f"/{obj_type.name.lower()}s"
                
                # Collection endpoints
                paths[base_path] = {
                    "get": self._generate_list_operation(obj_type),
                    "post": self._generate_create_operation(obj_type)
                }
                
                # Item endpoints
                item_path = f"{base_path}/{{id}}"
                paths[item_path] = {
                    "get": self._generate_get_operation(obj_type),
                    "put": self._generate_update_operation(obj_type),
                    "delete": self._generate_delete_operation(obj_type)
                }
                
                # Link endpoints
                forward_links = [
                    lt for lt in link_types 
                    if lt.fromTypeId == obj_type.id
                ]
                
                for link in forward_links:
                    link_path = f"{item_path}/{link.name.lower().replace(' ', '_')}"
                    paths[link_path] = self._generate_link_operations(obj_type, link)
        
        return paths
    
    def _generate_list_operation(self, object_type: ObjectType) -> Dict[str, Any]:
        """Generate list operation"""
        return {
            "summary": f"List {object_type.display_name}s",
            "operationId": f"list{object_type.name}s",
            "tags": [object_type.name],
            "parameters": [
                {"$ref": "#/components/parameters/limit"},
                {"$ref": "#/components/parameters/offset"},
                {"$ref": "#/components/parameters/sort"},
                {"$ref": "#/components/parameters/filter"}
            ],
            "responses": {
                "200": {
                    "description": "Success",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "data": {
                                        "type": "array",
                                        "items": {"$ref": f"#/components/schemas/{object_type.name}"}
                                    },
                                    "meta": {
                                        "type": "object",
                                        "properties": {
                                            "total": {"type": "integer"},
                                            "limit": {"type": "integer"},
                                            "offset": {"type": "integer"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    
    def _generate_create_operation(self, object_type: ObjectType) -> Dict[str, Any]:
        """Generate create operation"""
        return {
            "summary": f"Create {object_type.display_name}",
            "operationId": f"create{object_type.name}",
            "tags": [object_type.name],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": f"#/components/schemas/{object_type.name}Create"}
                    }
                }
            },
            "responses": {
                "201": {
                    "description": "Created",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": f"#/components/schemas/{object_type.name}"}
                        }
                    }
                }
            }
        }
    
    def _generate_get_operation(self, object_type: ObjectType) -> Dict[str, Any]:
        """Generate get operation"""
        return {
            "summary": f"Get {object_type.display_name}",
            "operationId": f"get{object_type.name}",
            "tags": [object_type.name],
            "parameters": [
                {
                    "name": "id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "format": "uuid"}
                },
                {"$ref": "#/components/parameters/expand"}
            ],
            "responses": {
                "200": {
                    "description": "Success",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": f"#/components/schemas/{object_type.name}"}
                        }
                    }
                },
                "404": {"description": "Not Found"}
            }
        }
    
    def _generate_update_operation(self, object_type: ObjectType) -> Dict[str, Any]:
        """Generate update operation"""
        return {
            "summary": f"Update {object_type.display_name}",
            "operationId": f"update{object_type.name}",
            "tags": [object_type.name],
            "parameters": [
                {
                    "name": "id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "format": "uuid"}
                }
            ],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": f"#/components/schemas/{object_type.name}Update"}
                    }
                }
            },
            "responses": {
                "200": {
                    "description": "Success",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": f"#/components/schemas/{object_type.name}"}
                        }
                    }
                },
                "404": {"description": "Not Found"}
            }
        }
    
    def _generate_delete_operation(self, object_type: ObjectType) -> Dict[str, Any]:
        """Generate delete operation"""
        return {
            "summary": f"Delete {object_type.display_name}",
            "operationId": f"delete{object_type.name}",
            "tags": [object_type.name],
            "parameters": [
                {
                    "name": "id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string", "format": "uuid"}
                }
            ],
            "responses": {
                "204": {"description": "Deleted"},
                "404": {"description": "Not Found"}
            }
        }
    
    def _generate_link_operations(
        self,
        object_type: ObjectType,
        link_type: LinkType
    ) -> Dict[str, Any]:
        """Generate operations for link endpoints"""
        operations = {}
        
        if self._is_many(link_type.cardinality):
            # List linked objects
            operations["get"] = {
                "summary": f"Get {link_type.displayName} for {object_type.display_name}",
                "operationId": f"get{object_type.name}{link_type.name}",
                "tags": [object_type.name],
                "parameters": [
                    {"$ref": "#/components/parameters/limit"},
                    {"$ref": "#/components/parameters/offset"}
                ],
                "responses": {
                    "200": {
                        "description": "Success",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {"$ref": f"#/components/schemas/{link_type.toTypeId}"}
                                }
                            }
                        }
                    }
                }
            }
            
            # Add/remove operations
            operations["post"] = {
                "summary": f"Add {link_type.displayName}",
                "operationId": f"add{object_type.name}{link_type.name}",
                "tags": [object_type.name],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "ids": {
                                        "type": "array",
                                        "items": {"type": "string", "format": "uuid"}
                                    }
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "Success"}
                }
            }
        else:
            # Single link
            operations["get"] = {
                "summary": f"Get {link_type.displayName} for {object_type.display_name}",
                "operationId": f"get{object_type.name}{link_type.name}",
                "tags": [object_type.name],
                "responses": {
                    "200": {
                        "description": "Success",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": f"#/components/schemas/{link_type.toTypeId}"}
                            }
                        }
                    },
                    "404": {"description": "Not Found"}
                }
            }
        
        return operations
    
    def generate_complete_spec(
        self,
        object_types: List[ObjectType],
        link_types: List[LinkType],
        api_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate complete OpenAPI specification"""
        # Generate schemas for all types
        for obj_type in object_types:
            if obj_type.status == Status.ACTIVE:
                self.generate_object_schema(obj_type, link_types)
                self._generate_create_update_schemas(obj_type)
        
        # Add common parameters
        self.components["parameters"] = {
            "limit": {
                "name": "limit",
                "in": "query",
                "schema": {"type": "integer", "default": 20, "maximum": 100}
            },
            "offset": {
                "name": "offset",
                "in": "query",
                "schema": {"type": "integer", "default": 0}
            },
            "sort": {
                "name": "sort",
                "in": "query",
                "schema": {"type": "string"},
                "description": "Sort field and order (e.g., 'name' or '-created_at')"
            },
            "filter": {
                "name": "filter",
                "in": "query",
                "schema": {"type": "string"},
                "description": "Filter expression"
            },
            "expand": {
                "name": "expand",
                "in": "query",
                "schema": {"type": "string"},
                "description": "Comma-separated list of relationships to expand"
            }
        }
        
        # Generate paths
        paths = self.generate_paths(object_types, link_types)
        
        # Complete spec
        spec = {
            "openapi": "3.0.3",
            "info": api_info,
            "servers": [
                {"url": "/api/v1", "description": "API v1"}
            ],
            "paths": paths,
            "components": self.components
        }
        
        return spec
    
    def _generate_create_update_schemas(self, object_type: ObjectType):
        """Generate create and update schemas"""
        # Create schema (no ID, required fields)
        create_schema = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        # Update schema (all optional)
        update_schema = {
            "type": "object",
            "properties": {}
        }
        
        for prop in object_type.properties:
            if not prop.is_primary_key:
                prop_schema = self._generate_property_schema(prop)
                create_schema["properties"][prop.name] = prop_schema
                update_schema["properties"][prop.name] = prop_schema
                
                if prop.is_required:
                    create_schema["required"].append(prop.name)
        
        self.components["schemas"][f"{object_type.name}Create"] = create_schema
        self.components["schemas"][f"{object_type.name}Update"] = update_schema


# Global instance
openapi_generator = OpenAPISchemaGenerator()