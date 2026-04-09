"""Installation models for remote agent installation (SSH and Proxmox)."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class InstallationStatus(StrEnum):
    """Status of an agent installation."""

    PENDING = "pending"
    CONNECTING = "connecting"
    TRANSFERRING = "transferring"
    CONFIGURING = "configuring"
    REGISTERING = "registering"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ── Embedded Models ─────────────────────────────────────────────────


class SSHCredentials(BaseModel):
    """SSH connection credentials."""

    model_config = ConfigDict(populate_by_name=True)

    host: str = Field(description="SSH host address")
    port: int = Field(default=22, description="SSH port")
    username: str = Field(description="SSH username")
    password: str | None = Field(default=None, description="SSH password")
    private_key: str | None = Field(
        default=None,
        alias="privateKey",
        description="SSH private key (PEM format)",
    )
    passphrase: str | None = Field(
        default=None,
        description="Passphrase for the private key",
    )

    @model_validator(mode="after")
    def require_auth_method(self) -> "SSHCredentials":
        """Require at least password or private_key."""
        if not self.password and not self.private_key:
            raise ValueError("Either password or privateKey must be provided")
        return self


class InstallationProgress(BaseModel):
    """Current progress of an installation."""

    model_config = ConfigDict(populate_by_name=True)

    phase: InstallationStatus = Field(
        default=InstallationStatus.PENDING,
        description="Current installation phase",
    )
    percent_complete: int = Field(
        default=0,
        ge=0,
        le=100,
        alias="percentComplete",
        description="Overall percent complete",
    )
    message: str = Field(default="", description="Human-readable progress message")
    started_at: datetime | None = Field(
        default=None,
        alias="startedAt",
        description="When this phase started",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        alias="updatedAt",
        description="Last progress update time",
    )


# ── Response Models ─────────────────────────────────────────────────


class InstallationResponse(BaseModel):
    """Full installation response."""

    model_config = ConfigDict(populate_by_name=True)

    installation_id: str = Field(alias="installationId")
    discovery_id: str | None = Field(default=None, alias="discoveryId")
    target_ip: str = Field(alias="targetIp")
    target_hostname: str | None = Field(default=None, alias="targetHostname")
    status: InstallationStatus
    progress: InstallationProgress
    node_id: str | None = Field(default=None, alias="nodeId")
    error: str | None = None
    agent_tier: str = Field(default="normal", alias="agentTier")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    completed_at: datetime | None = Field(default=None, alias="completedAt")


class InstallationSummary(BaseModel):
    """Abbreviated installation response for list endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    installation_id: str = Field(alias="installationId")
    target_ip: str = Field(alias="targetIp")
    target_hostname: str | None = Field(default=None, alias="targetHostname")
    status: InstallationStatus
    phase: InstallationStatus
    node_id: str | None = Field(default=None, alias="nodeId")
    created_at: datetime = Field(alias="createdAt")


# ── Request Models ──────────────────────────────────────────────────


class StartInstallationRequest(BaseModel):
    """Start a remote agent installation."""

    model_config = ConfigDict(populate_by_name=True)

    discovery_id: str | None = Field(
        default=None,
        alias="discoveryId",
        description="Discovery device ID to install on",
    )
    target_ip: str | None = Field(
        default=None,
        alias="targetIp",
        description="Target IP address (if no discovery_id)",
    )
    credentials: SSHCredentials = Field(description="SSH connection credentials")
    agent_tier: str = Field(
        default="normal",
        alias="agentTier",
        description="Agent tier to install (lite/normal/max)",
    )
    tags: list[str] = Field(default_factory=list, description="Tags for the node")

    @model_validator(mode="after")
    def require_target(self) -> "StartInstallationRequest":
        """Require either discovery_id or target_ip."""
        if not self.discovery_id and not self.target_ip:
            raise ValueError("Either discoveryId or targetIp must be provided")
        return self


# ── List Query Parameters ───────────────────────────────────────────


class ProxmoxInstallRequest(BaseModel):
    """Start a Proxmox-based remote agent installation.

    Installs the Hydra agent inside a Proxmox VM or LXC container using
    the PVE API rather than direct SSH.
    """

    model_config = ConfigDict(populate_by_name=True)

    plugin_id: str = Field(
        default="plg::proxmox",
        alias="pluginId",
        description="ID of the configured Proxmox plugin",
    )
    vmid: int = Field(
        gt=0,
        description="Proxmox VM/LXC container ID",
    )
    proxmox_node: str = Field(
        alias="proxmoxNode",
        min_length=1,
        max_length=128,
        description="PVE node name hosting the VM/CT",
    )
    vm_type: Literal["qemu", "lxc"] = Field(
        default="qemu",
        alias="vmType",
        description="VM type: qemu (with guest agent) or lxc",
    )
    agent_tier: str = Field(
        default="normal",
        alias="agentTier",
        description="Agent tier to install (lite/normal/max)",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Tags for the installed node",
    )
    discovery_id: str | None = Field(
        default=None,
        alias="discoveryId",
        description="Optional link to a discovered device",
    )

    @field_validator("plugin_id")
    @classmethod
    def validate_plugin_id(cls, v: str) -> str:
        """Validate plugin ID matches the plg:: pattern."""
        import re

        if not re.match(r"^plg::[a-z0-9]+(?:-[a-z0-9]+)*$", v):
            raise ValueError(
                f"Plugin ID '{v}' does not match required pattern: plg::<lowercase-alphanumeric-hyphens>"
            )
        return v


class InstallationListParams(BaseModel):
    """Query parameters for listing installations."""

    model_config = ConfigDict(populate_by_name=True)

    status: InstallationStatus | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    sort_by: Literal["createdAt", "updatedAt"] = Field(
        default="createdAt",
        alias="sortBy",
    )
    sort_order: Literal["asc", "desc"] = Field(
        default="desc",
        alias="sortOrder",
    )
