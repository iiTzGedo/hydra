"""Notification delivery — Redis pub/sub and email distribution."""

import json
from datetime import UTC, datetime

import structlog

from hydra.api.v1.core.email import send_notification_email
from hydra.api.v1.core.role_utils import get_active_temporary_roles
from hydra.api.v1.models.notifications import NOTIFICATION_CHANNEL
from hydra.api.v1.models.settings import NotificationSettings
from hydra.api.v1.services.notifications.preferences import should_deliver
from hydra.core.config import get_settings

logger = structlog.get_logger(__name__)


class DeliveryMixin:
    """Mixin providing Redis pub/sub and email delivery for notifications."""

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
