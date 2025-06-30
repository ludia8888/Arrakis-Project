"""
Scheduler-specific exceptions for proper error handling.

These exceptions replace generic catch-all handlers in the scheduler module
to provide better error visibility and handling in a life-critical system.
"""

from shared.exceptions import (
    OntologyException,
    ServiceException,
    InfrastructureException,
    ValidationError
)


# Job Execution Exceptions
class JobExecutionException(OntologyException):
    """Base exception for job execution errors."""
    pass


class JobTimeoutError(JobExecutionException):
    """Job execution timed out."""
    pass


class JobCancelledError(JobExecutionException):
    """Job execution was cancelled."""
    pass


class JobImportError(JobExecutionException):
    """Failed to import job module or function."""
    pass


class JobRuntimeError(JobExecutionException):
    """Runtime error during job execution."""
    pass


# Schedule Calculation Exceptions
class ScheduleException(OntologyException):
    """Base exception for schedule-related errors."""
    pass


class InvalidCronExpressionError(ScheduleException):
    """Invalid cron expression provided."""
    pass


class ScheduleCalculationError(ScheduleException):
    """Failed to calculate next schedule time."""
    pass


class InvalidScheduleError(ScheduleException):
    """Invalid schedule configuration."""
    pass


# Notification Exceptions
class NotificationException(ServiceException):
    """Base exception for notification errors."""
    pass


class EmailNotificationError(NotificationException):
    """Failed to send email notification."""
    pass


class SlackNotificationError(NotificationException):
    """Failed to send Slack notification."""
    pass


class WebhookNotificationError(NotificationException):
    """Failed to send webhook notification."""
    pass


# State Management Exceptions  
class StateManagementException(InfrastructureException):
    """Base exception for state management errors."""
    pass


class StateParsingError(StateManagementException):
    """Failed to parse state data."""
    pass


class StateUpdateError(StateManagementException):
    """Failed to update state."""
    pass


class StateLockError(StateManagementException):
    """Failed to acquire state lock."""
    pass