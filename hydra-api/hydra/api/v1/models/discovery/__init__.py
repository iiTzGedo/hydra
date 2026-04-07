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
    ScanMethod,
    ScanStatus,
)

# Request models
from .requests import (  # noqa: F401
    ApproveDeviceRequest,
    BulkApproveRequest,
    BulkRejectRequest,
    DiscoveryListParams,
    DismissDeviceRequest,
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
    ScanResponse,
    ScanSummary,
)

# Shared schemas
from .schemas import (  # noqa: F401
    Classification,
    DelegationInfo,
    DeviceIdentity,
    DiscoveredDevice,
    DiscoveryScan,
    Fingerprint,
    ProbeInfo,
    RawEvidence,
    ScanErrorInfo,
    ScanOptions,
    ScanProgress,
    ScanResultDevice,
    ScanResultSummary,
    ScanTarget,
)

__all__ = [
    # Enums
    "DiscoveryStatus",
    "ScanMethod",
    "ScanStatus",
    # Requests
    "ApproveDeviceRequest",
    "BulkApproveRequest",
    "BulkRejectRequest",
    "DismissDeviceRequest",
    "DiscoveryListParams",
    "RejectDeviceRequest",
    "ScanListParams",
    "StartScanRequest",
    "SubmitScanResultsRequest",
    # Responses
    "ApprovalResponse",
    "BulkOperationResponse",
    "DiscoveredDeviceResponse",
    "ScanResponse",
    "ScanSummary",
    # Schemas
    "Classification",
    "DelegationInfo",
    "DeviceIdentity",
    "DiscoveredDevice",
    "DiscoveryScan",
    "Fingerprint",
    "ProbeInfo",
    "RawEvidence",
    "ScanErrorInfo",
    "ScanOptions",
    "ScanProgress",
    "ScanResultDevice",
    "ScanResultSummary",
    "ScanTarget",
]
