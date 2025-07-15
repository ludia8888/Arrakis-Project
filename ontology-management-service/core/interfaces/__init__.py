"""Domain service interfaces using Python protocols"""

from .branch_interface import IBranchService
from .database import DatabaseClientProtocol
from .event import EventPublisherProtocol
from .schema import SchemaServiceProtocol
from .time_travel_interface import ITimeTravelService
from .validation import ValidationServiceProtocol

__all__ = [
    "SchemaServiceProtocol",
    "ValidationServiceProtocol",
    "EventPublisherProtocol",
    "DatabaseClientProtocol",
    "IBranchService",
    "ITimeTravelService",
]
