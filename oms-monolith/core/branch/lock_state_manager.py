"""
Lock State Manager
Manages branch states and state transitions
"""
import json
from typing import Optional, Dict, List
from datetime import datetime, timezone

from models.branch_state import (
    BranchState, BranchStateInfo, BranchStateTransition,
    BranchLock, is_valid_transition
)
from utils.logger import get_logger

logger = get_logger(__name__)


class InvalidStateTransitionError(Exception):
    """Raised when an invalid state transition is attempted"""
    pass


class LockStateManager:
    """
    Manages branch state information and transitions
    Handles persistence and caching of state data
    """
    
    def __init__(self, cache_service=None, db_service=None):
        self.cache_service = cache_service  # Redis for fast state checks
        self.db_service = db_service       # Persistent storage
        
        # In-memory cache for high performance (fallback if no Redis)
        self._branch_states: Dict[str, BranchStateInfo] = {}
    
    async def get_branch_state(self, branch_name: str) -> BranchStateInfo:
        """Get current state of a branch"""
        # Try cache first
        if self.cache_service:
            try:
                cached = await self.cache_service.get(f"branch_state:{branch_name}")
                if cached:
                    return BranchStateInfo.parse_obj(json.loads(cached))
            except Exception as e:
                logger.warning(f"Cache retrieval failed for branch {branch_name}: {e}")
        
        # Check in-memory cache
        if branch_name in self._branch_states:
            return self._branch_states[branch_name]
        
        # Try persistent storage
        if self.db_service:
            try:
                state = await self.db_service.get_branch_state(branch_name)
                if state:
                    await self._cache_branch_state(state)
                    return state
            except Exception as e:
                logger.warning(f"DB retrieval failed for branch {branch_name}: {e}")
        
        # Default state for new branches
        default_state = BranchStateInfo(
            branch_name=branch_name,
            current_state=BranchState.ACTIVE,
            state_changed_by="system",
            state_change_reason="Initial state",
            state_changed_at=datetime.now(timezone.utc),
            active_locks=[]
        )
        
        await self._store_branch_state(default_state)
        return default_state
    
    async def set_branch_state(
        self,
        branch_name: str,
        new_state: BranchState,
        changed_by: str = "system",
        reason: str = "State change"
    ) -> BranchStateInfo:
        """
        Set branch state directly
        
        Returns:
            Updated BranchStateInfo
            
        Raises:
            InvalidStateTransitionError: If transition is invalid
        """
        current_state = await self.get_branch_state(branch_name)
        
        # Check if transition is valid
        if current_state.current_state == new_state:
            logger.debug(f"Branch {branch_name} already in state {new_state}")
            return current_state
        
        # Perform transition
        updated_state = await self.transition_state(
            current_state,
            new_state,
            changed_by,
            reason
        )
        
        await self._store_branch_state(updated_state)
        
        logger.info(
            f"Branch state set: {branch_name} -> {new_state} by {changed_by}"
        )
        return updated_state
    
    async def transition_state(
        self,
        branch_state: BranchStateInfo,
        new_state: BranchState,
        changed_by: str,
        reason: str
    ) -> BranchStateInfo:
        """Transition branch to new state"""
        old_state = branch_state.current_state
        
        # Validate transition
        if not is_valid_transition(old_state, new_state):
            raise InvalidStateTransitionError(
                f"Invalid state transition: {old_state} -> {new_state}"
            )
        
        # Record transition
        transition = BranchStateTransition(
            branch_name=branch_state.branch_name,
            from_state=old_state,
            to_state=new_state,
            transitioned_by=changed_by,
            reason=reason,
            trigger="lock_manager",
            transitioned_at=datetime.now(timezone.utc)
        )
        
        # Update state
        branch_state.previous_state = old_state
        branch_state.current_state = new_state
        branch_state.state_changed_at = datetime.now(timezone.utc)
        branch_state.state_changed_by = changed_by
        branch_state.state_change_reason = reason
        
        # Store transition history
        if self.db_service:
            try:
                await self.db_service.store_state_transition(transition)
            except Exception as e:
                logger.error(f"Failed to store state transition: {e}")
        
        logger.info(
            f"Branch state transition: {branch_state.branch_name} "
            f"{old_state} -> {new_state} by {changed_by}"
        )
        
        return branch_state
    
    async def add_lock_to_state(self, branch_name: str, lock: BranchLock) -> BranchStateInfo:
        """Add a lock to branch state"""
        state = await self.get_branch_state(branch_name)
        state.active_locks.append(lock)
        await self._store_branch_state(state)
        return state
    
    async def remove_lock_from_state(self, branch_name: str, lock_id: str) -> BranchStateInfo:
        """Remove a lock from branch state"""
        state = await self.get_branch_state(branch_name)
        state.active_locks = [
            lock for lock in state.active_locks if lock.id != lock_id
        ]
        await self._store_branch_state(state)
        return state
    
    async def update_indexing_metadata(
        self,
        branch_name: str,
        indexing_service: str,
        started: bool = True
    ) -> BranchStateInfo:
        """Update indexing metadata in branch state"""
        state = await self.get_branch_state(branch_name)
        
        if started:
            state.indexing_started_at = datetime.now(timezone.utc)
            state.indexing_service = indexing_service
        else:
            state.indexing_completed_at = datetime.now(timezone.utc)
        
        await self._store_branch_state(state)
        return state
    
    async def _store_branch_state(self, state_info: BranchStateInfo):
        """Store branch state in cache and persistent storage"""
        # Update in-memory cache
        self._branch_states[state_info.branch_name] = state_info
        
        # Update Redis cache
        if self.cache_service:
            try:
                await self.cache_service.set(
                    f"branch_state:{state_info.branch_name}",
                    state_info.json(),
                    ttl=3600  # 1 hour
                )
            except Exception as e:
                logger.error(f"Failed to cache branch state: {e}")
        
        # Store in persistent DB (if available)
        if self.db_service:
            try:
                await self.db_service.store_branch_state(state_info)
            except Exception as e:
                logger.error(f"Failed to persist branch state: {e}")
    
    async def _cache_branch_state(self, state_info: BranchStateInfo):
        """Cache branch state without persisting"""
        self._branch_states[state_info.branch_name] = state_info
        
        if self.cache_service:
            try:
                await self.cache_service.set(
                    f"branch_state:{state_info.branch_name}",
                    state_info.json(),
                    ttl=3600
                )
            except Exception as e:
                logger.warning(f"Failed to cache branch state: {e}")