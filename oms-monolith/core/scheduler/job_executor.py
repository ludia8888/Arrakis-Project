"""
Job Executor - Handles job execution with lifecycle management
"""
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Callable, Optional, List
from abc import ABC, abstractmethod

from .models import JobMetadata, JobExecution, JobStatus, JobExecutionContext
from shared.monitoring.unified_metrics import get_metrics_collector
from shared.observability import tracing
from utils import logging

logger = logging.get_logger(__name__)
tracer = tracing.get_tracer(__name__)
metrics = get_metrics_collector()


class JobExecutorProtocol(ABC):
    """Protocol for job execution"""
    
    @abstractmethod
    async def execute_job(
        self,
        job_id: str,
        func: Callable,
        metadata: JobMetadata,
        args: List[Any],
        kwargs: Dict[str, Any]
    ) -> JobExecution:
        """Execute a job with full lifecycle management"""
        pass
    
    @abstractmethod
    def is_running(self, execution_id: str) -> bool:
        """Check if a job execution is running"""
        pass
    
    @abstractmethod
    async def cancel_execution(self, execution_id: str) -> bool:
        """Cancel a running job execution"""
        pass


class DefaultJobExecutor(JobExecutorProtocol):
    """Default implementation of job executor"""
    
    def __init__(
        self,
        worker_id: str,
        max_workers: int = 10,
        dependency_checker: Optional[Callable] = None,
        notification_service: Optional[Callable] = None,
        scheduler_ref: Optional[Any] = None
    ):
        self.worker_id = worker_id
        self._execution_semaphore = asyncio.Semaphore(max_workers)
        self._running_jobs: Dict[str, asyncio.Task] = {}
        self._dependency_checker = dependency_checker
        self._notification_service = notification_service
        self._scheduler_ref = scheduler_ref
        
        # Metrics
        self.job_counter = metrics.Counter(
            'scheduler_jobs_total',
            'Total scheduled jobs',
            ['status', 'category']
        )
        self.job_duration = metrics.Histogram(
            'scheduler_job_duration_seconds',
            'Job execution duration',
            ['job_name', 'status']
        )
        self.active_jobs = metrics.Gauge(
            'scheduler_active_jobs',
            'Currently running jobs'
        )
    
    async def execute_job(
        self,
        job_id: str,
        func: Callable,
        metadata: JobMetadata,
        args: List[Any],
        kwargs: Dict[str, Any]
    ) -> JobExecution:
        """Execute a job with full lifecycle management"""
        execution_id = str(uuid.uuid4())
        
        with tracer.start_as_current_span("execute_job") as span:
            span.set_attribute("job.id", job_id)
            span.set_attribute("execution.id", execution_id)
            
            # Create execution record
            execution = JobExecution(
                execution_id=execution_id,
                job_id=job_id,
                status=JobStatus.RUNNING,
                started_at=datetime.now(timezone.utc),
                worker_id=self.worker_id
            )
            
            # Check dependencies
            if metadata.dependencies and self._dependency_checker:
                if not await self._dependency_checker(metadata.dependencies):
                    execution.status = JobStatus.FAILED
                    execution.error = "Dependencies not met"
                    execution.completed_at = datetime.now(timezone.utc)
                    execution.duration = 0
                    return execution
            
            # Acquire semaphore
            async with self._execution_semaphore:
                self.active_jobs.inc()
                
                try:
                    # Create context
                    context = JobExecutionContext(
                        job_id=job_id,
                        execution_id=execution_id,
                        metadata=metadata,
                        scheduler=self._scheduler_ref
                    )
                    
                    # Execute with timeout
                    task = asyncio.create_task(func(context, *args, **kwargs))
                    self._running_jobs[execution_id] = task
                    
                    result = await asyncio.wait_for(
                        task,
                        timeout=metadata.timeout
                    )
                    
                    # Success
                    execution.status = JobStatus.COMPLETED
                    execution.result = result
                    execution.completed_at = datetime.now(timezone.utc)
                    execution.duration = (
                        execution.completed_at - execution.started_at
                    ).total_seconds()
                    
                    # Metrics
                    self.job_counter.labels(
                        status="completed",
                        category=metadata.category
                    ).inc()
                    self.job_duration.labels(
                        job_name=metadata.name,
                        status="success"
                    ).observe(execution.duration)
                    
                    # Success notifications
                    if metadata.notify_on_success and self._notification_service:
                        await self._notification_service(
                            metadata.notify_on_success,
                            f"Job {metadata.name} completed successfully",
                            execution
                        )
                    
                except asyncio.TimeoutError:
                    execution.status = JobStatus.FAILED
                    execution.error = f"Job timed out after {metadata.timeout}s"
                    execution.completed_at = datetime.now(timezone.utc)
                    execution.duration = (
                        execution.completed_at - execution.started_at
                    ).total_seconds()
                    span.record_exception(Exception(execution.error))
                    
                    # Cancel task
                    task.cancel()
                    
                    self._record_failure_metrics(metadata, execution)
                    
                except asyncio.CancelledError as e:
                    # Job was cancelled
                    execution.status = JobStatus.FAILED
                    execution.error = "Job execution was cancelled"
                    execution.completed_at = datetime.now(timezone.utc)
                    execution.duration = (
                        execution.completed_at - execution.started_at
                    ).total_seconds()
                    span.record_exception(e)
                    logger.warning(f"Job {job_id} was cancelled")
                    
                    self._record_failure_metrics(metadata, execution)
                    raise  # Re-raise to properly handle cancellation
                    
                except (ImportError, AttributeError) as e:
                    # Failed to import job module or access job function
                    execution.status = JobStatus.FAILED
                    execution.error = f"Job import/access error: {e}"
                    execution.completed_at = datetime.now(timezone.utc)
                    execution.duration = (
                        execution.completed_at - execution.started_at
                    ).total_seconds()
                    span.record_exception(e)
                    logger.error(f"Job {job_id} import failed: {e}")
                    
                    self._record_failure_metrics(metadata, execution)
                    
                except (ValueError, TypeError) as e:
                    # Invalid arguments or type errors in job
                    execution.status = JobStatus.FAILED
                    execution.error = f"Job argument error: {e}"
                    execution.completed_at = datetime.now(timezone.utc)
                    execution.duration = (
                        execution.completed_at - execution.started_at
                    ).total_seconds()
                    span.record_exception(e)
                    logger.error(f"Job {job_id} argument error: {e}")
                    
                    self._record_failure_metrics(metadata, execution)
                    
                except RuntimeError as e:
                    # Runtime errors during job execution
                    execution.status = JobStatus.FAILED
                    execution.error = f"Job runtime error: {e}"
                    execution.completed_at = datetime.now(timezone.utc)
                    execution.duration = (
                        execution.completed_at - execution.started_at
                    ).total_seconds()
                    span.record_exception(e)
                    logger.error(f"Job {job_id} runtime error: {e}")
                    
                    self._record_failure_metrics(metadata, execution)
                    
                    # Failure notifications
                    if metadata.notify_on_failure and self._notification_service:
                        await self._notification_service(
                            metadata.notify_on_failure,
                            f"Job {metadata.name} failed: {e}",
                            execution
                        )
                    
                finally:
                    # Cleanup
                    self._running_jobs.pop(execution_id, None)
                    self.active_jobs.dec()
            
            return execution
    
    def is_running(self, execution_id: str) -> bool:
        """Check if a job execution is running"""
        return execution_id in self._running_jobs
    
    async def cancel_execution(self, execution_id: str) -> bool:
        """Cancel a running job execution"""
        task = self._running_jobs.get(execution_id)
        if task:
            task.cancel()
            return True
        return False
    
    def get_running_executions(self) -> List[str]:
        """Get list of running execution IDs"""
        return list(self._running_jobs.keys())
    
    async def shutdown(self):
        """Shutdown executor and cancel all running jobs"""
        for execution_id, task in self._running_jobs.items():
            task.cancel()
        
        if self._running_jobs:
            await asyncio.gather(
                *self._running_jobs.values(),
                return_exceptions=True
            )
        
        self._running_jobs.clear()
    
    def _record_failure_metrics(self, metadata: JobMetadata, execution: JobExecution):
        """Record failure metrics"""
        self.job_counter.labels(
            status="failed",
            category=metadata.category
        ).inc()
        self.job_duration.labels(
            job_name=metadata.name,
            status="failed"
        ).observe(execution.duration or 0)