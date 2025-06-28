"""
Branch Service Factory
Creates appropriate branch service implementation based on configuration
"""
import logging
from typing import Optional

from shared.config import settings
from core.branch.interfaces import IBranchService

logger = logging.getLogger(__name__)


class BranchServiceFactory:
    """Factory for creating branch service implementations"""
    
    _instance: Optional[IBranchService] = None
    
    @classmethod
    def create_branch_service(cls, force_new: bool = False) -> IBranchService:
        """
        Create or return branch service instance
        
        Args:
            force_new: Force creation of new instance
            
        Returns:
            Branch service implementation
        """
        if cls._instance is not None and not force_new:
            return cls._instance
        
        # Check feature flag
        use_terminus_native = getattr(settings, 'USE_TERMINUS_NATIVE_BRANCH', False)
        
        if use_terminus_native:
            logger.info("Creating TerminusDB Native Branch Service")
            from core.branch.terminus_adapter import TerminusNativeBranchService
            
            cls._instance = TerminusNativeBranchService(
                terminus_url=getattr(settings, 'TERMINUS_SERVER_URL', 'http://localhost:6363'),
                database=getattr(settings, 'TERMINUS_DB', 'ontology_db'),
                organization=getattr(settings, 'TERMINUS_ORGANIZATION', 'admin')
            )
        else:
            logger.info("Creating Legacy Branch Service")
            from core.branch.service import BranchService
            from core.branch.diff_engine import DiffEngine
            from core.branch.conflict_resolver import ConflictResolver
            
            # Legacy service initialization with required dependencies
            tdb_endpoint = getattr(settings, 'TERMINUS_SERVER_URL', 'http://localhost:6363')
            diff_engine = DiffEngine(tdb_endpoint)
            conflict_resolver = ConflictResolver()
            
            cls._instance = BranchService(
                tdb_endpoint=tdb_endpoint,
                diff_engine=diff_engine,
                conflict_resolver=conflict_resolver
            )
        
        return cls._instance
    
    @classmethod
    def reset(cls):
        """Reset cached instance"""
        cls._instance = None


def get_branch_service() -> IBranchService:
    """Convenience function to get branch service"""
    return BranchServiceFactory.create_branch_service()