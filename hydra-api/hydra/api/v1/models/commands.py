"""Command models for command execution queue and history."""

from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from hydra.api.v1.core.validators import (
    NODE_ID_PATTERN_NEW,
    SERVICE_ID_PATTERN,
    validate_node_id_strict,
    validate_service_id,
)


class CommandType(str, Enum):
    """Types of commands that can be executed."""

    METADATA = "metadata"
    SERVICE = "service"
    PACKAGE = "package"
    CONFIG = "config"
    SYSTEM = "system"
    CUSTOM = "custom"


class CommandStatus(str, Enum):
    """Status of a command in the execution pipeline."""

    PENDING = "pending"
    QUEUED = "queued"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class CommandSource(str, Enum):
    """Source of the command request."""

    WEB = "web"
    API = "api"
    MCP = "mcp"
    AUTOMATION = "automation"


class CommandExecutionMethod(str, Enum):
    """How a command was or will be executed."""

    DIRECT = "direct"
    POLL = "poll"


class ServiceAction(str, Enum):
    """Actions that can be performed on services."""

    START = "start"
    STOP = "stop"
    RESTART = "restart"
    RELOAD = "reload"


class CommandTarget(BaseModel):
    """Target for a command."""

    node_id: Annotated[str, Field(alias="nodeId", description="Target node ID")]
    service_id: Annotated[
        str | None,
        Field(default=None, alias="serviceId", description="Target service ID (for service commands)"),
    ]

    model_config = {"populate_by_name": True}

    @field_validator("node_id")
    @classmethod
    def validate_node_id(cls, v: str) -> str:
        if not validate_node_id_strict(v):
            raise ValueError(f"Invalid node ID format. Must match pattern: {NODE_ID_PATTERN_NEW}")
        return v

    @field_validator("service_id")
    @classmethod
    def validate_service_id(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not validate_service_id(v):
            raise ValueError(f"Invalid service ID format. Must match pattern: {SERVICE_ID_PATTERN}")
        return v


class CommandResult(BaseModel):
    """Result of command execution."""

    success: bool = Field(description="Whether the command succeeded")
    output: str | None = Field(default=None, description="Command output")
    exit_code: Annotated[int | None, Field(default=None, alias="exitCode", description="Exit code")]
    error: str | None = Field(default=None, description="Error message if failed")

    model_config = {"populate_by_name": True}


class RequestedBy(BaseModel):
    """Information about who requested the command."""

    user_id: Annotated[str | None, Field(default=None, alias="userId")]
    source: CommandSource = Field(default=CommandSource.API)

    model_config = {"populate_by_name": True}


class CreateCommandRequest(BaseModel):
    """Request to create/queue a new command."""

    type: CommandType = Field(description="Type of command")
    target: CommandTarget = Field(description="Target node/service")
    action: str = Field(description="Action to execute")
    parameters: dict | None = Field(default=None, description="Action parameters")
    timeout_seconds: Annotated[
        int,
        Field(
            default=60,
            ge=1,
            le=3600,
            alias="timeoutSeconds",
            description="Command timeout in seconds",
        ),
    ]

    model_config = {"populate_by_name": True}


class SubmitCommandResultRequest(BaseModel):
    """Request from agent to submit command execution result."""

    success: bool = Field(description="Whether command succeeded")
    output: str | None = Field(default=None, description="Command output")
    exit_code: Annotated[int | None, Field(default=None, alias="exitCode")]
    error: str | None = Field(default=None, description="Error message if failed")

    model_config = {"populate_by_name": True}


class CommandSummary(BaseModel):
    """Summary view of a command."""

    command_id: Annotated[str, Field(alias="commandId")]
    type: CommandType
    target: CommandTarget
    action: str
    status: CommandStatus
    created_at: Annotated[datetime, Field(alias="createdAt")]

    model_config = {"populate_by_name": True}


class CommandResponse(BaseModel):
    """Full command response."""

    command_id: Annotated[str, Field(alias="commandId")]
    type: CommandType
    target: CommandTarget
    action: str
    parameters: dict | None = None
    status: CommandStatus
    result: CommandResult | None = None
    requested_by: Annotated[RequestedBy | None, Field(default=None, alias="requestedBy")]
    timeout_seconds: Annotated[int, Field(alias="timeoutSeconds")]
    created_at: Annotated[datetime, Field(alias="createdAt")]
    queued_at: Annotated[datetime | None, Field(default=None, alias="queuedAt")]
    started_at: Annotated[datetime | None, Field(default=None, alias="startedAt")]
    completed_at: Annotated[datetime | None, Field(default=None, alias="completedAt")]

    model_config = {"populate_by_name": True}


class CommandQueuedResponse(BaseModel):
    """Response when a command is queued or executed directly."""

    command_id: Annotated[str, Field(alias="commandId")]
    type: CommandType
    target: CommandTarget
    action: str
    status: CommandStatus = CommandStatus.QUEUED
    execution_method: Annotated[
        CommandExecutionMethod,
        Field(default=CommandExecutionMethod.POLL, alias="executionMethod"),
    ]
    result: CommandResult | None = None
    queued_at: Annotated[datetime | None, Field(default=None, alias="queuedAt")]
    completed_at: Annotated[datetime | None, Field(default=None, alias="completedAt")]

    model_config = {"populate_by_name": True}


class CommandCancelledResponse(BaseModel):
    """Response when a command is cancelled."""

    command_id: Annotated[str, Field(alias="commandId")]
    status: CommandStatus = CommandStatus.CANCELLED
    cancelled_at: Annotated[datetime, Field(alias="cancelledAt")]

    model_config = {"populate_by_name": True}


class PolledCommand(BaseModel):
    """Typed command payload returned to polling agents."""

    command_id: Annotated[str, Field(alias="commandId")]
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


class CommandListParams(BaseModel):
    """Parameters for listing commands."""

    node_id: str | None = Field(default=None, alias="nodeId")
    type: CommandType | None = None
    status: CommandStatus | None = None
    since: datetime | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)

    model_config = {"populate_by_name": True}
