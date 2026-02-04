"""Notification queries — list, detail, and stats."""

from datetime import datetime
from typing import Any

from hydra.api.v1.models.notifications import NotificationStatus


class QueryMixin:
    """Mixin providing notification list, detail, and stats queries."""

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
