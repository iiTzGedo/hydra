"""Generic resource-event publishing for the real-time events WebSocket.

A single ``/events/stream`` WebSocket lets clients subscribe to topic sets and
receive push events (command status changes, dashboard updates) via Redis
pub/sub. Publishers call the helpers here; the WebSocket router subscribes to
the corresponding Redis channels and forwards events to authorized clients.

Topic → (Redis channel, required permission):
    commands:*                  -> events:commands            (commands:read)
    command:{commandId}         -> events:command:{id}        (commands:read)
    dashboards:board:{boardId}  -> events:dashboards:board:{id} (dashboards:read)
"""

from __future__ import annotations

import json
from typing import Any

import structlog

from hydra.db.redis import RedisClient

logger = structlog.get_logger(__name__)

EVENT_CHANNEL_PREFIX = "events:"


def resolve_topic(topic: str) -> tuple[str, str] | None:
    """Map a client-facing topic to ``(redis_channel, required_permission)``.

    Returns None for unknown or malformed topics so the WebSocket can reject
    them without subscribing.
    """
    if topic == "commands:*":
        return f"{EVENT_CHANNEL_PREFIX}commands", "commands:read"
    if topic.startswith("command:"):
        command_id = topic[len("command:") :]
        if command_id:
            return f"{EVENT_CHANNEL_PREFIX}command:{command_id}", "commands:read"
    if topic.startswith("dashboards:board:"):
        board_id = topic[len("dashboards:board:") :]
        if board_id:
            return f"{EVENT_CHANNEL_PREFIX}dashboards:board:{board_id}", "dashboards:read"
    return None


async def _publish(
    redis: RedisClient,
    channels: list[str],
    event_type: str,
    data: dict[str, Any],
) -> None:
    """Publish an event payload to each channel. Best-effort — never raises."""
    payload = json.dumps({"eventType": event_type, "data": data})
    for channel in channels:
        try:
            await redis.publish(channel, payload)
        except Exception:  # pragma: no cover - transport failures are non-fatal
            logger.debug("resource_event_publish_failed", channel=channel, exc_info=True)


async def publish_command_event(
    redis: RedisClient,
    command_id: str,
    event_type: str,
    data: dict[str, Any],
) -> None:
    """Publish a command lifecycle event to the fan-out and per-command channels.

    Args:
        redis: Redis client.
        command_id: The command this event concerns.
        event_type: e.g. ``command.status_changed``, ``command.completed``.
        data: Serializable event payload (status, nodeId, etc.).
    """
    channels = [f"{EVENT_CHANNEL_PREFIX}commands"]
    if command_id:
        channels.append(f"{EVENT_CHANNEL_PREFIX}command:{command_id}")
    await _publish(redis, channels, event_type, data)


async def publish_dashboard_event(
    redis: RedisClient,
    board_id: str,
    event_type: str,
    data: dict[str, Any],
) -> None:
    """Publish a dashboard board update event.

    Args:
        redis: Redis client.
        board_id: The board this event concerns.
        event_type: e.g. ``dashboard.updated``, ``dashboard.widget_changed``.
        data: Serializable event payload.
    """
    if not board_id:
        return
    await _publish(
        redis, [f"{EVENT_CHANNEL_PREFIX}dashboards:board:{board_id}"], event_type, data
    )
