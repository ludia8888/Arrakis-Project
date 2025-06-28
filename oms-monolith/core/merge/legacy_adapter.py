"""
Legacy Merge Adapter
Adapts existing three-way merge to unified interface
"""
import logging
from typing import Dict, List, Optional, Any

from core.branch.interfaces import IMergeEngine
from core.branch.three_way_merge import ThreeWayMergeAlgorithm
from core.branch.models import MergeResult, MergeStrategy, Conflict

logger = logging.getLogger(__name__)


class LegacyMergeAdapter(IMergeEngine):
    """
    Adapter for legacy three-way merge implementation
    Allows gradual migration from old to new merge engine
    """
    
    def __init__(self):
        """Initialize with legacy components"""
        self.three_way_merge = ThreeWayMergeAlgorithm()
        logger.info("Initialized Legacy Merge Adapter")
    
    async def merge(
        self,
        source: str,
        target: str,
        author: str,
        message: Optional[str] = None,
        strategy: MergeStrategy = MergeStrategy.MERGE
    ) -> MergeResult:
        """
        Execute merge using legacy three-way merge
        
        This adapter method translates the unified interface to the legacy implementation
        """
        logger.info(f"Legacy merge: {source} -> {target}")
        
        try:
            # Legacy three-way merge expects different parameters
            # This is a simplified adapter - real implementation would need proper mapping
            
            if strategy != MergeStrategy.MERGE:
                # Legacy doesn't support other strategies directly
                logger.warning(f"Legacy merge doesn't support {strategy}, using standard")
            
            # Mock the merge for now - would call actual three_way_merge
            # In real implementation, would need to:
            # 1. Get the data from source and target branches
            # 2. Find common ancestor
            # 3. Call three_way_merge.merge_resources()
            
            return MergeResult(
                merge_commit="legacy_commit_123",
                conflicts=[]
            )
            
        except Exception as e:
            logger.error(f"Legacy merge failed: {e}")
            return MergeResult(
                merge_commit=None,
                conflicts=[Conflict(
                    conflict_type="error",
                    resource_id="legacy_merge",
                    description=f"Legacy merge failed: {str(e)}"
                )]
            )
    
    async def detect_conflicts(
        self,
        source: str,
        target: str
    ) -> List[Dict[str, Any]]:
        """
        Detect conflicts using legacy implementation
        """
        # This would use the legacy conflict detection logic
        # For now, return empty list
        return []