"""Property service protocol"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from models.domain import Property, PropertyCreate, PropertyUpdate


class PropertyServiceProtocol(ABC):
 """Protocol for property management service"""

 @abstractmethod
 async def create_property(
 self,
 branch: str,
 property_data: PropertyCreate,
 created_by: str
 ) -> Property:
 """Create a new property"""
 pass

 @abstractmethod
 async def get_property(
 self,
 branch: str,
 property_id: str
 ) -> Optional[Property]:
 """Get a property by ID"""
 pass

 @abstractmethod
 async def list_properties(
 self,
 branch: str,
 object_type: Optional[str] = None,
 skip: int = 0,
 limit: int = 100
 ) -> List[Property]:
 """List properties with optional filtering"""
 pass

 @abstractmethod
 async def update_property(
 self,
 branch: str,
 property_id: str,
 property_data: PropertyUpdate,
 updated_by: str
 ) -> Property:
 """Update a property"""
 pass

 @abstractmethod
 async def delete_property(
 self,
 branch: str,
 property_id: str,
 deleted_by: str
 ) -> bool:
 """Delete a property"""
 pass

 @abstractmethod
 async def validate_property(
 self,
 property_data: Dict[str, Any]
 ) -> Dict[str, Any]:
 """Validate a property definition"""
 pass

 @abstractmethod
 async def get_properties_by_object_type(
 self,
 branch: str,
 object_type_id: str
 ) -> List[Property]:
 """Get all properties for a specific object type"""
 pass
