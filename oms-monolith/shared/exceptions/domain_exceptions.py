"""
Domain-Specific Exceptions
Fine-grained exceptions for specific business domains
"""
from typing import Optional, Dict, Any, List
from shared.exceptions import OntologyException, ValidationError


# === Schema Domain Exceptions ===

class SchemaException(OntologyException):
    """Base exception for schema-related errors"""
    pass


class SchemaValidationError(SchemaException, ValidationError):
    """Schema validation failed"""
    def __init__(self, message: str, violations: Optional[List[Dict[str, Any]]] = None):
        super().__init__(message)
        self.violations = violations or []


class SchemaConflictError(SchemaException):
    """Schema conflict detected"""
    def __init__(self, message: str, conflicting_fields: Optional[List[str]] = None):
        super().__init__(message)
        self.conflicting_fields = conflicting_fields or []


class SchemaEvolutionError(SchemaException):
    """Schema evolution/migration error"""
    pass


# === Branch Domain Exceptions ===

class BranchException(OntologyException):
    """Base exception for branch operations"""
    pass


class BranchNotFoundError(BranchException):
    """Branch does not exist"""
    def __init__(self, branch_name: str):
        super().__init__(f"Branch '{branch_name}' not found")
        self.branch_name = branch_name


class BranchMergeConflictError(BranchException):
    """Merge conflict during branch operation"""
    def __init__(self, message: str, conflicts: Optional[List[Dict[str, Any]]] = None):
        super().__init__(message)
        self.conflicts = conflicts or []


class BranchLockError(BranchException):
    """Branch is locked and cannot be modified"""
    def __init__(self, branch_name: str, locked_by: Optional[str] = None):
        message = f"Branch '{branch_name}' is locked"
        if locked_by:
            message += f" by {locked_by}"
        super().__init__(message)
        self.branch_name = branch_name
        self.locked_by = locked_by


# === Validation Domain Exceptions ===

class ValidationDomainException(ValidationError):
    """Base for validation domain errors"""
    pass


class PolicyViolationError(ValidationDomainException):
    """Policy validation failed"""
    def __init__(self, message: str, policy_id: str, violations: Optional[List[str]] = None):
        super().__init__(message)
        self.policy_id = policy_id
        self.violations = violations or []


class DataQualityError(ValidationDomainException):
    """Data quality check failed"""
    def __init__(self, message: str, quality_issues: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.quality_issues = quality_issues or {}


# === Event Processing Exceptions ===

class EventProcessingException(OntologyException):
    """Base for event processing errors"""
    pass


class EventDeduplicationError(EventProcessingException):
    """Duplicate event detected"""
    def __init__(self, event_id: str):
        super().__init__(f"Duplicate event detected: {event_id}")
        self.event_id = event_id


class EventOrderingError(EventProcessingException):
    """Event received out of order"""
    def __init__(self, message: str, expected_sequence: int, received_sequence: int):
        super().__init__(message)
        self.expected_sequence = expected_sequence
        self.received_sequence = received_sequence


class EventHandlerNotFoundError(EventProcessingException):
    """No handler registered for event type"""
    def __init__(self, event_type: str):
        super().__init__(f"No handler registered for event type: {event_type}")
        self.event_type = event_type


# === Traversal Domain Exceptions ===

class TraversalException(OntologyException):
    """Base for graph traversal errors"""
    pass


class TraversalCycleDetectedError(TraversalException):
    """Cycle detected during traversal"""
    def __init__(self, message: str, cycle_path: Optional[List[str]] = None):
        super().__init__(message)
        self.cycle_path = cycle_path or []


class TraversalDepthLimitError(TraversalException):
    """Maximum traversal depth exceeded"""
    def __init__(self, max_depth: int):
        super().__init__(f"Maximum traversal depth ({max_depth}) exceeded")
        self.max_depth = max_depth


# === Version Control Exceptions ===

class VersionControlException(OntologyException):
    """Base for version control errors"""
    pass


class InvalidCommitError(VersionControlException):
    """Invalid commit operation"""
    pass


class HistoryRewriteError(VersionControlException):
    """Attempt to rewrite protected history"""
    def __init__(self, message: str, protected_commits: Optional[List[str]] = None):
        super().__init__(message)
        self.protected_commits = protected_commits or []


# === Batch Processing Exceptions ===

class BatchProcessingException(OntologyException):
    """Base for batch processing errors"""
    pass


class BatchSizeLimitError(BatchProcessingException):
    """Batch size exceeds limit"""
    def __init__(self, batch_size: int, max_size: int):
        super().__init__(f"Batch size {batch_size} exceeds maximum allowed {max_size}")
        self.batch_size = batch_size
        self.max_size = max_size


class PartialBatchFailureError(BatchProcessingException):
    """Some items in batch failed"""
    def __init__(self, message: str, failed_items: Optional[List[Dict[str, Any]]] = None):
        super().__init__(message)
        self.failed_items = failed_items or []
        self.failure_count = len(self.failed_items)