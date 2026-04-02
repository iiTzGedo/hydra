"""Shared auth/session helpers for token, cookie, and internal auth flows."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import Request, WebSocket

INTERNAL_REQUEST_HEADER = "X-Hydra-Internal-Request"
INTERNAL_USER_ID_HEADER = "X-Hydra-User-Id"
INTERNAL_ROLE_HEADER = "X-Hydra-Role"
INTERNAL_PERMISSIONS_HEADER = "X-Hydra-Permissions"
INTERNAL_CLIENT_ID_HEADER = "X-Hydra-Client-Id"
INTERNAL_SECRET_HEADER = "X-Hydra-Internal-Secret"

ACCESS_COOKIE_NAME = "hydra_access"
REFRESH_COOKIE_NAME = "hydra_refresh"
CSRF_COOKIE_NAME = "hydra_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"

ACCESS_BLACKLIST_PREFIX = "auth:access:blacklist:"
SESSION_PREFIX = "auth:session:"
REFRESH_PREFIX = "auth:refresh:"


def _to_unix_timestamp(value: int | float | str | datetime | None) -> int:
    """Normalize an exp claim or datetime into an integer UNIX timestamp."""
    if value is None:
        return 0
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return int(value.timestamp())
    return int(value)


def ttl_from_exp(value: int | float | str | datetime | None) -> int:
    """Return the remaining TTL in seconds from an exp-like value."""
    return max(_to_unix_timestamp(value) - int(datetime.now(timezone.utc).timestamp()), 0)


def session_key(session_id: str) -> str:
    """Build the Redis key for a session record."""
    return f"{SESSION_PREFIX}{session_id}"


def refresh_key(token_jti: str) -> str:
    """Build the Redis key for a refresh-token record."""
    return f"{REFRESH_PREFIX}{token_jti}"


def access_blacklist_key(token_jti: str) -> str:
    """Build the Redis key for a blacklisted access token."""
    return f"{ACCESS_BLACKLIST_PREFIX}{token_jti}"


async def store_json(redis_client, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
    """Serialize and store a JSON document with TTL."""
    await redis_client.setex(key, ttl_seconds, json.dumps(value))


async def load_json(redis_client, key: str) -> dict[str, Any] | None:
    """Load and deserialize a JSON document from Redis."""
    raw = await redis_client.get(key)
    if not raw:
        return None
    return json.loads(raw)


def should_use_secure_cookies(request: Request, settings) -> bool:
    """Use secure cookies on HTTPS requests or outside development."""
    return request.url.scheme == "https" or not settings.is_development


def cookie_settings(request: Request, settings) -> dict[str, Any]:
    """Return common cookie attributes for Hydra session cookies."""
    return {
        "httponly": True,
        "samesite": "lax",
        "path": "/",
        "secure": should_use_secure_cookies(request, settings),
    }


def websocket_cookie_value(websocket: WebSocket, cookie_name: str) -> str | None:
    """Get a cookie value from a WebSocket handshake."""
    return websocket.cookies.get(cookie_name)
