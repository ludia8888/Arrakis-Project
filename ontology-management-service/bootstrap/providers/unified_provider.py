"""
Unified provider that doesn't rely on punq or dependency_injector
Temporary solution to fix DI framework conflicts
"""
import os
from typing import Optional

from arrakis_common import get_logger
from bootstrap.config import get_config
from database.clients.postgres_client_secure import PostgresClientSecure

# SQLite client removed - PostgreSQL-only architecture
from database.clients.terminus_db import TerminusDBClient
from database.clients.unified_database_client import UnifiedDatabaseClient

logger = get_logger(__name__)

# Global instance cache
_db_client_instance: Optional[UnifiedDatabaseClient] = None


async def get_unified_db_client() -> UnifiedDatabaseClient:
 """
 Get or create a unified database client instance.
 Uses a simple singleton pattern to avoid DI framework conflicts.
 """
 global _db_client_instance

 logger.debug("get_unified_db_client called")

 if _db_client_instance is not None:
 logger.debug("Returning existing database client instance")
 return _db_client_instance

 logger.info("Creating new unified database client...")

 config = get_config()
 logger.debug(f"Config loaded: environment={config.service.environment}")

 # Create TerminusDB client using the config
 terminus_config = config.terminusdb

 logger.debug(
 f"Creating TerminusDB client: endpoint={terminus_config.endpoint},
     user={terminus_config.user}"
 )

 try:
 # TerminusDBClient expects the TerminusDBConfig directly
 terminus_client = TerminusDBClient(config = terminus_config)
 logger.info("TerminusDB client created successfully")
 except Exception as e:
 logger.error(
 f"Failed to create TerminusDB client: {type(e).__name__}: {str(e)}"
 )
 raise

 # SQLite fallback removed - PostgreSQL-only architecture

 # Create PostgreSQL client if configured
 postgres_client = None
 if config.postgres and config.postgres.host:
 try:
 postgres_client = PostgresClientSecure(config = config.postgres.model_dump())
 except Exception as e:
 logger.warning(f"Failed to create PostgreSQL client: {e}")

 # Create unified database client - PostgreSQL + TerminusDB only
 db_client = UnifiedDatabaseClient(
 terminus_client = terminus_client, postgres_client = postgres_client
 )

 await db_client.connect()
 _db_client_instance = db_client

 logger.info("Unified database client created and connected")
 return db_client


async def close_unified_db_client():
 """Close the unified database client if it exists"""
 global _db_client_instance

 if _db_client_instance is not None:
 await _db_client_instance.close()
 _db_client_instance = None
 logger.info("Unified database client closed")
