"""
State Manager - Handles persistent job state and execution records
"""
import json
import pickle
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod

from database.clients import RedisHAClient
from .models import JobMetadata, JobExecution, JobStatus
from utils import logging

logger = logging.get_logger(__name__)


class StateManagerProtocol(ABC):
    """Protocol for job state management"""
    
    @abstractmethod
    async def save_job_metadata(self, scheduled_job_id: str, metadata: JobMetadata):
        """Save job metadata"""
        pass
    
    @abstractmethod
    async def get_job_metadata(self, scheduled_job_id: str) -> Dict[str, Any]:
        """Get job metadata"""
        pass
    
    @abstractmethod
    async def save_execution(self, execution: JobExecution):
        """Save execution record"""
        pass
    
    @abstractmethod
    async def get_job_executions(
        self, job_id: str, limit: int = 10
    ) -> List[JobExecution]:
        """Get job execution history"""
        pass
    
    @abstractmethod
    async def save_checkpoint(
        self, job_id: str, execution_id: str, state: Dict[str, Any]
    ):
        """Save job checkpoint"""
        pass
    
    @abstractmethod
    async def get_checkpoint(
        self, job_id: str, execution_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get job checkpoint"""
        pass


class RedisStateManager(StateManagerProtocol):
    """Redis implementation of state manager"""
    
    def __init__(self, redis_client: RedisHAClient):
        self.redis_client = redis_client
    
    async def save_job_metadata(self, scheduled_job_id: str, metadata: JobMetadata):
        """Save job metadata to Redis"""
        key = f"job:metadata:{scheduled_job_id}"
        await self.redis_client.setex(
            key,
            86400 * 30,  # 30 days
            metadata.__dict__
        )
    
    async def get_job_metadata(self, scheduled_job_id: str) -> Dict[str, Any]:
        """Get job metadata from Redis"""
        key = f"job:metadata:{scheduled_job_id}"
        data = await self.redis_client.get(key)
        return data or {}
    
    async def save_execution(self, execution: JobExecution):
        """Save execution record"""
        key = f"execution:{execution.job_id}:{execution.execution_id}"
        await self.redis_client.setex(
            key,
            86400 * 30,  # 30 days
            execution.__dict__
        )
    
    async def get_job_executions(
        self, job_id: str, limit: int = 10
    ) -> List[JobExecution]:
        """Get job execution history"""
        pattern = f"execution:{job_id}:*"
        keys = await self.redis_client.keys(pattern)
        
        executions = []
        for key in keys[-limit:]:
            data = await self.redis_client.get(key)
            if data:
                executions.append(JobExecution(**data))
        
        return sorted(executions, key=lambda x: x.started_at, reverse=True)
    
    async def save_checkpoint(
        self, job_id: str, execution_id: str, state: Dict[str, Any]
    ):
        """Save job checkpoint"""
        key = f"checkpoint:{job_id}:{execution_id}"
        await self.redis_client.setex(
            key,
            86400,  # 24 hours
            pickle.dumps(state)
        )
    
    async def get_checkpoint(
        self, job_id: str, execution_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get job checkpoint"""
        key = f"checkpoint:{job_id}:{execution_id}"
        data = await self.redis_client.get(key)
        return pickle.loads(data) if data else None
    
    async def update_job_progress(
        self,
        job_id: str,
        execution_id: str,
        progress: int,
        message: Optional[str] = None
    ):
        """Update job progress"""
        key = f"progress:{job_id}:{execution_id}"
        await self.redis_client.setex(
            key,
            3600,  # 1 hour
            {
                "progress": progress,
                "message": message,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        )
    
    async def get_job_progress(
        self, job_id: str, execution_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get job progress"""
        key = f"progress:{job_id}:{execution_id}"
        return await self.redis_client.get(key)
    
    async def update_job_status(self, scheduled_job_id: str, status: JobStatus):
        """Update job status"""
        key = f"job:status:{scheduled_job_id}"
        await self.redis_client.setex(key, 86400, status.value)
    
    async def get_job_status(self, scheduled_job_id: str) -> Optional[JobStatus]:
        """Get job status"""
        key = f"job:status:{scheduled_job_id}"
        status_str = await self.redis_client.get(key)
        return JobStatus(status_str) if status_str else None
    
    async def cleanup_old_executions(self, days: int = 30):
        """Clean up old execution records"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        pattern = "execution:*"
        keys = await self.redis_client.keys(pattern)
        
        for key in keys:
            data = await self.redis_client.get(key)
            if data:
                try:
                    execution = JobExecution(**data)
                    if execution.started_at < cutoff:
                        await self.redis_client.delete(key)
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(f"Failed to parse execution JSON for {key}: {e}")
                    # Delete corrupted data
                    await self.redis_client.delete(key)
                except (KeyError, ValueError) as e:
                    logger.warning(f"Invalid execution data structure for {key}: {e}")
                    # Delete corrupted data
                    await self.redis_client.delete(key)
    
    async def get_execution_statistics(
        self,
        job_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get execution statistics"""
        pattern = f"execution:{job_id}:*" if job_id else "execution:*"
        keys = await self.redis_client.keys(pattern)
        
        stats = {
            "total": 0,
            "completed": 0,
            "failed": 0,
            "running": 0,
            "average_duration": 0,
            "success_rate": 0
        }
        
        durations = []
        
        for key in keys:
            data = await self.redis_client.get(key)
            if data:
                try:
                    execution = JobExecution(**data)
                    
                    # Apply date filters
                    if start_date and execution.started_at < start_date:
                        continue
                    if end_date and execution.started_at > end_date:
                        continue
                    
                    stats["total"] += 1
                    
                    if execution.status == JobStatus.COMPLETED:
                        stats["completed"] += 1
                        if execution.duration:
                            durations.append(execution.duration)
                    elif execution.status == JobStatus.FAILED:
                        stats["failed"] += 1
                    elif execution.status == JobStatus.RUNNING:
                        stats["running"] += 1
                        
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(f"Failed to parse execution JSON for statistics {key}: {e}")
                except (KeyError, ValueError) as e:
                    logger.warning(f"Invalid execution data for statistics {key}: {e}")
        
        if durations:
            stats["average_duration"] = sum(durations) / len(durations)
        
        if stats["total"] > 0:
            stats["success_rate"] = stats["completed"] / stats["total"]
        
        return stats