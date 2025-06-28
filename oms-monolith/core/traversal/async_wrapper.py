"""
Async Wrapper for Traversal Module

Provides async compatibility for traversal module components to ensure
consistent async patterns throughout the system.

This wrapper addresses the sync/async inconsistency identified in the analysis
while maintaining backward compatibility with existing sync usage.
"""

import asyncio
import logging
from typing import List, Dict, Optional, Any, Union
from functools import wraps

from core.traversal.traversal_engine import TraversalEngine
from core.traversal.dependency_analyzer import DependencyAnalyzer  
from core.traversal.semantic_validator import SemanticValidator
from core.traversal.models import (
    TraversalQuery, TraversalResult, DependencyPath, 
    SemanticConflict, GraphMetrics
)
from core.validation.config import get_validation_config
from database.clients.terminus_db import TerminusDBClient

logger = logging.getLogger(__name__)


def ensure_async(func):
    """
    Decorator to ensure a function runs in async context.
    
    Handles both sync and async functions transparently.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            # Run sync function in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
    return wrapper


class AsyncTraversalEngine:
    """
    Async wrapper for TraversalEngine.
    
    Provides consistent async interface for all traversal operations
    while maintaining compatibility with the existing sync implementation.
    """
    
    def __init__(self, traversal_engine: TraversalEngine):
        self.engine = traversal_engine
        self.config = get_validation_config()
    
    async def traverse(self, query: TraversalQuery) -> TraversalResult:
        """Async wrapper for traverse operation"""
        # TraversalEngine.traverse is already async, so call directly
        return await self.engine.traverse(query)
    
    async def find_dependency_paths(
        self, 
        start_node: str, 
        end_node: str, 
        max_depth: int = 5
    ) -> List[DependencyPath]:
        """Async wrapper for dependency path finding"""
        # TraversalEngine.find_dependency_paths is already async
        return await self.engine.find_dependency_paths(start_node, end_node, max_depth)
    
    async def get_graph_metrics(self) -> GraphMetrics:
        """Async wrapper for graph metrics calculation"""
        # TraversalEngine.get_graph_metrics is already async
        return await self.engine.get_graph_metrics()
    
    @classmethod
    async def create(
        cls,
        terminus_client: TerminusDBClient,
        database_name: str = "oms"
    ) -> "AsyncTraversalEngine":
        """Factory method to create async traversal engine"""
        config = get_validation_config()
        
        # Create sync traversal engine
        sync_engine = TraversalEngine(
            terminus_client=terminus_client,
            config=config,
            database_name=database_name
        )
        
        # Wrap in async interface
        return cls(sync_engine)


class AsyncDependencyAnalyzer:
    """
    Async wrapper for DependencyAnalyzer.
    
    Ensures all dependency analysis operations are properly async.
    """
    
    def __init__(self, dependency_analyzer: DependencyAnalyzer):
        self.analyzer = dependency_analyzer
        self.config = get_validation_config()
    
    async def analyze_change_impact(
        self, 
        changed_entity: str, 
        change_type: str = "modification"
    ) -> Dict[str, List[str]]:
        """Async wrapper for change impact analysis"""
        # DependencyAnalyzer.analyze_change_impact is already async
        return await self.analyzer.analyze_change_impact(changed_entity, change_type)
    
    async def detect_circular_dependencies(self) -> List[SemanticConflict]:
        """Async wrapper for circular dependency detection"""
        # DependencyAnalyzer.detect_circular_dependencies is already async
        return await self.analyzer.detect_circular_dependencies()
    
    async def find_critical_paths(self, max_paths: int = 10) -> List[DependencyPath]:
        """Async wrapper for critical path analysis"""
        # DependencyAnalyzer.find_critical_paths is already async
        return await self.analyzer.find_critical_paths(max_paths)
    
    async def analyze_orphaned_entities(self) -> List[SemanticConflict]:
        """Async wrapper for orphaned entity analysis"""
        # DependencyAnalyzer.analyze_orphaned_entities is already async
        return await self.analyzer.analyze_orphaned_entities()
    
    @classmethod
    async def create(
        cls,
        traversal_engine: TraversalEngine,
        terminus_client: TerminusDBClient,
        database_name: str = "oms"
    ) -> "AsyncDependencyAnalyzer":
        """Factory method to create async dependency analyzer"""
        config = get_validation_config()
        
        # Create sync dependency analyzer
        sync_analyzer = DependencyAnalyzer(
            traversal_engine=traversal_engine,
            terminus_client=terminus_client,
            config=config,
            database_name=database_name
        )
        
        return cls(sync_analyzer)


class AsyncSemanticValidator:
    """
    Async wrapper for SemanticValidator.
    
    Provides consistent async interface for semantic validation operations.
    """
    
    def __init__(self, semantic_validator: SemanticValidator):
        self.validator = semantic_validator
        self.config = get_validation_config()
    
    async def validate_merge_operation(
        self,
        source_branch: str,
        target_branch: str,
        base_branch: Optional[str] = None
    ) -> List[SemanticConflict]:
        """Async wrapper for merge validation"""
        # SemanticValidator.validate_merge_operation is already async
        return await self.validator.validate_merge_operation(
            source_branch, target_branch, base_branch
        )
    
    async def validate_schema_constraints(self) -> List[SemanticConflict]:
        """Async wrapper for schema constraint validation"""
        # SemanticValidator.validate_schema_constraints is already async
        return await self.validator.validate_schema_constraints()
    
    async def validate_semantic_consistency(self) -> List[SemanticConflict]:
        """Async wrapper for semantic consistency validation"""
        # SemanticValidator.validate_semantic_consistency is already async
        return await self.validator.validate_semantic_consistency()
    
    @classmethod
    async def create(
        cls,
        traversal_engine: TraversalEngine,
        dependency_analyzer: DependencyAnalyzer,
        terminus_client: TerminusDBClient
    ) -> "AsyncSemanticValidator":
        """Factory method to create async semantic validator"""
        config = get_validation_config()
        
        # Create sync semantic validator
        sync_validator = SemanticValidator(
            traversal_engine=traversal_engine,
            dependency_analyzer=dependency_analyzer,
            terminus_client=terminus_client,
            config=config
        )
        
        return cls(sync_validator)


class AsyncTraversalFacade:
    """
    Complete async facade for the traversal module.
    
    Provides a single entry point for all async traversal operations,
    ensuring consistent async patterns throughout the system.
    """
    
    def __init__(
        self,
        traversal_engine: AsyncTraversalEngine,
        dependency_analyzer: AsyncDependencyAnalyzer,
        semantic_validator: AsyncSemanticValidator
    ):
        self.traversal_engine = traversal_engine
        self.dependency_analyzer = dependency_analyzer
        self.semantic_validator = semantic_validator
        self.config = get_validation_config()
    
    # Delegate traversal operations
    async def traverse(self, query: TraversalQuery) -> TraversalResult:
        """Execute graph traversal"""
        return await self.traversal_engine.traverse(query)
    
    async def find_dependency_paths(
        self, 
        start_node: str, 
        end_node: str, 
        max_depth: int = 5
    ) -> List[DependencyPath]:
        """Find dependency paths between nodes"""
        return await self.traversal_engine.find_dependency_paths(
            start_node, end_node, max_depth
        )
    
    async def get_graph_metrics(self) -> GraphMetrics:
        """Get comprehensive graph metrics"""
        return await self.traversal_engine.get_graph_metrics()
    
    # Delegate dependency analysis operations
    async def analyze_change_impact(
        self, 
        changed_entity: str, 
        change_type: str = "modification"
    ) -> Dict[str, List[str]]:
        """Analyze impact of entity changes"""
        return await self.dependency_analyzer.analyze_change_impact(
            changed_entity, change_type
        )
    
    async def detect_circular_dependencies(self) -> List[SemanticConflict]:
        """Detect circular dependencies in the graph"""
        return await self.dependency_analyzer.detect_circular_dependencies()
    
    async def find_critical_paths(self, max_paths: int = 10) -> List[DependencyPath]:
        """Find critical dependency paths"""
        return await self.dependency_analyzer.find_critical_paths(max_paths)
    
    async def analyze_orphaned_entities(self) -> List[SemanticConflict]:
        """Analyze orphaned entities"""
        return await self.dependency_analyzer.analyze_orphaned_entities()
    
    # Delegate semantic validation operations
    async def validate_merge_operation(
        self,
        source_branch: str,
        target_branch: str,
        base_branch: Optional[str] = None
    ) -> List[SemanticConflict]:
        """Validate merge operations"""
        return await self.semantic_validator.validate_merge_operation(
            source_branch, target_branch, base_branch
        )
    
    async def validate_schema_constraints(self) -> List[SemanticConflict]:
        """Validate schema constraints"""
        return await self.semantic_validator.validate_schema_constraints()
    
    async def validate_semantic_consistency(self) -> List[SemanticConflict]:
        """Validate semantic consistency"""
        return await self.semantic_validator.validate_semantic_consistency()
    
    @classmethod
    async def create(
        cls,
        terminus_client: TerminusDBClient,
        database_name: str = "oms"
    ) -> "AsyncTraversalFacade":
        """
        Factory method to create complete async traversal facade.
        
        This is the recommended way to create async traversal components
        for consistent async patterns throughout the system.
        """
        config = get_validation_config()
        
        # Create sync components first
        sync_traversal_engine = TraversalEngine(
            terminus_client=terminus_client,
            config=config,
            database_name=database_name
        )
        
        sync_dependency_analyzer = DependencyAnalyzer(
            traversal_engine=sync_traversal_engine,
            terminus_client=terminus_client,
            config=config,
            database_name=database_name
        )
        
        sync_semantic_validator = SemanticValidator(
            traversal_engine=sync_traversal_engine,
            dependency_analyzer=sync_dependency_analyzer,
            terminus_client=terminus_client,
            config=config
        )
        
        # Wrap in async interfaces
        async_traversal_engine = AsyncTraversalEngine(sync_traversal_engine)
        async_dependency_analyzer = AsyncDependencyAnalyzer(sync_dependency_analyzer)
        async_semantic_validator = AsyncSemanticValidator(sync_semantic_validator)
        
        return cls(
            traversal_engine=async_traversal_engine,
            dependency_analyzer=async_dependency_analyzer,
            semantic_validator=async_semantic_validator
        )


# Factory functions for easy async access
async def create_async_traversal_facade(
    terminus_client: TerminusDBClient,
    database_name: str = "oms"
) -> AsyncTraversalFacade:
    """Convenience factory for creating async traversal facade"""
    return await AsyncTraversalFacade.create(terminus_client, database_name)


__all__ = [
    "AsyncTraversalEngine",
    "AsyncDependencyAnalyzer", 
    "AsyncSemanticValidator",
    "AsyncTraversalFacade",
    "create_async_traversal_facade",
    "ensure_async"
]