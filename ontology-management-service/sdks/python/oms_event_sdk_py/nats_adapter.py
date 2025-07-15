"""
NATS adapter for OMS Event SDK
Production-ready implementation for message publishing and subscribing
"""
import json
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import nats
from nats.aio.client import Client as NATS

from .models import PublishResult, Subscription

logger = logging.getLogger(__name__)


class NATSPublisher:
 """NATS implementation of EventPublisher"""

 def __init__(self, nc: NATS):
 self.nc = nc

 async def publish(self, channel: str, payload: Any) -> PublishResult:
 """Publish message to NATS channel"""
 try:
 # Convert payload to JSON
 if hasattr(payload, "dict"):
 # Pydantic model
 data = json.dumps(payload.dict()).encode()
 elif isinstance(payload, dict):
 data = json.dumps(payload).encode()
 else:
 data = str(payload).encode()

 # Replace channel placeholders with actual values
 # e.g., "oms.schema.created.{branch}" -> "oms.schema.created.main"
 actual_channel = self._resolve_channel(channel, payload)

 # Publish to NATS
 await self.nc.publish(actual_channel, data)

 logger.debug(f"Published message to channel: {actual_channel}")

 return PublishResult(
 success = True,
 message_id = None, # NATS doesn't return message IDs
 channel = actual_channel,
 )

 except Exception as e:
 logger.error(f"Failed to publish to NATS: {e}")
 return PublishResult(
 success = False, message_id = None, channel = channel, error = str(e)
 )

 def _resolve_channel(self, channel_template: str, payload: Any) -> str:
 """Resolve channel placeholders from payload data"""
 channel = channel_template

 # Extract values from payload
 if hasattr(payload, "__dict__"):
 data = payload.__dict__
 elif isinstance(payload, dict):
 data = payload
 else:
 return channel

 # Replace common placeholders
 replacements = {
 "{branch}": data.get("branch", "main"),
 "{branchName}": data.get("branchName", data.get("branch", "main")),
 "{resourceId}": data.get("resourceId", "unknown"),
 "{jobId}": data.get("jobId", "unknown"),
 }

 for placeholder, value in replacements.items():
 if placeholder in channel:
 channel = channel.replace(placeholder, str(value))

 return channel


class NATSSubscriber:
 """NATS implementation of EventSubscriber"""

 def __init__(self, nc: NATS):
 self.nc = nc
 self._subscriptions = []

 async def subscribe(
 self, channel: str, handler: Callable[[Any], Awaitable[None]]
 ) -> Subscription:
 """Subscribe to NATS channel"""
 try:
 # Create subscription
 async def message_handler(msg):
 try:
 # Parse message data
 data = json.loads(msg.data.decode())

 # Call user handler
 await handler(data)

 except json.JSONDecodeError:
 logger.error(f"Failed to decode message from {channel}")
 except Exception as e:
 logger.error(f"Handler error for {channel}: {e}")

 # Subscribe to NATS
 sub = await self.nc.subscribe(channel, cb = message_handler)
 self._subscriptions.append(sub)

 logger.info(f"Subscribed to channel: {channel}")

 # Return subscription object
 return NATSSubscription(sub, channel)

 except Exception as e:
 logger.error(f"Failed to subscribe to NATS: {e}")
 raise

 async def close(self):
 """Close all subscriptions"""
 for sub in self._subscriptions:
 await sub.unsubscribe()
 self._subscriptions.clear()


@dataclass
class NATSSubscription(Subscription):
 """NATS subscription implementation"""

 _sub: Any # NATS subscription object
 channel: str

 async def unsubscribe(self):
 """Unsubscribe from channel"""
 await self._sub.unsubscribe()
 logger.info(f"Unsubscribed from channel: {self.channel}")
