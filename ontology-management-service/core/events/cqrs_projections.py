#!/usr/bin/env python3
"""
Complete CQRS Implementation with Read Model Projections
======================================================
Separate read and write models with event-driven projections
"""

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Union
from enum import Enum
import logging
import redis.asyncio as redis
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import asyncpg

from .immutable_event_store import ImmutableEvent, EventType
from .event_sourcing import EventHandler

logger = logging.getLogger(__name__)

Base = declarative_base()

# Read Models (SQL-based for complex queries)

class SchemaReadModel(Base):
 """Schema read model for queries"""
 __tablename__ = 'schema_read_model'

 id = Column(String, primary_key = True)
 name = Column(String, nullable = False, index = True)
 properties = Column(JSON)
 metadata = Column(JSON)
 version = Column(Integer, nullable = False)
 is_deleted = Column(Boolean, default = False, index = True)
 created_at = Column(DateTime(timezone = True))
 updated_at = Column(DateTime(timezone = True))
 created_by = Column(String, index = True)
 updated_by = Column(String)

 def to_dict(self) -> Dict[str, Any]:
 return {
 'id': self.id,
 'name': self.name,
 'properties': self.properties,
 'metadata': self.metadata,
 'version': self.version,
 'is_deleted': self.is_deleted,
 'created_at': self.created_at.isoformat() if self.created_at else None,
 'updated_at': self.updated_at.isoformat() if self.updated_at else None,
 'created_by': self.created_by,
 'updated_by': self.updated_by
 }

class ObjectReadModel(Base):
 """Object read model for queries"""
 __tablename__ = 'object_read_model'

 id = Column(String, primary_key = True)
 schema_id = Column(String, nullable = False, index = True)
 object_data = Column(JSON)
 version = Column(Integer, nullable = False)
 is_deleted = Column(Boolean, default = False, index = True)
 created_at = Column(DateTime(timezone = True))
 updated_at = Column(DateTime(timezone = True))
 created_by = Column(String, index = True)
 updated_by = Column(String)

class LinkReadModel(Base):
 """Link read model for queries"""
 __tablename__ = 'link_read_model'

 id = Column(String, primary_key = True)
 source_id = Column(String, nullable = False, index = True)
 target_id = Column(String, nullable = False, index = True)
 link_type = Column(String, nullable = False, index = True)
 properties = Column(JSON)
 version = Column(Integer, nullable = False)
 is_deleted = Column(Boolean, default = False, index = True)
 created_at = Column(DateTime(timezone = True))
 updated_at = Column(DateTime(timezone = True))
 created_by = Column(String, index = True)
 updated_by = Column(String)

# Projection Base Classes

class ProjectionCheckpoint:
 """Manages projection checkpoints for resuming from last processed event"""

 def __init__(self, redis_client: redis.Redis):
 self.redis = redis_client

 async def get_checkpoint(self, projection_name: str) -> int:
 """Get last processed event version for projection"""
 checkpoint = await self.redis.get(f"projection_checkpoint:{projection_name}")
 return int(checkpoint) if checkpoint else 0

 async def save_checkpoint(self, projection_name: str, version: int):
 """Save checkpoint for projection"""
 await self.redis.set(f"projection_checkpoint:{projection_name}", version)

class ReadModelProjection(ABC):
 """Base class for read model projections"""

 def __init__(self, name: str, checkpoint_manager: ProjectionCheckpoint):
 self.name = name
 self.checkpoint_manager = checkpoint_manager
 self.supported_events: Set[EventType] = set()

 @abstractmethod
 async def project_event(self, event: ImmutableEvent) -> None:
 """Project event to read model"""
 pass

 @abstractmethod
 async def handle_replay(self, events: List[ImmutableEvent]) -> None:
 """Handle event replay for projection rebuild"""
 pass

 async def can_handle_event(self, event: ImmutableEvent) -> bool:
 """Check if projection can handle event"""
 return event.metadata.event_type in self.supported_events

 async def process_event(self, event: ImmutableEvent) -> None:
 """Process event and update checkpoint"""
 if await self.can_handle_event(event):
 await self.project_event(event)
 await self.checkpoint_manager.save_checkpoint(self.name, event.metadata.aggregate_version)

# SQL-based Read Model Manager

class SQLReadModelManager:
 """Manages SQL-based read models"""

 def __init__(self, database_url: str):
 self.engine = create_engine(database_url)
 self.SessionLocal = sessionmaker(autocommit = False, autoflush = False, bind = self.engine)

 async def initialize(self):
 """Initialize database tables"""
 Base.metadata.create_all(bind = self.engine)

 def get_session(self):
 """Get database session"""
 return self.SessionLocal()

# Schema Read Model Projection

class SchemaReadModelProjection(ReadModelProjection):
 """Schema read model projection"""

 def __init__(self, checkpoint_manager: ProjectionCheckpoint, sql_manager: SQLReadModelManager):
 super().__init__("schema_read_model", checkpoint_manager)
 self.sql_manager = sql_manager
 self.supported_events = {
 EventType.SCHEMA_CREATED,
 EventType.SCHEMA_UPDATED,
 EventType.SCHEMA_DELETED
 }

 async def project_event(self, event: ImmutableEvent) -> None:
 """Project schema event to read model"""
 session = self.sql_manager.get_session()

 try:
 if event.metadata.event_type == EventType.SCHEMA_CREATED:
 await self._handle_schema_created(session, event)
 elif event.metadata.event_type == EventType.SCHEMA_UPDATED:
 await self._handle_schema_updated(session, event)
 elif event.metadata.event_type == EventType.SCHEMA_DELETED:
 await self._handle_schema_deleted(session, event)

 session.commit()

 except Exception as e:
 session.rollback()
 logger.error(f"Error projecting schema event {event.event_id}: {e}")
 raise
 finally:
 session.close()

 async def _handle_schema_created(self, session, event: ImmutableEvent):
 """Handle schema created event"""
 payload = event.payload

 schema_model = SchemaReadModel(
 id = event.metadata.aggregate_id,
 name = payload["name"],
 properties = payload["properties"],
 metadata = payload["metadata"],
 version = event.metadata.aggregate_version,
 is_deleted = False,
 created_at = datetime.fromisoformat(payload["created_at"]),
 updated_at = datetime.fromisoformat(payload["created_at"]),
 created_by = payload.get("created_by"),
 updated_by = payload.get("created_by")
 )

 session.add(schema_model)

 async def _handle_schema_updated(self, session, event: ImmutableEvent):
 """Handle schema updated event"""
 payload = event.payload
 changes = payload["changes"]

 schema_model = session.query(SchemaReadModel).filter_by(
 id = event.metadata.aggregate_id
 ).first()

 if schema_model:
 if "name" in changes:
 schema_model.name = changes["name"]
 if "properties" in changes:
 schema_model.properties = changes["properties"]
 if "metadata" in changes:
 schema_model.metadata.update(changes["metadata"])

 schema_model.version = event.metadata.aggregate_version
 schema_model.updated_at = datetime.fromisoformat(payload["updated_at"])
 schema_model.updated_by = payload.get("updated_by")

 async def _handle_schema_deleted(self, session, event: ImmutableEvent):
 """Handle schema deleted event"""
 payload = event.payload

 schema_model = session.query(SchemaReadModel).filter_by(
 id = event.metadata.aggregate_id
 ).first()

 if schema_model:
 schema_model.is_deleted = True
 schema_model.version = event.metadata.aggregate_version
 schema_model.updated_at = datetime.fromisoformat(payload["deleted_at"])
 schema_model.updated_by = payload.get("deleted_by")

 async def handle_replay(self, events: List[ImmutableEvent]) -> None:
 """Handle event replay for schema read model"""
 session = self.sql_manager.get_session()

 try:
 # Clear existing data for replay
 session.query(SchemaReadModel).delete()

 # Process all events
 for event in events:
 if await self.can_handle_event(event):
 await self.project_event(event)

 session.commit()
 logger.info(f"Schema read model replay completed: {len(events)} events processed")

 except Exception as e:
 session.rollback()
 logger.error(f"Error during schema read model replay: {e}")
 raise
 finally:
 session.close()

# Redis-based Materialized Views

class RedisMaterializedView:
 """Redis-based materialized view for fast lookups"""

 def __init__(self, redis_client: redis.Redis, view_name: str):
 self.redis = redis_client
 self.view_name = view_name
 self.key_prefix = f"view:{view_name}:"

 async def set_item(self, key: str, data: Dict[str, Any], ttl: Optional[int] = None):
 """Set item in materialized view"""
 full_key = f"{self.key_prefix}{key}"
 await self.redis.set(full_key, json.dumps(data, default = str), ex = ttl)

 async def get_item(self, key: str) -> Optional[Dict[str, Any]]:
 """Get item from materialized view"""
 full_key = f"{self.key_prefix}{key}"
 data = await self.redis.get(full_key)
 return json.loads(data) if data else None

 async def delete_item(self, key: str):
 """Delete item from materialized view"""
 full_key = f"{self.key_prefix}{key}"
 await self.redis.delete(full_key)

 async def add_to_set(self, set_key: str, member: str):
 """Add member to set in view"""
 full_key = f"{self.key_prefix}set:{set_key}"
 await self.redis.sadd(full_key, member)

 async def remove_from_set(self, set_key: str, member: str):
 """Remove member from set in view"""
 full_key = f"{self.key_prefix}set:{set_key}"
 await self.redis.srem(full_key, member)

 async def get_set_members(self, set_key: str) -> Set[str]:
 """Get all members of a set"""
 full_key = f"{self.key_prefix}set:{set_key}"
 members = await self.redis.smembers(full_key)
 return {member.decode() if isinstance(member, bytes) else member for member in members}

# Specialized Materialized Views

class SchemaListView(ReadModelProjection):
 """Materialized view for schema listings"""

 def __init__(self, checkpoint_manager: ProjectionCheckpoint, redis_client: redis.Redis):
 super().__init__("schema_list_view", checkpoint_manager)
 self.view = RedisMaterializedView(redis_client, "schema_list")
 self.supported_events = {
 EventType.SCHEMA_CREATED,
 EventType.SCHEMA_UPDATED,
 EventType.SCHEMA_DELETED
 }

 async def project_event(self, event: ImmutableEvent) -> None:
 """Project event to schema list view"""
 if event.metadata.event_type == EventType.SCHEMA_CREATED:
 await self._handle_schema_created(event)
 elif event.metadata.event_type == EventType.SCHEMA_UPDATED:
 await self._handle_schema_updated(event)
 elif event.metadata.event_type == EventType.SCHEMA_DELETED:
 await self._handle_schema_deleted(event)

 async def _handle_schema_created(self, event: ImmutableEvent):
 """Handle schema created for list view"""
 payload = event.payload

 schema_summary = {
 "id": event.metadata.aggregate_id,
 "name": payload["name"],
 "property_count": len(payload["properties"]),
 "version": event.metadata.aggregate_version,
 "created_at": payload["created_at"],
 "created_by": payload.get("created_by")
 }

 # Add to main list
 await self.view.set_item(event.metadata.aggregate_id, schema_summary)

 # Add to indexes
 await self.view.add_to_set("all_schemas", event.metadata.aggregate_id)
 await self.view.add_to_set(f"by_user:{payload.get('created_by', 'unknown')}", event.metadata.aggregate_id)

 async def _handle_schema_updated(self, event: ImmutableEvent):
 """Handle schema updated for list view"""
 existing = await self.view.get_item(event.metadata.aggregate_id)
 if existing:
 payload = event.payload
 changes = payload["changes"]

 if "name" in changes:
 existing["name"] = changes["name"]
 if "properties" in changes:
 existing["property_count"] = len(changes["properties"])

 existing["version"] = event.metadata.aggregate_version
 existing["updated_at"] = payload["updated_at"]
 existing["updated_by"] = payload.get("updated_by")

 await self.view.set_item(event.metadata.aggregate_id, existing)

 async def _handle_schema_deleted(self, event: ImmutableEvent):
 """Handle schema deleted for list view"""
 # Remove from all indexes
 await self.view.remove_from_set("all_schemas", event.metadata.aggregate_id)

 # Remove main item
 await self.view.delete_item(event.metadata.aggregate_id)

 async def handle_replay(self, events: List[ImmutableEvent]) -> None:
 """Handle replay for schema list view"""
 # Clear existing view data
 all_schemas = await self.view.get_set_members("all_schemas")
 for schema_id in all_schemas:
 await self.view.delete_item(schema_id)

 # Clear sets
 await self.view.redis.delete(f"{self.view.key_prefix}set:all_schemas")

 # Process all events
 for event in events:
 if await self.can_handle_event(event):
 await self.project_event(event)

# Query Services

class SchemaQueryService:
 """Query service for schema read models"""

 def __init__(self, sql_manager: SQLReadModelManager, schema_list_view: SchemaListView):
 self.sql_manager = sql_manager
 self.schema_list_view = schema_list_view

 async def get_schema_by_id(self, schema_id: str) -> Optional[Dict[str, Any]]:
 """Get schema by ID from read model"""
 session = self.sql_manager.get_session()

 try:
 schema = session.query(SchemaReadModel).filter_by(
 id = schema_id, is_deleted = False
 ).first()

 return schema.to_dict() if schema else None

 finally:
 session.close()

 async def list_schemas(
 self,
 limit: int = 50,
 offset: int = 0,
 created_by: Optional[str] = None,
 name_pattern: Optional[str] = None
 ) -> Dict[str, Any]:
 """List schemas with filters"""
 session = self.sql_manager.get_session()

 try:
 query = session.query(SchemaReadModel).filter_by(is_deleted = False)

 if created_by:
 query = query.filter(SchemaReadModel.created_by == created_by)

 if name_pattern:
 query = query.filter(SchemaReadModel.name.like(f"%{name_pattern}%"))

 total_count = query.count()
 schemas = query.offset(offset).limit(limit).all()

 return {
 "schemas": [schema.to_dict() for schema in schemas],
 "total_count": total_count,
 "limit": limit,
 "offset": offset
 }

 finally:
 session.close()

 async def get_schema_summary(self, schema_id: str) -> Optional[Dict[str, Any]]:
 """Get schema summary from materialized view (fast)"""
 return await self.schema_list_view.view.get_item(schema_id)

 async def search_schemas(self, query: str) -> List[Dict[str, Any]]:
 """Search schemas by name or content"""
 session = self.sql_manager.get_session()

 try:
 # Use PostgreSQL full-text search if available
 schemas = session.query(SchemaReadModel).filter(
 SchemaReadModel.is_deleted == False,
 SchemaReadModel.name.like(f"%{query}%")
 ).limit(20).all()

 return [schema.to_dict() for schema in schemas]

 finally:
 session.close()

# CQRS Coordinator

class CQRSCoordinator:
 """Coordinates CQRS operations and projections"""

 def __init__(
 self,
 sql_manager: SQLReadModelManager,
 redis_client: redis.Redis,
 checkpoint_manager: ProjectionCheckpoint
 ):
 self.sql_manager = sql_manager
 self.redis_client = redis_client
 self.checkpoint_manager = checkpoint_manager

 # Initialize projections
 self.schema_read_model = SchemaReadModelProjection(checkpoint_manager, sql_manager)
 self.schema_list_view = SchemaListView(checkpoint_manager, redis_client)

 # Query services
 self.schema_query_service = SchemaQueryService(sql_manager, self.schema_list_view)

 # All projections
 self.projections = [
 self.schema_read_model,
 self.schema_list_view
 ]

 async def initialize(self):
 """Initialize CQRS coordinator"""
 await self.sql_manager.initialize()

 async def project_event(self, event: ImmutableEvent):
 """Project event to all relevant projections"""
 for projection in self.projections:
 try:
 await projection.process_event(event)
 except Exception as e:
 logger.error(f"Error in projection {projection.name}: {e}")

 async def rebuild_projections(self, events: List[ImmutableEvent]):
 """Rebuild all projections from events"""
 logger.info("Starting projection rebuild...")

 for projection in self.projections:
 try:
 await projection.handle_replay(events)
 logger.info(f"Rebuilt projection: {projection.name}")
 except Exception as e:
 logger.error(f"Error rebuilding projection {projection.name}: {e}")

 logger.info("Projection rebuild completed")

 async def get_projection_status(self) -> Dict[str, Any]:
 """Get status of all projections"""
 status = {}

 for projection in self.projections:
 checkpoint = await self.checkpoint_manager.get_checkpoint(projection.name)
 status[projection.name] = {
 "last_processed_version": checkpoint,
 "supported_events": [event.value for event in projection.supported_events]
 }

 return status

# Event Handler for CQRS Integration

class CQRSEventHandler(EventHandler):
 """Event handler that updates CQRS projections"""

 def __init__(self, coordinator: CQRSCoordinator):
 self.coordinator = coordinator

 async def handle(self, event: ImmutableEvent) -> None:
 """Handle event by updating projections"""
 await self.coordinator.project_event(event)

 def can_handle(self, event_type: EventType) -> bool:
 """Can handle all event types"""
 return True
