"""Shared WebSocket message types for chat endpoints."""


class WSMessageType:
    """WebSocket message types for client-server communication."""

    # Client -> Server
    AUTHENTICATE = "authenticate"
    CHAT_REQUEST = "chat_request"
    RETRY_MESSAGE = "retry_message"
    CANCEL = "cancel"
    PING = "ping"

    # Server -> Client
    AUTHENTICATED = "authenticated"
    TEXT_DELTA = "text_delta"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_RESULT = "tool_call_result"
    MESSAGE_COMPLETE = "message_complete"
    NOTIFICATION = "notification"
    ERROR = "error"
    PONG = "pong"
