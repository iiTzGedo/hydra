"""Remote agent installation endpoints."""

from __future__ import annotations

from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, Path, Query

from hydra.api.v1.core.deps import CurrentUser, MongoDBDep, require_permission
from hydra.api.v1.models.common import PaginationMeta, SuccessResponse
from hydra.api.v1.models.installations import (
    InstallationListParams,
    InstallationResponse,
    InstallationStatus,
    InstallationSummary,
    ProxmoxInstallRequest,
    StartInstallationRequest,
)
from hydra.api.v1.services.installations import (
    InstallationService,
    ProxmoxInstallationService,
)

router = APIRouter(prefix="/installations", tags=["Installations"])
logger = structlog.get_logger(__name__)


def get_installation_service(mongodb: MongoDBDep) -> InstallationService:
    """Get installation service dependency."""
    return InstallationService(mongodb)


def get_proxmox_installation_service(
    mongodb: MongoDBDep,
) -> ProxmoxInstallationService:
    """Get Proxmox installation service dependency."""
    return ProxmoxInstallationService(mongodb)


InstallationServiceDep = Annotated[
    InstallationService, Depends(get_installation_service)
]

ProxmoxInstallationServiceDep = Annotated[
    ProxmoxInstallationService, Depends(get_proxmox_installation_service)
]


@router.post(
    "",
    response_model=SuccessResponse[InstallationResponse],
    response_model_by_alias=True,
    status_code=201,
    summary="Start Installation",
    description="Start a remote agent installation via SSH.",
    dependencies=[Depends(require_permission("installations:write"))],
)
async def start_installation(
    request: StartInstallationRequest,
    service: InstallationServiceDep,
    user: CurrentUser,
) -> SuccessResponse[InstallationResponse]:
    """Start a remote agent installation.

    Creates an installation record and launches a background SSH workflow
    to deploy the Hydra agent on the target host.

    Args:
        request: Installation parameters and SSH credentials.
        service: Installation service instance.
        user: Authenticated user context.

    Returns:
        The created installation.
    """
    installation = await service.start_installation(
        request, user_id=user["userId"]
    )
    return SuccessResponse(data=InstallationResponse(**installation))


@router.post(
    "/proxmox",
    response_model=SuccessResponse[InstallationResponse],
    response_model_by_alias=True,
    status_code=201,
    summary="Start Proxmox Installation",
    description="Start a remote agent installation inside a Proxmox VM/LXC via the PVE API.",
    dependencies=[Depends(require_permission("installations:write"))],
)
async def start_proxmox_installation(
    request: ProxmoxInstallRequest,
    service: ProxmoxInstallationServiceDep,
    user: CurrentUser,
) -> SuccessResponse[InstallationResponse]:
    """Start a Proxmox-based remote agent installation.

    Uses the PVE API to install the Hydra agent inside a VM or LXC container
    without requiring direct SSH access.

    Args:
        request: Proxmox installation parameters.
        service: Proxmox installation service instance.
        user: Authenticated user context.

    Returns:
        The created installation.
    """
    installation = await service.start_proxmox_installation(
        request,
        user_id=user["userId"],
        user_role=user.get("role", ""),
        user_permissions=user.get("permissions", []),
    )
    return SuccessResponse(data=InstallationResponse(**installation))


@router.get(
    "",
    response_model=SuccessResponse[list[InstallationSummary]],
    response_model_by_alias=True,
    summary="List Installations",
    description="List remote agent installations with optional filtering and pagination.",
    dependencies=[Depends(require_permission("installations:read"))],
)
async def list_installations(
    service: InstallationServiceDep,
    user: CurrentUser,
    status: InstallationStatus | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort_by: Literal["createdAt", "updatedAt"] = Query(
        default="createdAt", alias="sortBy"
    ),
    sort_order: Literal["asc", "desc"] = Query(default="desc", alias="sortOrder"),
) -> SuccessResponse[list[InstallationSummary]]:
    """List installations with pagination.

    Args:
        service: Installation service instance.
        user: Authenticated user context.
        status: Filter by installation status.
        limit: Maximum number of results to return.
        offset: Number of results to skip.
        sort_by: Field to sort by.
        sort_order: Sort direction.

    Returns:
        Paginated list of installation summaries.
    """
    params = InstallationListParams(
        status=status,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    user_id = user.get("user_id") or user.get("userId", "")
    installations, total = await service.list_installations(params, user_id)

    summaries = [
        InstallationSummary(
            installation_id=inst["installationId"],
            target_ip=inst["targetIp"],
            target_hostname=inst.get("targetHostname"),
            status=inst["status"],
            phase=inst.get("progress", {}).get("phase", inst["status"]),
            node_id=inst.get("nodeId"),
            created_at=inst["createdAt"],
        )
        for inst in installations
    ]

    return SuccessResponse(
        data=summaries,
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.get(
    "/{installation_id}",
    response_model=SuccessResponse[InstallationResponse],
    response_model_by_alias=True,
    summary="Get Installation",
    description="Get details of a specific installation.",
    dependencies=[Depends(require_permission("installations:read"))],
)
async def get_installation(
    installation_id: str = Path(description="Installation ID"),
    *,
    service: InstallationServiceDep,
) -> SuccessResponse[InstallationResponse]:
    """Get an installation by ID.

    Args:
        installation_id: Unique installation identifier.
        service: Installation service instance.

    Returns:
        Full installation details including progress.
    """
    installation = await service.get_installation(installation_id)
    return SuccessResponse(data=InstallationResponse(**installation))


@router.post(
    "/{installation_id}/cancel",
    response_model=SuccessResponse[InstallationResponse],
    response_model_by_alias=True,
    summary="Cancel Installation",
    description="Cancel an active installation.",
    dependencies=[Depends(require_permission("installations:write"))],
)
async def cancel_installation(
    service: InstallationServiceDep,
    user: CurrentUser,
    installation_id: str = Path(description="Installation ID"),
) -> SuccessResponse[InstallationResponse]:
    """Cancel an active installation.

    Args:
        service: Installation service instance.
        user: Authenticated user context.
        installation_id: Installation to cancel.

    Returns:
        The cancelled installation.
    """
    user_id = user.get("user_id") or user.get("userId", "")
    installation = await service.cancel_installation(installation_id, user_id)
    return SuccessResponse(data=InstallationResponse(**installation))


@router.post(
    "/{installation_id}/retry",
    response_model=SuccessResponse[InstallationResponse],
    response_model_by_alias=True,
    summary="Retry Installation",
    description="Retry a failed installation.",
    dependencies=[Depends(require_permission("installations:write"))],
)
async def retry_installation(
    service: InstallationServiceDep,
    user: CurrentUser,
    installation_id: str = Path(description="Installation ID"),
) -> SuccessResponse[InstallationResponse]:
    """Retry a failed installation.

    Only installations in the 'failed' state can be retried.

    Args:
        service: Installation service instance.
        user: Authenticated user context.
        installation_id: Installation to retry.

    Returns:
        The retried installation with reset progress.
    """
    user_id = user.get("user_id") or user.get("userId", "")
    installation = await service.retry_installation(installation_id, user_id)
    return SuccessResponse(data=InstallationResponse(**installation))
