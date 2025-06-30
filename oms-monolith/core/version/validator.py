"""
Version Validator - Pure validation logic for version tracking
"""
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from abc import ABC, abstractmethod

from models.etag import (
    VersionInfo, calculate_content_hash, generate_commit_hash,
    create_json_patch, CacheValidation
)
from core.auth import UserContext
from utils.logger import get_logger

logger = get_logger(__name__)


class VersionValidatorProtocol(ABC):
    """Protocol for version validation"""
    
    @abstractmethod
    def validate_content_change(
        self,
        old_content_hash: Optional[str],
        new_content: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Validate if content has changed"""
        pass
    
    @abstractmethod
    def create_version_info(
        self,
        version: int,
        content_hash: str,
        user: UserContext,
        change_type: str,
        parent_commit: Optional[str] = None,
        change_summary: Optional[str] = None,
        fields_changed: Optional[List[str]] = None
    ) -> VersionInfo:
        """Create version info object"""
        pass
    
    @abstractmethod
    def validate_etag_match(
        self,
        client_etag: str,
        server_etag: str
    ) -> bool:
        """Validate ETag match"""
        pass


class DefaultVersionValidator(VersionValidatorProtocol):
    """Default implementation of version validator"""
    
    def validate_content_change(
        self,
        old_content_hash: Optional[str],
        new_content: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Validate if content has changed"""
        new_content_hash = calculate_content_hash(new_content)
        
        if old_content_hash is None:
            return True, new_content_hash
        
        has_changed = old_content_hash != new_content_hash
        return has_changed, new_content_hash
    
    def create_version_info(
        self,
        version: int,
        content_hash: str,
        user: UserContext,
        change_type: str,
        parent_commit: Optional[str] = None,
        change_summary: Optional[str] = None,
        fields_changed: Optional[List[str]] = None
    ) -> VersionInfo:
        """Create version info object"""
        timestamp = datetime.now(timezone.utc)
        
        # Generate commit hash
        commit_hash = generate_commit_hash(
            parent_commit, content_hash, user.username, timestamp
        )
        
        # Generate ETag
        etag = f'W/"{commit_hash[:12]}-{version}"'
        
        return VersionInfo(
            version=version,
            commit_hash=commit_hash,
            etag=etag,
            last_modified=timestamp,
            modified_by=user.username,
            parent_version=version - 1 if version > 1 else None,
            parent_commit=parent_commit,
            change_type=change_type,
            change_summary=change_summary,
            fields_changed=fields_changed or []
        )
    
    def validate_etag_match(
        self,
        client_etag: str,
        server_etag: str
    ) -> bool:
        """Validate ETag match"""
        return client_etag == server_etag
    
    def calculate_delta_efficiency(
        self,
        old_content: Dict[str, Any],
        new_content: Dict[str, Any]
    ) -> Tuple[str, Any, int]:
        """Calculate most efficient delta representation"""
        # Generate patch
        patches = create_json_patch(old_content, new_content)
        
        # Calculate sizes
        patch_size = len(json.dumps(patches))
        full_size = len(json.dumps(new_content))
        
        # Use patch if it's < 70% of full size
        if patch_size < full_size * 0.7:
            return "patch", patches, patch_size
        else:
            return "full", new_content, full_size
    
    def validate_cache_resources(
        self,
        validation: CacheValidation,
        get_current_etag_func
    ) -> CacheValidation:
        """Validate cache resources (requires ETag lookup function)"""
        # This method requires external ETag lookup
        # Implementation moved to service layer
        return validation