"""Notifications WebSocket endpoint.

Separated from the REST notifications router so it can be included at the
root application level, bypassing FastAPI's sub-application WebSocket routing
issues (same pattern as chat_ws.py).
"""

import asyncio
import contextlib
import json
from typing import Any

import structlog
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from hydra.api.v1.core.role_utils import get_active_temporary_roles
from hydra.api.v1.models.notifications import NOTIFICATION_CHANNEL
from hydra.api.v1.models.settings import NotificationSettings
from hydra.api.v1.routers.chat_ws import _authenticate_from_message, get_user_from_token
from hydra.api.v1.services.notifications import should_deliver
from hydra.db.mongodb import MongoDB, get_mongodb
from hydra.db.redis import RedisClient, get_redis

router = APIRouter(prefix="/notifications", tags=["Notifications"])
logger = structlog.get_logger(__name__)


async def _load_user_context(
    mongodb: MongoDB,
    user_payload: dict[str, Any],
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


@router.websocket("/ws")
async def notifications_ws(
    websocket: WebSocket,
    mongodb: MongoDB = Depends(get_mongodb),
) -> None:
    """WebSocket endpoint for real-time notifications.

    Authentication:
        - Preferred: Connect, then send { type: 'authenticate', token: '<jwt>' }
        - Legacy: Query param ws://host/api/v1/notifications/ws?token=<jwt>
        - Legacy: Header Authorization: Bearer <jwt>
    """
    # Try legacy auth from query params/headers first
    user = await get_user_from_token(websocket)
    needs_message_auth = user is None

    if user and user.get("sub_type") == "agent":
        await websocket.close(code=4003, reason="Agents cannot subscribe to notifications")
        return

    await websocket.accept()

    # If no token in connection, wait for message-based auth
    if needs_message_auth:
        user = await _authenticate_from_message(websocket)
        if not user:
            await websocket.close(code=4001, reason="Unauthorized")
            return
        if user.get("sub_type") == "agent":
            await websocket.close(code=4003, reason="Agents cannot subscribe to notifications")
            return

    # Confirm authentication to the client
    await websocket.send_json({"type": "authenticated"})

    user_id, user_roles, settings = await _load_user_context(mongodb, user)  # type: ignore[arg-type]
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
        with contextlib.suppress(asyncio.CancelledError):
            await task
