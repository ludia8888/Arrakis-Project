"""
GraphQL Schema for Graph Traversal

Provides GraphQL interface for TerminusDB graph traversal operations.
Supports path queries, dependency analysis, and semantic validation.
"""

import strawberry
from typing import List, Optional, Dict, Any
from datetime import datetime

from core.traversal.models import (
    TraversalDirection, ConflictType, GraphNode, GraphEdge, 
    DependencyPath, SemanticConflict, GraphMetrics
)


# GraphQL Types
@strawberry.enum
class TraversalDirectionEnum(TraversalDirection):
    """Graph traversal direction"""
    OUTBOUND = "outbound"
    INBOUND = "inbound" 
    BIDIRECTIONAL = "bidirectional"


@strawberry.enum
class ConflictTypeEnum(ConflictType):
    """Types of semantic conflicts"""
    DANGLING_REFERENCE = "dangling_reference"
    CIRCULAR_DEPENDENCY = "circular_dependency"
    TYPE_MISMATCH = "type_mismatch"
    CARDINALITY_VIOLATION = "cardinality_violation"
    ORPHANED_NODE = "orphaned_node"


@strawberry.type
class GraphNodeType:
    """GraphQL type for graph nodes"""
    id: str
    type: str
    label: str
    properties: strawberry.scalars.JSON
    depth: int


@strawberry.type
class GraphEdgeType:
    """GraphQL type for graph edges"""
    source: str
    target: str
    relation: str
    properties: strawberry.scalars.JSON


@strawberry.type
class DependencyPathType:
    """GraphQL type for dependency paths"""
    start_node: str
    end_node: str
    path: List[str]
    relations: List[str]
    total_weight: float
    is_critical: bool


@strawberry.type
class SemanticConflictType:
    """GraphQL type for semantic conflicts"""
    conflict_type: ConflictTypeEnum
    severity: str
    affected_nodes: List[str]
    description: str
    suggested_resolution: Optional[str]
    impact_scope: List[str]


@strawberry.type
class GraphMetricsType:
    """GraphQL type for graph metrics"""
    total_nodes: int
    total_edges: int
    connected_components: int
    average_degree: float
    density: float
    clustering_coefficient: float
    longest_path: int
    critical_nodes: List[str]
    orphaned_nodes: List[str]


@strawberry.type
class TraversalResultType:
    """GraphQL type for traversal results"""
    query_id: str
    nodes: List[GraphNodeType]
    edges: List[GraphEdgeType]
    paths: List[DependencyPathType]
    metrics: strawberry.scalars.JSON
    execution_time_ms: float
    timestamp: datetime


@strawberry.type
class ImpactAnalysisType:
    """GraphQL type for impact analysis results"""
    changed_entity: str
    change_type: str
    directly_affected: List[str]
    transitively_affected: List[str]
    critical_services: List[str]
    recommended_actions: List[str]


# Input Types
@strawberry.input
class TraversalQueryInput:
    """GraphQL input for traversal queries"""
    start_nodes: List[str]
    relations: List[str]
    direction: TraversalDirectionEnum = TraversalDirectionEnum.OUTBOUND
    max_depth: int = 5
    limit: Optional[int] = None
    filters: Optional[strawberry.scalars.JSON] = None
    include_metadata: bool = True


@strawberry.input
class PathQueryInput:
    """GraphQL input for path queries"""
    source: str
    target: str
    relations: Optional[List[str]] = None
    max_depth: int = 5
    direction: TraversalDirectionEnum = TraversalDirectionEnum.OUTBOUND
    include_paths: bool = True


@strawberry.input
class DependencyQueryInput:
    """GraphQL input for dependency queries"""
    entity: str
    depth: int = 3
    include_transitive: bool = True
    filter_critical: bool = False


@strawberry.input
class ImpactAnalysisInput:
    """GraphQL input for impact analysis"""
    changed_entity: str
    change_type: str = "modification"
    include_recommendations: bool = True


# GraphQL Queries
@strawberry.type
class TraversalQuery:
    """GraphQL queries for graph traversal"""
    
    @strawberry.field
    async def traverse(
        self, 
        query: TraversalQueryInput,
        info: strawberry.Info
    ) -> TraversalResultType:
        """
        Execute graph traversal using TerminusDB WOQL path queries.
        
        Example query:
        ```graphql
        query {
          traverse(query: {
            startNodes: ["Customer:123"],
            relations: ["has_order", "contains_product"],
            direction: OUTBOUND,
            maxDepth: 3,
            limit: 100
          }) {
            queryId
            nodes {
              id
              type
              label
              depth
            }
            paths {
              startNode
              endNode
              path
              totalWeight
              isCritical
            }
            executionTimeMs
          }
        }
        ```
        """
        from core.traversal.traversal_engine import TraversalEngine
        from core.traversal.models import TraversalQuery as CoreTraversalQuery
        from database.clients.terminus_db import TerminusDBClient
        
        # Initialize dependencies
        terminus_client = TerminusDBClient()
        traversal_engine = TraversalEngine(terminus_client)
        
        # Create core query object
        core_query = CoreTraversalQuery(
            start_nodes=query.start_nodes,
            relations=query.relations,
            direction=query.direction.value,
            max_depth=query.max_depth,
            limit=query.limit,
            filters=query.filters or {},
            include_metadata=query.include_metadata
        )
        
        # Execute traversal
        result = await traversal_engine.traverse(core_query)
        
        # Convert to GraphQL types
        return TraversalResultType(
            query_id=result.query_id,
            nodes=[
                GraphNodeType(
                    id=node.id,
                    type=node.type,
                    label=node.label,
                    properties=node.properties,
                    depth=node.depth
                ) for node in result.nodes
            ],
            edges=[
                GraphEdgeType(
                    source=edge.source,
                    target=edge.target,
                    relation=edge.relation,
                    properties=edge.properties
                ) for edge in result.edges
            ],
            paths=[
                DependencyPathType(
                    start_node=path.start_node,
                    end_node=path.end_node,
                    path=path.path,
                    relations=path.relations,
                    total_weight=path.total_weight,
                    is_critical=path.is_critical
                ) for path in result.paths
            ],
            metrics=result.metrics,
            execution_time_ms=result.execution_time_ms,
            timestamp=result.timestamp
        )
    
    @strawberry.field
    async def find_paths(
        self,
        query: PathQueryInput,
        limit: int = 10,
        info: strawberry.Info
    ) -> List[DependencyPathType]:
        """
        Find all paths between two entities.
        
        Example query:
        ```graphql
        query {
          findPaths(
            query: {
              source: "Product:laptop",
              target: "Country:USA",
              relations: ["manufactured_in", "located_in"],
              maxDepth: 4
            },
            limit: 5
          ) {
            startNode
            endNode
            path
            relations
            totalWeight
            isCritical
          }
        }
        ```
        """
        from core.traversal.traversal_engine import TraversalEngine
        from database.clients.terminus_db import TerminusDBClient
        
        # Initialize dependencies
        terminus_client = TerminusDBClient()
        traversal_engine = TraversalEngine(terminus_client)
        
        # Find paths
        paths = await traversal_engine.find_dependency_paths(
            start_node=query.source,
            end_node=query.target,
            max_depth=query.max_depth
        )
        
        # Convert to GraphQL types and apply limit
        return [
            DependencyPathType(
                start_node=path.start_node,
                end_node=path.end_node,
                path=path.path,
                relations=path.relations,
                total_weight=path.total_weight,
                is_critical=path.is_critical
            ) for path in paths[:limit]
        ]
    
    @strawberry.field
    async def dependencies(
        self,
        query: DependencyQueryInput,
        info: strawberry.Info
    ) -> ImpactAnalysisType:
        """
        Analyze dependencies for an entity.
        
        Example query:
        ```graphql
        query {
          dependencies(query: {
            entity: "Order",
            depth: 3,
            includeTransitive: true,
            filterCritical: false
          }) {
            changedEntity
            directlyAffected
            transitivelyAffected
            criticalServices
            recommendedActions
          }
        }
        ```
        """
        from core.traversal.traversal_engine import TraversalEngine
        from core.traversal.dependency_analyzer import DependencyAnalyzer
        from database.clients.terminus_db import TerminusDBClient
        
        # Initialize dependencies
        terminus_client = TerminusDBClient()
        traversal_engine = TraversalEngine(terminus_client)
        dependency_analyzer = DependencyAnalyzer(traversal_engine, terminus_client)
        
        # Analyze dependencies
        impact_analysis = await dependency_analyzer.analyze_change_impact(
            changed_entity=query.entity,
            change_type="analysis"
        )
        
        return ImpactAnalysisType(
            changed_entity=query.entity,
            change_type="analysis",
            directly_affected=impact_analysis["directly_affected"],
            transitively_affected=impact_analysis["transitively_affected"],
            critical_services=impact_analysis["critical_services"],
            recommended_actions=impact_analysis["recommended_actions"]
        )
    
    @strawberry.field
    async def impact_analysis(
        self,
        query: ImpactAnalysisInput,
        info: strawberry.Info
    ) -> ImpactAnalysisType:
        """
        Analyze impact of proposed changes.
        
        Example query:
        ```graphql
        query {
          impactAnalysis(query: {
            changedEntity: "Product.price",
            changeType: "modification",
            includeRecommendations: true
          }) {
            changedEntity
            changeType
            directlyAffected
            transitivelyAffected
            criticalServices
            recommendedActions
          }
        }
        ```
        """
        from core.traversal.traversal_engine import TraversalEngine
        from core.traversal.dependency_analyzer import DependencyAnalyzer
        from database.clients.terminus_db import TerminusDBClient
        
        # Initialize dependencies
        terminus_client = TerminusDBClient()
        traversal_engine = TraversalEngine(terminus_client)
        dependency_analyzer = DependencyAnalyzer(traversal_engine, terminus_client)
        
        # Analyze impact
        impact_analysis = await dependency_analyzer.analyze_change_impact(
            changed_entity=query.changed_entity,
            change_type=query.change_type
        )
        
        return ImpactAnalysisType(
            changed_entity=query.changed_entity,
            change_type=query.change_type,
            directly_affected=impact_analysis["directly_affected"],
            transitively_affected=impact_analysis["transitively_affected"],
            critical_services=impact_analysis["critical_services"],
            recommended_actions=impact_analysis["recommended_actions"] if query.include_recommendations else []
        )
    
    @strawberry.field
    async def graph_metrics(self, info: strawberry.Info) -> GraphMetricsType:
        """
        Get graph connectivity and health metrics.
        
        Example query:
        ```graphql
        query {
          graphMetrics {
            totalNodes
            totalEdges
            connectedComponents
            averageDegree
            density
            clusteringCoefficient
            longestPath
            criticalNodes
            orphanedNodes
          }
        }
        ```
        """
        from core.traversal.traversal_engine import TraversalEngine
        from database.clients.terminus_db import TerminusDBClient
        
        # Initialize dependencies
        terminus_client = TerminusDBClient()
        traversal_engine = TraversalEngine(terminus_client)
        
        # Get metrics
        metrics = await traversal_engine.get_graph_metrics()
        
        return GraphMetricsType(
            total_nodes=metrics.total_nodes,
            total_edges=metrics.total_edges,
            connected_components=metrics.connected_components,
            average_degree=metrics.average_degree,
            density=metrics.density,
            clustering_coefficient=metrics.clustering_coefficient,
            longest_path=metrics.longest_path,
            critical_nodes=metrics.critical_nodes,
            orphaned_nodes=metrics.orphaned_nodes
        )
    
    @strawberry.field
    async def semantic_conflicts(
        self,
        include_circular: bool = True,
        include_orphaned: bool = True,
        severity_filter: str = "all",
        info: strawberry.Info
    ) -> List[SemanticConflictType]:
        """
        Detect semantic conflicts in the ontology.
        
        Example query:
        ```graphql
        query {
          semanticConflicts(
            includeCircular: true,
            includeOrphaned: true,
            severityFilter: "high"
          ) {
            conflictType
            severity
            affectedNodes
            description
            suggestedResolution
            impactScope
          }
        }
        ```
        """
        from core.traversal.traversal_engine import TraversalEngine
        from core.traversal.dependency_analyzer import DependencyAnalyzer
        from database.clients.terminus_db import TerminusDBClient
        
        # Initialize dependencies
        terminus_client = TerminusDBClient()
        traversal_engine = TraversalEngine(terminus_client)
        dependency_analyzer = DependencyAnalyzer(traversal_engine, terminus_client)
        
        conflicts = []
        
        if include_circular:
            circular_conflicts = await dependency_analyzer.detect_circular_dependencies()
            conflicts.extend(circular_conflicts)
            
        if include_orphaned:
            orphan_conflicts = await dependency_analyzer.analyze_orphaned_entities()
            conflicts.extend(orphan_conflicts)
        
        # Filter by severity
        if severity_filter != "all":
            conflicts = [c for c in conflicts if c.severity == severity_filter]
        
        return [
            SemanticConflictType(
                conflict_type=ConflictTypeEnum(conflict.conflict_type.value),
                severity=conflict.severity,
                affected_nodes=conflict.affected_nodes,
                description=conflict.description,
                suggested_resolution=conflict.suggested_resolution,
                impact_scope=conflict.impact_scope
            ) for conflict in conflicts
        ]


# Schema definition
schema = strawberry.Schema(
    query=TraversalQuery,
    types=[
        TraversalResultType,
        GraphNodeType,
        GraphEdgeType,
        DependencyPathType,
        SemanticConflictType,
        GraphMetricsType,
        ImpactAnalysisType
    ]
)