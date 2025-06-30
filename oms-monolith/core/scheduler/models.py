"""
Scheduler Models - Shared data models for scheduler components
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from enum import Enum
from dataclasses import dataclass, field


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    MISSED = "missed"
    PAUSED = "paused"


class JobPriority(int, Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class JobMetadata:
    """Extended job metadata"""
    job_id: str
    name: str
    description: Optional[str] = None
    category: str = "general"
    owner: str = "system"
    priority: JobPriority = JobPriority.NORMAL
    max_retries: int = 3
    retry_delay: int = 60  # seconds
    timeout: int = 300  # seconds
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)  # Job IDs
    notify_on_failure: List[str] = field(default_factory=list)  # Email addresses
    notify_on_success: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None


@dataclass
class JobExecution:
    """Job execution record"""
    execution_id: str
    job_id: str
    status: JobStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Optional[Any] = None
    duration: Optional[float] = None
    retry_count: int = 0
    worker_id: Optional[str] = None


class JobExecutionContext:
    """Context passed to job functions"""
    def __init__(
        self,
        job_id: str,
        execution_id: str,
        metadata: JobMetadata,
        scheduler: Optional['EnterpriseScheduler'] = None
    ):
        self.job_id = job_id
        self.execution_id = execution_id
        self.metadata = metadata
        self.scheduler = scheduler
        self.logger = None  # Will be injected
        self._cancelled = False
        
    async def checkpoint(self, state: Dict[str, Any]):
        """Save job checkpoint for resumption"""
        if self.scheduler:
            await self.scheduler.save_checkpoint(self.job_id, self.execution_id, state)
    
    async def update_progress(self, progress: int, message: Optional[str] = None):
        """Update job progress (0-100)"""
        if self.scheduler:
            await self.scheduler.update_job_progress(
                self.job_id, self.execution_id, progress, message
            )
    
    def is_cancelled(self) -> bool:
        """Check if job is cancelled"""
        return self._cancelled
    
    async def emit_event(self, event_type: str, data: Dict[str, Any]):
        """Emit custom job event"""
        if self.scheduler:
            await self.scheduler.emit_job_event(self.job_id, event_type, data)