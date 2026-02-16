"""Tests for notification helpers and list behavior."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from hydra.api.v1.models.notifications import (
    NotificationSource,
    NotificationType,
    build_group_key,
)
from hydra.api.v1.models.settings import NotificationSettings
from hydra.api.v1.services.notifications import NotificationService, should_deliver
from tests.utils import create_mock_cursor


class _FakeAggregate:
    def __init__(self, result):
        self._result = result

    async def to_list(self, length=None):
        _ = length
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


@pytest.mark.asyncio
async def test_delete_notification_with_write_requires_visibility():
    mock_db = MagicMock()
    mock_db.notifications = MagicMock()
    mock_db.notification_reads = MagicMock()
    mock_db.notifications.find_one = AsyncMock(
        return_value={"notificationId": "ntf-1", "targetUserId": "user-admin", "targetRoles": ["admin"]}
    )
    mock_db.notifications.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))
    mock_db.notification_reads.delete_many = AsyncMock()

    service = NotificationService(mock_db, MagicMock())
    deleted = await service.delete_notification(
        "ntf-1",
        user_id="user-operator",
        user_roles=["operator"],
        has_write=True,
        has_manage=False,
    )

    assert deleted is False
    mock_db.notifications.delete_one.assert_not_awaited()
    mock_db.notification_reads.delete_many.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_notification_with_write_allows_visible_notification():
    mock_db = MagicMock()
    mock_db.notifications = MagicMock()
    mock_db.notification_reads = MagicMock()
    mock_db.notifications.find_one = AsyncMock(
        return_value={"notificationId": "ntf-1", "targetUserId": None, "targetRoles": ["operator"]}
    )
    mock_db.notifications.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))
    mock_db.notification_reads.delete_many = AsyncMock(return_value=MagicMock(deleted_count=1))

    service = NotificationService(mock_db, MagicMock())
    deleted = await service.delete_notification(
        "ntf-1",
        user_id="user-operator",
        user_roles=["operator"],
        has_write=True,
        has_manage=False,
    )

    assert deleted is True
    mock_db.notifications.delete_one.assert_awaited_once_with({"notificationId": "ntf-1"})
    mock_db.notification_reads.delete_many.assert_awaited_once_with({"notificationId": "ntf-1"})


@pytest.mark.asyncio
async def test_delete_many_with_manage_is_not_visibility_scoped():
    mock_db = MagicMock()
    mock_db.notifications = MagicMock()
    mock_db.notification_reads = MagicMock()
    mock_db.notifications.find = MagicMock(
        return_value=create_mock_cursor([{"notificationId": "ntf-1"}])
    )
    mock_db.notifications.delete_many = AsyncMock(return_value=MagicMock(deleted_count=1))
    mock_db.notification_reads.delete_many = AsyncMock(return_value=MagicMock(deleted_count=1))

    service = NotificationService(mock_db, MagicMock())
    deleted_count = await service.delete_many(
        user_id="user-viewer",
        user_roles=["viewer"],
        status="resolved",
        has_write=False,
        has_manage=True,
    )

    assert deleted_count == 1
    query = mock_db.notifications.find.call_args.args[0]
    assert query["status"] == "resolved"
    assert "$or" not in query
    assert "targetUserId" not in query
