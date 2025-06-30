"""
Version Tracking Service - Facade for decomposed version components
Maintains existing API while delegating to specialized components
"""
import json
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone

from models.etag import (
    VersionInfo, ResourceVersion, DeltaRequest, DeltaResponse,
    ResourceDelta, VersionConflict, CacheValidation
)
from core.auth import UserContext
from core.version import (
    VersionRepositoryProtocol, SQLiteVersionRepository,
    VersionValidatorProtocol, DefaultVersionValidator,
    DeltaProcessorProtocol, DefaultDeltaProcessor
)
from utils.logger import get_logger

logger = get_logger(__name__)


class VersionTrackingService:
    """
    Service for tracking resource versions and generating deltas
    Facade pattern - delegates to specialized components
    """
    
    def __init__(
        self, 
        repository: Optional[VersionRepositoryProtocol] = None,
        validator: Optional[VersionValidatorProtocol] = None,
        delta_processor: Optional[DeltaProcessorProtocol] = None,
        db_path: Optional[str] = None
    ):
        # Initialize components with dependency injection
        self.repository = repository or SQLiteVersionRepository(db_path)
        self.validator = validator or DefaultVersionValidator()
        self.delta_processor = delta_processor or DefaultDeltaProcessor(
            self.repository, self.validator
        )
        self._initialized = False
    
    async def initialize(self):
        """Initialize version tracking database"""
        if self._initialized:
            return
        
        # Delegate to repository
        await self.repository.initialize()
        
        self._initialized = True
        logger.info("Version tracking service initialized")
    
    async def track_change(
        self,
        resource_type: str,
        resource_id: str,
        branch: str,
        content: Dict[str, Any],
        change_type: str,
        user: UserContext,
        change_summary: Optional[str] = None,
        fields_changed: Optional[List[str]] = None
    ) -> ResourceVersion:
        """Track a change to a resource"""
        # Get previous version info
        prev_version_info = await self.repository.get_previous_version(
            resource_type, resource_id, branch
        )
        
        # Validate content change
        prev_content_hash = prev_version_info[2] if prev_version_info else None
        has_changed, content_hash = self.validator.validate_content_change(
            prev_content_hash, content
        )
        
        # Skip if content hasn't changed
        if not has_changed:
            logger.debug(f"No content change for {resource_type}/{resource_id}")
            return await self.get_resource_version(resource_type, resource_id, branch)
        
        # Determine version number
        new_version = (prev_version_info[0] + 1) if prev_version_info else 1
        prev_commit = prev_version_info[1] if prev_version_info else None
        
        # Create version info
        version_info = self.validator.create_version_info(
            new_version, content_hash, user, change_type,
            prev_commit, change_summary, fields_changed
        )
        
        # Store version
        content_size = len(json.dumps(content))
        await self.repository.save_version(
            resource_type, resource_id, branch,
            version_info, content_hash, content_size, content
        )
        
        # Update branch head
        await self.repository.update_branch_head(
            branch, resource_type, version_info.commit_hash, new_version
        )
        
        # Generate and store delta if applicable
        if prev_version_info:
            await self.delta_processor.generate_and_store_delta(
                resource_type, resource_id, branch,
                prev_version_info[0], new_version, content
            )
        
        # Create resource version object
        resource_version = ResourceVersion(
            resource_type=resource_type,
            resource_id=resource_id,
            branch=branch,
            current_version=version_info,
            content_hash=content_hash,
            content_size=content_size
        )
        
        logger.info(
            f"Tracked version {new_version} for {resource_type}/{resource_id} "
            f"on branch {branch} (commit: {version_info.commit_hash[:12]})"
        )
        
        return resource_version
    
    async def get_resource_version(
        self,
        resource_type: str,
        resource_id: str,
        branch: str,
        version: Optional[int] = None
    ) -> Optional[ResourceVersion]:
        """Get version info for a resource"""
        return await self.repository.get_version(
            resource_type, resource_id, branch, version
        )
    
    async def validate_etag(
        self,
        resource_type: str,
        resource_id: str,
        branch: str,
        client_etag: str
    ) -> Tuple[bool, Optional[ResourceVersion]]:
        """Validate client ETag and return current version"""
        current_version = await self.repository.get_version(
            resource_type, resource_id, branch
        )
        
        if not current_version:
            return False, None
        
        is_valid = self.validator.validate_etag_match(
            client_etag, current_version.current_version.etag
        )
        return is_valid, current_version
    
    async def get_delta(
        self,
        resource_type: str,
        resource_id: str,
        branch: str,
        delta_request: DeltaRequest
    ) -> DeltaResponse:
        """Get delta changes for a resource - Facade delegating to delta processor"""
        # Get current version
        current_version = await self.repository.get_version(
            resource_type, resource_id, branch
        )
        
        # Delegate to delta processor
        return await self.delta_processor.generate_delta_response(
            resource_type, resource_id, branch, delta_request, current_version
        )
    
    async def validate_cache(
        self,
        branch: str,
        validation: CacheValidation
    ) -> CacheValidation:
        """Validate multiple resource ETags"""
        for resource_key, client_etag in validation.resource_etags.items():
            # Parse resource key (format: "type:id")
            parts = resource_key.split(":", 1)
            if len(parts) != 2:
                validation.stale_resources.append(resource_key)
                continue
            
            resource_type, resource_id = parts
            
            # Check current ETag
            current_etag = await self.repository.validate_etag(
                resource_type, resource_id, branch
            )
            
            if not current_etag:
                validation.deleted_resources.append(resource_key)
            elif self.validator.validate_etag_match(client_etag, current_etag):
                validation.valid_resources.append(resource_key)
            else:
                validation.stale_resources.append(resource_key)
        
        return validation
    
    
    async def get_branch_version_summary(
        self,
        branch: str,
        resource_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get version summary for a branch"""
        return await self.repository.get_branch_summary(branch, resource_types)


# Global instance
_version_service: Optional[VersionTrackingService] = None


async def get_version_service() -> VersionTrackingService:
    """Get global version tracking service instance"""
    global _version_service
    if _version_service is None:
        _version_service = VersionTrackingService()
        await _version_service.initialize()
    return _version_service