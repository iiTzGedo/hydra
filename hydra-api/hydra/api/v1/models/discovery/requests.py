"""Discovery request models."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .enums import DiscoveryStatus, ScanStatus
from .schemas import ScanOptions, ScanResultDevice, ScanResultSummary, ScanTarget


class StartScanRequest(BaseModel):
    """Request to start a network discovery scan."""

    targets: list[ScanTarget] = Field(min_length=1, description="Scan targets")
    options: ScanOptions = Field(default_factory=ScanOptions)  # type: ignore[arg-type]
    delegate_to_node_id: Annotated[
        str | None,
        Field(default=None, alias="delegateToNodeId"),
    ]

    model_config = ConfigDict(populate_by_name=True)


class SubmitScanResultsRequest(BaseModel):
    """Request from agent to submit scan results."""

    results: list[ScanResultDevice] = Field(
        description="Discovered device data from delegated execution",
    )
    summary: ScanResultSummary
    error: dict[str, Any] | None = None

    model_config = ConfigDict(populate_by_name=True)


class DismissDeviceRequest(BaseModel):
    """Request to dismiss a discovered device."""

    reason: str | None = Field(default=None, description="Reason for dismissal")

    model_config = ConfigDict(populate_by_name=True)


class ApproveDeviceRequest(BaseModel):
    """Request to approve a discovered device."""

    model_config = ConfigDict(populate_by_name=True)

    auto_register: bool = Field(alias="autoRegister", default=True)
    node_id: str | None = Field(alias="nodeId", default=None)
    node_class: str | None = Field(alias="nodeClass", default=None)
    tags: list[str] = Field(default_factory=list)


class RejectDeviceRequest(BaseModel):
    """Request to reject a discovered device."""

    model_config = ConfigDict(populate_by_name=True)

    reason: str | None = None


class BulkApproveRequest(BaseModel):
    """Bulk approve multiple devices."""

    model_config = ConfigDict(populate_by_name=True)

    discovery_ids: list[str] = Field(alias="discoveryIds", min_length=1, max_length=50)
    auto_register: bool = Field(alias="autoRegister", default=True)


class BulkRejectRequest(BaseModel):
    """Bulk reject multiple devices."""

    model_config = ConfigDict(populate_by_name=True)

    discovery_ids: list[str] = Field(alias="discoveryIds", min_length=1, max_length=50)
    reason: str | None = None


class DiscoveryListParams(BaseModel):
    """Parameters for listing discovered devices."""

    status: DiscoveryStatus | None = None
    network_id: str | None = Field(default=None, alias="networkId")
    search: str | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    sort_by: Annotated[
        Literal["firstSeen", "lastSeen", "seenCount"],
        Field(default="lastSeen", alias="sortBy"),
    ]
    sort_order: Annotated[
        Literal["asc", "desc"],
        Field(default="desc", alias="sortOrder"),
    ]

    model_config = ConfigDict(populate_by_name=True)


class ScanListParams(BaseModel):
    """Parameters for listing scans."""

    status: ScanStatus | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    sort_by: Annotated[
        Literal["createdAt", "startedAt"],
        Field(default="createdAt", alias="sortBy"),
    ]
    sort_order: Annotated[
        Literal["asc", "desc"],
        Field(default="desc", alias="sortOrder"),
    ]

    model_config = ConfigDict(populate_by_name=True)
