#!/usr/bin/env python3
"""
Complete Event Sourcing Pattern Implementation
============================================
Full Event Sourcing with Aggregate Root, Commands, and Handlers
"""

import asyncio
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type, TypeVar, Generic, Union
from enum import Enum
import logging

from .immutable_event_store import ImmutableEventStore, ImmutableEvent, EventType

logger = logging.getLogger(__name__)

# Type variables for generics
T = TypeVar('T')
TAggregate = TypeVar('TAggregate', bound='AggregateRoot')
TCommand = TypeVar('TCommand', bound='Command')
TEvent = TypeVar('TEvent', bound='DomainEvent')

class CommandResult(Enum):
    """Command execution results"""
    SUCCESS = "success"
    VALIDATION_ERROR = "validation_error"
    BUSINESS_RULE_VIOLATION = "business_rule_violation"
    CONCURRENCY_ERROR = "concurrency_error"
    SYSTEM_ERROR = "system_error"

@dataclass
class CommandResponse:
    """Response from command execution"""
    result: CommandResult
    aggregate_id: str
    version: int
    events: List[ImmutableEvent] = field(default_factory=list)
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

# Base Classes

class Command(ABC):
    """Base command class"""
    
    def __init__(self, aggregate_id: str, correlation_id: str, user_id: Optional[str] = None):
        self.aggregate_id = aggregate_id
        self.correlation_id = correlation_id
        self.user_id = user_id
        self.timestamp = datetime.now(timezone.utc)
        
    @abstractmethod
    def validate(self) -> bool:
        """Validate command"""
        pass

class DomainEvent(ABC):
    """Base domain event class"""
    
    def __init__(self, aggregate_id: str, correlation_id: str, user_id: Optional[str] = None):
        self.aggregate_id = aggregate_id
        self.correlation_id = correlation_id
        self.user_id = user_id
        self.occurred_on = datetime.now(timezone.utc)
        
    @abstractmethod
    def to_payload(self) -> Dict[str, Any]:
        """Convert event to payload for storage"""
        pass
        
    @abstractmethod
    def get_event_type(self) -> EventType:
        """Get the event type"""
        pass

class AggregateRoot(ABC):
    """Base aggregate root with event sourcing capabilities"""
    
    def __init__(self, aggregate_id: str):
        self.aggregate_id = aggregate_id
        self.version = 0
        self.uncommitted_events: List[DomainEvent] = []
        
    def apply_event(self, event: Union[DomainEvent, ImmutableEvent]):
        """Apply event to aggregate state"""
        if isinstance(event, ImmutableEvent):
            # Convert from stored event
            domain_event = self._convert_immutable_event(event)
        else:
            domain_event = event
            
        # Apply the event
        self._apply_domain_event(domain_event)
        
        # Increment version only for new events
        if isinstance(event, DomainEvent):
            self.version += 1
            self.uncommitted_events.append(event)
        elif isinstance(event, ImmutableEvent):
            self.version = event.metadata.aggregate_version
            
    @abstractmethod
    def _apply_domain_event(self, event: DomainEvent):
        """Apply domain event to aggregate state (implemented by subclasses)"""
        pass
        
    @abstractmethod
    def _convert_immutable_event(self, event: ImmutableEvent) -> DomainEvent:
        """Convert immutable event to domain event (implemented by subclasses)"""
        pass
        
    def get_uncommitted_events(self) -> List[DomainEvent]:
        """Get uncommitted events"""
        return self.uncommitted_events.copy()
        
    def mark_events_as_committed(self):
        """Mark events as committed"""
        self.uncommitted_events.clear()

# Repository Pattern

class AggregateRepository(Generic[TAggregate], ABC):
    """Base repository for aggregates with event sourcing"""
    
    def __init__(self, event_store: ImmutableEventStore):
        self.event_store = event_store
        
    @abstractmethod
    async def get_by_id(self, aggregate_id: str) -> Optional[TAggregate]:
        """Get aggregate by ID"""
        pass
        
    @abstractmethod
    async def save(self, aggregate: TAggregate) -> List[ImmutableEvent]:
        """Save aggregate events"""
        pass
        
    @abstractmethod
    def _create_empty_aggregate(self, aggregate_id: str) -> TAggregate:
        """Create empty aggregate instance"""
        pass

# Command and Event Handlers

class CommandHandler(Generic[TCommand, TAggregate], ABC):
    """Base command handler"""
    
    def __init__(self, repository: AggregateRepository[TAggregate]):
        self.repository = repository
        
    @abstractmethod
    async def handle(self, command: TCommand) -> CommandResponse:
        """Handle command"""
        pass

class EventHandler(Generic[TEvent], ABC):
    """Base event handler for read model updates"""
    
    @abstractmethod
    async def handle(self, event: TEvent) -> None:
        """Handle event"""
        pass
        
    @abstractmethod
    def can_handle(self, event_type: EventType) -> bool:
        """Check if handler can handle event type"""
        pass

# Specific Domain Implementation for Schema Management

# Schema Commands

@dataclass
class CreateSchemaCommand(Command):
    """Create schema command"""
    name: str
    properties: List[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> bool:
        return bool(self.name and self.properties)

@dataclass
class UpdateSchemaCommand(Command):
    """Update schema command"""
    name: Optional[str] = None
    properties: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None
    expected_version: Optional[int] = None
    
    def validate(self) -> bool:
        return any([self.name, self.properties, self.metadata])

@dataclass
class DeleteSchemaCommand(Command):
    """Delete schema command"""
    expected_version: Optional[int] = None
    
    def validate(self) -> bool:
        return True

# Schema Events

class SchemaCreatedEvent(DomainEvent):
    """Schema created event"""
    
    def __init__(self, aggregate_id: str, correlation_id: str, name: str, 
                 properties: List[Dict[str, Any]], metadata: Dict[str, Any], 
                 user_id: Optional[str] = None):
        super().__init__(aggregate_id, correlation_id, user_id)
        self.name = name
        self.properties = properties
        self.metadata = metadata
        
    def to_payload(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "properties": self.properties,
            "metadata": self.metadata,
            "created_by": self.user_id,
            "created_at": self.occurred_on.isoformat()
        }
        
    def get_event_type(self) -> EventType:
        return EventType.SCHEMA_CREATED

class SchemaUpdatedEvent(DomainEvent):
    """Schema updated event"""
    
    def __init__(self, aggregate_id: str, correlation_id: str, changes: Dict[str, Any], 
                 user_id: Optional[str] = None):
        super().__init__(aggregate_id, correlation_id, user_id)
        self.changes = changes
        
    def to_payload(self) -> Dict[str, Any]:
        return {
            "changes": self.changes,
            "updated_by": self.user_id,
            "updated_at": self.occurred_on.isoformat()
        }
        
    def get_event_type(self) -> EventType:
        return EventType.SCHEMA_UPDATED

class SchemaDeletedEvent(DomainEvent):
    """Schema deleted event"""
    
    def __init__(self, aggregate_id: str, correlation_id: str, user_id: Optional[str] = None):
        super().__init__(aggregate_id, correlation_id, user_id)
        
    def to_payload(self) -> Dict[str, Any]:
        return {
            "deleted_by": self.user_id,
            "deleted_at": self.occurred_on.isoformat()
        }
        
    def get_event_type(self) -> EventType:
        return EventType.SCHEMA_DELETED

# Schema Aggregate

class SchemaAggregate(AggregateRoot):
    """Schema aggregate root"""
    
    def __init__(self, aggregate_id: str):
        super().__init__(aggregate_id)
        self.name: Optional[str] = None
        self.properties: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {}
        self.is_deleted = False
        self.created_at: Optional[datetime] = None
        self.updated_at: Optional[datetime] = None
        
    def create_schema(self, name: str, properties: List[Dict[str, Any]], 
                     metadata: Dict[str, Any], correlation_id: str, user_id: Optional[str] = None):
        """Create schema"""
        if self.name is not None:
            raise ValueError("Schema already exists")
            
        event = SchemaCreatedEvent(
            aggregate_id=self.aggregate_id,
            correlation_id=correlation_id,
            name=name,
            properties=properties,
            metadata=metadata,
            user_id=user_id
        )
        
        self.apply_event(event)
        
    def update_schema(self, changes: Dict[str, Any], correlation_id: str, user_id: Optional[str] = None):
        """Update schema"""
        if self.is_deleted:
            raise ValueError("Cannot update deleted schema")
            
        event = SchemaUpdatedEvent(
            aggregate_id=self.aggregate_id,
            correlation_id=correlation_id,
            changes=changes,
            user_id=user_id
        )
        
        self.apply_event(event)
        
    def delete_schema(self, correlation_id: str, user_id: Optional[str] = None):
        """Delete schema"""
        if self.is_deleted:
            raise ValueError("Schema already deleted")
            
        event = SchemaDeletedEvent(
            aggregate_id=self.aggregate_id,
            correlation_id=correlation_id,
            user_id=user_id
        )
        
        self.apply_event(event)
        
    def _apply_domain_event(self, event: DomainEvent):
        """Apply domain event to schema state"""
        if isinstance(event, SchemaCreatedEvent):
            self.name = event.name
            self.properties = event.properties
            self.metadata = event.metadata
            self.created_at = event.occurred_on
            self.updated_at = event.occurred_on
            
        elif isinstance(event, SchemaUpdatedEvent):
            changes = event.changes
            if "name" in changes:
                self.name = changes["name"]
            if "properties" in changes:
                self.properties = changes["properties"]
            if "metadata" in changes:
                self.metadata.update(changes["metadata"])
            self.updated_at = event.occurred_on
            
        elif isinstance(event, SchemaDeletedEvent):
            self.is_deleted = True
            self.updated_at = event.occurred_on
            
    def _convert_immutable_event(self, event: ImmutableEvent) -> DomainEvent:
        """Convert immutable event to domain event"""
        payload = event.payload
        
        if event.metadata.event_type == EventType.SCHEMA_CREATED:
            return SchemaCreatedEvent(
                aggregate_id=event.metadata.aggregate_id,
                correlation_id=event.metadata.correlation_id,
                name=payload["name"],
                properties=payload["properties"],
                metadata=payload["metadata"],
                user_id=event.metadata.user_id
            )
            
        elif event.metadata.event_type == EventType.SCHEMA_UPDATED:
            return SchemaUpdatedEvent(
                aggregate_id=event.metadata.aggregate_id,
                correlation_id=event.metadata.correlation_id,
                changes=payload["changes"],
                user_id=event.metadata.user_id
            )
            
        elif event.metadata.event_type == EventType.SCHEMA_DELETED:
            return SchemaDeletedEvent(
                aggregate_id=event.metadata.aggregate_id,
                correlation_id=event.metadata.correlation_id,
                user_id=event.metadata.user_id
            )
            
        else:
            raise ValueError(f"Unknown event type: {event.metadata.event_type}")

# Schema Repository

class SchemaRepository(AggregateRepository[SchemaAggregate]):
    """Schema aggregate repository"""
    
    async def get_by_id(self, aggregate_id: str) -> Optional[SchemaAggregate]:
        """Get schema aggregate by ID"""
        try:
            events = await self.event_store.get_events(aggregate_id)
            if not events:
                return None
                
            aggregate = self._create_empty_aggregate(aggregate_id)
            
            for event in events:
                aggregate.apply_event(event)
                
            return aggregate
            
        except Exception as e:
            logger.error(f"Error loading schema aggregate {aggregate_id}: {e}")
            return None
            
    async def save(self, aggregate: SchemaAggregate) -> List[ImmutableEvent]:
        """Save schema aggregate events"""
        uncommitted_events = aggregate.get_uncommitted_events()
        stored_events = []
        
        for domain_event in uncommitted_events:
            immutable_event = await self.event_store.append_event(
                event_type=domain_event.get_event_type(),
                aggregate_id=domain_event.aggregate_id,
                payload=domain_event.to_payload(),
                correlation_id=domain_event.correlation_id,
                user_id=domain_event.user_id,
                source_service="schema_service"
            )
            stored_events.append(immutable_event)
            
        aggregate.mark_events_as_committed()
        return stored_events
        
    def _create_empty_aggregate(self, aggregate_id: str) -> SchemaAggregate:
        """Create empty schema aggregate"""
        return SchemaAggregate(aggregate_id)

# Command Handlers

class CreateSchemaCommandHandler(CommandHandler[CreateSchemaCommand, SchemaAggregate]):
    """Create schema command handler"""
    
    async def handle(self, command: CreateSchemaCommand) -> CommandResponse:
        """Handle create schema command"""
        try:
            # Validate command
            if not command.validate():
                return CommandResponse(
                    result=CommandResult.VALIDATION_ERROR,
                    aggregate_id=command.aggregate_id,
                    version=0,
                    error_message="Invalid command parameters"
                )
                
            # Check if schema already exists
            existing_aggregate = await self.repository.get_by_id(command.aggregate_id)
            if existing_aggregate and not existing_aggregate.is_deleted:
                return CommandResponse(
                    result=CommandResult.BUSINESS_RULE_VIOLATION,
                    aggregate_id=command.aggregate_id,
                    version=existing_aggregate.version,
                    error_message="Schema already exists"
                )
                
            # Create new aggregate
            aggregate = self.repository._create_empty_aggregate(command.aggregate_id)
            aggregate.create_schema(
                name=command.name,
                properties=command.properties,
                metadata=command.metadata,
                correlation_id=command.correlation_id,
                user_id=command.user_id
            )
            
            # Save events
            events = await self.repository.save(aggregate)
            
            return CommandResponse(
                result=CommandResult.SUCCESS,
                aggregate_id=command.aggregate_id,
                version=aggregate.version,
                events=events
            )
            
        except Exception as e:
            logger.error(f"Error handling CreateSchemaCommand: {e}")
            return CommandResponse(
                result=CommandResult.SYSTEM_ERROR,
                aggregate_id=command.aggregate_id,
                version=0,
                error_message=str(e)
            )

class UpdateSchemaCommandHandler(CommandHandler[UpdateSchemaCommand, SchemaAggregate]):
    """Update schema command handler"""
    
    async def handle(self, command: UpdateSchemaCommand) -> CommandResponse:
        """Handle update schema command"""
        try:
            # Validate command
            if not command.validate():
                return CommandResponse(
                    result=CommandResult.VALIDATION_ERROR,
                    aggregate_id=command.aggregate_id,
                    version=0,
                    error_message="Invalid command parameters"
                )
                
            # Load aggregate
            aggregate = await self.repository.get_by_id(command.aggregate_id)
            if not aggregate or aggregate.is_deleted:
                return CommandResponse(
                    result=CommandResult.BUSINESS_RULE_VIOLATION,
                    aggregate_id=command.aggregate_id,
                    version=0,
                    error_message="Schema not found"
                )
                
            # Check expected version for concurrency control
            if command.expected_version is not None and aggregate.version != command.expected_version:
                return CommandResponse(
                    result=CommandResult.CONCURRENCY_ERROR,
                    aggregate_id=command.aggregate_id,
                    version=aggregate.version,
                    error_message=f"Expected version {command.expected_version}, got {aggregate.version}"
                )
                
            # Prepare changes
            changes = {}
            if command.name is not None:
                changes["name"] = command.name
            if command.properties is not None:
                changes["properties"] = command.properties
            if command.metadata is not None:
                changes["metadata"] = command.metadata
                
            # Update schema
            aggregate.update_schema(
                changes=changes,
                correlation_id=command.correlation_id,
                user_id=command.user_id
            )
            
            # Save events
            events = await self.repository.save(aggregate)
            
            return CommandResponse(
                result=CommandResult.SUCCESS,
                aggregate_id=command.aggregate_id,
                version=aggregate.version,
                events=events
            )
            
        except Exception as e:
            logger.error(f"Error handling UpdateSchemaCommand: {e}")
            return CommandResponse(
                result=CommandResult.SYSTEM_ERROR,
                aggregate_id=command.aggregate_id,
                version=0,
                error_message=str(e)
            )

class DeleteSchemaCommandHandler(CommandHandler[DeleteSchemaCommand, SchemaAggregate]):
    """Delete schema command handler"""
    
    async def handle(self, command: DeleteSchemaCommand) -> CommandResponse:
        """Handle delete schema command"""
        try:
            # Load aggregate
            aggregate = await self.repository.get_by_id(command.aggregate_id)
            if not aggregate or aggregate.is_deleted:
                return CommandResponse(
                    result=CommandResult.BUSINESS_RULE_VIOLATION,
                    aggregate_id=command.aggregate_id,
                    version=0,
                    error_message="Schema not found"
                )
                
            # Check expected version for concurrency control
            if command.expected_version is not None and aggregate.version != command.expected_version:
                return CommandResponse(
                    result=CommandResult.CONCURRENCY_ERROR,
                    aggregate_id=command.aggregate_id,
                    version=aggregate.version,
                    error_message=f"Expected version {command.expected_version}, got {aggregate.version}"
                )
                
            # Delete schema
            aggregate.delete_schema(
                correlation_id=command.correlation_id,
                user_id=command.user_id
            )
            
            # Save events
            events = await self.repository.save(aggregate)
            
            return CommandResponse(
                result=CommandResult.SUCCESS,
                aggregate_id=command.aggregate_id,
                version=aggregate.version,
                events=events
            )
            
        except Exception as e:
            logger.error(f"Error handling DeleteSchemaCommand: {e}")
            return CommandResponse(
                result=CommandResult.SYSTEM_ERROR,
                aggregate_id=command.aggregate_id,
                version=0,
                error_message=str(e)
            )

# Event Sourcing Service

class EventSourcingService:
    """Main service for event sourcing operations"""
    
    def __init__(self, event_store: ImmutableEventStore):
        self.event_store = event_store
        self.schema_repository = SchemaRepository(event_store)
        
        # Command handlers
        self.create_schema_handler = CreateSchemaCommandHandler(self.schema_repository)
        self.update_schema_handler = UpdateSchemaCommandHandler(self.schema_repository)
        self.delete_schema_handler = DeleteSchemaCommandHandler(self.schema_repository)
        
        # Event handlers registry
        self.event_handlers: Dict[EventType, List[EventHandler]] = {}
        
    async def handle_command(self, command: Command) -> CommandResponse:
        """Handle any command"""
        if isinstance(command, CreateSchemaCommand):
            return await self.create_schema_handler.handle(command)
        elif isinstance(command, UpdateSchemaCommand):
            return await self.update_schema_handler.handle(command)
        elif isinstance(command, DeleteSchemaCommand):
            return await self.delete_schema_handler.handle(command)
        else:
            return CommandResponse(
                result=CommandResult.VALIDATION_ERROR,
                aggregate_id=getattr(command, 'aggregate_id', ''),
                version=0,
                error_message=f"Unknown command type: {type(command)}"
            )
            
    def register_event_handler(self, event_type: EventType, handler: EventHandler):
        """Register event handler"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
        
    async def publish_events(self, events: List[ImmutableEvent]):
        """Publish events to registered handlers"""
        for event in events:
            handlers = self.event_handlers.get(event.metadata.event_type, [])
            for handler in handlers:
                try:
                    await handler.handle(event)
                except Exception as e:
                    logger.error(f"Error in event handler {type(handler).__name__}: {e}")
                    
    async def replay_aggregate_events(self, aggregate_id: str, from_version: int = 0):
        """Replay events for an aggregate"""
        async for event in self.event_store.replay_events(aggregate_id, from_version):
            await self.publish_events([event])
            
    async def get_aggregate_statistics(self) -> Dict[str, Any]:
        """Get event store statistics"""
        return await self.event_store.get_event_statistics()