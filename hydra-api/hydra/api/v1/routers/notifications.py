"""Notification REST endpoints."""

from datetime import datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Query

from hydra.api.v1.core.deps import CurrentUser, MongoDBDep, RedisDep, require_permission
from hydra.api.v1.core.exceptions import NotFoundError, ValidationError
from hydra.api.v1.models.common import PaginationMeta, SuccessResponse
from hydra.api.v1.models.notifications import (
    NotificationBulkActionRequest,
    NotificationBulkActionResponse,
    NotificationBulkDeleteRequest,
    NotificationResponse,
    NotificationStatsResponse,
)
from hydra.api.v1.models.query import AuditAction
from hydra.api.v1.services.notifications import NotificationService
from hydra.api.v1.services.query import log_audit

router = APIRouter(prefix="/notifications", tags=["Notifications"])
logger = structlog.get_logger(__name__)


def get_notification_service(mongodb: MongoDBDep, redis: RedisDep) -> NotificationService:
    """Get notification service dependency."""
    return NotificationService(mongodb, redis)


NotificationServiceDep = Annotated[NotificationService, Depends(get_notification_service)]


def _user_roles(current_user: dict) -> list[str]:
    """Extract role list from current user dict."""
    role = current_user.get("role", "")
    roles = current_user.get("roles", [])
    if role and role not in roles:
        roles = [role] + roles
    return roles


def _has_permission(current_user: dict, permission: str) -> bool:
    """Check if a user has a specific permission."""
    perms = current_user.get("permissions", [])
    if "*:*" in perms:
        return True
    if permission in perms:
        return True
    resource, _ = permission.split(":", 1) if ":" in permission else (permission, "*")
    return f"{resource}:*" in perms


# --------------------------------------------------------------------------
# List
# --------------------------------------------------------------------------


@router.get(
    "",
    response_model=SuccessResponse[list[NotificationResponse]],
    response_model_by_alias=True,
    summary="List Notifications",
    description="List notifications visible to the current user with optional filters.",
    dependencies=[Depends(require_permission("notifications:read"))],
)
async def list_notifications(
    notification_service: NotificationServiceDep,
    current_user: CurrentUser,
    tier: int | None = Query(default=None, ge=1, le=5, description="Exact tier filter"),
    tier_min: int | None = Query(default=None, ge=1, le=5, alias="tierMin", description="Minimum tier (inclusive)"),
    tier_max: int | None = Query(default=None, ge=1, le=5, alias="tierMax", description="Maximum tier (inclusive)"),
    status: str | None = Query(default=None, description="Status filter: active, resolved, expired"),
    read: bool | None = Query(default=None, description="Filter by read state"),
    acknowledged: bool | None = Query(default=None, description="Filter by acknowledged state"),
    source: str | None = Query(default=None, description="Source component filter"),
    node_id: str | None = Query(default=None, alias="nodeId", description="Source node filter"),
    notification_type: str | None = Query(default=None, alias="type", description="Notification type filter"),
    since: datetime | None = Query(default=None, description="Created after (ISO 8601)"),
    until: datetime | None = Query(default=None, description="Created before (ISO 8601)"),
    limit: int = Query(default=50, ge=1, le=200, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
) -> SuccessResponse[list[NotificationResponse]]:
    """List notifications for the current user.

    Args:
        notification_service: Notification service instance.
        current_user: Authenticated user.
        tier: Exact tier filter (1-5).
        tier_min: Minimum tier inclusive.
        status: Lifecycle status filter.
        read: Per-user read state filter.
        source: Source component filter.
        node_id: Source node filter.
        notification_type: Notification type filter.
        since: Created after timestamp.
        until: Created before timestamp.
        limit: Page size (default 50, max 200).
        offset: Pagination offset.

    Returns:
        Paginated list of notifications with read state.
    """
    user_id = current_user["user_id"]
    roles = _user_roles(current_user)

    notifications, total = await notification_service.list_notifications(
        user_id=user_id,
        user_roles=roles,
        tier=tier,
        tier_min=tier_min,
        tier_max=tier_max,
        status=status,
        read=read,
        acknowledged=acknowledged,
        source=source,
        node_id=node_id,
        notification_type=notification_type,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )

    return SuccessResponse(
        data=[NotificationResponse(**n) for n in notifications],
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


# --------------------------------------------------------------------------
# Stats
# --------------------------------------------------------------------------


@router.get(
    "/stats",
    response_model=SuccessResponse[NotificationStatsResponse],
    response_model_by_alias=True,
    summary="Notification Stats",
    description="Get aggregated notification counts for the current user.",
    dependencies=[Depends(require_permission("notifications:read"))],
)
async def get_notification_stats(
    notification_service: NotificationServiceDep,
    current_user: CurrentUser,
) -> SuccessResponse[NotificationStatsResponse]:
    """Get notification statistics.

    Args:
        notification_service: Notification service instance.
        current_user: Authenticated user.

    Returns:
        Aggregated counts by tier, status, and source.
    """
    user_id = current_user["user_id"]
    roles = _user_roles(current_user)
    stats = await notification_service.get_stats(user_id, roles)
    return SuccessResponse(data=NotificationStatsResponse(**stats))


# --------------------------------------------------------------------------
# Detail
# --------------------------------------------------------------------------


@router.get(
    "/{notification_id}",
    response_model=SuccessResponse[NotificationResponse],
    response_model_by_alias=True,
    summary="Get Notification",
    description="Get a single notification by ID.",
    dependencies=[Depends(require_permission("notifications:read"))],
)
async def get_notification(
    notification_id: str,
    notification_service: NotificationServiceDep,
    current_user: CurrentUser,
) -> SuccessResponse[NotificationResponse]:
    """Get a single notification with per-user read state.

    Args:
        notification_id: Notification ID.
        notification_service: Notification service instance.
        current_user: Authenticated user.

    Returns:
        Notification detail.

    Raises:
        NotFoundError: If notification does not exist.
    """
    user_id = current_user["user_id"]
    doc = await notification_service.get_notification(notification_id, user_id)
    if doc is None:
        raise NotFoundError("notification", notification_id)
    return SuccessResponse(data=NotificationResponse(**doc))


# --------------------------------------------------------------------------
# Mark Read (per-user)
# --------------------------------------------------------------------------


@router.patch(
    "/{notification_id}/read",
    response_model=SuccessResponse[dict],
    response_model_by_alias=True,
    summary="Mark Read",
    description="Mark a notification as read for the current user.",
    dependencies=[Depends(require_permission("notifications:read"))],
)
async def mark_read(
    notification_id: str,
    notification_service: NotificationServiceDep,
    current_user: CurrentUser,
) -> SuccessResponse[dict]:
    """Mark a notification as read.

    Args:
        notification_id: Notification ID.
        notification_service: Notification service instance.
        current_user: Authenticated user.

    Returns:
        Success confirmation.
    """
    user_id = current_user["user_id"]
    await notification_service.mark_read(notification_id, user_id)
    await log_audit(
        action=AuditAction.UPDATE,
        resource_type="notification",
        resource_id=notification_id,
        actor_type="user",
        actor_id=user_id,
        details={"action": "mark_read"},
    )
    return SuccessResponse(data={"notificationId": notification_id, "read": True})


# --------------------------------------------------------------------------
# Acknowledge
# --------------------------------------------------------------------------


@router.patch(
    "/{notification_id}/acknowledge",
    response_model=SuccessResponse[NotificationResponse],
    response_model_by_alias=True,
    summary="Acknowledge Notification",
    description="Acknowledge a notification (marks it as seen and handled).",
    dependencies=[Depends(require_permission("notifications:write"))],
)
async def acknowledge_notification(
    notification_id: str,
    notification_service: NotificationServiceDep,
    current_user: CurrentUser,
) -> SuccessResponse[NotificationResponse]:
    """Acknowledge a notification (tier 3+ only).

    Args:
        notification_id: Notification ID.
        notification_service: Notification service instance.
        current_user: Authenticated user.

    Returns:
        Updated notification.

    Raises:
        NotFoundError: If notification not found or already acknowledged.
        ValidationError: If notification tier is below acknowledge threshold.
    """
    user_id = current_user["user_id"]

    # Check tier eligibility before attempting acknowledge
    from hydra.api.v1.services.notifications import ACKNOWLEDGE_MIN_TIER
    raw = await notification_service.get_notification(notification_id, user_id)
    if raw is None:
        raise NotFoundError("notification", notification_id)
    if raw.get("tier", 0) < ACKNOWLEDGE_MIN_TIER:
        raise ValidationError(
            "Notifications at this level cannot be acknowledged",
            details={"notificationId": notification_id, "tier": raw.get("tier")},
        )

    doc = await notification_service.acknowledge(notification_id, user_id)
    if doc is None:
        raise NotFoundError("notification", notification_id)
    await log_audit(
        action=AuditAction.ACKNOWLEDGE,
        resource_type="notification",
        resource_id=notification_id,
        actor_type="user",
        actor_id=user_id,
    )
    return SuccessResponse(data=NotificationResponse(**doc))


# --------------------------------------------------------------------------
# Resolve
# --------------------------------------------------------------------------


@router.patch(
    "/{notification_id}/resolve",
    response_model=SuccessResponse[NotificationResponse],
    response_model_by_alias=True,
    summary="Resolve Notification",
    description="Manually resolve a notification.",
    dependencies=[Depends(require_permission("notifications:write"))],
)
async def resolve_notification(
    notification_id: str,
    notification_service: NotificationServiceDep,
    current_user: CurrentUser,
) -> SuccessResponse[NotificationResponse]:
    """Manually resolve a notification (tier 4+ only).

    Args:
        notification_id: Notification ID.
        notification_service: Notification service instance.
        current_user: Authenticated user.

    Returns:
        Updated notification.

    Raises:
        NotFoundError: If notification not found or already resolved.
        ValidationError: If notification tier is below resolve threshold.
    """
    user_id = current_user["user_id"]

    # Check tier eligibility before attempting resolve
    from hydra.api.v1.services.notifications import RESOLVE_MIN_TIER
    raw = await notification_service.get_notification(notification_id, user_id)
    if raw is None:
        raise NotFoundError("notification", notification_id)
    if raw.get("tier", 0) < RESOLVE_MIN_TIER:
        raise ValidationError(
            "Notifications at this level cannot be resolved",
            details={"notificationId": notification_id, "tier": raw.get("tier")},
        )

    doc = await notification_service.resolve(notification_id, user_id)
    if doc is None:
        raise NotFoundError("notification", notification_id)
    await log_audit(
        action=AuditAction.RESOLVE,
        resource_type="notification",
        resource_id=notification_id,
        actor_type="user",
        actor_id=user_id,
    )
    return SuccessResponse(data=NotificationResponse(**doc))


# --------------------------------------------------------------------------
# Delete
# --------------------------------------------------------------------------


@router.delete(
    "/{notification_id}",
    response_model=SuccessResponse[dict],
    response_model_by_alias=True,
    summary="Delete Notification",
    description="Delete a notification. Users can delete their own notifications; write/manage users can delete any visible notification.",
    dependencies=[Depends(require_permission("notifications:read"))],
)
async def delete_notification(
    notification_id: str,
    notification_service: NotificationServiceDep,
    current_user: CurrentUser,
) -> SuccessResponse[dict]:
    """Delete a notification and its read state.

    Permission model:
    - notifications:manage: unrestricted delete
    - notifications:write: can delete any visible notification
    - notifications:read: can delete own notifications (targetUserId == user_id)

    Args:
        notification_id: Notification ID.
        notification_service: Notification service instance.
        current_user: Authenticated user.

    Returns:
        Deletion confirmation.

    Raises:
        NotFoundError: If notification not found or insufficient permissions.
    """
    user_id = current_user["user_id"]
    roles = _user_roles(current_user)
    has_write = _has_permission(current_user, "notifications:write")
    has_manage = _has_permission(current_user, "notifications:manage")

    deleted = await notification_service.delete_notification(
        notification_id,
        user_id=user_id,
        user_roles=roles,
        has_write=has_write,
        has_manage=has_manage,
    )
    if not deleted:
        raise NotFoundError("notification", notification_id)
    await log_audit(
        action=AuditAction.DELETE,
        resource_type="notification",
        resource_id=notification_id,
        actor_type="user",
        actor_id=user_id,
    )
    return SuccessResponse(data={"notificationId": notification_id, "deleted": True})


# --------------------------------------------------------------------------
# Bulk: Read All
# --------------------------------------------------------------------------


@router.post(
    "/read-all",
    response_model=SuccessResponse[NotificationBulkActionResponse],
    response_model_by_alias=True,
    summary="Mark All Read",
    description="Mark all matching notifications as read for the current user.",
    dependencies=[Depends(require_permission("notifications:read"))],
)
async def mark_all_read(
    notification_service: NotificationServiceDep,
    current_user: CurrentUser,
    body: NotificationBulkActionRequest | None = None,
) -> SuccessResponse[NotificationBulkActionResponse]:
    """Mark all matching notifications as read.

    Args:
        notification_service: Notification service instance.
        current_user: Authenticated user.
        body: Optional filters for scoping the bulk action.

    Returns:
        Number of notifications affected.
    """
    user_id = current_user["user_id"]
    roles = _user_roles(current_user)
    filters = body or NotificationBulkActionRequest()

    count = await notification_service.mark_all_read(
        user_id=user_id,
        user_roles=roles,
        tier=filters.tier,
        tier_min=filters.tier_min,
        status=filters.status.value if filters.status else None,
        source=filters.source.value if filters.source else None,
        node_id=filters.node_id,
    )
    if count > 0:
        await log_audit(
            action=AuditAction.UPDATE,
            resource_type="notification",
            resource_id="bulk",
            actor_type="user",
            actor_id=user_id,
            details={"action": "mark_all_read", "affectedCount": count},
        )
    return SuccessResponse(data=NotificationBulkActionResponse(affected_count=count))


# --------------------------------------------------------------------------
# Bulk: Delete Many
# --------------------------------------------------------------------------


@router.post(
    "/delete-many",
    response_model=SuccessResponse[NotificationBulkActionResponse],
    response_model_by_alias=True,
    summary="Bulk Delete Notifications",
    description="Delete multiple notifications by IDs or filter criteria.",
    dependencies=[Depends(require_permission("notifications:read"))],
)
async def delete_many_notifications(
    notification_service: NotificationServiceDep,
    current_user: CurrentUser,
    body: NotificationBulkDeleteRequest,
) -> SuccessResponse[NotificationBulkActionResponse]:
    """Bulk delete notifications.

    Permission model:
    - notifications:manage: unrestricted delete
    - notifications:write: can delete any visible notification
    - notifications:read: can delete own notifications (targetUserId == user_id)

    Args:
        notification_service: Notification service instance.
        current_user: Authenticated user.
        body: Delete criteria (IDs, status, tier, before date).

    Returns:
        Number of notifications deleted.
    """
    user_id = current_user["user_id"]
    roles = _user_roles(current_user)
    has_write = _has_permission(current_user, "notifications:write")
    has_manage = _has_permission(current_user, "notifications:manage")

    count = await notification_service.delete_many(
        user_id=user_id,
        user_roles=roles,
        notification_ids=body.notification_ids,
        status=body.status.value if body.status else None,
        tier=body.tier,
        before=body.before,
        has_write=has_write,
        has_manage=has_manage,
    )
    if count > 0:
        await log_audit(
            action=AuditAction.DELETE,
            resource_type="notification",
            resource_id="bulk",
            actor_type="user",
            actor_id=user_id,
            details={"action": "delete_many", "affectedCount": count},
        )
    return SuccessResponse(data=NotificationBulkActionResponse(affected_count=count))


# --------------------------------------------------------------------------
# Bulk: Acknowledge All
# --------------------------------------------------------------------------


@router.post(
    "/acknowledge-all",
    response_model=SuccessResponse[NotificationBulkActionResponse],
    response_model_by_alias=True,
    summary="Acknowledge All",
    description="Acknowledge all matching notifications.",
    dependencies=[Depends(require_permission("notifications:write"))],
)
async def acknowledge_all(
    notification_service: NotificationServiceDep,
    current_user: CurrentUser,
    body: NotificationBulkActionRequest | None = None,
) -> SuccessResponse[NotificationBulkActionResponse]:
    """Acknowledge all matching notifications.

    Args:
        notification_service: Notification service instance.
        current_user: Authenticated user.
        body: Optional filters for scoping the bulk action.

    Returns:
        Number of notifications affected.
    """
    user_id = current_user["user_id"]
    roles = _user_roles(current_user)
    filters = body or NotificationBulkActionRequest()

    count = await notification_service.acknowledge_all(
        user_id=user_id,
        user_roles=roles,
        tier=filters.tier,
        tier_min=filters.tier_min,
        status=filters.status.value if filters.status else None,
        source=filters.source.value if filters.source else None,
        node_id=filters.node_id,
    )
    if count > 0:
        await log_audit(
            action=AuditAction.ACKNOWLEDGE,
            resource_type="notification",
            resource_id="bulk",
            actor_type="user",
            actor_id=user_id,
            details={"action": "acknowledge_all", "affectedCount": count},
        )
    return SuccessResponse(data=NotificationBulkActionResponse(affected_count=count))
