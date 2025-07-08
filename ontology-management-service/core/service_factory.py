"""
Service Factory for resolving circular dependencies
"""
from typing import Optional, Dict, Any
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from core.interfaces import IBranchService, ITimeTravelService
from core.branch.foundry_branch_service import FoundryBranchService
from core.time_travel.service import TimeTravelQueryService
from core.versioning.version_service import VersionTrackingService, get_version_service
from shared.cache.smart_cache import SmartCache
from common_logging.setup import get_logger

logger = get_logger(__name__)


class ServiceFactory:
    """Factory for creating and managing service instances"""
    
    _instances: Dict[str, Any] = {}
    
    @classmethod
    async def get_version_service(cls) -> VersionTrackingService:
        """Get or create version tracking service"""
        if "version_service" not in cls._instances:
            cls._instances["version_service"] = await get_version_service()
        return cls._instances["version_service"]
    
    @classmethod
    async def get_time_travel_service(
        cls,
        redis_client: Optional[redis.Redis] = None,
        smart_cache: Optional[SmartCache] = None
    ) -> ITimeTravelService:
        """Get or create time travel service"""
        if "time_travel_service" not in cls._instances:
            version_service = await cls.get_version_service()
            
            # Create service without branch_service first
            service = TimeTravelQueryService(
                version_service=version_service,
                redis_client=redis_client,
                smart_cache=smart_cache,
                branch_service=None  # Will be set later
            )
            await service.initialize()
            
            cls._instances["time_travel_service"] = service
            
            # Now inject branch service if available
            if "branch_service" in cls._instances:
                service.branch_service = cls._instances["branch_service"]
                
        return cls._instances["time_travel_service"]
    
    @classmethod
    async def get_branch_service(
        cls,
        db_session: AsyncSession,
        redis_client: Optional[redis.Redis] = None,
        smart_cache: Optional[SmartCache] = None
    ) -> IBranchService:
        """Get or create branch service"""
        if "branch_service" not in cls._instances:
            version_service = await cls.get_version_service()
            time_travel_service = await cls.get_time_travel_service(
                redis_client=redis_client,
                smart_cache=smart_cache
            )
            
            service = FoundryBranchService(
                db_session=db_session,
                time_travel_service=time_travel_service,
                version_service=version_service
            )
            
            cls._instances["branch_service"] = service
            
            # Update time travel service with branch service reference
            if hasattr(time_travel_service, 'branch_service'):
                time_travel_service.branch_service = service
                
        return cls._instances["branch_service"]
    
    @classmethod
    def clear_instances(cls):
        """Clear all cached service instances (useful for testing)"""
        cls._instances.clear()