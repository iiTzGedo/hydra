"""Authentication helpers for chat-style WebSocket endpoints."""

import asyncio
from collections.abc import Callable

import structlog
from fastapi import WebSocket

from .types import WSMessageType

logger = structlog.get_logger(__name__)

TokenPayload = dict
TokenDecoder = Callable[[str], TokenPayload]  # type: ignore[type-arg]
TokenVerifier = Callable[[str], TokenPayload | None]  # type: ignore[type-arg]
SessionVerifier = Callable[[WebSocket, str], TokenPayload | None]  # type: ignore[type-arg]


def verify_token(token: str, decode_token_fn: TokenDecoder) -> TokenPayload | None:  # type: ignore[type-arg]
    """Verify a JWT token and return the decoded payload."""
    try:
        payload = decode_token_fn(token)
        logger.info("ws_auth_success", user_id=payload.get("sub"))
        return payload
    except Exception as exc:
        logger.warning("ws_auth_token_invalid", error=str(exc))
        return None


async def authenticate_from_connection(
    websocket: WebSocket,
    verify_token_fn: TokenVerifier,
) -> TokenPayload | None:  # type: ignore[type-arg]
    """Try to authenticate from legacy query parameters or headers."""
    token = websocket.query_params.get("token")
    if not token:
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if not token:
        return None

    return verify_token_fn(token)


async def authenticate_from_message(
    websocket: WebSocket,
    verify_token_fn: TokenVerifier,
    verify_session_fn: SessionVerifier | None = None,
) -> TokenPayload | None:  # type: ignore[type-arg]
    """Wait for an authenticate message from the client after connection."""
    try:
        data = await asyncio.wait_for(websocket.receive_json(), timeout=10.0)
    except TimeoutError:
        logger.warning("ws_auth_timeout")
        return None
    except Exception as exc:
        logger.warning("ws_auth_receive_error", error=str(exc))
        return None

    if data.get("type") != WSMessageType.AUTHENTICATE:
        logger.warning("ws_auth_unexpected_message", msg_type=data.get("type"))
        return None

    token = data.get("token")
    if token:
        return verify_token_fn(token)

    csrf_token = data.get("csrfToken")
    if csrf_token and verify_session_fn:
        return await verify_session_fn(websocket, csrf_token)  # type: ignore[misc, no-any-return]

    logger.warning("ws_auth_no_token_in_message")
    return None
