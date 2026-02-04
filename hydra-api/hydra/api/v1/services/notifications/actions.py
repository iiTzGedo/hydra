"""Notification actions — mark read, acknowledge, resolve, delete."""

from datetime import UTC, datetime
from typing import Any

import structlog

from hydra.api.v1.models.notifications import (
    NotificationStatus,
    RESOLVED_RETENTION,
)
from hydra.api.v1.services.notifications.preferences import (
    ACKNOWLEDGE_MIN_TIER,
    RESOLVE_MIN_TIER,
)

logger = structlog.get_logger(__name__)


class ActionsMixin:
    """Mixin providing read/acknowledge/resolve/delete operations."""

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
