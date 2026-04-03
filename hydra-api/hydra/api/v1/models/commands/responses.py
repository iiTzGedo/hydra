"""Command response models."""

from datetime import datetime
from typing import Annotated

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
    parameters: dict | None = None
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
    parameters: dict | None = None
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
