"""Service models for request/response validation."""

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from hydra.api.v1.core.validators import TAG_PATTERN, validate_tag


class ServiceRuntime(StrEnum):
    """Service runtime environment."""

    SYSTEMD = "systemd"
    DOCKER = "docker"
    PODMAN = "podman"
    KUBERNETES = "kubernetes"
    LXC = "lxc"
    SUPERVISORD = "supervisord"
    PM2 = "pm2"
    RC = "rc"
    OPENRC = "openrc"
    WINSERVICE = "winservice"
    LAUNCHD = "launchd"
    CONTAINERD = "containerd"
    UNKNOWN = "unknown"


class ServiceStatus(StrEnum):
    """Service status."""

    RUNNING = "running"
    STOPPED = "stopped"
    PAUSED = "paused"
    EXITED = "exited"
    FAILED = "failed"
    RESTARTING = "restarting"
    UNKNOWN = "unknown"


class HealthStatus(StrEnum):
    """Service health status."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class ServicePort(BaseModel):
    """Service port configuration."""

    model_config = ConfigDict(populate_by_name=True)

    port: int = Field(ge=1, le=65535)
    protocol: str = "tcp"
    host_port: int | None = Field(default=None, alias="hostPort", ge=1, le=65535)


class ServiceEndpoint(BaseModel):
    """Service endpoint configuration."""

    model_config = ConfigDict(populate_by_name=True)

    url: str
    type: str  # http, https, grpc, tcp, udp
    internal: bool = True


class ServiceExposure(BaseModel):
    """Service network exposure."""

    model_config = ConfigDict(populate_by_name=True)

    ports: list[ServicePort] = Field(default_factory=list)
    endpoints: list[ServiceEndpoint] = Field(default_factory=list)


class ServiceResources(BaseModel):
    """Service resource allocation."""

    model_config = ConfigDict(populate_by_name=True)

    cpu_cores: float | None = Field(default=None, alias="cpuCores")
    cpu_shares: int | None = Field(default=None, alias="cpuShares")
    memory_bytes: int | None = Field(default=None, alias="memoryBytes")
    memory_limit_bytes: int | None = Field(default=None, alias="memoryLimitBytes")


class ServiceOrigin(BaseModel):
    """Service discovery origin metadata."""

    model_config = ConfigDict(populate_by_name=True)

    native_id: str = Field(alias="nativeId")
    discovered_by: str = Field(alias="discoveredBy")
    collected_at: datetime = Field(alias="collectedAt")


class ServiceHealth(BaseModel):
    """Service health information."""

    model_config = ConfigDict(populate_by_name=True)

    status: HealthStatus
    last_check: datetime | None = Field(default=None, alias="lastCheck")


class ServiceResponse(BaseModel):
    """Full service response model."""

    model_config = ConfigDict(populate_by_name=True)

    service_id: str = Field(alias="serviceId")
    runtime: str
    name: str
    display_name: str = Field(alias="displayName")
    description: str | None = None
    status: str
    version: str | None = None
    image: str | None = None
    profile_id: str = Field(alias="profileId")
    node_id: str = Field(alias="nodeId")
    exposure: ServiceExposure | None = None
    resources: dict[str, Any] | None = None
    attachments: dict[str, Any] | None = None
    origin: ServiceOrigin
    health: ServiceHealth | None = None
    tags: list[str] = Field(default_factory=list)
    first_seen: datetime = Field(alias="firstSeen")
    last_seen: datetime = Field(alias="lastSeen")


class ServiceSummary(BaseModel):
    """Abbreviated service response for lists."""

    model_config = ConfigDict(populate_by_name=True)

    service_id: str = Field(alias="serviceId")
    name: str
    display_name: str = Field(alias="displayName")
    runtime: str
    status: str
    version: str | None = None
    node_id: str = Field(alias="nodeId")
    last_seen: datetime = Field(alias="lastSeen")


class UpdateServiceRequest(BaseModel):
    """Update service metadata."""

    model_config = ConfigDict(populate_by_name=True)

    display_name: str | None = Field(default=None, alias="displayName", max_length=128)
    description: str | None = Field(default=None, max_length=1024)
    tags: list[str] | None = None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            for tag in v:
                if not validate_tag(tag):
                    raise ValueError(f"Invalid tag '{tag}'. Tags must match pattern: {TAG_PATTERN}")
        return v


class ServiceListParams(BaseModel):
    """Query parameters for listing services."""

    model_config = ConfigDict(populate_by_name=True)

    node_id: str | None = Field(default=None, alias="nodeId")
    runtime: ServiceRuntime | None = None
    status: ServiceStatus | None = None
    name: str | None = None
    tags: list[str] | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    search: str | None = Field(default=None, max_length=256)
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    sort_by: Literal["serviceId", "name", "lastSeen", "status", "runtime"] = Field(
        default="lastSeen", alias="sortBy"
    )
    sort_order: Literal["asc", "desc"] = Field(default="desc", alias="sortOrder")

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        for tag in v:
            if not validate_tag(tag):
                raise ValueError(f"Invalid tag '{tag}'. Tags must match pattern: {TAG_PATTERN}")
        return v


class KnownServiceCreateRequest(BaseModel):
    """Create a known service entry (allow-list for discovery)."""

    model_config = ConfigDict(populate_by_name=True)

    runtime: ServiceRuntime
    name: str = Field(max_length=128)
    description: str | None = Field(default=None, max_length=512)
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        for tag in v:
            if not validate_tag(tag):
                raise ValueError(f"Invalid tag '{tag}'. Tags must match pattern: {TAG_PATTERN}")
        return v


class KnownServiceResponse(BaseModel):
    """Known service response model."""

    model_config = ConfigDict(populate_by_name=True)

    known_service_id: str = Field(alias="knownServiceId")
    runtime: str
    name: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    created_by: str | None = Field(default=None, alias="createdBy")
