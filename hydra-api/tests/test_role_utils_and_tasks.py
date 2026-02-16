"""Tests for role utility helpers and async task wrapper."""

from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from hydra.api.v1.core.role_utils import get_active_temporary_roles, to_utc
from hydra.api.v1.core.tasks import _task_done_callback, safe_create_task


def test_to_utc_handles_none_naive_and_aware_values():
    assert to_utc(None) is None

    naive = datetime(2026, 1, 1, 10, 0, 0)
    converted_naive = to_utc(naive)
    assert converted_naive is not None
    assert converted_naive.tzinfo == UTC

    aware = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone(timedelta(hours=2)))
    converted_aware = to_utc(aware)
    assert converted_aware is not None
    assert converted_aware.tzinfo == UTC


def test_get_active_temporary_roles_filters_expired_roles():
    now = datetime.now(UTC)
    roles = [
        {
            "role": "operator",
            "expiresAt": now + timedelta(hours=1),
            "grantedBy": "user_admin",
            "grantedAt": now,
            "reason": "on-call",
        },
        {
            "role": "viewer",
            "expiresAt": now - timedelta(hours=1),
            "grantedBy": "user_admin",
            "grantedAt": now,
            "reason": "expired",
        },
        {
            "role": "family",
            "expiresAt": None,
            "grantedBy": "user_admin",
            "grantedAt": now,
            "reason": "no-expiry",
        },
    ]

    active = get_active_temporary_roles(roles)

    assert len(active) == 1
    assert active[0]["role"] == "operator"
    assert active[0]["granted_by"] == "user_admin"
    assert active[0]["expires_at"] > now


@pytest.mark.asyncio
async def test_safe_create_task_runs_task_without_errors():
    async def _ok() -> str:
        return "ok"

    task = safe_create_task(_ok(), name="test-task")
    result = await task

    assert result == "ok"
    assert task.get_name() == "test-task"


def test_task_done_callback_logs_errors():
    class FakeTask:
        def cancelled(self):
            return False

        def exception(self):
            return ValueError("boom")

        def get_name(self):
            return "boom-task"

    with patch("hydra.api.v1.core.tasks.logger.error") as log_error:
        _task_done_callback(FakeTask())

    log_error.assert_called_once()


def test_task_done_callback_noop_when_cancelled():
    class CancelledTask:
        def cancelled(self):
            return True

    with patch("hydra.api.v1.core.tasks.logger.error") as log_error:
        _task_done_callback(CancelledTask())

    log_error.assert_not_called()
