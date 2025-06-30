# Shared DLQ (Dead Letter Queue) Package

## Overview

This package provides a unified Dead Letter Queue implementation for the OMS monolith, consolidating previously duplicated DLQ handlers across different modules.

## Features

- **Unified DLQ Handler**: Single implementation for all DLQ operations
- **Retry Policies**: Configurable retry strategies with exponential backoff
- **Circuit Breaker**: Integrated circuit breaker pattern for fault tolerance
- **Message Categorization**: Automatic categorization of failures by reason
- **Poison Queue**: Automatic detection and quarantine of poison messages
- **Metrics**: Prometheus metrics for monitoring DLQ operations
- **Action-Specific Extensions**: Specialized handler for Action Service integration

## Usage

### Basic DLQ Handler

```python
from shared.dlq import DLQHandler, DLQConfig, DLQReason
import redis.asyncio as redis

# Create configuration
config = DLQConfig(
    name="my_service",
    max_retries=5,
    redis_key_prefix="myservice_dlq"
)

# Initialize handler
redis_client = redis.Redis.from_url("redis://localhost:6379")
dlq_handler = DLQHandler(redis_client, config)

# Send message to DLQ
try:
    # ... operation that might fail ...
except Exception as e:
    await dlq_handler.send_to_dlq(
        queue_name="processing_queue",
        original_message={"data": "example"},
        reason=DLQReason.EXECUTION_FAILED,
        error=e,
        metadata={"operation": "data_processing"}
    )
```

### Action Service DLQ Handler

```python
from shared.dlq import ActionDLQHandler, DLQConfig

# Action-specific configuration
config = DLQConfig(
    name="actions_service",
    max_retries=3,
    redis_key_prefix="action_dlq"
)

# Initialize with NATS support
dlq_handler = ActionDLQHandler(redis_client, config, nats_client)

# Automatically publishes to action-specific NATS topics
await dlq_handler.send_to_dlq(
    queue_name="action_execution",
    original_message={
        "action_type_id": "update_user",
        "object_ids": ["user123"],
        "parameters": {"status": "active"}
    },
    reason=DLQReason.WEBHOOK_FAILED,
    error=webhook_error
)
```

### Retry Policies

```python
from shared.dlq.models import RetryPolicy

# Custom retry policy
custom_policy = RetryPolicy(
    max_retries=10,
    initial_delay=5,      # 5 seconds
    max_delay=3600,       # 1 hour
    backoff_multiplier=1.5,
    jitter=True
)

# Pre-configured policies
from shared.dlq.models import WEBHOOK_RETRY_POLICY, EXECUTION_RETRY_POLICY
```

### DLQ Message Recovery

```python
# Register a retry handler
async def process_message(message):
    # Process the recovered message
    print(f"Processing recovered message: {message}")

dlq_handler.register_handler("processing_queue", process_message)

# Start automatic retry processor
await dlq_handler.start_retry_processor()

# Manual retry
success = await dlq_handler.retry_message("processing_queue", message_id)

# Get DLQ statistics
stats = await dlq_handler.get_dlq_stats()
print(f"Total messages in DLQ: {stats['total_messages']}")
print(f"Poison messages: {stats['total_poison_messages']}")
```

## DLQ Reasons

The following failure reasons are supported:

- `VALIDATION_FAILED`: Input validation errors
- `EXECUTION_FAILED`: Business logic failures
- `TIMEOUT`: Operation timeouts
- `RESOURCE_EXHAUSTED`: Resource limits exceeded
- `PLUGIN_ERROR`: Plugin/extension failures
- `WEBHOOK_FAILED`: External webhook failures
- `MAX_RETRIES_EXCEEDED`: Retry limit reached
- `POISON_MESSAGE`: Unprocessable message
- `NETWORK_ERROR`: Network connectivity issues
- `AUTHENTICATION_ERROR`: Auth/permission failures
- `UNKNOWN_ERROR`: Unclassified errors

## Configuration Options

### DLQConfig

- `name`: Queue name identifier
- `max_retries`: Maximum retry attempts (default: 3)
- `retry_policy`: RetryPolicy instance
- `ttl`: Message TTL in seconds (default: 86400)
- `poison_threshold`: Failures before marking as poison (default: 5)
- `deduplication_window`: Window for duplicate detection (default: 3600)
- `redis_key_prefix`: Redis key namespace (default: "dlq")
- `metrics_namespace`: Prometheus metrics namespace

### RetryPolicy

- `max_retries`: Maximum attempts
- `initial_delay`: First retry delay in seconds
- `max_delay`: Maximum delay between retries
- `backoff_multiplier`: Exponential backoff factor
- `jitter`: Add randomization to prevent thundering herd

## Metrics

The following Prometheus metrics are exposed:

- `dlq_messages_total{queue,reason}`: Total messages sent to DLQ
- `dlq_retry_attempts_total{queue,status}`: Retry attempt outcomes
- `dlq_size{queue}`: Current queue size
- `dlq_message_age_seconds{queue}`: Age of messages in queue
- `dlq_processing_time_seconds{queue}`: Time to process messages

## Migration from Legacy DLQ

If migrating from `core/action/dlq_handler.py`:

```python
# Old
from core.action.dlq_handler import DLQHandler

# New
from shared.dlq import ActionDLQHandler as DLQHandler
```

The API remains compatible, but you'll get deprecation warnings.

## Best Practices

1. **Choose appropriate retry policies**: Use aggressive retries for transient errors, conservative for validation failures
2. **Set reasonable TTLs**: Don't keep failed messages forever
3. **Monitor poison queues**: Set up alerts for poison queue growth
4. **Use structured metadata**: Include context for debugging
5. **Handle DLQ failures**: Have a fallback if DLQ itself fails

## Testing

```python
import pytest
from unittest.mock import AsyncMock
from shared.dlq import DLQHandler, DLQConfig

@pytest.fixture
def mock_redis():
    return AsyncMock()

@pytest.mark.asyncio
async def test_dlq_send(mock_redis):
    config = DLQConfig(name="test")
    handler = DLQHandler(mock_redis, config)
    
    message_id = await handler.send_to_dlq(
        queue_name="test_queue",
        original_message={"test": True},
        reason=DLQReason.VALIDATION_FAILED,
        error=ValueError("Test error")
    )
    
    assert message_id is not None
    assert mock_redis.set.called
```

## Troubleshooting

### Messages not being retried
- Check retry processor is started: `await dlq_handler.start_retry_processor()`
- Verify handler is registered for the queue
- Check message `next_retry_time` hasn't been exceeded

### High poison queue count
- Review error patterns in poison messages
- Check for data quality issues
- Consider adjusting validation rules

### Redis connection issues
- Verify Redis connectivity
- Check Redis memory usage
- Review Redis persistence settings

## Future Enhancements

- Batch retry operations
- Message transformation before retry
- Advanced routing rules
- Dead letter analytics dashboard
- Integration with monitoring systems