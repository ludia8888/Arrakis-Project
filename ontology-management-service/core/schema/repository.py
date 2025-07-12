"""
Schema Repository - Simplified Version
Stores schema definitions as documents to bypass TerminusDB schema validation issues
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
        List all ObjectType documents from the specified branch
        
        For now, we'll store ObjectTypes as regular documents
        """
        try:
            if not self.tdb:
                raise ValueError("TerminusDB client not available")
                
            # Query for all documents of type SchemaDefinition
            # Using a simple WOQL query to get all documents of type SchemaDefinition
            woql_query = """
            WOQL.triple("v:Doc", "rdf:type", "doc:SchemaDefinition")
            """
            
            if hasattr(self.db, 'terminus_client') and self.db.terminus_client:
                query_result = await self.db.terminus_client.query_branch(
                    db_name=self.db_name,
                    branch_name=branch,
                    query=woql_query
                )
                # Extract documents from WOQL result
                documents = []
                if query_result and 'bindings' in query_result:
                    for binding in query_result['bindings']:
                        if 'Doc' in binding:
                            doc_id = binding['Doc']
                            # Get full document details
                            doc = await self.db.terminus_client.get_document(
                                db_name=self.db_name,
                                branch_name=branch,
                                document_id=doc_id
                            )
                            if doc and doc.get('schemaType') == 'ObjectType':
                                documents.append(doc)
                query_result = documents
            else:
                logger.error("TerminusDB client not available")
                return []
            
            # Convert to list format
            schemas = []
            if query_result and isinstance(query_result, list):
                for doc in query_result:
                    schemas.append({
                        "@type": "ObjectType",
                        "@id": doc.get("@id", ""),
                        "name": doc.get("name", ""),
                        "displayName": doc.get("displayName", ""),
                        "description": doc.get("description", ""),
                        "properties": doc.get("properties", []),
                        "isActive": doc.get("isActive", True),
                        "createdBy": doc.get("createdBy", ""),
                        "createdAt": doc.get("createdAt", ""),
                        "modifiedBy": doc.get("modifiedBy", ""),
                        "modifiedAt": doc.get("modifiedAt", "")
                    })
            
            return schemas
            
        except Exception as e:
            logger.error(f"Error listing all object types from branch '{branch}': {e}")
            # Return empty list instead of raising to allow the service to continue
            return []

    async def create_new_object_type(self, branch: str, data: ObjectTypeCreate, author: str) -> bool:
        """
        Create a new ObjectType as a document
        
        We store schema definitions as regular documents with a special type
        to bypass TerminusDB's strict schema validation
        """
        try:
            if not self.tdb:
                raise ValueError("TerminusDB client not available")
                
            # Create a schema definition document
            doc = {
                "@type": "SchemaDefinition",  # Use a generic type
                "@id": f"SchemaDefinition/{data.name}",
                "schemaType": "ObjectType",  # Track what kind of schema this is
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
            
            # Actually store the document in the database
            if hasattr(self.db, 'terminus_client') and self.db.terminus_client:
                result = await self.db.terminus_client.insert_document(
                    db_name=self.db_name,
                    branch_name=branch,
                    document=doc,
                    commit_msg=f"Created ObjectType: {data.name}"
                )
            else:
                logger.error("TerminusDB client not available")
                return False
            
            if result:
                logger.info(f"Schema definition for '{data.name}' successfully created in database")
                return True
            else:
                logger.error(f"Failed to insert schema definition for '{data.name}'")
                return False
            
        except Exception as e:
            logger.error(f"Error creating new object type '{data.name}': {e}")
            return False

    async def get_object_type_by_name(self, name: str, branch: str) -> Optional[Dict[str, Any]]:
        """
        Get ObjectType by name
        """
        try:
            if not self.tdb:
                raise ValueError("TerminusDB client not available")
                
            # Query for the specific schema document
            if hasattr(self.db, 'terminus_client') and self.db.terminus_client:
                query_result = await self.db.terminus_client.get_document(
                    db_name=self.db_name,
                    branch_name=branch,
                    document_id=f"SchemaDefinition/{name}"
                )
            else:
                logger.error("TerminusDB client not available")
                return None
            
            if query_result:
                # Convert to ObjectType format
                return {
                    "@type": "ObjectType",
                    "@id": f"ObjectType/{name}",
                    "name": query_result.get("name", name),
                    "displayName": query_result.get("displayName", name),
                    "description": query_result.get("description", ""),
                    "properties": query_result.get("properties", []),
                    "isActive": query_result.get("isActive", True),
                    "createdBy": query_result.get("createdBy", ""),
                    "createdAt": query_result.get("createdAt", ""),
                    "modifiedBy": query_result.get("modifiedBy", ""),
                    "modifiedAt": query_result.get("modifiedAt", ""),
                    "versionHash": query_result.get("versionHash", "")
                }
            
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
                
            # Extract name from schema_id if it contains prefix
            name = schema_id.replace("ObjectType/", "").replace("SchemaDefinition/", "")
            
            # Get existing document
            if hasattr(self.db, 'terminus_client') and self.db.terminus_client:
                existing = await self.db.terminus_client.get_document(
                    db_name=self.db_name,
                    branch_name=branch,
                    document_id=f"SchemaDefinition/{name}"
                )
            else:
                logger.error("TerminusDB client not available")
                return False
            
            if not existing:
                logger.error(f"ObjectType '{schema_id}' not found for update")
                return False
            
            # Update the document
            updated_doc = {
                **existing,
                **schema_def,
                "@type": "SchemaDefinition",
                "@id": f"SchemaDefinition/{name}",
                "schemaType": "ObjectType",
                "modifiedBy": updated_by,
                "modifiedAt": datetime.utcnow().isoformat(),
                "versionHash": str(uuid.uuid4())
            }
            
            # Replace the document
            if hasattr(self.db, 'terminus_client') and self.db.terminus_client:
                result = await self.db.terminus_client.update_document(
                    db_name=self.db_name,
                    branch_name=branch,
                    document=updated_doc,
                    commit_msg=f"Updated ObjectType: {name}"
                )
            else:
                logger.error("TerminusDB client not available")
                return False
            
            if result:
                logger.info(f"Updated ObjectType '{schema_id}' successfully")
                return True
            else:
                logger.error(f"Failed to update ObjectType '{schema_id}'")
                return False
                
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
                
            # Extract name from schema_id if it contains prefix
            name = schema_id.replace("ObjectType/", "").replace("SchemaDefinition/", "")
            
            # Get existing document
            if hasattr(self.db, 'terminus_client') and self.db.terminus_client:
                existing = await self.db.terminus_client.get_document(
                    db_name=self.db_name,
                    branch_name=branch,
                    document_id=f"SchemaDefinition/{name}"
                )
            else:
                logger.error("TerminusDB client not available")
                return False
            
            if not existing:
                logger.error(f"ObjectType '{schema_id}' not found for deletion")
                return False
            
            # Mark as deleted (soft delete)
            updated_doc = {
                **existing,
                "isActive": False,
                "deletedBy": deleted_by,
                "deletedAt": datetime.utcnow().isoformat(),
                "modifiedBy": deleted_by,
                "modifiedAt": datetime.utcnow().isoformat()
            }
            
            # Replace the document
            if hasattr(self.db, 'terminus_client') and self.db.terminus_client:
                result = await self.db.terminus_client.update_document(
                    db_name=self.db_name,
                    branch_name=branch,
                    document=updated_doc,
                    commit_msg=f"Soft delete ObjectType: {name}"
                )
            else:
                logger.error("TerminusDB client not available")
                return False
            
            if result:
                logger.info(f"Marked ObjectType '{schema_id}' as deleted successfully")
                return True
            else:
                logger.error(f"Failed to mark ObjectType '{schema_id}' as deleted")
                return False
                
        except Exception as e:
            logger.error(f"Error marking object type '{schema_id}' as deleted: {e}", exc_info=True)
            return False