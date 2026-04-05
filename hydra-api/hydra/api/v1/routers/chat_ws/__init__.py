"""WebSocket endpoint for real-time chat with LLM and MCP integration."""

import asyncio
import contextlib
from typing import Any

import structlog
from fastapi import APIRouter, Depends, WebSocket

from hydra.api.v1.core.auth_session import (
    ACCESS_COOKIE_NAME,
    CSRF_COOKIE_NAME,
    load_json,
    session_key,
)
from hydra.api.v1.core.security import decode_token
from hydra.db.mongodb import MongoDB, get_mongodb
from hydra.db.redis import get_redis

from .connection import (
    authenticate_from_connection as _authenticate_from_connection_impl,
)
from .connection import (
    authenticate_from_message as _authenticate_from_message_impl,
)
from .connection import (
    verify_token as _verify_token_impl,
)
from .handler import ChatWebSocketHandler
from .notifications import (
    _notification_listener,
    load_websocket_user_roles,
)
from .types import WSMessageType

router = APIRouter(tags=["Chat WebSocket"])
logger = structlog.get_logger(__name__)


def _verify_token(token: str) -> dict[str, Any] | None:
    """Verify a JWT token and return the decoded payload."""
    return _verify_token_impl(token, decode_token)


async def _authenticate_from_connection(websocket: WebSocket) -> dict[str, Any] | None:
    """Try to authenticate from legacy query parameters or headers."""
    return await _authenticate_from_connection_impl(websocket, _verify_token)


async def get_user_from_token(websocket: WebSocket) -> dict[str, Any] | None:
    """Extract and verify a user from WebSocket query params or headers."""
    return await _authenticate_from_connection(websocket)


async def _authenticate_from_message(websocket: WebSocket) -> dict[str, Any] | None:
    """Wait for an authenticate message from the client after connection."""
    return await _authenticate_from_message_impl(websocket, _verify_token, _verify_cookie_session)  # type: ignore[arg-type]


async def _verify_cookie_session(websocket: WebSocket, csrf_token: str) -> dict[str, Any] | None:
    """Validate cookie-backed WebSocket auth with a CSRF bootstrap token."""
    access_token = websocket.cookies.get(ACCESS_COOKIE_NAME)
    csrf_cookie = websocket.cookies.get(CSRF_COOKIE_NAME)
    if not access_token or not csrf_cookie or csrf_cookie != csrf_token:
        return None

    payload = _verify_token(access_token)
    if not payload:
        return None

    session_id = payload.get("sid")
    if not session_id:
        return None

    redis = get_redis()
    session_record = await load_json(redis.client, session_key(session_id))
    if not session_record or session_record.get("revoked"):
        return None
    if session_record.get("csrfToken") != csrf_token:
        return None
    return payload


@router.websocket("/chat/ws")
async def chat_websocket(
    websocket: WebSocket,
    mongodb: MongoDB = Depends(get_mongodb),
) -> None:
    """WebSocket endpoint for real-time chat with streaming LLM responses.

    Authentication:
        - Preferred browser flow: connect with session cookies, then send
          { type: "authenticate", csrfToken: "<csrf-cookie-value>" }
        - Legacy: ws://host/api/v1/chat/ws?token=<jwt>
        - Legacy: Authorization: Bearer <jwt>
    """
    user = await _authenticate_from_connection(websocket)
    needs_message_auth = user is None

    if user and user.get("sub_type") == "agent":
        await websocket.close(code=4003, reason="Agents cannot use chat")
        return

    if not needs_message_auth and not user:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()

    if needs_message_auth:
        user = await _authenticate_from_message(websocket)
        if not user:
            await websocket.send_json({"type": WSMessageType.ERROR, "error": "Authentication failed"})
            await websocket.close(code=4001, reason="Unauthorized")
            return

        if user.get("sub_type") == "agent":
            await websocket.send_json({"type": WSMessageType.ERROR, "error": "Agents cannot use chat"})
            await websocket.close(code=4003, reason="Agents cannot use chat")
            return

    await websocket.send_json({"type": WSMessageType.AUTHENTICATED})

    user_id = user["sub"]  # type: ignore[index]
    handler = ChatWebSocketHandler(
        websocket=websocket,
        user_id=user_id,
        mongodb=mongodb,
    )

    logger.info("websocket_connected", user_id=user_id)

    user_roles = await load_websocket_user_roles(mongodb, user)  # type: ignore[arg-type]
    notification_task = asyncio.create_task(
        _notification_listener(websocket, get_redis(), mongodb, user_id, user_roles)
    )

    try:
        await handler.handle()
    finally:
        notification_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await notification_task
