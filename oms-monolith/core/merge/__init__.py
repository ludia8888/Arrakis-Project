"""
Merge Engine Module
Unified merge functionality for OMS
"""
from .unified_engine import UnifiedMergeEngine, get_unified_merge_engine
from .merge_factory import MergeEngineFactory, get_merge_engine
from .legacy_adapter import LegacyMergeAdapter

__all__ = [
    'UnifiedMergeEngine',
    'get_unified_merge_engine',
    'MergeEngineFactory', 
    'get_merge_engine',
    'LegacyMergeAdapter'
]