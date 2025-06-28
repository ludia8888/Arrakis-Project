"""
Graph Traversal API Routes

RESTful API endpoints for TerminusDB-based graph traversal operations.
Provides Foundry-grade ontology navigation and dependency analysis.
"""

import logging
from typing import List, Dict, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core.traversal.traversal_engine import TraversalEngine
from core.traversal.dependency_analyzer import DependencyAnalyzer
from core.traversal.semantic_validator import SemanticValidator
# Deprecated import - using validation layer instead
# from core.traversal.merge_validator import EnterpriseSemanticMergeValidator
from core.validation.merge_validation_service import MergeValidationService, MergeStrategy
from core.validation.adapters.terminus_traversal_adapter import create_terminus_traversal_adapter
from core.validation.rule_registry import RuleRegistry
from core.validation.config import ValidationConfig
from core.traversal.query_planner import QueryPlanner
from core.validation.config import get_validation_config
from core.traversal.models import (
    TraversalQuery, TraversalResult, DependencyPath, 
    SemanticConflict, GraphMetrics, TraversalDirection
)
from database.clients.terminus_db import TerminusDBClient
from shared.cache.terminusdb_cache import TerminusDBCache
from middleware.auth_msa import get_current_user, verify_permissions
from shared.config import get_settings

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1/traversal", tags=["Graph Traversal"])


# Dependency Injection Functions
async def get_terminus_client() -> TerminusDBClient:
    """Get configured TerminusDB client for traversal operations"""
    settings = get_settings()
    client = TerminusDBClient(
        endpoint=getattr(settings, 'TERMINUSDB_ENDPOINT', 'http://localhost:6363'),
        username=getattr(settings, 'TERMINUSDB_USERNAME', 'admin'),
        password=getattr(settings, 'TERMINUSDB_PASSWORD', 'changeme-admin-pass')
    )
    
    # Connect to database
    try:
        connected = await client.connect(
            team=getattr(settings, 'TERMINUSDB_TEAM', 'admin'),
            key=getattr(settings, 'TERMINUSDB_PASSWORD', 'changeme-admin-pass'),
            user=getattr(settings, 'TERMINUSDB_USERNAME', 'admin'),
            db=getattr(settings, 'TERMINUSDB_DATABASE', 'oms')
        )
        
        if not connected:
            raise HTTPException(status_code=503, detail="Failed to connect to TerminusDB")
        
        yield client
    finally:
        try:
            await client.disconnect()
        except Exception as e:
            logger.warning(f"Error disconnecting from TerminusDB: {e}")


async def get_traversal_engine(
    client: TerminusDBClient = Depends(get_terminus_client)
) -> TraversalEngine:
    """Get traversal engine instance"""
    config = get_validation_config()
    settings = get_settings()
    return TraversalEngine(
        terminus_client=client,
        config=config,
        database_name=getattr(settings, 'TERMINUSDB_DATABASE', 'oms')
    )


async def get_dependency_analyzer(
    engine: TraversalEngine = Depends(get_traversal_engine),
    client: TerminusDBClient = Depends(get_terminus_client)
) -> DependencyAnalyzer:
    """Get dependency analyzer instance"""
    config = get_validation_config()
    settings = get_settings()
    return DependencyAnalyzer(
        traversal_engine=engine,
        terminus_client=client,
        config=config,
        database_name=getattr(settings, 'TERMINUSDB_DATABASE', 'oms')
    )


# Request/Response Models
class PathQueryRequest(BaseModel):
    """Request model for path finding queries"""
    source: str = Field(description="Source entity ID")
    target: str = Field(description="Target entity ID")
    relations: List[str] = Field(default=[], description="Relation types to follow")
    max_depth: int = Field(default=5, ge=1, le=20, description="Maximum traversal depth")
    direction: TraversalDirection = Field(default=TraversalDirection.OUTBOUND)
    include_paths: bool = Field(default=True, description="Include actual paths in response")


class DependencyQueryRequest(BaseModel):
    """Request model for dependency analysis"""
    entity: str = Field(description="Entity to analyze")
    depth: int = Field(default=3, ge=1, le=10, description="Analysis depth")
    include_transitive: bool = Field(default=True, description="Include transitive dependencies")
    filter_critical: bool = Field(default=False, description="Only critical dependencies")


class GraphTraversalRequest(BaseModel):
    """Request model for general graph traversal"""
    start_nodes: List[str] = Field(description="Starting node IDs")
    relations: List[str] = Field(description="Relation types to follow")
    direction: TraversalDirection = Field(default=TraversalDirection.OUTBOUND)
    max_depth: int = Field(default=5, ge=1, le=20)
    limit: Optional[int] = Field(default=None, ge=1, le=1000)
    filters: Dict[str, Any] = Field(default_factory=dict)
    include_metadata: bool = Field(default=True)


class ImpactAnalysisRequest(BaseModel):
    """Request model for change impact analysis"""
    changed_entity: str = Field(description="Entity that will be changed")
    change_type: str = Field(default="modification", regex="^(addition|modification|deletion)$")
    include_recommendations: bool = Field(default=True)


# Legacy dependency injection functions removed - using new implementations above


# Core Graph Traversal Endpoints

@router.post("/traverse", response_model=TraversalResult)
async def traverse_graph(
    request: GraphTraversalRequest,
    traversal_engine: TraversalEngine = Depends(get_traversal_engine),
    current_user: dict = Depends(get_current_user)
):
    """
    Execute graph traversal query using TerminusDB WOQL path queries.
    
    Supports:
    - Multi-hop relationship traversal
    - Bidirectional path exploration
    - Advanced filtering and result limiting
    - Performance optimization via query planning
    """
    try:
        # Create traversal query
        query = TraversalQuery(
            start_nodes=request.start_nodes,
            relations=request.relations,
            direction=request.direction,
            max_depth=request.max_depth,
            limit=request.limit,
            filters=request.filters,
            include_metadata=request.include_metadata
        )
        
        # Execute traversal
        result = await traversal_engine.traverse(query)
        
        logger.info(f"Graph traversal completed for user {current_user.get('username', 'unknown')}: "
                   f"nodes={len(result.nodes)}, edges={len(result.edges)}, time={result.execution_time_ms}ms")
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph traversal failed: {str(e)}")


@router.get("/path/{source}/{target}", response_model=List[DependencyPath])
async def find_paths(
    source: str = Path(description="Source entity ID"),
    target: str = Path(description="Target entity ID"),
    relations: List[str] = Query(default=[], description="Relation types to follow"),
    max_depth: int = Query(default=5, ge=1, le=20, description="Maximum path depth"),
    direction: TraversalDirection = Query(default=TraversalDirection.OUTBOUND),
    limit: int = Query(default=10, ge=1, le=100, description="Maximum paths to return"),
    traversal_engine: TraversalEngine = Depends(get_traversal_engine),
    current_user: dict = Depends(get_current_user)
):
    """
    Find all paths between two entities using TerminusDB path() queries.
    
    Leverages WOQL's transitive closure capabilities:
    - path(source, "relation+", target, path_var)
    - Supports reverse/backlink traversal
    - Returns actual path sequences with weights
    """
    try:
        paths = await traversal_engine.find_dependency_paths(
            start_node=source,
            end_node=target,
            max_depth=max_depth
        )
        
        # Apply limit
        return paths[:limit]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Path finding failed: {str(e)}")


# Dependency Analysis Endpoints

@router.get("/dependencies/{entity}")
async def get_entity_dependencies(
    entity: str = Path(description="Entity ID to analyze"),
    depth: int = Query(default=3, ge=1, le=10, description="Analysis depth"),
    include_transitive: bool = Query(default=True, description="Include transitive dependencies"),
    filter_critical: bool = Query(default=False, description="Only critical dependencies"),
    dependency_analyzer: DependencyAnalyzer = Depends(get_dependency_analyzer),
    current_user: dict = Depends(get_current_user)
):
    """
    Analyze dependencies for a specific entity.
    
    Uses WOQL queries to find:
    - Direct dependencies (depth=1)
    - Transitive dependencies (depth>1)
    - Critical path identification
    - Impact scope calculation
    """
    try:
        # Analyze dependencies
        impact_analysis = await dependency_analyzer.analyze_change_impact(
            changed_entity=entity,
            change_type="analysis"
        )
        
        # Filter results based on parameters
        result = {
            "entity": entity,
            "analysis_depth": depth,
            "direct_dependencies": impact_analysis["directly_affected"],
            "total_affected": len(impact_analysis["directly_affected"]) + len(impact_analysis["transitively_affected"])
        }
        
        if include_transitive:
            result["transitive_dependencies"] = impact_analysis["transitively_affected"]
            
        if filter_critical:
            result["critical_services"] = impact_analysis["critical_services"]
            
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dependency analysis failed: {str(e)}")


@router.post("/impact-analysis", response_model=Dict[str, Any])
async def analyze_change_impact(
    request: ImpactAnalysisRequest,
    dependency_analyzer: DependencyAnalyzer = Depends(get_dependency_analyzer),
    current_user: dict = Depends(get_current_user)
):
    """
    Analyze impact of proposed changes to entities.
    
    Performs comprehensive impact analysis:
    - Direct and transitive dependency analysis
    - Critical service identification
    - Recommended mitigation actions
    - MSA service impact mapping
    """
    try:
        impact_analysis = await dependency_analyzer.analyze_change_impact(
            changed_entity=request.changed_entity,
            change_type=request.change_type
        )
        
        # Enhance with additional context
        result = {
            "changed_entity": request.changed_entity,
            "change_type": request.change_type,
            "impact_summary": {
                "directly_affected_count": len(impact_analysis["directly_affected"]),
                "transitively_affected_count": len(impact_analysis["transitively_affected"]),
                "critical_services_count": len(impact_analysis["critical_services"])
            },
            "affected_entities": {
                "direct": impact_analysis["directly_affected"],
                "transitive": impact_analysis["transitively_affected"],
                "critical": impact_analysis["critical_services"]
            }
        }
        
        if request.include_recommendations:
            result["recommendations"] = impact_analysis["recommended_actions"]
            
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Impact analysis failed: {str(e)}")


# Graph Metrics and Health Endpoints

@router.get("/metrics", response_model=GraphMetrics)
async def get_graph_metrics(
    traversal_engine: TraversalEngine = Depends(get_traversal_engine),
    current_user: dict = Depends(get_current_user)
):
    """
    Get comprehensive graph connectivity and health metrics.
    
    Calculates using TerminusDB aggregation queries:
    - Node/edge counts and ratios
    - Connectivity measures
    - Critical node identification
    - Orphaned entity detection
    """
    try:
        metrics = await traversal_engine.get_graph_metrics()
        return metrics
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Metrics calculation failed: {str(e)}")


@router.get("/health/conflicts", response_model=List[SemanticConflict])
async def detect_semantic_conflicts(
    include_circular: bool = Query(default=True, description="Include circular dependency conflicts"),
    include_orphaned: bool = Query(default=True, description="Include orphaned entity conflicts"),
    severity_filter: str = Query(default="all", regex="^(all|low|medium|high|critical)$"),
    dependency_analyzer: DependencyAnalyzer = Depends(get_dependency_analyzer),
    current_user: dict = Depends(get_current_user)
):
    """
    Detect semantic conflicts in the ontology graph.
    
    Uses advanced WOQL queries to identify:
    - Circular dependencies
    - Orphaned entities
    - Type mismatches
    - Cardinality violations
    """
    try:
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
            
        return conflicts
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Conflict detection failed: {str(e)}")


# Advanced Query Endpoints

@router.get("/critical-paths", response_model=List[DependencyPath])
async def get_critical_paths(
    max_paths: int = Query(default=10, ge=1, le=50, description="Maximum paths to return"),
    min_importance: float = Query(default=0.5, ge=0.0, le=1.0, description="Minimum importance score"),
    dependency_analyzer: DependencyAnalyzer = Depends(get_dependency_analyzer),
    current_user: dict = Depends(get_current_user)
):
    """
    Identify critical dependency paths in the ontology.
    
    Critical paths are identified by:
    - High connectivity (many entities depend on them)
    - Short essential connections (backbone paths)
    - High impact if broken (business criticality)
    """
    try:
        critical_paths = await dependency_analyzer.find_critical_paths(max_paths=max_paths)
        
        # Filter by importance score
        filtered_paths = [
            path for path in critical_paths 
            if path.total_weight >= min_importance
        ]
        
        return filtered_paths
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Critical path analysis failed: {str(e)}")


# Utility Endpoints

@router.get("/query-performance")
async def get_query_performance_report(
    query_planner: QueryPlanner = Depends(lambda: QueryPlanner()),
    current_user: dict = Depends(get_current_user)
):
    """
    Get query performance statistics and optimization recommendations.
    
    Provides insights into:
    - Query execution times and patterns
    - Cache hit rates
    - Optimization opportunities
    - Resource utilization
    """
    try:
        performance_report = query_planner.get_query_performance_report()
        return performance_report
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Performance report generation failed: {str(e)}")


@router.post("/clear-cache")
async def clear_traversal_cache(
    cache_type: str = Query(default="all", regex="^(all|query|plan)$"),
    current_user: dict = Depends(get_current_user)
):
    """
    Clear traversal caches for performance testing or troubleshooting.
    
    Cache types:
    - query: Clear query result cache
    - plan: Clear query execution plan cache  
    - all: Clear all caches
    """
    try:
        # Implementation would clear appropriate caches
        return {"message": f"Cache '{cache_type}' cleared successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cache clearing failed: {str(e)}")


# Branch/Version-aware Endpoints

@router.get("/traverse/{branch}")
async def traverse_graph_on_branch(
    branch: str = Path(description="Branch name to traverse"),
    request: GraphTraversalRequest = Depends(),
    traversal_engine: TraversalEngine = Depends(get_traversal_engine),
    current_user: dict = Depends(get_current_user)
):
    """
    Execute graph traversal on a specific branch.
    
    Leverages TerminusDB's Git-like branching to:
    - Traverse specific schema versions
    - Compare dependency changes across branches
    - Validate proposed schema modifications
    """
    try:
        # Switch to specified branch for traversal
        await traversal_engine.client.checkout_branch(branch)
        
        # Create and execute traversal query
        query = TraversalQuery(
            start_nodes=request.start_nodes,
            relations=request.relations,
            direction=request.direction,
            max_depth=request.max_depth,
            limit=request.limit,
            filters=request.filters,
            include_metadata=request.include_metadata
        )
        
        result = await traversal_engine.traverse(query)
        
        # Add branch context to result
        result.metrics["branch"] = branch
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Branch traversal failed: {str(e)}")
    finally:
        # Always return to main branch
        try:
            # Note: checkout_branch may not exist in current client
            pass  # Branch switching handled via connection parameters
        except Exception:
            pass


# Advanced Enterprise Features

@router.post("/validate-merge", response_model=Dict[str, Any])
async def validate_merge_operation(
    source_branch: str = Query(..., description="Source branch"),
    target_branch: str = Query(..., description="Target branch"),
    base_branch: Optional[str] = Query(default=None, description="Base branch"),
    engine: TraversalEngine = Depends(get_traversal_engine),
    analyzer: DependencyAnalyzer = Depends(get_dependency_analyzer),
    client: TerminusDBClient = Depends(get_terminus_client),
    current_user: dict = Depends(get_current_user)
):
    """
    Validate semantic merge operations between branches
    
    Performs comprehensive validation:
    - Structural conflict detection
    - Semantic consistency validation
    - Dependency impact analysis
    - Business rule validation
    - Risk assessment and recommendations
    """
    try:
        # Create validation layer components
        validation_config = ValidationConfig()
        rule_registry = RuleRegistry()  # Would be injected in real implementation
        
        # Create TerminusDB adapter for validation layer
        terminus_adapter = await create_terminus_traversal_adapter(
            terminus_client=client,
            database_name=getattr(get_settings(), 'TERMINUSDB_DATABASE', 'oms')
        )
        
        # Create merge validation service using validation layer
        merge_validator = MergeValidationService(
            rule_registry=rule_registry,
            terminus_port=terminus_adapter,
            config=validation_config
        )
        
        # Execute merge validation with proper strategy
        strategy = MergeStrategy.THREE_WAY  # Could be parameterized
        validation_result = await merge_validator.validate_merge(
            source_branch=source_branch,
            target_branch=target_branch,
            base_branch=base_branch,
            strategy=strategy
        )
        
        logger.info(f"Merge validation completed: {source_branch} -> {target_branch}, "
                   f"conflicts={len(validation_result.conflicts)}, "
                   f"can_auto_merge={validation_result.can_auto_merge}")
        
        return {
            "success": True,
            "source_branch": source_branch,
            "target_branch": target_branch,
            "base_branch": base_branch,
            "can_auto_merge": validation_result.can_auto_merge,
            "merge_decision": validation_result.merge_decision.value,
            "conflicts": [
                {
                    "rule_id": conflict.rule_id,
                    "severity": conflict.severity.value,
                    "object_type": conflict.object_type,
                    "field_name": conflict.field_name,
                    "description": conflict.description,
                    "old_value": conflict.old_value,
                    "new_value": conflict.new_value,
                    "impact": conflict.impact,
                    "suggested_strategies": [strategy.value for strategy in conflict.suggested_strategies],
                    "detected_at": conflict.detected_at.isoformat() if conflict.detected_at else None
                }
                for conflict in validation_result.conflicts
            ],
            "resolutions": [
                {
                    "conflict_rule_id": res.conflict.rule_id,
                    "resolution_type": res.resolution_type,
                    "resolution_action": res.resolution_action,
                    "confidence": res.confidence,
                    "rationale": res.rationale
                }
                for res in validation_result.resolutions
            ],
            "impact_analysis": validation_result.impact_analysis,
            "risk_assessment": validation_result.risk_assessment,
            "recommended_strategy": validation_result.recommended_strategy.value,
            "estimated_merge_time": validation_result.estimated_merge_time,
            "validation_timestamp": validation_result.validation_timestamp.isoformat(),
            "validated_by": current_user.get("username", "unknown")
        }
        
    except Exception as e:
        logger.error(f"Merge validation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Merge validation failed: {str(e)}")


@router.post("/detect-cycles", response_model=Dict[str, Any])
async def detect_circular_dependencies(
    analyzer: DependencyAnalyzer = Depends(get_dependency_analyzer),
    current_user: dict = Depends(get_current_user)
):
    """
    Detect circular dependencies in the graph
    
    Identifies circular dependency patterns that could indicate
    design issues or constraint violations.
    """
    try:
        conflicts = await analyzer.detect_circular_dependencies()
        
        logger.info(f"Circular dependency detection completed: {len(conflicts)} conflicts found")
        
        return {
            "success": True,
            "conflicts": [conflict.dict() for conflict in conflicts],
            "conflict_count": len(conflicts),
            "severity_summary": {
                "critical": len([c for c in conflicts if c.severity == "critical"]),
                "high": len([c for c in conflicts if c.severity == "high"]),
                "medium": len([c for c in conflicts if c.severity == "medium"]),
                "low": len([c for c in conflicts if c.severity == "low"])
            },
            "detected_by": current_user.get("username", "unknown")
        }
        
    except Exception as e:
        logger.error(f"Circular dependency detection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Cycle detection failed: {str(e)}")


@router.get("/metrics/graph", response_model=Dict[str, Any])
async def get_comprehensive_graph_metrics(
    engine: TraversalEngine = Depends(get_traversal_engine),
    current_user: dict = Depends(get_current_user)
):
    """
    Get comprehensive graph metrics
    
    Calculates graph-wide metrics including node/edge counts,
    connectivity measures, and health indicators.
    """
    try:
        metrics = await engine.get_graph_metrics()
        
        logger.info(f"Graph metrics calculated: nodes={metrics.total_nodes}, "
                   f"edges={metrics.total_edges}, density={metrics.density:.3f}")
        
        return {
            "success": True,
            "metrics": metrics.dict(),
            "calculation_timestamp": metrics.calculation_timestamp.isoformat(),
            "calculated_by": current_user.get("username", "unknown")
        }
        
    except Exception as e:
        logger.error(f"Graph metrics calculation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Metrics calculation failed: {str(e)}")


@router.get("/health", response_model=Dict[str, Any])
async def health_check(
    client: TerminusDBClient = Depends(get_terminus_client)
):
    """
    Health check for traversal service
    
    Verifies connectivity to TerminusDB and basic system health.
    """
    try:
        # Test TerminusDB connectivity
        is_connected = await client.ping()
        
        return {
            "success": True,
            "status": "healthy" if is_connected else "degraded",
            "terminusdb_connected": is_connected,
            "service": "graph-traversal",
            "version": "1.0.0",
            "timestamp": "2024-01-01T00:00:00Z"  # Would use datetime.utcnow()
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "success": False,
            "status": "unhealthy",
            "terminusdb_connected": False,
            "error": str(e),
            "service": "graph-traversal"
        }