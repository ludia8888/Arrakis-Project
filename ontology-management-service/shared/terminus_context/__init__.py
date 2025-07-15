"""
TerminusDB Context Management - Branch, Author, and Trace ID handling
"""
from .constants import (
    DEFAULT_BRANCH,
    ENV,
    format_author,
    format_branch,
    get_default_branch,
    is_readonly_branch,
    parse_branch,
)
from .context import (
    OverrideAuthor,
    OverrideBranch,
    build_commit_message,
    get_author,
    get_branch,
    get_commit_message,
    get_terminus_context,
    get_trace_id,
    set_author,
    set_branch,
    set_request_context,
    set_trace_id,
)

__all__ = [
    # Constants
    "ENV",
    "DEFAULT_BRANCH",
    "get_default_branch",
    "format_branch",
    "parse_branch",
    "is_readonly_branch",
    "format_author",
    # Context functions
    "get_author",
    "set_author",
    "get_branch",
    "set_branch",
    "get_trace_id",
    "set_trace_id",
    "get_commit_message",
    "build_commit_message",
    "OverrideBranch",
    "OverrideAuthor",
    "get_terminus_context",
    "set_request_context",
]
