"""Node models for request/response validation."""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


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


# Response Models
class NodeResponse(BaseModel):
    """Full node response model."""

    node_id: str = Field(alias="nodeId")
    node_class: NodeClass = Field(alias="class")
    node_type: NodeType = Field(alias="type")
    kind: NodeKind | None = None
    display_name: str = Field(alias="displayName")
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    parent_node_id: str | None = Field(default=None, alias="parentNodeId")
    network_ids: list[str] = Field(default_factory=list, alias="networkIds")
    registered_at: datetime = Field(alias="registeredAt")
    last_updated: datetime = Field(alias="lastUpdated")
    last_profile_at: datetime | None = Field(default=None, alias="lastProfileAt")
    status: NodeStatus


class NodeSummary(BaseModel):
    """Abbreviated node response for lists."""

    node_id: str = Field(alias="nodeId")
    node_class: NodeClass = Field(alias="class")
    node_type: NodeType = Field(alias="type")
    kind: NodeKind | None = None
    display_name: str = Field(alias="displayName")
    tags: list[str] = Field(default_factory=list)
    status: NodeStatus
    last_profile_at: datetime | None = Field(default=None, alias="lastProfileAt")


# Request Models
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
        if v is not None:
            for tag in v:
                if not tag or len(tag) > 64:
                    raise ValueError(f"Invalid tag: {tag}")
        return v


# Query Parameters
class NodeListParams(BaseModel):
    """Query parameters for listing nodes."""

    # Filters
    node_class: NodeClass | None = Field(default=None, alias="class")
    node_type: NodeType | None = Field(default=None, alias="type")
    kind: NodeKind | None = None
    status: NodeStatus | None = None
    tags: list[str] | None = None
    parent_node_id: str | None = Field(default=None, alias="parentNodeId")
    network_id: str | None = Field(default=None, alias="networkId")

    # Search
    search: str | None = Field(default=None, max_length=256)

    # Pagination
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)

    # Sorting
    sort_by: Literal["nodeId", "displayName", "registeredAt", "lastProfileAt", "lastUpdated"] = (
        Field(default="lastUpdated", alias="sortBy")
    )
    sort_order: Literal["asc", "desc"] = Field(default="desc", alias="sortOrder")
