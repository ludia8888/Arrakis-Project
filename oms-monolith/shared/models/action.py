"""
Unified Action Service domain models
Consolidates models from core/action/models.py and eliminates duplication
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ActionType(BaseModel):
    """
    Unified ActionType model - consolidation of core/action and legacy models
    """
    id: str
    objectTypeId: str
    name: str
    displayName: str
    description: Optional[str] = None
    inputSchema: Dict[str, Any]  # JSON Schema
    validationExpression: Optional[str] = None
    webhookUrl: Optional[str] = None
    isBatchable: bool = True
    isAsync: bool = False
    requiresApproval: bool = False
    approvalRoles: List[str] = Field(default_factory=list)
    onSuccessFunction: Optional[str] = None
    onFailureFunction: Optional[str] = None
    maxRetries: int = 3
    timeoutSeconds: int = 300
    batchSize: Optional[int] = 100
    continueOnError: bool = False
    implementation: str  # Plugin name
    status: str = "active"
    versionHash: str
    createdBy: str
    createdAt: datetime
    modifiedBy: str
    modifiedAt: datetime


class ActionDefinition(BaseModel):
    """Action definition for creation/modification"""
    name: str = Field(..., pattern="^[a-zA-Z][a-zA-Z0-9_]*$")
    displayName: str
    description: Optional[str] = None
    objectTypeId: str
    inputSchema: Dict[str, Any]
    validationExpression: Optional[str] = None
    webhookUrl: Optional[str] = None
    isBatchable: bool = True
    isAsync: bool = False
    requiresApproval: bool = False
    approvalRoles: List[str] = Field(default_factory=list)
    maxRetries: int = 3
    timeoutSeconds: int = 300
    implementation: str


class ExecutionOptions(BaseModel):
    """Action execution options"""
    forceAsync: bool = False
    forceSync: bool = False
    priority: str = "normal"  # low, normal, high, critical
    notificationWebhook: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Job(BaseModel):
    """Asynchronous job model"""
    id: str
    actionTypeId: str
    objectIds: List[str]
    parameters: Dict[str, Any]
    status: str  # pending, running, completed, failed, cancelled
    createdBy: str
    createdAt: datetime
    startedAt: Optional[datetime] = None
    completedAt: Optional[datetime] = None
    totalObjects: int
    processedObjects: int = 0
    successfulObjects: int = 0
    failedObjects: int = 0
    progressPercentage: float = 0.0
    estimatedDuration: float
    actualDuration: Optional[float] = None
    errorMessage: Optional[str] = None
    resultSummary: Optional[Dict[str, Any]] = None
    retryCount: int = 0


class ActionResult(BaseModel):
    """Action execution result"""
    actionTypeId: str
    totalObjects: int
    successful: int
    failed: int
    results: List[Dict[str, Any]]
    errors: List[Dict[str, Any]]
    executedBy: str
    executedAt: datetime
    executionTimeMs: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AsyncJobReference(BaseModel):
    """Asynchronous job reference"""
    jobId: str
    statusUrl: str
    estimatedDuration: float
    asyncFallback: bool = False
    message: Optional[str] = None


class ObjectActionResult(BaseModel):
    """Individual object action result"""
    objectId: str
    status: str  # success, failed, skipped
    changes: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    message: Optional[str] = None
    executionTimeMs: Optional[float] = None


class ActionContext(BaseModel):
    """Action execution context"""
    transaction: Any  # TerminusDB Transaction
    user: Dict[str, Any]
    parameters: Dict[str, Any]
    actionType: ActionType
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True


class ActionValidationResult(BaseModel):
    """Action input validation result"""
    isValid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class WebhookPayload(BaseModel):
    """Webhook payload"""
    actionTypeId: str
    actionName: str
    totalObjects: int
    successful: int
    failed: int
    results: List[ObjectActionResult]
    parameters: Dict[str, Any]
    executedBy: str
    executedAt: datetime
    webhookType: str  # completion, failure, progress


class JobFilter(BaseModel):
    """Job filter criteria"""
    status: Optional[List[str]] = None
    actionTypeId: Optional[str] = None
    createdBy: Optional[str] = None
    createdAfter: Optional[datetime] = None
    createdBefore: Optional[datetime] = None


class JobUpdate(BaseModel):
    """Job status update"""
    status: Optional[str] = None
    processedObjects: Optional[int] = None
    successfulObjects: Optional[int] = None
    failedObjects: Optional[int] = None
    progressPercentage: Optional[float] = None
    errorMessage: Optional[str] = None
    resultSummary: Optional[Dict[str, Any]] = None


class ActionPlugin(BaseModel):
    """Action plugin interface"""
    name: str
    version: str
    description: str
    supported_types: List[str]
    configuration_schema: Dict[str, Any]

    class Config:
        # Actual plugins implement this interface
        pass


# Backward compatibility aliases
ActionTypeModel = ActionType