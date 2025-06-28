"""
Validation Rules Package

Provides comprehensive breaking change detection rules for OMS schema validation.
Supports Foundry-OMS semantic validation categories:
- Validation Rule (HARD/SOFT UI-scheduling)
- Ontology Rule (object/link triggers)  
- Foundry Rule (dataset filtering/alerting)
- WOQL-based Semantic Validation
"""

# Base classes and interfaces
from .base import BaseRule, BreakingChangeRule, CompositeRule

# Data analysis rules
from .data_impact_analyzer import DataImpactAnalyzer
from .data_type import DataTypeChangeRule, UniqueConstraintAdditionRule, IndexRemovalRule

# Schema structure rules  
from .naming_convention_rule import NamingConventionRule
from .primary_key_change import PrimaryKeyChangeRule  # Advanced version with Foundry integration
from .required_field import RequiredFieldRemovalRule, RequiredFieldAdditionRule
from .shared_property import SharedPropertyChangeRule

# TerminusDB native integration rules
from .terminus_native_schema_rule import (
    TerminusNativeSchemaRule,
    TerminusNativeCircularDependencyRule,
    TerminusNativeMergeConflictRule
)
from .terminus_redundant_check import TerminusRedundantCheckRule, CardinalityValidationOptimizer

# Type compatibility rules
from .type_incompatibility import TypeIncompatibilityRule

# Foundry alerting rules
from .foundry_alerting_rule import FoundryDatasetAlertingRule, AlertConfig, FoundryAlert

# P1 Phase - Complete Foundry Dataset Rules Coverage
from .enum_value_constraint_rule import (
    EnumValueConstraintRule, EnumSchemaChangeRule, EnumConstraint,
    create_enum_constraint_rule, create_foundry_status_enum_rule, create_foundry_priority_enum_rule
)
from .array_element_rule import (
    ArrayElementConstraintRule, ArrayConstraint, ArrayConstraintType,
    create_unique_array_rule, create_enum_array_rule, create_foundry_tags_rule
)
from .foreign_ref_integrity_rule import (
    ForeignReferenceIntegrityRule, ForeignReference, ReferenceType, IntegrityAction,
    create_foreign_key_rule, create_cross_dataset_rule, create_foundry_entity_references
)

# Export all production-ready rule classes for plugin scanning
__all__ = [
    # Base classes
    "BaseRule",
    "BreakingChangeRule", 
    "CompositeRule",
    
    # Data analysis rules (Foundry Dataset Rules)
    "DataImpactAnalyzer",
    "DataTypeChangeRule",
    "UniqueConstraintAdditionRule", 
    "IndexRemovalRule",
    
    # Schema structure rules (Validation Rules - HARD/SOFT)
    "NamingConventionRule",
    "PrimaryKeyChangeRule",
    "RequiredFieldRemovalRule",
    "RequiredFieldAdditionRule", 
    "SharedPropertyChangeRule",
    
    # TerminusDB native rules (WOQL-based Semantic Validation)
    "TerminusNativeSchemaRule",
    "TerminusNativeCircularDependencyRule",
    "TerminusNativeMergeConflictRule",
    "TerminusRedundantCheckRule", 
    "CardinalityValidationOptimizer",
    
    # Type compatibility rules (Ontology Rules)
    "TypeIncompatibilityRule",
    
    # Foundry alerting rules (Enterprise Alerting)
    "FoundryDatasetAlertingRule",
    "AlertConfig",
    "FoundryAlert",
    
    # P1 Phase - Complete Foundry Dataset Rules Coverage
    "EnumValueConstraintRule",
    "EnumSchemaChangeRule", 
    "EnumConstraint",
    "ArrayElementConstraintRule",
    "ArrayConstraint",
    "ArrayConstraintType",
    "ForeignReferenceIntegrityRule",
    "ForeignReference",
    "ReferenceType",
    "IntegrityAction",
    
    # Factory functions for easy rule creation
    "create_enum_constraint_rule",
    "create_foundry_status_enum_rule",
    "create_foundry_priority_enum_rule",
    "create_unique_array_rule",
    "create_enum_array_rule", 
    "create_foundry_tags_rule",
    "create_foreign_key_rule",
    "create_cross_dataset_rule",
    "create_foundry_entity_references",
]

# Rule categories for automatic discovery
RULE_CATEGORIES = {
    "validation": [
        "RequiredFieldRemovalRule",
        "RequiredFieldAdditionRule", 
        "NamingConventionRule",
        "PrimaryKeyChangeRule"
    ],
    "ontology": [
        "TypeIncompatibilityRule",
        "SharedPropertyChangeRule",
        "DataTypeChangeRule"
    ],
    "foundry": [
        "DataImpactAnalyzer", 
        "UniqueConstraintAdditionRule",
        "IndexRemovalRule",
        "FoundryDatasetAlertingRule",
        # P1 Phase additions
        "EnumValueConstraintRule",
        "ArrayElementConstraintRule", 
        "ForeignReferenceIntegrityRule"
    ],
    "woql_semantic": [
        "TerminusNativeSchemaRule",
        "TerminusNativeCircularDependencyRule", 
        "TerminusNativeMergeConflictRule",
        "TerminusRedundantCheckRule",
        "CardinalityValidationOptimizer"
    ]
}

# Priority levels for rule execution order
RULE_PRIORITIES = {
    # High priority - run first (pre-filters)
    "TerminusNativeSchemaRule": 10,
    "TerminusRedundantCheckRule": 15,
    
    # Medium priority - core validation
    "RequiredFieldRemovalRule": 50,
    "PrimaryKeyChangeRule": 55,
    "TypeIncompatibilityRule": 60,
    
    # Lower priority - analysis and optimization
    "DataImpactAnalyzer": 80,
    "CardinalityValidationOptimizer": 90,
    
    # Alerting priority - run after analysis
    "FoundryDatasetAlertingRule": 25,
    
    # P1 Phase priorities
    "EnumValueConstraintRule": 40,  # Medium priority - after basic validation
    "EnumSchemaChangeRule": 35,     # Run before data validation
    "ArrayElementConstraintRule": 45,  # Run after field validation
    "ForeignReferenceIntegrityRule": 30,  # High priority - after schema validation
}
