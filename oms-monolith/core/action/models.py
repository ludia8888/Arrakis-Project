"""
Action Service 도메인 모델
DEPRECATED: Models moved to shared.models.action for consolidation
"""

import logging

# Import all models from shared location to maintain backward compatibility
from shared.models.action import (
    ActionType,
    ActionDefinition,
    ExecutionOptions,
    Job,
    ActionResult,
    AsyncJobReference,
    ObjectActionResult,
    ActionContext,
    ActionValidationResult,
    WebhookPayload,
    JobFilter,
    JobUpdate,
    ActionPlugin,
    ActionTypeModel
)

logger = logging.getLogger(__name__)

logger.warning(
    "core.action.models is deprecated. Import directly from shared.models.action instead."
)

# Re-export everything for backward compatibility
__all__ = [
    'ActionType',
    'ActionDefinition',
    'ExecutionOptions',
    'Job',
    'ActionResult',
    'AsyncJobReference',
    'ObjectActionResult',
    'ActionContext',
    'ActionValidationResult',
    'WebhookPayload',
    'JobFilter',
    'JobUpdate',
    'ActionPlugin',
    'ActionTypeModel'
]
