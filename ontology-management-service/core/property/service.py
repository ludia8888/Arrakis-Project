"""Property service implementation"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import re

from core.interfaces.property import PropertyServiceProtocol
from models.domain import Property, PropertyCreate, PropertyUpdate
from database.clients.terminus_db import TerminusDBClient
from models.exceptions import ResourceNotFoundError, ValidationError, ConflictError


logger = logging.getLogger(__name__)


class PropertyService(PropertyServiceProtocol):
    """Service for managing properties"""
    
    def __init__(self, terminus_client: TerminusDBClient):
        self.terminus_client = terminus_client
        self.valid_types = [
            "string", "integer", "number", "boolean", 
            "date", "datetime", "object", "array",
            "reference", "enum", "json"
        ]
    
    async def create_property(
        self, 
        branch: str,
        property_data: PropertyCreate,
        created_by: str
    ) -> Property:
        """Create a new property"""
        try:
            # Validate property data
            validation_result = await self.validate_property(property_data.dict())
            if not validation_result["valid"]:
                raise ValidationException(f"Invalid property: {', '.join(validation_result['errors'])}")
            
            # Generate property ID
            property_id = f"Property/{uuid.uuid4()}"
            
            # Create property document
            property_doc = {
                "@id": property_id,
                "@type": "Property",
                "name": property_data.name,
                "display_name": property_data.display_name or property_data.name,
                "description": property_data.description,
                "data_type_id": property_data.data_type_id,
                "semantic_type_id": property_data.semantic_type_id,
                "object_type": property_data.object_type,
                "branch": branch,
                "required": property_data.required or False,
                "unique": property_data.unique or False,
                "indexed": property_data.indexed or False,
                "searchable": property_data.searchable or False,
                "validation_rules": property_data.validation_rules or {},
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "created_by": created_by,
                "updated_by": created_by
            }
            
            # Add type-specific attributes
            if property_data.min_value is not None:
                property_doc["min_value"] = property_data.min_value
            if property_data.max_value is not None:
                property_doc["max_value"] = property_data.max_value
            if property_data.min_length is not None:
                property_doc["min_length"] = property_data.min_length
            if property_data.max_length is not None:
                property_doc["max_length"] = property_data.max_length
            if property_data.pattern:
                property_doc["pattern"] = property_data.pattern
            if property_data.format:
                property_doc["format"] = property_data.format
            if property_data.enum_values:
                property_doc["enum_values"] = property_data.enum_values
            if property_data.default_value is not None:
                property_doc["default_value"] = property_data.default_value
            
            # Save to database
            await self.terminus_client.create_document(
                branch=branch,
                document=property_doc
            )
            
            logger.info(f"Created property: {property_id}")
            return Property(**self._convert_from_db(property_doc))
            
        except Exception as e:
            logger.error(f"Failed to create property: {str(e)}")
            raise
    
    async def get_property(
        self, 
        branch: str, 
        property_id: str
    ) -> Optional[Property]:
        """Get a property by ID"""
        try:
            result = await self.terminus_client.get_document(
                branch=branch,
                document_id=property_id
            )
            
            if not result:
                raise NotFoundException(f"Property {property_id} not found")
            
            return Property(**self._convert_from_db(result))
            
        except Exception as e:
            logger.error(f"Failed to get property {property_id}: {str(e)}")
            raise
    
    async def list_properties(
        self,
        branch: str,
        object_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Property]:
        """List properties with optional filtering"""
        try:
            # Build query
            query = {
                "@type": "Property",
                "branch": branch
            }
            
            if object_type:
                query["object_type"] = object_type
            
            # Execute query using TerminusDB WOQL
            # Note: TerminusDB doesn't have query_documents, we need to use query with WOQL
            woql_query = f"""
                WOQL.and(
                    WOQL.triple("v:Property", "rdf:type", "@schema:Property"),
                    WOQL.triple("v:Property", "branch", "{branch}")
                )
            """
            
            # For now, return empty list until we implement proper WOQL query
            results = []
            logger.warning("Property query not fully implemented for TerminusDB")
            
            properties = []
            for doc in results:
                properties.append(Property(**self._convert_from_db(doc)))
            
            return properties
            
        except Exception as e:
            logger.error(f"Failed to list properties: {str(e)}")
            raise
    
    async def update_property(
        self,
        branch: str,
        property_id: str,
        property_data: PropertyUpdate,
        updated_by: str
    ) -> Property:
        """Update a property"""
        try:
            # Get existing property
            existing = await self.get_property(branch, property_id)
            if not existing:
                raise NotFoundException(f"Property {property_id} not found")
            
            # Prepare update document
            update_doc = {
                "@id": property_id,
                "@type": "Property",
                "updated_at": datetime.utcnow().isoformat(),
                "updated_by": updated_by
            }
            
            # Update fields if provided
            update_data = property_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                if value is not None:
                    # Convert snake_case to camelCase for DB
                    db_field = self._to_camel_case(field)
                    update_doc[db_field] = value
            
            # Update in database
            await self.terminus_client.update_document(
                branch=branch,
                document=update_doc
            )
            
            # Get updated property
            updated = await self.get_property(branch, property_id)
            logger.info(f"Updated property: {property_id}")
            return updated
            
        except Exception as e:
            logger.error(f"Failed to update property {property_id}: {str(e)}")
            raise
    
    async def delete_property(
        self,
        branch: str,
        property_id: str,
        deleted_by: str
    ) -> bool:
        """Delete a property"""
        try:
            # Check if property exists
            existing = await self.get_property(branch, property_id)
            if not existing:
                raise NotFoundException(f"Property {property_id} not found")
            
            # Delete from database
            await self.terminus_client.delete_document(
                branch=branch,
                document_id=property_id
            )
            
            logger.info(f"Deleted property: {property_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete property {property_id}: {str(e)}")
            raise
    
    async def validate_property(
        self,
        property_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate a property definition"""
        errors = []
        warnings = []
        
        # Check required fields
        required_fields = ["name", "data_type_id", "object_type"]
        for field in required_fields:
            if not property_data.get(field):
                errors.append(f"Property {field} is required")
        
        # Validate property name
        if property_data.get("name"):
            if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', property_data["name"]):
                errors.append("Property name must start with a letter and contain only letters, numbers, and underscores")
        
        # Validate data type
        if property_data.get("data_type_id"):
            type_name = property_data["data_type_id"].split("/")[-1] if "/" in property_data["data_type_id"] else property_data["data_type_id"]
            if type_name not in self.valid_types:
                errors.append(f"Invalid data type. Must be one of: {', '.join(self.valid_types)}")
        
        # Type-specific validations
        data_type = property_data.get("data_type_id", "").split("/")[-1]
        if data_type in ["integer", "number"]:
            if "min_value" in property_data and "max_value" in property_data:
                if property_data["min_value"] > property_data["max_value"]:
                    errors.append("min_value cannot be greater than max_value")
        
        elif data_type == "string":
            if "min_length" in property_data and "max_length" in property_data:
                if property_data["min_length"] > property_data["max_length"]:
                    errors.append("min_length cannot be greater than max_length")
            
            if property_data.get("pattern"):
                try:
                    re.compile(property_data["pattern"])
                except re.error:
                    errors.append("Invalid regex pattern")
        
        # Warnings
        if not property_data.get("description"):
            warnings.append("Property has no description")
        
        if not property_data.get("display_name"):
            warnings.append("Property has no display name")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    async def get_properties_by_object_type(
        self,
        branch: str,
        object_type_id: str
    ) -> List[Property]:
        """Get all properties for a specific object type"""
        try:
            query = {
                "@type": "Property",
                "object_type": object_type_id,
                "branch": branch
            }
            
            results = await self.terminus_client.query_documents(
                branch=branch,
                query=query
            )
            
            properties = []
            for doc in results:
                properties.append(Property(**self._convert_from_db(doc)))
            
            return properties
            
        except Exception as e:
            logger.error(f"Failed to get properties for object type {object_type_id}: {str(e)}")
            raise
    
    def _convert_from_db(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Convert database document to model format"""
        # Remove @ prefixed fields
        clean_doc = {k.replace("@", ""): v for k, v in doc.items() if not k.startswith("@context")}
        
        # Convert camelCase to snake_case
        snake_doc = {}
        for key, value in clean_doc.items():
            snake_key = self._to_snake_case(key)
            snake_doc[snake_key] = value
        
        # Ensure ID is present
        if "id" not in snake_doc and "@id" in doc:
            snake_doc["id"] = doc["@id"]
        
        return snake_doc
    
    def _to_snake_case(self, name: str) -> str:
        """Convert camelCase to snake_case"""
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    
    def _to_camel_case(self, name: str) -> str:
        """Convert snake_case to camelCase"""
        components = name.split('_')
        return components[0] + ''.join(x.title() for x in components[1:])