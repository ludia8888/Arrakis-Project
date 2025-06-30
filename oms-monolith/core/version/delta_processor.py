"""
Delta Processor - Handles delta generation and application
"""
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from abc import ABC, abstractmethod

from models.etag import (
    DeltaRequest, DeltaResponse, ResourceDelta, VersionInfo
)
from .repository import VersionRepositoryProtocol
from .validator import VersionValidatorProtocol
from utils.logger import get_logger

logger = get_logger(__name__)


class DeltaProcessorProtocol(ABC):
    """Protocol for delta processing"""
    
    @abstractmethod
    async def generate_delta_response(
        self,
        resource_type: str,
        resource_id: str,
        branch: str,
        delta_request: DeltaRequest,
        current_version: Optional[VersionInfo]
    ) -> DeltaResponse:
        """Generate delta response"""
        pass


class DefaultDeltaProcessor(DeltaProcessorProtocol):
    """Default implementation of delta processor"""
    
    def __init__(
        self,
        repository: VersionRepositoryProtocol,
        validator: VersionValidatorProtocol
    ):
        self.repository = repository
        self.validator = validator
    
    async def generate_delta_response(
        self,
        resource_type: str,
        resource_id: str,
        branch: str,
        delta_request: DeltaRequest,
        current_version: Optional[VersionInfo]
    ) -> DeltaResponse:
        """Generate delta response"""
        # Handle case where resource doesn't exist
        if not current_version:
            return DeltaResponse(
                to_version=VersionInfo(
                    version=0,
                    commit_hash="",
                    etag="",
                    last_modified=datetime.now(timezone.utc),
                    modified_by="system",
                    change_type="not_found"
                ),
                response_type="no_change",
                total_changes=0,
                delta_size=0,
                etag=""
            )
        
        # Check if client is up to date
        if delta_request.client_etag == current_version.etag:
            return DeltaResponse(
                to_version=current_version,
                response_type="no_change",
                total_changes=0,
                delta_size=0,
                etag=current_version.etag
            )
        
        # Get client version if specified
        client_version = None
        if delta_request.client_version:
            client_resource_version = await self.repository.get_version(
                resource_type, resource_id, branch, delta_request.client_version
            )
            if client_resource_version:
                client_version = client_resource_version.current_version
        
        # Try to get cached delta
        if client_version:
            cached_delta = await self.repository.get_delta(
                resource_type, resource_id, branch,
                client_version.version, current_version.version
            )
            
            if cached_delta:
                delta = ResourceDelta(
                    resource_type=resource_type,
                    resource_id=resource_id,
                    operation="update",
                    from_version=client_version.version,
                    to_version=current_version.version,
                    delta_type=cached_delta['delta_type'],
                    patches=cached_delta['delta_content'] 
                        if cached_delta['delta_type'] == 'patch' else None,
                    full_content=cached_delta['delta_content']
                        if cached_delta['delta_type'] == 'full' else None
                )
                
                return DeltaResponse(
                    from_version=client_version,
                    to_version=current_version,
                    response_type="delta",
                    changes=[delta],
                    total_changes=1,
                    delta_size=cached_delta['delta_size'],
                    etag=current_version.etag
                )
        
        # Return full content if no delta available
        content = await self.repository.get_content(
            resource_type, resource_id, branch, current_version.version
        )
        
        if content:
            delta = ResourceDelta(
                resource_type=resource_type,
                resource_id=resource_id,
                operation="update",
                from_version=client_version.version if client_version else None,
                to_version=current_version.version,
                delta_type="full",
                full_content=content
            )
            
            return DeltaResponse(
                from_version=client_version,
                to_version=current_version,
                response_type="full",
                changes=[delta],
                total_changes=1,
                delta_size=len(json.dumps(content)),
                etag=current_version.etag
            )
        
        # Fallback to no change
        return DeltaResponse(
            to_version=current_version,
            response_type="no_change",
            total_changes=0,
            delta_size=0,
            etag=current_version.etag
        )
    
    async def generate_and_store_delta(
        self,
        resource_type: str,
        resource_id: str,
        branch: str,
        from_version: int,
        to_version: int,
        new_content: Dict[str, Any]
    ):
        """Generate and store delta between versions"""
        # Get old content
        old_content = await self.repository.get_content(
            resource_type, resource_id, branch, from_version
        )
        
        if not old_content:
            return
        
        # Calculate most efficient delta
        delta_type, delta_content, delta_size = self.validator.calculate_delta_efficiency(
            old_content, new_content
        )
        
        # Store delta
        await self.repository.save_delta(
            resource_type, resource_id, branch,
            from_version, to_version, delta_type,
            delta_content, delta_size
        )