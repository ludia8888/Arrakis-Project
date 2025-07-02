"""
Unified DLQ handler integrated with resilience module.

This integrates DLQ retry logic with the unified resilience patterns,
replacing the custom retry implementation with UnifiedRetryExecutor.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional

import redis.asyncio as redis
from shared.infrastructure.unified_nats_client import UnifiedNATSClient as NATSClient
from shared.monitoring.unified_metrics import get_metrics_collector
from shared.resilience import (
    ResilienceRegistry,
    RetryConfig,
    RetryStrategy,
    CircuitBreakerConfig,
    RetryBudgetConfig,
    RETRY_POLICIES,
    UnifiedBackoffCalculator
)

from .config import DLQConfig
from .models import DLQMessage, DLQReason, MessageStatus, RetryPolicy
from .handlers import DLQHandler

logger = logging.getLogger(__name__)
metrics = get_metrics_collector()


class UnifiedDLQHandler(DLQHandler):
    """
    DLQ handler integrated with unified resilience module.
    
    This replaces the custom retry logic with the unified retry executor,
    providing consistent retry behavior across the system.
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        config: DLQConfig,
        nats_client: Optional[NATSClient] = None,
        resilience_name: Optional[str] = None
    ):
        super().__init__(redis_client, config, nats_client)
        
        # Initialize resilience components
        self.resilience_name = resilience_name or f"dlq_{config.name}"
        
        # Create circuit breaker for DLQ processing
        self.circuit_breaker = ResilienceRegistry.get_circuit_breaker(
            name=f"{self.resilience_name}_cb",
            config=CircuitBreakerConfig(
                failure_threshold=5,
                success_threshold=2,
                timeout=timedelta(minutes=5)
            )
        )
        
        # Create retry budget to prevent retry storms
        self.retry_budget = ResilienceRegistry.get_retry_budget(
            name=f"{self.resilience_name}_budget",
            config=RetryBudgetConfig(
                budget_percent=20.0,  # Allow 20% retry rate
                window_size=timedelta(minutes=1),
                min_requests=10
            )
        )
        
        # Get retry executor with circuit breaker and budget
        self.retry_executor = ResilienceRegistry.get_retry_executor(
            name=self.resilience_name,
            circuit_breaker_name=f"{self.resilience_name}_cb",
            retry_budget_name=f"{self.resilience_name}_budget"
        )
        
        # Create backoff calculator for next retry time calculation
        self.backoff_calculator = UnifiedBackoffCalculator()
    
    def _get_retry_config_for_reason(self, reason: DLQReason) -> RetryConfig:
        """Get appropriate retry config based on DLQ reason"""
        # Map DLQ reasons to retry policies
        reason_to_policy = {
            DLQReason.NETWORK_ERROR: "network",
            DLQReason.WEBHOOK_FAILED: "webhook",
            DLQReason.TIMEOUT: "network",
            DLQReason.EXECUTION_FAILED: "database",
            DLQReason.VALIDATION_FAILED: "validation",
            DLQReason.AUTHENTICATION_ERROR: "auth"
        }
        
        policy_name = reason_to_policy.get(reason, "standard")
        
        # Get predefined policy or create custom one
        if policy_name in RETRY_POLICIES:
            config = RETRY_POLICIES[policy_name].to_config()
        else:
            # Create config from DLQ retry policy
            config = self._convert_dlq_policy_to_retry_config(self.config.retry_policy)
        
        # Override max attempts with DLQ config
        config.max_attempts = self.config.max_retries
        
        return config
    
    def _convert_dlq_policy_to_retry_config(self, dlq_policy: RetryPolicy) -> RetryConfig:
        """Convert DLQ RetryPolicy to unified RetryConfig"""
        # Determine strategy based on backoff multiplier
        if dlq_policy.backoff_multiplier == 1.0:
            strategy = RetryStrategy.FIXED
        elif dlq_policy.backoff_multiplier > 1.0:
            strategy = RetryStrategy.EXPONENTIAL_WITH_JITTER if dlq_policy.jitter else RetryStrategy.EXPONENTIAL
        else:
            strategy = RetryStrategy.LINEAR
        
        return RetryConfig(
            strategy=strategy,
            max_attempts=dlq_policy.max_retries,
            initial_delay=dlq_policy.initial_delay,
            max_delay=dlq_policy.max_delay,
            exponential_base=dlq_policy.backoff_multiplier,
            jitter_enabled=dlq_policy.jitter,
            jitter_factor=0.5 if dlq_policy.jitter else 0.0
        )
    
    async def retry_message(self, queue_name: str, message_id: str) -> bool:
        """
        Retry a DLQ message using unified retry executor.
        
        This replaces the custom retry logic with the unified resilience module,
        providing consistent retry behavior with circuit breaker and retry budget.
        """
        try:
            # Get message from DLQ
            dlq_key = f"{self.config.redis_key_prefix}:{queue_name}:{message_id}"
            message_data = await self.redis.get(dlq_key)
            
            if not message_data:
                logger.warning(f"DLQ message not found: {message_id}")
                return False
            
            dlq_message = DLQMessage.from_dict(json.loads(message_data))
            
            # Check if handler registered
            handler = self.message_handlers.get(queue_name)
            if not handler:
                logger.error(f"No handler registered for queue: {queue_name}")
                return False
            
            # Get retry config based on reason
            retry_config = self._get_retry_config_for_reason(dlq_message.reason)
            
            # Override attempts based on current retry count
            retry_config.max_attempts = dlq_message.max_retries - dlq_message.retry_count
            
            # Define the retry function
            async def _execute_handler():
                # Apply transform function if configured
                original_message = dlq_message.original_message
                if self.config.transform_function:
                    try:
                        if asyncio.iscoroutinefunction(self.config.transform_function):
                            original_message = await self.config.transform_function(dlq_message)
                        else:
                            original_message = self.config.transform_function(dlq_message)
                    except Exception as e:
                        logger.error(f"Transform function failed for message {message_id}: {e}")
                        # Continue with original message if transform fails
                
                # Execute handler
                return await handler(original_message)
            
            # Update message status
            dlq_message.status = MessageStatus.PROCESSING
            dlq_message.retry_count += 1
            dlq_message.last_failure_time = datetime.now(timezone.utc)
            
            # Execute with retry
            start_time = asyncio.get_event_loop().time()
            result = await self.retry_executor.aexecute(_execute_handler, retry_config)
            
            if result.successful:
                # Success - remove from DLQ
                await self.remove_from_dlq(queue_name, message_id)
                
                # Call success callback if configured
                if self.config.success_callback:
                    try:
                        if asyncio.iscoroutinefunction(self.config.success_callback):
                            await self.config.success_callback(dlq_message)
                        else:
                            self.config.success_callback(dlq_message)
                    except Exception as e:
                        logger.error(f"Success callback failed for message {message_id}: {e}")
                
                # Update metrics
                metrics.counter(
                    'dlq_retries_total',
                    'DLQ retry attempts',
                    labels={'queue': queue_name, 'status': 'success'}
                ).inc()
                
                metrics.histogram(
                    'dlq_processing_time_seconds',
                    'Time to process DLQ message',
                    labels={'queue': queue_name}
                ).observe(asyncio.get_event_loop().time() - start_time)
                
                # Publish success event
                if self.nats:
                    await self._publish_dlq_event(dlq_message, "retry_success")
                
                logger.info(f"Successfully retried DLQ message: {message_id} after {result.attempts} attempts")
                return True
            
            else:
                # Failed after all retries
                metrics.counter(
                    'dlq_retries_total',
                    'DLQ retry attempts',
                    labels={'queue': queue_name, 'status': 'failure'}
                ).inc()
                
                # Update retry count from result
                dlq_message.retry_count = dlq_message.retry_count - 1 + result.attempts
                
                return await self._handle_retry_failure(dlq_message, result.last_error)
        
        except Exception as e:
            logger.error(f"Unexpected error retrying DLQ message: {e}")
            return False
    
    def get_next_retry_time(self, dlq_message: DLQMessage) -> Optional[datetime]:
        """
        Calculate next retry time using unified backoff calculator.
        
        This replaces the custom backoff calculation with the unified implementation.
        """
        if dlq_message.retry_count >= dlq_message.max_retries:
            return None
        
        # Get retry config for this message
        retry_config = self._get_retry_config_for_reason(dlq_message.reason)
        
        # Calculate delay using unified calculator
        delay = self.backoff_calculator.calculate_delay(
            attempt=dlq_message.retry_count + 1,
            config=retry_config
        )
        
        return datetime.now(timezone.utc) + timedelta(seconds=delay)
    
    async def _handle_retry_failure(self, dlq_message: DLQMessage, error: Exception) -> bool:
        """Handle retry failure with updated retry time calculation"""
        # Check if max retries exceeded
        if dlq_message.retry_count >= dlq_message.max_retries:
            # Move to poison queue
            await self.move_to_poison_queue(dlq_message)
            await self.remove_from_dlq(dlq_message.queue_name, dlq_message.message_id)
            logger.error(f"Message {dlq_message.message_id} moved to poison queue after {dlq_message.retry_count} retries")
            
            # Call failure callback if configured
            if self.config.failure_callback:
                try:
                    if asyncio.iscoroutinefunction(self.config.failure_callback):
                        await self.config.failure_callback(dlq_message)
                    else:
                        self.config.failure_callback(dlq_message)
                except Exception as e:
                    logger.error(f"Failure callback failed for message {dlq_message.message_id}: {e}")
        else:
            # Update message with new retry time using unified calculator
            dlq_message.next_retry_time = self.get_next_retry_time(dlq_message)
            dlq_message.add_error(str(error))
            dlq_message.status = MessageStatus.RETRYING
            
            # Update in Redis
            dlq_key = f"{self.config.redis_key_prefix}:{dlq_message.queue_name}:{dlq_message.message_id}"
            await self.redis.set(
                dlq_key,
                json.dumps(dlq_message.to_dict()),
                ex=self.config.ttl
            )
            
            logger.warning(
                f"Retry failed for message {dlq_message.message_id}, "
                f"retry count: {dlq_message.retry_count}/{dlq_message.max_retries}, "
                f"next retry at: {dlq_message.next_retry_time}"
            )
        
        return False
    
    def get_resilience_metrics(self) -> Dict[str, Any]:
        """Get resilience metrics for this DLQ handler"""
        return {
            "retry_executor": self.retry_executor.get_metrics().__dict__,
            "circuit_breaker": self.circuit_breaker.get_metrics(),
            "retry_budget": self.retry_budget.get_metrics()
        }


# Predefined retry policies for DLQ using unified configs
DLQ_RETRY_POLICIES = {
    "webhook": RETRY_POLICIES["webhook"],
    "validation": RETRY_POLICIES["validation"],
    "execution": RETRY_POLICIES["critical"],
    "network": RETRY_POLICIES["network"]
}