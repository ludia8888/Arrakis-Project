"""
Database health check implementation
"""
import asyncio
import os
import re
from typing import Any, Optional

from ..models import HealthCheckResult, HealthStatus
from .base import HealthCheck


class DatabaseHealthCheck(HealthCheck):
 """Health check for database connectivity and performance"""

 def __init__(
 self,
 connection_string: str,
 name: str = "database",
 timeout: float = 5.0,
 query: str = "SELECT 1",
 ):
 super().__init__(name, timeout)
 self.connection_string = connection_string
 self.query = query
 self._connection = None

 async def check(self) -> HealthCheckResult:
 """Check database health"""
 try:
 # Import database library dynamically
 try:
 import asyncpg

 return await self._check_postgres()
 except ImportError:
 pass

 try:
 import aiomysql

 return await self._check_mysql()
 except ImportError:
 pass

 # Fallback for generic check
 return await self._check_generic()

 except Exception as e:
 return self.create_result(
 status = HealthStatus.UNHEALTHY,
 message = f"Database connection failed: {str(e)}",
 details={"error": str(e)},
 )

 async def _check_postgres(self) -> HealthCheckResult:
 """PostgreSQL specific health check"""
 import asyncpg

 try:
 # Test connection
 conn = await asyncio.wait_for(
 asyncpg.connect(self.connection_string), timeout = self.timeout
 )

 try:
 # Execute test query
 result = await conn.fetchval(self.query)

 # Get connection pool stats if available
 pool_stats = {}
 if hasattr(conn, "_pool"):
 pool = conn._pool
 pool_stats = {
 "size": pool.get_size(),
 "free": pool.get_idle_size(),
 "used": pool.get_size() - pool.get_idle_size(),
 }

 return self.create_result(
 status = HealthStatus.HEALTHY,
 message = "PostgreSQL connection successful",
 details={
 "query_result": result,
 "pool_stats": pool_stats,
 "database": "postgresql",
 },
 )

 finally:
 await conn.close()

 except asyncio.TimeoutError:
 return self.create_result(
 status = HealthStatus.UNHEALTHY,
 message = f"Database connection timeout ({self.timeout}s)",
 details={"timeout": self.timeout},
 )
 except Exception as e:
 return self.create_result(
 status = HealthStatus.UNHEALTHY,
 message = f"PostgreSQL error: {str(e)}",
 details={"error": str(e), "database": "postgresql"},
 )

 async def _check_mysql(self) -> HealthCheckResult:
 """MySQL specific health check"""
 import aiomysql

 try:
 # Parse MySQL connection string properly
 connection_params = self._parse_mysql_connection_string(
 self.connection_string
 )

 conn = await asyncio.wait_for(
 aiomysql.connect(**connection_params), timeout = self.timeout
 )

 try:
 async with conn.cursor() as cursor:
 await cursor.execute(self.query)
 result = await cursor.fetchone()

 return self.create_result(
 status = HealthStatus.HEALTHY,
 message = "MySQL connection successful",
 details={"query_result": result, "database": "mysql"},
 )

 finally:
 conn.close()

 except asyncio.TimeoutError:
 return self.create_result(
 status = HealthStatus.UNHEALTHY,
 message = f"Database connection timeout ({self.timeout}s)",
 details={"timeout": self.timeout},
 )
 except Exception as e:
 return self.create_result(
 status = HealthStatus.UNHEALTHY,
 message = f"MySQL error: {str(e)}",
 details={"error": str(e), "database": "mysql"},
 )

 async def _check_generic(self) -> HealthCheckResult:
 """Generic database health check"""
 # This would use a generic database interface
 return self.create_result(
 status = HealthStatus.UNKNOWN,
 message = "No specific database driver available",
 details={"supported": ["postgresql", "mysql"]},
 )

 def _parse_mysql_connection_string(self, connection_string: str) -> dict:
 """Parse MySQL connection string into connection parameters"""
 try:
 # Handle mysql:// or mysql+aiomysql:// URLs
 if connection_string.startswith(("mysql://", "mysql+aiomysql://")):
 # Extract connection parts using regex
 pattern = r"mysql(?:\+aiomysql)?://(?:([^:]+)(?::([^@]+))?@)?([^:]+)(?::(\d+))?/([^?]+)(?:\?(.+))?"
 match = re.match(pattern, connection_string)

 if match:
 user, password, host, port, database, params = match.groups()

 connection_params = {
 "host": host or "localhost",
 "port": int(port) if port else 3306,
 "user": user or "root",
 "password": password or "",
 "db": database or "mysql",
 }

 # Parse additional parameters
 if params:
 for param in params.split("&"):
 if "=" in param:
 key, value = param.split("=", 1)
 if key in ("charset", "autocommit"):
 connection_params[key] = value

 return connection_params

 # Fallback to environment variables
 return {
 "host": os.getenv("DB_HOST", "localhost"),
 "port": int(os.getenv("DB_PORT", "3306")),
 "user": os.getenv("DB_USER", "root"),
 "password": os.getenv("DB_PASSWORD", ""),
 "db": os.getenv("DB_NAME", "mysql"),
 }

 except Exception as e:
 # Return default connection parameters if parsing fails
 return {
 "host": "localhost",
 "port": 3306,
 "user": "root",
 "password": "",
 "db": "mysql",
 }
