"""Time Machine endpoints for historical state queries."""

from datetime import datetime, timedelta, timezone
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Query

from hydra.v1.core.deps import MongoDBDep, require_permission
from hydra.v1.models.common import PaginationMeta, SuccessResponse
from hydra.v1.models.timemachine import (
    NodeTimeMachineResponse,
    TimelineEventType,
    TimelineResponse,
    TopologyTimeMachineResponse,
)
from hydra.v1.models.topologies import TopologyMode
from hydra.v1.services.timemachine import TimeMachineService

router = APIRouter(prefix="/timemachine", tags=["Time Machine"])
logger = structlog.get_logger(__name__)


def get_timemachine_service(mongodb: MongoDBDep) -> TimeMachineService:
    """Get time machine service dependency."""
    return TimeMachineService(mongodb)


TimeMachineServiceDep = Annotated[TimeMachineService, Depends(get_timemachine_service)]


@router.get(
    "/node/{node_id}",
    response_model=SuccessResponse[NodeTimeMachineResponse],
    summary="Get Node State at Time",
    description="Reconstruct a node's state at a specific point in time.",
    dependencies=[Depends(require_permission("nodes:read")), Depends(require_permission("profiles:read"))],
)
async def get_node_state_at(
    node_id: str,
    timemachine_service: TimeMachineServiceDep,
    timestamp: datetime = Query(..., description="Point in time to query state at"),
    sections: list[str] | None = Query(
        default=None,
        description="Profile sections to include (hardware, network, storage, software)",
    ),
) -> SuccessResponse[NodeTimeMachineResponse]:
    """Get node state at a specific time."""
    result = await timemachine_service.get_node_state_at(node_id, timestamp, sections)
    return SuccessResponse(data=NodeTimeMachineResponse(**result))


@router.get(
    "/topology",
    response_model=SuccessResponse[TopologyTimeMachineResponse],
    summary="Get Topology at Time",
    description="Get the topology that was valid at a specific point in time.",
    dependencies=[Depends(require_permission("topologies:read"))],
)
async def get_topology_at(
    timemachine_service: TimeMachineServiceDep,
    mode: TopologyMode = Query(...),
    timestamp: datetime = Query(..., description="Point in time to query topology at"),
    include_graph: bool = Query(default=True, alias="includeGraph"),
) -> SuccessResponse[TopologyTimeMachineResponse]:
    """Get topology valid at a specific time."""
    result = await timemachine_service.get_topology_at(mode, timestamp, include_graph)
    return SuccessResponse(data=TopologyTimeMachineResponse(**result))


@router.get(
    "/timeline",
    response_model=SuccessResponse[TimelineResponse],
    summary="Get Timeline",
    description="Get a timeline of infrastructure events within a time range.",
    dependencies=[Depends(require_permission("nodes:read"))],
)
async def get_timeline(
    timemachine_service: TimeMachineServiceDep,
    since: datetime | None = Query(
        default=None,
        description="Start of time range (defaults to 24 hours ago)",
    ),
    until: datetime | None = Query(
        default=None,
        description="End of time range (defaults to now)",
    ),
    node_id: str | None = Query(default=None, alias="nodeId"),
    event_types: list[TimelineEventType] | None = Query(
        default=None,
        alias="eventTypes",
        description="Filter by event types",
    ),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> SuccessResponse[TimelineResponse]:
    """Get timeline of infrastructure events."""
    # Default time range
    now = datetime.now(timezone.utc)
    if until is None:
        until = now
    if since is None:
        since = until - timedelta(hours=24)

    events, total = await timemachine_service.get_timeline(
        since=since,
        until=until,
        node_id=node_id,
        event_types=event_types,
        limit=limit,
        offset=offset,
    )

    return SuccessResponse(
        data=TimelineResponse(
            since=since,
            until=until,
            events=events,
            total=total,
        ),
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )
