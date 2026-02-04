"""Notification REST endpoints."""

import asyncio
import json
from datetime import datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

from hydra.api.v1.core.deps import CurrentUser, MongoDBDep, RedisDep, require_permission
from hydra.api.v1.core.exceptions import NotFoundError, ValidationError
from hydra.api.v1.models.common import PaginationMeta, SuccessResponse
from hydra.api.v1.models.notifications import (
    NOTIFICATION_CHANNEL,
    NotificationBulkActionRequest,
    NotificationBulkActionResponse,
    NotificationResponse,
    NotificationStatsResponse,
)
from hydra.api.v1.models.settings import NotificationSettings
from hydra.api.v1.models.query import AuditAction
from hydra.api.v1.services.notifications import NotificationService, should_deliver
from hydra.api.v1.services.query import log_audit
from hydra.api.v1.routers.chat_ws import get_user_from_token
from hydra.api.v1.core.role_utils import get_active_temporary_roles
from hydra.db.mongodb import get_mongodb, MongoDB
from hydra.db.redis import get_redis, RedisClient

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


async def _load_user_context(
    mongodb: MongoDB,
    user_payload: dict,
) -> tuple[str, list[str], NotificationSettings]:
    """Load user roles and notification settings from MongoDB."""
    user_id = user_payload["sub"]
    user_doc = await mongodb.users.find_one(
        {"userId": user_id},
        {"role": 1, "roles": 1, "temporaryRoles": 1},
    )

    roles: list[str] = []
    if user_doc:
        role = user_doc.get("role")
        if role:
            roles.append(role)
        roles.extend(user_doc.get("roles", []) or [])
        temp_roles = get_active_temporary_roles(user_doc.get("temporaryRoles", []))
        roles.extend([r.get("role") for r in temp_roles if r.get("role")])
    else:
        roles = user_payload.get("roles", []) or []
        role = user_payload.get("role")
        if role and role not in roles:
            roles = [role] + roles

    settings_doc = await mongodb.user_settings.find_one(
        {"userId": user_id},
        {"notifications": 1, "_id": 0},
    )
    settings = (
        NotificationSettings.model_validate(settings_doc["notifications"])
        if settings_doc and settings_doc.get("notifications") is not None
        else NotificationSettings()
    )

    return user_id, roles, settings


async def _notifications_ws_listener(
    websocket: WebSocket,
    redis_client: RedisClient,
    user_id: str,
    user_roles: list[str],
    settings: NotificationSettings,
) -> None:
    """Subscribe to Redis notification channel and push matching notifications."""
    pubsub = None
    try:
        pubsub = await redis_client.subscribe(NOTIFICATION_CHANNEL)
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue

            try:
                data = json.loads(message["data"])
            except (json.JSONDecodeError, TypeError):
                continue

            target_roles = data.get("targetRoles", [])
            target_user_id = data.get("targetUserId")

            user_targeted = target_user_id == user_id if target_user_id else False
            role_match = bool(set(user_roles) & set(target_roles)) if target_roles else False
            if not user_targeted and not role_match:
                continue

            if not should_deliver(settings, data, "browser"):
                continue

            try:
                await websocket.send_json({
                    "type": "notification",
                    "data": data,
                })
            except Exception:
                break
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.debug("notifications_ws_listener_stopped", user_id=user_id, exc_info=True)
    finally:
        if pubsub:
            try:
                await pubsub.unsubscribe(NOTIFICATION_CHANNEL)
                await pubsub.close()
            except Exception:
                pass


async def _notifications_ws_receiver(websocket: WebSocket) -> None:
    """Handle incoming WebSocket messages (ping/pong)."""
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


# --------------------------------------------------------------------------
# List
# --------------------------------------------------------------------------


@router.get(
    "",
    response_model=SuccessResponse[list[NotificationResponse]],
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
    summary="Delete Notification",
    description="Delete a notification (admin only).",
    dependencies=[Depends(require_permission("notifications:manage"))],
)
async def delete_notification(
    notification_id: str,
    notification_service: NotificationServiceDep,
    current_user: CurrentUser,
) -> SuccessResponse[dict]:
    """Delete a notification and its read state.

    Args:
        notification_id: Notification ID.
        notification_service: Notification service instance.
        current_user: Authenticated user.

    Returns:
        Deletion confirmation.

    Raises:
        NotFoundError: If notification not found.
    """
    deleted = await notification_service.delete_notification(notification_id)
    if not deleted:
        raise NotFoundError("notification", notification_id)
    user_id = current_user["user_id"]
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
# Bulk: Acknowledge All
# --------------------------------------------------------------------------


@router.post(
    "/acknowledge-all",
    response_model=SuccessResponse[NotificationBulkActionResponse],
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


# --------------------------------------------------------------------------
# WebSocket: Notifications
# --------------------------------------------------------------------------


@router.websocket("/ws")
async def notifications_ws(
    websocket: WebSocket,
    mongodb: MongoDB = Depends(get_mongodb),
):
    """WebSocket endpoint for real-time notifications."""
    user = await get_user_from_token(websocket)
    if not user:
        await websocket.close(code=4001, reason="Unauthorized")
        return
    if user.get("sub_type") == "agent":
        await websocket.close(code=4003, reason="Agents cannot subscribe to notifications")
        return

    await websocket.accept()

    user_id, user_roles, settings = await _load_user_context(mongodb, user)
    redis_client = get_redis()

    listener_task = asyncio.create_task(
        _notifications_ws_listener(websocket, redis_client, user_id, user_roles, settings)
    )
    receiver_task = asyncio.create_task(_notifications_ws_receiver(websocket))

    done, pending = await asyncio.wait(
        {listener_task, receiver_task},
        return_when=asyncio.FIRST_COMPLETED,
    )

    for task in pending:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
