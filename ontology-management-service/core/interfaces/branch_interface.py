"""
Branch Service Interface
"""
from typing import Protocol, Optional, Dict, Any, List
from datetime import datetime

from models.branch_state import BranchState, BranchStateInfo


class IBranchService(Protocol):
 """Interface for branch management operations"""

 async def create_branch(
 self,
 branch_name: str,
 parent_branch: str,
 parent_commit: str,
 user_id: str,
 description: Optional[str] = None
 ) -> Dict[str, Any]:
 """Create a new branch"""
 ...

 async def get_branch_state(
 self,
 branch_name: str
 ) -> Optional[BranchState]:
 """Get current state of a branch"""
 ...

 async def list_branches(
 self,
 include_deleted: bool = False
 ) -> List[BranchStateInfo]:
 """List all branches"""
 ...

 async def merge_branches(
 self,
 source_branch: str,
 target_branch: str,
 user_id: str,
 merge_strategy: str = "auto"
 ) -> Dict[str, Any]:
 """Merge source branch into target branch"""
 ...

 async def delete_branch(
 self,
 branch_name: str,
 user_id: str,
 force: bool = False
 ) -> bool:
 """Delete a branch"""
 ...

 async def get_branch_history(
 self,
 branch_name: str,
 limit: int = 100
 ) -> List[Dict[str, Any]]:
 """Get commit history for a branch"""
 ...
