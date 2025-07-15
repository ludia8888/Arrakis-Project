"""
Struct Type Definitions for OMS

Implements FR-ST-STRUCT requirement from Ontology_Requirements_Document.md
Provides complex multi-field property structures with validation.

IMPORTANT: Per Foundry constraints, nested structs are NOT supported.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from models.data_types import DataType
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StructFieldDefinition(BaseModel):
 """Definition of a single field within a struct type"""

 name: str = Field(..., description = "Field name within the struct")
 display_name: str = Field(..., description = "Human-readable field name")
 description: Optional[str] = Field(None, description = "Field description")
 data_type_id: str = Field(..., description = "ID of the data type for this field")
 semantic_type_id: Optional[str] = Field(None, description = "Optional semantic type")
 is_required: bool = Field(False, description = "Whether this field is required")
 default_value: Optional[Any] = Field(
 None, description = "Default value if not provided"
 )
 validation_rules: Optional[Dict[str, Any]] = Field(
 None, description = "Additional validation"
 )

 @field_validator("name")
 @classmethod
 def validate_field_name(cls, v: str) -> str:
 """Ensure field name follows naming conventions"""
 if not v:
 raise ValueError("Field name cannot be empty")
 if not (v[0].isalpha() or v[0] == "_"):
 raise ValueError("Field name must start with a letter or underscore")
 if not all(c.isalnum() or c == "_" for c in v):
 raise ValueError(
 "Field name can only contain letters, numbers, and underscores"
 )
 return v


class StructType(BaseModel):
 """
 Struct Type definition - complex multi-field property structures
 Implements requirement FR-ST-STRUCT

 IMPORTANT: Nested structs are NOT supported per Foundry constraints.
 """

 id: str = Field(..., description = "Unique identifier for the struct type")
 name: str = Field(..., description = "Human-readable name")
 description: Optional[str] = Field(None, description = "Detailed description")

 # Field definitions
 fields: List[StructFieldDefinition] = Field(
 ..., description = "List of field definitions in this struct", min_length = 1
 )

 # Display settings
 display_template: Optional[str] = Field(
 None,
 description = "Template for displaying struct values (e.g., '{firstName} {lastName}')",
 )

 # Metadata
 tags: List[str] = Field(default_factory = list,
     description = "Tags for categorization")

 # Audit fields
 created_at: datetime = Field(default_factory = datetime.utcnow)
 created_by: str
 modified_at: Optional[datetime] = None
 modified_by: Optional[str] = None

 # Status
 is_active: bool = Field(True, description = "Whether this struct type is active")
 is_system: bool = Field(False, description = "Whether this is a system-defined type")

 # Computed fields
 field_count: int = Field(0, description = "Number of fields in the struct")
 required_fields: List[str] = Field(
 default_factory = list, description = "List of required field names"
 )

 @model_validator(mode = "after")
 def validate_and_compute(self) -> "StructType":
 """Validate struct and compute derived fields"""
 # Check for duplicate field names
 field_names = [f.name for f in self.fields]
 if len(field_names) != len(set(field_names)):
 raise ValueError("Duplicate field names are not allowed in a struct")

 # Compute field count
 self.field_count = len(self.fields)

 # Compute required fields
 self.required_fields = [f.name for f in self.fields if f.is_required]

 # IMPORTANT: Validate no nested structs
 for field in self.fields:
 if field.data_type_id.startswith("struct:"):
 raise ValueError(
 f"Nested structs are not supported. Field '{field.name}' "
 f"references struct type '{field.data_type_id}'. "
 "Please flatten the structure or use separate properties."
 )

 return self

 def validate_value(self, value: Dict[str, Any]) -> tuple[bool, List[str]]:
 """
 Validate a value against this struct type
 Returns (is_valid, list_of_errors)
 """
 errors = []

 if not isinstance(value, dict):
 return False, ["Value must be a dictionary/object"]

 # Check required fields
 for required_field in self.required_fields:
 if required_field not in value:
 errors.append(f"Required field '{required_field}' is missing")

 # Validate each field
 for field in self.fields:
 if field.name in value:
 field_value = value[field.name]
 # Real implementation: Validate against data_type_id and semantic_type_id
 try:
 from models.data_types import data_type_registry
 from models.semantic_types import semantic_type_registry

 # Validate against data type
 data_type = data_type_registry.get(field.data_type_id)
 if data_type:
 is_valid, type_errors = data_type.validate_value(field_value)
 if not is_valid:
 errors.extend(
 [
 f"Field '{field.name}': {error}"
 for error in type_errors
 ]
 )
 else:
 errors.append(
 f"Field '{field.name}': Unknown data type '{field.data_type_id}'"
 )

 # Validate against semantic type if specified
 if field.semantic_type_id:
 semantic_type = semantic_type_registry.get(
 field.semantic_type_id
 )
 if semantic_type:
 is_valid, semantic_errors = semantic_type.validate(
 field_value
 )
 if not is_valid:
 errors.extend(
 [
 f"Field '{field.name}': {error}"
 for error in semantic_errors
 ]
 )
 else:
 errors.append(
 f"Field '{field.name}': Unknown semantic type '{field.semantic_type_id}'"
 )

 # Apply custom validation rules if specified
 if field.validation_rules:
 validation_errors = self._apply_field_validation_rules(
 field, field_value
 )
 if validation_errors:
 errors.extend(
 [
 f"Field '{field.name}': {error}"
 for error in validation_errors
 ]
 )

 except ImportError as e:
 # Fallback to basic validation if registries are not available
 errors.append(
 f"Field '{field.name}': Registry validation unavailable - {str(e)}"
 )
 except Exception as e:
 # Continue validation despite individual field validation errors
 errors.append(f"Field '{field.name}': Validation error - {str(e)}")

 # Check for unexpected fields
 expected_fields = {f.name for f in self.fields}
 provided_fields = set(value.keys())
 unexpected = provided_fields - expected_fields
 if unexpected:
 errors.append(f"Unexpected fields: {', '.join(unexpected)}")

 return len(errors) == 0, errors

 def _apply_field_validation_rules(
 self, field: StructFieldDefinition, value: Any
 ) -> List[str]:
 """Apply custom validation rules to a field value"""
 errors = []

 if not field.validation_rules:
 return errors

 # Apply common validation rules
 for rule_name, rule_value in field.validation_rules.items():
 try:
 if rule_name == "min_length" and isinstance(value, str):
 if len(value) < rule_value:
 errors.append(
 f"Value must be at least {rule_value} characters long"
 )

 elif rule_name == "max_length" and isinstance(value, str):
 if len(value) > rule_value:
 errors.append(
 f"Value must be no more than {rule_value} characters long"
 )

 elif rule_name == "pattern" and isinstance(value, str):
 import re

 if not re.match(rule_value, value):
 errors.append("Value does not match required pattern")

 elif rule_name == "min_value" and isinstance(value, (int, float)):
 if value < rule_value:
 errors.append(f"Value must be at least {rule_value}")

 elif rule_name == "max_value" and isinstance(value, (int, float)):
 if value > rule_value:
 errors.append(f"Value must be no more than {rule_value}")

 elif rule_name == "allowed_values":
 if value not in rule_value:
 errors.append(
 f"Value must be one of: {', '.join(map(str, rule_value))}"
 )

 elif rule_name == "forbidden_values":
 if value in rule_value:
 errors.append(
 f"Value cannot be one of: {', '.join(map(str, rule_value))}"
 )

 except Exception as e:
 errors.append(f"Validation rule '{rule_name}' failed: {str(e)}")

 return errors

 def format_display(self, value: Dict[str, Any]) -> str:
 """Format struct value for display using the display_template"""
 if self.display_template:
 try:
 # Simple template replacement
 result = self.display_template
 for field_name, field_value in value.items():
 result = result.replace(f"{{{field_name}}}", str(field_value))
 return result
 except AttributeError as e:
 # Value is not a dict or template is invalid
 import logging

 logger = logging.getLogger(__name__)
 logger.warning(
 f"Struct display template '{self.display_template}' failed - invalid value type {type(value)}: {e}"
 )
 return str(value)
 except Exception as e:
 # Log unexpected struct formatting errors
 import logging

 logger = logging.getLogger(__name__)
 logger.error(
 f"Unexpected struct formatting error for template '{self.display_template}' and value {value}: {e}"
 )
 return str(value)
 return str(value)

 def get_field(self, field_name: str) -> Optional[StructFieldDefinition]:
 """Get a specific field definition by name"""
 for field in self.fields:
 if field.name == field_name:
 return field
 return None

 def to_json_schema(self) -> Dict[str, Any]:
 """Convert struct type to JSON Schema format"""
 properties = {}
 required = []

 for field in self.fields:
 # Basic property definition
 properties[field.name] = {
 "type": self._map_data_type_to_json_type(field.data_type_id),
 "description": field.description or field.display_name,
 }

 if field.default_value is not None:
 properties[field.name]["default"] = field.default_value

 if field.is_required:
 required.append(field.name)

 return {
 "type": "object",
 "title": self.name,
 "description": self.description,
 "properties": properties,
 "required": required,
 "additionalProperties": False,
 }

 def _map_data_type_to_json_type(self, data_type_id: str) -> str:
 """Map OMS data type to JSON Schema type"""
 # This would integrate with DataTypeRegistry
 type_mapping = {
 "string": "string",
 "integer": "integer",
 "decimal": "number",
 "boolean": "boolean",
 "date": "string",
 "datetime": "string",
 "array": "array",
 "object": "object",
 }
 return type_mapping.get(data_type_id, "string")

 class Config:
 json_encoders = {datetime: lambda v: v.isoformat()}


# Predefined Struct Types
PREDEFINED_STRUCT_TYPES = {
 "address": StructType(
 id = "address",
 name = "Address",
 description = "Standard postal address structure",
 fields = [
 StructFieldDefinition(
 name = "street1",
 display_name = "Street Address 1",
 data_type_id = "string",
 is_required = True,
 ),
 StructFieldDefinition(
 name = "street2",
 display_name = "Street Address 2",
 data_type_id = "string",
 is_required = False,
 ),
 StructFieldDefinition(
 name = "city",
 display_name = "City",
 data_type_id = "string",
 is_required = True,
 ),
 StructFieldDefinition(
 name = "state",
 display_name = "State/Province",
 data_type_id = "string",
 is_required = True,
 ),
 StructFieldDefinition(
 name = "postal_code",
 display_name = "Postal Code",
 data_type_id = "string",
 semantic_type_id = "postal_code_us",
 is_required = True,
 ),
 StructFieldDefinition(
 name = "country",
 display_name = "Country",
 data_type_id = "string",
 semantic_type_id = "iso_country_code",
 is_required = True,
 default_value = "US",
 ),
 ],
 display_template = "{street1}, {city}, {state} {postal_code}",
 created_by = "system",
 is_system = True,
 ),
 "person_name": StructType(
 id = "person_name",
 name = "Person Name",
 description = "Standard person name structure",
 fields = [
 StructFieldDefinition(
 name = "first_name",
 display_name = "First Name",
 data_type_id = "string",
 is_required = True,
 ),
 StructFieldDefinition(
 name = "middle_name",
 display_name = "Middle Name",
 data_type_id = "string",
 is_required = False,
 ),
 StructFieldDefinition(
 name = "last_name",
 display_name = "Last Name",
 data_type_id = "string",
 is_required = True,
 ),
 StructFieldDefinition(
 name = "suffix",
 display_name = "Suffix",
 data_type_id = "string",
 is_required = False,
 ),
 ],
 display_template = "{first_name} {last_name}",
 created_by = "system",
 is_system = True,
 ),
 "time_range": StructType(
 id = "time_range",
 name = "Time Range",
 description = "Start and end time range",
 fields = [
 StructFieldDefinition(
 name = "start_time",
 display_name = "Start Time",
 data_type_id = "datetime",
 is_required = True,
 ),
 StructFieldDefinition(
 name = "end_time",
 display_name = "End Time",
 data_type_id = "datetime",
 is_required = True,
 ),
 StructFieldDefinition(
 name = "timezone",
 display_name = "Time Zone",
 data_type_id = "string",
 is_required = False,
 default_value = "UTC",
 ),
 ],
 display_template = "{start_time} - {end_time}",
 created_by = "system",
 is_system = True,
 ),
}


class StructTypeRegistry:
 """Registry for managing struct types"""

 def __init__(self):
 self._types: Dict[str, StructType] = {}
 self._load_predefined_types()

 def _load_predefined_types(self):
 """Load predefined struct types"""
 for type_id, struct_type in PREDEFINED_STRUCT_TYPES.items():
 self._types[type_id] = struct_type

 def register(self, struct_type: StructType) -> None:
 """Register a new struct type"""
 if struct_type.id in self._types and self._types[struct_type.id].is_system:
 raise ValueError(f"Cannot override system struct type: {struct_type.id}")

 # Validate no nested structs
 for field in struct_type.fields:
 if field.data_type_id in self._types or field.data_type_id.startswith(
 "struct:"
 ):
 raise ValueError(
 f"Nested structs are not supported. Field '{field.name}' "
 f"in struct '{struct_type.id}' references another struct type. "
 "Please flatten the structure."
 )

 self._types[struct_type.id] = struct_type

 def get(self, type_id: str) -> Optional[StructType]:
 """Get a struct type by ID"""
 return self._types.get(type_id)

 def list_all(self) -> List[StructType]:
 """List all registered struct types"""
 return list(self._types.values())

 def validate_value(self, type_id: str, value: Any) -> tuple[bool, List[str]]:
 """Validate a value against a struct type"""
 struct_type = self.get(type_id)
 if not struct_type:
 return False, [f"Unknown struct type: {type_id}"]
 return struct_type.validate_value(value)

 def exists(self, type_id: str) -> bool:
 """Check if a struct type exists"""
 return type_id in self._types


# Global registry instance
struct_type_registry = StructTypeRegistry()
