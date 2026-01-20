"""Time Machine endpoints for historical state queries."""

from datetime import datetime, timedelta, timezone
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Query

from hydra.api.v1.core.deps import MongoDBDep, require_permission
from hydra.api.v1.models.common import PaginationMeta, SuccessResponse
from hydra.api.v1.models.timemachine import (
    NodeTimeMachineResponse,
    TimelineEventType,
    TimelineResponse,
    TopologyTimeMachineResponse,
)
from hydra.api.v1.models.topologies import TopologyMode
from hydra.api.v1.services.timemachine import TimeMachineService

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
    """Reconstruct a node's complete state at a historical point in time.

    Args:
        node_id: Unique identifier of the node.
        timemachine_service: Time machine service instance.
        timestamp: Point in time to reconstruct state for.
        sections: Specific profile sections to include in response.

    Returns:
        Node state as it existed at the specified timestamp.

    Raises:
        HTTPException 404: Node not found or no profile exists before timestamp.
        HTTPException 403: Insufficient permissions.
    """
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
    """Retrieve the infrastructure topology valid at a specific timestamp.

    Args:
        timemachine_service: Time machine service instance.
        mode: Topology mode (infrastructure or network).
        timestamp: Point in time to query.
        include_graph: Include full graph data.

    Returns:
        Topology that was valid at the specified timestamp.

    Raises:
        HTTPException 404: No topology exists that covers the specified timestamp.
        HTTPException 403: Insufficient permissions.
    """
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
    """Retrieve a timeline of infrastructure events within a time range.

    Args:
        timemachine_service: Time machine service instance.
        since: Start of time range (defaults to 24 hours ago).
        until: End of time range (defaults to now).
        node_id: Filter events for a specific node.
        event_types: Filter by event types (profile_submitted, node_registered, etc.).
        limit: Maximum number of events to return.
        offset: Number of events to skip.

    Returns:
        Timeline of events with pagination metadata.

    Raises:
        HTTPException 403: Insufficient permissions.
    """
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
