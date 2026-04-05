"""Notification helpers for chat WebSocket connections."""

import asyncio
import inspect
import json
from typing import Any

import structlog
from fastapi import WebSocket

from hydra.api.v1.core.role_utils import get_active_temporary_roles
from hydra.api.v1.models.notifications import NOTIFICATION_CHANNEL
from hydra.api.v1.models.settings import NotificationSettings
from hydra.api.v1.services.notifications import should_deliver
from hydra.db.mongodb import MongoDB
from hydra.db.redis import RedisClient

from .types import WSMessageType

logger = structlog.get_logger(__name__)


async def load_websocket_user_roles(
    mongodb: MongoDB,
    user_payload: dict[str, Any],
) -> list[str]:
    """Load active roles for a WebSocket user from MongoDB with JWT fallback."""
    user_doc_result = mongodb.users.find_one(
        {"userId": user_payload["sub"]},
        {"role": 1, "roles": 1, "temporaryRoles": 1},
    )
    user_doc = await user_doc_result if inspect.isawaitable(user_doc_result) else user_doc_result
    if user_doc:
        roles = [role for role in [user_doc.get("role")] if role]
        roles.extend(user_doc.get("roles", []) or [])
        temp_roles = get_active_temporary_roles(user_doc.get("temporaryRoles", []))
        roles.extend([role["role"] for role in temp_roles if role.get("role")])
        return roles

    roles = user_payload.get("roles", []) or []
    role = user_payload.get("role")
    if role and role not in roles:
        return [role] + roles
    return roles


async def _notification_listener(
    websocket: WebSocket,
    redis_client: RedisClient,
    mongodb: MongoDB,
    user_id: str,
    user_roles: list[str],
) -> None:
    """Subscribe to Redis notifications and forward matching events."""
    pubsub = None
    settings_doc = await mongodb.user_settings.find_one(
        {"userId": user_id},
        {"notifications": 1, "_id": 0},
    )
    notif_settings = (
        NotificationSettings.model_validate(settings_doc["notifications"])
        if settings_doc and settings_doc.get("notifications") is not None
        else NotificationSettings()
    )

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
            role_match = bool(set(user_roles) & set(target_roles))
            if not user_targeted and not role_match:
                continue

            if not should_deliver(notif_settings, data, "browser"):
                continue

            try:
                await websocket.send_json({
                    "type": WSMessageType.NOTIFICATION,
                    "data": data,
                })
            except Exception:
                break
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.debug("notification_listener_stopped", user_id=user_id, exc_info=True)
    finally:
        if pubsub:
            try:
                await pubsub.unsubscribe(NOTIFICATION_CHANNEL)
                await pubsub.close()
            except Exception:
                pass
