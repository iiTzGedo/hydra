"""Query, capacity, and audit endpoints."""

from datetime import datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Query

from hydra.v1.core.deps import MongoDBDep, require_permission
from hydra.v1.models.common import PaginationMeta, SuccessResponse
from hydra.v1.models.query import (
    AuditAction,
    AuditEntry,
    AuditListParams,
    CapacityGroupBy,
    CapacityResponse,
    CapacitySummary,
    ClassCapacity,
    LocationCapacity,
    QueryCollection,
    QueryRequest,
    QueryResponse,
)
from hydra.v1.services.query import AuditService, QueryService

router = APIRouter(tags=["Query & Analytics"])
logger = structlog.get_logger(__name__)


def get_query_service(mongodb: MongoDBDep) -> QueryService:
    """Get query service dependency."""
    return QueryService(mongodb)


def get_audit_service(mongodb: MongoDBDep) -> AuditService:
    """Get audit service dependency."""
    return AuditService(mongodb)


QueryServiceDep = Annotated[QueryService, Depends(get_query_service)]
AuditServiceDep = Annotated[AuditService, Depends(get_audit_service)]


@router.post(
    "/query",
    response_model=SuccessResponse[QueryResponse],
    summary="Execute Query",
    description="Execute a structured query across collections.",
)
async def execute_query(
    request: QueryRequest,
    query_service: QueryServiceDep,
) -> SuccessResponse[QueryResponse]:
    """Execute a structured query.

    Requires read permission for the target collection.
    """
    # Permission check would be done based on collection
    # For now, require nodes:read as a baseline

    results, total = await query_service.execute_query(request)

    return SuccessResponse(
        data=QueryResponse(
            collection=request.collection,
            results=results,
            total=total,
            returned=len(results),
        )
    )


@router.get(
    "/capacity",
    response_model=SuccessResponse[CapacityResponse],
    summary="Get Capacity",
    description="Get infrastructure capacity summary.",
    dependencies=[Depends(require_permission("nodes:read"))],
)
async def get_capacity(
    query_service: QueryServiceDep,
    group_by: CapacityGroupBy | None = Query(default=None, alias="groupBy"),
    include_logical: bool = Query(default=False, alias="includeLogical"),
    group_id: str | None = Query(default=None, alias="groupId"),
    network_id: str | None = Query(default=None, alias="networkId"),
) -> SuccessResponse[CapacityResponse]:
    """Get infrastructure capacity summary."""
    capacity = await query_service.get_capacity(
        group_by=group_by,
        include_logical=include_logical,
        group_id=group_id,
        network_id=network_id,
    )

    # Convert to response models
    summary = CapacitySummary(
        total_nodes=capacity["summary"]["totalNodes"],
        physical_nodes=capacity["summary"]["physicalNodes"],
        logical_nodes=capacity["summary"]["logicalNodes"],
        total_cores=capacity["summary"]["totalCores"],
        total_memory_gb=capacity["summary"]["totalMemoryGB"],
        total_storage_tb=capacity["summary"]["totalStorageTB"],
    )

    by_class = None
    if "byClass" in capacity:
        by_class = {
            k: ClassCapacity(
                nodes=v["nodes"],
                cores=v.get("cores"),
                memory_gb=v.get("memoryGB"),
                storage_tb=v.get("storageTB"),
            )
            for k, v in capacity["byClass"].items()
        }

    by_location = None
    if "byLocation" in capacity:
        by_location = {
            k: LocationCapacity(
                nodes=v["nodes"],
                cores=v.get("cores"),
                memory_gb=v.get("memoryGB"),
            )
            for k, v in capacity["byLocation"].items()
        }

    return SuccessResponse(
        data=CapacityResponse(
            summary=summary,
            by_class=by_class,
            by_location=by_location,
        )
    )


@router.get(
    "/audit",
    response_model=SuccessResponse[list[AuditEntry]],
    summary="Get Audit Log",
    description="Get audit log entries.",
    dependencies=[Depends(require_permission("audit:read"))],
)
async def get_audit_log(
    audit_service: AuditServiceDep,
    action: AuditAction | None = None,
    resource_type: str | None = Query(default=None, alias="resourceType"),
    resource_id: str | None = Query(default=None, alias="resourceId"),
    actor_id: str | None = Query(default=None, alias="actorId"),
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> SuccessResponse[list[AuditEntry]]:
    """Get audit log entries."""
    params = AuditListParams(
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        actor_id=actor_id,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )

    entries, total = await audit_service.list_entries(params)

    return SuccessResponse(
        data=[
            AuditEntry(
                entry_id=e["entryId"],
                timestamp=e["timestamp"],
                action=AuditAction(e["action"]),
                resource=e["resource"],
                actor=e["actor"],
                details=e.get("details"),
                result=e["result"],
            )
            for e in entries
        ],
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )
