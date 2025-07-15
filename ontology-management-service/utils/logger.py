"""
Logger Bridge - Connects existing logger usage to common_logging
Maintains backward compatibility while migrating to common_logging
"""

import logging
import warnings
from typing import Any, Dict, Optional, Union

# Standard logging setup since common_logging module doesn't exist
# Using local implementations for structured logging

# Production imports - provide original logger components inline
# These components were moved from logger_original to maintain backward compatibility


class OriginalStructuredFormatter(logging.Formatter):
 """Original structured formatter for backward compatibility"""

 def format(self, record):
 return super().format(record)


class StructuredLoggerAdapter(logging.LoggerAdapter):
 """Structured logger adapter for backward compatibility"""

 def process(self, msg, kwargs):
 return msg, kwargs


def log_operation_start(logger, operation: str, **kwargs):
 """Log operation start"""
 logger.info(f"Starting operation: {operation}", extra = kwargs)


def log_operation_end(logger, operation: str, **kwargs):
 """Log operation end"""
 logger.info(f"Completed operation: {operation}", extra = kwargs)


def log_validation_result(logger, result: bool, **kwargs):
 """Log validation result"""
 logger.info(f"Validation result: {result}", extra = kwargs)


def log_performance_metric(logger, metric: str, value: float, **kwargs):
 """Log performance metric"""
 logger.info(f"Performance metric {metric}: {value}", extra = kwargs)


def configure_production_logging(**kwargs):
 """Configure production logging"""
 return setup_production_logging(**kwargs)


def configure_development_logging(**kwargs):
 """Configure development logging"""
 return setup_development_logging(**kwargs)


# Re-export original components and common_logging components
__all__ = [
 "get_logger",
 "get_structured_logger",
 "setup_logging",
 "setup_development_logging",
 "setup_production_logging",
 "JSONFormatter",
 "StructuredFormatter", # from common_logging
 "OriginalStructuredFormatter", # from utils.logger_original
 "TraceIDFilter",
 "AuditFieldFilter",
 "ServiceFilter",
 "StructuredLoggerAdapter", # backward compatibility
 "log_operation_start",
 "log_operation_end",
 "log_validation_result",
 "log_performance_metric",
 "configure_production_logging",
 "configure_development_logging",
]


def get_logger(
 name: Optional[str] = None,
 level: str = "INFO",
 use_json: bool = None,
 service_name: str = "oms-monolith",
 version: str = "1.0.0",
):
 """
 Bridge function that redirects to common_logging
 Maintains the same interface as original logger.py
 """
 # Show deprecation warning on first use
 if not hasattr(get_logger, "_warning_shown"):
 warnings.warn(
 "utils.logger.get_logger is being migrated to common_logging.setup.get_logger. "
 "Please update your imports to use common_logging directly.",
 DeprecationWarning,
 stacklevel = 2,
 )
 get_logger._warning_shown = True

 # Configure common_logging based on parameters
 import os

 if use_json is None:
 use_json = os.environ.get("LOG_FORMAT", "text").lower() == "json"

 # Setup common_logging if not already done
 level_str = str(level)
 if level_str.startswith("LogLevel."):
 level_str = level_str.replace("LogLevel.", "")

 format_type = "json" if use_json else "structured"
 setup_logging(
 service = service_name, version = version, level = level_str, format_type = format_type
 )

 # Return common_logging logger
 return common_get_logger(name or __name__)


def get_structured_logger(
 name: Optional[str] = None, context: Dict[str, Any] = None, **kwargs
):
 """
 Bridge function for structured logger
 Maps to common_logging structured logger
 """
 # Setup common_logging with extra fields from context
 if context:
 setup_logging(service = "oms-monolith", extra_fields = context, **kwargs)

 # Get common_logging logger
 return common_get_logger(name or __name__)


# Auto-configuration based on environment - production level
import os

if os.environ.get("ENVIRONMENT", "development").lower() in [
 "production",
 "prod",
 "staging",
]:
 setup_production_logging(service = "oms-monolith")
else:
 setup_development_logging(service = "oms-monolith")
