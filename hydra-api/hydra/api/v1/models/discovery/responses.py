"""Discovery response models."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from .enums import DiscoveryStatus, ScanStatus, ScanTrigger
from .schemas import (
    Classification,
    DelegationInfo,
    DeviceIdentity,
    Eligibility,
    Fingerprint,
    ProbeInfo,
    RawEvidence,
    ScanErrorInfo,
    ScanExecution,
    ScanOptions,
    ScanProgress,
    ScanResultSummary,
    ScanTarget,
)


class ScanResponse(BaseModel):
    """Full scan response."""

    model_config = ConfigDict(populate_by_name=True)

    scan_id: Annotated[str, Field(alias="scanId")]
    status: ScanStatus
    targets: list[ScanTarget]
    options: ScanOptions
    triggered_via: Annotated[
        ScanTrigger | None,
        Field(default=None, alias="triggeredVia"),
    ]
    execution: ScanExecution | None = None
    delegate_to_node_id: Annotated[
        str | None,
        Field(default=None, alias="delegateToNodeId"),
    ]
    summary: ScanResultSummary | None = None
    progress: ScanProgress = Field(default_factory=ScanProgress)  # type: ignore[arg-type]
    delegation: DelegationInfo | None = None
    error: ScanErrorInfo | None = None
    result_count: Annotated[int, Field(default=0, alias="resultCount")]
    started_at: Annotated[datetime | None, Field(default=None, alias="startedAt")]
    completed_at: Annotated[datetime | None, Field(default=None, alias="completedAt")]
    created_at: Annotated[datetime, Field(alias="createdAt")]
    updated_at: Annotated[datetime, Field(alias="updatedAt")]


class ScanSummary(BaseModel):
    """Summary view of a scan for list endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    scan_id: Annotated[str, Field(alias="scanId")]
    status: ScanStatus
    target_count: Annotated[int, Field(alias="targetCount")]
    result_count: Annotated[int, Field(default=0, alias="resultCount")]
    progress: ScanProgress = Field(default_factory=ScanProgress)  # type: ignore[arg-type]
    started_at: Annotated[datetime | None, Field(default=None, alias="startedAt")]
    created_at: Annotated[datetime, Field(alias="createdAt")]


class DiscoveredDeviceResponse(BaseModel):
    """Response model for a discovered device."""

    model_config = ConfigDict(populate_by_name=True)

    discovery_id: Annotated[str, Field(alias="discoveryId")]
    identity: DeviceIdentity
    network_id: Annotated[str | None, Field(default=None, alias="networkId")]
    probe: ProbeInfo
    status: DiscoveryStatus
    first_seen: Annotated[datetime, Field(alias="firstSeen")]
    last_seen: Annotated[datetime, Field(alias="lastSeen")]
    seen_count: Annotated[int, Field(alias="seenCount")]
    open_ports: Annotated[list[int], Field(default_factory=list, alias="openPorts")]
    protocols: list[str] = Field(default_factory=list)
    raw_evidence: Annotated[
        RawEvidence | None,
        Field(default=None, alias="rawEvidence"),
    ]
    fingerprint: Fingerprint | None = None
    classification: Classification | None = None
    eligibility: Eligibility | None = None
    dismissed_at: Annotated[datetime | None, Field(default=None, alias="dismissedAt")]
    dismissed_by: Annotated[str | None, Field(default=None, alias="dismissedBy")]
    dismiss_reason: Annotated[str | None, Field(default=None, alias="dismissReason")]
    dismiss_permanent: Annotated[bool, Field(default=False, alias="dismissPermanent")]
    approved_at: Annotated[datetime | None, Field(default=None, alias="approvedAt")]
    approved_by: Annotated[str | None, Field(default=None, alias="approvedBy")]
    rejected_at: Annotated[datetime | None, Field(default=None, alias="rejectedAt")]
    rejected_by: Annotated[str | None, Field(default=None, alias="rejectedBy")]
    reject_reason: Annotated[str | None, Field(default=None, alias="rejectReason")]
    matched_node_id: Annotated[str | None, Field(default=None, alias="matchedNodeId")]


class ApprovalResponse(BaseModel):
    """Response from approve/reject operation."""

    model_config = ConfigDict(populate_by_name=True)

    discovery_id: str = Field(alias="discoveryId")
    status: str
    matched_node_id: str | None = Field(alias="matchedNodeId", default=None)


class BulkOperationResponse(BaseModel):
    """Response from bulk approve/reject."""

    model_config = ConfigDict(populate_by_name=True)

    processed: int
    succeeded: int
    failed: int
    results: list[ApprovalResponse]
    errors: list[dict[str, str]] = Field(default_factory=list)


class ExclusionResponse(BaseModel):
    """Response model for a discovery exclusion."""

    model_config = ConfigDict(populate_by_name=True)

    exclusion_id: Annotated[str, Field(alias="exclusionId")]
    type: str
    value: str
    label: str
    reason: str | None = None
    created_by: Annotated[str, Field(alias="createdBy")]
    created_at: Annotated[datetime, Field(alias="createdAt")]


class ScanDiffResponse(BaseModel):
    """Response model for scan diff comparison."""

    model_config = ConfigDict(populate_by_name=True)

    network_id: Annotated[str, Field(alias="networkId")]
    from_scan: Annotated[dict[str, Any] | None, Field(alias="fromScan")]
    to_scan: Annotated[dict[str, Any] | None, Field(alias="toScan")]
    arrived: list[dict[str, Any]] = Field(default_factory=list)
    departed: list[dict[str, Any]] = Field(default_factory=list)
    changed: list[dict[str, Any]] = Field(default_factory=list)
    unchanged: int = 0
    error: str | None = None
