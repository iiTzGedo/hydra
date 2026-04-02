"""Query, capacity, and audit endpoints."""

from datetime import datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from hydra.api.v1.core.deps import MongoDBDep, get_current_user, require_permission
from hydra.api.v1.models.common import PaginationMeta, SuccessResponse
from hydra.api.v1.models.query import (
    AuditAction,
    AuditEntry,
    AuditListParams,
    CapacityGroupBy,
    CapacityResponse,
    CapacitySummary,
    ClassCapacity,
    LocationCapacity,
    QueryRequest,
    QueryResponse,
)
from hydra.api.v1.services.groups import GroupsService
from hydra.api.v1.services.query import AuditService, QueryService, log_audit

router = APIRouter(tags=["Query & Analytics"])
logger = structlog.get_logger(__name__)


def get_query_service(mongodb: MongoDBDep) -> QueryService:
    """Get query service dependency."""
    return QueryService(mongodb, groups_service=GroupsService(mongodb))


def get_audit_service(mongodb: MongoDBDep) -> AuditService:
    """Get audit service dependency."""
    return AuditService(mongodb)


QueryServiceDep = Annotated[QueryService, Depends(get_query_service)]
AuditServiceDep = Annotated[AuditService, Depends(get_audit_service)]


@router.post(
    "/query",
    response_model=SuccessResponse[QueryResponse],
    response_model_by_alias=True,
    summary="Execute Query",
    description="Execute a structured query across collections.",
    dependencies=[Depends(require_permission("query:read"))],
)
async def execute_query(
    request: QueryRequest,
    query_service: QueryServiceDep,
) -> SuccessResponse[QueryResponse]:
    """Execute a structured query against infrastructure data.

    Args:
        request: Query specification including collection, filters, and options.
        query_service: Query service instance.

    Returns:
        Query results with pagination metadata.

    Raises:
        HTTPException 400: Invalid query specification.
        HTTPException 403: Insufficient permissions for target collection.
    """
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
    response_model_by_alias=True,
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
    """Retrieve aggregated infrastructure capacity metrics.

    Args:
        query_service: Query service instance.
        group_by: Group capacity by class or location.
        include_logical: Include logical nodes (VMs, containers) in capacity.
        group_id: Filter to nodes in a specific group.
        network_id: Filter to nodes in a specific network.

    Returns:
        Capacity summary with optional grouping breakdown.

    Raises:
        HTTPException 403: Insufficient permissions.
    """
    capacity = await query_service.get_capacity(
        group_by=group_by,
        include_logical=include_logical,
        group_id=group_id,
        network_id=network_id,
    )

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
    response_model_by_alias=True,
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
    """Retrieve audit log entries for compliance and troubleshooting.

    Args:
        audit_service: Audit service instance.
        action: Filter by audit action type.
        resource_type: Filter by resource type (node, service, user, etc.).
        resource_id: Filter by specific resource ID.
        actor_id: Filter by actor (user or agent) ID.
        since: Only include entries after this timestamp.
        until: Only include entries before this timestamp.
        limit: Maximum number of results to return.
        offset: Number of results to skip.

    Returns:
        Paginated list of audit entries.

    Raises:
        HTTPException 403: Insufficient permissions.
    """
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


@router.delete(
    "/audit",
    response_model=SuccessResponse[dict],
    response_model_by_alias=True,
    summary="Delete Audit Entries",
    description="Delete audit log entries within a time window. Admin only.",
    dependencies=[Depends(require_permission("audit:delete"))],
)
async def delete_audit_entries(
    audit_service: AuditServiceDep,
    request: Request,
    since: datetime = Query(..., description="Start of time window (inclusive)"),
    until: datetime = Query(..., description="End of time window (inclusive)"),
    current_user: dict = Depends(get_current_user),
) -> SuccessResponse[dict]:
    """Delete audit log entries within a specific time window.

    Only admins with audit:delete permission can perform this operation.
    The deletion itself is audited.

    Args:
        audit_service: Audit service instance.
        request: FastAPI request for IP extraction.
        since: Start of the deletion window.
        until: End of the deletion window.
        current_user: Authenticated user.

    Returns:
        Number of entries deleted.

    Raises:
        HTTPException 400: Invalid time window.
        HTTPException 403: Insufficient permissions.
    """
    if since >= until:
        raise HTTPException(
            status_code=400,
            detail="'since' must be before 'until'",
        )

    deleted_count = await audit_service.delete_entries_by_window(since, until)

    # Self-audit the deletion
    client_ip = request.client.host if request.client else None
    await log_audit(
        action=AuditAction.DELETE,
        resource_type="audit_log",
        resource_id=f"{since.isoformat()}/{until.isoformat()}",
        actor_type="user",
        actor_id=current_user.get("userId", current_user.get("username", "unknown")),
        success=True,
        details={
            "since": since.isoformat(),
            "until": until.isoformat(),
            "deletedCount": deleted_count,
        },
        ip=client_ip,
    )

    return SuccessResponse(
        data={
            "deletedCount": deleted_count,
            "since": since.isoformat(),
            "until": until.isoformat(),
        }
    )
