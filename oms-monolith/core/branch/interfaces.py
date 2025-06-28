"""
Branch Service Interfaces
Defines abstract interfaces for branch operations
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime

from core.branch.models import ChangeProposal, BranchDiff, MergeResult


class IBranchService(ABC):
    """Abstract interface for branch operations"""
    
    @abstractmethod
    async def create_branch(self, parent: str, name: str, description: Optional[str] = None) -> str:
        """Create a new branch from parent"""
        pass
    
    @abstractmethod
    async def delete_branch(self, branch_name: str) -> bool:
        """Delete a branch"""
        pass
    
    @abstractmethod
    async def list_branches(self) -> List[Dict[str, Any]]:
        """List all branches"""
        pass
    
    @abstractmethod
    async def get_branch_info(self, branch_name: str) -> Dict[str, Any]:
        """Get branch information"""
        pass
    
    @abstractmethod
    async def merge_branches(
        self, 
        source: str, 
        target: str, 
        author: str,
        message: Optional[str] = None
    ) -> MergeResult:
        """Merge source branch into target branch"""
        pass
    
    @abstractmethod
    async def get_diff(self, from_ref: str, to_ref: str) -> BranchDiff:
        """Get differences between two references"""
        pass


class ILockService(ABC):
    """Abstract interface for lock operations"""
    
    @abstractmethod
    async def acquire_lock(
        self, 
        resource: str, 
        lock_type: str,
        timeout: Optional[int] = None
    ) -> Any:
        """Acquire a lock on resource"""
        pass
    
    @abstractmethod
    async def release_lock(self, lock_id: str) -> bool:
        """Release a lock"""
        pass
    
    @abstractmethod
    async def is_locked(self, resource: str) -> bool:
        """Check if resource is locked"""
        pass


class IMergeEngine(ABC):
    """Abstract interface for merge operations"""
    
    @abstractmethod
    async def merge(
        self,
        source: str,
        target: str,
        author: str,
        message: Optional[str] = None,
        strategy: Any = None
    ) -> Any:
        """Execute merge with given strategy"""
        pass
    
    @abstractmethod
    async def detect_conflicts(
        self,
        source: str,
        target: str
    ) -> List[Dict[str, Any]]:
        """Detect conflicts between branches"""
        pass