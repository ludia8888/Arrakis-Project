"""
Extended Schema Service with full implementation
Handles all schema types in OMS
"""
import logging
import json
from typing import Any, Dict, List, Optional
from datetime import datetime
import uuid
import httpx
from fastapi import HTTPException

from database.clients.terminus_db import TerminusDBClient
from models.domain import (
    ObjectType, ObjectTypeCreate, ObjectTypeUpdate,
    Property, PropertyCreate, PropertyUpdate,
    Status
)

logger = logging.getLogger(__name__)


async def safe_terminus_request(client, method: str, url: str, **kwargs) -> httpx.Response:
    """Safe wrapper for TerminusDB requests with timeout and error handling"""
    kwargs.setdefault('timeout', 5.0)
    try:
        if method == "POST":
            response = await client.post(url, **kwargs)
        elif method == "GET":
            response = await client.get(url, **kwargs)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        response.raise_for_status()
        return response
    except httpx.TimeoutException as exc:
        logger.error(f"TerminusDB timeout: {exc}")
        raise HTTPException(status_code=503, detail="Database timeout")
    except httpx.RequestError as exc:
        logger.error(f"TerminusDB unreachable: {exc}")
        raise HTTPException(status_code=503, detail="Database unavailable")
    except httpx.HTTPStatusError as exc:
        logger.error(f"TerminusDB error: {exc.response.status_code} - {exc.response.text}")
        raise


class ExtendedSchemaService:
    """Extended schema service with full type support"""
    
    def __init__(self, tdb_endpoint: Optional[str] = None, event_publisher: Optional[Any] = None):
        self.tdb_endpoint = tdb_endpoint or "http://localhost:6363"
        self.db_name = "oms"
        self.tdb = None
        self.event_publisher = event_publisher
    
    async def initialize(self):
        """Initialize service with TerminusDB connection"""
        try:
            self.tdb = TerminusDBClient(
                endpoint=self.tdb_endpoint,
                username="admin",
                password="root"
            )
            
            connected = await self.tdb.connect(
                team="admin",
                key="root",
                user="admin",
                db=self.db_name
            )
            
            if connected:
                logger.info(f"Extended Schema Service connected to TerminusDB")
            else:
                logger.error("Failed to connect to TerminusDB")
                
        except Exception as e:
            logger.error(f"Extended Schema Service initialization failed: {e}")
    
    # ==================== Properties ====================
    
    async def list_properties(self, branch: str, object_type_id: str) -> List[Dict[str, Any]]:
        """List all properties of an object type"""
        try:
            if not self.tdb or not self.tdb.connected:
                await self.initialize()
            
            # Query properties for specific object type
            result = await safe_terminus_request(
                self.tdb.client,
                "GET",
                f"{self.tdb.endpoint}/api/document/admin/{self.db_name}?type=Property",
                auth=("admin", "root")
            )
            
            if result.status_code == 200:
                text = result.text.strip()
                if not text:
                    return []
                
                properties = []
                for line in text.split('\n'):
                    if line.strip():
                        try:
                            prop = json.loads(line)
                            # Filter by object type
                            if prop.get('objectType') == f"ObjectType/{object_type_id}":
                                properties.append(prop)
                        except:
                            pass
                return properties
            return []
            
        except Exception as e:
            logger.error(f"Error listing properties: {e}")
            return []
    
    async def create_property(self, branch: str, object_type_id: str, data: PropertyCreate) -> Property:
        """Create a new property for an object type"""
        try:
            if not self.tdb or not self.tdb.connected:
                await self.initialize()
            
            # Create property document
            doc = {
                "@type": "Property",
                "@id": f"Property/{object_type_id}_{data.name}",
                "name": data.name,
                "displayName": data.display_name or data.name,
                "description": data.description or "",
                "dataType": data.data_type_id,
                "objectType": f"ObjectType/{object_type_id}",
                "required": data.is_required,
                "indexed": data.is_indexed
            }
            
            # Insert into database
            result = await self.tdb.client.post(
                f"{self.tdb.endpoint}/api/document/admin/{self.db_name}?author=OMS&message=Create Property",
                json=[doc],
                auth=("admin", "root")
            )
            
            if result.status_code in [200, 201]:
                logger.info(f"Created Property: {data.name} for ObjectType: {object_type_id}")
                
                return Property(
                    id=f"{object_type_id}_{data.name}",
                    object_type_id=object_type_id,
                    name=data.name,
                    display_name=data.display_name or data.name,
                    description=data.description,
                    data_type_id=data.data_type_id,
                    is_required=data.is_required,
                    is_indexed=data.is_indexed,
                    version_hash=str(uuid.uuid4())[:16],
                    created_at=datetime.now(),
                    modified_at=datetime.now()
                )
            else:
                raise Exception(f"Failed to create Property: {result.text}")
                
        except Exception as e:
            logger.error(f"Error creating property: {e}")
            raise
    
    # ==================== Shared Properties ====================
    
    async def list_shared_properties(self, branch: str) -> List[Dict[str, Any]]:
        """List all shared properties"""
        try:
            if not self.tdb or not self.tdb.connected:
                await self.initialize()
            
            result = await self.tdb.client.get(
                f"{self.tdb.endpoint}/api/document/admin/{self.db_name}?type=SharedProperty",
                auth=("admin", "root")
            )
            
            if result.status_code == 200:
                text = result.text.strip()
                if not text:
                    return []
                
                properties = []
                for line in text.split('\n'):
                    if line.strip():
                        try:
                            properties.append(json.loads(line))
                        except:
                            pass
                return properties
            return []
            
        except Exception as e:
            logger.error(f"Error listing shared properties: {e}")
            return []
    
    async def create_shared_property(self, branch: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new shared property"""
        try:
            if not self.tdb or not self.tdb.connected:
                await self.initialize()
            
            doc = {
                "@type": "SharedProperty",
                "@id": f"SharedProperty/{data['name']}",
                "name": data['name'],
                "displayName": data['displayName'],
                "description": data.get('description', ''),
                "dataType": data['dataType'],
                "constraints": data.get('constraints'),
                "defaultValue": data.get('defaultValue')
            }
            
            result = await self.tdb.client.post(
                f"{self.tdb.endpoint}/api/document/admin/{self.db_name}?author=OMS&message=Create SharedProperty",
                json=[doc],
                auth=("admin", "root")
            )
            
            if result.status_code in [200, 201]:
                logger.info(f"Created SharedProperty: {data['name']}")
                return doc
            else:
                raise Exception(f"Failed to create SharedProperty: {result.text}")
                
        except Exception as e:
            logger.error(f"Error creating shared property: {e}")
            raise
    
    # ==================== Link Types ====================
    
    async def list_link_types(self, branch: str) -> List[Dict[str, Any]]:
        """List all link types"""
        try:
            if not self.tdb or not self.tdb.connected:
                await self.initialize()
            
            result = await self.tdb.client.get(
                f"{self.tdb.endpoint}/api/document/admin/{self.db_name}?type=LinkType",
                auth=("admin", "root")
            )
            
            if result.status_code == 200:
                text = result.text.strip()
                if not text:
                    return []
                
                links = []
                for line in text.split('\n'):
                    if line.strip():
                        try:
                            links.append(json.loads(line))
                        except:
                            pass
                return links
            return []
            
        except Exception as e:
            logger.error(f"Error listing link types: {e}")
            return []
    
    async def create_link_type(self, branch: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new link type"""
        try:
            if not self.tdb or not self.tdb.connected:
                await self.initialize()
            
            doc = {
                "@type": "LinkType",
                "@id": f"LinkType/{data['name']}",
                "name": data['name'],
                "displayName": data['displayName'],
                "description": data.get('description', ''),
                "sourceObjectType": f"ObjectType/{data['sourceObjectType']}",
                "targetObjectType": f"ObjectType/{data['targetObjectType']}",
                "cardinality": data.get('cardinality', 'one-to-many')
            }
            
            result = await self.tdb.client.post(
                f"{self.tdb.endpoint}/api/document/admin/{self.db_name}?author=OMS&message=Create LinkType",
                json=[doc],
                auth=("admin", "root")
            )
            
            if result.status_code in [200, 201]:
                logger.info(f"Created LinkType: {data['name']}")
                return doc
            else:
                raise Exception(f"Failed to create LinkType: {result.text}")
                
        except Exception as e:
            logger.error(f"Error creating link type: {e}")
            raise
    
    # ==================== Action Types ====================
    
    async def list_action_types(self, branch: str) -> List[Dict[str, Any]]:
        """List all action types"""
        try:
            if not self.tdb or not self.tdb.connected:
                await self.initialize()
            
            result = await self.tdb.client.get(
                f"{self.tdb.endpoint}/api/document/admin/{self.db_name}?type=ActionType",
                auth=("admin", "root")
            )
            
            if result.status_code == 200:
                text = result.text.strip()
                if not text:
                    return []
                
                actions = []
                for line in text.split('\n'):
                    if line.strip():
                        try:
                            actions.append(json.loads(line))
                        except:
                            pass
                return actions
            return []
            
        except Exception as e:
            logger.error(f"Error listing action types: {e}")
            return []
    
    async def create_action_type(self, branch: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new action type"""
        try:
            if not self.tdb or not self.tdb.connected:
                await self.initialize()
            
            doc = {
                "@type": "ActionType",
                "@id": f"ActionType/{data['name']}",
                "name": data['name'],
                "displayName": data['displayName'],
                "description": data.get('description', ''),
                "targetTypes": [f"ObjectType/{t}" for t in data['targetTypes']],
                "operations": data['operations'],
                "sideEffects": data.get('sideEffects'),
                "permissions": data.get('permissions')
            }
            
            result = await self.tdb.client.post(
                f"{self.tdb.endpoint}/api/document/admin/{self.db_name}?author=OMS&message=Create ActionType",
                json=[doc],
                auth=("admin", "root")
            )
            
            if result.status_code in [200, 201]:
                logger.info(f"Created ActionType: {data['name']}")
                return doc
            else:
                raise Exception(f"Failed to create ActionType: {result.text}")
                
        except Exception as e:
            logger.error(f"Error creating action type: {e}")
            raise
    
    # ==================== Interfaces ====================
    
    async def list_interfaces(self, branch: str) -> List[Dict[str, Any]]:
        """List all interfaces"""
        try:
            if not self.tdb or not self.tdb.connected:
                await self.initialize()
            
            result = await self.tdb.client.get(
                f"{self.tdb.endpoint}/api/document/admin/{self.db_name}?type=Interface",
                auth=("admin", "root")
            )
            
            if result.status_code == 200:
                text = result.text.strip()
                if not text:
                    return []
                
                interfaces = []
                for line in text.split('\n'):
                    if line.strip():
                        try:
                            interfaces.append(json.loads(line))
                        except:
                            pass
                return interfaces
            return []
            
        except Exception as e:
            logger.error(f"Error listing interfaces: {e}")
            return []
    
    async def create_interface(self, branch: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new interface"""
        try:
            if not self.tdb or not self.tdb.connected:
                await self.initialize()
            
            doc = {
                "@type": "Interface",
                "@id": f"Interface/{data['name']}",
                "name": data['name'],
                "displayName": data['displayName'],
                "description": data.get('description', ''),
                "properties": [f"Property/{p}" for p in data.get('properties', [])],
                "sharedProperties": [f"SharedProperty/{p}" for p in data.get('sharedProperties', [])],
                "actions": [f"ActionType/{a}" for a in data.get('actions', [])]
            }
            
            result = await self.tdb.client.post(
                f"{self.tdb.endpoint}/api/document/admin/{self.db_name}?author=OMS&message=Create Interface",
                json=[doc],
                auth=("admin", "root")
            )
            
            if result.status_code in [200, 201]:
                logger.info(f"Created Interface: {data['name']}")
                return doc
            else:
                raise Exception(f"Failed to create Interface: {result.text}")
                
        except Exception as e:
            logger.error(f"Error creating interface: {e}")
            raise
    
    # ==================== Semantic Types ====================
    
    async def list_semantic_types(self, branch: str) -> List[Dict[str, Any]]:
        """List all semantic types"""
        try:
            if not self.tdb or not self.tdb.connected:
                await self.initialize()
            
            result = await self.tdb.client.get(
                f"{self.tdb.endpoint}/api/document/admin/{self.db_name}?type=SemanticType",
                auth=("admin", "root")
            )
            
            if result.status_code == 200:
                text = result.text.strip()
                if not text:
                    return []
                
                types = []
                for line in text.split('\n'):
                    if line.strip():
                        try:
                            types.append(json.loads(line))
                        except:
                            pass
                return types
            return []
            
        except Exception as e:
            logger.error(f"Error listing semantic types: {e}")
            return []
    
    async def create_semantic_type(self, branch: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new semantic type"""
        try:
            if not self.tdb or not self.tdb.connected:
                await self.initialize()
            
            doc = {
                "@type": "SemanticType",
                "@id": f"SemanticType/{data['name']}",
                "name": data['name'],
                "displayName": data['displayName'],
                "description": data.get('description', ''),
                "baseType": data['baseType'],
                "constraints": data.get('constraints'),
                "validationRules": data.get('validationRules', []),
                "examples": data.get('examples', [])
            }
            
            result = await self.tdb.client.post(
                f"{self.tdb.endpoint}/api/document/admin/{self.db_name}?author=OMS&message=Create SemanticType",
                json=[doc],
                auth=("admin", "root")
            )
            
            if result.status_code in [200, 201]:
                logger.info(f"Created SemanticType: {data['name']}")
                return doc
            else:
                raise Exception(f"Failed to create SemanticType: {result.text}")
                
        except Exception as e:
            logger.error(f"Error creating semantic type: {e}")
            raise
    
    # ==================== Struct Types ====================
    
    async def list_struct_types(self, branch: str) -> List[Dict[str, Any]]:
        """List all struct types"""
        try:
            if not self.tdb or not self.tdb.connected:
                await self.initialize()
            
            result = await self.tdb.client.get(
                f"{self.tdb.endpoint}/api/document/admin/{self.db_name}?type=StructType",
                auth=("admin", "root")
            )
            
            if result.status_code == 200:
                text = result.text.strip()
                if not text:
                    return []
                
                types = []
                for line in text.split('\n'):
                    if line.strip():
                        try:
                            types.append(json.loads(line))
                        except:
                            pass
                return types
            return []
            
        except Exception as e:
            logger.error(f"Error listing struct types: {e}")
            return []
    
    async def create_struct_type(self, branch: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new struct type"""
        try:
            if not self.tdb or not self.tdb.connected:
                await self.initialize()
            
            # First create the struct type
            doc = {
                "@type": "StructType",
                "@id": f"StructType/{data['name']}",
                "name": data['name'],
                "displayName": data['displayName'],
                "description": data.get('description', ''),
                "fields": []  # Will be populated with field IDs
            }
            
            # Create struct fields
            field_docs = []
            field_ids = []
            for idx, field in enumerate(data['fields']):
                field_id = f"StructField/{data['name']}_{field['name']}"
                field_doc = {
                    "@type": "StructField",
                    "@id": field_id,
                    "name": field['name'],
                    "displayName": field['displayName'],
                    "fieldType": field['fieldType'],
                    "required": field.get('required', False),
                    "structType": f"StructType/{data['name']}"
                }
                field_docs.append(field_doc)
                field_ids.append(field_id)
            
            doc['fields'] = field_ids
            
            # Insert all documents
            all_docs = [doc] + field_docs
            
            result = await self.tdb.client.post(
                f"{self.tdb.endpoint}/api/document/admin/{self.db_name}?author=OMS&message=Create StructType",
                json=all_docs,
                auth=("admin", "root")
            )
            
            if result.status_code in [200, 201]:
                logger.info(f"Created StructType: {data['name']} with {len(field_docs)} fields")
                return doc
            else:
                raise Exception(f"Failed to create StructType: {result.text}")
                
        except Exception as e:
            logger.error(f"Error creating struct type: {e}")
            raise
