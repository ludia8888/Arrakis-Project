#!/usr/bin/env python3
"""
Complete Immutable Event Store Implementation
============================================
True immutable event log with cryptographic integrity guarantees
"""

import asyncio
import hashlib
import json
import time
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union, AsyncIterator, Tuple
from enum import Enum
import hmac
import base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key
import redis.asyncio as redis
import logging

logger = logging.getLogger(__name__)

class EventType(Enum):
 """Immutable event types"""
 SCHEMA_CREATED = "schema.created"
 SCHEMA_UPDATED = "schema.updated"
 SCHEMA_DELETED = "schema.deleted"
 BRANCH_CREATED = "branch.created"
 BRANCH_MERGED = "branch.merged"
 OBJECT_CREATED = "object.created"
 OBJECT_UPDATED = "object.updated"
 OBJECT_DELETED = "object.deleted"
 LINK_CREATED = "link.created"
 LINK_UPDATED = "link.updated"
 LINK_DELETED = "link.deleted"
 USER_ACTION = "user.action"
 SYSTEM_EVENT = "system.event"
 AGGREGATE_SNAPSHOT = "aggregate.snapshot"

@dataclass(frozen = True)
class ImmutableEventMetadata:
 """Immutable event metadata with cryptographic properties"""
 event_id: str
 event_type: EventType
 aggregate_id: str
 aggregate_version: int
 timestamp: datetime
 correlation_id: str
 causation_id: Optional[str]
 user_id: Optional[str]
 source_service: str
 content_hash: str
 signature: str
 previous_event_hash: Optional[str] = None

 def to_dict(self) -> Dict[str, Any]:
 """Convert to dictionary for storage"""
 return {
 "event_id": self.event_id,
 "event_type": self.event_type.value,
 "aggregate_id": self.aggregate_id,
 "aggregate_version": self.aggregate_version,
 "timestamp": self.timestamp.isoformat(),
 "correlation_id": self.correlation_id,
 "causation_id": self.causation_id,
 "user_id": self.user_id,
 "source_service": self.source_service,
 "content_hash": self.content_hash,
 "signature": self.signature,
 "previous_event_hash": self.previous_event_hash
 }

@dataclass(frozen = True)
class ImmutableEvent:
 """Immutable event with cryptographic integrity"""
 metadata: ImmutableEventMetadata
 payload: Dict[str, Any]

 @property
 def event_id(self) -> str:
 return self.metadata.event_id

 @property
 def content_hash(self) -> str:
 return self.metadata.content_hash

 @property
 def is_snapshot(self) -> bool:
 return self.metadata.event_type == EventType.AGGREGATE_SNAPSHOT

 def to_dict(self) -> Dict[str, Any]:
 """Convert to dictionary for storage"""
 return {
 "metadata": self.metadata.to_dict(),
 "payload": self.payload
 }

 def verify_integrity(self, public_key: bytes) -> bool:
 """Verify event cryptographic integrity"""
 try:
 # Verify content hash
 calculated_hash = self._calculate_content_hash()
 if calculated_hash != self.metadata.content_hash:
 return False

 # Verify signature
 return self._verify_signature(public_key)
 except Exception as e:
 logger.error(f"Event integrity verification failed: {e}")
 return False

 def _calculate_content_hash(self) -> str:
 """Calculate SHA-256 hash of event content"""
 content = {
 "event_type": self.metadata.event_type.value,
 "aggregate_id": self.metadata.aggregate_id,
 "aggregate_version": self.metadata.aggregate_version,
 "payload": self.payload
 }
 content_json = json.dumps(content, sort_keys = True, separators=(',', ':'))
 return hashlib.sha256(content_json.encode()).hexdigest()

 def _verify_signature(self, public_key: bytes) -> bool:
 """Verify event signature using RSA public key"""
 try:
 key = load_pem_public_key(public_key)
 signature_bytes = base64.b64decode(self.metadata.signature)
 content_to_verify = f"{self.metadata.content_hash}:{self.metadata.timestamp.isoformat()}"

 key.verify(
 signature_bytes,
 content_to_verify.encode(),
 padding.PSS(
 mgf = padding.MGF1(hashes.SHA256()),
 salt_length = padding.PSS.MAX_LENGTH
 ),
 hashes.SHA256()
 )
 return True
 except Exception:
 return False

class EventIntegrityChain:
 """Maintains chain of event integrity hashes"""

 def __init__(self):
 self._chain: List[str] = []
 self._genesis_hash = "0" * 64 # Genesis block hash

 def add_event(self, event: ImmutableEvent) -> str:
 """Add event to integrity chain and return chain hash"""
 previous_hash = self._chain[-1] if self._chain else self._genesis_hash

 # Calculate chain hash including previous hash
 chain_content = f"{previous_hash}:{event.content_hash}:{event.metadata.timestamp.isoformat()}"
 chain_hash = hashlib.sha256(chain_content.encode()).hexdigest()

 self._chain.append(chain_hash)
 return chain_hash

 def verify_chain(self, events: List[ImmutableEvent]) -> bool:
 """Verify the entire event chain integrity"""
 if len(events) != len(self._chain):
 return False

 current_hash = self._genesis_hash
 for i, event in enumerate(events):
 expected_content = f"{current_hash}:{event.content_hash}:{event.metadata.timestamp.isoformat()}"
 expected_hash = hashlib.sha256(expected_content.encode()).hexdigest()

 if expected_hash != self._chain[i]:
 return False

 current_hash = self._chain[i]

 return True

class ImmutableEventStore:
 """Complete immutable event store with cryptographic guarantees"""

 def __init__(self, redis_client: redis.Redis, private_key: bytes, public_key: bytes):
 self.redis = redis_client
 self.private_key = load_pem_private_key(private_key, password = None)
 self.public_key = public_key
 self.integrity_chain = EventIntegrityChain()

 # Storage keys
 self.EVENT_PREFIX = "immutable_event:"
 self.AGGREGATE_PREFIX = "aggregate_events:"
 self.CHAIN_PREFIX = "event_chain:"
 self.SNAPSHOT_PREFIX = "aggregate_snapshot:"
 self.METADATA_PREFIX = "event_metadata:"

 async def append_event(
 self,
 event_type: EventType,
 aggregate_id: str,
 payload: Dict[str, Any],
 correlation_id: str,
 user_id: Optional[str] = None,
 causation_id: Optional[str] = None,
 source_service: str = "oms"
 ) -> ImmutableEvent:
 """Append immutable event to store"""

 # Get current aggregate version
 current_version = await self._get_aggregate_version(aggregate_id)
 new_version = current_version + 1

 # Get previous event hash for chaining
 previous_hash = await self._get_last_event_hash(aggregate_id)

 # Create event metadata
 event_id = str(uuid.uuid4())
 timestamp = datetime.now(timezone.utc)

 # Calculate content hash
 content = {
 "event_type": event_type.value,
 "aggregate_id": aggregate_id,
 "aggregate_version": new_version,
 "payload": payload
 }
 content_json = json.dumps(content, sort_keys = True, separators=(',', ':'))
 content_hash = hashlib.sha256(content_json.encode()).hexdigest()

 # Sign the event
 signature = self._sign_event(content_hash, timestamp)

 # Create metadata
 metadata = ImmutableEventMetadata(
 event_id = event_id,
 event_type = event_type,
 aggregate_id = aggregate_id,
 aggregate_version = new_version,
 timestamp = timestamp,
 correlation_id = correlation_id,
 causation_id = causation_id,
 user_id = user_id,
 source_service = source_service,
 content_hash = content_hash,
 signature = signature,
 previous_event_hash = previous_hash
 )

 # Create immutable event
 event = ImmutableEvent(metadata = metadata, payload = payload)

 # Store event atomically
 await self._store_event_atomic(event)

 # Add to integrity chain
 chain_hash = self.integrity_chain.add_event(event)
 await self.redis.set(f"{self.CHAIN_PREFIX}{aggregate_id}:{new_version}", chain_hash)

 logger.info(f"Immutable event stored: {event_id} for aggregate {aggregate_id} version {new_version}")
 return event

 async def get_events(
 self,
 aggregate_id: str,
 from_version: int = 0,
 to_version: Optional[int] = None,
 verify_integrity: bool = True
 ) -> List[ImmutableEvent]:
 """Get events for aggregate with optional integrity verification"""

 # Get event IDs from aggregate stream
 pattern = f"{self.AGGREGATE_PREFIX}{aggregate_id}:*"
 keys = await self.redis.keys(pattern)

 # Sort by version
 version_keys = []
 for key in keys:
 try:
 version = int(key.decode().split(':')[-1])
 if from_version <= version <= (to_version or float('inf')):
 version_keys.append((version, key))
 except (ValueError, IndexError):
 continue

 version_keys.sort(key = lambda x: x[0])

 # Retrieve events
 events = []
 for version, key in version_keys:
 event_id = await self.redis.get(key)
 if event_id:
 event = await self._get_event_by_id(event_id.decode())
 if event:
 if verify_integrity and not event.verify_integrity(self.public_key):
 raise ValueError(f"Event integrity verification failed: {event.event_id}")
 events.append(event)

 return events

 async def get_aggregate_state(
 self,
 aggregate_id: str,
 at_version: Optional[int] = None
 ) -> Dict[str, Any]:
 """Reconstruct aggregate state from events"""

 # Try to find nearest snapshot
 snapshot_version = 0
 state = {}

 if at_version is None or at_version > 10: # Use snapshots for efficiency
 snapshot = await self._get_latest_snapshot(aggregate_id, at_version)
 if snapshot:
 state = snapshot["state"]
 snapshot_version = snapshot["version"]

 # Apply events after snapshot
 from_version = snapshot_version + 1
 to_version = at_version

 events = await self.get_events(aggregate_id, from_version, to_version)

 # Apply events to reconstruct state
 for event in events:
 state = self._apply_event_to_state(state, event)

 return state

 async def create_snapshot(
 self,
 aggregate_id: str,
 state: Dict[str, Any],
 correlation_id: str
 ) -> ImmutableEvent:
 """Create aggregate snapshot for performance optimization"""

 # Create snapshot event
 snapshot_event = await self.append_event(
 event_type = EventType.AGGREGATE_SNAPSHOT,
 aggregate_id = aggregate_id,
 payload={"state": state},
 correlation_id = correlation_id,
 source_service = "event_store"
 )

 # Store snapshot for quick access
 snapshot_data = {
 "version": snapshot_event.metadata.aggregate_version,
 "state": state,
 "event_id": snapshot_event.event_id,
 "timestamp": snapshot_event.metadata.timestamp.isoformat()
 }

 await self.redis.set(
 f"{self.SNAPSHOT_PREFIX}{aggregate_id}:{snapshot_event.metadata.aggregate_version}",
 json.dumps(snapshot_data)
 )

 return snapshot_event

 async def replay_events(
 self,
 aggregate_id: str,
 from_version: int = 0,
 replay_handler: Optional[callable] = None
 ) -> AsyncIterator[ImmutableEvent]:
 """Replay events from event store"""

 events = await self.get_events(aggregate_id, from_version)

 for event in events:
 if replay_handler:
 await replay_handler(event)
 yield event

 async def verify_aggregate_integrity(self, aggregate_id: str) -> bool:
 """Verify complete aggregate event chain integrity"""

 events = await self.get_events(aggregate_id, verify_integrity = True)

 # Verify chain integrity
 if not self.integrity_chain.verify_chain(events):
 return False

 # Verify each event individually
 for event in events:
 if not event.verify_integrity(self.public_key):
 return False

 return True

 async def get_event_statistics(self) -> Dict[str, Any]:
 """Get event store statistics"""

 total_events = 0
 event_types = {}
 aggregates = set()

 # Count events by scanning keys
 pattern = f"{self.EVENT_PREFIX}*"
 async for key in self.redis.scan_iter(pattern):
 total_events += 1

 # Get aggregate count
 pattern = f"{self.AGGREGATE_PREFIX}*"
 async for key in self.redis.scan_iter(pattern):
 aggregate_id = key.decode().split(':')[1]
 aggregates.add(aggregate_id)

 return {
 "total_events": total_events,
 "total_aggregates": len(aggregates),
 "event_types": event_types,
 "integrity_chain_length": len(self.integrity_chain._chain)
 }

 # Private methods

 def _sign_event(self, content_hash: str, timestamp: datetime) -> str:
 """Sign event with private key"""
 content_to_sign = f"{content_hash}:{timestamp.isoformat()}"
 signature = self.private_key.sign(
 content_to_sign.encode(),
 padding.PSS(
 mgf = padding.MGF1(hashes.SHA256()),
 salt_length = padding.PSS.MAX_LENGTH
 ),
 hashes.SHA256()
 )
 return base64.b64encode(signature).decode()

 async def _store_event_atomic(self, event: ImmutableEvent):
 """Store event atomically with all required indexes"""

 pipe = self.redis.pipeline()

 # Store main event
 event_key = f"{self.EVENT_PREFIX}{event.event_id}"
 pipe.set(event_key, json.dumps(event.to_dict()))

 # Store aggregate index
 aggregate_key = f"{self.AGGREGATE_PREFIX}{event.metadata.aggregate_id}:{event.metadata.aggregate_version}"
 pipe.set(aggregate_key, event.event_id)

 # Store metadata index
 metadata_key = f"{self.METADATA_PREFIX}{event.event_id}"
 pipe.set(metadata_key, json.dumps(event.metadata.to_dict()))

 # Update aggregate version
 version_key = f"aggregate_version:{event.metadata.aggregate_id}"
 pipe.set(version_key, event.metadata.aggregate_version)

 await pipe.execute()

 async def _get_event_by_id(self, event_id: str) -> Optional[ImmutableEvent]:
 """Retrieve event by ID"""

 event_data = await self.redis.get(f"{self.EVENT_PREFIX}{event_id}")
 if not event_data:
 return None

 try:
 data = json.loads(event_data)

 # Reconstruct metadata
 metadata_dict = data["metadata"]
 metadata = ImmutableEventMetadata(
 event_id = metadata_dict["event_id"],
 event_type = EventType(metadata_dict["event_type"]),
 aggregate_id = metadata_dict["aggregate_id"],
 aggregate_version = metadata_dict["aggregate_version"],
 timestamp = datetime.fromisoformat(metadata_dict["timestamp"]),
 correlation_id = metadata_dict["correlation_id"],
 causation_id = metadata_dict.get("causation_id"),
 user_id = metadata_dict.get("user_id"),
 source_service = metadata_dict["source_service"],
 content_hash = metadata_dict["content_hash"],
 signature = metadata_dict["signature"],
 previous_event_hash = metadata_dict.get("previous_event_hash")
 )

 return ImmutableEvent(metadata = metadata, payload = data["payload"])

 except (json.JSONDecodeError, KeyError, ValueError) as e:
 logger.error(f"Failed to deserialize event {event_id}: {e}")
 return None

 async def _get_aggregate_version(self, aggregate_id: str) -> int:
 """Get current aggregate version"""

 version = await self.redis.get(f"aggregate_version:{aggregate_id}")
 return int(version) if version else 0

 async def _get_last_event_hash(self, aggregate_id: str) -> Optional[str]:
 """Get hash of last event for this aggregate"""

 current_version = await self._get_aggregate_version(aggregate_id)
 if current_version == 0:
 return None

 chain_hash = await self.redis.get(f"{self.CHAIN_PREFIX}{aggregate_id}:{current_version}")
 return chain_hash.decode() if chain_hash else None

 async def _get_latest_snapshot(
 self,
 aggregate_id: str,
 before_version: Optional[int] = None
 ) -> Optional[Dict[str, Any]]:
 """Get latest snapshot before specified version"""

 pattern = f"{self.SNAPSHOT_PREFIX}{aggregate_id}:*"
 keys = await self.redis.keys(pattern)

 # Find latest snapshot before version
 latest_version = 0
 latest_key = None

 for key in keys:
 try:
 version = int(key.decode().split(':')[-1])
 if version > latest_version and (before_version is None or version <= before_version):
 latest_version = version
 latest_key = key
 except (ValueError, IndexError):
 continue

 if latest_key:
 snapshot_data = await self.redis.get(latest_key)
 return json.loads(snapshot_data) if snapshot_data else None

 return None

 def _apply_event_to_state(self, state: Dict[str, Any], event: ImmutableEvent) -> Dict[str, Any]:
 """Apply event to aggregate state (domain-specific logic)"""

 if event.metadata.event_type == EventType.AGGREGATE_SNAPSHOT:
 return event.payload.get("state", {})

 # Domain-specific event application logic
 new_state = state.copy()

 if event.metadata.event_type == EventType.SCHEMA_CREATED:
 new_state["schemas"] = new_state.get("schemas", {})
 new_state["schemas"][event.payload["schema_id"]] = event.payload

 elif event.metadata.event_type == EventType.SCHEMA_UPDATED:
 if "schemas" in new_state and event.payload["schema_id"] in new_state["schemas"]:
 new_state["schemas"][event.payload["schema_id"]].update(event.payload)

 elif event.metadata.event_type == EventType.SCHEMA_DELETED:
 if "schemas" in new_state:
 new_state["schemas"].pop(event.payload["schema_id"], None)

 # Add more event types as needed

 new_state["last_updated"] = event.metadata.timestamp.isoformat()
 new_state["version"] = event.metadata.aggregate_version

 return new_state


async def create_immutable_event_store(redis_url: str = "redis://localhost:6379") -> ImmutableEventStore:
 """Factory function to create immutable event store"""

 # Generate RSA key pair for event signing (in production, use existing keys)
 private_key = rsa.generate_private_key(
 public_exponent = 65537,
 key_size = 2048
 )

 private_pem = private_key.private_bytes(
 encoding = serialization.Encoding.PEM,
 format = serialization.PrivateFormat.PKCS8,
 encryption_algorithm = serialization.NoEncryption()
 )

 public_pem = private_key.public_key().public_bytes(
 encoding = serialization.Encoding.PEM,
 format = serialization.PublicFormat.SubjectPublicKeyInfo
 )

 # Create Redis connection
 redis_client = redis.from_url(redis_url)

 return ImmutableEventStore(redis_client, private_pem, public_pem)
