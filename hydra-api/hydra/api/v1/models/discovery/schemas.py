"""Discovery shared schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .enums import (
    DiscoveryStatus,
    HostnameSource,
    ProfilingStrategy,
    ScanMethod,
    ScanStatus,
    ScanTrigger,
)

# ── Port & Protocol Detail Models ──────────────────────────────────────


class PortInference(BaseModel):
    """Inferred application details from a port banner."""

    model_config = ConfigDict(populate_by_name=True)

    os: str | None = None
    arch: str | None = None
    application: str | None = None
    version: str | None = None


class DetailedPort(BaseModel):
    """A single open port with service identification and banner data."""

    model_config = ConfigDict(populate_by_name=True)

    port: int
    protocol: str = "tcp"
    state: str = "open"
    service: str | None = None
    banner: str | None = None
    inference: PortInference | None = None


class MdnsDetail(BaseModel):
    """mDNS/Bonjour discovery details."""

    model_config = ConfigDict(populate_by_name=True)

    services: list[str] = Field(default_factory=list)
    hostname: str | None = None
    txt_records: Annotated[
        dict[str, str],
        Field(default_factory=dict, alias="txtRecords"),
    ]


class SsdpDetail(BaseModel):
    """SSDP/UPnP discovery details."""

    model_config = ConfigDict(populate_by_name=True)

    server: str | None = None
    location: str | None = None
    usn: str | None = None
    device_type: Annotated[str | None, Field(default=None, alias="deviceType")]


class SnmpDetail(BaseModel):
    """SNMP query result details."""

    model_config = ConfigDict(populate_by_name=True)

    sys_descr: Annotated[str | None, Field(default=None, alias="sysDescr")]
    sys_name: Annotated[str | None, Field(default=None, alias="sysName")]
    sys_object_id: Annotated[str | None, Field(default=None, alias="sysObjectID")]


class LldpDetail(BaseModel):
    """LLDP neighbor details."""

    model_config = ConfigDict(populate_by_name=True)

    chassis_id: Annotated[str | None, Field(default=None, alias="chassisId")]
    port_id: Annotated[str | None, Field(default=None, alias="portId")]
    system_name: Annotated[str | None, Field(default=None, alias="systemName")]
    system_description: Annotated[
        str | None,
        Field(default=None, alias="systemDescription"),
    ]


class ProtocolDetails(BaseModel):
    """Structured protocol discovery results."""

    model_config = ConfigDict(populate_by_name=True)

    mdns: MdnsDetail | None = None
    ssdp: SsdpDetail | None = None
    snmp: SnmpDetail | None = None
    lldp: LldpDetail | None = None


class HttpResponseDetail(BaseModel):
    """HTTP response captured during banner grabbing."""

    model_config = ConfigDict(populate_by_name=True)

    port: int
    status_code: Annotated[int | None, Field(default=None, alias="statusCode")]
    server: str | None = None
    title: str | None = None
    redirect_to: Annotated[str | None, Field(default=None, alias="redirectTo")]
    identified_as: Annotated[str | None, Field(default=None, alias="identifiedAs")]


# ── Identity Models ────────────────────────────────────────────────────


class ObservedIp(BaseModel):
    """An IP address observation tied to a scan."""

    model_config = ConfigDict(populate_by_name=True)

    address: str
    seen_at: Annotated[datetime, Field(alias="seenAt")]
    seen_in_scan: Annotated[str | None, Field(default=None, alias="seenInScan")]


# ── Scan Target & Options ─────────────────────────────────────────────


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

    model_config = ConfigDict(populate_by_name=True)

    hosts_scanned: Annotated[int, Field(alias="hostsScanned")]
    hosts_alive: Annotated[int, Field(alias="hostsAlive")]
    new_discoveries: Annotated[int, Field(alias="newDiscoveries")]
    returning_devices: Annotated[int, Field(alias="returningDevices")]
    departed_since_last: Annotated[
        int,
        Field(default=0, alias="departedSinceLast"),
    ]
    already_registered: Annotated[
        int,
        Field(default=0, alias="alreadyRegistered"),
    ]
    errors: list[str] = Field(default_factory=list)


# ── Device Sub-Documents ───────────────────────────────────────────────


class DeviceIdentity(BaseModel):
    """Identity information for a discovered device."""

    model_config = ConfigDict(populate_by_name=True)

    primary_mac: Annotated[str | None, Field(default=None, alias="primaryMac")]
    observed_macs: Annotated[
        list[str],
        Field(default_factory=list, alias="observedMacs"),
    ]
    mac_vendor: Annotated[str | None, Field(default=None, alias="macVendor")]
    mac_resolved: Annotated[bool, Field(default=False, alias="macResolved")]
    current_ip: Annotated[str, Field(alias="currentIp")]
    observed_ips: Annotated[
        list[ObservedIp],
        Field(default_factory=list, alias="observedIps"),
    ]
    hostname: str | None = None
    hostname_sources: Annotated[
        list[HostnameSource],
        Field(default_factory=list, alias="hostnameSources"),
    ]


class ProbeInfo(BaseModel):
    """Information about how a device was discovered."""

    model_config = ConfigDict(populate_by_name=True)

    scanned_by: Annotated[
        str,
        Field(alias="scannedBy", description="nodeId of scanning agent or 'api'"),
    ]
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

    open_ports: Annotated[
        list[DetailedPort],
        Field(default_factory=list, alias="openPorts"),
    ]
    port_numbers: Annotated[
        list[int],
        Field(default_factory=list, alias="portNumbers"),
    ]
    service_hints: Annotated[
        list[str],
        Field(default_factory=list, alias="serviceHints"),
    ]
    protocols: ProtocolDetails | None = None
    http_responses: Annotated[
        list[HttpResponseDetail],
        Field(default_factory=list, alias="httpResponses"),
    ]
    os_hint: Annotated[str | None, Field(default=None, alias="osHint")]
    vendor: str | None = None
    mac_oui: Annotated[str | None, Field(default=None, alias="macOui")]
    device_family: Annotated[str | None, Field(default=None, alias="deviceFamily")]


class Classification(BaseModel):
    """Device classification result."""

    model_config = ConfigDict(populate_by_name=True)

    suggested_class: Annotated[str, Field(alias="suggestedClass")]
    suggested_type: Annotated[str | None, Field(default=None, alias="suggestedType")]
    suggested_kind: Annotated[str | None, Field(default=None, alias="suggestedKind")]
    suggested_node_id: Annotated[
        str | None,
        Field(default=None, alias="suggestedNodeId"),
    ]
    suggested_display_name: Annotated[
        str | None,
        Field(default=None, alias="suggestedDisplayName"),
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    signals: list[str] = Field(default_factory=list)
    explanation: str | None = None
    eligible_for_registration: Annotated[
        bool,
        Field(default=True, alias="eligibleForRegistration"),
    ]


class Eligibility(BaseModel):
    """Agent compatibility and remote install assessment for a discovered device."""

    model_config = ConfigDict(populate_by_name=True)

    registerable: bool = True
    agent_compatible: Annotated[bool, Field(default=False, alias="agentCompatible")]
    agent_platform: Annotated[
        str | None,
        Field(default=None, alias="agentPlatform"),
    ]
    profiling_strategy: Annotated[
        ProfilingStrategy | None,
        Field(default=None, alias="profilingStrategy"),
    ]
    remote_installable: Annotated[
        bool,
        Field(default=False, alias="remoteInstallable"),
    ]
    remote_install_method: Annotated[
        str | None,
        Field(default=None, alias="remoteInstallMethod"),
    ]
    remote_install_blockers: Annotated[
        list[str],
        Field(default_factory=list, alias="remoteInstallBlockers"),
    ]
    blockers: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


# ── Scan Sub-Documents ─────────────────────────────────────────────────


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


class ScanExecution(BaseModel):
    """Execution context for a scan (who ran it, from where)."""

    model_config = ConfigDict(populate_by_name=True)

    scanned_by: Annotated[str | None, Field(default=None, alias="scannedBy")]
    scanned_from: Annotated[str | None, Field(default=None, alias="scannedFrom")]
    method: str | None = None
    delegated_to: Annotated[str | None, Field(default=None, alias="delegatedTo")]


# ── Ingest Payload (from agent scan results) ───────────────────────────


class ScanResultDevice(BaseModel):
    """Device payload ingested from delegated scan execution."""

    model_config = ConfigDict(populate_by_name=True)

    identity: DeviceIdentity
    network_id: Annotated[str | None, Field(default=None, alias="networkId")]
    probe: ProbeInfo
    open_ports: Annotated[list[int], Field(default_factory=list, alias="openPorts")]
    protocols: list[str] = Field(default_factory=list)
    raw_evidence: Annotated[
        RawEvidence | None,
        Field(default=None, alias="rawEvidence"),
    ]


# ── Top-Level Document Models ──────────────────────────────────────────


class DiscoveredDevice(BaseModel):
    """A device discovered through network scanning."""

    model_config = ConfigDict(populate_by_name=True)

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
    eligibility: Eligibility | None = None
    dismissed_at: Annotated[datetime | None, Field(default=None, alias="dismissedAt")]
    dismissed_by: Annotated[str | None, Field(default=None, alias="dismissedBy")]
    dismiss_reason: Annotated[str | None, Field(default=None, alias="dismissReason")]
    dismiss_permanent: Annotated[bool, Field(default=False, alias="dismissPermanent")]
    matched_node_id: Annotated[
        str | None,
        Field(default=None, alias="matchedNodeId"),
    ]


class DiscoveryScan(BaseModel):
    """Stored scan document shape."""

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
    started_by: Annotated[str, Field(alias="startedBy")]
    started_at: Annotated[datetime | None, Field(default=None, alias="startedAt")]
    completed_at: Annotated[datetime | None, Field(default=None, alias="completedAt")]
    created_at: Annotated[datetime, Field(alias="createdAt")]
    updated_at: Annotated[datetime, Field(alias="updatedAt")]


# ── Exclusion Model ───────────────────────────────────────────────────


class DiscoveryExclusion(BaseModel):
    """A rule to exclude devices from discovery results."""

    model_config = ConfigDict(populate_by_name=True)

    exclusion_id: Annotated[str, Field(alias="exclusionId")]
    type: Literal["mac", "ip", "ip-range"]
    value: str
    label: str
    reason: str | None = None
    created_by: Annotated[str, Field(alias="createdBy")]
    created_at: Annotated[datetime, Field(alias="createdAt")]


# ── Scan Diff Models ──────────────────────────────────────────────────


class DiffDeviceSummary(BaseModel):
    """Abbreviated device info for scan diff results."""

    model_config = ConfigDict(populate_by_name=True)

    discovery_id: Annotated[str, Field(alias="discoveryId")]
    ip: str | None = None
    mac: str | None = None
    hostname: str | None = None
    classification: Classification | None = None


class DiffChange(BaseModel):
    """A changed field between two scans for a device."""

    model_config = ConfigDict(populate_by_name=True)

    field: str
    from_value: Annotated[Any, Field(alias="from")]
    to_value: Annotated[Any, Field(alias="to")]


class DiffChangedDevice(BaseModel):
    """A device that changed between two scans."""

    model_config = ConfigDict(populate_by_name=True)

    discovery_id: Annotated[str, Field(alias="discoveryId")]
    ip: str | None = None
    hostname: str | None = None
    changes: list[DiffChange] = Field(default_factory=list)


class ScanDiffResult(BaseModel):
    """Result of comparing two scans."""

    model_config = ConfigDict(populate_by_name=True)

    network_id: Annotated[str, Field(alias="networkId")]
    from_scan: Annotated[dict[str, Any], Field(alias="fromScan")]
    to_scan: Annotated[dict[str, Any], Field(alias="toScan")]
    arrived: list[DiffDeviceSummary] = Field(default_factory=list)
    departed: list[DiffDeviceSummary] = Field(default_factory=list)
    changed: list[DiffChangedDevice] = Field(default_factory=list)
    unchanged: int = 0


# ── Drift Detection ──────────────────────────────────────────────────


class DriftChange(BaseModel):
    """A single field that drifted between scans."""

    model_config = ConfigDict(populate_by_name=True)

    field: str
    previous: Any = None
    current: Any = None


class DriftReport(BaseModel):
    """Drift detection report for a re-scanned device."""

    model_config = ConfigDict(populate_by_name=True)

    drift_id: Annotated[str, Field(alias="driftId")]
    discovery_id: Annotated[str, Field(alias="discoveryId")]
    node_id: Annotated[str | None, Field(default=None, alias="nodeId")]
    severity: Literal["info", "warning"]
    changes: list[DriftChange] = Field(default_factory=list)
    previous_classification: Annotated[
        str | None,
        Field(default=None, alias="previousClassification"),
    ]
    current_classification: Annotated[
        str | None,
        Field(default=None, alias="currentClassification"),
    ]
    detected_at: Annotated[datetime, Field(alias="detectedAt")]
