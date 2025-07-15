"""Domain service interfaces using Python protocols"""

from .schema import SchemaServiceProtocol
from .validation import ValidationServiceProtocol
from .event import EventPublisherProtocol
from .database import DatabaseClientProtocol
from .branch_interface import IBranchService
from .time_travel_interface import ITimeTravelService

__all__ = [
 "SchemaServiceProtocol",
 "ValidationServiceProtocol",
 "EventPublisherProtocol",
 "DatabaseClientProtocol",
 "IBranchService",
 "ITimeTravelService"
]
