"""
Unified DLQ handlers consolidating middleware and core/action implementations.
"""

import asyncio
import json
import logging
import traceback
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional

import httpx
import redis.asyncio as redis
from shared.infrastructure.unified_nats_client import UnifiedNATSClient as NATSClient
from shared.monitoring.unified_metrics import get_metrics_collector

from .config import DLQConfig
from .models import DLQMessage, DLQReason, MessageStatus, RetryPolicy

logger = logging.getLogger(__name__)
metrics = get_metrics_collector()

# Unified metrics
dlq_messages = metrics.counter('dlq_messages_total', 'Total DLQ messages', ['queue', 'reason'])
dlq_retries = metrics.counter('dlq_retry_attempts_total', 'DLQ retry attempts', ['queue', 'status'])
dlq_size = metrics.gauge('dlq_size', 'Current DLQ size', ['queue'])
dlq_age = metrics.histogram('dlq_message_age_seconds', 'Age of messages in DLQ', ['queue'])
dlq_processing_time = metrics.histogram('dlq_processing_time_seconds', 'Time to process DLQ message', ['queue'])


class DLQHandler:
    """Unified Dead Letter Queue handler with advanced features"""

    def __init__(
        self,
        redis_client: redis.Redis,
        config: DLQConfig,
        nats_client: Optional[NATSClient] = None
    ):
        self.redis = redis_client
        self.config = config
        self.nats = nats_client
        self.processing_queues: Dict[str, asyncio.Queue] = {}
        self.message_handlers: Dict[str, Callable] = {}
        self._running = False
        self._tasks: List[asyncio.Task] = []

    def register_handler(self, queue_name: str, handler: Callable):
        """Register message handler for retry processing"""
        self.message_handlers[queue_name] = handler

    async def send_to_dlq(
        self,
        queue_name: str,
        original_message: Dict[str, Any],
        reason: DLQReason,
        error: Exception,
        retry_count: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Send message to DLQ"""
        try:
            # Create DLQ message
            message_id = f"{queue_name}:{datetime.now(timezone.utc).timestamp()}:{hash(str(original_message))}"

            dlq_message = DLQMessage(
                message_id=message_id,
                queue_name=queue_name,
                original_message=original_message,
                reason=reason,
                error_details=str(error),
                stack_trace=traceback.format_exc() if error else None,
                retry_count=retry_count,
                max_retries=self.config.max_retries,
                first_failure_time=datetime.now(timezone.utc),
                last_failure_time=datetime.now(timezone.utc),
                next_retry_time=self.config.retry_policy.get_next_retry_time(retry_count),
                metadata=metadata or {}
            )

            # Store in Redis
            dlq_key = f"{self.config.redis_key_prefix}:{queue_name}:{message_id}"
            await self.redis.set(
                dlq_key,
                json.dumps(dlq_message.to_dict()),
                ex=self.config.ttl
            )

            # Add to queue index
            await self.redis.zadd(
                f"{self.config.redis_key_prefix}:index:{queue_name}",
                {message_id: datetime.now(timezone.utc).timestamp()}
            )

            # Update metrics
            dlq_messages.labels(queue=queue_name, reason=reason.value).inc()
            await self._update_queue_size(queue_name)

            # Publish event if NATS available
            if self.nats:
                await self._publish_dlq_event(dlq_message, "message_added")

            logger.warning(
                f"Message sent to DLQ - Queue: {queue_name}, Reason: {reason.value}, "
                f"Message ID: {message_id}, Retry Count: {retry_count}"
            )

            return message_id

        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.error(f"Failed to send message to DLQ: {e}")
            raise
        except RuntimeError as e:
            logger.error(f"Runtime error sending message to DLQ: {e}")
            raise

    async def retry_message(self, queue_name: str, message_id: str) -> bool:
        """Manually retry a DLQ message"""
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

            # Update retry count
            dlq_message.retry_count += 1
            dlq_message.last_failure_time = datetime.now(timezone.utc)
            dlq_message.status = MessageStatus.PROCESSING

            try:
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
                start_time = asyncio.get_event_loop().time()
                await handler(original_message)

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
                dlq_retries.labels(queue=queue_name, status='success').inc()
                dlq_processing_time.labels(queue=queue_name).observe(
                    asyncio.get_event_loop().time() - start_time
                )

                # Publish success event
                if self.nats:
                    await self._publish_dlq_event(dlq_message, "retry_success")

                logger.info(f"Successfully retried DLQ message: {message_id}")
                return True

            except (asyncio.TimeoutError, httpx.HTTPError) as retry_error:
                # Network or timeout failure
                dlq_retries.labels(queue=queue_name, status='failure').inc()
                return await self._handle_retry_failure(dlq_message, retry_error)

            except RuntimeError as retry_error:
                # Failed retry
                dlq_retries.labels(queue=queue_name, status='failure').inc()
                return await self._handle_retry_failure(dlq_message, retry_error)

        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.error(f"Data access error retrying DLQ message: {e}")
            return False
        except RuntimeError as e:
            logger.error(f"Runtime error retrying DLQ message: {e}")
            return False

    async def _handle_retry_failure(self, dlq_message: DLQMessage, error: Exception) -> bool:
        """Handle retry failure"""
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
            # Update message with new retry time
            dlq_message.next_retry_time = self.config.retry_policy.get_next_retry_time(
                dlq_message.retry_count
            )
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
                f"retry count: {dlq_message.retry_count}/{dlq_message.max_retries}"
            )

        return False

    async def remove_from_dlq(self, queue_name: str, message_id: str):
        """Remove message from DLQ"""
        dlq_key = f"{self.config.redis_key_prefix}:{queue_name}:{message_id}"
        await self.redis.delete(dlq_key)
        await self.redis.zrem(f"{self.config.redis_key_prefix}:index:{queue_name}", message_id)
        await self._update_queue_size(queue_name)

    async def move_to_poison_queue(self, dlq_message: DLQMessage):
        """Move message to poison queue for manual intervention"""
        poison_key = f"poison:{dlq_message.queue_name}:{dlq_message.message_id}"

        # Mark as poison message
        dlq_message.reason = DLQReason.POISON_MESSAGE
        dlq_message.status = MessageStatus.POISON

        # Store in poison queue (no expiry)
        await self.redis.set(
            poison_key,
            json.dumps(dlq_message.to_dict())
        )

        # Add to poison index
        await self.redis.zadd(
            f"poison:index:{dlq_message.queue_name}",
            {dlq_message.message_id: datetime.now(timezone.utc).timestamp()}
        )

        # Publish poison event
        if self.nats:
            await self._publish_dlq_event(dlq_message, "moved_to_poison")

    async def get_dlq_messages(
        self,
        queue_name: str,
        limit: int = 100,
        include_expired: bool = False
    ) -> List[DLQMessage]:
        """Get messages from DLQ"""
        # Get message IDs from index
        if include_expired:
            message_ids = await self.redis.zrange(
                f"{self.config.redis_key_prefix}:index:{queue_name}",
                0,
                limit - 1
            )
        else:
            # Only get messages ready for retry
            max_score = datetime.now(timezone.utc).timestamp()
            message_ids = await self.redis.zrangebyscore(
                f"{self.config.redis_key_prefix}:index:{queue_name}",
                0,
                max_score,
                start=0,
                num=limit
            )

        messages = []
        for message_id in message_ids:
            dlq_key = f"{self.config.redis_key_prefix}:{queue_name}:{message_id.decode() if isinstance(message_id, bytes) else message_id}"
            message_data = await self.redis.get(dlq_key)

            if message_data:
                try:
                    dlq_message = DLQMessage.from_dict(json.loads(message_data))

                    # Calculate message age
                    age = (datetime.now(timezone.utc) - dlq_message.first_failure_time).total_seconds()
                    dlq_age.labels(queue=queue_name).observe(age)

                    messages.append(dlq_message)
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    logger.error(f"Error deserializing DLQ message: {e}")

        return messages

    async def start_retry_processor(self):
        """Start background retry processor"""
        if self._running:
            return

        self._running = True

        # Start processor for each registered queue
        for queue_name in self.message_handlers.keys():
            task = asyncio.create_task(self._process_queue_retries(queue_name))
            self._tasks.append(task)

        logger.info("DLQ retry processor started")

    async def stop_retry_processor(self):
        """Stop background retry processor"""
        self._running = False

        # Cancel all tasks
        for task in self._tasks:
            task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        logger.info("DLQ retry processor stopped")

    async def _process_queue_retries(self, queue_name: str):
        """Process retries for a specific queue"""
        logger.info(f"Starting retry processor for queue: {queue_name}")

        while self._running:
            try:
                # Get messages ready for retry
                messages = await self.get_dlq_messages(queue_name, limit=10, include_expired=False)

                for message in messages:
                    if message.next_retry_time and message.next_retry_time <= datetime.now(timezone.utc):
                        # Retry the message
                        asyncio.create_task(self.retry_message(queue_name, message.message_id))

                # Sleep before next check
                await asyncio.sleep(10)

            except redis.RedisError as e:
                logger.error(f"Redis error in retry processor for queue {queue_name}: {e}")
                await asyncio.sleep(30)
            except (ConnectionError, TimeoutError) as e:
                logger.error(f"Network error in retry processor for queue {queue_name}: {e}")
                await asyncio.sleep(30)
            except RuntimeError as e:
                logger.error(f"Runtime error in retry processor for queue {queue_name}: {e}")
                await asyncio.sleep(30)

    async def _update_queue_size(self, queue_name: str):
        """Update queue size metric"""
        size = await self.redis.zcard(f"{self.config.redis_key_prefix}:index:{queue_name}")
        dlq_size.labels(queue=queue_name).set(size)

    async def _publish_dlq_event(self, dlq_message: DLQMessage, event_type: str):
        """Publish DLQ event to NATS"""
        if not self.nats:
            return

        topic = f"dlq.{dlq_message.queue_name}.{event_type}"
        
        if event_type == "moved_to_poison":
            topic = f"dlq.{dlq_message.queue_name}.poison"

        await self.nats.publish(
            topic,
            {
                'message_id': dlq_message.message_id,
                'reason': dlq_message.reason.value,
                'retry_count': dlq_message.retry_count,
                'queue_name': dlq_message.queue_name,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'event_type': event_type
            }
        )

    async def get_dlq_stats(self) -> Dict[str, Any]:
        """Get DLQ statistics"""
        stats = {
            'queues': {},
            'total_messages': 0,
            'total_poison_messages': 0
        }

        # Get all queue patterns
        queue_patterns = await self.redis.keys(f"{self.config.redis_key_prefix}:index:*")

        for pattern in queue_patterns:
            queue_name = pattern.decode().replace(f"{self.config.redis_key_prefix}:index:", "")
            queue_size = await self.redis.zcard(pattern)

            # Get poison queue size
            poison_size = await self.redis.zcard(f"poison:index:{queue_name}")

            stats['queues'][queue_name] = {
                'size': queue_size,
                'poison_size': poison_size
            }

            stats['total_messages'] += queue_size
            stats['total_poison_messages'] += poison_size

        return stats

    async def replay_messages(
        self,
        queue_name: str,
        status: Optional[MessageStatus] = None,
        limit: Optional[int] = None
    ) -> int:
        """Replay messages from DLQ - reset them for retry"""
        messages = await self.get_dlq_messages(queue_name, limit=limit or 1000)
        
        replayed = 0
        for message in messages:
            # Filter by status if specified
            if status and message.status != status:
                continue
                
            # Reset message for retry
            message.status = MessageStatus.PENDING
            message.retry_count = 0
            message.error_details = None
            message.stack_trace = None
            message.next_retry_time = datetime.now(timezone.utc)
            
            # Update in Redis
            dlq_key = f"{self.config.redis_key_prefix}:{queue_name}:{message.message_id}"
            await self.redis.set(
                dlq_key,
                json.dumps(message.to_dict()),
                ex=self.config.ttl
            )
            
            replayed += 1
            
        logger.info(f"Replayed {replayed} messages in DLQ {queue_name}")
        return replayed

    async def purge_messages(
        self,
        queue_name: str,
        status: Optional[MessageStatus] = None,
        older_than_hours: Optional[int] = None
    ) -> int:
        """Purge messages from DLQ"""
        messages = await self.get_dlq_messages(queue_name, limit=10000, include_expired=True)
        
        purged = 0
        cutoff_time = None
        if older_than_hours:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
        
        for message in messages:
            # Filter by status if specified
            if status and message.status != status:
                continue
                
            # Filter by age if specified
            if cutoff_time and message.first_failure_time > cutoff_time:
                continue
                
            # Delete message
            await self.remove_from_dlq(queue_name, message.message_id)
            purged += 1
            
        logger.info(f"Purged {purged} messages from DLQ {queue_name}")
        return purged


class ActionDLQHandler(DLQHandler):
    """Action-specific DLQ handler with NATS integration"""

    def __init__(
        self,
        redis_client: redis.Redis,
        config: DLQConfig,
        nats_client: Optional[NATSClient] = None
    ):
        # Set action-specific defaults
        if not config.redis_key_prefix:
            config.redis_key_prefix = "action_dlq"
        if not config.metrics_namespace:
            config.metrics_namespace = "action_dlq"
            
        super().__init__(redis_client, config, nats_client)

    async def _publish_dlq_event(self, dlq_message: DLQMessage, event_type: str):
        """Action-specific event publishing"""
        if not self.nats:
            return

        # Action-specific topic structure
        if event_type == "moved_to_poison":
            topic = f"dlq.{dlq_message.queue_name}.poison"
        else:
            topic = f"dlq.{dlq_message.queue_name}.{event_type}"

        await self.nats.publish(
            topic,
            {
                'message_id': dlq_message.message_id,
                'reason': dlq_message.reason.value,
                'retry_count': dlq_message.retry_count,
                'queue_name': dlq_message.queue_name,
                'action_type_id': dlq_message.original_message.get('action_type_id'),
                'object_ids': dlq_message.original_message.get('object_ids', []),
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'event_type': event_type
            }
        )