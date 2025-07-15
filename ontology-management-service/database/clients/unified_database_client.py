import asyncio
import logging
from typing import Optional

from bootstrap.config import AppConfig, get_config

from .base import DatabaseBackend
from .postgres_client_secure import PostgresClientSecure
from .terminus_db import TerminusDBClient

# SQLite support removed - PostgreSQL-only architecture

logger = logging.getLogger(__name__)

_db_client: Optional["UnifiedDatabaseClient"] = None
_db_client_lock = asyncio.Lock()


class UnifiedDatabaseClient:
 """A unified client to interact with multiple database backends - PostgreSQL + TerminusDB only."""

 def __init__(
 self,
 terminus_client: Optional[TerminusDBClient] = None,
 postgres_client: Optional[PostgresClientSecure] = None,
 ):
 self.terminus_client = terminus_client
 self.postgres_client = postgres_client

 async def connect(self):
 if self.terminus_client:
 await self.terminus_client._initialize_client()
 logger.info("Unified Database Client connected.")

 async def close(self):
 if self.terminus_client:
 await self.terminus_client.close()
 logger.info("Unified Database Client disconnected.")

 def get_client(self, backend: DatabaseBackend):
 if backend == DatabaseBackend.TERMINUSDB:
 return self.terminus_client
 elif backend == DatabaseBackend.POSTGRES:
 return self.postgres_client
 # SQLite backend removed - PostgreSQL-only architecture
 else:
 raise ValueError(f"Unknown database backend: {backend}")


async def get_unified_database_client(config: AppConfig) -> "UnifiedDatabaseClient":
 """
 Singleton factory for UnifiedDatabaseClient.

 This function creates and initializes the database client based on the
 provided application settings. It's designed to be used with the
 dependency-injector library, which passes the main `AppConfig` object.

 Args:
 config: The main application settings object.

 Returns:
 An initialized and connected UnifiedDatabaseClient instance.
 """
 global _db_client
 async with _db_client_lock:
 if _db_client:
 return _db_client

 logger.info("Initializing UnifiedDatabaseClient for the first time...")

 terminus_client_instance = None
 if config.terminusdb:
 terminus_client_instance = TerminusDBClient(
 config = config.terminusdb, service_name = config.service.name
 )
 else:
 logger.warning(
 "TerminusDB config not found, client will not be initialized."
 )

 _db_client = UnifiedDatabaseClient(
 terminus_client = terminus_client_instance,
 )
 await _db_client.connect()
 logger.info("UnifiedDatabaseClient has been successfully initialized.")
 return _db_client


async def get_unified_database_client_legacy(
 config: AppConfig = None,
) -> "UnifiedDatabaseClient":
 """
 Legacy or alternative factory for the client.
 Ensures compatibility by accepting the config object.

 Args:
 config: The main application settings object (optional).

 Returns:
 An initialized and connected UnifiedDatabaseClient instance.
 """
 if not config:
 config = get_config()

 return await get_unified_database_client(config)
