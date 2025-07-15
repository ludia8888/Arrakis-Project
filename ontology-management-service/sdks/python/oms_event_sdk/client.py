"""
Auto-generated Python client for oms-event-sdk
Generated at: 2025-06-25T11:15:14.778609
DO NOT EDIT - This file is auto-generated
"""

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

from .models import *


@dataclass
class ClientConfig:
 """Client configuration"""

 nats_url: Optional[str] = None
 websocket_url: Optional[str] = None
 http_url: Optional[str] = None
 credentials: Optional[Dict[str, str]] = None


class EventPublisher:
 """Abstract event publisher interface"""

 async def publish(self, channel: str, payload: Any) -> PublishResult:
 """Publish event to channel"""
 import json
 import time
 import uuid

 # Default implementation using HTTP fallback
 try:
 import os

 import httpx

 # Try to use configured event gateway
 event_gateway_url = os.getenv("EVENT_GATEWAY_URL", "http://oms:8000/events")

 event_data = {
 "channel": channel,
 "payload": payload,
 "timestamp": time.time(),
 "message_id": str(uuid.uuid4()),
 "publisher": "oms-event-sdk",
 }

 async with httpx.AsyncClient() as client:
 response = await client.post(
 f"{event_gateway_url}/publish", json = event_data, timeout = 10.0
 )

 if response.status_code == 200:
 return PublishResult(
 success = True,
 message_id = event_data["message_id"],
 timestamp = event_data["timestamp"],
 )
 else:
 return PublishResult(
 success = False,
 error = f"HTTP {response.status_code}: {response.text}",
 message_id = event_data["message_id"],
 )

 except Exception as e:
 return PublishResult(
 success = False, error = str(e), message_id = str(uuid.uuid4())
 )


class EventSubscriber:
 """Abstract event subscriber interface"""

 async def subscribe(
 self, channel: str, handler: Callable[[Any], Awaitable[None]]
 ) -> Subscription:
 """Subscribe to events on a channel"""
 import asyncio
 import json
 import os
 import time
 import uuid

 subscription_id = str(uuid.uuid4())

 # Production WebSocket connection - no fallbacks
 websocket_url = os.getenv("EVENT_WEBSOCKET_URL", "ws://oms:8000/events/ws")

 # Production import - websockets must be available
 import websockets

 async def websocket_subscriber():
 async with websockets.connect(
 f"{websocket_url}?channel={channel}"
 ) as websocket:
 await websocket.send(
 json.dumps(
 {
 "action": "subscribe",
 "channel": channel,
 "subscription_id": subscription_id,
 }
 )
 )

 async for message in websocket:
 data = json.loads(message)
 await handler(data.get("payload"))

 # Start the WebSocket subscriber in background
 task = asyncio.create_task(websocket_subscriber())

 return Subscription(
 id = subscription_id,
 channel = channel,
 active = True,
 transport = "websocket",
 task = task,
 )

 async def _polling_subscriber(
 self,
 channel: str,
 handler: Callable[[Any], Awaitable[None]],
 subscription_id: str,
 ) -> Subscription:
 """Fallback polling-based subscription"""
 import asyncio
 import os

 import httpx

 event_gateway_url = os.getenv("EVENT_GATEWAY_URL", "http://oms:8000/events")
 poll_interval = float(os.getenv("EVENT_POLL_INTERVAL", "5.0"))

 async def polling_loop():
 last_timestamp = time.time()

 while True:
 try:
 async with httpx.AsyncClient() as client:
 response = await client.get(
 f"{event_gateway_url}/poll",
 params={
 "channel": channel,
 "since": last_timestamp,
 "subscription_id": subscription_id,
 },
 timeout = 10.0,
 )

 if response.status_code == 200:
 events = response.json().get("events", [])
 for event in events:
 try:
 await handler(event.get("payload"))
 last_timestamp = max(
 last_timestamp,
 event.get("timestamp", last_timestamp),
 )
 except Exception as e:
 print(f"Error handling polled event: {e}")

 await asyncio.sleep(poll_interval)

 except Exception as e:
 print(f"Polling error: {e}")
 await asyncio.sleep(poll_interval)

 # Start polling in background
 task = asyncio.create_task(polling_loop())

 return Subscription(
 id = subscription_id,
 channel = channel,
 active = True,
 transport = "polling",
 task = task,
 )


class OMSEventClient:
 """
 Auto-generated OMS Event API client

 This client provides typed methods for all AsyncAPI operations.
 """

 def __init__(self, publisher: EventPublisher, subscriber: EventSubscriber):
 self.publisher = publisher
 self.subscriber = subscriber

 @classmethod
 async def connect(cls, config: ClientConfig = None) -> "OMSEventClient":
 """
 Create client with appropriate adapters

 Args:
 config: Client configuration

 Returns:
 Connected client instance
 """
 if config is None:
 config = ClientConfig()

 # Default URLs from AsyncAPI spec
 nats_url = config.nats_url or "nats://nats.oms.company.com:4222"
 ws_url = config.websocket_url or "ws://localhost:8080"

 # Create concrete implementations of publisher and subscriber
 publisher = EventPublisher()
 subscriber = EventSubscriber()

 # Create and return the client
 client = cls(publisher, subscriber)

 # Test connection to verify it's working
 await client._test_connection(config)

 return client

 async def _test_connection(self, config: ClientConfig):
 """Test the connection to event services"""
 import time

 try:
 # Test publish capability
 test_result = await self.publisher.publish(
 "_test_channel",
 {"test": True, "timestamp": time.time(), "source": "oms-event-sdk"},
 )

 if not test_result.success:
 print(f"Warning: Event publishing test failed: {test_result.error}")

 except Exception as e:
 print(f"Warning: Event connection test failed: {e}")

 # Generated client methods

 async def publishschemacreated(self, payload: Schemacreated) -> PublishResult:
 """
 Publish Schema Created

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("oms.schema.created.{branch}", payload)

 async def publisheventbridgeschemacreated(
 self, payload: SchemacreatedEventBridge
 ) -> PublishResult:
 """
 Publish Schema Created to EventBridge

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("eventbridge/schema/created", payload)

 async def publishschemaupdated(self, payload: Schemaupdated) -> PublishResult:
 """
 Publish Schema Updated

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("oms.schema.updated.{branch}", payload)

 async def publisheventbridgeschemaupdated(
 self, payload: SchemaupdatedEventBridge
 ) -> PublishResult:
 """
 Publish Schema Updated to EventBridge

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("eventbridge/schema/updated", payload)

 async def publishschemadeleted(self, payload: Schemadeleted) -> PublishResult:
 """
 Publish Schema Deleted

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("oms.schema.deleted.{branch}", payload)

 async def publisheventbridgeschemadeleted(
 self, payload: SchemadeletedEventBridge
 ) -> PublishResult:
 """
 Publish Schema Deleted to EventBridge

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("eventbridge/schema/deleted", payload)

 async def publishschemavalidated(self, payload: Schemavalidated) -> PublishResult:
 """
 Publish Schema Validated

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("oms.schema.validated.{branch}", payload)

 async def publisheventbridgeschemavalidated(
 self, payload: SchemavalidatedEventBridge
 ) -> PublishResult:
 """
 Publish Schema Validated to EventBridge

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("eventbridge/schema/validated", payload)

 async def publishobjecttypecreated(
 self, payload: Objecttypecreated
 ) -> PublishResult:
 """
 Publish Object Type Created

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish(
 "oms.objecttype.created.{branch}.{resourceId}", payload
 )

 async def publisheventbridgeobjecttypecreated(
 self, payload: ObjecttypecreatedEventBridge
 ) -> PublishResult:
 """
 Publish Object Type Created to EventBridge

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("eventbridge/objecttype/created", payload)

 async def publishobjecttypeupdated(
 self, payload: Objecttypeupdated
 ) -> PublishResult:
 """
 Publish Object Type Updated

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish(
 "oms.objecttype.updated.{branch}.{resourceId}", payload
 )

 async def publisheventbridgeobjecttypeupdated(
 self, payload: ObjecttypeupdatedEventBridge
 ) -> PublishResult:
 """
 Publish Object Type Updated to EventBridge

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("eventbridge/objecttype/updated", payload)

 async def publishobjecttypedeleted(
 self, payload: Objecttypedeleted
 ) -> PublishResult:
 """
 Publish Object Type Deleted

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish(
 "oms.objecttype.deleted.{branch}.{resourceId}", payload
 )

 async def publisheventbridgeobjecttypedeleted(
 self, payload: ObjecttypedeletedEventBridge
 ) -> PublishResult:
 """
 Publish Object Type Deleted to EventBridge

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("eventbridge/objecttype/deleted", payload)

 async def publishpropertycreated(self, payload: Propertycreated) -> PublishResult:
 """
 Publish Property Created

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish(
 "oms.property.created.{branch}.{resourceId}", payload
 )

 async def publisheventbridgepropertycreated(
 self, payload: PropertycreatedEventBridge
 ) -> PublishResult:
 """
 Publish Property Created to EventBridge

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("eventbridge/property/created", payload)

 async def publishpropertyupdated(self, payload: Propertyupdated) -> PublishResult:
 """
 Publish Property Updated

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish(
 "oms.property.updated.{branch}.{resourceId}", payload
 )

 async def publisheventbridgepropertyupdated(
 self, payload: PropertyupdatedEventBridge
 ) -> PublishResult:
 """
 Publish Property Updated to EventBridge

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("eventbridge/property/updated", payload)

 async def publishpropertydeleted(self, payload: Propertydeleted) -> PublishResult:
 """
 Publish Property Deleted

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish(
 "oms.property.deleted.{branch}.{resourceId}", payload
 )

 async def publisheventbridgepropertydeleted(
 self, payload: PropertydeletedEventBridge
 ) -> PublishResult:
 """
 Publish Property Deleted to EventBridge

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("eventbridge/property/deleted", payload)

 async def publishlinktypecreated(self, payload: Linktypecreated) -> PublishResult:
 """
 Publish Link Type Created

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish(
 "oms.linktype.created.{branch}.{resourceId}", payload
 )

 async def publisheventbridgelinktypecreated(
 self, payload: LinktypecreatedEventBridge
 ) -> PublishResult:
 """
 Publish Link Type Created to EventBridge

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("eventbridge/linktype/created", payload)

 async def publishlinktypeupdated(self, payload: Linktypeupdated) -> PublishResult:
 """
 Publish Link Type Updated

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish(
 "oms.linktype.updated.{branch}.{resourceId}", payload
 )

 async def publisheventbridgelinktypeupdated(
 self, payload: LinktypeupdatedEventBridge
 ) -> PublishResult:
 """
 Publish Link Type Updated to EventBridge

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("eventbridge/linktype/updated", payload)

 async def publishlinktypedeleted(self, payload: Linktypedeleted) -> PublishResult:
 """
 Publish Link Type Deleted

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish(
 "oms.linktype.deleted.{branch}.{resourceId}", payload
 )

 async def publisheventbridgelinktypedeleted(
 self, payload: LinktypedeletedEventBridge
 ) -> PublishResult:
 """
 Publish Link Type Deleted to EventBridge

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("eventbridge/linktype/deleted", payload)

 async def publishbranchcreated(self, payload: Branchcreated) -> PublishResult:
 """
 Publish Branch Created

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("oms.branch.created.{branchName}", payload)

 async def publisheventbridgebranchcreated(
 self, payload: BranchcreatedEventBridge
 ) -> PublishResult:
 """
 Publish Branch Created to EventBridge

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("eventbridge/branch/created", payload)

 async def publishbranchupdated(self, payload: Branchupdated) -> PublishResult:
 """
 Publish Branch Updated

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("oms.branch.updated.{branchName}", payload)

 async def publisheventbridgebranchupdated(
 self, payload: BranchupdatedEventBridge
 ) -> PublishResult:
 """
 Publish Branch Updated to EventBridge

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("eventbridge/branch/updated", payload)

 async def publishbranchdeleted(self, payload: Branchdeleted) -> PublishResult:
 """
 Publish Branch Deleted

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("oms.branch.deleted.{branchName}", payload)

 async def publisheventbridgebranchdeleted(
 self, payload: BranchdeletedEventBridge
 ) -> PublishResult:
 """
 Publish Branch Deleted to EventBridge

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("eventbridge/branch/deleted", payload)

 async def publishbranchmerged(self, payload: Branchmerged) -> PublishResult:
 """
 Publish Branch Merged

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("oms.branch.merged.{branchName}", payload)

 async def publisheventbridgebranchmerged(
 self, payload: BranchmergedEventBridge
 ) -> PublishResult:
 """
 Publish Branch Merged to EventBridge

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("eventbridge/branch/merged", payload)

 async def publishproposalcreated(self, payload: Proposalcreated) -> PublishResult:
 """
 Publish Proposal Created

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("oms.proposal.created.{branch}", payload)

 async def publisheventbridgeproposalcreated(
 self, payload: ProposalcreatedEventBridge
 ) -> PublishResult:
 """
 Publish Proposal Created to EventBridge

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("eventbridge/proposal/created", payload)

 async def publishproposalupdated(self, payload: Proposalupdated) -> PublishResult:
 """
 Publish Proposal Updated

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("oms.proposal.updated.{branch}", payload)

 async def publisheventbridgeproposalupdated(
 self, payload: ProposalupdatedEventBridge
 ) -> PublishResult:
 """
 Publish Proposal Updated to EventBridge

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("eventbridge/proposal/updated", payload)

 async def publishproposalapproved(self, payload: Proposalapproved) -> PublishResult:
 """
 Publish Proposal Approved

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("oms.proposal.approved.{branch}", payload)

 async def publisheventbridgeproposalapproved(
 self, payload: ProposalapprovedEventBridge
 ) -> PublishResult:
 """
 Publish Proposal Approved to EventBridge

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("eventbridge/proposal/approved", payload)

 async def publishproposalrejected(self, payload: Proposalrejected) -> PublishResult:
 """
 Publish Proposal Rejected

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("oms.proposal.rejected.{branch}", payload)

 async def publisheventbridgeproposalrejected(
 self, payload: ProposalrejectedEventBridge
 ) -> PublishResult:
 """
 Publish Proposal Rejected to EventBridge

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("eventbridge/proposal/rejected", payload)

 async def publishproposalmerged(self, payload: Proposalmerged) -> PublishResult:
 """
 Publish Proposal Merged

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("oms.proposal.merged.{branch}", payload)

 async def publisheventbridgeproposalmerged(
 self, payload: ProposalmergedEventBridge
 ) -> PublishResult:
 """
 Publish Proposal Merged to EventBridge

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("eventbridge/proposal/merged", payload)

 async def publishactionstarted(self, payload: Actionstarted) -> PublishResult:
 """
 Publish Action Started

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("oms.action.started.{jobId}", payload)

 async def publisheventbridgeactionstarted(
 self, payload: ActionstartedEventBridge
 ) -> PublishResult:
 """
 Publish Action Started to EventBridge

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("eventbridge/action/started", payload)

 async def publishactioncompleted(self, payload: Actioncompleted) -> PublishResult:
 """
 Publish Action Completed

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("oms.action.completed.{jobId}", payload)

 async def publisheventbridgeactioncompleted(
 self, payload: ActioncompletedEventBridge
 ) -> PublishResult:
 """
 Publish Action Completed to EventBridge

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("eventbridge/action/completed", payload)

 async def publishactionfailed(self, payload: Actionfailed) -> PublishResult:
 """
 Publish Action Failed

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("oms.action.failed.{jobId}", payload)

 async def publisheventbridgeactionfailed(
 self, payload: ActionfailedEventBridge
 ) -> PublishResult:
 """
 Publish Action Failed to EventBridge

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("eventbridge/action/failed", payload)

 async def publishactioncancelled(self, payload: Actioncancelled) -> PublishResult:
 """
 Publish Action Cancelled

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("oms.action.cancelled.{jobId}", payload)

 async def publisheventbridgeactioncancelled(
 self, payload: ActioncancelledEventBridge
 ) -> PublishResult:
 """
 Publish Action Cancelled to EventBridge

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("eventbridge/action/cancelled", payload)

 async def publishsystemhealthcheck(
 self, payload: Systemhealthcheck
 ) -> PublishResult:
 """
 Publish System Health Check

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("oms.system.healthcheck.{branch}", payload)

 async def publisheventbridgesystemhealthcheck(
 self, payload: SystemhealthcheckEventBridge
 ) -> PublishResult:
 """
 Publish System Health Check to EventBridge

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("eventbridge/system/healthcheck", payload)

 async def publishsystemerror(self, payload: Systemerror) -> PublishResult:
 """
 Publish System Error

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("oms.system.error.{branch}", payload)

 async def publisheventbridgesystemerror(
 self, payload: SystemerrorEventBridge
 ) -> PublishResult:
 """
 Publish System Error to EventBridge

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("eventbridge/system/error", payload)

 async def publishsystemmaintenance(
 self, payload: Systemmaintenance
 ) -> PublishResult:
 """
 Publish System Maintenance

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("oms.system.maintenance.{branch}", payload)

 async def publisheventbridgesystemmaintenance(
 self, payload: SystemmaintenanceEventBridge
 ) -> PublishResult:
 """
 Publish System Maintenance to EventBridge

 Args:
 payload: Message payload

 Returns:
 PublishResult with success status
 """
 return await self.publisher.publish("eventbridge/system/maintenance", payload)

 async def close(self) -> None:
 """Close all connections and cleanup resources"""
 # Implementation depends on transport
 pass
