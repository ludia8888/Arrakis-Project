# Core branch module exports
from .conflict_resolver import ConflictResolver
from .diff_engine import DiffEngine
from .merge_strategies import MergeStrategyImplementor
from .service import BranchService

__all__ = [
    "BranchService",
    "DiffEngine",
    "ConflictResolver",
    "MergeStrategyImplementor",
]
