"""Command response models."""

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, Field

from .enums import CommandExecutionMethod, CommandStatus, CommandType
from .schemas import ChainReference, CommandError, CommandResult, CommandTarget, RequestedBy


class CommandSummary(BaseModel):
    """Summary view of a command."""

    command_id: Annotated[str, Field(alias="commandId")]
    registry_id: Annotated[str | None, Field(default=None, alias="registryId")]
    type: CommandType
    target: CommandTarget
    action: str
    status: CommandStatus
    created_at: Annotated[datetime, Field(alias="createdAt")]

    model_config = {"populate_by_name": True}


class CommandResponse(BaseModel):
    """Full command response."""

    command_id: Annotated[str, Field(alias="commandId")]
    registry_id: Annotated[str | None, Field(default=None, alias="registryId")]
    type: CommandType
    target: CommandTarget
    action: str
    parameters: dict[str, Any] | None = None
    status: CommandStatus
    execution_method: Annotated[
        CommandExecutionMethod | None,
        Field(default=None, alias="executionMethod"),
    ]
    result: CommandResult | None = None
    error: CommandError | None = None
    requested_by: Annotated[RequestedBy | None, Field(default=None, alias="requestedBy")]
    timeout_seconds: Annotated[int, Field(alias="timeoutSeconds")]
    retry_count: Annotated[int, Field(default=0, alias="retryCount")]
    max_retries: Annotated[int, Field(default=0, alias="maxRetries")]
    retried_from: Annotated[str | None, Field(default=None, alias="retriedFrom")]
    queue_position: Annotated[int | None, Field(default=None, alias="queuePosition")]
    chain: ChainReference | None = None
    created_at: Annotated[datetime, Field(alias="createdAt")]
    queued_at: Annotated[datetime | None, Field(default=None, alias="queuedAt")]
    started_at: Annotated[datetime | None, Field(default=None, alias="startedAt")]
    completed_at: Annotated[datetime | None, Field(default=None, alias="completedAt")]
    cancelled_at: Annotated[datetime | None, Field(default=None, alias="cancelledAt")]
    cancelled_by: Annotated[str | None, Field(default=None, alias="cancelledBy")]
    # Confirmation fields
    danger_level: Annotated[str | None, Field(default=None, alias="dangerLevel")]
    confirmation_message: Annotated[str | None, Field(default=None, alias="confirmationMessage")]
    confirmation_expires_at: Annotated[datetime | None, Field(default=None, alias="confirmationExpiresAt")]

    model_config = {"populate_by_name": True}


class CommandQueuedResponse(BaseModel):
    """Response when a command is queued, executed directly, or pending confirmation."""

    command_id: Annotated[str, Field(alias="commandId")]
    registry_id: Annotated[str | None, Field(default=None, alias="registryId")]
    type: CommandType
    target: CommandTarget
    action: str
    status: CommandStatus = CommandStatus.QUEUED
    execution_method: Annotated[
        CommandExecutionMethod | None,
        Field(default=CommandExecutionMethod.AGENT_POLL, alias="executionMethod"),
    ]
    result: CommandResult | None = None
    queue_position: Annotated[int | None, Field(default=None, alias="queuePosition")]
    queued_at: Annotated[datetime | None, Field(default=None, alias="queuedAt")]
    completed_at: Annotated[datetime | None, Field(default=None, alias="completedAt")]
    # Confirmation fields (populated when status is pending_confirmation)
    requires_confirmation: Annotated[bool, Field(default=False, alias="requiresConfirmation")]
    confirmation_message: Annotated[str | None, Field(default=None, alias="confirmationMessage")]
    danger_level: Annotated[str | None, Field(default=None, alias="dangerLevel")]
    affected_nodes: Annotated[list[str], Field(default_factory=list, alias="affectedNodes")]
    confirmation_expires_at: Annotated[datetime | None, Field(default=None, alias="confirmationExpiresAt")]

    model_config = {"populate_by_name": True}


class CommandCancelledResponse(BaseModel):
    """Response when a command is cancelled."""

    command_id: Annotated[str, Field(alias="commandId")]
    status: CommandStatus = CommandStatus.CANCELLED
    cancelled_at: Annotated[datetime, Field(alias="cancelledAt")]
    cancelled_by: Annotated[str | None, Field(default=None, alias="cancelledBy")]

    model_config = {"populate_by_name": True}


class PolledCommand(BaseModel):
    """Typed command payload returned to polling agents."""

    command_id: Annotated[str, Field(alias="commandId")]
    registry_id: Annotated[str | None, Field(default=None, alias="registryId")]
    type: CommandType
    action: str
    target: CommandTarget
    parameters: dict[str, Any] | None = None
    timeout_seconds: Annotated[int, Field(alias="timeoutSeconds")]

    model_config = {"populate_by_name": True}


class CommandPollResponse(BaseModel):
    """Response for agent command polling."""

    commands: list[PolledCommand] = Field(
        default_factory=list,
        description="Pending commands for the node",
    )


class CommandResultSubmittedResponse(BaseModel):
    """Response when command result is submitted."""

    command_id: Annotated[str, Field(alias="commandId")]
    status: CommandStatus
    completed_at: Annotated[datetime, Field(alias="completedAt")]

    model_config = {"populate_by_name": True}


class CommandRetriedResponse(BaseModel):
    """Response when a command retry is created."""

    command_id: Annotated[str, Field(alias="commandId", description="New retry command ID")]
    original_command_id: Annotated[
        str, Field(alias="originalCommandId", description="Original command being retried")
    ]
    retry_count: Annotated[int, Field(alias="retryCount", description="Current retry count")]
    max_retries: Annotated[int, Field(alias="maxRetries", description="Maximum retries allowed")]
    status: CommandStatus = CommandStatus.QUEUED

    model_config = {"populate_by_name": True}


class DryRunResponse(BaseModel):
    """Response for a dry-run command preview."""

    model_config = {"populate_by_name": True}

    would_require_confirmation: Annotated[
        bool, Field(alias="wouldRequireConfirmation")
    ]
    estimated_delivery_mode: Annotated[
        str, Field(alias="estimatedDeliveryMode")
    ]
    target_node_tier: Annotated[
        str | None, Field(default=None, alias="targetNodeTier")
    ]
    permission_check_passed: Annotated[
        bool, Field(alias="permissionCheckPassed")
    ]
    rate_limit_ok: Annotated[bool, Field(alias="rateLimitOk")]
    cooldown_ok: Annotated[bool, Field(alias="cooldownOk")]
    danger_level: Annotated[str, Field(alias="dangerLevel")]
    registry_id: Annotated[str, Field(alias="registryId")]
    target_node_id: Annotated[str, Field(alias="targetNodeId")]


class QueueStats(BaseModel):
    """Queue statistics."""

    total_queued: Annotated[int, Field(alias="totalQueued")]
    total_executing: Annotated[int, Field(alias="totalExecuting")]
    oldest_queued_at: Annotated[datetime | None, Field(default=None, alias="oldestQueuedAt")]

    model_config = {"populate_by_name": True}


class QueueViewResponse(BaseModel):
    """Response for queue view endpoint."""

    queue: list[CommandSummary] = Field(default_factory=list)
    stats: QueueStats


class QueueFlushResponse(BaseModel):
    """Response for queue flush endpoint."""

    flushed_count: Annotated[int, Field(alias="flushedCount")]

    model_config = {"populate_by_name": True}
