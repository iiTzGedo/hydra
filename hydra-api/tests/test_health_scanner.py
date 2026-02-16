"""Tests for health scanner audit/notification emission behavior."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hydra.api.v1.models.notifications import (
    NotificationSource,
    NotificationStatus,
    NotificationType,
)
from hydra.api.v1.services.health_scanner import HealthScanner


@pytest.mark.asyncio
async def test_emit_with_audit_skips_audit_when_dedup_candidate_exists():
    mock_db = MagicMock()
    mock_db.notifications = MagicMock()
    mock_db.notifications.find_one = AsyncMock(return_value={"notificationId": "ntf-1"})

    scanner = HealthScanner(mock_db, MagicMock())
    scanner.notif.emit = AsyncMock()

    with patch(
        "hydra.api.v1.services.health_scanner.log_audit",
        AsyncMock(return_value="aud-1"),
    ) as mock_log_audit:
        await scanner._emit_with_audit(
            notification_type=NotificationType.NODE_PROFILE_STALE,
            source=NotificationSource(component="hydra-api", service="health-scanner"),
            title="Profile stale",
            message="Profile is stale",
            details={"nodeId": "node-1"},
            resource_type="node",
            resource_id="node-1",
        )

    mock_log_audit.assert_not_awaited()
    scanner.notif.emit.assert_awaited_once()
    assert scanner.notif.emit.await_args.kwargs["audit_entry_id"] is None


@pytest.mark.asyncio
async def test_emit_with_audit_logs_when_no_recent_dedup_candidate():
    mock_db = MagicMock()
    mock_db.notifications = MagicMock()
    mock_db.notifications.find_one = AsyncMock(return_value=None)

    scanner = HealthScanner(mock_db, MagicMock())
    scanner.notif.emit = AsyncMock()

    with patch(
        "hydra.api.v1.services.health_scanner.log_audit",
        AsyncMock(return_value="aud-2"),
    ) as mock_log_audit:
        await scanner._emit_with_audit(
            notification_type=NotificationType.NODE_PROFILE_STALE,
            source=NotificationSource(component="hydra-api", service="health-scanner"),
            title="Profile stale",
            message="Profile is stale",
            details={"nodeId": "node-1"},
            resource_type="node",
            resource_id="node-1",
        )

    mock_log_audit.assert_awaited_once()
    scanner.notif.emit.assert_awaited_once()
    assert scanner.notif.emit.await_args.kwargs["audit_entry_id"] == "aud-2"

    query = mock_db.notifications.find_one.await_args.args[0]
    assert query["status"] == NotificationStatus.ACTIVE.value
    assert "$or" in query
    assert any("event.lastSeenAt" in clause for clause in query["$or"])
    assert any("createdAt" in clause for clause in query["$or"])
