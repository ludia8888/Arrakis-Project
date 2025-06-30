"""
Lock Cleanup Service
Handles cleanup of expired locks and maintenance operations
"""
import asyncio
from typing import List, Tuple, Callable
from datetime import datetime, timezone

from models.branch_state import (
    BranchLock, is_lock_expired_by_ttl, is_lock_expired_by_heartbeat
)
from utils.logger import get_logger

logger = get_logger(__name__)


class LockCleanupService:
    """
    Manages cleanup of expired locks
    Handles both TTL-based and heartbeat-based expiration
    """
    
    def __init__(self):
        # Cleanup settings
        self.cleanup_interval = 300  # Check every 5 minutes
        self.batch_size = 100  # Process locks in batches
        
        # Background task handle
        self._cleanup_task = None
        
        # Cleanup callbacks
        self._cleanup_callbacks: List[Callable] = []
        
        # Statistics
        self._cleanup_stats = {
            "total_cleaned": 0,
            "ttl_expired": 0,
            "heartbeat_expired": 0,
            "last_cleanup": None
        }
    
    async def start(self):
        """Start the cleanup service"""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Lock cleanup service started")
    
    async def stop(self):
        """Stop the cleanup service"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("Lock cleanup service stopped")
    
    def add_cleanup_callback(self, callback: Callable):
        """Add a callback to be called when locks are cleaned up"""
        self._cleanup_callbacks.append(callback)
    
    async def cleanup_expired_locks(
        self,
        active_locks: List[BranchLock],
        release_callback: Callable
    ) -> List[Tuple[str, str]]:
        """
        Remove expired locks based on TTL
        
        Args:
            active_locks: List of currently active locks
            release_callback: Callback to release the lock
            
        Returns:
            List of (lock_id, reason) tuples for cleaned locks
        """
        cleaned_locks = []
        
        # Process in batches for performance
        for i in range(0, len(active_locks), self.batch_size):
            batch = active_locks[i:i + self.batch_size]
            
            for lock in batch:
                if not lock.is_active:
                    continue
                
                cleanup_reason = None
                
                # Check TTL expiration
                if is_lock_expired_by_ttl(lock):
                    cleanup_reason = "TTL_EXPIRED"
                    self._cleanup_stats["ttl_expired"] += 1
                
                # Cleanup if expired and auto-release enabled
                if cleanup_reason and lock.auto_release_enabled:
                    try:
                        await release_callback(lock.id, f"system_cleanup_{cleanup_reason}")
                        cleaned_locks.append((lock.id, cleanup_reason))
                        self._cleanup_stats["total_cleaned"] += 1
                        
                        logger.info(f"TTL expired lock cleaned up: {lock.id} (reason: {cleanup_reason})")
                    except (ConnectionError, TimeoutError) as e:
                        logger.error(f"Network error cleaning up lock {lock.id}: {e}")
                    except RuntimeError as e:
                        logger.error(f"Runtime error cleaning up lock {lock.id}: {e}")
            
            # Brief yield to avoid blocking
            if i + self.batch_size < len(active_locks):
                await asyncio.sleep(0)
        
        if cleaned_locks:
            logger.info(f"Cleaned up {len(cleaned_locks)} TTL expired locks")
        
        return cleaned_locks
    
    async def cleanup_heartbeat_expired_locks(
        self,
        active_locks: List[BranchLock],
        release_callback: Callable
    ) -> List[Tuple[str, str]]:
        """
        Remove locks that have missed heartbeats
        
        Args:
            active_locks: List of currently active locks
            release_callback: Callback to release the lock
            
        Returns:
            List of (lock_id, reason) tuples for cleaned locks
        """
        cleaned_locks = []
        
        for lock in active_locks:
            if not lock.is_active or lock.heartbeat_interval <= 0:
                continue
            
            if is_lock_expired_by_heartbeat(lock):
                if lock.auto_release_enabled:
                    try:
                        await release_callback(lock.id, "system_cleanup_HEARTBEAT_MISSED")
                        cleaned_locks.append((lock.id, "HEARTBEAT_MISSED"))
                        self._cleanup_stats["heartbeat_expired"] += 1
                        self._cleanup_stats["total_cleaned"] += 1
                        
                        logger.warning(
                            f"Heartbeat expired lock cleaned up: {lock.id} "
                            f"(missed heartbeats from {lock.heartbeat_source})"
                        )
                    except (ConnectionError, TimeoutError) as e:
                        logger.error(f"Network error cleaning up heartbeat expired lock {lock.id}: {e}")
                    except RuntimeError as e:
                        logger.error(f"Runtime error cleaning up heartbeat expired lock {lock.id}: {e}")
        
        if cleaned_locks:
            logger.warning(f"Cleaned up {len(cleaned_locks)} heartbeat expired locks")
        
        return cleaned_locks
    
    async def force_cleanup_branch(
        self,
        branch_name: str,
        active_locks: List[BranchLock],
        release_callback: Callable,
        reason: str = "force_cleanup"
    ) -> int:
        """
        Force cleanup all locks for a specific branch
        
        Returns:
            Number of locks cleaned up
        """
        branch_locks = [
            lock for lock in active_locks 
            if lock.branch_name == branch_name and lock.is_active
        ]
        
        cleaned_count = 0
        for lock in branch_locks:
            try:
                await release_callback(lock.id, f"system_{reason}")
                cleaned_count += 1
            except (ConnectionError, TimeoutError) as e:
                logger.error(f"Network error force cleaning lock {lock.id}: {e}")
            except RuntimeError as e:
                logger.error(f"Runtime error force cleaning lock {lock.id}: {e}")
        
        if cleaned_count > 0:
            logger.info(
                f"Force cleaned {cleaned_count} locks for branch {branch_name}: {reason}"
            )
        
        return cleaned_count
    
    async def _cleanup_loop(self):
        """Background task to periodically cleanup expired locks"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                
                # Update last cleanup time
                self._cleanup_stats["last_cleanup"] = datetime.now(timezone.utc)
                
                # Notify callbacks
                for callback in self._cleanup_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback()
                        else:
                            callback()
                    except RuntimeError as e:
                        logger.error(f"Cleanup callback runtime error: {e}")
                
                logger.debug("Cleanup cycle completed")
                
            except asyncio.CancelledError:
                break
            except RuntimeError as e:
                logger.error(f"Runtime error in cleanup loop: {e}")
                await asyncio.sleep(30)  # Brief pause before retry
    
    def get_cleanup_statistics(self) -> dict:
        """Get cleanup statistics"""
        stats = self._cleanup_stats.copy()
        stats["cleanup_interval_seconds"] = self.cleanup_interval
        stats["batch_size"] = self.batch_size
        return stats
    
    def reset_statistics(self):
        """Reset cleanup statistics"""
        self._cleanup_stats = {
            "total_cleaned": 0,
            "ttl_expired": 0,
            "heartbeat_expired": 0,
            "last_cleanup": None
        }
        logger.info("Cleanup statistics reset")