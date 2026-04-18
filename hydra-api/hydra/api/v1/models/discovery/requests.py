"""Discovery request models."""

from __future__ import annotations

from datetime import datetime
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
    permanent: bool = Field(
        default=False,
        description="If true, device will not reappear in future scans",
    )

    model_config = ConfigDict(populate_by_name=True)


class ApproveDeviceRequest(BaseModel):
    """Request to approve a discovered device."""

    model_config = ConfigDict(populate_by_name=True)

    auto_register: bool = Field(alias="autoRegister", default=True)
    node_id: str | None = Field(alias="nodeId", default=None)
    display_name: str | None = Field(alias="displayName", default=None)
    description: str | None = None
    node_class: str | None = Field(alias="nodeClass", default=None)
    node_type: str | None = Field(alias="nodeType", default=None)
    kind: str | None = None
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

    model_config = ConfigDict(populate_by_name=True)

    status: DiscoveryStatus | None = None
    network_id: str | None = Field(default=None, alias="networkId")
    device_class: str | None = Field(default=None, alias="deviceClass")
    agent_compatible: bool | None = Field(default=None, alias="agentCompatible")
    remote_installable: bool | None = Field(default=None, alias="remoteInstallable")
    min_confidence: float | None = Field(default=None, ge=0.0, le=1.0, alias="minConfidence")
    since: datetime | None = None
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


class ScanListParams(BaseModel):
    """Parameters for listing scans."""

    model_config = ConfigDict(populate_by_name=True)

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


class CreateExclusionRequest(BaseModel):
    """Request to create a discovery exclusion rule."""

    model_config = ConfigDict(populate_by_name=True)

    type: Literal["mac", "ip", "ip-range"]
    value: str = Field(min_length=1, max_length=256)
    label: str = Field(min_length=1, max_length=128)
    reason: str | None = Field(default=None, max_length=512)


class RegisterDeviceRequest(BaseModel):
    """Request to register a discovered device as a node.

    Unlike approve, register always creates a node. Fields override
    classification suggestions when provided.
    """

    model_config = ConfigDict(populate_by_name=True)

    node_id: str | None = Field(alias="nodeId", default=None)
    display_name: str | None = Field(alias="displayName", default=None)
    description: str | None = None
    node_class: str | None = Field(alias="class", default=None)
    node_type: str | None = Field(alias="type", default=None)
    kind: str | None = None
    tags: list[str] = Field(default_factory=list)
    override_classification: bool = Field(
        alias="overrideClassification",
        default=False,
        description="If true, use provided values even if classification disagrees",
    )


class ExclusionListParams(BaseModel):
    """Parameters for listing exclusions."""

    model_config = ConfigDict(populate_by_name=True)

    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class ResolveMacRequest(BaseModel):
    """Agent-submitted MAC resolution result for an IP-only discovery."""

    model_config = ConfigDict(populate_by_name=True)

    ip: str = Field(min_length=7, max_length=15, description="IPv4 address")
    mac: str = Field(
        min_length=11,
        max_length=17,
        description="Resolved MAC address (any case/separator)",
    )
    network_id: str = Field(alias="networkId", description="Network the IP lives on")
    source_node_id: str | None = Field(
        alias="sourceNodeId",
        default=None,
        description="Agent node that performed the resolution",
    )
