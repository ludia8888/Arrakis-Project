# Core branch module exports
# Legacy imports removed - use service_factory instead
from .conflict_resolver import ConflictResolver

# New abstractions and adapters
from .interfaces import IBranchService, ILockService, IMergeEngine
from .service_factory import BranchServiceFactory, get_branch_service
from .terminus_adapter import TerminusNativeBranchService

# Lock management components
from .lock_manager import BranchLockManager, get_lock_manager, initialize_lock_manager
from .lock_manager_core import LockManagerCore, LockConflictError
from .lock_state_manager import LockStateManager, InvalidStateTransitionError
from .lock_heartbeat_service import LockHeartbeatService
from .lock_cleanup_service import LockCleanupService

__all__ = [
    # Core services (legacy removed)
    "ConflictResolver",
    
    # New abstractions
    "IBranchService",
    "ILockService", 
    "IMergeEngine",
    "BranchServiceFactory",
    "get_branch_service",
    "TerminusNativeBranchService",
    
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