"""
Resilient Job Executor - Integrates scheduler with unified resilience module

This replaces the missing retry logic in the scheduler with the unified
retry executor, providing consistent retry behavior across the system.
"""
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Callable, Optional, List

from shared.resilience import (
    ResilienceRegistry,
    RetryConfig,
    RetryStrategy,
    CircuitBreakerConfig,
    RETRY_POLICIES,
    with_retry,
    with_resilience
)
from shared.monitoring.unified_metrics import get_metrics_collector
from shared.observability import tracing
from utils import logging

from .models import JobMetadata, JobExecution, JobStatus, JobExecutionContext
from .job_executor import DefaultJobExecutor
from .advanced_scheduler import AdvancedScheduler

logger = logging.get_logger(__name__)
tracer = tracing.get_tracer(__name__)
metrics = get_metrics_collector()


class ResilientJobExecutor(DefaultJobExecutor):
    """
    Job executor with integrated retry and circuit breaker patterns.
    
    This adds retry logic to the scheduler, which was missing in the original
    implementation despite having retry configuration in JobMetadata.
    """
    
    def __init__(
        self,
        worker_id: str,
        max_workers: int = 10,
        dependency_checker: Optional[Callable] = None,
        notification_service: Optional[Callable] = None,
        scheduler_ref: Optional[AdvancedScheduler] = None,
        resilience_name: Optional[str] = None
    ):
        super().__init__(
            worker_id=worker_id,
            max_workers=max_workers,
            dependency_checker=dependency_checker,
            notification_service=notification_service,
            scheduler_ref=scheduler_ref
        )
        
        # Initialize resilience components
        self.resilience_name = resilience_name or f"scheduler_{worker_id}"
        
        # Create circuit breaker for job execution
        self.circuit_breaker = ResilienceRegistry.get_circuit_breaker(
            name=f"{self.resilience_name}_cb",
            config=CircuitBreakerConfig(
                failure_threshold=10,
                success_threshold=3,
                timeout=timedelta(minutes=5)
            )
        )
        
        # Get retry executor
        self.retry_executor = ResilienceRegistry.get_retry_executor(
            name=self.resilience_name,
            circuit_breaker_name=f"{self.resilience_name}_cb"
        )
        
        # Additional metrics for retry
        self.retry_counter = metrics.Counter(
            'scheduler_job_retries_total',
            'Total job retry attempts',
            ['job_name', 'status']
        )
    
    def _get_retry_config_for_job(self, metadata: JobMetadata) -> RetryConfig:
        """Get retry config based on job metadata"""
        # Use predefined policies based on job category
        category_to_policy = {
            "critical": "critical",
            "data_processing": "database",
            "external_api": "network",
            "webhook": "webhook"
        }
        
        policy_name = category_to_policy.get(metadata.category, "standard")
        
        if policy_name in RETRY_POLICIES:
            config = RETRY_POLICIES[policy_name].to_config()
        else:
            # Create custom config from job metadata
            config = RetryConfig(
                strategy=RetryStrategy.EXPONENTIAL_WITH_JITTER,
                max_attempts=metadata.max_retries,
                initial_delay=metadata.retry_delay,
                max_delay=metadata.retry_delay * 10,  # Cap at 10x initial delay
                exponential_base=2.0,
                jitter_enabled=True
            )
        
        # Override with job-specific settings
        config.max_attempts = metadata.max_retries
        
        # Add retryable exceptions based on job type
        config.retryable_exceptions = [
            asyncio.TimeoutError,
            ConnectionError,
            RuntimeError  # For transient failures
        ]
        
        return config
    
    async def execute_job(
        self,
        job_id: str,
        func: Callable,
        metadata: JobMetadata,
        args: List[Any],
        kwargs: Dict[str, Any]
    ) -> JobExecution:
        """Execute a job with retry support"""
        execution_id = str(uuid.uuid4())
        
        with tracer.start_as_current_span("execute_resilient_job") as span:
            span.set_attribute("job.id", job_id)
            span.set_attribute("execution.id", execution_id)
            span.set_attribute("job.max_retries", metadata.max_retries)
            
            # Create execution record
            execution = JobExecution(
                execution_id=execution_id,
                job_id=job_id,
                status=JobStatus.RUNNING,
                started_at=datetime.now(timezone.utc),
                worker_id=self.worker_id,
                retry_count=0
            )
            
            # Check dependencies
            if metadata.dependencies and self._dependency_checker:
                if not await self._dependency_checker(metadata.dependencies):
                    execution.status = JobStatus.FAILED
                    execution.error = "Dependencies not met"
                    execution.completed_at = datetime.now(timezone.utc)
                    execution.duration = 0
                    return execution
            
            # Get retry config
            retry_config = self._get_retry_config_for_job(metadata)
            
            # Define the job execution function
            async def _execute_job_with_context():
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
                        
                        return result
                    finally:
                        # Cleanup
                        self._running_jobs.pop(execution_id, None)
                        self.active_jobs.dec()
            
            # Execute with retry
            if metadata.max_retries > 0:
                result = await self.retry_executor.aexecute(
                    _execute_job_with_context,
                    retry_config
                )
                
                execution.retry_count = result.attempts - 1  # First attempt is not a retry
                
                if result.successful:
                    # Success
                    execution.status = JobStatus.COMPLETED
                    execution.result = result.result
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
                    
                    if execution.retry_count > 0:
                        self.retry_counter.labels(
                            job_name=metadata.name,
                            status="success"
                        ).inc(execution.retry_count)
                    
                    # Success notifications
                    if metadata.notify_on_success and self._notification_service:
                        await self._notification_service(
                            metadata.notify_on_success,
                            f"Job {metadata.name} completed successfully after {result.attempts} attempts",
                            execution
                        )
                else:
                    # Failed after all retries
                    execution.status = JobStatus.FAILED
                    execution.error = str(result.last_error)
                    execution.completed_at = datetime.now(timezone.utc)
                    execution.duration = (
                        execution.completed_at - execution.started_at
                    ).total_seconds()
                    span.record_exception(result.last_error)
                    
                    self._record_failure_metrics(metadata, execution)
                    self.retry_counter.labels(
                        job_name=metadata.name,
                        status="failed"
                    ).inc(execution.retry_count)
                    
                    # Check if we should reschedule
                    if await self._should_reschedule_failed_job(metadata, execution):
                        await self._reschedule_failed_job(job_id, metadata, execution)
                    
                    # Failure notifications
                    if metadata.notify_on_failure and self._notification_service:
                        await self._notification_service(
                            metadata.notify_on_failure,
                            f"Job {metadata.name} failed after {result.attempts} attempts: {result.last_error}",
                            execution
                        )
            else:
                # No retry configured, execute once
                try:
                    result = await _execute_job_with_context()
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
                    
                except Exception as e:
                    execution.status = JobStatus.FAILED
                    execution.error = str(e)
                    execution.completed_at = datetime.now(timezone.utc)
                    execution.duration = (
                        execution.completed_at - execution.started_at
                    ).total_seconds()
                    span.record_exception(e)
                    
                    self._record_failure_metrics(metadata, execution)
            
            return execution
    
    async def _should_reschedule_failed_job(
        self,
        metadata: JobMetadata,
        execution: JobExecution
    ) -> bool:
        """Determine if a failed job should be rescheduled"""
        # Don't reschedule if:
        # 1. Job doesn't have reschedule_on_failure enabled
        # 2. Job has already been retried max times within execution
        # 3. Job is a one-time job without cron
        
        if not metadata.reschedule_on_failure:
            return False
        
        if execution.retry_count >= metadata.max_retries:
            return False
        
        if not metadata.cron_expression and metadata.next_run is None:
            return False
        
        return True
    
    async def _reschedule_failed_job(
        self,
        job_id: str,
        metadata: JobMetadata,
        execution: JobExecution
    ):
        """Reschedule a failed job for later retry"""
        if not self._scheduler_ref:
            logger.warning("No scheduler reference available for rescheduling")
            return
        
        # Calculate next retry time with exponential backoff
        retry_delay = metadata.retry_delay * (2 ** execution.retry_count)
        next_run = datetime.now(timezone.utc) + timedelta(seconds=retry_delay)
        
        # Update job metadata
        metadata.next_run = next_run
        metadata.reschedule_count = getattr(metadata, 'reschedule_count', 0) + 1
        
        logger.info(
            f"Rescheduling failed job {job_id} to run at {next_run} "
            f"(retry {execution.retry_count + 1}/{metadata.max_retries})"
        )
        
        # Note: The actual rescheduling would be handled by the scheduler
        # This is just updating the metadata. The scheduler needs to check
        # for jobs with updated next_run times.
    
    def get_resilience_metrics(self) -> Dict[str, Any]:
        """Get resilience metrics for this executor"""
        return {
            "retry_executor": self.retry_executor.get_metrics().__dict__,
            "circuit_breaker": self.circuit_breaker.get_metrics()
        }


# Convenience decorator for scheduled jobs
def scheduled_job_with_retry(
    retry_policy: str = "standard",
    circuit_breaker_name: Optional[str] = None
):
    """
    Decorator to add retry logic to scheduled job functions.
    
    Example:
        @scheduled_job_with_retry(retry_policy="network")
        async def sync_external_data(context: JobExecutionContext):
            async with httpx.AsyncClient() as client:
                response = await client.get("https://api.example.com/data")
                return response.json()
    """
    def decorator(func):
        # Apply resilience patterns
        if circuit_breaker_name:
            func = with_resilience(
                retry_policy=retry_policy,
                circuit_breaker_name=circuit_breaker_name
            )(func)
        else:
            func = with_retry(policy=retry_policy)(func)
        
        return func
    
    return decorator