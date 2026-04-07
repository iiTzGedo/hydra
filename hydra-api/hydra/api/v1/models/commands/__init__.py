"""Command models package.

All command models are split into sub-modules:
- enums.py: Command-related enums
- schemas.py: Shared embedded schemas (CommandTarget, CommandResult, etc.)
- requests.py: Request models
- responses.py: Response models
- registry.py: Command registry/catalog models
"""

# Enums
from .enums import (  # noqa: F401
    CommandExecutionMethod,
    CommandSource,
    CommandStatus,
    CommandType,
    DangerLevel,
    ServiceAction,
)

# Registry models
from .registry import (  # noqa: F401
    AuditConfig,
    AuditLogLevel,
    CommandCategory,
    CommandDefinitionResponse,
    CommandDefinitionSummary,
    CommandDeliveryMode,
    ExecutionConfig,
    RbacConfig,
    RegistryMetadata,
)

# Request models
from .requests import (  # noqa: F401
    REGISTRY_ID_PATTERN,
    CommandListParams,
    CreateCommandRequest,
    QueueFlushRequest,
    SubmitCommandResultRequest,
)

# Response models
from .responses import (  # noqa: F401
    CommandCancelledResponse,
    CommandPollResponse,
    CommandQueuedResponse,
    CommandResponse,
    CommandResultSubmittedResponse,
    CommandRetriedResponse,
    CommandSummary,
    DryRunResponse,
    PolledCommand,
    QueueFlushResponse,
    QueueStats,
    QueueViewResponse,
)

# Shared schemas
from .schemas import (  # noqa: F401
    ChainReference,
    CommandError,
    CommandResult,
    CommandTarget,
    RequestedBy,
)

# Workflow models
from .workflows import (  # noqa: F401
    CreateWorkflowRequest,
    ExecuteWorkflowRequest,
    StepFailurePolicy,
    UpdateWorkflowRequest,
    WorkflowExecutionResponse,
    WorkflowExecutionStatus,
    WorkflowExecutionSummary,
    WorkflowInput,
    WorkflowResponse,
    WorkflowStep,
    WorkflowStepExecution,
    WorkflowSummary,
)

__all__ = [
    # Enums
    "CommandExecutionMethod",
    "CommandSource",
    "CommandStatus",
    "CommandType",
    "DangerLevel",
    "ServiceAction",
    # Registry
    "AuditConfig",
    "AuditLogLevel",
    "CommandCategory",
    "CommandDefinitionResponse",
    "CommandDefinitionSummary",
    "CommandDeliveryMode",
    "ExecutionConfig",
    "RbacConfig",
    "RegistryMetadata",
    # Requests
    "REGISTRY_ID_PATTERN",
    "CommandListParams",
    "CreateCommandRequest",
    "QueueFlushRequest",
    "SubmitCommandResultRequest",
    # Responses
    "CommandCancelledResponse",
    "CommandPollResponse",
    "CommandQueuedResponse",
    "CommandResponse",
    "CommandResultSubmittedResponse",
    "CommandRetriedResponse",
    "CommandSummary",
    "DryRunResponse",
    "PolledCommand",
    "QueueFlushResponse",
    "QueueStats",
    "QueueViewResponse",
    # Schemas
    "ChainReference",
    "CommandError",
    "CommandResult",
    "CommandTarget",
    "RequestedBy",
    # Workflows
    "CreateWorkflowRequest",
    "ExecuteWorkflowRequest",
    "StepFailurePolicy",
    "UpdateWorkflowRequest",
    "WorkflowExecutionResponse",
    "WorkflowExecutionStatus",
    "WorkflowExecutionSummary",
    "WorkflowInput",
    "WorkflowResponse",
    "WorkflowStep",
    "WorkflowStepExecution",
    "WorkflowSummary",
]
