"""
DEPRECATED: This module is deprecated and will be removed.
Use core.branch.conflict_resolver instead.

This file is kept for backward compatibility only.
"""

import warnings
from core.branch.conflict_resolver import ConflictResolver as BranchConflictResolver

warnings.warn(
    "core.schema.conflict_resolver is deprecated. Use core.branch.conflict_resolver instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export for backward compatibility
ConflictResolver = BranchConflictResolver

# Create global instance for compatibility
conflict_resolver = ConflictResolver()