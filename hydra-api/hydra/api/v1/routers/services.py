"""Service management endpoints."""

from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, Query

from hydra.api.v1.core.deps import MongoDBDep, require_permission
from hydra.api.v1.models.common import PaginationMeta, SuccessResponse
from hydra.api.v1.models.services import (
    ServiceListParams,
    ServiceResponse,
    ServiceRuntime,
    ServiceStatus,
    ServiceSummary,
    UpdateServiceRequest,
)
from hydra.api.v1.services.services_service import ServicesService

router = APIRouter(prefix="/services", tags=["Services"])
logger = structlog.get_logger(__name__)


def get_services_service(mongodb: MongoDBDep) -> ServicesService:
    """Get services service dependency."""
    return ServicesService(mongodb)


ServicesServiceDep = Annotated[ServicesService, Depends(get_services_service)]


@router.get(
    "",
    response_model=SuccessResponse[list[ServiceSummary]],
    summary="List Services",
    description="List all discovered services with optional filters and pagination.",
    dependencies=[Depends(require_permission("services:read"))],
)
async def list_services(
    services_service: ServicesServiceDep,
    node_id: str | None = Query(default=None, alias="nodeId"),
    runtime: ServiceRuntime | None = None,
    status: ServiceStatus | None = None,
    name: str | None = None,
    tags: list[str] | None = Query(default=None),
    port: int | None = Query(default=None, ge=1, le=65535),
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort_by: Literal["serviceId", "name", "lastSeen", "status", "runtime"] = Query(
        default="lastSeen", alias="sortBy"
    ),
    sort_order: Literal["asc", "desc"] = Query(default="desc", alias="sortOrder"),
) -> SuccessResponse[list[ServiceSummary]]:
    """Retrieve a paginated list of discovered services.

    Args:
        services_service: Services service instance.
        node_id: Filter by host node ID.
        runtime: Filter by service runtime (systemd, docker, kubernetes, etc.).
        status: Filter by service status (running, stopped, unknown).
        name: Filter by service name (partial match).
        tags: Filter by tags (services must have all specified tags).
        port: Filter by listening port.
        search: Search query for service name or ID.
        limit: Maximum number of results to return.
        offset: Number of results to skip.
        sort_by: Field to sort by.
        sort_order: Sort direction (ascending or descending).

    Returns:
        Paginated list of service summaries with metadata.

    Raises:
        HTTPException 403: Insufficient permissions.
    """
    params = ServiceListParams(
        node_id=node_id,
        runtime=runtime,
        status=status,
        name=name,
        tags=tags,
        port=port,
        search=search,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    services, total = await services_service.list_services(params)

    return SuccessResponse(
        data=[ServiceSummary(**service) for service in services],
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.get(
    "/{service_id}",
    response_model=SuccessResponse[ServiceResponse],
    summary="Get Service",
    description="Get detailed information about a specific service.",
    dependencies=[Depends(require_permission("services:read"))],
)
async def get_service(
    service_id: str,
    services_service: ServicesServiceDep,
) -> SuccessResponse[ServiceResponse]:
    """Retrieve detailed information for a single service.

    Args:
        service_id: Unique identifier of the service.
        services_service: Services service instance.

    Returns:
        Complete service details including configuration and ports.

    Raises:
        HTTPException 404: Service not found.
        HTTPException 403: Insufficient permissions.
    """
    service = await services_service.get_service(service_id)
    return SuccessResponse(data=ServiceResponse(**service))


@router.patch(
    "/{service_id}",
    response_model=SuccessResponse[ServiceResponse],
    summary="Update Service",
    description="Update service metadata (display name, description, tags).",
    dependencies=[Depends(require_permission("services:update"))],
)
async def update_service(
    service_id: str,
    request: UpdateServiceRequest,
    services_service: ServicesServiceDep,
) -> SuccessResponse[ServiceResponse]:
    """Update metadata for an existing service.

    Args:
        service_id: Unique identifier of the service.
        request: Fields to update.
        services_service: Services service instance.

    Returns:
        Updated service details.

    Raises:
        HTTPException 404: Service not found.
        HTTPException 403: Insufficient permissions.
    """
    service = await services_service.update_service(service_id, request)
    return SuccessResponse(data=ServiceResponse(**service))


@router.delete(
    "/{service_id}",
    response_model=SuccessResponse[ServiceResponse],
    summary="Archive Service",
    description="Archive a service (soft delete). The service's data is preserved.",
    dependencies=[Depends(require_permission("services:delete"))],
)
async def archive_service(
    service_id: str,
    services_service: ServicesServiceDep,
) -> SuccessResponse[ServiceResponse]:
    """Archive a service without permanently deleting its data.

    Args:
        service_id: Unique identifier of the service.
        services_service: Services service instance.

    Returns:
        Archived service details with updated status.

    Raises:
        HTTPException 404: Service not found.
        HTTPException 403: Insufficient permissions.
    """
    service = await services_service.archive_service(service_id)
    return SuccessResponse(data=ServiceResponse(**service))


nodes_services_router = APIRouter(prefix="/nodes", tags=["Nodes"])


@nodes_services_router.get(
    "/{node_id}/services",
    response_model=SuccessResponse[list[ServiceSummary]],
    summary="Get Node Services",
    description="Get all services running on a specific node.",
    dependencies=[Depends(require_permission("services:read"))],
)
async def get_node_services(
    node_id: str,
    services_service: ServicesServiceDep,
    runtime: ServiceRuntime | None = None,
    status: ServiceStatus | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SuccessResponse[list[ServiceSummary]]:
    """Retrieve all services running on a specific node.

    Args:
        node_id: Unique identifier of the host node.
        services_service: Services service instance.
        runtime: Filter by service runtime.
        status: Filter by service status.
        limit: Maximum number of results to return.
        offset: Number of results to skip.

    Returns:
        Paginated list of services on the specified node.

    Raises:
        HTTPException 404: Node not found.
        HTTPException 403: Insufficient permissions.
    """
    runtime_value = runtime.value if runtime else None
    status_value = status.value if status else None

    services, total = await services_service.get_services_by_node(
        node_id,
        runtime=runtime_value,
        status=status_value,
        limit=limit,
        offset=offset,
    )

    return SuccessResponse(
        data=[ServiceSummary(**service) for service in services],
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )
