"""
Lock Heartbeat Service
Manages heartbeat monitoring and health checking for distributed locks
"""
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta

from models.branch_state import (
    BranchLock, HeartbeatRecord, 
    is_lock_expired_by_heartbeat
)
from utils.logger import get_logger

logger = get_logger(__name__)


class LockHeartbeatService:
    """
    Manages heartbeat functionality for distributed locks
    Monitors lock health and detects missed heartbeats
    """
    
    def __init__(self, db_service=None):
        self.db_service = db_service
        
        # Heartbeat settings
        self.heartbeat_check_interval = 30  # Check heartbeats every 30 seconds
        self.heartbeat_grace_multiplier = 3  # Allow 3x heartbeat_interval before expiry
        
        # Background task handle
        self._heartbeat_checker_task = None
        
        # Heartbeat history tracking
        self._heartbeat_history: Dict[str, List[HeartbeatRecord]] = {}
    
    async def start(self):
        """Start the heartbeat monitoring service"""
        self._heartbeat_checker_task = asyncio.create_task(self._heartbeat_checker_loop())
        logger.info("Lock heartbeat service started")
    
    async def stop(self):
        """Stop the heartbeat monitoring service"""
        if self._heartbeat_checker_task:
            self._heartbeat_checker_task.cancel()
            try:
                await self._heartbeat_checker_task
            except asyncio.CancelledError:
                pass
        logger.info("Lock heartbeat service stopped")
    
    async def send_heartbeat(
        self,
        lock: BranchLock,
        service_name: str,
        status: str = "healthy",
        progress_info: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send a heartbeat for a lock to indicate the service is still active
        
        Args:
            lock: The lock to send heartbeat for
            service_name: Name of the service sending the heartbeat
            status: Status of the service (healthy, warning, error)
            progress_info: Optional progress information
            
        Returns:
            True if heartbeat was recorded successfully
        """
        if not lock or not lock.is_active:
            logger.warning(f"Attempted to send heartbeat for inactive lock: {lock.id if lock else 'None'}")
            return False
        
        # Update lock heartbeat
        now = datetime.now(timezone.utc)
        lock.last_heartbeat = now
        lock.heartbeat_source = service_name
        
        # Create heartbeat record
        heartbeat = HeartbeatRecord(
            lock_id=lock.id,
            branch_name=lock.branch_name,
            service_name=service_name,
            heartbeat_at=now,
            status=status,
            progress_info=progress_info
        )
        
        # Store in history
        if lock.id not in self._heartbeat_history:
            self._heartbeat_history[lock.id] = []
        self._heartbeat_history[lock.id].append(heartbeat)
        
        # Keep only recent history (last 100 heartbeats)
        if len(self._heartbeat_history[lock.id]) > 100:
            self._heartbeat_history[lock.id] = self._heartbeat_history[lock.id][-100:]
        
        # Store heartbeat record in persistent storage
        if self.db_service:
            try:
                await self.db_service.store_heartbeat_record(heartbeat)
            except Exception as e:
                logger.error(f"Failed to persist heartbeat record: {e}")
        
        logger.debug(
            f"Heartbeat received for lock {lock.id} from {service_name} (status: {status})"
        )
        
        return True
    
    async def get_lock_health_status(self, lock: BranchLock) -> Dict[str, Any]:
        """Get health status and heartbeat information for a lock"""
        if not lock:
            return None
        
        now = datetime.now(timezone.utc)
        health_status = {
            "lock_id": lock.id,
            "is_active": lock.is_active,
            "heartbeat_enabled": lock.heartbeat_interval > 0,
            "last_heartbeat": lock.last_heartbeat,
            "heartbeat_source": lock.heartbeat_source,
            "heartbeat_expired": is_lock_expired_by_heartbeat(lock),
            "auto_release_enabled": lock.auto_release_enabled
        }
        
        if lock.last_heartbeat:
            seconds_since_heartbeat = (now - lock.last_heartbeat).total_seconds()
            health_status["seconds_since_last_heartbeat"] = int(seconds_since_heartbeat)
            
            if lock.heartbeat_interval > 0:
                health_status["heartbeat_health"] = self._calculate_heartbeat_health(
                    seconds_since_heartbeat, lock.heartbeat_interval
                )
        
        # Add recent heartbeat history
        if lock.id in self._heartbeat_history:
            recent_heartbeats = self._heartbeat_history[lock.id][-10:]
            health_status["recent_heartbeats"] = [
                {
                    "time": hb.heartbeat_at.isoformat(),
                    "service": hb.service_name,
                    "status": hb.status
                }
                for hb in recent_heartbeats
            ]
        
        return health_status
    
    def check_heartbeat_expired(self, lock: BranchLock) -> bool:
        """Check if a lock has missed its heartbeat"""
        return is_lock_expired_by_heartbeat(lock)
    
    async def get_expired_heartbeat_locks(self, active_locks: List[BranchLock]) -> List[BranchLock]:
        """Get all locks that have missed heartbeats"""
        expired_locks = []
        
        for lock in active_locks:
            if self.check_heartbeat_expired(lock):
                expired_locks.append(lock)
        
        return expired_locks
    
    def _calculate_heartbeat_health(self, seconds_since: float, interval: int) -> str:
        """Calculate heartbeat health status"""
        if seconds_since < interval:
            return "healthy"
        elif seconds_since < interval * self.heartbeat_grace_multiplier:
            return "warning"
        else:
            return "critical"
    
    async def _heartbeat_checker_loop(self):
        """Background task to check for missed heartbeats"""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_check_interval)
                # The actual checking is handled by the cleanup service
                logger.debug("Heartbeat check cycle completed")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat checker loop: {e}")
                await asyncio.sleep(5)  # Brief pause before retry
    
    def get_heartbeat_statistics(self) -> Dict[str, Any]:
        """Get statistics about heartbeat monitoring"""
        total_locks_monitored = len(self._heartbeat_history)
        active_heartbeats = sum(
            1 for history in self._heartbeat_history.values()
            if history and (datetime.now(timezone.utc) - history[-1].heartbeat_at).total_seconds() < 300
        )
        
        return {
            "total_locks_monitored": total_locks_monitored,
            "active_heartbeats": active_heartbeats,
            "check_interval": self.heartbeat_check_interval,
            "grace_multiplier": self.heartbeat_grace_multiplier
        }