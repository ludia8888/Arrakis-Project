"""
Graph Traversal Models

Data models for TerminusDB-based graph traversal operations.
"""

from typing import List, Dict, Optional, Set, Union, Any
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime


class TraversalDirection(str, Enum):
    """Graph traversal direction"""
    OUTBOUND = "outbound"
    INBOUND = "inbound"
    BIDIRECTIONAL = "bidirectional"


class ConflictType(str, Enum):
    """Types of semantic conflicts in graph"""
    DANGLING_REFERENCE = "dangling_reference"
    CIRCULAR_DEPENDENCY = "circular_dependency"
    TYPE_MISMATCH = "type_mismatch"
    CARDINALITY_VIOLATION = "cardinality_violation"
    ORPHANED_NODE = "orphaned_node"


class TraversalQuery(BaseModel):
    """Query specification for graph traversal"""
    start_nodes: List[str] = Field(description="Starting node IDs")
    relations: List[str] = Field(description="Relation types to follow")
    direction: TraversalDirection = TraversalDirection.OUTBOUND
    max_depth: int = Field(default=5, ge=1, le=20)
    limit: Optional[int] = Field(default=None, ge=1)
    filters: Dict[str, Any] = Field(default_factory=dict)
    include_metadata: bool = True
    

class GraphNode(BaseModel):
    """Graph node representation"""
    id: str
    type: str
    label: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    depth: int = 0
    

class GraphEdge(BaseModel):
    """Graph edge representation"""
    source: str
    target: str
    relation: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    

class DependencyPath(BaseModel):
    """Path between nodes showing dependency chain"""
    start_node: str
    end_node: str
    path: List[str]
    relations: List[str]
    total_weight: float = 0.0
    is_critical: bool = False
    

class TraversalResult(BaseModel):
    """Result of graph traversal operation"""
    query_id: str
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    paths: List[DependencyPath]
    metrics: Dict[str, Any] = Field(default_factory=dict)
    execution_time_ms: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    

class SemanticConflict(BaseModel):
    """Detected semantic conflict in graph"""
    conflict_type: ConflictType
    severity: str = Field(pattern="^(low|medium|high|critical)$")
    affected_nodes: List[str]
    description: str
    suggested_resolution: Optional[str] = None
    impact_scope: List[str] = Field(default_factory=list)
    

class GraphMetrics(BaseModel):
    """Graph connectivity and health metrics"""
    total_nodes: int
    total_edges: int
    connected_components: int
    average_degree: float
    density: float
    clustering_coefficient: float
    longest_path: int
    critical_nodes: List[str] = Field(default_factory=list)
    orphaned_nodes: List[str] = Field(default_factory=list)
    

class MSAMapping(BaseModel):
    """Mapping between ontology entities and MSA services"""
    entity_type: str
    msa_service: str
    api_endpoint: str
    data_schema: Dict[str, Any]
    dependency_weight: float = 1.0
    is_authoritative: bool = True