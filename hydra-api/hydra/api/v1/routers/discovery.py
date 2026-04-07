"""Network discovery endpoints."""

from __future__ import annotations

from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, Query

from hydra.api.v1.core.deps import CurrentUser, MongoDBDep, require_permission
from hydra.api.v1.models.common import PaginationMeta, SuccessResponse
from hydra.api.v1.models.discovery import (
    ApprovalResponse,
    ApproveDeviceRequest,
    BulkApproveRequest,
    BulkOperationResponse,
    BulkRejectRequest,
    DiscoveredDeviceResponse,
    DiscoveryListParams,
    DiscoveryStatus,
    DismissDeviceRequest,
    RejectDeviceRequest,
    ScanListParams,
    ScanResponse,
    ScanStatus,
    ScanSummary,
    StartScanRequest,
    SubmitScanResultsRequest,
)
from hydra.api.v1.services.discovery import DiscoveryService

router = APIRouter(prefix="/discovery", tags=["Discovery"])
logger = structlog.get_logger(__name__)


def get_discovery_service(mongodb: MongoDBDep) -> DiscoveryService:
    """Get discovery service dependency."""
    return DiscoveryService(mongodb)


DiscoveryServiceDep = Annotated[DiscoveryService, Depends(get_discovery_service)]


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
    result = await service.bulk_approve(request, user_id=user["userId"])
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
        discovery_id, request, user_id=user["userId"]
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
    "/devices/{discovery_id}/dismiss",
    response_model=SuccessResponse[DiscoveredDeviceResponse],
    response_model_by_alias=True,
    summary="Dismiss Discovered Device",
    description="Dismiss a discovered device so it no longer appears in pending lists.",
    dependencies=[Depends(require_permission("discovery:scan"))],
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
    )
    return SuccessResponse(data=DiscoveredDeviceResponse(**device))
