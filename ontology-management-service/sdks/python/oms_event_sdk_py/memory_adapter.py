"""
In-memory adapter for OMS Event SDK
Used for testing and development when NATS is not available
"""
import asyncio
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List

from .models import PublishResult, Subscription

logger = logging.getLogger(__name__)


class InMemoryPublisher:
 """In-memory implementation of EventPublisher for testing"""

 def __init__(self):
 self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
 self._message_history: List[Dict[str, Any]] = []

 async def publish(self, channel: str, payload: Any) -> PublishResult:
 """Publish message to in-memory channel"""
 try:
 # Convert payload to dict
 if hasattr(payload, "dict"):
 data = payload.dict()
 elif isinstance(payload, dict):
 data = payload
 else:
 data = {"data": str(payload)}

 # Store in history
 self._message_history.append({"channel": channel, "payload": data})

 # Notify subscribers
 for handler in self._subscribers.get(channel, []):
 try:
 await handler(data)
 except Exception as e:
 logger.error(f"Handler error: {e}")

 logger.debug(f"Published in-memory message to channel: {channel}")

 return PublishResult(
 success = True,
 message_id = str(len(self._message_history) - 1),
 channel = channel,
 )

 except Exception as e:
 logger.error(f"Failed to publish in-memory: {e}")
 return PublishResult(
 success = False, message_id = None, channel = channel, error = str(e)
 )

 def add_subscriber(self, channel: str, handler: Callable):
 """Add subscriber to channel"""
 self._subscribers[channel].append(handler)

 def remove_subscriber(self, channel: str, handler: Callable):
 """Remove subscriber from channel"""
 if channel in self._subscribers:
 self._subscribers[channel].remove(handler)


class InMemorySubscriber:
 """In-memory implementation of EventSubscriber for testing"""

 def __init__(self, publisher: InMemoryPublisher):
 self.publisher = publisher
 self._subscriptions = []

 async def subscribe(
 self, channel: str, handler: Callable[[Any], Awaitable[None]]
 ) -> Subscription:
 """Subscribe to in-memory channel"""
 try:
 # Add handler to publisher
 self.publisher.add_subscriber(channel, handler)

 # Create subscription
 sub = InMemorySubscription(channel, handler, self.publisher)
 self._subscriptions.append(sub)

 logger.info(f"Subscribed to in-memory channel: {channel}")

 return sub

 except Exception as e:
 logger.error(f"Failed to subscribe in-memory: {e}")
 raise

 async def close(self):
 """Close all subscriptions"""
 for sub in self._subscriptions:
 await sub.unsubscribe()
 self._subscriptions.clear()


@dataclass
class InMemorySubscription(Subscription):
 """In-memory subscription implementation"""

 channel: str
 handler: Callable
 publisher: InMemoryPublisher = field(repr = False)

 async def unsubscribe(self):
 """Unsubscribe from channel"""
 self.publisher.remove_subscriber(self.channel, self.handler)
 logger.info(f"Unsubscribed from in-memory channel: {self.channel}")
