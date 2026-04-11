"""Plugin system models for request/response validation."""

import re
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from hydra.api.v1.models.icons import IconDescriptor

# ── Enums ───────────────────────────────────────────────────────────


class PluginStatus(StrEnum):
    """Plugin lifecycle status."""

    INSTALLED = "installed"
    CONFIGURED = "configured"
    ENABLED = "enabled"
    ACTIVE = "active"
    DISABLED = "disabled"
    ERROR = "error"


class PluginClassification(StrEnum):
    """Plugin classification tier."""

    CORE = "core"
    DEFAULT = "default"
    COMMUNITY = "community"


class PluginCategory(StrEnum):
    """Plugin functional category."""

    INFRASTRUCTURE = "infrastructure"
    MONITORING = "monitoring"
    VERSION_CONTROL = "version_control"
    DATABASES = "databases"
    CLOUD = "cloud"
    DEVELOPMENT = "development"
    OTHER = "other"


class ExecutionPathType(StrEnum):
    """How plugin commands reach their target."""

    PLUGIN_VIA_API_DIRECT = "plugin_via_api_direct"
    PLUGIN_VIA_AGENT_DIRECT = "plugin_via_agent_direct"
    PLUGIN_VIA_AGENT_POLL = "plugin_via_agent_poll"
    NATIVE_FALLBACK = "native_fallback"


# ── Embedded Models ─────────────────────────────────────────────────


PLUGIN_ID_PATTERN = re.compile(r"^plg::[a-z0-9]+(?:-[a-z0-9]+)*$")


class PluginTouchpoints(BaseModel):
    """Capabilities a plugin can contribute to the platform."""

    model_config = ConfigDict(populate_by_name=True)

    profile_enrichment: bool = Field(
        default=False,
        alias="profileEnrichment",
        description="Plugin enriches collected profiles",
    )
    discovery_provider: bool = Field(
        default=False,
        alias="discoveryProvider",
        description="Plugin provides network/service discovery",
    )
    command_provider: bool = Field(
        default=False,
        alias="commandProvider",
        description="Plugin contributes executable commands",
    )
    execution_handler: bool = Field(
        default=False,
        alias="executionHandler",
        description="Plugin handles command execution",
    )
    topology_provider: bool = Field(
        default=False,
        alias="topologyProvider",
        description="Plugin contributes topology data",
    )
    workflow_block_provider: bool = Field(
        default=False,
        alias="workflowBlockProvider",
        description="Plugin provides workflow building blocks",
    )


class PluginHealthStatus(BaseModel):
    """Plugin health check state."""

    model_config = ConfigDict(populate_by_name=True)

    status: str = Field(default="unknown", description="Current health status")
    last_check: datetime | None = Field(
        default=None,
        alias="lastCheck",
        description="Timestamp of last health check",
    )
    consecutive_failures: int = Field(
        default=0,
        alias="consecutiveFailures",
        description="Number of consecutive health check failures",
    )
    last_error: str | None = Field(
        default=None,
        alias="lastError",
        description="Error message from last failed check",
    )
    response_time_ms: float | None = Field(
        default=None,
        alias="responseTimeMs",
        description="Response time of last health check in milliseconds",
    )


class NodeBinding(BaseModel):
    """Binding between a plugin and a specific node."""

    model_config = ConfigDict(populate_by_name=True)

    node_id: str = Field(alias="nodeId", description="Bound node identifier")
    enabled: bool = Field(default=True, description="Whether this binding is active")
    allowed_commands: list[str] = Field(
        default_factory=list,
        alias="allowedCommands",
        description="Commands this plugin may execute on the node",
    )
    bound_at: datetime = Field(alias="boundAt", description="When the binding was created")


class PluginManifest(BaseModel):
    """Declarative plugin manifest describing identity and capabilities."""

    model_config = ConfigDict(populate_by_name=True)

    plugin_id: str = Field(
        alias="pluginId",
        description="Unique plugin identifier (e.g. plg::docker)",
    )
    name: str = Field(min_length=1, max_length=128, description="Human-readable plugin name")
    version: str = Field(min_length=1, max_length=32, description="Semantic version string")
    description: str = Field(default="", max_length=1024, description="Plugin description")
    author: str = Field(default="", max_length=128, description="Plugin author or maintainer")
    classification: PluginClassification = Field(
        default=PluginClassification.COMMUNITY,
        description="Plugin classification tier",
    )
    category: PluginCategory = Field(
        default=PluginCategory.OTHER,
        description="Functional category",
    )
    touchpoints: PluginTouchpoints = Field(
        default_factory=PluginTouchpoints,
        description="Capabilities this plugin contributes",
    )
    supported_tiers: list[str] = Field(
        default_factory=lambda: ["normal", "max"],
        alias="supportedTiers",
        description="Agent tiers this plugin supports",
    )
    health_check_endpoint: str | None = Field(
        default=None,
        alias="healthCheckEndpoint",
        description="HTTP endpoint for health checks",
    )
    contributed_commands: list[str] = Field(
        default_factory=list,
        alias="contributedCommands",
        description="Registry IDs of commands this plugin provides",
    )

    @field_validator("plugin_id")
    @classmethod
    def validate_plugin_id(cls, v: str) -> str:
        """Validate plugin ID matches required pattern."""
        if not PLUGIN_ID_PATTERN.match(v):
            raise ValueError(
                f"Plugin ID '{v}' does not match required pattern: plg::<lowercase-alphanumeric-hyphens>"
            )
        return v


# ── Response Models ─────────────────────────────────────────────────


class PluginResponse(BaseModel):
    """Full plugin response (credentials are never exposed)."""

    model_config = ConfigDict(populate_by_name=True)

    plugin_id: str = Field(alias="pluginId")
    manifest: PluginManifest
    status: PluginStatus
    icon: IconDescriptor | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    node_bindings: list[NodeBinding] = Field(default_factory=list, alias="nodeBindings")
    health: PluginHealthStatus = Field(default_factory=PluginHealthStatus)
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class PluginSummary(BaseModel):
    """Abbreviated plugin response for list endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    plugin_id: str = Field(alias="pluginId")
    name: str
    status: PluginStatus
    icon: IconDescriptor | None = None
    classification: PluginClassification
    category: PluginCategory
    health_status: str = Field(alias="healthStatus")
    node_count: int = Field(alias="nodeCount")
    created_at: datetime = Field(alias="createdAt")


# ── Request Models ──────────────────────────────────────────────────


class RegisterPluginRequest(BaseModel):
    """Register a new plugin with the platform."""

    model_config = ConfigDict(populate_by_name=True)

    manifest: PluginManifest = Field(description="Plugin manifest")
    config: dict[str, Any] = Field(default_factory=dict, description="Plugin configuration")
    credentials: dict[str, str] | None = Field(
        default=None,
        description="Plugin credentials (encrypted at rest, never returned in responses)",
    )


class UpdatePluginConfigRequest(BaseModel):
    """Update plugin configuration and/or credentials."""

    model_config = ConfigDict(populate_by_name=True)

    config: dict[str, Any] | None = Field(
        default=None,
        description="Updated configuration (merged with existing)",
    )
    credentials: dict[str, str] | None = Field(
        default=None,
        description="Updated credentials (replaces existing)",
    )


class BindNodeRequest(BaseModel):
    """Bind a node to a plugin."""

    model_config = ConfigDict(populate_by_name=True)

    allowed_commands: list[str] = Field(
        default_factory=list,
        alias="allowedCommands",
        description="Commands this plugin may execute on the node",
    )


# ── List Query Parameters ──────────────────────────────────────────


class PluginListParams(BaseModel):
    """Query parameters for listing plugins."""

    model_config = ConfigDict(populate_by_name=True)

    status: PluginStatus | None = None
    classification: PluginClassification | None = None
    category: PluginCategory | None = None
    search: str | None = Field(default=None, max_length=256)
    sort_by: Literal["createdAt", "name", "status"] = Field(
        default="createdAt",
        alias="sortBy",
    )
    sort_order: Literal["asc", "desc"] = Field(default="desc", alias="sortOrder")
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
