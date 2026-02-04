"""Tests for notification helpers and list behavior."""

from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock

import pytest

from hydra.api.v1.models.notifications import (
    NotificationSource,
    NotificationType,
    build_group_key,
)
from hydra.api.v1.models.settings import NotificationSettings
from hydra.api.v1.services.notifications import NotificationService, should_deliver


class _FakeAggregate:
    def __init__(self, result):
        self._result = result

    async def to_list(self, length=None):
        return self._result


def test_build_group_key_entity_ids():
    source = NotificationSource(component="hydra-api", service="test")

    key = build_group_key(
        NotificationType.COMMAND_EXECUTION_FAILED,
        source,
        {"commandId": "cmd-123"},
    )
    assert key == "command_execution_failed:cmd-123"

    key = build_group_key(
        NotificationType.API_KEY_CREATED,
        source,
        {"entityId": "key-123"},
    )
    assert key == "api_key_created:key-123"

    key = build_group_key(
        NotificationType.REGISTRATION_TOKEN_CREATED,
        source,
        {"token": "reg-abc"},
    )
    assert key == "registration_token_created:reg-abc"

    key = build_group_key(
        NotificationType.USER_SETTINGS_UPDATED,
        source,
        {"userId": "user-1"},
    )
    assert key == "user_settings_updated:user-1"


def test_should_deliver_quiet_hours_blocks_low_tier():
    settings = NotificationSettings(
        quiet_hours_enabled=True,
        quiet_hours_start="22:00",
        quiet_hours_end="06:00",
        quiet_hours_min_tier=5,
        browser_min_tier=1,
    )
    notification = {"type": NotificationType.NODE_PROFILE_STALE.value, "tier": 4}
    now = datetime(2026, 2, 4, 23, 0, tzinfo=UTC)

    assert should_deliver(settings, notification, "browser", now) is False


def test_should_deliver_muted_type():
    settings = NotificationSettings(muted_types=[NotificationType.API_KEY_CREATED.value])
    notification = {"type": NotificationType.API_KEY_CREATED.value, "tier": 2}

    assert should_deliver(settings, notification, "browser", datetime.now(UTC)) is False


@pytest.mark.asyncio
async def test_list_notifications_read_filter_uses_aggregate():
    mock_db = MagicMock()
    mock_db.notifications = MagicMock()

    count_result = [{"count": 2}]
    list_result = [{"notificationId": "ntf-1", "readAt": "2026-02-04T00:00:00Z"}]
    mock_db.notifications.aggregate = MagicMock(
        side_effect=[_FakeAggregate(count_result), _FakeAggregate(list_result)]
    )

    service = NotificationService(mock_db, MagicMock())
    notifications, total = await service.list_notifications(
        user_id="user-1",
        user_roles=["admin"],
        read=True,
    )

    assert total == 2
    assert notifications == list_result
    assert mock_db.notifications.aggregate.call_count == 2
