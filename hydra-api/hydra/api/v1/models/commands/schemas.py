"""Shared embedded schemas for command models."""

from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from hydra.api.v1.core.validators import (
    NODE_ID_PATTERN_NEW,
    SERVICE_ID_PATTERN,
    validate_node_id_strict,
    validate_service_id,
)
from .enums import CommandSource


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
    data: dict | None = Field(default=None, description="Structured result data")

    model_config = {"populate_by_name": True}


class CommandError(BaseModel):
    """Structured error for rejected or failed commands."""

    code: str = Field(description="Error code")
    message: str = Field(description="Human-readable error message")
    details: dict | None = Field(default=None, description="Additional error details")

    model_config = {"populate_by_name": True}


class RequestedBy(BaseModel):
    """Information about who requested the command."""

    user_id: Annotated[str | None, Field(default=None, alias="userId")]
    source: CommandSource = Field(default=CommandSource.API)
    client_id: Annotated[str | None, Field(default=None, alias="clientId")]

    model_config = {"populate_by_name": True}


class ChainReference(BaseModel):
    """Reference to a command chain (workflow) this command belongs to."""

    chain_id: Annotated[str, Field(alias="chainId")]
    sequence: int = Field(description="Step sequence number in the chain")
    depends_on: list[str] = Field(default_factory=list, alias="dependsOn")

    model_config = {"populate_by_name": True}
