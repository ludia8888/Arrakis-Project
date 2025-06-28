"""
Core Lock Manager
Handles the fundamental lock acquisition and release operations
"""
import asyncio
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from models.branch_state import (
    BranchLock, LockType, LockScope
)
from utils.logger import get_logger

logger = get_logger(__name__)


class LockConflictError(Exception):
    """Raised when a lock cannot be acquired due to conflicts"""
    pass


class LockManagerCore:
    """
    Core lock management functionality
    Handles lock acquisition, release, and conflict detection
    """
    
    def __init__(self):
        # In-memory lock storage
        self._active_locks: Dict[str, BranchLock] = {}
        
        # Lock timeout settings
        self.default_lock_timeout = timedelta(hours=2)
        self.indexing_lock_timeout = timedelta(hours=4)
        self.maintenance_lock_timeout = timedelta(hours=1)
    
    async def acquire_lock(
        self,
        branch_name: str,
        lock_type: LockType,
        locked_by: str,
        lock_scope: LockScope = LockScope.BRANCH,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        reason: str = "Lock acquired",
        timeout: Optional[timedelta] = None,
        enable_heartbeat: bool = True,
        heartbeat_interval: int = 60,
        existing_locks: List[BranchLock] = None
    ) -> BranchLock:
        """
        Acquire a lock on a branch or resource
        
        Returns:
            BranchLock object if successful
            
        Raises:
            LockConflictError: If lock cannot be acquired
        """
        lock_id = str(uuid4())
        
        # Determine timeout
        if timeout is None:
            timeout = self._get_default_timeout(lock_type)
        
        expires_at = datetime.now(timezone.utc) + timeout
        
        # Create lock object with TTL & Heartbeat support
        lock = BranchLock(
            id=lock_id,
            branch_name=branch_name,
            lock_type=lock_type,
            lock_scope=lock_scope,
            resource_type=resource_type,
            resource_id=resource_id,
            locked_by=locked_by,
            expires_at=expires_at,
            reason=reason,
            heartbeat_interval=heartbeat_interval if enable_heartbeat else 0,
            last_heartbeat=datetime.now(timezone.utc) if enable_heartbeat else None,
            heartbeat_source=locked_by if enable_heartbeat else None,
            auto_release_enabled=True
        )
        
        # Check for conflicts with existing locks
        if existing_locks:
            self._check_lock_conflicts(lock, existing_locks)
        
        # Add to active locks
        self._active_locks[lock_id] = lock
        
        logger.info(
            f"Lock acquired: {lock_id} on {branch_name} by {locked_by} "
            f"({lock_type.value}, expires: {expires_at}, heartbeat: {enable_heartbeat})"
        )
        
        return lock
    
    def release_lock(self, lock_id: str, released_by: Optional[str] = None) -> Optional[BranchLock]:
        """
        Release a lock
        
        Returns:
            Released lock if found, None otherwise
        """
        lock = self._active_locks.get(lock_id)
        if not lock:
            logger.warning(f"Attempted to release non-existent lock: {lock_id}")
            return None
        
        # Mark lock as released
        lock.is_active = False
        lock.released_at = datetime.now(timezone.utc)
        lock.released_by = released_by or "system"
        
        # Remove from active locks
        del self._active_locks[lock_id]
        
        logger.info(f"Lock released: {lock_id} by {released_by}")
        return lock
    
    def get_lock(self, lock_id: str) -> Optional[BranchLock]:
        """Get a specific lock by ID"""
        return self._active_locks.get(lock_id)
    
    def get_active_locks(self, branch_name: Optional[str] = None) -> List[BranchLock]:
        """Get all active locks, optionally filtered by branch"""
        locks = list(self._active_locks.values())
        
        if branch_name:
            locks = [lock for lock in locks if lock.branch_name == branch_name]
        
        return locks
    
    def _check_lock_conflicts(self, new_lock: BranchLock, existing_locks: List[BranchLock]):
        """Check if a new lock conflicts with existing locks"""
        for existing_lock in existing_locks:
            if not existing_lock.is_active:
                continue
            
            if self._locks_conflict(existing_lock, new_lock):
                raise LockConflictError(
                    f"Lock conflict: {new_lock.lock_type.value} lock on "
                    f"{new_lock.branch_name} conflicts with existing "
                    f"{existing_lock.lock_type.value} lock {existing_lock.id}"
                )
    
    def _locks_conflict(self, lock1: BranchLock, lock2: BranchLock) -> bool:
        """Check if two locks conflict"""
        # Same branch is required for conflict
        if lock1.branch_name != lock2.branch_name:
            return False
        
        # Branch-level locks conflict with everything
        if (lock1.lock_scope == LockScope.BRANCH or 
            lock2.lock_scope == LockScope.BRANCH):
            return True
        
        # Resource type level conflicts
        if (lock1.lock_scope == LockScope.RESOURCE_TYPE and
            lock2.lock_scope == LockScope.RESOURCE_TYPE and
            lock1.resource_type == lock2.resource_type):
            return True
        
        # Specific resource conflicts
        if (lock1.lock_scope == LockScope.RESOURCE and
            lock2.lock_scope == LockScope.RESOURCE and
            lock1.resource_type == lock2.resource_type and
            lock1.resource_id == lock2.resource_id):
            return True
        
        return False
    
    def _get_default_timeout(self, lock_type: LockType) -> timedelta:
        """Get default timeout for lock type"""
        timeouts = {
            LockType.INDEXING: self.indexing_lock_timeout,
            LockType.MAINTENANCE: self.maintenance_lock_timeout,
            LockType.MIGRATION: timedelta(hours=6),
            LockType.BACKUP: timedelta(hours=2),
            LockType.MANUAL: timedelta(hours=24)
        }
        return timeouts.get(lock_type, self.default_lock_timeout)
    
    def check_write_permission(
        self,
        branch_state,
        action: str,
        resource_type: Optional[str] = None
    ) -> tuple[bool, str]:
        """
        Check if a write operation is allowed based on current locks
        
        Returns:
            Tuple of (allowed, reason_if_not)
        """
        # This is a simplified version - the full logic would check
        # the branch state and active locks
        return branch_state.can_perform_action(action, resource_type)