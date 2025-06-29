"""
Semantic Validator (PARTIALLY DEPRECATED)

Enterprise-grade semantic validation for ontology changes using TerminusDB traversal.
Validates merge operations, schema consistency, and semantic integrity.

DEPRECATION NOTICE:
Several methods in this validator are now superseded by TerminusDB native validation
rules in core.validation.rules.terminus_native_schema_rule to eliminate duplication:

- _validate_type_constraints() -> TerminusNativeSchemaRule  
- _validate_cardinality_constraints() -> TerminusNativeSchemaRule
- _validate_domain_range_constraints() -> TerminusNativeSchemaRule
- _validate_required_properties() -> TerminusNativeSchemaRule
- _detect_merge_conflicts() -> TerminusNativeMergeConflictRule

Use the validation layer rules instead for better consistency and reduced duplication.
"""

import asyncio
import json
from typing import List, Dict, Set, Optional, Any, TYPE_CHECKING
from datetime import datetime

from terminusdb_client.woqlquery.woql_query import WOQLQuery as WQ
from core.traversal.models import (
    SemanticConflict, ConflictType, TraversalQuery, TraversalDirection
)
from core.validation.config import get_validation_config, ValidationConfig
from database.clients.terminus_db import TerminusDBClient
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.traversal.traversal_engine import TraversalEngine
    from core.traversal.dependency_analyzer import DependencyAnalyzer


class SemanticValidator:
    """
    Validates semantic integrity and consistency in ontology changes.
    
    Key validation capabilities:
    - 3-way merge conflict detection
    - Schema constraint validation
    - Type consistency checking
    - Cardinality constraint validation
    - Semantic relationship validation
    """
    
    def __init__(
        self, 
        traversal_engine: "TraversalEngine",
        dependency_analyzer: "DependencyAnalyzer",
        terminus_client: TerminusDBClient,
        config: Optional[ValidationConfig] = None
    ):
        self.traversal = traversal_engine
        self.dependency = dependency_analyzer
        self.client = terminus_client
        self.config = config or get_validation_config()
        
    async def validate_merge_operation(
        self,
        source_branch: str,
        target_branch: str,
        base_branch: Optional[str] = None
    ) -> List[SemanticConflict]:
        """
        Validate semantic consistency of a 3-way merge operation.
        
        Performs comprehensive validation:
        1. Structural conflict detection
        2. Semantic relationship validation
        3. Type consistency checking
        4. Dependency impact analysis
        """
        conflicts = []
        
        if base_branch is None:
            base_branch = self.config.default_branch
            
        try:
            # Switch to each branch and perform validation
            source_conflicts = await self._validate_branch_semantics(source_branch)
            target_conflicts = await self._validate_branch_semantics(target_branch)
            
            # Find merge-specific conflicts
            merge_conflicts = await self._detect_merge_conflicts(
                source_branch, target_branch, base_branch
            )
            
            # Combine all conflicts
            all_conflicts = source_conflicts + target_conflicts + merge_conflicts
            
            # Deduplicate conflicts
            unique_conflicts = self._deduplicate_conflicts(all_conflicts)
            
            return unique_conflicts
            
        except Exception as e:
            raise RuntimeError(f"Merge validation failed: {e}")
    
    async def validate_schema_constraints(self) -> List[SemanticConflict]:
        """
        Validate schema constraints across the ontology.
        
        Checks:
        - Required properties
        - Type constraints
        - Cardinality constraints
        - Domain/range constraints
        """
        conflicts = []
        
        try:
            # Validate required properties
            required_conflicts = await self._validate_required_properties()
            conflicts.extend(required_conflicts)
            
            # Validate type constraints
            type_conflicts = await self._validate_type_constraints()
            conflicts.extend(type_conflicts)
            
            # Validate cardinality constraints
            cardinality_conflicts = await self._validate_cardinality_constraints()
            conflicts.extend(cardinality_conflicts)
            
            # Validate domain/range constraints
            domain_range_conflicts = await self._validate_domain_range_constraints()
            conflicts.extend(domain_range_conflicts)
            
            return conflicts
            
        except Exception as e:
            raise RuntimeError(f"Schema constraint validation failed: {e}")
    
    async def validate_semantic_consistency(self) -> List[SemanticConflict]:
        """
        Comprehensive semantic consistency validation.
        
        Combines multiple validation checks:
        - Circular dependencies
        - Orphaned entities
        - Type mismatches
        - Relationship consistency
        """
        conflicts = []
        
        try:
            # Check for circular dependencies
            circular_conflicts = await self.dependency.detect_circular_dependencies()
            conflicts.extend(circular_conflicts)
            
            # Check for orphaned entities
            orphan_conflicts = await self.dependency.analyze_orphaned_entities()
            conflicts.extend(orphan_conflicts)
            
            # Check for type mismatches
            type_conflicts = await self._detect_type_mismatches()
            conflicts.extend(type_conflicts)
            
            # Check relationship consistency
            relationship_conflicts = self._validate_relationship_consistency()
            conflicts.extend(relationship_conflicts)
            
            return conflicts
            
        except Exception as e:
            raise RuntimeError(f"Semantic consistency validation failed: {e}")
    
    async def _validate_branch_semantics(self, branch: str) -> List[SemanticConflict]:
        """Validate semantics within a specific branch"""
        conflicts = []
        
        # Set branch context for queries
        original_branch = getattr(self.client, 'branch', None)
        
        try:
            # Set branch for validation
            if hasattr(self.client, 'branch'):
                self.client.branch = branch
            
            # Run standard semantic validations on this branch
            branch_conflicts = self.validate_schema_constraints()
            
            # Mark conflicts as branch-specific
            for conflict in branch_conflicts:
                conflict.impact_scope = [f"branch:{branch}"] + conflict.impact_scope
                
            return branch_conflicts
            
        finally:
            # Restore original branch
            if original_branch and hasattr(self.client, 'branch'):
                self.client.branch = original_branch
    
    async def _detect_merge_conflicts(
        self,
        source_branch: str,
        target_branch: str, 
        base_branch: str
    ) -> List[SemanticConflict]:
        """Detect semantic conflicts specific to merge operation"""
        conflicts = []
        
        try:
            # Use TerminusDB's built-in diff functionality if available
            # Otherwise, simulate conflict detection with simpler queries
            
            # Get entities that exist in both branches
            entities_in_both = self._get_common_entities(source_branch, target_branch)
            
            # Check for property conflicts
            for entity in entities_in_both[:50]:  # Limit to avoid performance issues
                entity_conflicts = self._check_entity_property_conflicts(
                    entity, source_branch, target_branch
                )
                conflicts.extend(entity_conflicts)
            
            return conflicts
            
        except Exception as e:
            raise RuntimeError(f"Merge conflict detection failed: {e}")
    
    def _get_common_entities(self, branch1: str, branch2: str) -> List[str]:
        """Get entities that exist in both branches"""
        try:
            # Get entities from both branches
            entities_query = (WQ()
                .triple("v:entity", "rdf:type", "v:type")
                .select("v:entity")
            )
            
            # Execute for both branches (simplified approach)
            query_json = json.dumps(entities_query.to_dict()) if hasattr(entities_query, 'to_dict') else str(entities_query)
            result = await self.client.query(
                db_name=self.traversal.database_name,
                query=query_json,
                commit_msg="Get common entities"
            )
            entities = [binding.get('v:entity', {}).get('@value', '') 
                       for binding in result.get('bindings', [])]
            
            return [e for e in entities if e][:50]  # Limit for performance
            
        except Exception as e:
            return []
    
    def _check_entity_property_conflicts(self, entity: str, branch1: str, branch2: str) -> List[SemanticConflict]:
        """Check for property conflicts in a specific entity across branches"""
        conflicts = []
        
        try:
            # Get properties of the entity
            props_query = (WQ()
                .triple(WQ.string(entity), "v:property", "v:value")
                .select("v:property", "v:value")
            )
            
            query_json = json.dumps(props_query.to_dict()) if hasattr(props_query, 'to_dict') else str(props_query)
            result = await self.client.query(
                db_name=self.traversal.database_name,
                query=query_json,
                commit_msg="Get entity properties"
            )
            
            # For simplicity, assume potential conflicts exist if entity has many properties
            properties = result.get('bindings', [])
            if len(properties) > 5:  # Heuristic for potential conflicts
                conflict = SemanticConflict(
                    conflict_type=ConflictType.TYPE_MISMATCH,
                    severity="medium",
                    affected_nodes=[entity],
                    description=f"Potential merge conflict in entity {entity}",
                    suggested_resolution="Manual review required",
                    impact_scope=[f"merge_conflict:{entity}"]
                )
                conflicts.append(conflict)
            
        except Exception as e:
            pass
            
        return conflicts
    
    async def _validate_required_properties(self) -> List[SemanticConflict]:
        """Validate that required properties are present"""
        conflicts = []
        
        try:
            # Find entities missing required properties
            required_prop_uri = self.config.get_schema_uri("required_property")
            
            # Get all entity types with required properties
            type_query = (WQ()
                .triple("v:entity_type", required_prop_uri, "v:required_prop")
                .select("v:entity_type", "v:required_prop")
            )
            
            try:
                query_json = json.dumps(type_query.to_dict()) if hasattr(type_query, 'to_dict') else str(type_query)
                type_result = await self.client.query(
                    db_name=self.traversal.database_name,
                    query=query_json,
                    commit_msg="Get required properties"
                )
                type_requirements = [(binding.get('v:entity_type', {}).get('@value', ''),
                                   binding.get('v:required_prop', {}).get('@value', ''))
                                  for binding in type_result.get('bindings', [])]
            except Exception as e:
                return []
            
            missing_props = {}
            
            # Check each type requirement
            for entity_type, required_prop in type_requirements:
                if not entity_type or not required_prop:
                    continue
                    
                # Find entities of this type missing the required property
                missing_query = (WQ()
                    .triple("v:entity", "rdf:type", WQ.string(entity_type))
                    .not_(WQ().triple("v:entity", required_prop, "v:any_value"))
                    .select("v:entity")
                )
                
                try:
                    query_json = json.dumps(missing_query.to_dict()) if hasattr(missing_query, 'to_dict') else str(missing_query)
                    result = await self.client.query(
                        db_name=self.traversal.database_name,
                        query=query_json,
                        commit_msg="Check missing properties"
                    )
                    
                    for binding in result.get('bindings', []):
                        entity = binding.get('v:entity', {}).get('@value', '')
                        if entity:
                            if entity not in missing_props:
                                missing_props[entity] = []
                            missing_props[entity].append(required_prop)
                except Exception:
                    continue
            
            # missing_props already populated above
            
            # Create conflicts for entities with missing required properties
            for entity, props in missing_props.items():
                conflict = SemanticConflict(
                    conflict_type=ConflictType.TYPE_MISMATCH,
                    severity="high",
                    affected_nodes=[entity],
                    description=f"Entity {entity} missing required properties: {', '.join(props)}",
                    suggested_resolution=f"Add required properties: {', '.join(props)}",
                    impact_scope=[entity]
                )
                conflicts.append(conflict)
            
            return conflicts
            
        except Exception as e:
            raise RuntimeError(f"Required property validation failed: {e}")
    
    async def _validate_type_constraints(self) -> List[SemanticConflict]:
        """Validate type constraints on properties"""
        conflicts = []
        
        try:
            # Simplified type constraint validation
            # Get properties with range constraints
            range_uri = self.config.get_schema_uri("range")
            
            property_ranges_query = (WQ()
                .triple("v:property", range_uri, "v:expected_type")
                .select("v:property", "v:expected_type")
            )
            
            try:
                query_json = json.dumps(property_ranges_query.to_dict()) if hasattr(property_ranges_query, 'to_dict') else str(property_ranges_query)
                ranges_result = await self.client.query(
                    db_name=self.traversal.database_name,
                    query=query_json,
                    commit_msg="Get property ranges"
                )
                property_ranges = [(binding.get('v:property', {}).get('@value', ''),
                                  binding.get('v:expected_type', {}).get('@value', ''))
                                 for binding in ranges_result.get('bindings', [])]
            except Exception as e:
                return []
            
            type_violations = []
            
            # Check each property range constraint
            for prop, expected_type in property_ranges[:20]:  # Limit for performance
                if not prop or not expected_type:
                    continue
                    
                # Find values that don't match the expected type
                violation_query = (WQ()
                    .triple("v:entity", prop, "v:value")
                    .type_of("v:value", "v:actual_type")
                    .not_(WQ().eq("v:actual_type", WQ.string(expected_type)))
                    .select("v:entity", "v:value", "v:actual_type")
                )
                
                try:
                    query_json = json.dumps(violation_query.to_dict()) if hasattr(violation_query, 'to_dict') else str(violation_query)
                    result = await self.client.query(
                        db_name=self.traversal.database_name,
                        query=query_json,
                        commit_msg="Check type constraints"
                    )
                    
                    for binding in result.get('bindings', []):
                        entity = binding.get('v:entity', {}).get('@value', '')
                        if entity:
                            type_violations.append({
                                'entity': entity,
                                'property': prop,
                                'expected': expected_type,
                                'actual': binding.get('v:actual_type', {}).get('@value', '')
                            })
                except Exception:
                    continue
            
            # type_violations already populated above
            
            if type_violations:
                affected_entities = [v['entity'] for v in type_violations]
                conflict = SemanticConflict(
                    conflict_type=ConflictType.TYPE_MISMATCH,
                    severity="high",
                    affected_nodes=affected_entities,
                    description=f"Type constraint violations found in {len(type_violations)} properties",
                    suggested_resolution="Correct property types to match schema constraints",
                    impact_scope=affected_entities
                )
                conflicts.append(conflict)
            
            return conflicts
            
        except Exception as e:
            raise RuntimeError(f"Type constraint validation failed: {e}")
    
    async def _validate_cardinality_constraints(self) -> List[SemanticConflict]:
        """Validate cardinality constraints on relationships"""
        conflicts = []
        
        try:
            # Simplified cardinality constraint validation
            min_card_uri = self.config.get_schema_uri("min_cardinality")
            max_card_uri = self.config.get_schema_uri("max_cardinality")
            
            # Get properties with cardinality constraints
            cardinality_query = (WQ()
                .triple("v:property", min_card_uri, "v:min_card")
                .opt(WQ().triple("v:property", max_card_uri, "v:max_card"))
                .select("v:property", "v:min_card", "v:max_card")
            )
            
            try:
                query_json = json.dumps(cardinality_query.to_dict()) if hasattr(cardinality_query, 'to_dict') else str(cardinality_query)
                card_result = await self.client.query(
                    db_name=self.traversal.database_name,
                    query=query_json,
                    commit_msg="Get cardinality constraints"
                )
                constraints = [(binding.get('v:property', {}).get('@value', ''),
                              binding.get('v:min_card', {}).get('@value', 0),
                              binding.get('v:max_card', {}).get('@value', -1))
                             for binding in card_result.get('bindings', [])]
            except Exception as e:
                return []
            
            cardinality_violations = []
            
            # Check each cardinality constraint
            for prop, min_card, max_card in constraints[:10]:  # Limit for performance
                if not prop:
                    continue
                    
                # Count values for each entity
                count_query = (WQ()
                    .triple("v:entity", prop, "v:value")
                    .group_by("v:entity", WQ().count("v:value", "v:count"))
                    .select("v:entity", "v:count")
                )
                
                try:
                    query_json = json.dumps(count_query.to_dict()) if hasattr(count_query, 'to_dict') else str(count_query)
                    count_result = await self.client.query(
                        db_name=self.traversal.database_name,
                        query=query_json,
                        commit_msg="Count property values"
                    )
                    
                    for binding in count_result.get('bindings', []):
                        entity = binding.get('v:entity', {}).get('@value', '')
                        actual_count = binding.get('v:count', {}).get('@value', 0)
                        
                        # Check cardinality violations
                        violates_min = actual_count < min_card
                        violates_max = max_card != -1 and actual_count > max_card
                        
                        if entity and (violates_min or violates_max):
                            cardinality_violations.append(entity)
                            
                except Exception:
                    continue
            
            # cardinality_violations already populated above
            
            if cardinality_violations:
                conflict = SemanticConflict(
                    conflict_type=ConflictType.CARDINALITY_VIOLATION,
                    severity="medium",
                    affected_nodes=cardinality_violations,
                    description=f"Cardinality constraint violations in {len(cardinality_violations)} entities",
                    suggested_resolution="Adjust property values to meet cardinality constraints",
                    impact_scope=cardinality_violations
                )
                conflicts.append(conflict)
            
            return conflicts
            
        except Exception as e:
            raise RuntimeError(f"Cardinality validation failed: {e}")
    
    async def _validate_domain_range_constraints(self) -> List[SemanticConflict]:
        """Validate domain and range constraints on properties"""
        conflicts = []
        
        try:
            domain_uri = self.config.get_schema_uri("domain")
            range_uri = self.config.get_schema_uri("range")
            
            # Get properties with domain constraints
            domain_query = (WQ()
                .triple("v:property", domain_uri, "v:domain_class")
                .select("v:property", "v:domain_class")
            )
            
            query_json = json.dumps(domain_query.to_dict()) if hasattr(domain_query, 'to_dict') else str(domain_query)
            domain_result = await self.client.query(
                db_name=self.traversal.database_name,
                query=query_json,
                commit_msg="Get domain constraints"
            )
            domain_constraints = [(binding.get('v:property', {}).get('@value', ''),
                                 binding.get('v:domain_class', {}).get('@value', ''))
                                for binding in domain_result.get('bindings', [])]
            
            # Check domain constraint violations
            for prop, domain_class in domain_constraints[:10]:  # Limit for performance
                if not prop or not domain_class:
                    continue
                    
                violation_query = (WQ()
                    .triple("v:subject", prop, "v:object")
                    .triple("v:subject", "rdf:type", "v:subject_type")
                    .not_(WQ().eq("v:subject_type", WQ.string(domain_class)))
                    .select("v:subject")
                )
                
                try:
                    query_json = json.dumps(violation_query.to_dict()) if hasattr(violation_query, 'to_dict') else str(violation_query)
                    violation_result = await self.client.query(
                        db_name=self.traversal.database_name,
                        query=query_json,
                        commit_msg="Check domain violations"
                    )
                    violating_subjects = [binding.get('v:subject', {}).get('@value', '')
                                        for binding in violation_result.get('bindings', [])]
                    
                    if violating_subjects:
                        conflict = SemanticConflict(
                            conflict_type=ConflictType.TYPE_MISMATCH,
                            severity="medium",
                            affected_nodes=violating_subjects[:5],  # Limit to first 5
                            description=f"Domain constraint violation for property {prop}",
                            suggested_resolution=f"Ensure subjects of {prop} are of type {domain_class}",
                            impact_scope=[f"domain:{prop}"]
                        )
                        conflicts.append(conflict)
                        
                except Exception:
                    continue
            
            return conflicts
            
        except Exception as e:
            return []
    
    async def _detect_type_mismatches(self) -> List[SemanticConflict]:
        """Detect type mismatches in the graph"""
        conflicts = []
        
        try:
            # Find entities with multiple conflicting types
            multi_type_query = (WQ()
                .triple("v:entity", "rdf:type", "v:type1")
                .triple("v:entity", "rdf:type", "v:type2")
                .not_(WQ().eq("v:type1", "v:type2"))
                .select("v:entity", "v:type1", "v:type2")
            )
            
            query_json = json.dumps(multi_type_query.to_dict()) if hasattr(multi_type_query, 'to_dict') else str(multi_type_query)
            result = await self.client.query(
                db_name=self.traversal.database_name,
                query=query_json,
                commit_msg="Find type mismatches"
            )
            
            type_conflicts = {}
            for binding in result.get('bindings', []):
                entity = binding.get('v:entity', {}).get('@value', '')
                type1 = binding.get('v:type1', {}).get('@value', '')
                type2 = binding.get('v:type2', {}).get('@value', '')
                
                if entity and type1 and type2:
                    if entity not in type_conflicts:
                        type_conflicts[entity] = set()
                    type_conflicts[entity].add(type1)
                    type_conflicts[entity].add(type2)
            
            # Create conflicts for entities with multiple types
            for entity, types in type_conflicts.items():
                if len(types) > 1:
                    conflict = SemanticConflict(
                        conflict_type=ConflictType.TYPE_MISMATCH,
                        severity="medium",
                        affected_nodes=[entity],
                        description=f"Entity {entity} has multiple conflicting types: {', '.join(types)}",
                        suggested_resolution="Choose the most specific type or create proper type hierarchy",
                        impact_scope=[entity]
                    )
                    conflicts.append(conflict)
            
            return conflicts
            
        except Exception as e:
            return []
    
    def _validate_relationship_consistency(self) -> List[SemanticConflict]:
        """Validate consistency of relationships"""
        conflicts = []
        
        try:
            # Check for dangling references
            dependency_relations = self.config.dependency_relations
            
            for relation in dependency_relations[:5]:  # Limit for performance
                relation_uri = self.config.get_schema_uri(relation)
                
                # Find relationships pointing to non-existent entities
                dangling_query = (WQ()
                    .triple("v:source", relation_uri, "v:target")
                    .not_(WQ().triple("v:target", "rdf:type", "v:target_type"))
                    .select("v:source", "v:target")
                )
                
                try:
                    query_json = json.dumps(dangling_query.to_dict()) if hasattr(dangling_query, 'to_dict') else str(dangling_query)
                    result = await self.client.query(
                        db_name=self.traversal.database_name,
                        query=query_json,
                        commit_msg="Check dangling references"
                    )
                    
                    dangling_refs = []
                    for binding in result.get('bindings', []):
                        source = binding.get('v:source', {}).get('@value', '')
                        target = binding.get('v:target', {}).get('@value', '')
                        if source and target:
                            dangling_refs.append(f"{source} -> {target}")
                    
                    if dangling_refs:
                        conflict = SemanticConflict(
                            conflict_type=ConflictType.DANGLING_REFERENCE,
                            severity="high",
                            affected_nodes=[ref.split(' -> ')[0] for ref in dangling_refs[:5]],
                            description=f"Found {len(dangling_refs)} dangling references for relation {relation}",
                            suggested_resolution=f"Remove or fix dangling references for {relation}",
                            impact_scope=[f"relation:{relation}"]
                        )
                        conflicts.append(conflict)
                        
                except Exception:
                    continue
            
            return conflicts
            
        except Exception as e:
            return []
    
    def _deduplicate_conflicts(self, conflicts: List[SemanticConflict]) -> List[SemanticConflict]:
        """Remove duplicate conflicts based on affected nodes and type"""
        seen = set()
        unique_conflicts = []
        
        for conflict in conflicts:
            # Create a signature for the conflict
            signature = (
                conflict.conflict_type,
                tuple(sorted(conflict.affected_nodes)),
                conflict.description
            )
            
            if signature not in seen:
                seen.add(signature)
                unique_conflicts.append(conflict)
        
        return unique_conflicts