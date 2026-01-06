"""Network management endpoints."""

from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, Query

from hydra.api.v1.core.deps import CurrentUser, MongoDBDep, require_permission
from hydra.api.v1.models.common import PaginationMeta, SuccessResponse
from hydra.api.v1.models.networks import (
    CreateNetworkRequest,
    NetworkListParams,
    NetworkNodeInfo,
    NetworkResponse,
    NetworkSummary,
    NetworkType,
    UpdateNetworkRequest,
)
from hydra.api.v1.services.networks import NetworksService

router = APIRouter(prefix="/networks", tags=["Networks"])
logger = structlog.get_logger(__name__)


def get_networks_service(mongodb: MongoDBDep) -> NetworksService:
    """Get networks service dependency."""
    return NetworksService(mongodb)


NetworksServiceDep = Annotated[NetworksService, Depends(get_networks_service)]


@router.get(
    "",
    response_model=SuccessResponse[list[NetworkSummary]],
    summary="List Networks",
    description="List all networks with optional filters and pagination.",
    dependencies=[Depends(require_permission("networks:read"))],
)
async def list_networks(
    networks_service: NetworksServiceDep,
    # Filter params
    type: NetworkType | None = None,
    parent_network_id: str | None = Query(default=None, alias="parentNetworkId"),
    router_node_id: str | None = Query(default=None, alias="routerNodeId"),
    cidr: str | None = None,
    tags: list[str] | None = Query(default=None),
    search: str | None = None,
    # Pagination
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    # Sorting
    sort_by: Literal["networkId", "name", "createdAt", "updatedAt", "nodeCount"] = Query(
        default="updatedAt", alias="sortBy"
    ),
    sort_order: Literal["asc", "desc"] = Query(default="desc", alias="sortOrder"),
) -> SuccessResponse[list[NetworkSummary]]:
    """List networks with filters."""
    params = NetworkListParams(
        type=type,
        parent_network_id=parent_network_id,
        router_node_id=router_node_id,
        cidr=cidr,
        tags=tags,
        search=search,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    networks, total = await networks_service.list_networks(params)

    return SuccessResponse(
        data=[NetworkSummary(**network) for network in networks],
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.post(
    "",
    response_model=SuccessResponse[NetworkResponse],
    status_code=201,
    summary="Create Network",
    description="Create a new network manually.",
    dependencies=[Depends(require_permission("networks:create"))],
)
async def create_network(
    request: CreateNetworkRequest,
    networks_service: NetworksServiceDep,
    current_user: CurrentUser,
) -> SuccessResponse[NetworkResponse]:
    """Create a new network."""
    network = await networks_service.create_network(
        request,
        created_by=current_user.get("user_id", "manual"),
    )
    return SuccessResponse(data=NetworkResponse(**network))


@router.get(
    "/{network_id}",
    response_model=SuccessResponse[NetworkResponse],
    summary="Get Network",
    description="Get detailed information about a specific network.",
    dependencies=[Depends(require_permission("networks:read"))],
)
async def get_network(
    network_id: str,
    networks_service: NetworksServiceDep,
    include_nodes: bool = Query(default=False, alias="includeNodes"),
) -> SuccessResponse[NetworkResponse]:
    """Get a single network by ID."""
    network = await networks_service.get_network(network_id, include_nodes=include_nodes)
    return SuccessResponse(data=NetworkResponse(**network))


@router.put(
    "/{network_id}",
    response_model=SuccessResponse[NetworkResponse],
    summary="Update Network",
    description="Update network configuration.",
    dependencies=[Depends(require_permission("networks:update"))],
)
async def update_network(
    network_id: str,
    request: UpdateNetworkRequest,
    networks_service: NetworksServiceDep,
) -> SuccessResponse[NetworkResponse]:
    """Update a network's configuration."""
    network = await networks_service.update_network(network_id, request)
    return SuccessResponse(data=NetworkResponse(**network))


@router.delete(
    "/{network_id}",
    response_model=SuccessResponse[NetworkResponse],
    summary="Delete Network",
    description="Delete a network. Use force=true to delete even if nodes are associated.",
    dependencies=[Depends(require_permission("networks:delete"))],
)
async def delete_network(
    network_id: str,
    networks_service: NetworksServiceDep,
    force: bool = Query(default=False),
) -> SuccessResponse[NetworkResponse]:
    """Delete a network."""
    network = await networks_service.delete_network(network_id, force=force)
    return SuccessResponse(data=NetworkResponse(**network))


@router.get(
    "/{network_id}/nodes",
    response_model=SuccessResponse[list[NetworkNodeInfo]],
    summary="Get Network Nodes",
    description="Get all nodes that belong to a specific network.",
    dependencies=[Depends(require_permission("networks:read"))],
)
async def get_network_nodes(
    network_id: str,
    networks_service: NetworksServiceDep,
) -> SuccessResponse[list[NetworkNodeInfo]]:
    """Get nodes in a network."""
    nodes = await networks_service.get_network_nodes(network_id)
    return SuccessResponse(data=[NetworkNodeInfo(**node) for node in nodes])
