"""Shared utilities and globals for Hydra MCP server.

Provides common helper functions and initialized instances used by both
server.py and tool_handlers.py, eliminating duplication.
"""

from typing import Any

from hydra_mcp.client import HydraClient
from hydra_mcp.config import get_settings
from hydra_mcp.toon import TOONFormatter

# Shared global instances
settings = get_settings()
client = HydraClient(settings)
toon = TOONFormatter(
    delimiter=settings.toon_delimiter,
    indent=settings.toon_indent,
    length_marker=settings.toon_length_marker,
)


def safe_list(data: Any) -> list:
    """Ensure data is a list, returning empty list if not.

    This helper eliminates the repeated ``isinstance(x, list) else []`` pattern
    used when handling API responses that may not always be lists.

    Args:
        data: The data to check, typically from an API response.

    Returns:
        The data if it's a list, otherwise an empty list.
    """
    return data if isinstance(data, list) else []


def format_list_response(key: str, data: Any) -> str:
    """Format a list response with TOON, ensuring data is a list.

    Args:
        key: The key to use in the response dict (e.g., "nodes", "services").
        data: The data to format, will be coerced to list if needed.

    Returns:
        TOON-formatted string.
    """
    return toon.format({key: safe_list(data)})
