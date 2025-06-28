"""
Merge Engine Factory
Creates appropriate merge engine based on configuration
"""
import logging
from typing import Optional

from shared.config import settings
from core.branch.interfaces import IMergeEngine

logger = logging.getLogger(__name__)


class MergeEngineFactory:
    """Factory for creating merge engine implementations"""
    
    _instance: Optional[IMergeEngine] = None
    
    @classmethod
    def create_merge_engine(cls, force_new: bool = False) -> IMergeEngine:
        """
        Create or return merge engine instance
        
        Args:
            force_new: Force creation of new instance
            
        Returns:
            Merge engine implementation
        """
        if cls._instance is not None and not force_new:
            return cls._instance
        
        # Check feature flag
        use_unified = getattr(settings, 'USE_UNIFIED_MERGE_ENGINE', True)
        
        if use_unified:
            logger.info("Creating Unified Merge Engine")
            from core.merge.unified_engine import UnifiedMergeEngine
            
            # Get TerminusDB client if using native branch service
            terminus_client = None
            if getattr(settings, 'USE_TERMINUS_NATIVE_BRANCH', False):
                try:
                    from core.branch.service_factory import get_branch_service
                    branch_service = get_branch_service()
                    if hasattr(branch_service, 'client'):
                        terminus_client = branch_service.client
                except:
                    pass
            
            cls._instance = UnifiedMergeEngine(terminus_client)
        else:
            logger.info("Creating Legacy Three-Way Merge Engine")
            from core.merge.legacy_adapter import LegacyMergeAdapter
            
            cls._instance = LegacyMergeAdapter()
        
        return cls._instance
    
    @classmethod
    def reset(cls):
        """Reset cached instance"""
        cls._instance = None


def get_merge_engine() -> IMergeEngine:
    """Convenience function to get merge engine"""
    return MergeEngineFactory.create_merge_engine()