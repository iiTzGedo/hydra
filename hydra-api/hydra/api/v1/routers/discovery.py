"""Network discovery endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, Query

from hydra.api.v1.core.deps import (
    CurrentUser,
    MongoDBDep,
    get_authenticated_auth_source,
    get_authenticated_client_id,
    require_permission,
)
from hydra.api.v1.models.common import PaginationMeta, SuccessResponse
from hydra.api.v1.models.discovery import (
    ApprovalResponse,
    ApproveDeviceRequest,
    BulkApproveRequest,
    BulkOperationResponse,
    BulkRejectRequest,
    CreateExclusionRequest,
    DiscoveredDeviceResponse,
    DiscoveryListParams,
    DiscoveryStatus,
    DismissDeviceRequest,
    ExclusionListParams,
    ExclusionResponse,
    RegisterDeviceRequest,
    RegisterDeviceResponse,
    RejectDeviceRequest,
    ResolveMacRequest,
    ScanDiffResponse,
    ScanListParams,
    ScanResponse,
    ScanStatus,
    ScanSummary,
    ScanTrigger,
    StartScanRequest,
    SubmitScanResultsRequest,
)
from hydra.api.v1.services.discovery import DiscoveryService
from hydra.api.v1.services.discovery.exclusions import ExclusionService

router = APIRouter(prefix="/discovery", tags=["Discovery"])
logger = structlog.get_logger(__name__)


def _get_scan_trigger(current_user: dict[str, object]) -> ScanTrigger:
    """Map request provenance to a discovery trigger source."""
    auth_source = get_authenticated_auth_source(current_user)
    client_id = get_authenticated_client_id(current_user)

    if auth_source == "cookie":
        return ScanTrigger.WEB
    if auth_source == "internal" and client_id == "hydra-web":
        return ScanTrigger.WEB
    if auth_source == "internal" and client_id == "hydra-mcp":
        return ScanTrigger.MCP
    return ScanTrigger.API


def get_discovery_service(mongodb: MongoDBDep) -> DiscoveryService:
    """Get discovery service dependency."""
    return DiscoveryService(mongodb)


def get_exclusion_service(mongodb: MongoDBDep) -> ExclusionService:
    """Get exclusion service dependency."""
    return ExclusionService(mongodb)


DiscoveryServiceDep = Annotated[DiscoveryService, Depends(get_discovery_service)]
ExclusionServiceDep = Annotated[ExclusionService, Depends(get_exclusion_service)]


# ── Scans ────────────────────────────────────────────────────────────────


@router.post(
    "/scans",
    response_model=SuccessResponse[ScanResponse],
    response_model_by_alias=True,
    status_code=201,
    summary="Start Scan",
    description="Start a new network discovery scan.",
    dependencies=[Depends(require_permission("discovery:scan"))],
)
async def start_scan(
    request: StartScanRequest,
    service: DiscoveryServiceDep,
    user: CurrentUser,
) -> SuccessResponse[ScanResponse]:
    """Start a network discovery scan."""
    scan = await service.start_scan(
        request,
        user_id=user["userId"],
        user_role=user.get("role", "operator"),
        user_permissions=user.get("permissions", []),
        triggered_via=_get_scan_trigger(user),
    )
    return SuccessResponse(data=ScanResponse(**scan))


@router.get(
    "/scans",
    response_model=SuccessResponse[list[ScanSummary]],
    response_model_by_alias=True,
    summary="List Scans",
    description="List network discovery scans with optional filtering.",
    dependencies=[Depends(require_permission("discovery:read"))],
)
async def list_scans(
    service: DiscoveryServiceDep,
    status: ScanStatus | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort_by: Literal["createdAt", "startedAt"] = Query(default="createdAt", alias="sortBy"),
    sort_order: Literal["asc", "desc"] = Query(default="desc", alias="sortOrder"),
) -> SuccessResponse[list[ScanSummary]]:
    """List scans with pagination."""
    params = ScanListParams(
        status=status,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    scans, total = await service.list_scans(params)
    summaries = [
        ScanSummary(
            scan_id=s["scanId"],
            status=s["status"],
            target_count=len(s.get("targets", [])),
            result_count=s.get("resultCount", 0),
            progress=s.get("progress", {}),
            started_at=s.get("startedAt"),
            created_at=s["createdAt"],
        )
        for s in scans
    ]
    return SuccessResponse(
        data=summaries,
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.get(
    "/scans/{scan_id}",
    response_model=SuccessResponse[ScanResponse],
    response_model_by_alias=True,
    summary="Get Scan",
    description="Get details of a specific scan.",
    dependencies=[Depends(require_permission("discovery:read"))],
)
async def get_scan(
    scan_id: str,
    service: DiscoveryServiceDep,
) -> SuccessResponse[ScanResponse]:
    """Get a scan by ID."""
    scan = await service.get_scan(scan_id)
    return SuccessResponse(data=ScanResponse(**scan))


@router.post(
    "/scans/{scan_id}/results",
    response_model=SuccessResponse[ScanResponse],
    response_model_by_alias=True,
    summary="Submit Scan Results",
    description="Submit results from a completed scan (agent auth).",
    dependencies=[Depends(require_permission("discovery:scan"))],
)
async def submit_scan_results(
    scan_id: str,
    request: SubmitScanResultsRequest,
    service: DiscoveryServiceDep,
) -> SuccessResponse[ScanResponse]:
    """Submit scan results."""
    scan = await service.submit_scan_results(scan_id, request)
    return SuccessResponse(data=ScanResponse(**scan))


@router.delete(
    "/scans/{scan_id}",
    response_model=SuccessResponse[dict[str, str | bool | int]],
    response_model_by_alias=True,
    summary="Delete Scan",
    description=(
        "Hard-delete a scan record. When ``cascade=true`` is set, also "
        "delete every unregistered discovery produced by that scan. "
        "Registered discoveries (already promoted to nodes) are preserved."
    ),
    dependencies=[Depends(require_permission("discovery:configure"))],
)
async def delete_scan(
    scan_id: str,
    service: DiscoveryServiceDep,
    user: CurrentUser,
    cascade: bool = Query(
        default=False,
        description="Also delete unregistered discoveries produced by this scan",
    ),
) -> SuccessResponse[dict[str, str | bool | int]]:
    """Permanently delete a scan, optionally cascading to its discoveries."""
    result = await service.delete_scan(scan_id, user_id=user["userId"], cascade=cascade)
    return SuccessResponse(
        data={
            "deleted": True,
            "scanId": scan_id,
            "cascadeDeleted": result.get("cascadeDeleted", 0),
        },
    )


# ── Scan Diff ───────────────────────────────────────────────────────────


@router.get(
    "/diff",
    response_model=SuccessResponse[ScanDiffResponse],
    response_model_by_alias=True,
    summary="Scan Diff",
    description="Compare two scans for a network to find arrived, departed, and changed devices.",
    dependencies=[Depends(require_permission("discovery:read"))],
)
async def scan_diff(
    service: DiscoveryServiceDep,
    network_id: str = Query(alias="networkId"),
    from_scan: str | None = Query(default=None, alias="fromScan"),
    to_scan: str | None = Query(default=None, alias="toScan"),
) -> SuccessResponse[ScanDiffResponse]:
    """Compare scans to find network changes."""
    result = await service.compute_scan_diff(
        network_id=network_id,
        from_scan_id=from_scan,
        to_scan_id=to_scan,
    )
    return SuccessResponse(data=ScanDiffResponse(**result))


# ── Discovered Devices ──────────────────────────────────────────────────


@router.get(
    "/devices",
    response_model=SuccessResponse[list[DiscoveredDeviceResponse]],
    response_model_by_alias=True,
    summary="List Discovered Devices",
    description="List discovered devices with optional filtering.",
    dependencies=[Depends(require_permission("discovery:read"))],
)
async def list_discoveries(
    service: DiscoveryServiceDep,
    status: DiscoveryStatus | None = None,
    network_id: str | None = Query(default=None, alias="networkId"),
    device_class: str | None = Query(default=None, alias="deviceClass"),
    agent_compatible: bool | None = Query(default=None, alias="agentCompatible"),
    remote_installable: bool | None = Query(default=None, alias="remoteInstallable"),
    min_confidence: float | None = Query(default=None, ge=0.0, le=1.0, alias="minConfidence"),
    since: datetime | None = None,
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort_by: Literal["firstSeen", "lastSeen", "seenCount"] = Query(default="lastSeen", alias="sortBy"),
    sort_order: Literal["asc", "desc"] = Query(default="desc", alias="sortOrder"),
) -> SuccessResponse[list[DiscoveredDeviceResponse]]:
    """List discovered devices with pagination."""
    params = DiscoveryListParams(
        status=status,
        network_id=network_id,
        device_class=device_class,
        agent_compatible=agent_compatible,
        remote_installable=remote_installable,
        min_confidence=min_confidence,
        since=since,
        search=search,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    devices, total = await service.list_discoveries(params)
    responses = [DiscoveredDeviceResponse(**d) for d in devices]
    return SuccessResponse(
        data=responses,
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.post(
    "/devices/bulk-approve",
    response_model=SuccessResponse[BulkOperationResponse],
    response_model_by_alias=True,
    summary="Bulk Approve Devices",
    description="Approve multiple discovered devices at once.",
    dependencies=[Depends(require_permission("discovery:scan"))],
)
async def bulk_approve(
    request: BulkApproveRequest,
    service: DiscoveryServiceDep,
    user: CurrentUser,
) -> SuccessResponse[BulkOperationResponse]:
    """Bulk approve discovered devices."""
    result = await service.bulk_approve(
        request,
        user_id=user["userId"],
        user_permissions=user.get("permissions", []),
    )
    return SuccessResponse(data=BulkOperationResponse(**result))


@router.post(
    "/devices/bulk-reject",
    response_model=SuccessResponse[BulkOperationResponse],
    response_model_by_alias=True,
    summary="Bulk Reject Devices",
    description="Reject multiple discovered devices at once.",
    dependencies=[Depends(require_permission("discovery:scan"))],
)
async def bulk_reject(
    request: BulkRejectRequest,
    service: DiscoveryServiceDep,
    user: CurrentUser,
) -> SuccessResponse[BulkOperationResponse]:
    """Bulk reject discovered devices."""
    result = await service.bulk_reject(request, user_id=user["userId"])
    return SuccessResponse(data=BulkOperationResponse(**result))


@router.get(
    "/devices/{discovery_id}",
    response_model=SuccessResponse[DiscoveredDeviceResponse],
    response_model_by_alias=True,
    summary="Get Discovered Device",
    description="Get details of a specific discovered device.",
    dependencies=[Depends(require_permission("discovery:read"))],
)
async def get_discovery(
    discovery_id: str,
    service: DiscoveryServiceDep,
) -> SuccessResponse[DiscoveredDeviceResponse]:
    """Get a discovered device by ID."""
    device = await service.get_discovery(discovery_id)
    return SuccessResponse(data=DiscoveredDeviceResponse(**device))


@router.post(
    "/devices/{discovery_id}/approve",
    response_model=SuccessResponse[ApprovalResponse],
    response_model_by_alias=True,
    summary="Approve Discovered Device",
    description="Approve a discovered device, optionally auto-registering it as a node.",
    dependencies=[Depends(require_permission("discovery:scan"))],
)
async def approve_device(
    discovery_id: str,
    request: ApproveDeviceRequest,
    service: DiscoveryServiceDep,
    user: CurrentUser,
) -> SuccessResponse[ApprovalResponse]:
    """Approve a discovered device."""
    result = await service.approve_device(
        discovery_id,
        request,
        user_id=user["userId"],
        user_permissions=user.get("permissions", []),
    )
    return SuccessResponse(data=ApprovalResponse(**result))


@router.post(
    "/devices/{discovery_id}/reject",
    response_model=SuccessResponse[ApprovalResponse],
    response_model_by_alias=True,
    summary="Reject Discovered Device",
    description="Reject a discovered device.",
    dependencies=[Depends(require_permission("discovery:scan"))],
)
async def reject_device(
    discovery_id: str,
    request: RejectDeviceRequest,
    service: DiscoveryServiceDep,
    user: CurrentUser,
) -> SuccessResponse[ApprovalResponse]:
    """Reject a discovered device."""
    result = await service.reject_device(
        discovery_id, request, user_id=user["userId"]
    )
    return SuccessResponse(data=ApprovalResponse(**result))


@router.post(
    "/devices/{discovery_id}/register",
    response_model=SuccessResponse[RegisterDeviceResponse],
    response_model_by_alias=True,
    status_code=201,
    summary="Register Discovered Device",
    description="Register a discovered device as a node with optional field overrides.",
    dependencies=[Depends(require_permission("nodes:create"))],
)
async def register_device(
    discovery_id: str,
    request: RegisterDeviceRequest,
    service: DiscoveryServiceDep,
    user: CurrentUser,
) -> SuccessResponse[RegisterDeviceResponse]:
    """Register a discovered device as a node."""
    result = await service.register_device(
        discovery_id, request, user_id=user["userId"]
    )
    return SuccessResponse(data=RegisterDeviceResponse(**result))


@router.delete(
    "/devices/{discovery_id}",
    response_model=SuccessResponse[dict[str, str | bool]],
    response_model_by_alias=True,
    summary="Delete Discovered Device",
    description=(
        "Hard-delete a discovery record from the database. Unlike dismiss "
        "(soft delete), this removes the entry entirely so the next scan "
        "re-discovers the device from scratch."
    ),
    dependencies=[Depends(require_permission("discovery:dismiss"))],
)
async def delete_discovery(
    discovery_id: str,
    service: DiscoveryServiceDep,
    user: CurrentUser,
) -> SuccessResponse[dict[str, str | bool]]:
    """Permanently delete a discovered device."""
    await service.delete_discovery(discovery_id, user_id=user["userId"])
    return SuccessResponse(
        data={"deleted": True, "discoveryId": discovery_id},
    )


@router.post(
    "/devices/{discovery_id}/dismiss",
    response_model=SuccessResponse[DiscoveredDeviceResponse],
    response_model_by_alias=True,
    summary="Dismiss Discovered Device",
    description="Dismiss a discovered device so it no longer appears in pending lists.",
    dependencies=[Depends(require_permission("discovery:dismiss"))],
)
async def dismiss_discovery(
    discovery_id: str,
    request: DismissDeviceRequest,
    service: DiscoveryServiceDep,
    user: CurrentUser,
) -> SuccessResponse[DiscoveredDeviceResponse]:
    """Dismiss a discovered device."""
    device = await service.dismiss_discovery(
        discovery_id,
        reason=request.reason,
        user_id=user["userId"],
        permanent=request.permanent,
    )
    return SuccessResponse(data=DiscoveredDeviceResponse(**device))


# ── MAC Resolution ──────────────────────────────────────────────────────


@router.post(
    "/devices/_resolve-mac",
    response_model=SuccessResponse[DiscoveredDeviceResponse | None],
    response_model_by_alias=True,
    summary="Submit MAC Resolution",
    description=(
        "Agent-submitted MAC for an IP-only discovery. Rekeys the discovery "
        "from disc::ip::* to disc::mac::* (or merges into the existing MAC "
        "record). See spec §2.4.3."
    ),
    dependencies=[Depends(require_permission("discovery:scan"))],
)
async def submit_mac_resolution(
    request: ResolveMacRequest,
    service: DiscoveryServiceDep,
) -> SuccessResponse[DiscoveredDeviceResponse | None]:
    """Apply an agent-reported MAC to an existing IP-only discovery."""
    result = await service.submit_mac_resolution(
        ip=request.ip,
        mac=request.mac,
        network_id=request.network_id,
    )
    return SuccessResponse(
        data=DiscoveredDeviceResponse(**result) if result else None,
    )


# ── Exclusions ──────────────────────────────────────────────────────────


@router.post(
    "/exclusions",
    response_model=SuccessResponse[ExclusionResponse],
    response_model_by_alias=True,
    status_code=201,
    summary="Create Exclusion",
    description="Create a discovery exclusion rule to skip specific devices during scans.",
    dependencies=[Depends(require_permission("discovery:configure"))],
)
async def create_exclusion(
    request: CreateExclusionRequest,
    exclusion_service: ExclusionServiceDep,
    user: CurrentUser,
) -> SuccessResponse[ExclusionResponse]:
    """Create a discovery exclusion."""
    exclusion = await exclusion_service.create_exclusion(
        request, user_id=user["userId"],
    )
    return SuccessResponse(data=ExclusionResponse(**exclusion))


@router.get(
    "/exclusions",
    response_model=SuccessResponse[list[ExclusionResponse]],
    response_model_by_alias=True,
    summary="List Exclusions",
    description="List discovery exclusion rules.",
    dependencies=[Depends(require_permission("discovery:read"))],
)
async def list_exclusions(
    exclusion_service: ExclusionServiceDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SuccessResponse[list[ExclusionResponse]]:
    """List discovery exclusions."""
    params = ExclusionListParams(limit=limit, offset=offset)
    exclusions, total = await exclusion_service.list_exclusions(params)
    responses = [ExclusionResponse(**e) for e in exclusions]
    return SuccessResponse(
        data=responses,
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.delete(
    "/exclusions/{exclusion_id}",
    response_model=SuccessResponse[dict[str, str | bool]],
    response_model_by_alias=True,
    summary="Delete Exclusion",
    description="Delete a discovery exclusion rule.",
    dependencies=[Depends(require_permission("discovery:configure"))],
)
async def delete_exclusion(
    exclusion_id: str,
    exclusion_service: ExclusionServiceDep,
) -> SuccessResponse[dict[str, str | bool]]:
    """Delete a discovery exclusion."""
    await exclusion_service.delete_exclusion(exclusion_id)
    return SuccessResponse(data={"deleted": True, "exclusionId": exclusion_id})
