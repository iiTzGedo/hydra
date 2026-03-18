"""WebSocket endpoint for real-time chat with LLM and MCP integration."""

import asyncio

import structlog
from fastapi import APIRouter, Depends, WebSocket

from hydra.api.v1.core.security import decode_token
from hydra.db.mongodb import MongoDB, get_mongodb
from hydra.db.redis import get_redis

from .connection import (
    authenticate_from_connection as _authenticate_from_connection_impl,
    authenticate_from_message as _authenticate_from_message_impl,
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


def _verify_token(token: str) -> dict | None:
    """Verify a JWT token and return the decoded payload."""
    return _verify_token_impl(token, decode_token)


async def _authenticate_from_connection(websocket: WebSocket) -> dict | None:
    """Try to authenticate from query parameters or headers (legacy support)."""
    return await _authenticate_from_connection_impl(websocket, _verify_token)


async def get_user_from_token(websocket: WebSocket) -> dict | None:
    """Extract and verify a user from WebSocket query params or headers."""
    return await _authenticate_from_connection(websocket)


async def _authenticate_from_message(websocket: WebSocket) -> dict | None:
    """Wait for an authenticate message from the client after connection."""
    return await _authenticate_from_message_impl(websocket, _verify_token)


@router.websocket("/chat/ws")
async def chat_websocket(
    websocket: WebSocket,
    mongodb: MongoDB = Depends(get_mongodb),
):
    """WebSocket endpoint for real-time chat with streaming LLM responses.

    Authentication:
        - Preferred: connect without a token, then send
          { type: "authenticate", token: "<jwt>" }
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

    user_id = user["sub"]
    handler = ChatWebSocketHandler(
        websocket=websocket,
        user_id=user_id,
        mongodb=mongodb,
    )

    logger.info("websocket_connected", user_id=user_id)

    user_roles = await load_websocket_user_roles(mongodb, user)
    notification_task = asyncio.create_task(
        _notification_listener(websocket, get_redis(), mongodb, user_id, user_roles)
    )

    try:
        await handler.handle()
    finally:
        notification_task.cancel()
        try:
            await notification_task
        except asyncio.CancelledError:
            pass
