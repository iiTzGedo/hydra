"""Tests for the generic resource-events WebSocket and event publisher."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from hydra.api.v1.routers.resource_events_ws import (
    _authorize_topics,
    _events_listener,
    _events_receiver,
)
from hydra.api.v1.services.events import (
    EVENT_CHANNEL_PREFIX,
    publish_command_event,
    publish_dashboard_event,
    resolve_topic,
)


class _FakePubSub:
    def __init__(self, messages):
        self._messages = messages
        self.unsubscribed = []
        self.closed = False

    async def listen(self):
        for message in self._messages:
            yield message

    async def unsubscribe(self, *channels):
        self.unsubscribed.extend(channels)

    async def close(self):
        self.closed = True


# ── resolve_topic ────────────────────────────────────────────────────────


def test_resolve_topic_maps_known_topics():
    assert resolve_topic("commands:*") == (
        f"{EVENT_CHANNEL_PREFIX}commands",
        "commands:read",
    )
    assert resolve_topic("command:cmd-123") == (
        f"{EVENT_CHANNEL_PREFIX}command:cmd-123",
        "commands:read",
    )
    assert resolve_topic("dashboards:board:board_9") == (
        f"{EVENT_CHANNEL_PREFIX}dashboards:board:board_9",
        "dashboards:read",
    )


def test_resolve_topic_rejects_unknown_or_empty():
    assert resolve_topic("bogus") is None
    assert resolve_topic("command:") is None
    assert resolve_topic("dashboards:board:") is None
    assert resolve_topic("nodes:*") is None


# ── _authorize_topics ──────────────────────────────────────────────────────


def test_authorize_topics_filters_by_permission():
    channel_to_topic, rejected = _authorize_topics(
        ["commands:*", "dashboards:board:b1", "bogus"],
        ["commands:read"],
    )
    # Only the commands topic is permitted; dashboards + bogus are rejected.
    assert channel_to_topic == {f"{EVENT_CHANNEL_PREFIX}commands": "commands:*"}
    assert set(rejected) == {"dashboards:board:b1", "bogus"}


def test_authorize_topics_wildcard_permission_grants_all():
    channel_to_topic, rejected = _authorize_topics(
        ["commands:*", "dashboards:board:b1"],
        ["*:*"],
    )
    assert set(channel_to_topic.values()) == {"commands:*", "dashboards:board:b1"}
    assert rejected == []


# ── _events_listener ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_events_listener_forwards_with_topic_mapping():
    websocket = MagicMock()
    websocket.send_json = AsyncMock()

    channel = f"{EVENT_CHANNEL_PREFIX}commands"
    messages = [
        {"type": "subscribe", "channel": channel, "data": 1},  # ignored (not "message")
        {
            "type": "message",
            "channel": channel,
            "data": json.dumps(
                {"eventType": "command.completed", "data": {"commandId": "cmd-1"}}
            ),
        },
    ]
    pubsub = _FakePubSub(messages)
    redis_client = MagicMock()
    redis_client.subscribe = AsyncMock(return_value=pubsub)

    await _events_listener(websocket, redis_client, {channel: "commands:*"})

    redis_client.subscribe.assert_awaited_once_with(channel)
    websocket.send_json.assert_awaited_once_with(
        {
            "type": "event",
            "topic": "commands:*",
            "eventType": "command.completed",
            "data": {"commandId": "cmd-1"},
        }
    )
    assert pubsub.closed is True


@pytest.mark.asyncio
async def test_events_listener_skips_malformed_payloads():
    websocket = MagicMock()
    websocket.send_json = AsyncMock()
    channel = f"{EVENT_CHANNEL_PREFIX}command:cmd-9"
    messages = [
        {"type": "message", "channel": channel, "data": "not-json{"},
    ]
    redis_client = MagicMock()
    redis_client.subscribe = AsyncMock(return_value=_FakePubSub(messages))

    await _events_listener(websocket, redis_client, {channel: "command:cmd-9"})
    websocket.send_json.assert_not_awaited()


# ── _events_receiver ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_events_receiver_replies_to_ping_only():
    from fastapi import WebSocketDisconnect

    websocket = MagicMock()
    websocket.receive_json = AsyncMock(
        side_effect=[
            {"type": "ping"},
            {"type": "other"},
            WebSocketDisconnect(),
        ]
    )
    websocket.send_json = AsyncMock()

    await _events_receiver(websocket)

    websocket.send_json.assert_awaited_once_with({"type": "pong"})


# ── publishers ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_publish_command_event_targets_fanout_and_per_command_channels():
    redis = MagicMock()
    redis.publish = AsyncMock(return_value=1)

    await publish_command_event(
        redis, "cmd-42", "command.status_changed", {"status": "executing"}
    )

    channels = [call.args[0] for call in redis.publish.await_args_list]
    assert channels == [
        f"{EVENT_CHANNEL_PREFIX}commands",
        f"{EVENT_CHANNEL_PREFIX}command:cmd-42",
    ]
    payload = json.loads(redis.publish.await_args_list[0].args[1])
    assert payload["eventType"] == "command.status_changed"
    assert payload["data"] == {"status": "executing"}


@pytest.mark.asyncio
async def test_publish_command_event_swallows_redis_errors():
    redis = MagicMock()
    redis.publish = AsyncMock(side_effect=RuntimeError("redis down"))
    # Must not raise — publishing is best-effort.
    await publish_command_event(redis, "cmd-1", "command.completed", {})


@pytest.mark.asyncio
async def test_publish_dashboard_event_targets_board_channel():
    redis = MagicMock()
    redis.publish = AsyncMock(return_value=1)

    await publish_dashboard_event(redis, "board_7", "dashboard.updated", {"v": 2})
    redis.publish.assert_awaited_once()
    assert (
        redis.publish.await_args.args[0]
        == f"{EVENT_CHANNEL_PREFIX}dashboards:board:board_7"
    )


@pytest.mark.asyncio
async def test_publish_dashboard_event_ignores_blank_board():
    redis = MagicMock()
    redis.publish = AsyncMock()
    await publish_dashboard_event(redis, "", "dashboard.updated", {})
    redis.publish.assert_not_awaited()
