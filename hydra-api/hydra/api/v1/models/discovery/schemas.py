"""Discovery shared schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .enums import DiscoveryStatus, ScanMethod, ScanStatus


class ScanTarget(BaseModel):
    """Target specification for a network scan."""

    network_id: Annotated[str | None, Field(default=None, alias="networkId")]
    subnet: str | None = Field(
        default=None,
        description="CIDR subnet to scan (e.g. 192.168.1.0/24)",
    )
    delegate_to_node_id: Annotated[
        str | None,
        Field(default=None, alias="delegateToNodeId"),
    ]

    model_config = ConfigDict(populate_by_name=True)


class ScanOptions(BaseModel):
    """Options controlling scan behavior."""

    methods: list[ScanMethod] = Field(
        default_factory=lambda: list(ScanMethod),
        description="Scanning methods to use",
    )
    port_tier: Annotated[
        Literal["tier1", "tier2"],
        Field(default="tier1", alias="portTier"),
    ]
    timeout_seconds: Annotated[
        int,
        Field(default=60, ge=1, le=600, alias="timeoutSeconds"),
    ]
    include_iot_protocols: Annotated[
        bool,
        Field(default=False, alias="includeIoTProtocols"),
    ]

    model_config = ConfigDict(populate_by_name=True)


class ScanResultSummary(BaseModel):
    """Summary of scan results."""

    hosts_scanned: Annotated[int, Field(alias="hostsScanned")]
    hosts_alive: Annotated[int, Field(alias="hostsAlive")]
    new_discoveries: Annotated[int, Field(alias="newDiscoveries")]
    returning_devices: Annotated[int, Field(alias="returningDevices")]
    errors: list[str] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class DeviceIdentity(BaseModel):
    """Identity information for a discovered device."""

    primary_mac: Annotated[str | None, Field(default=None, alias="primaryMac")]
    current_ip: Annotated[str, Field(alias="currentIp")]
    hostname: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class ProbeInfo(BaseModel):
    """Information about how a device was discovered."""

    scanned_by: Annotated[str, Field(alias="scannedBy", description="nodeId of scanning agent")]
    method: ScanMethod
    scanned_at: Annotated[datetime, Field(alias="scannedAt")]
    source_subnet: Annotated[str | None, Field(default=None, alias="sourceSubnet")]
    delegated_by_scan_id: Annotated[
        str | None,
        Field(default=None, alias="delegatedByScanId"),
    ]
    scan_methods: Annotated[
        list[ScanMethod],
        Field(default_factory=list, alias="scanMethods"),
    ]

    model_config = ConfigDict(populate_by_name=True)


class RawEvidence(BaseModel):
    """Raw evidence captured during discovery before enrichment/classification."""

    model_config = ConfigDict(populate_by_name=True)

    vendor: str | None = None
    mac_oui: Annotated[str | None, Field(default=None, alias="macOui")]
    dns_names: Annotated[list[str], Field(default_factory=list, alias="dnsNames")]
    banners: dict[str, str] = Field(default_factory=dict)
    protocol_details: Annotated[
        dict[str, Any],
        Field(default_factory=dict, alias="protocolDetails"),
    ]
    signals: list[str] = Field(default_factory=list)


class Fingerprint(BaseModel):
    """Device fingerprint from port/protocol analysis."""

    model_config = ConfigDict(populate_by_name=True)

    open_ports: Annotated[list[int], Field(default_factory=list, alias="openPorts")]
    service_hints: Annotated[list[str], Field(default_factory=list, alias="serviceHints")]
    protocols: list[str] = Field(default_factory=list)
    os_hint: Annotated[str | None, Field(default=None, alias="osHint")]
    vendor: str | None = None
    mac_oui: Annotated[str | None, Field(default=None, alias="macOui")]
    device_family: Annotated[str | None, Field(default=None, alias="deviceFamily")]


class Classification(BaseModel):
    """Device classification result."""

    model_config = ConfigDict(populate_by_name=True)

    suggested_class: Annotated[str, Field(alias="suggestedClass")]
    suggested_type: Annotated[str | None, Field(default=None, alias="suggestedType")]
    confidence: float = Field(ge=0.0, le=1.0)
    signals: list[str] = Field(default_factory=list)
    explanation: str | None = None
    eligible_for_registration: Annotated[
        bool,
        Field(default=True, alias="eligibleForRegistration"),
    ]


class DelegationInfo(BaseModel):
    """Execution details for a delegated scan."""

    model_config = ConfigDict(populate_by_name=True)

    delegated_to: Annotated[str | None, Field(default=None, alias="delegatedTo")]
    command_id: Annotated[str | None, Field(default=None, alias="commandId")]
    execution_method: Annotated[
        str | None,
        Field(default=None, alias="executionMethod"),
    ]
    command_status: Annotated[str | None, Field(default=None, alias="commandStatus")]
    notes: list[str] = Field(default_factory=list)


class ScanProgress(BaseModel):
    """Progress metadata for an in-flight or completed scan."""

    model_config = ConfigDict(populate_by_name=True)

    phase: str = "queued"
    hosts_total: Annotated[int, Field(default=0, alias="hostsTotal")]
    hosts_scanned: Annotated[int, Field(default=0, alias="hostsScanned")]
    hosts_alive: Annotated[int, Field(default=0, alias="hostsAlive")]
    percent_complete: Annotated[
        float,
        Field(default=0.0, alias="percentComplete", ge=0.0, le=100.0),
    ]


class ScanErrorInfo(BaseModel):
    """Structured error information for a failed scan."""

    model_config = ConfigDict(populate_by_name=True)

    code: str
    message: str
    details: dict[str, Any] | None = None


class ScanResultDevice(BaseModel):
    """Device payload ingested from delegated scan execution."""

    identity: DeviceIdentity
    network_id: Annotated[str | None, Field(default=None, alias="networkId")]
    probe: ProbeInfo
    open_ports: Annotated[list[int], Field(default_factory=list, alias="openPorts")]
    protocols: list[str] = Field(default_factory=list)
    raw_evidence: Annotated[
        RawEvidence | None,
        Field(default=None, alias="rawEvidence"),
    ]

    model_config = ConfigDict(populate_by_name=True)


class DiscoveredDevice(BaseModel):
    """A device discovered through network scanning."""

    discovery_id: Annotated[str, Field(alias="discoveryId")]
    identity: DeviceIdentity
    network_id: Annotated[str | None, Field(default=None, alias="networkId")]
    probe: ProbeInfo
    status: DiscoveryStatus = DiscoveryStatus.PENDING
    first_seen: Annotated[datetime, Field(alias="firstSeen")]
    last_seen: Annotated[datetime, Field(alias="lastSeen")]
    seen_count: Annotated[int, Field(default=1, alias="seenCount")]
    open_ports: Annotated[list[int], Field(default_factory=list, alias="openPorts")]
    protocols: list[str] = Field(default_factory=list)
    raw_evidence: Annotated[
        RawEvidence | None,
        Field(default=None, alias="rawEvidence"),
    ]
    fingerprint: Fingerprint | None = None
    classification: Classification | None = None
    dismissed_at: Annotated[datetime | None, Field(default=None, alias="dismissedAt")]
    dismissed_by: Annotated[str | None, Field(default=None, alias="dismissedBy")]
    dismiss_reason: Annotated[str | None, Field(default=None, alias="dismissReason")]
    matched_node_id: Annotated[
        str | None,
        Field(default=None, alias="matchedNodeId", description="Set after registration"),
    ]

    model_config = ConfigDict(populate_by_name=True)


class DiscoveryScan(BaseModel):
    """Stored scan document shape."""

    scan_id: Annotated[str, Field(alias="scanId")]
    status: ScanStatus
    targets: list[ScanTarget]
    options: ScanOptions
    delegate_to_node_id: Annotated[
        str | None,
        Field(default=None, alias="delegateToNodeId"),
    ]
    summary: ScanResultSummary | None = None
    progress: ScanProgress = Field(default_factory=ScanProgress)  # type: ignore[arg-type]
    delegation: DelegationInfo | None = None
    error: ScanErrorInfo | None = None
    result_count: Annotated[int, Field(default=0, alias="resultCount")]
    started_by: Annotated[str, Field(alias="startedBy")]
    started_at: Annotated[datetime | None, Field(default=None, alias="startedAt")]
    completed_at: Annotated[datetime | None, Field(default=None, alias="completedAt")]
    created_at: Annotated[datetime, Field(alias="createdAt")]
    updated_at: Annotated[datetime, Field(alias="updatedAt")]

    model_config = ConfigDict(populate_by_name=True)
