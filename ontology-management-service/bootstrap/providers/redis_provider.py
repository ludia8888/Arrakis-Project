"""
Provider for the Redis client.
"""
import os
from typing import Any, Dict, Optional

import redis.asyncio as redis
from arrakis_common import get_logger
from bootstrap.config import get_config

from .base import Provider

logger = get_logger(__name__)

class RedisProvider(Provider[redis.Redis]):
 """
 Provides a Redis client based on the application configuration.
 Connects to a single Redis instance.
 """
 def __init__(self):
 self._config = get_config().redis
 self._client: Optional[redis.Redis] = None

 async def provide(self) -> redis.Redis:
 """Create and return a Redis client instance."""
 if self._client:
 return self._client

 # Get REDIS_URL from environment first, as it's common in containerized setups
 redis_url_env = os.getenv("REDIS_URL")

 if redis_url_env:
 redis_url = redis_url_env
 logger.info(f"Connecting to Redis using REDIS_URL from environment: {redis_url}")
 elif self._config:
 # Construct the URL from config as a fallback
 redis_url = f"redis://{':'+self._config.password+'@' if self._config.password else ''}{self._config.host}:{self._config.port}/{self._config.db}"
 logger.info(f"Connecting to Redis using constructed URL: redis://{self._config.host}:{self._config.port}/{self._config.db}")
 else:
 raise ValueError("Redis configuration not found and REDIS_URL environment variable is not set.")

 try:
 client_config: Dict[str, Any] = {
 "decode_responses": True
 }
 if self._config:
 client_config["max_connections"] = self._config.max_connections
 client_config["socket_timeout"] = self._config.socket_timeout

 client = redis.from_url(
 redis_url,
 **client_config
 )
 await client.ping()
 if self._config:
 logger.info(f"Successfully connected to Redis at {self._config.host}:{self._config.port}")
 else:
 logger.info(f"Successfully connected to Redis at {redis_url}")
 self._client = client
 except Exception as e:
 logger.error(f"Failed to connect to Redis: {e}")
 raise

 return self._client

 async def shutdown(self) -> None:
 """Close the Redis client connection."""
 if self._client:
 await self._client.close()
 logger.info("Redis connection closed.")
