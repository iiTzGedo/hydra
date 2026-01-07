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
    """List topologies with filters."""
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
    """Get the latest topology for a mode."""
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
    """Compare two topologies."""
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
    """Get a single topology by ID."""
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
    """Generate a new topology."""
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
    """Get a subgraph centered on a node."""
    result = await topologies_service.get_subgraph(
        node_id=node_id,
        depth=depth,
        include_services=include_services,
        include_networks=include_networks,
    )
    return SuccessResponse(data=SubgraphResponse(**result))
