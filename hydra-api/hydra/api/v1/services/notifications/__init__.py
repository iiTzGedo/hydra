"""Notification service — emission, deduplication, auto-resolution, CRUD.

Re-exports all public symbols so that ``from hydra.api.v1.services.notifications import ...``
continues to work unchanged.
"""

from typing import Any, cast

import structlog

from hydra.api.v1.models.notifications import (
    NotificationActor,
    NotificationSource,
    NotificationType,
)
from hydra.api.v1.services.notifications.preferences import (
    ACKNOWLEDGE_MIN_TIER,
    CATEGORY_MAP,
    RESOLVE_MIN_TIER,
    is_quiet_hours,
    resolve_category,
    should_deliver,
)
from hydra.api.v1.services.notifications.service import NotificationService
from hydra.db.mongodb import MongoDB
from hydra.db.redis import RedisClient

logger = structlog.get_logger(__name__)
_UNSET = object()

__all__ = [
    # Class
    "NotificationService",
    # Preferences / constants
    "ACKNOWLEDGE_MIN_TIER",
    "RESOLVE_MIN_TIER",
    "CATEGORY_MAP",
    "resolve_category",
    "is_quiet_hours",
    "should_deliver",
    # Module-level helper
    "emit_notification",
]


# ---------------------------------------------------------------------------
# Module-level helper for fire-and-forget emission from services
# ---------------------------------------------------------------------------


async def emit_notification(
    notification_type: NotificationType,
    source: NotificationSource,
    title: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
    links: list[dict[str, Any]] | None = None,
    actor: NotificationActor | None = None,
    target_user_id: str | None = None,
    target_roles: list[str] | None = None,
    correlation_id: str | None = None,
    audit_entry_id: str | None = None,
    group_key: str | None = None,
    mongodb: MongoDB | object = _UNSET,
    redis: RedisClient | None | object = _UNSET,
    resolve_dependencies: bool = True,
) -> str | None:
    """Convenience function to emit a notification from any service.

    Uses injected MongoDB/Redis dependencies when provided, otherwise falls
    back to the process singletons, then calls NotificationService.emit().
    Safe to call from anywhere — never raises.
    """
    try:
        resolved_mongodb = mongodb
        resolved_redis = redis

        if resolve_dependencies:
            from hydra.db.mongodb import get_mongodb
            from hydra.db.redis import get_redis

            if resolved_mongodb is _UNSET:
                resolved_mongodb = get_mongodb()
            if resolved_redis is _UNSET:
                resolved_redis = get_redis()

        if resolved_mongodb is _UNSET:
            raise RuntimeError("MongoDB dependency is required to emit notifications")
        if resolved_redis is _UNSET:
            resolved_redis = None

        service = NotificationService(
            cast(MongoDB, resolved_mongodb),
            cast(RedisClient | None, resolved_redis),
        )
        return await service.emit(
            notification_type=notification_type,
            source=source,
            title=title,
            message=message,
            details=details,
            links=links,
            actor=actor,
            target_user_id=target_user_id,
            target_roles=target_roles,
            correlation_id=correlation_id,
            audit_entry_id=audit_entry_id,
            group_key=group_key,
        )
    except Exception:
        logger.exception(
            "emit_notification_helper_failed",
            notification_type=notification_type.value,
        )
        return None
