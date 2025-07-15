"""
Logging Setup Module for Arrakis Common

This module provides unified logging configuration functionality
that replaces the old common_logging imports throughout the MSA.
"""

import logging
import os
from typing import Optional, Dict, Any, List


def setup_logging(
 service: str = "unknown",
 version: str = "1.0.0",
 level: str = "INFO",
 format_type: str = "json",
 environment: Optional[str] = None,
 enable_trace: bool = True,
 enable_audit: bool = False,
 mask_sensitive: bool = True,
 extra_fields: Optional[Dict[str, Any]] = None,
 handlers: Optional[List[logging.Handler]] = None
) -> logging.Logger:
 """Setup unified logging configuration.

 Args:
 service: Service name
 version: Service version
 level: Log level ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
 format_type: Format type ("json", "structured", "audit")
 environment: Environment name (defaults to ENVIRONMENT env var)
 enable_trace: Enable trace ID injection
 enable_audit: Enable audit-specific formatting
 mask_sensitive: Enable sensitive data masking
 extra_fields: Additional fields to include in logs
 handlers: Custom handlers (defaults to console handler)

 Returns:
 Configured root logger
 """
 # Get environment from env var if not provided
 if environment is None:
 environment = os.getenv("ENVIRONMENT", "unknown")

 # Get log level from env var if not explicitly set
 if level == "INFO":
 level = os.getenv("LOG_LEVEL", "INFO").upper()

 # Clear existing handlers
 root_logger = logging.getLogger()
 root_logger.handlers.clear()

 # Set log level
 root_logger.setLevel(getattr(logging, level))

 # Create basic formatter
 formatter = logging.Formatter(
 '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
 )

 # Create handlers
 if handlers is None:
 handlers = [logging.StreamHandler()]

 # Configure handlers
 for handler in handlers:
 handler.setFormatter(formatter)
 root_logger.addHandler(handler)

 # Log setup completion
 logger = logging.getLogger(__name__)
 logger.info(
 "Logging configured for service: %s", service
 )

 return root_logger


def get_logger(name: str) -> logging.Logger:
 """Get logger instance.

 Args:
 name: Logger name (typically __name__)

 Returns:
 Logger instance
 """
 return logging.getLogger(name)


def setup_development_logging(service: str, **kwargs) -> logging.Logger:
 """Setup development-friendly logging configuration."""
 return setup_logging(
 service = service,
 level = "DEBUG",
 environment = "development",
 mask_sensitive = False,
 **kwargs
 )


def setup_production_logging(service: str, **kwargs) -> logging.Logger:
 """Setup production logging configuration."""
 return setup_logging(
 service = service,
 level = "INFO",
 environment = "production",
 mask_sensitive = True,
 **kwargs
 )
