"""Topology management endpoints."""

from datetime import datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Query

from hydra.api.v1.core.deps import MongoDBDep, require_permission
from hydra.api.v1.models.common import PaginationMeta, SuccessResponse
from hydra.api.v1.models.topologies import (
    GenerateTopologyRequest,
    SubgraphResponse,
    TopologyDiffResponse,
    TopologyListParams,
    TopologyMode,
    TopologyResponse,
    TopologySummary,
)
from hydra.api.v1.services.topologies import TopologiesService

router = APIRouter(prefix="/topologies", tags=["Topologies"])
logger = structlog.get_logger(__name__)


def get_topologies_service(mongodb: MongoDBDep) -> TopologiesService:
    """Get topologies service dependency."""
    return TopologiesService(mongodb)


TopologiesServiceDep = Annotated[TopologiesService, Depends(get_topologies_service)]


@router.get(
    "",
    response_model=SuccessResponse[list[TopologySummary]],
    summary="List Topologies",
    description="List all topology snapshots with optional filters and pagination.",
    dependencies=[Depends(require_permission("topologies:read"))],
)
async def list_topologies(
    topologies_service: TopologiesServiceDep,
    mode: TopologyMode | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> SuccessResponse[list[TopologySummary]]:
    """Retrieve a paginated list of topology snapshots.

    Args:
        topologies_service: Topologies service instance.
        mode: Filter by topology mode (infrastructure or network).
        since: Only include topologies created after this timestamp.
        until: Only include topologies created before this timestamp.
        limit: Maximum number of results to return.
        offset: Number of results to skip.

    Returns:
        Paginated list of topology summaries with metadata.

    Raises:
        HTTPException 403: Insufficient permissions.
    """
    params = TopologyListParams(
        mode=mode,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )

    topologies, total = await topologies_service.list_topologies(params)

    return SuccessResponse(
        data=[TopologySummary(**t) for t in topologies],
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.get(
    "/latest",
    response_model=SuccessResponse[TopologyResponse],
    summary="Get Latest Topology",
    description="Get the latest topology for a specific mode.",
    dependencies=[Depends(require_permission("topologies:read"))],
)
async def get_latest_topology(
    topologies_service: TopologiesServiceDep,
    mode: TopologyMode = Query(...),
    include_graph: bool = Query(default=True, alias="includeGraph"),
) -> SuccessResponse[TopologyResponse]:
    """Retrieve the most recent topology snapshot for a given mode.

    Args:
        topologies_service: Topologies service instance.
        mode: Topology mode (infrastructure or network).
        include_graph: Include full graph data (nodes and edges).

    Returns:
        Latest topology with optional graph data.

    Raises:
        HTTPException 404: No topologies exist for the specified mode.
        HTTPException 403: Insufficient permissions.
    """
    topology = await topologies_service.get_latest_topology(mode, include_graph=include_graph)
    return SuccessResponse(data=TopologyResponse(**topology))


@router.get(
    "/diff",
    response_model=SuccessResponse[TopologyDiffResponse],
    summary="Compare Topologies",
    description="Compare two topologies and return the differences.",
    dependencies=[Depends(require_permission("topologies:read"))],
)
async def diff_topologies(
    topologies_service: TopologiesServiceDep,
    from_id: str | None = Query(default=None, alias="fromId"),
    to_id: str | None = Query(default=None, alias="toId"),
    mode: TopologyMode | None = None,
) -> SuccessResponse[TopologyDiffResponse]:
    """Compare two topology snapshots to identify infrastructure changes.

    Args:
        topologies_service: Topologies service instance.
        from_id: Starting topology ID (defaults to second-latest).
        to_id: Ending topology ID (defaults to latest).
        mode: Topology mode to compare (required if IDs not specified).

    Returns:
        Diff result showing added, removed, and modified elements.

    Raises:
        HTTPException 400: Mode required when IDs not specified.
        HTTPException 404: Topology not found or insufficient topologies.
        HTTPException 403: Insufficient permissions.
    """
    result = await topologies_service.diff_topologies(from_id, to_id, mode)
    return SuccessResponse(data=TopologyDiffResponse(**result))


@router.get(
    "/{topology_id}",
    response_model=SuccessResponse[TopologyResponse],
    summary="Get Topology",
    description="Get detailed information about a specific topology.",
    dependencies=[Depends(require_permission("topologies:read"))],
)
async def get_topology(
    topology_id: str,
    topologies_service: TopologiesServiceDep,
    include_graph: bool = Query(default=True, alias="includeGraph"),
) -> SuccessResponse[TopologyResponse]:
    """Retrieve a specific topology snapshot by ID.

    Args:
        topology_id: Unique identifier of the topology.
        topologies_service: Topologies service instance.
        include_graph: Include full graph data (nodes and edges).

    Returns:
        Complete topology data with optional graph information.

    Raises:
        HTTPException 404: Topology not found.
        HTTPException 403: Insufficient permissions.
    """
    topology = await topologies_service.get_topology(topology_id, include_graph=include_graph)
    return SuccessResponse(data=TopologyResponse(**topology))


@router.post(
    "/generate",
    response_model=SuccessResponse[TopologyResponse],
    status_code=201,
    summary="Generate Topology",
    description="Trigger generation of a new topology snapshot.",
    dependencies=[Depends(require_permission("topologies:create"))],
)
async def generate_topology(
    request: GenerateTopologyRequest,
    topologies_service: TopologiesServiceDep,
) -> SuccessResponse[TopologyResponse]:
    """Manually trigger generation of a new topology snapshot.

    Args:
        request: Generation options including mode.
        topologies_service: Topologies service instance.

    Returns:
        Newly generated topology data.

    Raises:
        HTTPException 400: Invalid generation request.
        HTTPException 403: Insufficient permissions.
    """
    topology = await topologies_service.generate_topology(request)
    return SuccessResponse(data=TopologyResponse(**topology))


@router.get(
    "/subgraph",
    response_model=SuccessResponse[SubgraphResponse],
    summary="Get Node Subgraph",
    description="Get a subgraph centered on a specific node with its immediate neighbors.",
    dependencies=[Depends(require_permission("topologies:read"))],
)
async def get_subgraph(
    topologies_service: TopologiesServiceDep,
    node_id: str = Query(..., alias="nodeId", description="The center node ID"),
    depth: int = Query(default=1, ge=1, le=3, description="Depth of neighbors to include"),
    include_services: bool = Query(default=True, alias="includeServices"),
    include_networks: bool = Query(default=True, alias="includeNetworks"),
) -> SuccessResponse[SubgraphResponse]:
    """Extract a subgraph centered on a specific node.

    Args:
        topologies_service: Topologies service instance.
        node_id: Center node for the subgraph.
        depth: Number of hops to include from center node.
        include_services: Include services running on nodes.
        include_networks: Include network connections.

    Returns:
        Subgraph containing the node and its neighbors.

    Raises:
        HTTPException 404: Node not found in current topology.
        HTTPException 403: Insufficient permissions.
    """
    result = await topologies_service.get_subgraph(
        node_id=node_id,
        depth=depth,
        include_services=include_services,
        include_networks=include_networks,
    )
    return SuccessResponse(data=SubgraphResponse(**result))
