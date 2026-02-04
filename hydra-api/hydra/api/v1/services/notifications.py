"""Notification service — emission, deduplication, auto-resolution, CRUD."""

import json
from datetime import UTC, datetime, timedelta, time
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import structlog

from hydra.db.mongodb import MongoDB
from hydra.db.redis import RedisClient
from hydra.core.config import get_settings
from hydra.api.v1.models.settings import NotificationSettings
from hydra.api.v1.core.role_utils import get_active_temporary_roles
from hydra.api.v1.core.email import send_notification_email
from hydra.api.v1.models.notifications import (
    AUTO_RESOLVE_MAP,
    DEDUP_WINDOW,
    DEFAULT_TARGET_ROLES,
    ESCALATION_THRESHOLD,
    NOTIFICATION_CHANNEL,
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

logger = structlog.get_logger(__name__)

# ------------------------------------------------------------------
# Tier-based action thresholds
# ------------------------------------------------------------------

ACKNOWLEDGE_MIN_TIER = 3  # Yellow (Warning) and above
RESOLVE_MIN_TIER = 4      # Orange (High) and above

# ------------------------------------------------------------------
# Preference Helpers
# ------------------------------------------------------------------

CATEGORY_MAP: dict[str, set[str]] = {
    "node": {
        NotificationType.NODE_OFFLINE.value,
        NotificationType.NODE_PROFILE_STALE.value,
        NotificationType.NODE_HEALTH_DEGRADED.value,
        NotificationType.NODE_REGISTERED.value,
    },
    "service": {
        NotificationType.SERVICE_DISCOVERED.value,
        NotificationType.SERVICE_STATE_CHANGED.value,
        NotificationType.SERVICE_CRASHED.value,
        NotificationType.SERVICE_INSTABILITY.value,
        NotificationType.UNKNOWN_SERVICE_DISCOVERED.value,
    },
    "profile": {
        NotificationType.AGENT_PROFILE_SUBMITTED.value,
        NotificationType.AGENT_PROFILE_FAILED.value,
        NotificationType.PROFILE_MAJOR_CHANGE.value,
        NotificationType.CONFIG_FILE_CHANGED.value,
        NotificationType.NETWORK_CONFIG_CHANGED.value,
    },
    "security": {
        NotificationType.PASSWORD_RESET_REQUESTED.value,
        NotificationType.PASSWORD_CHANGED.value,
        NotificationType.API_KEY_CREATED.value,
        NotificationType.API_KEY_REVOKED.value,
        NotificationType.API_KEY_EXPIRING.value,
        NotificationType.TOKEN_EXPIRING.value,
        NotificationType.AUTH_BRUTE_FORCE_DETECTED.value,
        NotificationType.USER_LOGIN_NEW_DEVICE.value,
        NotificationType.ROLE_ELEVATION_GRANTED.value,
        NotificationType.ROLE_ELEVATION_REVOKED.value,
        NotificationType.SUB_ACCOUNT_LINKED.value,
        NotificationType.USER_PENDING_APPROVAL.value,
    },
    "system": {
        NotificationType.API_INTERNAL_ERROR.value,
        NotificationType.DATABASE_CONNECTION_FAILED.value,
        NotificationType.WEBSOCKET_FAILURE.value,
        NotificationType.LLM_PROVIDER_FAILURE.value,
        NotificationType.MCP_AUTH_DENIED.value,
        NotificationType.MCP_TOOL_WRITE_FAILED.value,
        NotificationType.MCP_WRITE_SUCCEEDED.value,
        NotificationType.TOPOLOGY_GENERATION_FAILED.value,
        NotificationType.TOPOLOGY_REGENERATED.value,
        NotificationType.NETWORK_DISCOVERED.value,
    },
    "command": {
        NotificationType.COMMAND_EXECUTION_SUCCEEDED.value,
        NotificationType.COMMAND_EXECUTION_FAILED.value,
        NotificationType.COMMAND_EXECUTION_TIMEOUT.value,
    },
}


def resolve_category(notification_type: NotificationType | str) -> str:
    """Resolve a notification category from its type."""
    value = notification_type.value if isinstance(notification_type, NotificationType) else str(notification_type)
    for category, types in CATEGORY_MAP.items():
        if value in types:
            return category
    return "system"


def _parse_hhmm(value: str | None) -> time | None:
    if not value:
        return None
    try:
        parts = value.split(":")
        if len(parts) != 2:
            return None
        hour = int(parts[0])
        minute = int(parts[1])
        return time(hour=hour, minute=minute)
    except Exception:
        return None


def _coerce_settings(settings: NotificationSettings | dict | None) -> NotificationSettings:
    if isinstance(settings, NotificationSettings):
        return settings
    if isinstance(settings, dict):
        return NotificationSettings.model_validate(settings)
    return NotificationSettings()


def is_quiet_hours(settings: NotificationSettings | dict, now: datetime) -> bool:
    """Determine if current time is within quiet hours for user settings."""
    settings = _coerce_settings(settings)
    if not settings.quiet_hours_enabled:
        return False

    start = _parse_hhmm(settings.quiet_hours_start)
    end = _parse_hhmm(settings.quiet_hours_end)
    if start is None or end is None:
        return False

    tz = None
    if settings.timezone:
        try:
            tz = ZoneInfo(settings.timezone)
        except Exception:
            tz = ZoneInfo("UTC")

    local_now = now.astimezone(tz) if tz else now
    current = local_now.time()

    if start <= end:
        return start <= current < end
    # Wrap-around case (e.g., 22:00 -> 06:00)
    return current >= start or current < end


def should_deliver(
    settings: NotificationSettings | dict | None,
    notification: dict,
    channel: str,
    now: datetime | None = None,
) -> bool:
    """Check if a notification should be delivered via a specific channel."""
    settings = _coerce_settings(settings)
    now = now or datetime.now(UTC)

    notif_type = notification.get("type")
    tier = notification.get("tier")
    group_key = notification.get("groupKey")

    if tier is None and notif_type:
        try:
            tier = TIER_MAP.get(NotificationType(notif_type))
        except Exception:
            tier = None
    if tier is None:
        tier = 3

    if notif_type and notif_type in settings.muted_types:
        return False
    if group_key and group_key in settings.muted_group_keys:
        return False

    if channel == "email":
        if not settings.email_enabled:
            return False
        if tier < settings.email_min_tier:
            return False
    elif channel == "browser":
        if not settings.browser_enabled:
            return False
        if tier < settings.browser_min_tier:
            return False
    else:
        return False

    if settings.quiet_hours_enabled and is_quiet_hours(settings, now):
        if tier < settings.quiet_hours_min_tier:
            return False

    category = resolve_category(notif_type or "")
    if category == "node" and not settings.node_notifications:
        return False
    if category == "service" and not settings.service_notifications:
        return False
    if category == "profile" and not settings.profile_notifications:
        return False
    if category == "security" and not settings.security_notifications:
        return False
    if category == "system" and not settings.system_notifications:
        return False
    if category == "command" and not settings.command_notifications:
        return False

    return True


def _generate_notification_id() -> str:
    """Generate a unique notification ID."""
    return f"ntf-{uuid4().hex[:8]}"


class NotificationService:
    """Core notification service handling emission, deduplication, and CRUD.

    Design principles:
    - ``emit()`` is fire-and-forget: never raises, logs failures.
    - Read state (``notification_reads``) is per-user; lifecycle state
      (acknowledged, resolved) lives on the notification document.
    - Deduplication uses ``groupKey`` within a configurable time window.
    """

    def __init__(self, mongodb: MongoDB, redis: RedisClient):
        self.db = mongodb
        self.redis = redis

    # ------------------------------------------------------------------
    # Emission
    # ------------------------------------------------------------------

    async def emit(
        self,
        notification_type: NotificationType,
        source: NotificationSource,
        title: str,
        message: str,
        *,
        details: dict | None = None,
        links: list[dict] | None = None,
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
        details: dict | None,
        links: list[dict] | None,
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
            return dedup_result["notificationId"]

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
        self, group_key: str, tier: int, now: datetime
    ) -> dict | None:
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

    # ------------------------------------------------------------------
    # Redis Pub/Sub
    # ------------------------------------------------------------------

    async def _publish_to_redis(self, doc: dict) -> None:
        """Publish a notification summary to the Redis pub/sub channel."""
        try:
            summary = {
                "notificationId": doc.get("notificationId"),
                "type": doc.get("type"),
                "tier": doc.get("tier"),
                "tierLabel": doc.get("tierLabel"),
                "title": doc.get("title"),
                "groupKey": doc.get("groupKey"),
                "status": doc.get("status"),
                "occurrenceCount": (doc.get("event") or {}).get("occurrenceCount", 1),
                "targetRoles": doc.get("targetRoles", []),
                "targetUserId": doc.get("targetUserId"),
                "createdAt": doc.get("createdAt", "").isoformat()
                if isinstance(doc.get("createdAt"), datetime)
                else str(doc.get("createdAt", "")),
            }
            await self.redis.publish(NOTIFICATION_CHANNEL, json.dumps(summary))
        except Exception:
            logger.warning("notification_redis_publish_failed", exc_info=True)

    # ------------------------------------------------------------------
    # Email Delivery
    # ------------------------------------------------------------------

    async def _get_user_notification_settings(self, user_id: str) -> NotificationSettings:
        """Fetch notification settings for a user with defaults."""
        doc = await self.db.user_settings.find_one(
            {"userId": user_id},
            {"notifications": 1, "_id": 0},
        )
        if doc and doc.get("notifications") is not None:
            return NotificationSettings.model_validate(doc["notifications"])
        return NotificationSettings()

    async def _deliver_email(self, doc: dict) -> None:
        """Send email notifications to matching recipients (best-effort)."""
        try:
            target_user_id = doc.get("targetUserId")
            target_roles = doc.get("targetRoles", [])

            recipients: list[dict] = []
            if target_user_id:
                user_doc = await self.db.users.find_one(
                    {"userId": target_user_id, "status": "active"},
                    {"userId": 1, "email": 1, "role": 1, "temporaryRoles": 1},
                )
                if user_doc:
                    recipients = [user_doc]
            elif target_roles:
                cursor = self.db.users.find(
                    {
                        "status": "active",
                        "$or": [
                            {"role": {"$in": target_roles}},
                            {"temporaryRoles.role": {"$in": target_roles}},
                        ],
                    },
                    {"userId": 1, "email": 1, "role": 1, "temporaryRoles": 1},
                )
                recipients = await cursor.to_list(length=10000)
            else:
                return

            settings = get_settings()
            now = datetime.now(UTC)

            for user in recipients:
                email = user.get("email")
                if not email:
                    continue

                # Confirm role eligibility for temporary roles
                if not target_user_id:
                    roles = [user.get("role")] if user.get("role") else []
                    temp_roles = get_active_temporary_roles(user.get("temporaryRoles", []))
                    roles.extend([r.get("role") for r in temp_roles if r.get("role")])
                    if not set(roles) & set(target_roles):
                        continue

                notif_settings = await self._get_user_notification_settings(user["userId"])
                if not should_deliver(notif_settings, doc, "email", now):
                    continue

                try:
                    await send_notification_email(settings, email, doc)
                except Exception:
                    logger.warning(
                        "notification_email_send_failed",
                        user_id=user.get("userId"),
                        email=email,
                        notification_id=doc.get("notificationId"),
                        exc_info=True,
                    )
        except Exception:
            logger.warning("notification_email_delivery_failed", exc_info=True)

    # ------------------------------------------------------------------
    # List / Detail Queries
    # ------------------------------------------------------------------

    async def list_notifications(
        self,
        user_id: str,
        user_roles: list[str],
        *,
        tier: int | None = None,
        tier_min: int | None = None,
        tier_max: int | None = None,
        status: str | None = None,
        read: bool | None = None,
        acknowledged: bool | None = None,
        source: str | None = None,
        node_id: str | None = None,
        notification_type: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """List notifications visible to the current user.

        Returns (notifications_with_read_state, total_count).
        """
        # Visibility: user-targeted OR role-targeted
        visibility_filter: dict[str, Any] = {
            "$or": [
                {"targetRoles": {"$in": user_roles}},
                {"targetUserId": user_id},
            ]
        }

        query: dict[str, Any] = {**visibility_filter}

        if tier is not None:
            query["tier"] = tier
        if tier_min is not None:
            query.setdefault("tier", {})["$gte"] = tier_min
        if tier_max is not None:
            query.setdefault("tier", {})["$lte"] = tier_max
        if status:
            query["status"] = status
        else:
            # Default: show active notifications
            query["status"] = NotificationStatus.ACTIVE.value
        if acknowledged is True:
            query["acknowledgedAt"] = {"$ne": None}
        elif acknowledged is False:
            query["acknowledgedAt"] = None
        if source:
            query["source.component"] = source
        if node_id:
            query["source.nodeId"] = node_id
        if notification_type:
            query["type"] = notification_type
        if since:
            query.setdefault("createdAt", {})["$gte"] = since
        if until:
            query.setdefault("createdAt", {})["$lte"] = until

        # When read filter is provided, use an aggregation pipeline so totals are accurate
        if read is not None:
            read_match = (
                {"readAt": {"$ne": None}}
                if read
                else {"$or": [{"readAt": None}, {"readAt": {"$exists": False}}]}
            )

            base_pipeline = [
                {"$match": query},
                {
                    "$lookup": {
                        "from": "notification_reads",
                        "let": {"nid": "$notificationId"},
                        "pipeline": [
                            {
                                "$match": {
                                    "$expr": {
                                        "$and": [
                                            {"$eq": ["$notificationId", "$$nid"]},
                                            {"$eq": ["$userId", user_id]},
                                        ]
                                    }
                                }
                            },
                            {"$project": {"readAt": 1, "_id": 0}},
                        ],
                        "as": "readState",
                    }
                },
                {"$addFields": {"readAt": {"$arrayElemAt": ["$readState.readAt", 0]}}},
                {"$project": {"_id": 0, "readState": 0}},
                {"$match": read_match},
            ]

            count_pipeline = [*base_pipeline, {"$count": "count"}]
            count_result = await self.db.notifications.aggregate(count_pipeline).to_list(length=1)
            total = count_result[0]["count"] if count_result else 0

            list_pipeline = [
                *base_pipeline,
                {"$sort": {"createdAt": -1}},
                {"$skip": offset},
                {"$limit": limit},
            ]
            notifications = await self.db.notifications.aggregate(list_pipeline).to_list(length=limit)
            return notifications, total

        # Default path: no read filter
        total = await self.db.notifications.count_documents(query)

        cursor = (
            self.db.notifications.find(query, {"_id": 0})
            .sort("createdAt", -1)
            .skip(offset)
            .limit(limit)
        )
        notifications = await cursor.to_list(length=limit)

        # Join per-user read state
        if notifications:
            notification_ids = [n["notificationId"] for n in notifications]
            read_docs = await self.db.notification_reads.find(
                {"notificationId": {"$in": notification_ids}, "userId": user_id},
                {"_id": 0},
            ).to_list(length=len(notification_ids))

            read_map = {d["notificationId"]: d.get("readAt") for d in read_docs}
            for n in notifications:
                n["readAt"] = read_map.get(n["notificationId"])

        return notifications, total

    async def get_notification(
        self, notification_id: str, user_id: str
    ) -> dict | None:
        """Get a single notification with per-user read state."""
        doc = await self.db.notifications.find_one(
            {"notificationId": notification_id}, {"_id": 0}
        )
        if doc is None:
            return None

        read_doc = await self.db.notification_reads.find_one(
            {"notificationId": notification_id, "userId": user_id},
            {"_id": 0},
        )
        doc["readAt"] = read_doc.get("readAt") if read_doc else None
        return doc

    async def get_stats(
        self, user_id: str, user_roles: list[str]
    ) -> dict:
        """Get aggregated notification statistics for the current user."""
        visibility_filter: dict[str, Any] = {
            "$or": [
                {"targetRoles": {"$in": user_roles}},
                {"targetUserId": user_id},
            ]
        }

        pipeline = [
            {"$match": {**visibility_filter, "status": NotificationStatus.ACTIVE.value}},
            {
                "$facet": {
                    "byTier": [
                        {"$group": {"_id": "$tierLabel", "count": {"$sum": 1}}}
                    ],
                    "byStatus": [
                        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
                    ],
                    "bySource": [
                        {"$group": {"_id": "$source.component", "count": {"$sum": 1}}}
                    ],
                    "total": [{"$count": "count"}],
                }
            },
        ]

        results = await self.db.notifications.aggregate(pipeline).to_list(length=1)
        facets = results[0] if results else {}

        total = facets.get("total", [{}])
        total_count = total[0].get("count", 0) if total else 0

        by_tier = {r["_id"]: r["count"] for r in facets.get("byTier", [])}
        by_status = {r["_id"]: r["count"] for r in facets.get("byStatus", [])}
        by_source = {r["_id"]: r["count"] for r in facets.get("bySource", [])}

        # Compute unread count: total active minus those with read state
        active_ids_cursor = self.db.notifications.find(
            {**visibility_filter, "status": NotificationStatus.ACTIVE.value},
            {"notificationId": 1, "_id": 0},
        )
        active_ids = [d["notificationId"] for d in await active_ids_cursor.to_list(length=10000)]

        read_count = 0
        if active_ids:
            read_count = await self.db.notification_reads.count_documents(
                {"notificationId": {"$in": active_ids}, "userId": user_id}
            )

        unread = total_count - read_count

        return {
            "total": total_count,
            "unread": max(unread, 0),
            "byTier": by_tier,
            "byStatus": by_status,
            "bySource": by_source,
        }

    # ------------------------------------------------------------------
    # Mark Read (per-user)
    # ------------------------------------------------------------------

    async def mark_read(self, notification_id: str, user_id: str) -> bool:
        """Mark a notification as read for this user. Returns True if upserted."""
        now = datetime.now(UTC)
        result = await self.db.notification_reads.update_one(
            {"notificationId": notification_id, "userId": user_id},
            {
                "$set": {"readAt": now, "lastViewedAt": now},
                "$setOnInsert": {
                    "notificationId": notification_id,
                    "userId": user_id,
                },
            },
            upsert=True,
        )
        return result.upserted_id is not None or result.modified_count > 0

    async def mark_all_read(
        self,
        user_id: str,
        user_roles: list[str],
        *,
        tier: int | None = None,
        tier_min: int | None = None,
        status: str | None = None,
        source: str | None = None,
        node_id: str | None = None,
    ) -> int:
        """Mark all visible notifications as read for this user.

        Returns the number of notifications marked.
        """
        visibility_filter: dict[str, Any] = {
            "$or": [
                {"targetRoles": {"$in": user_roles}},
                {"targetUserId": user_id},
            ]
        }
        query: dict[str, Any] = {
            **visibility_filter,
            "status": status or NotificationStatus.ACTIVE.value,
        }
        if tier is not None:
            query["tier"] = tier
        if tier_min is not None:
            query["tier"] = {"$gte": tier_min}
        if source:
            query["source.component"] = source
        if node_id:
            query["source.nodeId"] = node_id

        cursor = self.db.notifications.find(query, {"notificationId": 1, "_id": 0})
        notification_ids = [d["notificationId"] for d in await cursor.to_list(length=10000)]

        if not notification_ids:
            return 0

        now = datetime.now(UTC)
        ops = [
            {
                "updateOne": {
                    "filter": {"notificationId": nid, "userId": user_id},
                    "update": {
                        "$set": {"readAt": now, "lastViewedAt": now},
                        "$setOnInsert": {"notificationId": nid, "userId": user_id},
                    },
                    "upsert": True,
                }
            }
            for nid in notification_ids
        ]

        # Use bulk_write for efficiency
        from pymongo import UpdateOne

        bulk_ops = [
            UpdateOne(
                {"notificationId": nid, "userId": user_id},
                {
                    "$set": {"readAt": now, "lastViewedAt": now},
                    "$setOnInsert": {"notificationId": nid, "userId": user_id},
                },
                upsert=True,
            )
            for nid in notification_ids
        ]

        if bulk_ops:
            result = await self.db.notification_reads.bulk_write(bulk_ops)
            return result.upserted_count + result.modified_count

        return 0

    # ------------------------------------------------------------------
    # Acknowledge
    # ------------------------------------------------------------------

    async def acknowledge(
        self, notification_id: str, user_id: str
    ) -> dict | None:
        """Acknowledge a notification (tier 3+ only). Returns updated doc or None.

        Also marks the notification as read for the user.
        """
        now = datetime.now(UTC)
        result = await self.db.notifications.find_one_and_update(
            {
                "notificationId": notification_id,
                "acknowledgedAt": None,
                "tier": {"$gte": ACKNOWLEDGE_MIN_TIER},
            },
            {
                "$set": {
                    "acknowledgedAt": now,
                    "acknowledgedBy": user_id,
                }
            },
            return_document=True,
        )
        if result:
            result.pop("_id", None)
            # Also mark as read for this user
            await self.mark_read(notification_id, user_id)
            logger.info(
                "notification_acknowledged",
                notification_id=notification_id,
                user_id=user_id,
            )
        return result

    async def acknowledge_all(
        self,
        user_id: str,
        user_roles: list[str],
        *,
        tier: int | None = None,
        tier_min: int | None = None,
        status: str | None = None,
        source: str | None = None,
        node_id: str | None = None,
    ) -> int:
        """Acknowledge all matching notifications (tier 3+ only). Returns count.

        Also marks acknowledged notifications as read for the user.
        """
        now = datetime.now(UTC)
        # Enforce minimum tier for acknowledge
        effective_tier_min = max(tier_min or ACKNOWLEDGE_MIN_TIER, ACKNOWLEDGE_MIN_TIER)

        visibility_filter: dict[str, Any] = {
            "$or": [
                {"targetRoles": {"$in": user_roles}},
                {"targetUserId": user_id},
            ]
        }
        query: dict[str, Any] = {
            **visibility_filter,
            "status": status or NotificationStatus.ACTIVE.value,
            "acknowledgedAt": None,
            "tier": {"$gte": effective_tier_min},
        }
        if tier is not None:
            # Only allow tiers at or above the minimum
            if tier < ACKNOWLEDGE_MIN_TIER:
                return 0
            query["tier"] = tier
        if source:
            query["source.component"] = source
        if node_id:
            query["source.nodeId"] = node_id

        # Get IDs before updating so we can mark them as read
        cursor = self.db.notifications.find(query, {"notificationId": 1, "_id": 0})
        notification_ids = [d["notificationId"] for d in await cursor.to_list(length=10000)]

        if not notification_ids:
            return 0

        result = await self.db.notifications.update_many(
            {"notificationId": {"$in": notification_ids}},
            {"$set": {"acknowledgedAt": now, "acknowledgedBy": user_id}},
        )

        # Bulk mark as read
        if notification_ids:
            from pymongo import UpdateOne

            bulk_ops = [
                UpdateOne(
                    {"notificationId": nid, "userId": user_id},
                    {
                        "$set": {"readAt": now, "lastViewedAt": now},
                        "$setOnInsert": {"notificationId": nid, "userId": user_id},
                    },
                    upsert=True,
                )
                for nid in notification_ids
            ]
            if bulk_ops:
                await self.db.notification_reads.bulk_write(bulk_ops)

        if result.modified_count > 0:
            logger.info(
                "notifications_bulk_acknowledged",
                user_id=user_id,
                count=result.modified_count,
            )
        return result.modified_count

    # ------------------------------------------------------------------
    # Resolve
    # ------------------------------------------------------------------

    async def resolve(
        self, notification_id: str, user_id: str
    ) -> dict | None:
        """Manually resolve a notification (tier 4+ only). Returns updated doc or None."""
        now = datetime.now(UTC)
        expires_at = now + RESOLVED_RETENTION

        result = await self.db.notifications.find_one_and_update(
            {
                "notificationId": notification_id,
                "status": NotificationStatus.ACTIVE.value,
                "tier": {"$gte": RESOLVE_MIN_TIER},
            },
            {
                "$set": {
                    "status": NotificationStatus.RESOLVED.value,
                    "resolvedAt": now,
                    "resolvedBy": user_id,
                    "expiresAt": expires_at,
                }
            },
            return_document=True,
        )
        if result:
            result.pop("_id", None)
            logger.info(
                "notification_resolved",
                notification_id=notification_id,
                user_id=user_id,
            )
        return result

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete_notification(self, notification_id: str) -> bool:
        """Hard-delete a notification and its read state. Returns True if deleted."""
        result = await self.db.notifications.delete_one(
            {"notificationId": notification_id}
        )
        if result.deleted_count > 0:
            await self.db.notification_reads.delete_many(
                {"notificationId": notification_id}
            )
            logger.info("notification_deleted", notification_id=notification_id)
            return True
        return False


# ---------------------------------------------------------------------------
# Module-level helper for fire-and-forget emission from services
# ---------------------------------------------------------------------------


async def emit_notification(
    notification_type: NotificationType,
    source: NotificationSource,
    title: str,
    message: str,
    *,
    details: dict | None = None,
    links: list[dict] | None = None,
    actor: NotificationActor | None = None,
    target_user_id: str | None = None,
    target_roles: list[str] | None = None,
    correlation_id: str | None = None,
    audit_entry_id: str | None = None,
    group_key: str | None = None,
) -> str | None:
    """Convenience function to emit a notification from any service.

    Obtains the MongoDB and Redis singletons, creates a NotificationService,
    and calls emit(). Safe to call from anywhere — never raises.
    """
    try:
        from hydra.db.mongodb import get_mongodb
        from hydra.db.redis import get_redis

        mongodb = get_mongodb()
        redis = get_redis()
        service = NotificationService(mongodb, redis)
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
