"""
DEPRECATED: This module is deprecated and will be removed.
Use core.merge.unified_engine instead for all merge strategies.

Advanced merge strategies are now integrated into UnifiedMergeEngine.
"""
import warnings
import logging
from typing import Dict
from datetime import datetime, timezone

from core.branch.models import ChangeProposal, MergeResult
from core.merge import get_unified_merge_engine
from database.clients.terminus_db import TerminusDBClient

warnings.warn(
    "core.branch.merge_strategies is deprecated. Use core.merge.unified_engine instead.",
    DeprecationWarning,
    stacklevel=2
)

logger = logging.getLogger(__name__)


class MergeStrategyImplementor:
    """
    DEPRECATED: Use UnifiedMergeEngine instead.
    
    This class now delegates to UnifiedMergeEngine for backward compatibility.
    """
    
    def __init__(self, tdb_client: TerminusDBClient):
        warnings.warn(
            "MergeStrategyImplementor is deprecated. Use UnifiedMergeEngine instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self.tdb = tdb_client
        self.unified_engine = get_unified_merge_engine()
        self.unified_engine.terminus = tdb_client
    
    async def perform_squash_merge(
        self,
        proposal: ChangeProposal,
        user: Dict[str, str]
    ) -> MergeResult:
        """Delegate to UnifiedMergeEngine"""
        logger.warning("Using deprecated MergeStrategyImplementor.perform_squash_merge")
        
        return await self.unified_engine.merge(
            source_branch=proposal.sourceBranch,
            target_branch=proposal.targetBranch,
            author=user.get("id", "system"),
            message=proposal.description,
            strategy="squash"
        )
    
    async def perform_rebase_merge(
        self,
        proposal: ChangeProposal,
        user: Dict[str, str]
    ) -> MergeResult:
        """Delegate to UnifiedMergeEngine"""
        logger.warning("Using deprecated MergeStrategyImplementor.perform_rebase_merge")
        
        return await self.unified_engine.merge(
            source_branch=proposal.sourceBranch,
            target_branch=proposal.targetBranch,
            author=user.get("id", "system"),
            message=proposal.description,
            strategy="rebase"
        )
    
    async def _collect_branch_changes(self, base_branch: str, source_branch: str):
        """Deprecated method - kept for compatibility"""
        warnings.warn(
            "_collect_branch_changes is deprecated and will be removed",
            DeprecationWarning,
            stacklevel=2
        )
        return []
    
    def _generate_squash_commit_message(self, proposal: ChangeProposal, changes) -> str:
        """Deprecated method - kept for compatibility"""
        return f"Squashed merge: {proposal.description}"