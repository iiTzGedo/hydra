"""Discovery models package.

All discovery models are split into sub-modules:
- enums.py: Discovery-related enums
- schemas.py: Shared embedded schemas (ScanTarget, DeviceIdentity, etc.)
- requests.py: Request models
- responses.py: Response models
"""

# Enums
from .enums import (  # noqa: F401
    DiscoveryStatus,
    HostnameSource,
    ProfilingStrategy,
    ScanMethod,
    ScanStatus,
    ScanTrigger,
)

# Request models
from .requests import (  # noqa: F401
    ApproveDeviceRequest,
    BulkApproveRequest,
    BulkRejectRequest,
    CreateExclusionRequest,
    DiscoveryListParams,
    DismissDeviceRequest,
    ExclusionListParams,
    RejectDeviceRequest,
    ScanListParams,
    StartScanRequest,
    SubmitScanResultsRequest,
)

# Response models
from .responses import (  # noqa: F401
    ApprovalResponse,
    BulkOperationResponse,
    DiscoveredDeviceResponse,
    ExclusionResponse,
    ScanDiffResponse,
    ScanResponse,
    ScanSummary,
)

# Shared schemas
from .schemas import (  # noqa: F401
    Classification,
    DelegationInfo,
    DetailedPort,
    DeviceIdentity,
    DiffChange,
    DiffChangedDevice,
    DiffDeviceSummary,
    DiscoveredDevice,
    DiscoveryExclusion,
    DiscoveryScan,
    Eligibility,
    Fingerprint,
    HttpResponseDetail,
    LldpDetail,
    MdnsDetail,
    ObservedIp,
    PortInference,
    ProbeInfo,
    ProtocolDetails,
    RawEvidence,
    ScanErrorInfo,
    ScanExecution,
    ScanOptions,
    ScanProgress,
    ScanResultDevice,
    ScanResultSummary,
    ScanTarget,
    SnmpDetail,
    SsdpDetail,
)

__all__ = [
    # Enums
    "DiscoveryStatus",
    "HostnameSource",
    "ProfilingStrategy",
    "ScanMethod",
    "ScanStatus",
    "ScanTrigger",
    # Requests
    "ApproveDeviceRequest",
    "BulkApproveRequest",
    "BulkRejectRequest",
    "CreateExclusionRequest",
    "DismissDeviceRequest",
    "DiscoveryListParams",
    "ExclusionListParams",
    "RejectDeviceRequest",
    "ScanListParams",
    "StartScanRequest",
    "SubmitScanResultsRequest",
    # Responses
    "ApprovalResponse",
    "BulkOperationResponse",
    "DiscoveredDeviceResponse",
    "ExclusionResponse",
    "ScanDiffResponse",
    "ScanResponse",
    "ScanSummary",
    # Schemas
    "Classification",
    "DelegationInfo",
    "DiffChange",
    "DiffChangedDevice",
    "DiffDeviceSummary",
    "DetailedPort",
    "DeviceIdentity",
    "DiscoveredDevice",
    "DiscoveryExclusion",
    "DiscoveryScan",
    "Eligibility",
    "Fingerprint",
    "HttpResponseDetail",
    "LldpDetail",
    "MdnsDetail",
    "ObservedIp",
    "PortInference",
    "ProbeInfo",
    "ProtocolDetails",
    "RawEvidence",
    "ScanErrorInfo",
    "ScanExecution",
    "ScanOptions",
    "ScanProgress",
    "ScanResultDevice",
    "ScanResultSummary",
    "ScanTarget",
    "SnmpDetail",
    "SsdpDetail",
]
