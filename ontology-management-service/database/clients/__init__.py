# Export unified HTTP client and database clients
# Lazy import TerminusDBClient to avoid missing httpx_pool dependency during tests
# from .terminus_db import TerminusDBClient
from .redis_ha_client import RedisHAClient
from .unified_http_client import (
    ClientMode,
    HTTPClientConfig,
    UnifiedHTTPClient,
    create_basic_client,
    create_secure_client,
    create_service_client,
)

__all__ = [
    # HTTP Clients
    "UnifiedHTTPClient",
    "create_basic_client",
    "create_secure_client",
    "create_service_client",
    "ClientMode",
    "HTTPClientConfig",
    # Database Clients
    # "TerminusDBClient",
    "RedisHAClient",
]
