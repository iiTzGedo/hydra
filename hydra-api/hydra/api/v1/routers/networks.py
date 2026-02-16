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
    response_model_by_alias=True,
    summary="List Networks",
    description="List all networks with optional filters and pagination.",
    dependencies=[Depends(require_permission("networks:read"))],
)
async def list_networks(
    networks_service: NetworksServiceDep,
    type: NetworkType | None = None,
    parent_network_id: str | None = Query(default=None, alias="parentNetworkId"),
    router_node_id: str | None = Query(default=None, alias="routerNodeId"),
    cidr: str | None = None,
    tags: list[str] | None = Query(default=None),
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort_by: Literal["networkId", "name", "createdAt", "updatedAt", "nodeCount"] = Query(
        default="updatedAt", alias="sortBy"
    ),
    sort_order: Literal["asc", "desc"] = Query(default="desc", alias="sortOrder"),
) -> SuccessResponse[list[NetworkSummary]]:
    """Retrieve a paginated list of discovered and manually created networks.

    Args:
        networks_service: Networks service instance.
        type: Filter by network type (vlan, vxlan, subnet, etc.).
        parent_network_id: Filter by parent network ID.
        router_node_id: Filter by router/gateway node ID.
        cidr: Filter by CIDR notation (exact match).
        tags: Filter by tags (networks must have all specified tags).
        search: Search query for network name or ID.
        limit: Maximum number of results to return.
        offset: Number of results to skip.
        sort_by: Field to sort by.
        sort_order: Sort direction (ascending or descending).

    Returns:
        Paginated list of network summaries with metadata.

    Raises:
        HTTPException 403: Insufficient permissions.
    """
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
    response_model_by_alias=True,
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
    """Manually create a new network definition.

    Args:
        request: Network configuration including CIDR and type.
        networks_service: Networks service instance.
        current_user: Authenticated user making the request.

    Returns:
        Created network details.

    Raises:
        HTTPException 400: Invalid network configuration.
        HTTPException 403: Insufficient permissions.
        HTTPException 409: Network with same CIDR already exists.
    """
    network = await networks_service.create_network(
        request,
        created_by=current_user.get("user_id", "manual"),
    )
    return SuccessResponse(data=NetworkResponse(**network))


@router.get(
    "/{network_id}",
    response_model=SuccessResponse[NetworkResponse],
    response_model_by_alias=True,
    summary="Get Network",
    description="Get detailed information about a specific network.",
    dependencies=[Depends(require_permission("networks:read"))],
)
async def get_network(
    network_id: str,
    networks_service: NetworksServiceDep,
    include_nodes: bool = Query(default=False, alias="includeNodes"),
) -> SuccessResponse[NetworkResponse]:
    """Retrieve detailed information for a single network.

    Args:
        network_id: Unique identifier of the network.
        networks_service: Networks service instance.
        include_nodes: Include list of nodes in this network.

    Returns:
        Complete network details including configuration.

    Raises:
        HTTPException 404: Network not found.
        HTTPException 403: Insufficient permissions.
    """
    network = await networks_service.get_network(network_id, include_nodes=include_nodes)
    return SuccessResponse(data=NetworkResponse(**network))


@router.patch(
    "/{network_id}",
    response_model=SuccessResponse[NetworkResponse],
    response_model_by_alias=True,
    summary="Update Network",
    description="Update network configuration.",
    dependencies=[Depends(require_permission("networks:update"))],
)
async def update_network(
    network_id: str,
    request: UpdateNetworkRequest,
    networks_service: NetworksServiceDep,
) -> SuccessResponse[NetworkResponse]:
    """Update configuration for an existing network.

    Args:
        network_id: Unique identifier of the network.
        request: Fields to update.
        networks_service: Networks service instance.

    Returns:
        Updated network details.

    Raises:
        HTTPException 404: Network not found.
        HTTPException 403: Insufficient permissions.
    """
    network = await networks_service.update_network(network_id, request)
    return SuccessResponse(data=NetworkResponse(**network))


@router.delete(
    "/{network_id}",
    response_model=SuccessResponse[NetworkResponse],
    response_model_by_alias=True,
    summary="Delete Network",
    description="Delete a network. Use force=true to delete even if nodes are associated.",
    dependencies=[Depends(require_permission("networks:delete"))],
)
async def delete_network(
    network_id: str,
    networks_service: NetworksServiceDep,
    force: bool = Query(default=False),
) -> SuccessResponse[NetworkResponse]:
    """Delete a network definition.

    Args:
        network_id: Unique identifier of the network.
        networks_service: Networks service instance.
        force: Delete even if nodes are still associated with this network.

    Returns:
        Deleted network details.

    Raises:
        HTTPException 404: Network not found.
        HTTPException 403: Insufficient permissions.
        HTTPException 409: Network has associated nodes and force=false.
    """
    network = await networks_service.delete_network(network_id, force=force)
    return SuccessResponse(data=NetworkResponse(**network))


@router.get(
    "/{network_id}/nodes",
    response_model=SuccessResponse[list[NetworkNodeInfo]],
    response_model_by_alias=True,
    summary="Get Network Nodes",
    description="Get all nodes that belong to a specific network.",
    dependencies=[Depends(require_permission("networks:read"))],
)
async def get_network_nodes(
    network_id: str,
    networks_service: NetworksServiceDep,
) -> SuccessResponse[list[NetworkNodeInfo]]:
    """Retrieve all nodes that have interfaces in the specified network.

    Args:
        network_id: Unique identifier of the network.
        networks_service: Networks service instance.

    Returns:
        List of nodes with their IP addresses in this network.

    Raises:
        HTTPException 404: Network not found.
        HTTPException 403: Insufficient permissions.
    """
    nodes = await networks_service.get_network_nodes(network_id)
    return SuccessResponse(data=[NetworkNodeInfo(**node) for node in nodes])
