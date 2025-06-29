"""
Shared modules for OMS

This module provides common functionality used across the OMS monolith including:
- Infrastructure components (cache, database, messaging)
- Security and authentication utilities
- Event handling and publishing
- Observability (metrics, tracing, logging)
- Common models and utilities
"""

# Import commonly used components for easier access
from shared.events import EventPublisher

__all__ = ['EventPublisher']