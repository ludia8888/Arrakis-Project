"""
Database Client Factory

Centralized factory for all database clients in the OMS system.
This factory ensures proper singleton management and configuration.
"""

import os
import logging
from typing import Dict, Any, Optional
from functools import lru_cache

from shared.database.interfaces import (
    IDocumentDatabase,
    ICacheDatabase,
    IExternalService,
    IVersionControl,
    IRelationalDatabase
)

# Import actual implementations
from database.clients.terminus_db import TerminusDBClient
from database.clients.redis_ha_client import RedisHAClient
from core.integrations.user_service_client import UserServiceClient
from core.integrations.iam_service_client import get_iam_service_client

# For audit service, we'll create a simple wrapper
from core.audit.audit_database import get_audit_db

logger = logging.getLogger(__name__)


class DatabaseClientFactory:
    """
    Factory for creating and managing database client instances.
    Uses singleton pattern to ensure only one instance per client type.
    """
    
    _instances: Dict[str, Any] = {}
    _config: Dict[str, Any] = {}
    
    @classmethod
    def configure(cls, config: Dict[str, Any]) -> None:
        """Configure the factory with database connection settings"""
        cls._config = config
        logger.info("Database client factory configured")
    
    @classmethod
    def get_terminus_client(cls) -> IDocumentDatabase:
        """Get TerminusDB client instance (singleton)"""
        if 'terminus' not in cls._instances:
            # Get config from environment or provided config
            url = cls._config.get('TERMINUS_URL', os.getenv('TERMINUS_URL', 'http://localhost:6363'))
            key = cls._config.get('TERMINUS_KEY', os.getenv('TERMINUS_KEY'))
            account = cls._config.get('TERMINUS_ACCOUNT', os.getenv('TERMINUS_ACCOUNT', 'admin'))
            cert_path = cls._config.get('TERMINUS_CERT_PATH', os.getenv('TERMINUS_CERT_PATH'))
            
            cls._instances['terminus'] = TerminusDBClient(
                url=url,
                key=key,
                account=account,
                cert_path=cert_path
            )
            logger.info(f"Created TerminusDB client for {url}")
        
        return cls._instances['terminus']
    
    @classmethod
    def get_redis_client(cls) -> ICacheDatabase:
        """Get Redis HA client instance (singleton)"""
        if 'redis' not in cls._instances:
            # Get config from environment or provided config
            sentinels = cls._config.get('REDIS_SENTINELS', [
                (os.getenv('REDIS_SENTINEL_HOST', 'localhost'), 
                 int(os.getenv('REDIS_SENTINEL_PORT', '26379')))
            ])
            master_name = cls._config.get('REDIS_MASTER', os.getenv('REDIS_MASTER', 'mymaster'))
            password = cls._config.get('REDIS_PASSWORD', os.getenv('REDIS_PASSWORD'))
            
            cls._instances['redis'] = RedisHAClient(
                sentinels=sentinels,
                master_name=master_name,
                password=password
            )
            logger.info(f"Created Redis HA client for master: {master_name}")
        
        return cls._instances['redis']
    
    @classmethod
    def get_user_service_client(cls) -> IExternalService:
        """Get User Service client instance (singleton)"""
        if 'user_service' not in cls._instances:
            base_url = cls._config.get('USER_SERVICE_URL', 
                                      os.getenv('USER_SERVICE_URL', 'http://user-service:8080'))
            timeout = cls._config.get('USER_SERVICE_TIMEOUT', 30)
            
            cls._instances['user_service'] = UserServiceClient(
                base_url=base_url,
                timeout=timeout
            )
            logger.info(f"Created User Service client for {base_url}")
        
        return cls._instances['user_service']
    
    @classmethod
    def get_iam_service_client(cls) -> IExternalService:
        """Get IAM Service client instance (singleton)"""
        if 'iam_service' not in cls._instances:
            # Use the existing get_iam_service_client function
            cls._instances['iam_service'] = get_iam_service_client()
            logger.info("Created IAM Service client")
        
        return cls._instances['iam_service']
    
    @classmethod
    def get_audit_service_client(cls) -> Any:
        """Get Audit Service client instance (singleton)"""
        if 'audit_service' not in cls._instances:
            # Use the existing get_audit_db function
            cls._instances['audit_service'] = get_audit_db()
            logger.info("Created Audit Service client")
        
        return cls._instances['audit_service']
    
    @classmethod
    def get_version_control_client(cls) -> IVersionControl:
        """
        Get version control client (uses TerminusDB native versioning).
        This returns the same instance as get_terminus_client() since
        TerminusDB provides native version control.
        """
        # TerminusDB client implements both IDocumentDatabase and IVersionControl
        return cls.get_terminus_client()
    
    @classmethod
    def get_client(cls, client_type: str) -> Any:
        """
        Generic method to get any client by type name.
        
        Args:
            client_type: One of 'terminus', 'redis', 'user_service', 
                        'iam_service', 'audit_service', 'version_control'
        
        Returns:
            The requested client instance
        
        Raises:
            ValueError: If client_type is not recognized
        """
        client_map = {
            'terminus': cls.get_terminus_client,
            'redis': cls.get_redis_client,
            'user_service': cls.get_user_service_client,
            'iam_service': cls.get_iam_service_client,
            'audit_service': cls.get_audit_service_client,
            'version_control': cls.get_version_control_client,
        }
        
        if client_type not in client_map:
            raise ValueError(f"Unknown client type: {client_type}")
        
        return client_map[client_type]()
    
    @classmethod
    def reset(cls) -> None:
        """
        Reset all client instances. Useful for testing or configuration changes.
        This will close all existing connections before clearing.
        """
        logger.info("Resetting all database client instances")
        
        # Close connections if clients have close methods
        for name, client in cls._instances.items():
            if hasattr(client, 'close'):
                try:
                    client.close()
                    logger.info(f"Closed connection for {name}")
                except Exception as e:
                    logger.error(f"Error closing {name}: {e}")
        
        cls._instances.clear()
        cls._config.clear()
    
    @classmethod
    def get_status(cls) -> Dict[str, bool]:
        """Get connection status for all initialized clients"""
        status = {}
        
        for name, client in cls._instances.items():
            try:
                if hasattr(client, 'health_check'):
                    status[name] = client.health_check()
                elif hasattr(client, 'ping'):
                    status[name] = client.ping()
                else:
                    status[name] = True  # Assume healthy if no check method
            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                status[name] = False
        
        return status


# Convenience functions for backward compatibility
@lru_cache(maxsize=1)
def get_database_factory() -> DatabaseClientFactory:
    """Get the singleton DatabaseClientFactory instance"""
    return DatabaseClientFactory


def get_terminus_client() -> IDocumentDatabase:
    """Convenience function to get TerminusDB client"""
    return DatabaseClientFactory.get_terminus_client()


def get_redis_client() -> ICacheDatabase:
    """Convenience function to get Redis client"""
    return DatabaseClientFactory.get_redis_client()


def get_user_service_client() -> IExternalService:
    """Convenience function to get User Service client"""
    return DatabaseClientFactory.get_user_service_client()