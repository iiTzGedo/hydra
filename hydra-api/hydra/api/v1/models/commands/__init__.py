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

# Shared schemas
from .schemas import (  # noqa: F401
    ChainReference,
    CommandError,
    CommandResult,
    CommandTarget,
    RequestedBy,
)

# Request models
from .requests import (  # noqa: F401
    CommandListParams,
    CreateCommandRequest,
    QueueFlushRequest,
    REGISTRY_ID_PATTERN,
    SubmitCommandResultRequest,
)

# Registry models
from .registry import (  # noqa: F401
    AuditConfig,
    AuditLogLevel,
    CommandCategory,
    CommandDeliveryMode,
    CommandDefinitionResponse,
    CommandDefinitionSummary,
    ExecutionConfig,
    RbacConfig,
    RegistryMetadata,
)

# Response models
from .responses import (  # noqa: F401
    CommandCancelledResponse,
    CommandPollResponse,
    CommandQueuedResponse,
    CommandResponse,
    CommandResultSubmittedResponse,
    CommandSummary,
    PolledCommand,
    QueueFlushResponse,
    QueueStats,
    QueueViewResponse,
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
