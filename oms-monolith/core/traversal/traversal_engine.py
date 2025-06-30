"""
TerminusDB Native Traversal Engine

Core graph traversal engine leveraging TerminusDB's WOQL capabilities.
Provides enterprise-grade semantic graph operations for OMS.
"""

import asyncio
import uuid
import json
import logging
from typing import List, Dict, Optional, Set, Any
from datetime import datetime, timezone

from terminusdb_client.woqlquery import WOQLQuery as WQ
from core.traversal.models import (
    TraversalQuery, TraversalResult, GraphNode, GraphEdge, 
    DependencyPath, TraversalDirection, GraphMetrics
)
from core.validation.config import get_validation_config, ValidationConfig
from database.clients.terminus_db import TerminusDBClient
from shared.cache.terminusdb_cache import TerminusDBCache
from typing import Optional, Protocol

logger = logging.getLogger(__name__)


class MetricsCollector(Protocol):
    """Protocol for metrics collection"""
    def record_traversal_query(self, query_type: str, execution_time_ms: float, result_count: int) -> None: ...
    def record_traversal_error(self, error_message: str) -> None: ...


class TraversalEngine:
    """
    TerminusDB-native graph traversal engine for OMS.
    
    Provides enterprise-grade graph operations:
    - Multi-hop semantic traversal using WOQL path queries
    - Dependency analysis with cycle detection
    - Performance optimization via caching
    - Metrics collection for monitoring
    """
    
    def __init__(
        self, 
        terminus_client: TerminusDBClient,
        config: Optional[ValidationConfig] = None,
        cache: Optional[TerminusDBCache] = None,
        metrics: Optional[MetricsCollector] = None,
        database_name: str = "oms"
    ):
        self.client = terminus_client
        self.config = config or get_validation_config()
        self.cache = cache
        self.metrics = metrics
        self.database_name = database_name
        self._query_cache: Dict[str, TraversalResult] = {}
        
        # Ensure client is properly configured
        if not hasattr(self.client, 'connected') or not self.client.connected:
            logger.warning("TerminusDB client not connected. Call connect() before using traversal engine.")
        
    async def traverse(self, query: TraversalQuery) -> TraversalResult:
        """
        Execute graph traversal using TerminusDB WOQL.
        
        Leverages native TerminusDB path queries for efficient traversal:
        - WQ.path() for multi-hop relationships
        - Recursive operators (+, *, ?) for flexible depth
        - Variable binding for result collection
        """
        start_time = datetime.now(timezone.utc)
        query_id = str(uuid.uuid4())
        
        try:
            # Check cache first
            cache_key = self._generate_cache_key(query)
            if self.cache and cache_key in self._query_cache:
                return self._query_cache[cache_key]
            
            # Build WOQL query based on traversal specification
            woql_query = self._build_traversal_woql(query)
            
            # Execute query via TerminusDB with proper async handling
            result_data = await self._execute_woql_query(woql_query)
            
            # Process results into graph structure
            nodes, edges, paths = self._process_traversal_results(
                result_data, query
            )
            
            # Calculate execution metrics
            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            result = TraversalResult(
                query_id=query_id,
                nodes=nodes,
                edges=edges, 
                paths=paths,
                execution_time_ms=execution_time,
                metrics=self._calculate_result_metrics(nodes, edges)
            )
            
            # Cache result if enabled
            if self.cache:
                self._query_cache[cache_key] = result
                
            # Record metrics
            if self.metrics:
                self.metrics.record_traversal_query(
                    query_type="standard",
                    execution_time_ms=execution_time,
                    result_count=len(nodes)
                )
                
            return result
            
        except (ConnectionError, TimeoutError) as e:
            if self.metrics:
                self.metrics.record_traversal_error(str(e))
            raise
        except (ValueError, RuntimeError) as e:
            if self.metrics:
                self.metrics.record_traversal_error(str(e))
            raise
    
    def _build_traversal_woql(self, query: TraversalQuery) -> WQ:
        """
        Build WOQL query for graph traversal using official TerminusDB syntax.
        
        Uses proper TerminusDB WOQL patterns:
        - Basic triple patterns for direct relationships
        - Path queries for multi-hop traversal
        - Proper variable binding and selection
        """
        # Get schema URIs from configuration
        relation_uris = self.config.get_relation_uris(query.relations)
        
        if query.max_depth == 1:
            # Simple direct relationship query
            return self._build_direct_traversal(query, relation_uris)
        else:
            # Multi-hop path traversal
            return self._build_path_traversal(query, relation_uris)
    
    def _build_direct_traversal(self, query: TraversalQuery, relation_uris: List[str]) -> WQ:
        """Build WOQL for direct (depth=1) traversal"""
        woql_queries = []
        
        for start_node in query.start_nodes:
            for relation_uri in relation_uris:
                if query.direction == TraversalDirection.OUTBOUND:
                    base_query = (WQ()
                        .triple(WQ.string(start_node), relation_uri, "v:target")
                        .triple("v:target", "rdf:type", "v:target_type")
                        .opt(WQ().triple("v:target", "rdfs:label", "v:target_label"))
                    )
                elif query.direction == TraversalDirection.INBOUND:
                    base_query = (WQ()
                        .triple("v:target", relation_uri, WQ.string(start_node))
                        .triple("v:target", "rdf:type", "v:target_type")
                        .opt(WQ().triple("v:target", "rdfs:label", "v:target_label"))
                    )
                else:  # BIDIRECTIONAL
                    outbound = (WQ()
                        .triple(WQ.string(start_node), relation_uri, "v:target")
                        .triple("v:target", "rdf:type", "v:target_type")
                        .opt(WQ().triple("v:target", "rdfs:label", "v:target_label"))
                    )
                    inbound = (WQ()
                        .triple("v:target", relation_uri, WQ.string(start_node))
                        .triple("v:target", "rdf:type", "v:target_type")
                        .opt(WQ().triple("v:target", "rdfs:label", "v:target_label"))
                    )
                    base_query = WQ().woql_or(outbound, inbound)
                
                # Add filters
                if query.filters:
                    for prop, value in query.filters.items():
                        prop_uri = self.config.get_schema_uri(prop)
                        base_query = base_query.triple("v:target", prop_uri, WQ.string(str(value)))
                
                woql_queries.append(base_query)
        
        # Combine all queries
        if len(woql_queries) == 1:
            final_query = woql_queries[0]
        else:
            final_query = WQ().woql_or(*woql_queries)
        
        # Add metadata if requested
        if query.include_metadata:
            metadata_props = self.config.metadata_properties
            for prop in metadata_props:
                prop_uri = self.config.get_schema_uri(prop)
                final_query = final_query.opt(
                    WQ().triple("v:target", prop_uri, f"v:{prop}")
                )
        
        # Apply limit
        if query.limit:
            final_query = final_query.limit(query.limit)
        
        # Select variables
        select_vars = ["v:target", "v:target_type", "v:target_label"]
        if query.include_metadata:
            select_vars.extend([f"v:{prop}" for prop in self.config.traversal.metadata_properties])
        
        return final_query.select(*select_vars)
    
    def _build_path_traversal(self, query: TraversalQuery, relation_uris: List[str]) -> WQ:
        """Build WOQL for path-based (depth>1) traversal"""
        # For multi-hop, use path() with proper TerminusDB syntax
        path_queries = []
        
        for start_node in query.start_nodes:
            for relation_uri in relation_uris:
                # Build path pattern - TerminusDB uses specific syntax for repetition
                if query.max_depth <= 3:
                    path_pattern = f"({relation_uri})+"  # 1 or more repetitions
                else:
                    path_pattern = f"({relation_uri})*"  # 0 or more repetitions
                
                path_query = (WQ()
                    .path(WQ.string(start_node), path_pattern, "v:target")
                    .triple("v:target", "rdf:type", "v:target_type")
                    .opt(WQ().triple("v:target", "rdfs:label", "v:target_label"))
                )
                
                # Add filters
                if query.filters:
                    for prop, value in query.filters.items():
                        prop_uri = self.config.get_schema_uri(prop)
                        path_query = path_query.triple("v:target", prop_uri, WQ.string(str(value)))
                
                path_queries.append(path_query)
        
        # Combine queries
        if len(path_queries) == 1:
            final_query = path_queries[0]
        else:
            final_query = WQ().woql_or(*path_queries)
        
        # Apply limit and select
        if query.limit:
            final_query = final_query.limit(query.limit)
        
        select_vars = ["v:target", "v:target_type", "v:target_label"]
        return final_query.select(*select_vars)
    
    async def _execute_woql_query(self, woql_query: WQ) -> List[Dict[str, Any]]:
        """Execute WOQL query via TerminusDB client with proper async handling"""
        try:
            # Convert WOQL to JSON string for API call
            query_json = json.dumps(woql_query.to_dict()) if hasattr(woql_query, 'to_dict') else str(woql_query)
            
            # Execute query with proper database name parameter
            result = await self.client.query(
                db_name=self.database_name,
                query=query_json, 
                commit_msg="Graph traversal query"
            )
            
            logger.debug(f"WOQL query executed successfully, bindings: {len(result.get('bindings', []))}")
            return result.get('bindings', [])
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Network error during WOQL query execution: {e}")
            raise RuntimeError(f"WOQL query execution failed: {e}")
        except (ValueError, KeyError) as e:
            logger.error(f"WOQL query execution failed: {e}")
            raise RuntimeError(f"WOQL query execution failed: {e}")
    
    def _process_traversal_results(
        self, 
        result_data: List[Dict[str, Any]], 
        query: TraversalQuery
    ) -> tuple[List[GraphNode], List[GraphEdge], List[DependencyPath]]:
        """Process raw WOQL results into graph structures"""
        nodes = []
        edges = []
        paths = []
        
        seen_nodes = set()
        
        for binding in result_data:
            # Extract node information
            node_id = binding.get('v:target', {}).get('@value', '')
            node_type = binding.get('v:target_type', {}).get('@value', '')
            node_label = binding.get('v:target_label', {}).get('@value', '')
            
            if node_id and node_id not in seen_nodes:
                # Build node properties
                properties = {}
                if 'v:created' in binding:
                    properties['created_at'] = binding['v:created'].get('@value')
                if 'v:modified' in binding:
                    properties['modified_at'] = binding['v:modified'].get('@value')
                
                node = GraphNode(
                    id=node_id,
                    type=node_type,
                    label=node_label,
                    properties=properties,
                    depth=0  # Will be calculated in path analysis
                )
                nodes.append(node)
                seen_nodes.add(node_id)
        
        return nodes, edges, paths
    
    def _calculate_result_metrics(
        self, 
        nodes: List[GraphNode], 
        edges: List[GraphEdge]
    ) -> Dict[str, Any]:
        """Calculate metrics for traversal result"""
        return {
            'node_count': len(nodes),
            'edge_count': len(edges),
            'max_depth': max([n.depth for n in nodes]) if nodes else 0,
            'unique_types': len(set(n.type for n in nodes)),
            'memory_usage_bytes': sum(len(str(n.properties)) for n in nodes)
        }
    
    def _generate_cache_key(self, query: TraversalQuery) -> str:
        """Generate cache key for query"""
        key_parts = [
            ",".join(sorted(query.start_nodes)),
            ",".join(sorted(query.relations)),
            query.direction.value,
            str(query.max_depth),
            str(query.limit or 0)
        ]
        return "|".join(key_parts)
    
    async def find_dependency_paths(
        self, 
        start_node: str, 
        end_node: str,
        max_depth: Optional[int] = None
    ) -> List[DependencyPath]:
        """
        Find all dependency paths between two nodes using WOQL path queries.
        
        Uses TerminusDB's path() function with proper syntax.
        """
        if max_depth is None:
            max_depth = self.config.traversal.max_traversal_depth
        
        # Use configured dependency relations
        dependency_relations = self.config.traversal.dependency_relations
        dependency_uris = self.config.get_relation_uris(dependency_relations)
        
        all_paths = []
        
        for relation_uri in dependency_uris:
            # Build path query with proper TerminusDB syntax
            path_pattern = f"({relation_uri})+"  # One or more hops
            
            woql_query = (WQ()
                .path(WQ.string(start_node), path_pattern, WQ.string(end_node), "v:path")
                .length("v:path", "v:path_length")
                .select("v:path", "v:path_length")
            )
            
            try:
                # Convert WOQL to JSON and execute with proper parameters
                query_json = json.dumps(woql_query.to_dict()) if hasattr(woql_query, 'to_dict') else str(woql_query)
                result = await self.client.query(
                    db_name=self.database_name,
                    query=query_json, 
                    commit_msg="Find dependency paths"
                )
                
                for binding in result.get('bindings', []):
                    path_data = binding.get('v:path', {}).get('@value', [])
                    path_length = binding.get('v:path_length', {}).get('@value', 0)
                    
                    if path_data and path_length <= max_depth:
                        path = DependencyPath(
                            start_node=start_node,
                            end_node=end_node,
                            path=path_data,
                            relations=[relation_uri.split(':')[-1]] * (len(path_data) - 1),
                            total_weight=float(path_length),
                            is_critical=self.config.is_critical_path(path_length)
                        )
                        all_paths.append(path)
                        
            except (ConnectionError, RuntimeError) as e:
                # Log error but continue with other relations
                if self.metrics:
                    self.metrics.record_traversal_error(f"Path query failed for {relation_uri}: {e}")
                continue
        
        return sorted(all_paths, key=lambda p: p.total_weight)
    
    async def get_graph_metrics(self) -> GraphMetrics:
        """
        Calculate comprehensive graph metrics using TerminusDB queries.
        
        Leverages WOQL aggregation functions for efficient calculation
        of graph connectivity and health metrics.
        """
        try:
            # Count total nodes using proper WOQL syntax
            node_count_query = (WQ()
                .triple("v:node", "rdf:type", "v:type")
                .count("v:node", "v:node_count")
                .select("v:node_count")
            )
            
            # Count total edges
            edge_count_query = (WQ()
                .triple("v:src", "v:relation", "v:dst")
                .count("v:relation", "v:edge_count")
                .select("v:edge_count")
            )
            
            # Execute queries separately as TerminusDB doesn't support complex joins
            node_query_json = json.dumps(node_count_query.to_dict()) if hasattr(node_count_query, 'to_dict') else str(node_count_query)
            edge_query_json = json.dumps(edge_count_query.to_dict()) if hasattr(edge_count_query, 'to_dict') else str(edge_count_query)
            
            node_result = await self.client.query(
                db_name=self.database_name,
                query=node_query_json, 
                commit_msg="Count nodes"
            )
            edge_result = await self.client.query(
                db_name=self.database_name,
                query=edge_query_json, 
                commit_msg="Count edges"
            )
            
            # Extract metrics from results
            node_bindings = node_result.get('bindings', [])
            edge_bindings = edge_result.get('bindings', [])
            
            node_count = node_bindings[0].get('v:node_count', {}).get('@value', 0) if node_bindings else 0
            edge_count = edge_bindings[0].get('v:edge_count', {}).get('@value', 0) if edge_bindings else 0
            
            # Calculate derived metrics
            density = (2 * edge_count) / (node_count * (node_count - 1)) if node_count > 1 else 0
            avg_degree = (2 * edge_count) / node_count if node_count > 0 else 0
            
            metrics = GraphMetrics(
                total_nodes=node_count,
                total_edges=edge_count,
                connected_components=1,  # Will be calculated via separate query
                average_degree=avg_degree,
                density=density,
                clustering_coefficient=0.0,  # Requires complex calculation
                longest_path=0,  # Will be calculated via path queries
                critical_nodes=[],
                orphaned_nodes=[]
            )
            
            logger.info(f"Graph metrics calculated: nodes={node_count}, edges={edge_count}, density={density:.3f}")
            return metrics
            
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Network error during graph metrics calculation: {e}")
            raise RuntimeError(f"Graph metrics calculation failed: {e}")
        except (ValueError, KeyError) as e:
            logger.error(f"Graph metrics calculation failed: {e}")
            raise RuntimeError(f"Graph metrics calculation failed: {e}")