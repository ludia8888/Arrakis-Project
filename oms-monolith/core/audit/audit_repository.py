"""
Audit Repository - Storage layer for audit events
Implements the repository pattern for audit data persistence
"""
from typing import List, Dict, Any, Optional, Tuple, Protocol
from datetime import datetime
import asyncio

from core.audit.models import AuditEventV1, AuditEventFilter, AuditAction
from core.audit.storage_adapter import AuditStorageAdapter
from shared.database.audit_database import get_audit_database
from shared.exceptions import InfrastructureException, DatabaseConnectionError
from utils.logger import get_logger

logger = get_logger(__name__)


class AuditRepositoryInterface(Protocol):
    """Interface for audit repository implementations"""
    
    async def store_event(self, event: AuditEventV1) -> bool:
        """Store a single audit event"""
        ...
    
    async def store_events_batch(self, events: List[AuditEventV1]) -> int:
        """Store multiple audit events in batch"""
        ...
    
    async def query_events(
        self, 
        filter_criteria: AuditEventFilter
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Query audit events with filtering"""
        ...
    
    async def get_event_by_id(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get specific audit event by ID"""
        ...
    
    async def get_statistics(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get audit statistics"""
        ...
    
    async def cleanup_expired_events(self) -> int:
        """Clean up expired audit events"""
        ...
    
    async def verify_integrity(self) -> Dict[str, Any]:
        """Verify audit log integrity"""
        ...


class AuditRepository(AuditRepositoryInterface):
    """
    Concrete implementation of audit repository
    Handles all storage operations for audit events
    """
    
    def __init__(self):
        self._storage: Optional[AuditStorageAdapter] = None
        self._initialized = False
        self._init_lock = asyncio.Lock()
    
    async def initialize(self):
        """Initialize the repository with database connection"""
        async with self._init_lock:
            if not self._initialized:
                try:
                    raw_database = await get_audit_database()
                    self._storage = AuditStorageAdapter(raw_database)
                    self._initialized = True
                    logger.info("Audit repository initialized successfully")
                except (ConnectionError, TimeoutError) as e:
                    logger.error(f"Failed to connect to audit database: {e}")
                    raise DatabaseConnectionError(f"Audit database connection failed: {e}")
                except ValueError as e:
                    logger.error(f"Invalid configuration for audit repository: {e}")
                    raise InfrastructureException(f"Audit repository initialization failed: {e}")
                except RuntimeError as e:
                    logger.error(f"Runtime error initializing audit repository: {e}")
                    raise InfrastructureException(f"Audit repository initialization failed: {e}")
    
    async def _ensure_initialized(self):
        """Ensure repository is initialized before operations"""
        if not self._initialized:
            await self.initialize()
    
    async def store_event(self, event: AuditEventV1) -> bool:
        """Store a single audit event"""
        await self._ensure_initialized()
        return await self._storage.store_audit_event(event)
    
    async def store_events_batch(self, events: List[AuditEventV1]) -> int:
        """Store multiple audit events in batch"""
        await self._ensure_initialized()
        return await self._storage.store_audit_events_batch(events)
    
    async def query_events(
        self, 
        filter_criteria: AuditEventFilter
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Query audit events with filtering"""
        await self._ensure_initialized()
        return await self._storage.query_audit_events(filter_criteria)
    
    async def get_event_by_id(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get specific audit event by ID"""
        await self._ensure_initialized()
        return await self._storage.get_audit_event_by_id(event_id)
    
    async def get_statistics(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get audit statistics"""
        await self._ensure_initialized()
        return await self._storage.get_audit_statistics(start_time, end_time)
    
    async def cleanup_expired_events(self) -> int:
        """Clean up expired audit events"""
        await self._ensure_initialized()
        return await self._storage.cleanup_expired_events()
    
    async def verify_integrity(self) -> Dict[str, Any]:
        """Verify audit log integrity"""
        await self._ensure_initialized()
        return await self._storage.verify_integrity()