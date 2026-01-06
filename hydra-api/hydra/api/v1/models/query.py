"""Query and analytics models."""

from datetime import datetime
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, Field


class QueryCollection(str, Enum):
    """Collections that can be queried."""

    NODES = "nodes"
    PROFILES = "profiles"
    SERVICES = "services"
    GROUPS = "groups"
    NETWORKS = "networks"


class CapacityGroupBy(str, Enum):
    """Grouping options for capacity summary."""

    NODE = "node"
    CLASS = "class"
    LOCATION = "location"
    NETWORK = "network"
    GROUP = "group"


class AuditAction(str, Enum):
    """Types of audited actions."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    REGISTER = "register"
    EXECUTE = "execute"


# ==================== Query Request/Response Models ====================


class QueryRequest(BaseModel):
    """Request for structured query across collections."""

    collection: QueryCollection = Field(description="Collection to query")
    filter: dict[str, Any] | None = Field(default=None, description="MongoDB-style filter")
    projection: dict[str, int] | None = Field(
        default=None, description="Fields to include (1) or exclude (0)"
    )
    sort: dict[str, int] | None = Field(default=None, description="Sort specification")
    limit: int = Field(default=50, ge=1, le=200, description="Max results")
    skip: int = Field(default=0, ge=0, description="Skip N results")


class QueryResponse(BaseModel):
    """Response from structured query."""

    collection: QueryCollection
    results: list[dict[str, Any]]
    total: int
    returned: int


# ==================== Capacity Models ====================


class CapacitySummary(BaseModel):
    """Overall infrastructure capacity summary."""

    total_nodes: Annotated[int, Field(alias="totalNodes")]
    physical_nodes: Annotated[int, Field(alias="physicalNodes")]
    logical_nodes: Annotated[int, Field(alias="logicalNodes")]
    total_cores: Annotated[int, Field(alias="totalCores")]
    total_memory_gb: Annotated[float, Field(alias="totalMemoryGB")]
    total_storage_tb: Annotated[float, Field(alias="totalStorageTB")]

    model_config = {"populate_by_name": True}


class ClassCapacity(BaseModel):
    """Capacity breakdown by node class."""

    nodes: int
    cores: int | None = None
    memory_gb: Annotated[float | None, Field(default=None, alias="memoryGB")]
    storage_tb: Annotated[float | None, Field(default=None, alias="storageTB")]

    model_config = {"populate_by_name": True}


class LocationCapacity(BaseModel):
    """Capacity breakdown by location."""

    nodes: int
    cores: int | None = None
    memory_gb: Annotated[float | None, Field(default=None, alias="memoryGB")]

    model_config = {"populate_by_name": True}


class CapacityResponse(BaseModel):
    """Full capacity response."""

    summary: CapacitySummary
    by_class: Annotated[dict[str, ClassCapacity] | None, Field(default=None, alias="byClass")]
    by_location: Annotated[dict[str, LocationCapacity] | None, Field(default=None, alias="byLocation")]

    model_config = {"populate_by_name": True}


# ==================== Audit Models ====================


class AuditResource(BaseModel):
    """Resource affected by an audit action."""

    type: str
    id: str


class AuditActor(BaseModel):
    """Actor who performed the action."""

    type: str  # "user", "agent", "system"
    id: str
    ip: str | None = None


class AuditResult(BaseModel):
    """Result of the audited action."""

    success: bool
    error: str | None = None


class AuditEntry(BaseModel):
    """Audit log entry."""

    entry_id: Annotated[str, Field(alias="entryId")]
    timestamp: datetime
    action: AuditAction
    resource: AuditResource
    actor: AuditActor
    details: dict[str, Any] | None = None
    result: AuditResult

    model_config = {"populate_by_name": True}


class AuditListParams(BaseModel):
    """Parameters for listing audit entries."""

    action: AuditAction | None = None
    resource_type: str | None = Field(default=None, alias="resourceType")
    resource_id: str | None = Field(default=None, alias="resourceId")
    actor_id: str | None = Field(default=None, alias="actorId")
    since: datetime | None = None
    until: datetime | None = None
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)

    model_config = {"populate_by_name": True}
