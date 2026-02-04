"""Utilities for background task management."""

import asyncio
from collections.abc import Coroutine
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def safe_create_task(
    coro: Coroutine[Any, Any, Any],
    *,
    name: str | None = None,
) -> asyncio.Task[Any]:
    """Create an asyncio task with automatic exception logging.

    Wraps asyncio.create_task to ensure exceptions from fire-and-forget
    tasks are logged instead of silently dropped.

    Args:
        coro: The coroutine to schedule.
        name: Optional name for the task (used in log messages).

    Returns:
        The created asyncio.Task.
    """
    task = asyncio.create_task(coro, name=name)
    task.add_done_callback(_task_done_callback)
    return task


def _task_done_callback(task: asyncio.Task[Any]) -> None:
    """Log exceptions from completed background tasks."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error(
            "background_task_failed",
            task_name=task.get_name(),
            error=str(exc),
            error_type=type(exc).__name__,
            exc_info=exc,
        )
