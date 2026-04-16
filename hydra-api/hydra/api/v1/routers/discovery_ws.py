"""Discovery scan streaming WebSocket endpoint.

Provides real-time scan progress for API-direct scans via Redis pub/sub.
Agent-delegated scans use polling instead.
"""

import asyncio
import contextlib
import json
from typing import Any

import structlog
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from hydra.api.v1.routers.chat_ws import _authenticate_from_message, get_user_from_token
from hydra.api.v1.services.users import UsersService
from hydra.db.mongodb import MongoDB, get_mongodb
from hydra.db.redis import RedisClient, get_redis

router = APIRouter(prefix="/discovery", tags=["Discovery"])
logger = structlog.get_logger(__name__)

SCAN_CHANNEL_PREFIX = "discovery:scan:"


def _has_permission(user_permissions: list[str], required: str) -> bool:
    """Apply the same wildcard permission matching used by HTTP routes."""
    if "*:*" in user_permissions:
        return True
    if required in user_permissions:
        return True
    resource, _action = required.split(":", 1) if ":" in required else (required, "*")
    return f"{resource}:*" in user_permissions


async def _load_current_user(
    mongodb: MongoDB,
    user_payload: dict[str, Any],
) -> dict[str, Any]:
    """Resolve a websocket auth payload into the current user context."""
    current_user = await UsersService(mongodb).get_current_user(user_payload)

    auth_source = user_payload.get("auth_source")
    client_id = user_payload.get("client_id")
    if auth_source is not None:
        current_user["auth_source"] = auth_source
        current_user["authSource"] = auth_source
    if client_id is not None:
        current_user["client_id"] = client_id
        current_user["clientId"] = client_id
    if "user_id" in current_user and "userId" not in current_user:
        current_user["userId"] = current_user["user_id"]
    if "node_id" in current_user and "nodeId" not in current_user:
        current_user["nodeId"] = current_user["node_id"]

    return current_user


async def _scan_ws_listener(
    websocket: WebSocket,
    redis_client: RedisClient,
    scan_id: str,
) -> None:
    """Subscribe to scan progress channel and forward events."""
    channel = f"{SCAN_CHANNEL_PREFIX}{scan_id}"
    pubsub = None
    try:
        pubsub = await redis_client.subscribe(channel)
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue

            try:
                data = json.loads(message["data"])
            except (json.JSONDecodeError, TypeError):
                continue

            try:
                await websocket.send_json(data)
            except Exception:
                break

            # Auto-close after terminal events
            event_type = data.get("type")
            if event_type in ("scan_complete", "scan_failed"):
                break
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.debug(
            "scan_ws_listener_stopped",
            scan_id=scan_id,
            exc_info=True,
        )
    finally:
        if pubsub:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.close()
            except Exception:
                pass


async def _scan_ws_receiver(websocket: WebSocket) -> None:
    """Handle incoming messages (ping/pong keepalive)."""
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


@router.websocket("/scan/{scan_id}/stream")
async def scan_stream_ws(
    websocket: WebSocket,
    scan_id: str,
    mongodb: MongoDB = Depends(get_mongodb),
) -> None:
    """WebSocket endpoint for real-time scan progress streaming.

    Authentication: Connect, then send ``{ type: 'authenticate', token: '<jwt>' }``
    or pass token via query param ``?token=<jwt>``.

    Events emitted:
        - ``{ type: 'progress', data: { hostsScanned, hostsAlive, percentComplete } }``
        - ``{ type: 'device_found', data: { ip, openPorts } }``
        - ``{ type: 'scan_complete', data: { summary } }``
        - ``{ type: 'scan_failed', data: { error } }``
    """
    user = await get_user_from_token(websocket)
    needs_message_auth = user is None

    await websocket.accept()

    if needs_message_auth:
        user = await _authenticate_from_message(websocket)
        if not user:
            await websocket.close(code=4001, reason="Unauthorized")
            return

    if user is None:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    current_user = await _load_current_user(mongodb, user)
    if current_user.get("type") == "agent":
        await websocket.close(code=4003, reason="Agents cannot subscribe to discovery streams")
        return

    permissions = current_user.get("permissions", [])
    if not isinstance(permissions, list) or not _has_permission(permissions, "discovery:read"):
        await websocket.close(code=4003, reason="Missing discovery:read permission")
        return

    await websocket.send_json({"type": "authenticated", "scanId": scan_id})

    redis_client = get_redis()

    listener_task = asyncio.create_task(
        _scan_ws_listener(websocket, redis_client, scan_id)
    )
    receiver_task = asyncio.create_task(_scan_ws_receiver(websocket))

    done, pending = await asyncio.wait(
        {listener_task, receiver_task},
        return_when=asyncio.FIRST_COMPLETED,
    )

    for task in pending:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
