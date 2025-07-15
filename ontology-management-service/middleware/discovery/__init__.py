"""
Service discovery middleware package
"""

from .balancer import LoadBalancer
from .coordinator import DiscoveryCoordinator
from .health import HealthChecker
from .models import (
    LoadBalancerStrategy,
    ServiceEndpoint,
    ServiceInstance,
    ServiceRegistration,
    ServiceStatus,
)
from .providers.base import DiscoveryProvider
from .providers.dns import DnsDiscoveryProvider
from .providers.redis import RedisDiscoveryProvider

__all__ = [
    "ServiceInstance",
    "ServiceEndpoint",
    "ServiceStatus",
    "LoadBalancerStrategy",
    "ServiceRegistration",
    "DiscoveryProvider",
    "RedisDiscoveryProvider",
    "DnsDiscoveryProvider",
    "LoadBalancer",
    "HealthChecker",
    "DiscoveryCoordinator",
]
