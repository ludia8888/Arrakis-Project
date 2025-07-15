"""
Production NATS Client Module
Uses real NATS client implementation only - NO FALLBACKS
"""

# Production imports - real NATS client must be available
from .real_nats_client import RealNATSClient as NATSClient
from .real_nats_client import get_nats_client, get_real_nats_client

__all__ = ["NATSClient", "get_nats_client", "get_real_nats_client"]
