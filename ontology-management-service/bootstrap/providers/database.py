"""Database providers for all database clients"""
from typing import Optional

import punq
from bootstrap.config import AppConfig
from database.clients.postgres_client import PostgresClient

# SQLite client removed - PostgreSQL-only architecture
from database.clients.postgres_client_secure import PostgresClientSecure
from database.clients.terminus_db import TerminusDBClient

# SQLite secure client removed - PostgreSQL-only architecture
from database.clients.unified_database_client import UnifiedDatabaseClient

from .base import SingletonProvider


class PostgresClientProvider(SingletonProvider[PostgresClient]):
 """Provider for PostgresClient instances."""

 def __init__(self, container: punq.Container):
 super().__init__()
 self._container = container
 self._instance: Optional[PostgresClient] = None

 async def _create(self) -> PostgresClient:
 config = self._container.resolve(AppConfig)
 if not config.postgres:
 raise ValueError("PostgreSQL configuration is missing.")
 client = PostgresClientSecure(config.postgres.model_dump())
 await client.connect()
 return client

 async def startup(self):
 client = await self.provide()
 await client.connect()

 async def shutdown(self):
 if self._instance is not None:
 client = await self.provide()
 await client.close()


# SQLiteClientProvider removed - PostgreSQL-only architecture


class TerminusDBClientProvider(SingletonProvider[TerminusDBClient]):
 """Provider for TerminusDBClient instances."""

 def __init__(self, container: punq.Container):
 super().__init__()
 self._container = container
 self._instance: Optional[TerminusDBClient] = None

 async def _create(self) -> TerminusDBClient:
 config = self._container.resolve(AppConfig)
 if not config.terminusdb:
 raise ValueError("TerminusDB configuration is missing.")

 client = TerminusDBClient(
 server_url = config.terminusdb.url,
 team = config.terminusdb.team,
 user = config.terminusdb.user,
 database = config.terminusdb.database,
 token = config.terminusdb.token,
 )
 await client.connect()
 return client

 async def startup(self):
 client = await self.provide()
 await client.connect()

 async def shutdown(self):
 if self._instance is not None:
 client = await self.provide()
 await client.close()


class UnifiedDatabaseProvider(SingletonProvider[UnifiedDatabaseClient]):
 """Provider for UnifiedDatabaseClient instances."""

 def __init__(self, container: punq.Container):
 self._container = container

 async def _create(self) -> UnifiedDatabaseClient:
 postgres_client: Optional[PostgresClient] = None
 # sqlite_client removed - PostgreSQL-only architecture
 terminusdb_client: Optional[TerminusDBClient] = None

 if self._container.is_registered(PostgresClient):
 postgres_client = self._container.resolve(PostgresClient)

 # SQLite client registration removed - PostgreSQL-only architecture

 if self._container.is_registered(TerminusDBClient):
 terminusdb_client = self._container.resolve(TerminusDBClient)

 client = UnifiedDatabaseClient(
 postgres_client = postgres_client,
 # sqlite_client removed - PostgreSQL-only architecture
 terminus_client = terminusdb_client,
 )
 return client

 async def shutdown(self) -> None:
 pass


# Utility functions for accessing database clients
def get_postgres_client() -> Optional[PostgresClient]:
 """Get the PostgreSQL client instance if available."""
 try:
 from bootstrap.main import container

 if container.is_registered(PostgresClient):
 return container.resolve(PostgresClient)
 except Exception:
 pass
 return None


def get_terminusdb_client() -> Optional[TerminusDBClient]:
 """Get the TerminusDB client instance if available."""
 try:
 from bootstrap.main import container

 if container.is_registered(TerminusDBClient):
 return container.resolve(TerminusDBClient)
 except Exception:
 pass
 return None


def get_unified_client() -> Optional[UnifiedDatabaseClient]:
 """Get the unified database client instance if available."""
 try:
 from bootstrap.main import container

 if container.is_registered(UnifiedDatabaseClient):
 return container.resolve(UnifiedDatabaseClient)
 except Exception:
 pass
 return None
