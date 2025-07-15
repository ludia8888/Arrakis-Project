"""
Merge hint metadata definition

Metadata model for specifying merge strategy in schema
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class MergeStrategy(str, Enum):
    """Merge strategy type"""

    LCS_REORDERABLE = "lcs-reorderable"  # List where order matters
    UNORDERED_SET = "unordered-set"  # Set where order doesn't matter
    KEYED_MAP = "keyed-map"  # Map identified by key
    ATOMIC = "atomic"  # Process as atomic unit
    CUSTOM = "custom"  # Custom merge logic


class ConflictResolution(str, Enum):
    """Conflict resolution strategy"""

    MANUAL = "manual"  # Manual resolution required
    PREFER_SOURCE = "prefer-source"  # Prefer source
    PREFER_TARGET = "prefer-target"  # Prefer target
    MERGE_BOTH = "merge-both"  # Attempt to merge both
    FAIL_FAST = "fail-fast"  # Fail immediately


class MergeHint(BaseModel):
    """Merge hint metadata"""

    strategy: MergeStrategy = Field(
        default=MergeStrategy.KEYED_MAP, description="Merge strategy"
    )

    identity_key: Optional[str] = Field(
        default=None,
        description="Key identifying list/map items (example: 'name', 'id')",
    )

    order_field: Optional[str] = Field(
        default=None,
        description="Field name indicating order (example: 'order', 'sortOrder')",
    )

    conflict_resolution: ConflictResolution = Field(
        default=ConflictResolution.MANUAL, description="Conflict resolution strategy"
    )

    preserve_order: bool = Field(
        default=False, description="Whether to preserve order information"
    )

    semantic_groups: Optional[List[List[str]]] = Field(
        default=None, description="Field groups that must be processed together"
    )

    validation_rules: Optional[List[str]] = Field(
        default=None, description="Post-merge validation rules (expressions)"
    )

    custom_merger: Optional[str] = Field(
        default=None, description="Custom merge function name"
    )


class PropertyMergeHint(MergeHint):
    """Hints for Property array merging"""

    # Property-specific settings
    merge_property_groups: bool = Field(
        default=True, description="Merge related properties as a group"
    )

    handle_type_changes: bool = Field(
        default=True, description="Automatically handle type changes"
    )


class FieldMergeHint(BaseModel):
    """Merge hints for individual fields"""

    field_name: str = Field(..., description="Field name")

    merge_hint: MergeHint = Field(..., description="Merge hint for the field")


class SchemaMergeMetadata(BaseModel):
    """
    Schema-wide merge metadata

    Metadata added to ObjectType or other schema definitions
    """

    # Default merge strategy
    default_strategy: MergeStrategy = Field(
        default=MergeStrategy.KEYED_MAP, description="Default merge strategy"
    )

    # Per-field merge hints
    field_hints: Dict[str, MergeHint] = Field(
        default_factory=dict, description="Per-field merge hints"
    )

    # Fields requiring special handling
    properties_hint: Optional[PropertyMergeHint] = Field(
        default=None, description="Properties array merge hints"
    )

    # Semantic field groups
    semantic_field_groups: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Semantically related field group definitions"
    )

    # State transition rules (integration with existing models)
    enforce_state_transitions: bool = Field(
        default=True, description="Whether to enforce state transition rules"
    )

    # Merge validation rules
    post_merge_validations: Optional[List[str]] = Field(
        default=None, description="Validation rules to execute after merge"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "default_strategy": "keyed-map",
                "field_hints": {
                    "properties": {
                        "strategy": "lcs-reorderable",
                        "identity_key": "name",
                        "preserve_order": True,
                        "conflict_resolution": "manual",
                    },
                    "interfaces": {"strategy": "unordered-set", "identity_key": "name"},
                },
                "properties_hint": {
                    "merge_property_groups": True,
                    "handle_type_changes": True,
                },
                "semantic_field_groups": [
                    {
                        "name": "tax_info",
                        "fields": ["isTaxable", "taxRate", "taxExemptionReason"],
                        "merge_as_unit": True,
                    }
                ],
            }
        }


def get_merge_hint_for_field(
    schema_metadata: Optional[SchemaMergeMetadata], field_name: str
) -> Optional[MergeHint]:
    """Get merge hint for a specific field"""
    if not schema_metadata:
        return None

    # Check field-specific hints
    if field_name in schema_metadata.field_hints:
        return schema_metadata.field_hints[field_name]

    # Special handling for properties field
    if field_name == "properties" and schema_metadata.properties_hint:
        return schema_metadata.properties_hint

    return None


def create_default_merge_hints() -> SchemaMergeMetadata:
    """Create default merge hints"""
    return SchemaMergeMetadata(
        default_strategy=MergeStrategy.KEYED_MAP,
        field_hints={
            "properties": MergeHint(
                strategy=MergeStrategy.LCS_REORDERABLE,
                identity_key="name",
                preserve_order=True,
                conflict_resolution=ConflictResolution.MANUAL,
            ),
            "parentTypes": MergeHint(
                strategy=MergeStrategy.UNORDERED_SET,
                conflict_resolution=ConflictResolution.MERGE_BOTH,
            ),
            "interfaces": MergeHint(
                strategy=MergeStrategy.UNORDERED_SET,
                conflict_resolution=ConflictResolution.MERGE_BOTH,
            ),
            "fieldGroups": MergeHint(
                strategy=MergeStrategy.KEYED_MAP,
                identity_key="name",
                conflict_resolution=ConflictResolution.MANUAL,
            ),
        },
        enforce_state_transitions=True,
    )
