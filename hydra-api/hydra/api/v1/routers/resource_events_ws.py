"""Generic resource-events WebSocket endpoint.

A single ``/events/stream`` socket serves real-time updates for multiple
resource types (command execution, dashboard boards). Clients authenticate,
then send one ``subscribe`` message listing the topics they want; the server
validates each topic against the caller's permissions and forwards matching
events published to Redis.

This replaces the need for per-feature WebSocket endpoints (P2G-T03 command
tracking and P2DASH-T029 dashboard real-time both ride this socket).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any

import structlog
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from hydra.api.v1.routers.chat_ws import _authenticate_from_message, get_user_from_token
from hydra.api.v1.routers.discovery_ws import _has_permission, _load_current_user
from hydra.api.v1.services.events import resolve_topic
from hydra.db.mongodb import MongoDB, get_mongodb
from hydra.db.redis import RedisClient, get_redis

router = APIRouter(tags=["Events"])
logger = structlog.get_logger(__name__)

# Wait this long for the client's initial subscribe message before closing.
_SUBSCRIBE_TIMEOUT_SECONDS = 30


def _authorize_topics(
    topics: list[str],
    permissions: list[str],
) -> tuple[dict[str, str], list[str]]:
    """Resolve and authorize a list of topics.

    Returns ``(channel_to_topic, rejected)`` where ``channel_to_topic`` maps a
    Redis channel to the granted topic, and ``rejected`` lists topics that were
    unknown or not permitted.
    """
    channel_to_topic: dict[str, str] = {}
    rejected: list[str] = []
    for topic in topics:
        if not isinstance(topic, str):
            continue
        resolved = resolve_topic(topic)
        if resolved is None:
            rejected.append(topic)
            continue
        channel, required_permission = resolved
        if not _has_permission(permissions, required_permission):
            rejected.append(topic)
            continue
        channel_to_topic[channel] = topic
    return channel_to_topic, rejected


async def _events_listener(
    websocket: WebSocket,
    redis_client: RedisClient,
    channel_to_topic: dict[str, str],
) -> None:
    """Subscribe to the granted channels and forward events to the client."""
    pubsub = None
    channels = list(channel_to_topic.keys())
    try:
        pubsub = await redis_client.subscribe(*channels)
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue

            channel = message.get("channel")
            if isinstance(channel, bytes):
                channel = channel.decode()

            raw = message.get("data")
            if isinstance(raw, bytes):
                raw = raw.decode()
            try:
                event = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue

            out: dict[str, Any] = {
                "type": "event",
                "topic": channel_to_topic.get(channel),
                "eventType": event.get("eventType"),
                "data": event.get("data"),
            }
            try:
                await websocket.send_json(out)
            except Exception:
                break
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.debug("events_listener_stopped", exc_info=True)
    finally:
        if pubsub:
            try:
                await pubsub.unsubscribe(*channels)
                await pubsub.close()
            except Exception:
                pass


async def _events_receiver(websocket: WebSocket) -> None:
    """Handle incoming client messages (ping/pong keepalive)."""
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


@router.websocket("/events/stream")
async def events_stream_ws(
    websocket: WebSocket,
    mongodb: MongoDB = Depends(get_mongodb),
) -> None:
    """WebSocket for real-time resource events.

    Flow:
        1. Authenticate (``?token=<jwt>`` query param, or send
           ``{ type: 'authenticate', token: '<jwt>' }`` / CSRF cookie auth).
        2. Receive ``{ type: 'subscribe', topics: ['commands:*', ...] }``.
        3. Server replies ``{ type: 'subscribed', topics: [...], rejected: [...] }``
           and forwards ``{ type: 'event', topic, eventType, data }`` messages.

    Supported topics: ``commands:*``, ``command:{id}``, ``dashboards:board:{id}``.
    Each topic is authorized against the caller's permissions; unauthorized or
    unknown topics are returned in ``rejected``. The subscription set is fixed
    for the connection — to change it, reconnect.
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
        await websocket.close(code=4003, reason="Agents cannot subscribe to events")
        return

    await websocket.send_json({"type": "authenticated"})

    # Await the initial subscribe message.
    try:
        first = await asyncio.wait_for(
            websocket.receive_json(), timeout=_SUBSCRIBE_TIMEOUT_SECONDS
        )
    except TimeoutError:
        await websocket.close(code=4002, reason="No subscribe message received")
        return
    except WebSocketDisconnect:
        return

    if first.get("type") != "subscribe" or not isinstance(first.get("topics"), list):
        await websocket.close(code=4002, reason="Expected a subscribe message")
        return

    permissions = current_user.get("permissions", [])
    if not isinstance(permissions, list):
        permissions = []

    channel_to_topic, rejected = _authorize_topics(first["topics"], permissions)

    if not channel_to_topic:
        await websocket.send_json(
            {"type": "subscribed", "topics": [], "rejected": rejected}
        )
        await websocket.close(code=4003, reason="No authorized topics")
        return

    await websocket.send_json(
        {
            "type": "subscribed",
            "topics": list(channel_to_topic.values()),
            "rejected": rejected,
        }
    )

    redis_client = get_redis()
    listener_task = asyncio.create_task(
        _events_listener(websocket, redis_client, channel_to_topic)
    )
    receiver_task = asyncio.create_task(_events_receiver(websocket))

    _done, pending = await asyncio.wait(
        {listener_task, receiver_task},
        return_when=asyncio.FIRST_COMPLETED,
    )

    for task in pending:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
