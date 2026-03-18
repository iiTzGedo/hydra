"""Node models for request/response validation."""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from hydra.api.v1.core.validators import (
    NETWORK_ID_PATTERN,
    TAG_PATTERN,
    validate_network_id,
    validate_tag,
)


class NodeClass(str, Enum):
    """Node class types."""

    COMPUTE = "compute"
    NETWORKING = "networking"
    IOT = "iot"


class NodeType(str, Enum):
    """Node type (physical or logical)."""

    PHYSICAL = "physical"
    LOGICAL = "logical"


class NodeKind(str, Enum):
    """Node kind (specific hardware/software type)."""

    # Compute
    BARE_METAL = "bare-metal"
    VM = "vm"
    LXC = "lxc"
    DOCKER = "docker"
    KUBERNETES_POD = "kubernetes-pod"
    # Networking
    ROUTER = "router"
    SWITCH = "switch"
    ACCESS_POINT = "access-point"
    FIREWALL = "firewall"
    LOAD_BALANCER = "load-balancer"
    # IoT
    SENSOR = "sensor"
    ACTUATOR = "actuator"
    CONTROLLER = "controller"
    HUB = "hub"
    BRIDGE = "bridge"
    APPLIANCE = "appliance"
    # Generic
    OTHER = "other"


class NodeStatus(str, Enum):
    """Node status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"
    PENDING = "pending"


class AgentTier(str, Enum):
    """Agent tier classification."""

    LITE = "lite"
    NORMAL = "normal"
    MAX = "max"


class NodeResponse(BaseModel):
    """Full node response model."""

    model_config = ConfigDict(populate_by_name=True)

    node_id: str = Field(alias="nodeId")
    node_class: NodeClass = Field(alias="class")
    node_type: NodeType = Field(alias="type")
    kind: NodeKind | None = None
    display_name: str = Field(alias="displayName")
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    parent_node_id: str | None = Field(default=None, alias="parentNodeId")
    network_ids: list[str] = Field(default_factory=list, alias="networkIds")
    registered_by: str | None = Field(default=None, alias="registeredBy")
    registered_at: datetime = Field(alias="registeredAt")
    last_updated: datetime = Field(alias="lastUpdated")
    last_profile_at: datetime | None = Field(default=None, alias="lastProfileAt")
    last_seen_at: datetime | None = Field(default=None, alias="lastSeenAt")
    status: NodeStatus
    agent_tier: AgentTier | None = Field(default=None, alias="agentTier")
    server_address: str | None = Field(default=None, alias="serverAddress")
    server_port: int | None = Field(default=None, alias="serverPort")
    server_tls_enabled: bool | None = Field(default=None, alias="serverTlsEnabled")
    server_reachable: bool | None = Field(default=None, alias="serverReachable")
    failed_direct_attempts: int | None = Field(default=None, alias="failedDirectAttempts")
    last_direct_contact: datetime | None = Field(default=None, alias="lastDirectContact")
    last_poll_contact: datetime | None = Field(default=None, alias="lastPollContact")


class NodeSummary(BaseModel):
    """Abbreviated node response for lists."""

    model_config = ConfigDict(populate_by_name=True)

    node_id: str = Field(alias="nodeId")
    node_class: NodeClass = Field(alias="class")
    node_type: NodeType = Field(alias="type")
    kind: NodeKind | None = None
    display_name: str = Field(alias="displayName")
    tags: list[str] = Field(default_factory=list)
    registered_by: str | None = Field(default=None, alias="registeredBy")
    status: NodeStatus
    last_profile_at: datetime | None = Field(default=None, alias="lastProfileAt")
    last_seen_at: datetime | None = Field(default=None, alias="lastSeenAt")
    agent_tier: AgentTier | None = Field(default=None, alias="agentTier")


class AgentInfo(BaseModel):
    """Agent information for a registered node."""

    node_id: str = Field(alias="nodeId")
    node_class: NodeClass = Field(alias="class")
    node_type: NodeType = Field(alias="type")
    kind: NodeKind | None = None
    display_name: str = Field(alias="displayName")
    tags: list[str] = Field(default_factory=list)
    registered_by: str | None = Field(default=None, alias="registeredBy")
    registered_at: datetime = Field(alias="registeredAt")
    status: NodeStatus
    last_profile_at: datetime | None = Field(default=None, alias="lastProfileAt")
    last_seen_at: datetime | None = Field(default=None, alias="lastSeenAt")
    profile_count: int = Field(default=0, alias="profileCount")
    last_profile_version: str | None = Field(default=None, alias="lastProfileVersion")
    is_healthy: bool = Field(alias="isHealthy", description="True if seen within last 24 hours")
    agent_tier: AgentTier | None = Field(default=None, alias="agentTier")

    model_config = {"populate_by_name": True}


class AgentListResponse(BaseModel):
    """List of registered agents response."""

    agents: list[AgentInfo]
    total: int
    active: int = Field(description="Number of agents with recent profiles")
    limit: int
    offset: int

    model_config = {"populate_by_name": True}


class UpdateNodeRequest(BaseModel):
    """Update node metadata."""

    display_name: str | None = Field(default=None, alias="displayName", max_length=128)
    description: str | None = Field(default=None, max_length=1024)
    kind: NodeKind | None = None
    tags: list[str] | None = None
    parent_node_id: str | None = Field(default=None, alias="parentNodeId")
    status: NodeStatus | None = None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str] | None) -> list[str] | None:
        """Validate tags match the required pattern."""
        if v is not None:
            for tag in v:
                if not validate_tag(tag):
                    raise ValueError(
                        f"Invalid tag '{tag}'. Tags must match pattern: {TAG_PATTERN} "
                        f"and be max 64 characters."
                    )
        return v


class NodeListParams(BaseModel):
    """Query parameters for listing nodes."""

    node_class: NodeClass | None = Field(default=None, alias="class")
    node_type: NodeType | None = Field(default=None, alias="type")
    kind: NodeKind | None = None
    status: NodeStatus | None = None
    agent_tier: AgentTier | None = Field(default=None, alias="agentTier")
    tags: list[str] | None = None
    parent_node_id: str | None = Field(default=None, alias="parentNodeId")
    network_id: str | None = Field(default=None, alias="networkId")
    search: str | None = Field(default=None, max_length=256)
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    sort_by: Literal["nodeId", "displayName", "registeredAt", "lastProfileAt", "lastUpdated"] = (
        Field(default="lastUpdated", alias="sortBy")
    )
    sort_order: Literal["asc", "desc"] = Field(default="desc", alias="sortOrder")

    @field_validator("network_id")
    @classmethod
    def validate_network_id(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not validate_network_id(v):
            raise ValueError(f"Invalid network ID format. Must match pattern: {NETWORK_ID_PATTERN}")
        return v
