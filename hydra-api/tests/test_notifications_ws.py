"""Tests for notification WebSocket helpers and endpoint flow."""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocketDisconnect

from hydra.api.v1.models.notifications import NOTIFICATION_CHANNEL
from hydra.api.v1.models.settings import NotificationSettings
from hydra.api.v1.routers.notifications_ws import (
    _load_user_context,
    _notifications_ws_listener,
    _notifications_ws_receiver,
    notifications_ws,
)


class _FakePubSub:
    def __init__(self, messages):
        self._messages = messages
        self.unsubscribed_channels = []
        self.closed = False

    async def listen(self):
        for message in self._messages:
            yield message

    async def unsubscribe(self, channel):
        self.unsubscribed_channels.append(channel)

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_load_user_context_uses_database_roles_and_settings():
    mongodb = MagicMock()
    mongodb.users.find_one = AsyncMock(return_value={
        "userId": "user-1",
        "role": "admin",
        "roles": ["operator"],
        "temporaryRoles": [{
            "role": "family",
            "expiresAt": datetime.now(UTC) + timedelta(hours=1),
            "grantedBy": "user_admin123",
            "grantedAt": datetime.now(UTC),
        }],
    })
    mongodb.user_settings.find_one = AsyncMock(return_value={
        "notifications": {
            "browserMinTier": 2,
            "mutedTypes": ["api_key_created"],
        }
    })

    user_id, roles, settings = await _load_user_context(
        mongodb,
        {"sub": "user-1", "role": "viewer", "roles": ["viewer"]},
    )

    assert user_id == "user-1"
    assert roles == ["admin", "operator", "family"]
    assert settings.browser_min_tier == 2
    assert settings.muted_types == ["api_key_created"]


@pytest.mark.asyncio
async def test_load_user_context_falls_back_to_token_roles():
    mongodb = MagicMock()
    mongodb.users.find_one = AsyncMock(return_value=None)
    mongodb.user_settings.find_one = AsyncMock(return_value=None)

    user_id, roles, settings = await _load_user_context(
        mongodb,
        {"sub": "user-2", "role": "viewer", "roles": ["family"]},
    )

    assert user_id == "user-2"
    assert roles == ["viewer", "family"]
    assert settings == NotificationSettings()


@pytest.mark.asyncio
async def test_notifications_ws_listener_filters_and_forwards_matching_messages():
    websocket = MagicMock()
    websocket.send_json = AsyncMock()
    payload = {
        "notificationId": "ntf-1",
        "targetRoles": ["admin"],
        "type": "node_profile_stale",
        "tier": 3,
    }
    pubsub = _FakePubSub([
        {"type": "subscribe", "data": 1},
        {"type": "message", "data": "{invalid json"},
        {"type": "message", "data": json.dumps({"notificationId": "ntf-x", "targetRoles": ["viewer"]})},
        {"type": "message", "data": json.dumps(payload)},
    ])
    redis_client = MagicMock()
    redis_client.subscribe = AsyncMock(return_value=pubsub)

    with patch("hydra.api.v1.routers.notifications_ws.should_deliver", return_value=True):
        await _notifications_ws_listener(
            websocket,
            redis_client,
            user_id="user-1",
            user_roles=["admin"],
            settings=NotificationSettings(),
        )

    redis_client.subscribe.assert_awaited_once_with(NOTIFICATION_CHANNEL)
    websocket.send_json.assert_awaited_once_with({"type": "notification", "data": payload})
    assert pubsub.unsubscribed_channels == [NOTIFICATION_CHANNEL]
    assert pubsub.closed is True


@pytest.mark.asyncio
async def test_notifications_ws_receiver_replies_to_ping_only():
    websocket = MagicMock()
    websocket.receive_json = AsyncMock(side_effect=[
        {"type": "ping"},
        {"type": "noop"},
        WebSocketDisconnect(),
    ])
    websocket.send_json = AsyncMock()

    await _notifications_ws_receiver(websocket)

    websocket.send_json.assert_awaited_once_with({"type": "pong"})


@pytest.mark.asyncio
async def test_notifications_ws_rejects_agents_before_accept():
    websocket = MagicMock()
    websocket.accept = AsyncMock()
    websocket.close = AsyncMock()

    with patch(
        "hydra.api.v1.routers.notifications_ws.get_user_from_token",
        AsyncMock(return_value={"sub": "node-1", "sub_type": "agent"}),
    ):
        await notifications_ws(websocket, mongodb=MagicMock())

    websocket.accept.assert_not_awaited()
    websocket.close.assert_awaited_once_with(
        code=4003,
        reason="Agents cannot subscribe to notifications",
    )


@pytest.mark.asyncio
async def test_notifications_ws_closes_when_message_auth_fails():
    websocket = MagicMock()
    websocket.accept = AsyncMock()
    websocket.close = AsyncMock()

    with (
        patch("hydra.api.v1.routers.notifications_ws.get_user_from_token", AsyncMock(return_value=None)),
        patch("hydra.api.v1.routers.notifications_ws._authenticate_from_message", AsyncMock(return_value=None)),
    ):
        await notifications_ws(websocket, mongodb=MagicMock())

    websocket.accept.assert_awaited_once()
    websocket.close.assert_awaited_once_with(code=4001, reason="Unauthorized")


@pytest.mark.asyncio
async def test_notifications_ws_accepts_message_auth_and_runs_listener_tasks():
    websocket = MagicMock()
    websocket.accept = AsyncMock()
    websocket.send_json = AsyncMock()

    listener = AsyncMock(return_value=None)
    receiver = AsyncMock(return_value=None)
    redis_client = MagicMock()

    with (
        patch("hydra.api.v1.routers.notifications_ws.get_user_from_token", AsyncMock(return_value=None)),
        patch(
            "hydra.api.v1.routers.notifications_ws._authenticate_from_message",
            AsyncMock(return_value={"sub": "user-1", "sub_type": "user"}),
        ),
        patch(
            "hydra.api.v1.routers.notifications_ws._load_user_context",
            AsyncMock(return_value=("user-1", ["admin"], NotificationSettings())),
        ),
        patch("hydra.api.v1.routers.notifications_ws.get_redis", return_value=redis_client),
        patch("hydra.api.v1.routers.notifications_ws._notifications_ws_listener", listener),
        patch("hydra.api.v1.routers.notifications_ws._notifications_ws_receiver", receiver),
    ):
        await notifications_ws(websocket, mongodb=MagicMock())

    websocket.accept.assert_awaited_once()
    websocket.send_json.assert_awaited_once_with({"type": "authenticated"})
    listener.assert_awaited_once_with(websocket, redis_client, "user-1", ["admin"], NotificationSettings())
    receiver.assert_awaited_once_with(websocket)
