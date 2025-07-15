"""
OMS common exception classes
Define business logic and system level exceptions separately
"""

from typing import Any, Dict, Optional


class OMSException(Exception):
    """OMS system top-level exception class"""

    pass


class ConcurrencyError(OMSException):
    """Concurrency conflict exception

    Raised when optimistic locking fails
    - Concurrent modification attempt on the same resource
    - Update failure due to version mismatch
    """

    pass


class ConflictError(OMSException):
    """Business logic conflict exception

    Raised when business rules are violated
    - Duplicate resource creation attempt
    - Invalid state transition
    - Unauthorized operation attempt
    """

    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        expected_commit: Optional[str] = None,
        actual_commit: Optional[str] = None,
        merge_hints: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)

    self.message = message
    self.resource_type = resource_type
    self.resource_id = resource_id
    self.expected_commit = expected_commit
    self.actual_commit = actual_commit
    self.merge_hints = merge_hints


class ValidationError(OMSException):
    """Data validation failure exception

    Raised when input data fails validation
    """

    pass


class ResourceNotFoundError(OMSException):
    """Resource not found exception

    Raised when requested resource does not exist
    """

    pass


class ServiceUnavailableError(OMSException):
    """Service unavailable exception

    Raised when external service or dependency is temporarily unavailable
    """

    pass
