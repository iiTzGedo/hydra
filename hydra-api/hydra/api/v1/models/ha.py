"""Home Assistant integration models."""

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field


class HASyncRequest(BaseModel):
    """Request to trigger HA sync."""

    domains: list[str] | None = Field(
        default=None,
        description="HA domains to sync (e.g., climate, light, switch). Null = all.",
    )
    create_nodes: Annotated[
        bool,
        Field(default=True, alias="createNodes", description="Create Hydra nodes for HA devices"),
    ]

    model_config = ConfigDict(populate_by_name=True)


class HAControlRequest(BaseModel):
    """Request to control an HA device."""

    entity_id: Annotated[str, Field(alias="entityId", description="Home Assistant entity ID")]
    service: str = Field(description="Service to call (e.g., turn_on, set_temperature)")
    data: dict[str, Any] | None = Field(default=None, description="Service data")

    model_config = ConfigDict(populate_by_name=True)


class HAStatusResponse(BaseModel):
    """Home Assistant integration status."""

    enabled: bool = Field(description="Whether HA integration is enabled")
    connected: bool = Field(description="Whether currently connected to HA")
    url: str | None = Field(default=None, description="HA instance URL")
    last_sync: Annotated[datetime | None, Field(default=None, alias="lastSync")]
    entity_count: Annotated[int, Field(default=0, alias="entityCount")]
    mapped_nodes: Annotated[int, Field(default=0, alias="mappedNodes")]

    model_config = ConfigDict(populate_by_name=True)


class HydraNodeMapping(BaseModel):
    """Mapping from HA device to Hydra node."""

    node_id: Annotated[str, Field(alias="nodeId")]
    display_name: Annotated[str, Field(alias="displayName")]

    model_config = ConfigDict(populate_by_name=True)


class HADevice(BaseModel):
    """Home Assistant device/entity."""

    entity_id: Annotated[str, Field(alias="entityId")]
    name: str
    domain: str
    area: str | None = None
    state: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    hydra_node: Annotated[HydraNodeMapping | None, Field(default=None, alias="hydraNode")]
    last_updated: Annotated[datetime | None, Field(default=None, alias="lastUpdated")]

    model_config = ConfigDict(populate_by_name=True)


class HADeviceListResponse(BaseModel):
    """Response for listing HA devices."""

    devices: list[HADevice]
    total: int


class HASyncResponse(BaseModel):
    """Response when HA sync is triggered."""

    job_id: Annotated[str, Field(alias="jobId")]
    status: str
    started_at: Annotated[datetime, Field(alias="startedAt")]

    model_config = ConfigDict(populate_by_name=True)


class HAControlResponse(BaseModel):
    """Response from HA control action."""

    entity_id: Annotated[str, Field(alias="entityId")]
    service: str
    success: bool
    new_state: Annotated[dict[str, Any] | None, Field(default=None, alias="newState")]

    model_config = ConfigDict(populate_by_name=True)


class HAArea(BaseModel):
    """Home Assistant area."""

    area_id: Annotated[str, Field(alias="areaId")]
    name: str
    device_count: Annotated[int, Field(alias="deviceCount")]
    entity_count: Annotated[int, Field(alias="entityCount")]

    model_config = ConfigDict(populate_by_name=True)


class HAAreaListResponse(BaseModel):
    """Response for listing HA areas."""

    areas: list[HAArea]
    total: int


class HADeviceListParams(BaseModel):
    """Parameters for listing HA devices."""

    domain: str | None = None
    area: str | None = None
    mapped: bool | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)

    model_config = ConfigDict(populate_by_name=True)
