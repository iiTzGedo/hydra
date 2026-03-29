"""Command registry/catalog models."""

from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class CommandCategory(str, Enum):
    """Command categories matching registry ID prefixes."""

    SERVICE = "service"
    NODE = "node"
    AGENT = "agent"


class AuditLogLevel(str, Enum):
    """Audit log verbosity levels."""

    MINIMAL = "minimal"
    STANDARD = "standard"
    VERBOSE = "verbose"


class CommandDeliveryMode(str, Enum):
    """How a command should be dispatched to an agent."""

    DIRECT_OR_POLL = "direct_or_poll"
    POLL_ONLY = "poll_only"


class ExecutionConfig(BaseModel):
    """Execution configuration for a command definition."""

    runtimes: dict[str, str] = Field(
        default_factory=dict,
        description="Command templates per runtime (systemd, docker, etc.)",
    )
    handler: str | None = Field(
        default=None,
        description="For agent/node commands: internal handler name",
    )
    timeout: int = Field(
        default=60,
        ge=1,
        le=3600,
        description="Timeout in seconds",
    )
    delivery_mode: Annotated[
        CommandDeliveryMode,
        Field(default=CommandDeliveryMode.POLL_ONLY, alias="deliveryMode"),
    ]
    retryable: bool = Field(default=False)
    max_retries: Annotated[int, Field(default=0, alias="maxRetries")]

    model_config = ConfigDict(populate_by_name=True)


class RbacConfig(BaseModel):
    """RBAC configuration for a command definition."""

    minimum_role: Annotated[str, Field(alias="minimumRole")]
    requires_confirmation: Annotated[bool, Field(default=False, alias="requiresConfirmation")]
    confirmation_message: Annotated[
        str | None,
        Field(default=None, alias="confirmationMessage"),
    ]

    model_config = ConfigDict(populate_by_name=True)


class AuditConfig(BaseModel):
    """Audit configuration for a command definition."""

    log_level: Annotated[
        AuditLogLevel,
        Field(default=AuditLogLevel.STANDARD, alias="logLevel"),
    ]
    capture_output: Annotated[bool, Field(default=True, alias="captureOutput")]
    sensitive_parameters: Annotated[
        list[str],
        Field(default_factory=list, alias="sensitiveParameters"),
    ]

    model_config = ConfigDict(populate_by_name=True)


class RegistryMetadata(BaseModel):
    """Metadata for a command definition."""

    version: str = Field(default="0.5.0")
    added_at: Annotated[datetime, Field(alias="addedAt")]
    built_in: Annotated[bool, Field(default=True, alias="builtIn")]
    deprecated: bool = Field(default=False)
    deprecation_message: Annotated[
        str | None,
        Field(default=None, alias="deprecationMessage"),
    ]

    model_config = ConfigDict(populate_by_name=True)


class CommandDefinitionResponse(BaseModel):
    """Full command definition response."""

    registry_id: Annotated[str, Field(alias="registryId")]
    category: CommandCategory
    action: str
    display_name: Annotated[str, Field(alias="displayName")]
    description: str | None = None
    target_schema: Annotated[dict | None, Field(default=None, alias="targetSchema")]
    parameters_schema: Annotated[dict | None, Field(default=None, alias="parametersSchema")]
    execution: ExecutionConfig
    rbac: RbacConfig
    audit: AuditConfig
    metadata: RegistryMetadata

    model_config = ConfigDict(populate_by_name=True)


class CommandDefinitionSummary(BaseModel):
    """Summary view of a command definition for catalog listing."""

    registry_id: Annotated[str, Field(alias="registryId")]
    category: CommandCategory
    action: str
    display_name: Annotated[str, Field(alias="displayName")]
    description: str | None = None
    minimum_role: Annotated[str, Field(alias="minimumRole")]
    requires_confirmation: Annotated[bool, Field(alias="requiresConfirmation")]
    timeout: int
    delivery_mode: Annotated[
        CommandDeliveryMode,
        Field(default=CommandDeliveryMode.POLL_ONLY, alias="deliveryMode"),
    ]
    built_in: Annotated[bool, Field(alias="builtIn")]
    deprecated: bool = False

    model_config = ConfigDict(populate_by_name=True)
