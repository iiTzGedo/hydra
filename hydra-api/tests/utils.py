"""Test helpers shared across test modules."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock


class AsyncIterator:
    """Async iterator wrapper for mocking MongoDB cursors."""

    def __init__(self, items: list[Any]):
        self.items = items
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.items):
            raise StopAsyncIteration
        item = self.items[self.index]
        self.index += 1
        return item


def create_mock_cursor(items: list[Any]) -> MagicMock:
    """Create a mock MongoDB cursor that supports async iteration and chaining."""
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.to_list = AsyncMock(return_value=items)

    def make_aiter():
        return AsyncIterator(items)

    mock_cursor.__aiter__ = lambda self: make_aiter()

    return mock_cursor
