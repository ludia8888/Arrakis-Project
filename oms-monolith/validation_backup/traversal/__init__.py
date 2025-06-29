"""
TerminusDB Native Graph Traversal Engine

Enterprise-grade semantic graph traversal service for OMS (Ontology Management System).
Leverages TerminusDB's native WOQL capabilities for:
- Domain dependency analysis
- Semantic merge validation  
- Multi-hop ontology reasoning
- MSA interconnection mapping
"""

from .traversal_engine import TraversalEngine
from .dependency_analyzer import DependencyAnalyzer
from .semantic_validator import SemanticValidator
from .query_planner import QueryPlanner
from .models import (
    TraversalQuery,
    TraversalResult,
    DependencyPath,
    SemanticConflict,
    GraphMetrics
)

__all__ = [
    'TraversalEngine',
    'DependencyAnalyzer', 
    'SemanticValidator',
    'QueryPlanner',
    'TraversalQuery',
    'TraversalResult',
    'DependencyPath',
    'SemanticConflict',
    'GraphMetrics'
]