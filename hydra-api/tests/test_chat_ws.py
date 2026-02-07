"""Tests for WebSocket chat handler."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hydra.api.v1.routers.chat_ws import (
    ChatWebSocketHandler,
    WSMessageType,
    get_user_from_token,
)


class TestWSMessageType:
    """Test WebSocket message type constants."""

    def test_request_message_types(self):
        """Test client-to-server message types."""
        assert WSMessageType.CHAT_REQUEST == "chat_request"
        assert WSMessageType.CANCEL == "cancel"
        assert WSMessageType.PING == "ping"

    def test_response_message_types(self):
        """Test server-to-client message types."""
        assert WSMessageType.TEXT_DELTA == "text_delta"
        assert WSMessageType.TOOL_CALL_START == "tool_call_start"
        assert WSMessageType.TOOL_CALL_RESULT == "tool_call_result"
        assert WSMessageType.MESSAGE_COMPLETE == "message_complete"
        assert WSMessageType.ERROR == "error"
        assert WSMessageType.PONG == "pong"


class TestGetUserFromToken:
    """Test WebSocket authentication helper."""

    @pytest.mark.asyncio
    async def test_valid_query_token(self):
        """Test authentication with valid query parameter token."""
        mock_ws = MagicMock()
        mock_ws.query_params = {"token": "valid_jwt_token"}
        mock_ws.headers = {}

        with patch("hydra.api.v1.routers.chat_ws.decode_token") as mock_decode:
            mock_decode.return_value = {"sub": "user_123", "sub_type": "user"}
            result = await get_user_from_token(mock_ws)

            assert result is not None
            assert result["sub"] == "user_123"
            mock_decode.assert_called_once_with("valid_jwt_token")

    @pytest.mark.asyncio
    async def test_valid_header_token(self):
        """Test authentication with valid Authorization header."""
        mock_ws = MagicMock()
        mock_ws.query_params = {}
        mock_ws.headers = {"authorization": "Bearer valid_jwt_token"}

        with patch("hydra.api.v1.routers.chat_ws.decode_token") as mock_decode:
            mock_decode.return_value = {"sub": "user_456", "sub_type": "user"}
            result = await get_user_from_token(mock_ws)

            assert result is not None
            assert result["sub"] == "user_456"
            mock_decode.assert_called_once_with("valid_jwt_token")

    @pytest.mark.asyncio
    async def test_no_token(self):
        """Test authentication fails without token."""
        mock_ws = MagicMock()
        mock_ws.query_params = {}
        mock_ws.headers = {}

        result = await get_user_from_token(mock_ws)
        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_token(self):
        """Test authentication fails with invalid token."""
        mock_ws = MagicMock()
        mock_ws.query_params = {"token": "invalid_token"}
        mock_ws.headers = {}

        with patch("hydra.api.v1.routers.chat_ws.decode_token") as mock_decode:
            mock_decode.side_effect = Exception("Invalid token")
            result = await get_user_from_token(mock_ws)

            assert result is None

    @pytest.mark.asyncio
    async def test_query_token_takes_precedence(self):
        """Test that query param token takes precedence over header."""
        mock_ws = MagicMock()
        mock_ws.query_params = {"token": "query_token"}
        mock_ws.headers = {"authorization": "Bearer header_token"}

        with patch("hydra.api.v1.routers.chat_ws.decode_token") as mock_decode:
            mock_decode.return_value = {"sub": "user_query"}
            await get_user_from_token(mock_ws)

            mock_decode.assert_called_once_with("query_token")


class TestChatWebSocketHandler:
    """Test ChatWebSocketHandler methods."""

    @pytest.fixture
    def mock_websocket(self):
        """Create a mock WebSocket."""
        ws = MagicMock()
        ws.send_json = AsyncMock()
        ws.receive_json = AsyncMock()
        return ws

    @pytest.fixture
    def mock_mongodb(self):
        """Create a mock MongoDB instance."""
        mongo = MagicMock()
        mongo.chat_sessions = MagicMock()
        mongo.chat_messages = MagicMock()
        mongo.chat_sessions.find_one = AsyncMock()
        mongo.chat_sessions.find_one_and_update = AsyncMock()
        mongo.chat_sessions.update_one = AsyncMock()
        mongo.chat_messages.insert_one = AsyncMock()
        return mongo

    @pytest.fixture
    def handler(self, mock_websocket, mock_mongodb):
        """Create a ChatWebSocketHandler instance."""
        return ChatWebSocketHandler(
            websocket=mock_websocket,
            user_id="user_123",
            mongodb=mock_mongodb,
        )

    def test_find_tool_server_found(self, handler):
        """Test finding server for a known tool."""
        tools = [
            {"name": "list_nodes", "server_id": "hydra-mcp"},
            {"name": "query_prometheus", "server_id": "prometheus-mcp"},
        ]

        result = handler._find_tool_server("list_nodes", tools)
        assert result == "hydra-mcp"

    def test_find_tool_server_not_found(self, handler):
        """Test finding server for unknown tool returns None."""
        tools = [
            {"name": "list_nodes", "server_id": "hydra-mcp"},
        ]

        result = handler._find_tool_server("unknown_tool", tools)
        assert result is None

    def test_find_tool_server_empty_list(self, handler):
        """Test finding server with empty tools list."""
        result = handler._find_tool_server("any_tool", [])
        assert result is None

    def test_format_history_simple_messages(self, handler):
        """Test formatting simple user/assistant messages."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        result = handler._format_history(messages)

        assert len(result) == 2
        assert result[0] == {"role": "user", "content": "Hello"}
        assert result[1] == {"role": "assistant", "content": "Hi there!"}

    def test_format_history_with_complete_tool_calls(self, handler):
        """Test formatting messages with tool calls and responses."""
        messages = [
            {"role": "user", "content": "List nodes"},
            {
                "role": "assistant",
                "content": "Let me check...",
                "toolCalls": [
                    {"id": "tc_1", "name": "list_nodes", "arguments": {}},
                ],
            },
            {"role": "tool", "toolCallId": "tc_1", "content": "Node list: [...]"},
            {"role": "assistant", "content": "Here are the nodes."},
        ]

        result = handler._format_history(messages)

        assert len(result) == 4
        # Check assistant message with tool calls
        assert result[1]["role"] == "assistant"
        assert result[1]["content"] == "Let me check..."
        assert len(result[1]["tool_calls"]) == 1
        assert result[1]["tool_calls"][0]["id"] == "tc_1"
        # Check tool response
        assert result[2]["role"] == "tool"
        assert result[2]["tool_call_id"] == "tc_1"

    def test_format_history_strips_orphan_tool_calls(self, handler):
        """Test that tool calls without responses are stripped."""
        messages = [
            {
                "role": "assistant",
                "content": "Processing...",
                "toolCalls": [
                    {"id": "tc_orphan", "name": "list_nodes", "arguments": {}},
                ],
            },
        ]

        result = handler._format_history(messages)

        # Should be empty or just the content without tool_calls
        # because tc_orphan has no corresponding tool response
        assert len(result) == 1
        assert result[0]["role"] == "assistant"
        assert result[0]["content"] == "Processing..."
        assert "tool_calls" not in result[0]

    def test_format_history_handles_snake_case(self, handler):
        """Test formatting handles snake_case field names."""
        messages = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "tc_1", "name": "get_node", "input": {"nodeId": "test"}},
                ],
            },
            {"role": "tool", "tool_call_id": "tc_1", "content": "Node data"},
        ]

        result = handler._format_history(messages)

        assert len(result) == 2
        assert result[0]["tool_calls"][0]["input"] == {"nodeId": "test"}
        assert result[1]["tool_call_id"] == "tc_1"

    def test_build_system_prompt_without_tools(self, handler):
        """Test building system prompt without tools."""
        result = handler._build_system_prompt([])

        assert "You are an AI assistant" in result
        assert "Available tools:" not in result

    def test_build_system_prompt_with_tools(self, handler):
        """Test building system prompt with tools."""
        tools = [
            {"name": "list_nodes"},
            {"name": "get_node"},
            {"name": "query_infrastructure"},
        ]

        result = handler._build_system_prompt(tools)

        assert "You are an AI assistant" in result
        assert "Available tools:" in result
        assert "list_nodes" in result
        assert "get_node" in result
        assert "query_infrastructure" in result

    @pytest.mark.asyncio
    async def test_send_message(self, handler, mock_websocket):
        """Test sending a message to WebSocket."""
        await handler._send({"type": "pong"})

        mock_websocket.send_json.assert_called_once_with({"type": "pong"})

    @pytest.mark.asyncio
    async def test_send_error(self, handler, mock_websocket):
        """Test sending an error message."""
        await handler._send_error("Something went wrong")

        mock_websocket.send_json.assert_called_once_with({
            "type": WSMessageType.ERROR,
            "error": "Something went wrong",
        })

    @pytest.mark.asyncio
    async def test_handle_ping_pong(self, handler, mock_websocket):
        """Test ping/pong handling."""
        # Mock receive_json to return ping then raise disconnect
        from fastapi import WebSocketDisconnect
        mock_websocket.receive_json = AsyncMock(
            side_effect=[{"type": "ping"}, WebSocketDisconnect()]
        )

        await handler.handle()

        # Verify pong was sent
        mock_websocket.send_json.assert_called_with({"type": "pong"})

    @pytest.mark.asyncio
    async def test_handle_cancel_sets_flag(self, handler, mock_websocket):
        """Test cancel message sets cancelled flag."""
        from fastapi import WebSocketDisconnect
        mock_websocket.receive_json = AsyncMock(
            side_effect=[{"type": "cancel"}, WebSocketDisconnect()]
        )

        assert handler._cancelled is False
        await handler.handle()
        assert handler._cancelled is True

    @pytest.mark.asyncio
    async def test_handle_unknown_message_type(self, handler, mock_websocket):
        """Test handling of unknown message type."""
        from fastapi import WebSocketDisconnect
        mock_websocket.receive_json = AsyncMock(
            side_effect=[{"type": "unknown_type"}, WebSocketDisconnect()]
        )

        await handler.handle()

        # Should send error for unknown type
        mock_websocket.send_json.assert_called_with({
            "type": WSMessageType.ERROR,
            "error": "Unknown message type: unknown_type",
        })

    @pytest.mark.asyncio
    async def test_chat_request_without_session_id(self, handler, mock_websocket):
        """Test chat request without sessionId returns error."""
        from fastapi import WebSocketDisconnect
        mock_websocket.receive_json = AsyncMock(
            side_effect=[
                {"type": "chat_request", "content": "Hello"},
                WebSocketDisconnect(),
            ]
        )

        await handler.handle()

        mock_websocket.send_json.assert_any_call({
            "type": WSMessageType.ERROR,
            "error": "sessionId is required",
        })

    @pytest.mark.asyncio
    async def test_chat_request_without_content(self, handler, mock_websocket):
        """Test chat request without content returns error."""
        from fastapi import WebSocketDisconnect
        mock_websocket.receive_json = AsyncMock(
            side_effect=[
                {"type": "chat_request", "sessionId": "sess_123"},
                WebSocketDisconnect(),
            ]
        )

        await handler.handle()

        mock_websocket.send_json.assert_any_call({
            "type": WSMessageType.ERROR,
            "error": "content is required",
        })


class TestWebSocketEndpoint:
    """Test the WebSocket endpoint behavior."""

    @pytest.mark.asyncio
    async def test_rejects_unauthenticated_connection(self):
        """Test WebSocket rejects connection without valid auth."""
        mock_ws = MagicMock()
        mock_ws.query_params = {}
        mock_ws.headers = {}
        mock_ws.close = AsyncMock()

        with patch("hydra.api.v1.routers.chat_ws._authenticate_from_connection") as mock_conn_auth, \
             patch("hydra.api.v1.routers.chat_ws._authenticate_from_message") as mock_msg_auth:
            mock_conn_auth.return_value = None
            mock_msg_auth.return_value = None

            from hydra.api.v1.routers.chat_ws import chat_websocket

            mock_ws.accept = AsyncMock()
            mock_ws.send_json = AsyncMock()
            mock_mongodb = MagicMock()
            await chat_websocket(mock_ws, mock_mongodb)

            mock_ws.close.assert_called_once_with(code=4001, reason="Unauthorized")

    @pytest.mark.asyncio
    async def test_rejects_agent_connection(self):
        """Test WebSocket rejects agent connections."""
        mock_ws = MagicMock()
        mock_ws.query_params = {"token": "agent_token"}
        mock_ws.headers = {}
        mock_ws.close = AsyncMock()

        with patch("hydra.api.v1.routers.chat_ws._authenticate_from_connection") as mock_auth:
            mock_auth.return_value = {"sub": "agent_node", "sub_type": "agent"}

            from hydra.api.v1.routers.chat_ws import chat_websocket

            mock_mongodb = MagicMock()
            await chat_websocket(mock_ws, mock_mongodb)

            mock_ws.close.assert_called_once_with(
                code=4003, reason="Agents cannot use chat"
            )

    @pytest.mark.asyncio
    async def test_accepts_valid_user_connection(self):
        """Test WebSocket accepts valid user connection."""
        from fastapi import WebSocketDisconnect

        mock_ws = MagicMock()
        mock_ws.query_params = {"token": "user_token"}
        mock_ws.headers = {}
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock()
        mock_ws.receive_json = AsyncMock(side_effect=WebSocketDisconnect())

        with patch("hydra.api.v1.routers.chat_ws._authenticate_from_connection") as mock_auth:
            mock_auth.return_value = {"sub": "user_123", "sub_type": "user"}

            from hydra.api.v1.routers.chat_ws import chat_websocket

            mock_mongodb = MagicMock()
            mock_mongodb.chat_sessions = MagicMock()
            mock_mongodb.chat_messages = MagicMock()

            await chat_websocket(mock_ws, mock_mongodb)

            mock_ws.accept.assert_called_once()
