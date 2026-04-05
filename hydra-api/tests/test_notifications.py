"""Tests for notification helpers, routes, and list behavior."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hydra.api.v1.core.exceptions import NotFoundError, ValidationError
from hydra.api.v1.models.notifications import (
    NotificationBulkActionRequest,
    NotificationBulkDeleteRequest,
    NotificationSource,
    NotificationStatsResponse,
    NotificationStatus,
    NotificationType,
    SourceComponent,
    build_group_key,
)
from hydra.api.v1.models.settings import NotificationSettings
from hydra.api.v1.routers.notifications import (
    _has_permission,
    _user_roles,
    acknowledge_all,
    acknowledge_notification,
    delete_many_notifications,
    delete_notification,
    get_notification,
    get_notification_stats,
    list_notifications,
    mark_all_read,
    mark_read,
    resolve_notification,
)
from hydra.api.v1.services.notifications import NotificationService, should_deliver
from tests.utils import create_mock_cursor


class _FakeAggregate:
    def __init__(self, result):
        self._result = result

    async def to_list(self, length=None):
        _ = length
        return self._result


def _sample_notification(
    *,
    notification_id: str = "ntf-1",
    notification_type: NotificationType = NotificationType.NODE_PROFILE_STALE,
    tier: int = 3,
    status: NotificationStatus = NotificationStatus.ACTIVE,
) -> dict:
    now = datetime.now(UTC)
    return {
        "notificationId": notification_id,
        "type": notification_type.value,
        "tier": tier,
        "tierLabel": "warning" if tier == 3 else "high",
        "source": {
            "component": SourceComponent.HYDRA_API.value,
            "service": "tests",
        },
        "title": "Notification title",
        "message": "Notification message",
        "details": {"key": "value"},
        "targetUserId": None,
        "targetRoles": ["admin"],
        "groupKey": f"{notification_type.value}:{notification_id}",
        "status": status.value,
        "createdAt": now,
    }


def _current_user(
    *,
    user_id: str = "user_admin123",
    role: str = "admin",
    roles: list[str] | None = None,
    permissions: list[str] | None = None,
) -> dict:
    return {
        "user_id": user_id,
        "role": role,
        "roles": roles or [],
        "permissions": permissions or ["*:*"],
    }


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


def test_user_roles_merges_primary_role_once():
    current_user = {"role": "admin", "roles": ["admin", "operator"]}

    assert _user_roles(current_user) == ["admin", "operator"]


def test_has_permission_supports_resource_wildcards():
    current_user = {"permissions": ["notifications:*"]}

    assert _has_permission(current_user, "notifications:manage") is True
    assert _has_permission(current_user, "nodes:read") is False


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


@pytest.mark.asyncio
async def test_list_notifications_maps_filters_and_metadata():
    service = MagicMock()
    service.list_notifications = AsyncMock(return_value=([_sample_notification()], 1))

    response = await list_notifications(
        notification_service=service,
        current_user=_current_user(roles=["operator"]),
        tier=None,
        tier_min=3,
        tier_max=5,
        status="active",
        read=False,
        acknowledged=True,
        source="hydra-api",
        node_id="node-1",
        notification_type=NotificationType.NODE_PROFILE_STALE.value,
        since=None,
        until=None,
        limit=25,
        offset=5,
    )

    assert response.meta.total == 1
    assert response.meta.limit == 25
    assert response.meta.offset == 5
    assert response.data[0].notification_id == "ntf-1"
    service.list_notifications.assert_awaited_once_with(
        user_id="user_admin123",
        user_roles=["admin", "operator"],
        tier=None,
        tier_min=3,
        tier_max=5,
        status="active",
        read=False,
        acknowledged=True,
        source="hydra-api",
        node_id="node-1",
        notification_type=NotificationType.NODE_PROFILE_STALE.value,
        since=None,
        until=None,
        limit=25,
        offset=5,
    )


@pytest.mark.asyncio
async def test_get_notification_stats_returns_typed_response():
    service = MagicMock()
    service.get_stats = AsyncMock(return_value={
        "total": 4,
        "unread": 2,
        "needsAttention": 1,
        "acknowledgedPending": 1,
        "byTier": {"3": 2, "4": 2},
        "byStatus": {"active": 3, "resolved": 1},
        "bySource": {"hydra-api": 4},
    })

    response = await get_notification_stats(
        notification_service=service,
        current_user=_current_user(roles=["operator"]),
    )

    assert isinstance(response.data, NotificationStatsResponse)
    assert response.data.total == 4
    service.get_stats.assert_awaited_once_with("user_admin123", ["admin", "operator"])


@pytest.mark.asyncio
async def test_get_notification_raises_not_found_for_missing_document():
    service = MagicMock()
    service.get_notification = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError):
        await get_notification(
            notification_id="missing",
            notification_service=service,
            current_user=_current_user(),
        )


@pytest.mark.asyncio
async def test_mark_read_audits_and_returns_confirmation():
    service = MagicMock()
    service.mark_read = AsyncMock()
    audit = AsyncMock()

    with patch("hydra.api.v1.routers.notifications.log_audit", audit):
        response = await mark_read(
            notification_id="ntf-1",
            notification_service=service,
            current_user=_current_user(),
        )

    assert response.data == {"notificationId": "ntf-1", "read": True}
    service.mark_read.assert_awaited_once_with("ntf-1", "user_admin123")
    audit.assert_awaited_once()


@pytest.mark.asyncio
async def test_acknowledge_notification_rejects_low_tier_items():
    service = MagicMock()
    service.get_notification = AsyncMock(return_value=_sample_notification(tier=2))
    service.acknowledge = AsyncMock()

    with pytest.raises(ValidationError):
        await acknowledge_notification(
            notification_id="ntf-1",
            notification_service=service,
            current_user=_current_user(),
        )

    service.acknowledge.assert_not_awaited()


@pytest.mark.asyncio
async def test_acknowledge_notification_returns_updated_document():
    raw = _sample_notification(tier=3)
    updated = {**raw, "acknowledgedAt": datetime.now(UTC), "acknowledgedBy": "user_admin123"}
    service = MagicMock()
    service.get_notification = AsyncMock(return_value=raw)
    service.acknowledge = AsyncMock(return_value=updated)
    audit = AsyncMock()

    with patch("hydra.api.v1.routers.notifications.log_audit", audit):
        response = await acknowledge_notification(
            notification_id="ntf-1",
            notification_service=service,
            current_user=_current_user(),
        )

    assert response.data.notification_id == "ntf-1"
    assert response.data.acknowledged_by == "user_admin123"
    service.acknowledge.assert_awaited_once_with("ntf-1", "user_admin123")
    audit.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolve_notification_raises_not_found_when_update_returns_none():
    raw = _sample_notification(
        notification_type=NotificationType.TOPOLOGY_GENERATION_FAILED,
        tier=4,
    )
    service = MagicMock()
    service.get_notification = AsyncMock(return_value=raw)
    service.resolve = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError):
        await resolve_notification(
            notification_id="ntf-1",
            notification_service=service,
            current_user=_current_user(),
        )


@pytest.mark.asyncio
async def test_delete_notification_uses_permission_wildcards():
    service = MagicMock()
    service.delete_notification = AsyncMock(return_value=True)
    audit = AsyncMock()

    with patch("hydra.api.v1.routers.notifications.log_audit", audit):
        response = await delete_notification(
            notification_id="ntf-1",
            notification_service=service,
            current_user=_current_user(permissions=["notifications:*"]),
        )

    assert response.data == {"notificationId": "ntf-1", "deleted": True}
    service.delete_notification.assert_awaited_once_with(
        "ntf-1",
        user_id="user_admin123",
        user_roles=["admin"],
        has_write=True,
        has_manage=True,
    )
    audit.assert_awaited_once()


@pytest.mark.asyncio
async def test_mark_all_read_maps_bulk_filters_and_audits():
    service = MagicMock()
    service.mark_all_read = AsyncMock(return_value=3)
    audit = AsyncMock()

    with patch("hydra.api.v1.routers.notifications.log_audit", audit):
        response = await mark_all_read(
            notification_service=service,
            current_user=_current_user(roles=["operator"]),
            body=NotificationBulkActionRequest(
                tier=4,
                tier_min=3,
                status=NotificationStatus.ACTIVE,
                source=SourceComponent.HYDRA_API,
                node_id="node-9",
            ),
        )

    assert response.data.affected_count == 3
    service.mark_all_read.assert_awaited_once_with(
        user_id="user_admin123",
        user_roles=["admin", "operator"],
        tier=4,
        tier_min=3,
        status="active",
        source="hydra-api",
        node_id="node-9",
    )
    audit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_many_notifications_passes_permission_flags_and_body():
    service = MagicMock()
    service.delete_many = AsyncMock(return_value=2)
    audit = AsyncMock()

    with patch("hydra.api.v1.routers.notifications.log_audit", audit):
        response = await delete_many_notifications(
            notification_service=service,
            current_user=_current_user(permissions=["notifications:write"]),
            body=NotificationBulkDeleteRequest(
                notification_ids=["ntf-1", "ntf-2"],
                status=NotificationStatus.RESOLVED,
                tier=4,
                before=datetime(2026, 2, 4, tzinfo=UTC),
            ),
        )

    assert response.data.affected_count == 2
    service.delete_many.assert_awaited_once_with(
        user_id="user_admin123",
        user_roles=["admin"],
        notification_ids=["ntf-1", "ntf-2"],
        status="resolved",
        tier=4,
        before=datetime(2026, 2, 4, tzinfo=UTC),
        has_write=True,
        has_manage=False,
    )
    audit.assert_awaited_once()


@pytest.mark.asyncio
async def test_acknowledge_all_skips_audit_when_nothing_changed():
    service = MagicMock()
    service.acknowledge_all = AsyncMock(return_value=0)
    audit = AsyncMock()

    with patch("hydra.api.v1.routers.notifications.log_audit", audit):
        response = await acknowledge_all(
            notification_service=service,
            current_user=_current_user(),
            body=None,
        )

    assert response.data.affected_count == 0
    service.acknowledge_all.assert_awaited_once_with(
        user_id="user_admin123",
        user_roles=["admin"],
        tier=None,
        tier_min=None,
        status=None,
        source=None,
        node_id=None,
    )
    audit.assert_not_awaited()


@pytest.mark.asyncio
async def test_emit_notification_returns_notification_id():
    mock_mongodb = MagicMock()
    mock_redis = MagicMock()
    service = MagicMock()
    service.emit = AsyncMock(return_value="ntf-123")

    with (
        patch("hydra.db.mongodb.get_mongodb", return_value=mock_mongodb),
        patch("hydra.db.redis.get_redis", return_value=mock_redis),
        patch("hydra.api.v1.services.notifications.NotificationService", return_value=service),
    ):
        from hydra.api.v1.services.notifications import emit_notification

        result = await emit_notification(
            NotificationType.NODE_PROFILE_STALE,
            NotificationSource(component=SourceComponent.HYDRA_API, service="tests"),
            "Notification title",
            "Notification body",
        )

    assert result == "ntf-123"
    service.emit.assert_awaited_once()


@pytest.mark.asyncio
async def test_emit_notification_returns_none_when_service_raises():
    service = MagicMock()
    service.emit = AsyncMock(side_effect=RuntimeError("boom"))

    with (
        patch("hydra.db.mongodb.get_mongodb", return_value=MagicMock()),
        patch("hydra.db.redis.get_redis", return_value=MagicMock()),
        patch("hydra.api.v1.services.notifications.NotificationService", return_value=service),
        patch("hydra.api.v1.services.notifications.logger.exception") as log_exception,
    ):
        from hydra.api.v1.services.notifications import emit_notification

        result = await emit_notification(
            NotificationType.NODE_PROFILE_STALE,
            NotificationSource(component=SourceComponent.HYDRA_API, service="tests"),
            "Notification title",
            "Notification body",
        )

    assert result is None
    log_exception.assert_called_once()
