"""
Database Interface Definitions

This module defines the interfaces for all database clients in the OMS system.
All database implementations should conform to these interfaces.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable, Set
from datetime import datetime


class IDocumentDatabase(ABC):
    """Interface for document-based databases (e.g., TerminusDB)"""
    
    @abstractmethod
    async def create(self, collection: str, document: Dict[str, Any]) -> str:
        """Create a new document in the specified collection"""
        pass
    
    @abstractmethod
    async def read(self, collection: str, document_id: str) -> Optional[Dict[str, Any]]:
        """Read a document by ID"""
        pass
    
    @abstractmethod
    async def update(self, collection: str, document_id: str, document: Dict[str, Any]) -> bool:
        """Update an existing document"""
        pass
    
    @abstractmethod
    async def delete(self, collection: str, document_id: str) -> bool:
        """Delete a document by ID"""
        pass
    
    @abstractmethod
    async def query(self, woql: str) -> List[Dict[str, Any]]:
        """Execute a WOQL query (TerminusDB specific)"""
        pass
    
    @abstractmethod
    async def list(self, collection: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """List documents in a collection with optional filters"""
        pass


class ICacheDatabase(ABC):
    """Interface for cache databases (e.g., Redis)"""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get value by key"""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set key-value with optional TTL in seconds"""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a key"""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        pass
    
    @abstractmethod
    async def expire(self, key: str, ttl: int) -> bool:
        """Set TTL for a key"""
        pass
    
    @abstractmethod
    async def mget(self, keys: List[str]) -> List[Optional[Any]]:
        """Get multiple values by keys"""
        pass
    
    @abstractmethod
    async def mset(self, mapping: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Set multiple key-value pairs"""
        pass


class IMessageQueue(ABC):
    """Interface for message queue systems"""
    
    @abstractmethod
    async def publish(self, topic: str, message: Dict[str, Any]) -> bool:
        """Publish a message to a topic"""
        pass
    
    @abstractmethod
    async def subscribe(self, topic: str, handler: Callable) -> bool:
        """Subscribe to a topic with a message handler"""
        pass
    
    @abstractmethod
    async def unsubscribe(self, topic: str) -> bool:
        """Unsubscribe from a topic"""
        pass


class IExternalService(ABC):
    """Interface for external service clients (MSA)"""
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the service is healthy"""
        pass
    
    @abstractmethod
    async def call(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make a service call"""
        pass


class IVersionControl(ABC):
    """Interface for version control operations (TerminusDB native)"""
    
    @abstractmethod
    async def branch(self, branch_name: str, from_commit: Optional[str] = None) -> bool:
        """Create a new branch"""
        pass
    
    @abstractmethod
    async def checkout(self, branch_or_commit: str) -> bool:
        """Checkout a branch or commit"""
        pass
    
    @abstractmethod
    async def commit(self, message: str, author: Optional[str] = None) -> str:
        """Create a new commit"""
        pass
    
    @abstractmethod
    async def merge(self, branch: str, message: Optional[str] = None) -> bool:
        """Merge a branch into current branch"""
        pass
    
    @abstractmethod
    async def diff(self, commit1: str, commit2: str) -> Dict[str, Any]:
        """Get diff between two commits"""
        pass
    
    @abstractmethod
    async def log(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get commit history"""
        pass


class IRelationalDatabase(ABC):
    """Interface for relational databases (e.g., SQLite for issue tracking)"""
    
    @abstractmethod
    async def execute(self, query: str, params: Optional[tuple] = None) -> Any:
        """Execute a SQL query"""
        pass
    
    @abstractmethod
    async def fetch_one(self, query: str, params: Optional[tuple] = None) -> Optional[Dict[str, Any]]:
        """Fetch one row"""
        pass
    
    @abstractmethod
    async def fetch_all(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Fetch all rows"""
        pass
    
    @abstractmethod
    async def transaction(self) -> 'ITransaction':
        """Start a transaction"""
        pass


class ITransaction(ABC):
    """Interface for database transactions"""
    
    @abstractmethod
    async def commit(self) -> bool:
        """Commit the transaction"""
        pass
    
    @abstractmethod
    async def rollback(self) -> bool:
        """Rollback the transaction"""
        pass
    
    @abstractmethod
    async def __aenter__(self):
        """Enter transaction context"""
        pass
    
    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit transaction context"""
        pass