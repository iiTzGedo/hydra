"""Home Assistant integration endpoints."""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Query

from hydra.api.v1.core.deps import MongoDBDep, require_permission
from hydra.api.v1.models.common import PaginationMeta, SuccessResponse
from hydra.api.v1.models.ha import (
    HAArea,
    HAAreaListResponse,
    HAControlRequest,
    HAControlResponse,
    HADevice,
    HADeviceListParams,
    HADeviceListResponse,
    HAStatusResponse,
    HASyncRequest,
    HASyncResponse,
    HydraNodeMapping,
)
from hydra.api.v1.services.ha import HomeAssistantService

router = APIRouter(prefix="/ha", tags=["Home Assistant"])
logger = structlog.get_logger(__name__)


def get_ha_service(mongodb: MongoDBDep) -> HomeAssistantService:
    """Get Home Assistant service dependency."""
    return HomeAssistantService(mongodb)


HAServiceDep = Annotated[HomeAssistantService, Depends(get_ha_service)]


@router.get(
    "/status",
    response_model=SuccessResponse[HAStatusResponse],
    summary="Get HA Status",
    description="Get Home Assistant integration status.",
    dependencies=[Depends(require_permission("ha:read"))],
)
async def get_ha_status(
    ha_service: HAServiceDep,
) -> SuccessResponse[HAStatusResponse]:
    """Get Home Assistant integration status.

    Args:
        ha_service: Home Assistant service instance.

    Returns:
        Integration status including connection state, entity count, and last sync time.

    Raises:
        HTTPException 403: Insufficient permissions.
    """
    status = await ha_service.get_status()

    return SuccessResponse(
        data=HAStatusResponse(
            enabled=status["enabled"],
            connected=status["connected"],
            url=status.get("url"),
            last_sync=status.get("lastSync"),
            entity_count=status.get("entityCount", 0),
            mapped_nodes=status.get("mappedNodes", 0),
        )
    )


@router.get(
    "/devices",
    response_model=SuccessResponse[HADeviceListResponse],
    summary="List HA Devices",
    description="List Home Assistant devices mapped to Hydra nodes.",
    dependencies=[Depends(require_permission("ha:read"))],
)
async def list_ha_devices(
    ha_service: HAServiceDep,
    domain: str | None = None,
    area: str | None = None,
    mapped: bool | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SuccessResponse[HADeviceListResponse]:
    """List Home Assistant devices with optional filters.

    Args:
        ha_service: Home Assistant service instance.
        domain: Filter by HA domain (light, switch, sensor, etc.).
        area: Filter by HA area name.
        mapped: Filter by Hydra node mapping status.
        limit: Maximum number of devices to return.
        offset: Number of devices to skip.

    Returns:
        Paginated list of HA devices with their states and Hydra mappings.

    Raises:
        HTTPException 403: Insufficient permissions.
    """
    params = HADeviceListParams(
        domain=domain,
        area=area,
        mapped=mapped,
        limit=limit,
        offset=offset,
    )

    devices, total = await ha_service.list_devices(params)

    return SuccessResponse(
        data=HADeviceListResponse(
            devices=[
                HADevice(
                    entity_id=d["entityId"],
                    name=d["name"],
                    domain=d["domain"],
                    area=d.get("area"),
                    state=d["state"],
                    attributes=d.get("attributes", {}),
                    hydra_node=(
                        HydraNodeMapping(
                            node_id=d["hydraNode"]["nodeId"],
                            display_name=d["hydraNode"]["displayName"],
                        )
                        if d.get("hydraNode")
                        else None
                    ),
                    last_updated=d.get("lastUpdated"),
                )
                for d in devices
            ],
            total=total,
        ),
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.post(
    "/sync",
    response_model=SuccessResponse[HASyncResponse],
    status_code=202,
    summary="Sync from HA",
    description="Trigger sync from Home Assistant.",
    dependencies=[Depends(require_permission("ha:sync"))],
)
async def sync_ha(
    request: HASyncRequest,
    ha_service: HAServiceDep,
) -> SuccessResponse[HASyncResponse]:
    """Trigger a synchronization from Home Assistant.

    Starts a background job to fetch and sync device states from Home Assistant.

    Args:
        request: Sync request with optional filters and options.
        ha_service: Home Assistant service instance.

    Returns:
        Sync job details including job ID and status.

    Raises:
        HTTPException 403: Insufficient permissions.
    """
    result = await ha_service.sync_devices(request)

    return SuccessResponse(
        data=HASyncResponse(
            job_id=result["jobId"],
            status=result["status"],
            started_at=result["startedAt"],
        )
    )


@router.post(
    "/control",
    response_model=SuccessResponse[HAControlResponse],
    summary="Control HA Device",
    description="Control a Home Assistant device.",
    dependencies=[Depends(require_permission("ha:control"))],
)
async def control_ha_device(
    request: HAControlRequest,
    ha_service: HAServiceDep,
) -> SuccessResponse[HAControlResponse]:
    """Send a control command to a Home Assistant device.

    Args:
        request: Control request with entity ID, service, and optional data.
        ha_service: Home Assistant service instance.

    Returns:
        Control result including success status and new device state.

    Raises:
        HTTPException 403: Insufficient permissions.
        HTTPException 404: Entity not found.
    """
    result = await ha_service.control_device(request)

    return SuccessResponse(
        data=HAControlResponse(
            entity_id=result["entityId"],
            service=result["service"],
            success=result["success"],
            new_state=result.get("newState"),
        )
    )


@router.get(
    "/areas",
    response_model=SuccessResponse[HAAreaListResponse],
    summary="List HA Areas",
    description="List Home Assistant areas.",
    dependencies=[Depends(require_permission("ha:read"))],
)
async def list_ha_areas(
    ha_service: HAServiceDep,
) -> SuccessResponse[HAAreaListResponse]:
    """List all Home Assistant areas.

    Args:
        ha_service: Home Assistant service instance.

    Returns:
        List of areas with device and entity counts.

    Raises:
        HTTPException 403: Insufficient permissions.
    """
    areas, total = await ha_service.list_areas()

    return SuccessResponse(
        data=HAAreaListResponse(
            areas=[
                HAArea(
                    area_id=a["areaId"],
                    name=a["name"],
                    device_count=a.get("deviceCount", 0),
                    entity_count=a.get("entityCount", 0),
                )
                for a in areas
            ],
            total=total,
        )
    )
