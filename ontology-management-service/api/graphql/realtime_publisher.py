"""
GraphQL Realtime Publisher
Real-time event publishing and subscription management
"""

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncIterator, Dict, Optional, Set

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Real-time event types"""

    SCHEMA_CHANGED = "schema_changed"
    BRANCH_UPDATED = "branch_updated"
    ACTION_PROGRESS = "action_progress"
    PROPOSAL_UPDATED = "proposal_updated"
    USER_NOTIFICATION = "user_notification"


@dataclass
class RealtimeEvent:
    """Real-time event"""

    event_type: EventType
    payload: Dict[str, Any]
    user_id: Optional[str] = None
    timestamp: float = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


class RealtimeSubscription:
    """Real-time subscription"""

    def __init__(self, subscription_id: str, user_id: str, event_types: Set[EventType]):
        self.subscription_id = subscription_id
        self.user_id = user_id
        self.event_types = event_types
        self.queue: asyncio.Queue = asyncio.Queue()
        self.created_at = time.time()
        self.last_activity = time.time()

    async def send_event(self, event: RealtimeEvent):
        """Send event"""
        if event.event_type in self.event_types:
            if event.user_id is None or event.user_id == self.user_id:
                await self.queue.put(event)
                self.last_activity = time.time()

    async def get_events(self) -> AsyncIterator[RealtimeEvent]:
        """Receive events"""
        while True:
            try:
                event = await asyncio.wait_for(self.queue.get(), timeout=30.0)
                yield event
            except asyncio.TimeoutError:
                # Keepalive
                keepalive_event = RealtimeEvent(
                    event_type=EventType.USER_NOTIFICATION,
                    payload={"type": "keepalive"},
                    user_id=self.user_id,
                )
                yield keepalive_event


class RealtimePublisher:
    """Real-time publisher"""

    def __init__(self):
        self.subscriptions: Dict[str, RealtimeSubscription] = {}
        self.user_subscriptions: Dict[str, Set[str]] = {}
        self._cleanup_task = None
        self.nc: Optional[object] = None
        self._connected = False
        # Don't start cleanup task in __init__ to avoid event loop issues

    def _start_cleanup_task(self):
        """Start cleanup task"""

        async def cleanup_stale_subscriptions():
            while True:
                try:
                    await asyncio.sleep(60)  # Clean up every minute
                    current_time = time.time()
                    stale_subscriptions = []

                    for sub_id, subscription in self.subscriptions.items():
                        if (
                            current_time - subscription.last_activity > 300
                        ):  # 5 minutes inactive
                            stale_subscriptions.append(sub_id)

                    for sub_id in stale_subscriptions:
                        await self.unsubscribe(sub_id)

                except Exception as e:
                    logger.error(f"Cleanup task error: {e}")

        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(cleanup_stale_subscriptions())

    async def subscribe(self, user_id: str, event_types: Set[EventType]) -> str:
        """Register subscription"""
        # Start cleanup task on first subscription if not already started
        if self._cleanup_task is None:
            self._start_cleanup_task()

        subscription_id = f"{user_id}_{int(time.time() * 1000)}"
        subscription = RealtimeSubscription(subscription_id, user_id, event_types)

        self.subscriptions[subscription_id] = subscription

        if user_id not in self.user_subscriptions:
            self.user_subscriptions[user_id] = set()
        self.user_subscriptions[user_id].add(subscription_id)

        logger.info(f"Created subscription {subscription_id} for user {user_id}")
        return subscription_id

    async def unsubscribe(self, subscription_id: str):
        """Unregister subscription"""
        if subscription_id in self.subscriptions:
            subscription = self.subscriptions[subscription_id]
            user_id = subscription.user_id

            del self.subscriptions[subscription_id]

            if user_id in self.user_subscriptions:
                self.user_subscriptions[user_id].discard(subscription_id)
                if not self.user_subscriptions[user_id]:
                    del self.user_subscriptions[user_id]

            logger.info(f"Removed subscription {subscription_id}")

    async def publish(self, event: RealtimeEvent):
        """Publish event"""
        logger.debug(
            f"Publishing event {event.event_type} to {len(self.subscriptions)} subscriptions"
        )

        tasks = []
        for subscription in self.subscriptions.values():
            tasks.append(subscription.send_event(event))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def get_subscription_events(
        self, subscription_id: str
    ) -> AsyncIterator[RealtimeEvent]:
        """Subscription event stream"""
        if subscription_id not in self.subscriptions:
            return

        subscription = self.subscriptions[subscription_id]
        async for event in subscription.get_events():
            yield event

    def get_subscription_count(self) -> int:
        """Active subscription count"""
        return len(self.subscriptions)

    def get_user_subscription_count(self, user_id: str) -> int:
        """User subscription count"""
        return len(self.user_subscriptions.get(user_id, set()))

    async def connect(self):
        """NATS JetStream connection (currently dummy implementation).

        Called from GraphQL service lifecycle so it just needs to exist.
        Can be replaced with actual connection logic when using nats-py later.
        """
        if self.nc is None:
            # Mark as connected with dummy object
            self.nc = object()
            self._connected = True
            logger.info("RealtimePublisher dummy connect called - marked as connected")

    async def disconnect(self):
        """NATS connection disconnect (dummy)."""
        if self.nc is not None:
            self.nc = None
            self._connected = False
            logger.info(
                "RealtimePublisher dummy disconnect called - marked as disconnected"
            )

    @asynccontextmanager
    async def connection(self):
        """NATS connection context manager (dummy)."""
        try:
            await self.connect()
            yield self
        finally:
            # Can skip disconnect if persistent connection is needed
            pass


# Global real-time publisher instance
realtime_publisher = RealtimePublisher()


# Convenience functions
async def publish_schema_change(schema_id: str, change_type: str, user_id: str = None):
    """Publish schema change event"""
    event = RealtimeEvent(
        event_type=EventType.SCHEMA_CHANGED,
        payload={
            "schema_id": schema_id,
            "change_type": change_type,
            "timestamp": time.time(),
        },
        user_id=user_id,
    )
    await realtime_publisher.publish(event)


async def publish_branch_update(branch_name: str, operation: str, user_id: str = None):
    """Publish branch update event"""
    event = RealtimeEvent(
        event_type=EventType.BRANCH_UPDATED,
        payload={
            "branch_name": branch_name,
            "operation": operation,
            "timestamp": time.time(),
        },
        user_id=user_id,
    )
    await realtime_publisher.publish(event)


async def publish_action_progress(
    action_id: str, progress: float, status: str, user_id: str = None
):
    """Publish action progress event"""
    event = RealtimeEvent(
        event_type=EventType.ACTION_PROGRESS,
        payload={
            "action_id": action_id,
            "progress": progress,
            "status": status,
            "timestamp": time.time(),
        },
        user_id=user_id,
    )
    await realtime_publisher.publish(event)
