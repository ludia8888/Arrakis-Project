"""
oms-event-sdk - Auto-generated SDK for OMS Event API
"""

__version__ = "1.0.0"
__author__ = "OMS Team"

from .client import ClientConfig, EventPublisher, EventSubscriber, OMSEventClient
from .models import *

__all__ = [
    "OMSEventClient",
    "ClientConfig",
    "EventPublisher",
    "EventSubscriber",
    "PublishResult",
    "Subscription",
]
