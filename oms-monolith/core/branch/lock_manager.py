"""
Branch Lock Manager - Orchestrator
Coordinates lock management across core, state, heartbeat, and cleanup services
"""
import asyncio
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone, timedelta

from models.branch_state import (
    BranchState, BranchLock, LockType, LockScope
)
from core.branch.lock_manager_core import LockManagerCore, LockConflictError
from core.branch.lock_state_manager import LockStateManager, InvalidStateTransitionError
from core.branch.lock_heartbeat_service import LockHeartbeatService
from core.branch.lock_cleanup_service import LockCleanupService
from utils.logger import get_logger

logger = get_logger(__name__)


class BranchLockManager:
    """
    Orchestrates branch lock management across multiple services
    Provides a unified interface for lock operations
    """
    
    def __init__(self, cache_service=None, db_service=None):
        # Initialize component services
        self.core = LockManagerCore()
        self.state_manager = LockStateManager(cache_service, db_service)
        self.heartbeat_service = LockHeartbeatService(db_service)
        self.cleanup_service = LockCleanupService()
        
        # Register cleanup callback
        self.cleanup_service.add_cleanup_callback(self._perform_cleanup)
    
    async def initialize(self):
        """Initialize all lock management services"""
        await self.heartbeat_service.start()
        await self.cleanup_service.start()
        logger.info("Branch Lock Manager initialized with all services")
    
    async def shutdown(self):
        """Shutdown all lock management services"""
        await self.heartbeat_service.stop()
        await self.cleanup_service.stop()
        logger.info("Branch Lock Manager shutdown complete")
    
    # ==================== Core Lock Operations ====================
    
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
        heartbeat_interval: int = 60
    ) -> str:
        """
        Acquire a lock on a branch or resource
        
        Returns:
            Lock ID if successful
            
        Raises:
            LockConflictError: If lock cannot be acquired
        """
        # Get current branch state
        branch_state = await self.state_manager.get_branch_state(branch_name)
        
        # Create lock through core service
        lock = await self.core.acquire_lock(
            branch_name=branch_name,
            lock_type=lock_type,
            locked_by=locked_by,
            lock_scope=lock_scope,
            resource_type=resource_type,
            resource_id=resource_id,
            reason=reason,
            timeout=timeout,
            enable_heartbeat=enable_heartbeat,
            heartbeat_interval=heartbeat_interval,
            existing_locks=branch_state.active_locks
        )
        
        # Update branch state
        await self.state_manager.add_lock_to_state(branch_name, lock)
        
        # Update branch state if needed
        if lock_type == LockType.INDEXING and lock_scope == LockScope.BRANCH:
            await self.state_manager.transition_state(
                branch_state,
                BranchState.LOCKED_FOR_WRITE,
                locked_by,
                f"Indexing lock acquired: {reason}"
            )
        
        return lock.id
    
    async def release_lock(self, lock_id: str, released_by: Optional[str] = None) -> bool:
        """
        Release a lock
        
        Returns:
            True if lock was released, False if not found
        """
        # Get lock from core
        lock = self.core.get_lock(lock_id)
        if not lock:
            return False
        
        # Release through core service
        released_lock = self.core.release_lock(lock_id, released_by)
        if not released_lock:
            return False
        
        # Update branch state
        branch_state = await self.state_manager.remove_lock_from_state(
            released_lock.branch_name, lock_id
        )
        
        # Check if we should transition state
        if (released_lock.lock_type == LockType.INDEXING and 
            released_lock.lock_scope == LockScope.BRANCH and
            not self._has_active_indexing_locks(branch_state)):
            
            # Transition to READY state
            await self.state_manager.transition_state(
                branch_state,
                BranchState.READY,
                released_by or "system",
                "Indexing completed, ready for merge"
            )
        
        return True
    
    # ==================== State Management ====================
    
    async def get_branch_state(self, branch_name: str):
        """Get current state of a branch"""
        return await self.state_manager.get_branch_state(branch_name)
    
    async def set_branch_state(
        self,
        branch_name: str,
        new_state: BranchState,
        changed_by: str = "system",
        reason: str = "State change"
    ) -> bool:
        """Set branch state directly"""
        try:
            await self.state_manager.set_branch_state(
                branch_name, new_state, changed_by, reason
            )
            
            # Special handling for ERROR state - release all locks
            if new_state == BranchState.ERROR:
                await self._release_all_branch_locks(branch_name, "error_state")
            
            return True
        except InvalidStateTransitionError as e:
            logger.error(f"Invalid state transition: {e}")
            return False
    
    # ==================== Heartbeat Operations ====================
    
    async def send_heartbeat(
        self,
        lock_id: str,
        service_name: str,
        status: str = "healthy",
        progress_info: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send a heartbeat for a lock"""
        lock = self.core.get_lock(lock_id)
        if not lock:
            return False
        
        return await self.heartbeat_service.send_heartbeat(
            lock, service_name, status, progress_info
        )
    
    async def get_lock_health_status(self, lock_id: str) -> Optional[Dict[str, Any]]:
        """Get health status and heartbeat information for a lock"""
        lock = self.core.get_lock(lock_id)
        if not lock:
            return None
        
        return await self.heartbeat_service.get_lock_health_status(lock)
    
    # ==================== Query Operations ====================
    
    async def list_active_locks(self, branch_name: Optional[str] = None) -> List[BranchLock]:
        """List all active locks, optionally filtered by branch"""
        return self.core.get_active_locks(branch_name)
    
    async def get_lock_status(self, lock_id: str) -> Optional[BranchLock]:
        """Get status of a specific lock"""
        return self.core.get_lock(lock_id)
    
    async def check_write_permission(
        self,
        branch_name: str,
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None
    ) -> tuple[bool, str]:
        """Check if a write operation is allowed"""
        branch_state = await self.state_manager.get_branch_state(branch_name)
        return self.core.check_write_permission(branch_state, action, resource_type)
    
    # ==================== Specialized Lock Operations ====================
    
    async def lock_for_indexing(
        self,
        branch_name: str,
        locked_by: str = "funnel-service",
        reason: str = "Data indexing in progress",
        resource_types: Optional[List[str]] = None,
        force_branch_lock: bool = False
    ) -> List[str]:
        """Lock resources for Funnel Service indexing"""
        lock_ids = []
        
        if force_branch_lock:
            # Full branch lock
            logger.warning(f"Full branch lock requested for {branch_name}")
            lock_id = await self.acquire_lock(
                branch_name=branch_name,
                lock_type=LockType.INDEXING,
                locked_by=locked_by,
                lock_scope=LockScope.BRANCH,
                reason=f"FORCE BRANCH LOCK: {reason}",
                timeout=self.core.indexing_lock_timeout
            )
            lock_ids.append(lock_id)
        else:
            # Resource-type specific locks
            if not resource_types:
                resource_types = ["object_type", "link_type", "action_type"]
            
            for resource_type in resource_types:
                try:
                    lock_id = await self.acquire_lock(
                        branch_name=branch_name,
                        lock_type=LockType.INDEXING,
                        locked_by=locked_by,
                        lock_scope=LockScope.RESOURCE_TYPE,
                        resource_type=resource_type,
                        reason=f"Indexing {resource_type}: {reason}",
                        timeout=self.core.indexing_lock_timeout,
                        enable_heartbeat=True,
                        heartbeat_interval=120
                    )
                    lock_ids.append(lock_id)
                except LockConflictError as e:
                    logger.warning(f"Could not lock {resource_type}: {e}")
        
        # Update indexing metadata
        await self.state_manager.update_indexing_metadata(
            branch_name, locked_by, started=True
        )
        
        return lock_ids
    
    async def complete_indexing(
        self,
        branch_name: str,
        completed_by: str = "funnel-service",
        resource_types: Optional[List[str]] = None
    ) -> bool:
        """Mark indexing as complete and release locks"""
        branch_state = await self.state_manager.get_branch_state(branch_name)
        
        # Find indexing locks to release
        indexing_locks = [
            lock for lock in branch_state.active_locks
            if lock.lock_type == LockType.INDEXING and lock.is_active
        ]
        
        if resource_types:
            indexing_locks = [
                lock for lock in indexing_locks
                if lock.resource_type in resource_types
            ]
        
        # Release the locks
        released_count = 0
        for lock in indexing_locks:
            if await self.release_lock(lock.id, completed_by):
                released_count += 1
        
        # Update indexing metadata
        await self.state_manager.update_indexing_metadata(
            branch_name, completed_by, started=False
        )
        
        return released_count > 0
    
    async def force_unlock(
        self,
        branch_name: str,
        admin_user: str,
        reason: str = "Administrative unlock"
    ) -> int:
        """Force unlock all locks on a branch (admin only)"""
        return await self.cleanup_service.force_cleanup_branch(
            branch_name,
            self.core.get_active_locks(branch_name),
            self.release_lock,
            reason
        )
    
    # ==================== Extension Operations ====================
    
    async def extend_lock_ttl(
        self,
        lock_id: str,
        extension_duration: timedelta,
        extended_by: str,
        reason: str = "TTL extension"
    ) -> bool:
        """Extend the TTL of an existing lock"""
        lock = self.core.get_lock(lock_id)
        if not lock or not lock.is_active:
            return False
        
        old_expires_at = lock.expires_at
        if lock.expires_at:
            lock.expires_at = lock.expires_at + extension_duration
        else:
            lock.expires_at = datetime.now(timezone.utc) + extension_duration
        
        # Update branch state
        branch_state = await self.state_manager.get_branch_state(lock.branch_name)
        await self.state_manager._store_branch_state(branch_state)
        
        logger.info(
            f"Lock TTL extended: {lock_id} by {extended_by}. "
            f"Old: {old_expires_at}, New: {lock.expires_at}. Reason: {reason}"
        )
        
        return True
    
    # ==================== Private Helper Methods ====================
    
    def _has_active_indexing_locks(self, branch_state) -> bool:
        """Check if branch has any active indexing locks"""
        return any(
            lock.is_active and lock.lock_type == LockType.INDEXING
            for lock in branch_state.active_locks
        )
    
    async def _release_all_branch_locks(self, branch_name: str, reason: str):
        """Release all active locks for a branch"""
        locks = self.core.get_active_locks(branch_name)
        for lock in locks:
            if lock.is_active:
                await self.release_lock(lock.id, f"system_{reason}")
    
    async def _perform_cleanup(self):
        """Cleanup callback called by cleanup service"""
        active_locks = self.core.get_active_locks()
        
        # Cleanup TTL expired locks
        await self.cleanup_service.cleanup_expired_locks(
            active_locks, self.release_lock
        )
        
        # Cleanup heartbeat expired locks
        await self.cleanup_service.cleanup_heartbeat_expired_locks(
            active_locks, self.release_lock
        )


# ==================== Global Instance Management ====================

_lock_manager: Optional[BranchLockManager] = None


def get_lock_manager() -> BranchLockManager:
    """Get global lock manager instance"""
    global _lock_manager
    if _lock_manager is None:
        _lock_manager = BranchLockManager()
    return _lock_manager


async def initialize_lock_manager(cache_service=None, db_service=None):
    """Initialize global lock manager"""
    global _lock_manager
    _lock_manager = BranchLockManager(cache_service, db_service)
    await _lock_manager.initialize()
    return _lock_manager