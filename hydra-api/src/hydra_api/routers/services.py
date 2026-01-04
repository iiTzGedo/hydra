"""Service management endpoints."""

from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, Query

from hydra_api.core.deps import MongoDBDep, require_permission
from hydra_api.models.common import PaginationMeta, SuccessResponse
from hydra_api.models.services import (
    ServiceListParams,
    ServiceResponse,
    ServiceRuntime,
    ServiceStatus,
    ServiceSummary,
    UpdateServiceRequest,
)
from hydra_api.services.services_service import ServicesService

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
    # Filter params
    node_id: str | None = Query(default=None, alias="nodeId"),
    runtime: ServiceRuntime | None = None,
    status: ServiceStatus | None = None,
    name: str | None = None,
    tags: list[str] | None = Query(default=None),
    port: int | None = Query(default=None, ge=1, le=65535),
    search: str | None = None,
    # Pagination
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    # Sorting
    sort_by: Literal["serviceId", "name", "lastSeen", "status", "runtime"] = Query(
        default="lastSeen", alias="sortBy"
    ),
    sort_order: Literal["asc", "desc"] = Query(default="desc", alias="sortOrder"),
) -> SuccessResponse[list[ServiceSummary]]:
    """List services with filters."""
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
    """Get a single service by ID."""
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
    """Update a service's metadata."""
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
    """Archive a service."""
    service = await services_service.archive_service(service_id)
    return SuccessResponse(data=ServiceResponse(**service))


# ==================== Node Services Endpoints ====================
# Additional router for /nodes/{nodeId}/services pattern

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
    """Get services for a node."""
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
