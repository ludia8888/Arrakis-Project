"""Common Logging Package

Unified logging utilities for user-service and oms-monolith.
Provides consistent JSON formatting, structured logging, and trace context.
"""

from .filters import AuditFieldFilter, ServiceFilter, TraceIDFilter
from .formatter import JSONFormatter, StructuredFormatter
from .setup import setup_logging

__version__ = "1.0.0"
__all__ = [
    "setup_logging",
    "JSONFormatter",
    "StructuredFormatter",
    "TraceIDFilter",
    "AuditFieldFilter",
    "ServiceFilter",
]
