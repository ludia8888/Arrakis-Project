"""Enterprise-grade scheduler facade with distributed execution, persistence and monitoring"""

import asyncio
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED, EVENT_JOB_SUBMITTED, EVENT_JOB_REMOVED, EVENT_JOB_MODIFIED

from database.clients import RedisHAClient
from utils import logging
from shared.monitoring.unified_metrics import get_metrics_collector
from shared.observability import tracing
from shared.audit.unified_audit_logger import get_unified_audit_logger

from . import (
    JobStatus, JobMetadata, JobExecution,
    JobExecutorProtocol, DefaultJobExecutor,
    StateManagerProtocol, RedisStateManager,
    NotificationServiceProtocol, DefaultNotificationService,
    ScheduleCalculatorProtocol, DefaultScheduleCalculator
)

logger = logging.get_logger(__name__)
tracer = tracing.get_tracer(__name__)
metrics = get_metrics_collector()


class EnterpriseScheduler:
    """Enterprise scheduler facade with distributed execution, persistence, monitoring and fault tolerance"""
    
    def __init__(self, redis_client: RedisHAClient, worker_id: Optional[str] = None, max_workers: int = 10,
                 job_defaults: Optional[Dict] = None, timezone: str = "UTC",
                 job_executor: Optional[JobExecutorProtocol] = None,
                 state_manager: Optional[StateManagerProtocol] = None,
                 notification_service: Optional[NotificationServiceProtocol] = None,
                 schedule_calculator: Optional[ScheduleCalculatorProtocol] = None):
        self.redis_client = redis_client
        self.worker_id = worker_id or str(uuid.uuid4())
        
        # Initialize components
        self.state_manager = state_manager or RedisStateManager(redis_client)
        self.notification_service = notification_service or DefaultNotificationService()
        self.schedule_calculator = schedule_calculator or DefaultScheduleCalculator(timezone)
        self.job_executor = job_executor or DefaultJobExecutor(
            worker_id=self.worker_id, max_workers=max_workers,
            state_manager=self.state_manager, notification_service=self.notification_service, scheduler_ref=self
        )
        
        # Job registry
        self._job_functions: Dict[str, Callable] = {}
        self._job_metadata: Dict[str, JobMetadata] = {}
        
        # Setup APScheduler
        self.scheduler = AsyncIOScheduler(
            jobstores={'default': RedisJobStore(db=0, jobs_key='apscheduler.jobs', 
                                               run_times_key='apscheduler.run_times', redis=redis_client._get_connection())},
            executors={'default': AsyncIOExecutor()},
            job_defaults=job_defaults or {'coalesce': True, 'max_instances': 3, 'misfire_grace_time': 30},
            timezone=timezone
        )
        
        self.scheduler.add_listener(self._on_job_event, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_MISSED | EVENT_JOB_SUBMITTED | EVENT_JOB_REMOVED | EVENT_JOB_MODIFIED)
        
        # Expose metrics
        self.job_counter = self.job_executor.job_counter
        self.job_duration = self.job_executor.job_duration
        self.active_jobs = self.job_executor.active_jobs
        self.audit_logger = get_unified_audit_logger()
    
    async def start(self):
        """Start the scheduler"""
        logger.info(f"Starting scheduler with worker_id: {self.worker_id}")
        await self.job_executor.register_worker()
        self.scheduler.start()
        asyncio.create_task(self.job_executor.monitor_jobs())
        asyncio.create_task(self.state_manager.cleanup_old_executions())
        asyncio.create_task(self.job_executor.process_dependencies())
        logger.info("Scheduler started successfully")
    
    async def shutdown(self, wait: bool = True):
        """Shutdown the scheduler"""
        logger.info("Shutting down scheduler...")
        await self.job_executor.shutdown()
        self.scheduler.shutdown(wait=wait)
        await self.job_executor.unregister_worker()
        logger.info("Scheduler shutdown complete")
    
    def register_job(self, func: Callable, job_id: Optional[str] = None, name: Optional[str] = None, **metadata_kwargs):
        """Register a job function"""
        job_id = job_id or func.__name__
        self._job_functions[job_id] = func
        self._job_metadata[job_id] = JobMetadata(job_id=job_id, name=name or func.__name__, **metadata_kwargs)
        logger.info(f"Registered job: {job_id}")
        return job_id
    
    async def schedule_job(self, job_id: str, trigger: Union[str, CronTrigger, IntervalTrigger, DateTrigger],
                          args: Optional[List] = None, kwargs: Optional[Dict] = None, **scheduler_kwargs) -> str:
        """Schedule a job"""
        with tracer.start_as_current_span("schedule_job") as span:
            span.set_attribute("job.id", job_id)
            if job_id not in self._job_functions:
                raise ValueError(f"Job {job_id} not registered")
            
            parsed_trigger = self.schedule_calculator.parse_trigger(trigger)
            job = self.scheduler.add_job(
                self._execute_job, trigger=parsed_trigger, args=[job_id, args or [], kwargs or {}],
                id=f"{job_id}_{uuid.uuid4().hex[:8]}", name=self._job_metadata[job_id].name, **scheduler_kwargs
            )
            
            await self.state_manager.save_job_metadata(job.id, self._job_metadata[job_id])
            await self.audit_logger.log_event(
                user_id=self._job_metadata[job_id].owner, action="job.scheduled", resource=f"job:{job.id}",
                details={"job_id": job_id, "trigger": str(parsed_trigger), 
                        "next_run": job.next_run_time.isoformat() if job.next_run_time else None}
            )
            self.job_counter.labels(status="scheduled", category=self._job_metadata[job_id].category).inc()
            return job.id
    
    async def schedule_one_time_job(self, job_id: str, run_date: Union[str, datetime],
                                   args: Optional[List] = None, kwargs: Optional[Dict] = None, **scheduler_kwargs) -> str:
        """Schedule a one-time job"""
        if isinstance(run_date, str):
            run_date = datetime.fromisoformat(run_date)
        return await self.schedule_job(job_id, DateTrigger(run_date=run_date), args, kwargs, **scheduler_kwargs)
    
    async def schedule_recurring_job(self, job_id: str, cron_expression: str,
                                   args: Optional[List] = None, kwargs: Optional[Dict] = None, **scheduler_kwargs) -> str:
        """Schedule a recurring job with cron expression"""
        return await self.schedule_job(job_id, CronTrigger.from_crontab(cron_expression), args, kwargs, **scheduler_kwargs)
    
    async def pause_job(self, scheduled_job_id: str):
        self.scheduler.pause_job(scheduled_job_id)
        await self.state_manager.update_job_status(scheduled_job_id, JobStatus.PAUSED)
    
    async def resume_job(self, scheduled_job_id: str):
        self.scheduler.resume_job(scheduled_job_id)
        await self.state_manager.update_job_status(scheduled_job_id, JobStatus.PENDING)
    
    async def cancel_job(self, scheduled_job_id: str):
        self.scheduler.remove_job(scheduled_job_id)
        await self.state_manager.update_job_status(scheduled_job_id, JobStatus.CANCELLED)
    
    async def get_job_status(self, scheduled_job_id: str) -> Dict[str, Any]:
        """Get job status and details"""
        job = self.scheduler.get_job(scheduled_job_id)
        if not job:
            return {"status": "not_found"}
        
        executions = await self.state_manager.get_job_executions(scheduled_job_id)
        return {
            "id": job.id, "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger), "pending": job.pending,
            "executions": [exec.__dict__ for exec in executions],
            "metadata": await self.state_manager.get_job_metadata(scheduled_job_id)
        }
    
    async def list_jobs(self, category: Optional[str] = None, status: Optional[JobStatus] = None, owner: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all scheduled jobs with filters"""
        jobs = []
        for job in self.scheduler.get_jobs():
            metadata = await self.state_manager.get_job_metadata(job.id)
            if category and metadata.get("category") != category:
                continue
            if owner and metadata.get("owner") != owner:
                continue
            
            jobs.append({
                "id": job.id, "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger), "metadata": metadata
            })
        return jobs
    
    async def get_execution_history(self, job_id: Optional[str] = None, status: Optional[JobStatus] = None,
                                   start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, limit: int = 100) -> List[JobExecution]:
        """Get job execution history"""
        return await self.state_manager.get_execution_history(job_id, status, start_date, end_date, limit)
    
    async def _execute_job(self, job_id: str, args: List, kwargs: Dict):
        """Execute a job - delegate to JobExecutor"""
        func = self._job_functions.get(job_id)
        metadata = self._job_metadata.get(job_id)
        if not func or not metadata:
            logger.error(f"Job function or metadata not found: {job_id}")
            return
        await self.job_executor.execute_job(func=func, metadata=metadata, args=args, kwargs=kwargs)
    
    async def _on_job_event(self, event):
        """Handle APScheduler events"""
        if event.exception:
            logger.error(f"Job {event.job_id} crashed: {event.exception}")
    
    # Helper methods
    async def save_checkpoint(self, job_id: str, execution_id: str, state: Dict[str, Any]):
        await self.state_manager.save_checkpoint(job_id, execution_id, state)
    
    async def get_checkpoint(self, job_id: str, execution_id: str) -> Optional[Dict[str, Any]]:
        return await self.state_manager.get_checkpoint(job_id, execution_id)
    
    async def update_job_progress(self, job_id: str, execution_id: str, progress: int, message: Optional[str] = None):
        await self.state_manager.update_job_progress(job_id, execution_id, progress, message)
    
    async def emit_job_event(self, job_id: str, event_type: str, data: Dict[str, Any]):
        await self.notification_service.emit_job_event(job_id, event_type, data)


def scheduled_job(scheduler: EnterpriseScheduler, job_id: Optional[str] = None, **metadata_kwargs):
    """Decorator to register a scheduled job"""
    def decorator(func: Callable):
        nonlocal job_id
        job_id = job_id or func.__name__
        if not asyncio.iscoroutinefunction(func):
            raise ValueError(f"Job function {func.__name__} must be async")
        scheduler.register_job(func, job_id, **metadata_kwargs)
        return func
    return decorator