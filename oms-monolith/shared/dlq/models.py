"""
Unified DLQ models consolidating core/action and middleware implementations.
"""

import json
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Callable


class DLQReason(Enum):
    """Consolidated reasons for sending message to DLQ"""
    VALIDATION_FAILED = "validation_failed"
    EXECUTION_FAILED = "execution_failed"
    TIMEOUT = "timeout"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    PLUGIN_ERROR = "plugin_error"
    WEBHOOK_FAILED = "webhook_failed"
    MAX_RETRIES_EXCEEDED = "max_retries_exceeded"
    POISON_MESSAGE = "poison_message"
    UNKNOWN_ERROR = "unknown_error"
    NETWORK_ERROR = "network_error"
    AUTHENTICATION_ERROR = "authentication_error"


class MessageStatus(Enum):
    """Message status in DLQ - consolidated from middleware version"""
    PENDING = "pending"
    PROCESSING = "processing"
    RETRYING = "retrying"
    FAILED = "failed"
    POISON = "poison"
    EXPIRED = "expired"
    SUCCEEDED = "succeeded"


@dataclass
class DLQMessage:
    """Unified DLQ message structure"""
    message_id: str
    queue_name: str
    original_message: Dict[str, Any]
    reason: DLQReason
    error_details: str
    stack_trace: Optional[str]
    retry_count: int
    max_retries: int
    first_failure_time: datetime
    last_failure_time: datetime
    next_retry_time: Optional[datetime]
    status: MessageStatus = MessageStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_history: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['reason'] = self.reason.value
        data['status'] = self.status.value
        data['first_failure_time'] = self.first_failure_time.isoformat()
        data['last_failure_time'] = self.last_failure_time.isoformat()
        data['next_retry_time'] = self.next_retry_time.isoformat() if self.next_retry_time else None
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DLQMessage':
        """Create from dictionary"""
        data = data.copy()
        data['reason'] = DLQReason(data['reason'])
        data['status'] = MessageStatus(data.get('status', 'pending'))
        data['first_failure_time'] = datetime.fromisoformat(data['first_failure_time'])
        data['last_failure_time'] = datetime.fromisoformat(data['last_failure_time'])
        if data.get('next_retry_time'):
            data['next_retry_time'] = datetime.fromisoformat(data['next_retry_time'])
        return cls(**data)

    def add_error(self, error: str, details: Optional[Dict[str, Any]] = None):
        """Add error to history"""
        self.error_details = error
        self.error_history.append({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'error': error,
            'details': details or {},
            'retry_count': self.retry_count
        })

    def should_retry(self) -> bool:
        """Check if message should be retried"""
        return (
            self.retry_count < self.max_retries and
            self.status not in [MessageStatus.POISON, MessageStatus.EXPIRED, MessageStatus.SUCCEEDED]
        )


class RetryPolicy:
    """Configurable retry policy for DLQ messages"""

    def __init__(
        self,
        max_retries: int = 5,
        initial_delay: int = 60,  # seconds
        max_delay: int = 3600,    # 1 hour
        backoff_multiplier: float = 2.0,
        jitter: bool = True
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_multiplier = backoff_multiplier
        self.jitter = jitter

    def get_next_retry_time(self, retry_count: int) -> Optional[datetime]:
        """Calculate next retry time based on retry count"""
        if retry_count >= self.max_retries:
            return None

        # Exponential backoff
        delay = min(
            self.initial_delay * (self.backoff_multiplier ** retry_count),
            self.max_delay
        )

        # Add jitter to prevent thundering herd
        if self.jitter:
            import random
            delay = delay * (0.5 + random.random())

        return datetime.now(timezone.utc) + timedelta(seconds=delay)


# Specialized retry policies for different scenarios
WEBHOOK_RETRY_POLICY = RetryPolicy(
    max_retries=3,
    initial_delay=30,
    max_delay=300,
    backoff_multiplier=2.0
)

VALIDATION_RETRY_POLICY = RetryPolicy(
    max_retries=1,  # Validation errors rarely recover
    initial_delay=60,
    max_delay=60,
    backoff_multiplier=1.0
)

EXECUTION_RETRY_POLICY = RetryPolicy(
    max_retries=5,
    initial_delay=60,
    max_delay=1800,  # 30 minutes
    backoff_multiplier=3.0
)

NETWORK_RETRY_POLICY = RetryPolicy(
    max_retries=3,
    initial_delay=5,
    max_delay=60,
    backoff_multiplier=2.0
)