"""Command request models."""

import re
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, Field, field_validator

from .enums import CommandStatus, CommandType
from .schemas import CommandTarget

REGISTRY_ID_PATTERN = r"^reg::(service|node|agent)::[a-z][a-z0-9-]*$"


class CreateCommandRequest(BaseModel):
    """Request to create/queue a new command."""

    registry_id: Annotated[
        str,
        Field(
            alias="registryId",
            description="Registry ID of the command to execute (e.g. reg::service::restart)",
        ),
    ]
    target: CommandTarget = Field(description="Target node/service")
    parameters: dict[str, Any] | None = Field(default=None, description="Action parameters")
    timeout_seconds: Annotated[
        int | None,
        Field(
            default=None,
            ge=1,
            le=3600,
            alias="timeoutSeconds",
            description="Command timeout in seconds (overrides registry default)",
        ),
    ]

    model_config = {"populate_by_name": True}

    @field_validator("registry_id")
    @classmethod
    def validate_registry_id(cls, v: str) -> str:
        if not re.match(REGISTRY_ID_PATTERN, v):
            raise ValueError(
                f"Invalid registryId format. Must match pattern: {REGISTRY_ID_PATTERN}"
            )
        return v


class SubmitCommandResultRequest(BaseModel):
    """Request from agent to submit command execution result."""

    success: bool = Field(description="Whether command succeeded")
    output: str | None = Field(default=None, description="Command output")
    exit_code: Annotated[int | None, Field(default=None, alias="exitCode")]
    error: str | None = Field(default=None, description="Error message if failed")
    data: dict[str, Any] | None = Field(default=None, description="Structured result data")

    model_config = {"populate_by_name": True}


class CommandListParams(BaseModel):
    """Parameters for listing commands."""

    node_id: str | None = Field(default=None, alias="nodeId")
    service_id: str | None = Field(default=None, alias="serviceId")
    registry_id: str | None = Field(default=None, alias="registryId")
    type: CommandType | None = None
    status: CommandStatus | None = None
    since: datetime | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)

    model_config = {"populate_by_name": True}


class QueueFlushRequest(BaseModel):
    """Request to flush the command queue."""

    scope: str = Field(
        description="Flush scope: 'all', 'node:<nodeId>', or 'user:<userId>'"
    )
    confirm: bool = Field(
        default=False,
        description="Must be true to confirm the flush operation",
    )

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, v: str) -> str:
        if v == "all":
            return v
        if v.startswith("node:") and len(v) > 5:
            return v
        if v.startswith("user:") and len(v) > 5:
            return v
        raise ValueError("Scope must be 'all', 'node:<nodeId>', or 'user:<userId>'")
