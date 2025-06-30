"""
Dependency Analyzer

Enterprise-grade dependency analysis using TerminusDB native traversal.
Provides impact analysis, circular dependency detection, and critical path identification.
"""

import asyncio
import json
import logging
from typing import List, Dict, Set, Optional, Tuple, TYPE_CHECKING
from datetime import datetime

from terminusdb_client.woqlquery import WOQLQuery as WQ
from core.traversal.models import (
    DependencyPath, SemanticConflict, ConflictType, GraphNode
)
from core.validation.config import get_validation_config, ValidationConfig
from database.clients.terminus_db import TerminusDBClient
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.traversal.traversal_engine import TraversalEngine


class DependencyAnalyzer:
    """
    Analyzes dependencies and relationships in the ontology graph.
    
    Key capabilities:
    - Impact analysis for schema changes
    - Circular dependency detection
    - Critical path identification  
    - MSA service dependency mapping
    """
    
    def __init__(self, traversal_engine: "TraversalEngine", terminus_client: TerminusDBClient, config: Optional[ValidationConfig] = None, database_name: str = "oms"):
        self.traversal = traversal_engine
        self.client = terminus_client
        self.config = config or get_validation_config()
        self.database_name = database_name
        self._dependency_cache: Dict[str, List[DependencyPath]] = {}
        
        # Ensure client is connected
        if not hasattr(self.client, 'connected') or not self.client.connected:
            logger.warning("TerminusDB client not connected. Call connect() before using dependency analyzer.")
        
    async def analyze_change_impact(
        self, 
        changed_entity: str, 
        change_type: str = "modification"
    ) -> Dict[str, List[str]]:
        """
        Analyze impact of changes to an entity across the dependency graph.
        
        Uses TerminusDB WOQL to find all entities that depend on the changed entity,
        both directly and transitively.
        """
        impact_analysis = {
            "directly_affected": [],
            "transitively_affected": [],
            "critical_services": [],
            "recommended_actions": []
        }
        
        try:
            # Find direct dependents using proper WOQL syntax
            dependency_relations = self.config.dependency_relations
            
            # Build queries for each dependency relation
            relation_queries = []
            for relation in dependency_relations:
                relation_uri = self.config.get_schema_uri(relation)
                impact_level_uri = self.config.get_schema_uri("impact_level")
                
                relation_query = (WQ()
                    .triple("v:dependent", relation_uri, WQ.string(changed_entity))
                    .opt(WQ().triple("v:dependent", impact_level_uri, "v:impact_level"))
                    .select("v:dependent", "v:impact_level")
                )
                relation_queries.append(relation_query)
            
            # Execute queries and collect results
            all_dependents = []
            for query in relation_queries:
                try:
                    query_json = json.dumps(query.to_dict()) if hasattr(query, 'to_dict') else str(query)
                    result = await self.client.query(
                        db_name=self.database_name,
                        query=query_json,
                        commit_msg="Find direct dependents"
                    )
                    all_dependents.extend(result.get('bindings', []))
                except (json.JSONDecodeError, AttributeError) as e:
                    # Log error but continue
                    logger.error(f"Error serializing query for relation: {e}")
                    continue
                except RuntimeError as e:
                    # Log error but continue
                    logger.error(f"Query execution error for relation: {e}")
                    continue
            
            # Process direct dependencies
            direct_dependents = []
            for binding in all_dependents:
                dependent = binding.get('v:dependent', {}).get('@value', '')
                impact_level = binding.get('v:impact_level', {}).get('@value', 'medium')
                
                if dependent and dependent not in direct_dependents:
                    direct_dependents.append(dependent)
                    if impact_level == 'critical':
                        impact_analysis["critical_services"].append(dependent)
            
            impact_analysis["directly_affected"] = direct_dependents
            
            # Find transitive dependencies using path queries
            transitive_dependents = set()
            max_depth = min(5, self.config.max_traversal_depth)
            
            for dependent in direct_dependents[:10]:  # Limit to avoid performance issues
                try:
                    paths = self.traversal.find_dependency_paths(
                        dependent, changed_entity, max_depth=max_depth
                    )
                    for path in paths:
                        transitive_dependents.update(path.path[1:-1])  # Exclude start/end
                except (RuntimeError, ValueError) as e:
                    # Skip if path finding fails
                    continue
            
            impact_analysis["transitively_affected"] = list(transitive_dependents)
            
            # Generate recommendations based on change type and impact
            recommendations = self._generate_impact_recommendations(
                changed_entity, change_type, direct_dependents, 
                list(transitive_dependents)
            )
            impact_analysis["recommended_actions"] = recommendations
            
            return impact_analysis
            
        except (KeyError, ValueError) as e:
            raise RuntimeError(f"Data processing error in impact analysis for {changed_entity}: {e}")
        except RuntimeError as e:
            raise RuntimeError(f"Impact analysis failed for {changed_entity}: {e}")
    
    async def detect_circular_dependencies(self) -> List[SemanticConflict]:
        """
        Detect circular dependencies in the ontology graph using WOQL path queries.
        
        Uses TerminusDB's path() function with cycle detection to identify
        problematic dependency cycles.
        """
        conflicts = []
        
        try:
            # Find cycles by checking each dependency relation
            dependency_relations = self.config.dependency_relations
            all_cycles = []
            
            for relation in dependency_relations:
                relation_uri = self.config.get_schema_uri(relation)
                
                # Simple cycle detection: find nodes that have paths to themselves
                cycle_query = (WQ()
                    .path("v:node", f"({relation_uri})+", "v:node", "v:cycle_path")
                    .triple("v:node", "rdf:type", "v:node_type")
                    .select("v:node", "v:cycle_path")
                )
                
                try:
                    query_json = json.dumps(cycle_query.to_dict()) if hasattr(cycle_query, 'to_dict') else str(cycle_query)
                    result = await self.client.query(
                        db_name=self.database_name,
                        query=query_json,
                        commit_msg="Detect circular dependencies"
                    )
                    all_cycles.extend(result.get('bindings', []))
                except (json.JSONDecodeError, AttributeError) as e:
                    # Skip if query serialization fails for this relation
                    continue
                except RuntimeError as e:
                    # Skip if cycle detection fails for this relation
                    continue
            
            # Process detected cycles
            seen_cycles = set()
            for binding in all_cycles:
                node = binding.get('v:node', {}).get('@value', '')
                cycle_path = binding.get('v:cycle_path', {}).get('@value', [])
                
                if node and cycle_path and len(cycle_path) > 1:
                    # Create a normalized cycle representation for deduplication
                    normalized_cycle = tuple(sorted(cycle_path))
                    if normalized_cycle not in seen_cycles:
                        seen_cycles.add(normalized_cycle)
                        
                        severity = self.config.get_severity_level(
                            1.0 / len(cycle_path)  # Shorter cycles are more severe
                        )
                        
                        conflict = SemanticConflict(
                            conflict_type=ConflictType.CIRCULAR_DEPENDENCY,
                            severity=severity,
                            affected_nodes=cycle_path,
                            description=f"Circular dependency detected: {' -> '.join(cycle_path)} -> {cycle_path[0]}",
                            suggested_resolution=f"Break cycle by removing dependency between {cycle_path[-1]} and {cycle_path[0]}",
                            impact_scope=cycle_path
                        )
                        conflicts.append(conflict)
            
            return conflicts
            
        except (KeyError, ValueError) as e:
            raise RuntimeError(f"Data processing error in circular dependency detection: {e}")
        except RuntimeError as e:
            raise RuntimeError(f"Circular dependency detection failed: {e}")
    
    async def find_critical_paths(self, max_paths: int = 10) -> List[DependencyPath]:
        """
        Identify critical dependency paths in the ontology.
        
        Critical paths are those that:
        1. Connect many entities (high fan-out)
        2. Are short but essential (backbone connections)
        3. Have high impact if broken
        """
        try:
            # Find high-degree nodes using simpler queries
            dependency_relations = self.config.dependency_relations
            node_degrees = {}
            
            # Calculate in-degree and out-degree separately
            for relation in dependency_relations:
                relation_uri = self.config.get_schema_uri(relation)
                
                # In-degree: count incoming connections
                in_degree_query = (WQ()
                    .triple("v:source", relation_uri, "v:node")
                    .group_by("v:node", WQ().count("v:source", "v:in_count"))
                    .select("v:node", "v:in_count")
                )
                
                # Out-degree: count outgoing connections  
                out_degree_query = (WQ()
                    .triple("v:node", relation_uri, "v:target")
                    .group_by("v:node", WQ().count("v:target", "v:out_count"))
                    .select("v:node", "v:out_count")
                )
                
                try:
                    # Execute queries
                    in_query_json = json.dumps(in_degree_query.to_dict()) if hasattr(in_degree_query, 'to_dict') else str(in_degree_query)
                    out_query_json = json.dumps(out_degree_query.to_dict()) if hasattr(out_degree_query, 'to_dict') else str(out_degree_query)
                    in_result = await self.client.query(
                        db_name=self.database_name,
                        query=in_query_json,
                        commit_msg="Calculate in-degrees"
                    )
                    out_result = await self.client.query(
                        db_name=self.database_name,
                        query=out_query_json,
                        commit_msg="Calculate out-degrees"
                    )
                    
                    # Process in-degree results
                    for binding in in_result.get('bindings', []):
                        node = binding.get('v:node', {}).get('@value', '')
                        in_count = binding.get('v:in_count', {}).get('@value', 0)
                        if node:
                            if node not in node_degrees:
                                node_degrees[node] = {'in': 0, 'out': 0}
                            node_degrees[node]['in'] += in_count
                    
                    # Process out-degree results
                    for binding in out_result.get('bindings', []):
                        node = binding.get('v:node', {}).get('@value', '')
                        out_count = binding.get('v:out_count', {}).get('@value', 0)
                        if node:
                            if node not in node_degrees:
                                node_degrees[node] = {'in': 0, 'out': 0}
                            node_degrees[node]['out'] += out_count
                            
                except (json.JSONDecodeError, AttributeError) as e:
                    # Skip if query serialization fails
                    continue
                except RuntimeError as e:
                    # Skip if degree calculation fails
                    continue
            
            # Find high-degree nodes
            high_degree_threshold = self.config.high_degree_threshold
            high_degree_nodes = []
            
            for node, degrees in node_degrees.items():
                total_degree = degrees['in'] + degrees['out']
                if total_degree >= high_degree_threshold:
                    high_degree_nodes.append((node, total_degree))
            
            # Sort by degree (highest first) and limit
            high_degree_nodes.sort(key=lambda x: x[1], reverse=True)
            high_degree_nodes = high_degree_nodes[:20]
            
            critical_paths = []
            
            # Find critical paths between high-degree nodes
            max_search_depth = min(4, self.config.max_traversal_depth)
            
            for i, (node1, degree1) in enumerate(high_degree_nodes[:5]):
                for node2, degree2 in high_degree_nodes[i+1:5]:
                    try:
                        paths = self.traversal.find_dependency_paths(
                            node1, node2, max_depth=max_search_depth
                        )
                        
                        for path in paths[:2]:  # Top 2 paths per node pair
                            path.is_critical = True
                            path.total_weight = (degree1 + degree2) / len(path.path) if path.path else 1.0
                            critical_paths.append(path)
                    except (RuntimeError, ValueError) as e:
                        # Skip if path finding fails
                        continue
            
            # Sort by criticality score
            critical_paths.sort(key=lambda p: p.total_weight, reverse=True)
            return critical_paths[:max_paths]
            
        except (KeyError, ValueError) as e:
            raise RuntimeError(f"Data processing error in critical path analysis: {e}")
        except RuntimeError as e:
            raise RuntimeError(f"Critical path analysis failed: {e}")
    
    async def analyze_orphaned_entities(self) -> List[SemanticConflict]:
        """
        Find entities that have no incoming or outgoing dependencies.
        
        Orphaned entities may indicate:
        1. Unused schema definitions
        2. Broken references
        3. Incomplete modeling
        """
        conflicts = []
        
        try:
            # Find orphaned entities by checking for lack of relationships
            if not self.config.orphan_detection_enabled:
                return []
            
            # Get all entities
            all_entities_query = (WQ()
                .triple("v:entity", "rdf:type", "v:entity_type")
                .select("v:entity", "v:entity_type")
            )
            
            try:
                query_json = json.dumps(all_entities_query.to_dict()) if hasattr(all_entities_query, 'to_dict') else str(all_entities_query)
                all_entities_result = await self.client.query(
                    db_name=self.database_name,
                    query=query_json,
                    commit_msg="Get all entities"
                )
                all_entities = [(binding.get('v:entity', {}).get('@value', ''), 
                               binding.get('v:entity_type', {}).get('@value', '')) 
                              for binding in all_entities_result.get('bindings', [])]
            except (json.JSONDecodeError, RuntimeError) as e:
                return []
            
            # Check each entity for relationships
            orphaned_entities = []
            dependency_relations = self.config.dependency_relations
            
            for entity, entity_type in all_entities[:100]:  # Limit to avoid performance issues
                if not entity or self.config.system_namespace in entity_type:
                    continue
                    
                has_relationships = False
                
                # Check for any incoming or outgoing relationships
                for relation in dependency_relations:
                    relation_uri = self.config.get_schema_uri(relation)
                    
                    # Check outgoing
                    outgoing_query = (WQ()
                        .triple(WQ.string(entity), relation_uri, "v:target")
                        .limit(1)
                        .select("v:target")
                    )
                    
                    # Check incoming
                    incoming_query = (WQ()
                        .triple("v:source", relation_uri, WQ.string(entity))
                        .limit(1)
                        .select("v:source")
                    )
                    
                    try:
                        out_query_json = json.dumps(outgoing_query.to_dict()) if hasattr(outgoing_query, 'to_dict') else str(outgoing_query)
                        in_query_json = json.dumps(incoming_query.to_dict()) if hasattr(incoming_query, 'to_dict') else str(incoming_query)
                        out_result = await self.client.query(
                            db_name=self.database_name,
                            query=out_query_json,
                            commit_msg="Check outgoing"
                        )
                        in_result = await self.client.query(
                            db_name=self.database_name,
                            query=in_query_json,
                            commit_msg="Check incoming"
                        )
                        
                        if (out_result.get('bindings') or in_result.get('bindings')):
                            has_relationships = True
                            break
                    except (json.JSONDecodeError, RuntimeError):
                        continue
                
                if not has_relationships:
                    orphaned_entities.append(entity)
            
            # Result already collected above
            
            if orphaned_entities:
                conflict = SemanticConflict(
                    conflict_type=ConflictType.ORPHANED_NODE,
                    severity="medium",
                    affected_nodes=orphaned_entities,
                    description=f"Found {len(orphaned_entities)} orphaned entities with no dependencies",
                    suggested_resolution="Review and either connect to dependency graph or remove if unused",
                    impact_scope=orphaned_entities
                )
                conflicts.append(conflict)
            
            return conflicts
            
        except (KeyError, ValueError) as e:
            raise RuntimeError(f"Data processing error in orphaned entity analysis: {e}")
        except RuntimeError as e:
            raise RuntimeError(f"Orphaned entity analysis failed: {e}")
    
    def _generate_impact_recommendations(
        self,
        changed_entity: str,
        change_type: str,
        direct_dependents: List[str],
        transitive_dependents: List[str]
    ) -> List[str]:
        """Generate actionable recommendations based on impact analysis"""
        recommendations = []
        
        total_affected = len(direct_dependents) + len(transitive_dependents)
        
        if change_type == "deletion":
            recommendations.append(f"⚠️  BREAKING CHANGE: Deleting {changed_entity} will affect {total_affected} entities")
            recommendations.append("Consider deprecation workflow instead of immediate deletion")
            
        elif change_type == "modification":
            if self.config.is_high_impact_change(total_affected):
                recommendations.append(f"📊 High impact change affecting {total_affected} entities")
                recommendations.append("Consider phased rollout with compatibility layer")
            
        if direct_dependents:
            recommendations.append(f"🔗 Update {len(direct_dependents)} direct dependents: {', '.join(direct_dependents[:3])}{'...' if len(direct_dependents) > 3 else ''}")
            
        if transitive_dependents:
            recommendations.append(f"🌐 Validate {len(transitive_dependents)} transitive dependencies")
            
        return recommendations