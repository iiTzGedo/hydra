"""Notification emission — deduplication, auto-resolution, document creation."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog

from hydra.api.v1.models.notifications import (
    AUTO_RESOLVE_MAP,
    DEDUP_WINDOW,
    DEFAULT_TARGET_ROLES,
    RESOLVED_RETENTION,
    TIER_LABELS,
    TIER_MAP,
    TTL_MAP,
    ActorType,
    NotificationActor,
    NotificationSource,
    NotificationStatus,
    NotificationType,
    build_group_key,
)
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)


def _generate_notification_id() -> str:
    """Generate a unique notification ID."""
    return f"ntf-{uuid4().hex[:8]}"


class EmissionMixin:
    """Mixin providing notification emission, deduplication, and auto-resolution."""
    db: MongoDB

    async def _publish_to_redis(self, doc: dict[str, Any]) -> None: ...

    async def _deliver_email(self, doc: dict[str, Any]) -> None: ...


    async def emit(
        self,
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
    ) -> str | None:
        """Emit a notification — best-effort, never raises.

        Returns the notification ID on success, ``None`` on failure or dedup.
        """
        try:
            return await self._emit_inner(
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
                "notification_emit_failed",
                notification_type=notification_type.value,
                source_component=source.component.value,
            )
            return None

    async def _emit_inner(
        self,
        notification_type: NotificationType,
        source: NotificationSource,
        title: str,
        message: str,
        details: dict[str, Any] | None,
        links: list[dict[str, Any]] | None,
        actor: NotificationActor | None,
        target_user_id: str | None,
        target_roles: list[str] | None,
        correlation_id: str | None,
        audit_entry_id: str | None,
        group_key: str | None,
    ) -> str | None:
        now = datetime.now(UTC)
        tier = TIER_MAP.get(notification_type, 3)
        tier_label = TIER_LABELS[tier].value
        group_key = group_key or build_group_key(notification_type, source, details)

        # Resolve defaults
        if actor is None:
            actor = NotificationActor(type=ActorType.SYSTEM, id="system")
        if target_roles is None:
            if target_user_id is not None:
                target_roles = []
            else:
                target_roles = DEFAULT_TARGET_ROLES.get(tier, ["admin", "operator"])

        # 1. Check auto-resolution: does this event resolve outstanding ones?
        await self._check_auto_resolve(notification_type, source, now)

        # 2. Deduplicate: merge into existing if within window
        dedup_result = await self._deduplicate(group_key, tier, now)
        if dedup_result is not None:
            # Existing notification was updated instead of creating new
            await self._publish_to_redis(dedup_result)
            return dedup_result["notificationId"]  # type: ignore[no-any-return]

        # 3. Compute TTL
        expires_at = self._compute_expiry(tier, now)

        # 4. Build document
        notification_id = _generate_notification_id()
        doc: dict[str, Any] = {
            "notificationId": notification_id,
            "type": notification_type.value,
            "tier": tier,
            "tierLabel": tier_label,
            "source": source.model_dump(by_alias=True, exclude_none=True),
            "title": title[:120],
            "message": message,
            "details": details,
            "links": links,
            "targetUserId": target_user_id,
            "targetRoles": target_roles,
            "actor": actor.model_dump(by_alias=True, exclude_none=True),
            "event": {
                "firstSeenAt": now,
                "lastSeenAt": now,
                "occurrenceCount": 1,
            },
            "createdAt": now,
            "acknowledgedAt": None,
            "acknowledgedBy": None,
            "resolvedAt": None,
            "resolvedBy": None,
            "expiresAt": expires_at,
            "groupKey": group_key,
            "correlationId": correlation_id,
            "auditEntryId": audit_entry_id,
            "status": NotificationStatus.ACTIVE.value,
        }

        # 5. Persist
        await self.db.notifications.insert_one(doc)

        logger.info(
            "notification_emitted",
            notification_id=notification_id,
            type=notification_type.value,
            tier=tier,
            group_key=group_key,
        )

        # 6. Publish for real-time delivery
        await self._publish_to_redis(doc)

        # 7. Send email notifications (best-effort, async)
        try:
            from hydra.api.v1.core.tasks import safe_create_task
            safe_create_task(self._deliver_email(doc))
        except Exception:
            logger.warning("notification_email_delivery_failed", exc_info=True)

        return notification_id

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    async def _deduplicate(
        self, group_key: str, _tier: int, now: datetime
    ) -> dict[str, Any] | None:
        """Check for an existing active notification with the same groupKey.

        If found within the dedup window, update it (increment count, refresh
        lastSeenAt) and optionally escalate tier.

        Returns the updated document if deduped, ``None`` to create new.
        """
        window_start = now - DEDUP_WINDOW

        existing = await self.db.notifications.find_one(
            {
                "groupKey": group_key,
                "status": NotificationStatus.ACTIVE.value,
                "$or": [
                    {"event.lastSeenAt": {"$gte": window_start}},
                    {"createdAt": {"$gte": window_start}},
                ],
            },
            sort=[("event.lastSeenAt", -1), ("createdAt", -1)],
        )

        if existing is None:
            return None

        from hydra.api.v1.models.notifications import ESCALATION_THRESHOLD

        new_count = existing.get("event", {}).get("occurrenceCount", 1) + 1
        update: dict[str, Any] = {
            "$set": {
                "event.lastSeenAt": now,
                "event.occurrenceCount": new_count,
            }
        }

        # Escalate tier if threshold reached (cap at 5)
        if new_count >= ESCALATION_THRESHOLD and existing["tier"] < 5:
            escalated_tier = min(existing["tier"] + 1, 5)
            update["$set"]["tier"] = escalated_tier
            update["$set"]["tierLabel"] = TIER_LABELS[escalated_tier].value
            update["$set"]["expiresAt"] = self._compute_expiry(escalated_tier, now)
            logger.info(
                "notification_escalated",
                notification_id=existing["notificationId"],
                old_tier=existing["tier"],
                new_tier=escalated_tier,
                occurrence_count=new_count,
            )

        await self.db.notifications.update_one(
            {"_id": existing["_id"]}, update
        )

        # Return refreshed doc for publishing
        updated = await self.db.notifications.find_one({"_id": existing["_id"]})
        if updated:
            updated.pop("_id", None)
        return updated

    # ------------------------------------------------------------------
    # Auto-Resolution
    # ------------------------------------------------------------------

    async def _check_auto_resolve(
        self,
        notification_type: NotificationType,
        source: NotificationSource,
        now: datetime,
    ) -> int:
        """Auto-resolve active notifications that this event type clears.

        Returns the number of notifications resolved.
        """
        types_to_resolve = AUTO_RESOLVE_MAP.get(notification_type)
        if not types_to_resolve:
            return 0

        type_values = [t.value for t in types_to_resolve]

        # Build a filter that matches the same source entity
        match_filter: dict[str, Any] = {
            "type": {"$in": type_values},
            "status": NotificationStatus.ACTIVE.value,
        }

        # Scope resolution to the same node/service
        if source.node_id:
            match_filter["source.nodeId"] = source.node_id
        if source.service_id:
            match_filter["source.serviceId"] = source.service_id

        expires_at = now + RESOLVED_RETENTION

        result = await self.db.notifications.update_many(
            match_filter,
            {
                "$set": {
                    "status": NotificationStatus.RESOLVED.value,
                    "resolvedAt": now,
                    "resolvedBy": "system",
                    "expiresAt": expires_at,
                }
            },
        )

        if result.modified_count > 0:
            logger.info(
                "notifications_auto_resolved",
                resolving_type=notification_type.value,
                resolved_count=result.modified_count,
                node_id=source.node_id,
            )

        return result.modified_count

    # ------------------------------------------------------------------
    # TTL Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_expiry(tier: int, now: datetime) -> datetime | None:
        """Compute the expiry timestamp based on tier TTL rules."""
        ttl = TTL_MAP.get(tier)
        if ttl is None:
            return None
        return now + ttl
