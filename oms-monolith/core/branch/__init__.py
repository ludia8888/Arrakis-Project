# Core branch module exports
from .service import BranchService
from .diff_engine import DiffEngine
from .conflict_resolver import ConflictResolver
from .merge_strategies import MergeStrategyImplementor
from .three_way_merge import ThreeWayMergeAlgorithm

# Lock management components
from .lock_manager import BranchLockManager, get_lock_manager, initialize_lock_manager
from .lock_manager_core import LockManagerCore, LockConflictError
from .lock_state_manager import LockStateManager, InvalidStateTransitionError
from .lock_heartbeat_service import LockHeartbeatService
from .lock_cleanup_service import LockCleanupService

__all__ = [
    # Core services
    "BranchService",
    "DiffEngine", 
    "ConflictResolver",
    "MergeStrategyImplementor",
    "ThreeWayMergeAlgorithm",
    
    # Lock management
    "BranchLockManager",
    "get_lock_manager",
    "initialize_lock_manager",
    "LockManagerCore",
    "LockConflictError",
    "LockStateManager",
    "InvalidStateTransitionError",
    "LockHeartbeatService",
    "LockCleanupService"
]