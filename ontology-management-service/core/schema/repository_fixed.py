"""
Schema Repository - Fixed Version
Properly handles TerminusDB schema operations
"""
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from database.clients.unified_database_client import UnifiedDatabaseClient
from models.domain import ObjectType, ObjectTypeCreate
from shared.terminus_context import get_author

logger = logging.getLogger(__name__)


class SchemaRepository:
    """Schema database operations repository"""

    def __init__(self, db: UnifiedDatabaseClient):
        """
        Initializes the SchemaRepository.

        Args:
            db: An instance of UnifiedDatabaseClient.
        """
        self.db = db
        self.tdb = db.terminus_client if hasattr(db, 'terminus_client') else None
        self.db_name = "arrakis"  # Database name
        logger.debug("SchemaRepository initialized with UnifiedDatabaseClient.")

    async def list_all_object_types(self, branch: str = "main") -> List[Dict[str, Any]]:
        """
        List all ObjectTypes from the schema
        
        Args:
            branch (str): Branch name to query
            
        Returns:
            List[Dict[str, Any]]: List of object types
        """
        try:
            if not self.tdb:
                raise ValueError("TerminusDB client not available")
                
            # Get the current schema
            schema = await self.tdb.get_schema(self.db_name)
            
            # Extract classes from schema
            object_types = []
            if "@graph" in schema:
                for item in schema["@graph"]:
                    if item.get("@type") == "Class":
                        # Convert from schema format to our ObjectType format
                        object_type = {
                            "@type": "ObjectType",
                            "@id": item.get("@id", ""),
                            "name": item.get("@id", "").replace("terminusdb:///schema#", ""),
                            "displayName": item.get("@label", ""),
                            "description": item.get("@comment", ""),
                            "properties": [],
                            "isActive": True
                        }
                        object_types.append(object_type)
            
            return object_types
        except Exception as e:
            logger.error(f"Error listing all object types from branch '{branch}': {e}")
            raise

    async def create_new_object_type(self, branch: str, data: ObjectTypeCreate, author: str) -> bool:
        """
        Create a new ObjectType in the schema
        
        Args:
            branch (str): Branch name
            data (ObjectTypeCreate): ObjectType data to create
            author (str): Author of the operation
            
        Returns:
            bool: Success status
        """
        try:
            if not self.tdb:
                raise ValueError("TerminusDB client not available")
                
            # Get current schema
            current_schema = await self.tdb.get_schema(self.db_name)
            
            # Prepare new class definition
            new_class = {
                "@id": f"terminusdb:///schema#{data.name}",
                "@type": "Class",
                "@label": data.display_name or data.name,
                "@comment": data.description or f"{data.name} object type"
            }
            
            # Add to schema graph
            if "@graph" not in current_schema:
                current_schema["@graph"] = []
            
            # Check if class already exists
            for item in current_schema["@graph"]:
                if item.get("@id") == new_class["@id"]:
                    logger.warning(f"ObjectType '{data.name}' already exists")
                    return False
                    
            current_schema["@graph"].append(new_class)
            
            # Update schema
            await self.tdb.update_schema(
                self.db_name,
                current_schema,
                commit_msg=f"Create ObjectType: {data.name}"
            )
            
            # Also store metadata in documents for our system
            metadata_doc = {
                "@type": "ObjectTypeMetadata",
                "@id": f"ObjectTypeMetadata/{data.name}",
                "name": data.name,
                "displayName": data.display_name or data.name,
                "description": data.description or "",
                "createdBy": author,
                "createdAt": datetime.utcnow().isoformat(),
                "modifiedBy": author,
                "modifiedAt": datetime.utcnow().isoformat(),
                "versionHash": str(uuid.uuid4()),
                "properties": [],
                "isActive": True
            }
            
            await self.tdb.insert_document(
                self.db_name,
                branch,
                metadata_doc,
                commit_msg=f"Create ObjectType metadata: {data.name}"
            )
            
            return True
        except Exception as e:
            logger.error(f"Error creating new object type '{data.name}': {e}")
            raise

    async def get_object_type_by_name(self, name: str, branch: str) -> Optional[Dict[str, Any]]:
        """
        Get ObjectType by name
        """
        try:
            if not self.tdb:
                raise ValueError("TerminusDB client not available")
                
            # Get schema
            schema = await self.tdb.get_schema(self.db_name)
            
            # Find class in schema
            if "@graph" in schema:
                for item in schema["@graph"]:
                    if item.get("@type") == "Class" and item.get("@id") == f"terminusdb:///schema#{name}":
                        # Get metadata document
                        metadata = await self.tdb.get_document(
                            self.db_name,
                            branch,
                            f"ObjectTypeMetadata/{name}"
                        )
                        
                        if metadata:
                            return metadata
                        else:
                            # Return basic info from schema
                            return {
                                "@type": "ObjectType",
                                "@id": f"ObjectType/{name}",
                                "name": name,
                                "displayName": item.get("@label", name),
                                "description": item.get("@comment", ""),
                                "properties": [],
                                "isActive": True
                            }
            
            logger.warning(f"ObjectType '{name}' not found in branch '{branch}'.")
            return None
        except Exception as e:
            logger.error(f"Error getting object type by name '{name}': {e}", exc_info=True)
            return None

    async def update_object_type(self, schema_id: str, branch: str, schema_def: Dict[str, Any], updated_by: str) -> bool:
        """
        Update ObjectType
        """
        try:
            if not self.tdb:
                raise ValueError("TerminusDB client not available")
                
            # Extract name from schema_id
            name = schema_id.replace("ObjectType/", "")
            
            # Update metadata document
            metadata_doc = await self.tdb.get_document(
                self.db_name,
                branch, 
                f"ObjectTypeMetadata/{name}"
            )
            
            if metadata_doc:
                # Update fields
                metadata_doc.update(schema_def)
                metadata_doc["modifiedBy"] = updated_by
                metadata_doc["modifiedAt"] = datetime.utcnow().isoformat()
                
                await self.tdb.update_document(
                    self.db_name,
                    branch,
                    metadata_doc,
                    commit_msg=f"Update ObjectType metadata: {name}"
                )
                
            # Also update schema if display name or description changed
            if "displayName" in schema_def or "description" in schema_def:
                schema = await self.tdb.get_schema(self.db_name)
                
                if "@graph" in schema:
                    for item in schema["@graph"]:
                        if item.get("@id") == f"terminusdb:///schema#{name}":
                            if "displayName" in schema_def:
                                item["@label"] = schema_def["displayName"]
                            if "description" in schema_def:
                                item["@comment"] = schema_def["description"]
                            
                            await self.tdb.update_schema(
                                self.db_name,
                                schema,
                                commit_msg=f"Update ObjectType schema: {name}"
                            )
                            break
            
            return True
        except Exception as e:
            logger.error(f"Error updating object type '{schema_id}': {e}", exc_info=True)
            return False
    
    async def get_object_type_by_id(self, schema_id: str, branch: str) -> Optional[Dict[str, Any]]:
        """
        Get ObjectType by ID
        """
        # Extract name from ID
        name = schema_id.replace("ObjectType/", "")
        return await self.get_object_type_by_name(name, branch)
    
    async def mark_object_type_deleted(self, schema_id: str, branch: str, deleted_by: str) -> bool:
        """
        Mark ObjectType as deleted (soft delete)
        """
        try:
            if not self.tdb:
                raise ValueError("TerminusDB client not available")
                
            # Extract name from schema_id
            name = schema_id.replace("ObjectType/", "")
            
            # Update metadata document
            metadata_doc = await self.tdb.get_document(
                self.db_name,
                branch,
                f"ObjectTypeMetadata/{name}"
            )
            
            if metadata_doc:
                metadata_doc["status"] = "deleted"
                metadata_doc["deletedBy"] = deleted_by
                metadata_doc["deletedAt"] = datetime.utcnow().isoformat()
                metadata_doc["isActive"] = False
                
                await self.tdb.update_document(
                    self.db_name,
                    branch,
                    metadata_doc,
                    commit_msg=f"Mark ObjectType as deleted: {name}"
                )
                
                logger.info(f"Marked ObjectType '{schema_id}' as deleted in branch '{branch}'")
                return True
            
            return False
        except Exception as e:
            logger.error(f"Error marking object type '{schema_id}' as deleted: {e}", exc_info=True)
            return False