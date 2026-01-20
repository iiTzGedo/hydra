"""WebSocket endpoint for real-time chat with LLM and MCP integration."""

import secrets
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from hydra.api.v1.core.security import decode_token
from hydra.api.v1.models.chat import ToolCallStatus
from hydra.api.v1.services.chat import ChatService, ChatSessionNotFoundError
from hydra.api.v1.services.llm_bridge import LLMBridge, LLMProviderError
from hydra.api.v1.services.mcp_client import MCPClient, MCPClientError
from hydra.db.mongodb import MongoDB, get_mongodb

router = APIRouter(tags=["Chat WebSocket"])
logger = structlog.get_logger(__name__)


class WSMessageType:
    """WebSocket message types for client-server communication."""

    CHAT_REQUEST = "chat_request"
    CANCEL = "cancel"
    PING = "ping"

    TEXT_DELTA = "text_delta"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_RESULT = "tool_call_result"
    MESSAGE_COMPLETE = "message_complete"
    ERROR = "error"
    PONG = "pong"


class ChatWebSocketHandler:
    """Handler for WebSocket chat connections with LLM and MCP integration."""

    def __init__(
        self,
        websocket: WebSocket,
        user_id: str,
        mongodb: MongoDB,
    ):
        """Initialize the WebSocket handler.

        Args:
            websocket: The WebSocket connection instance.
            user_id: ID of the authenticated user.
            mongodb: MongoDB database instance.
        """
        self.websocket = websocket
        self.user_id = user_id
        self.mongodb = mongodb
        self.chat_service = ChatService(mongodb)
        self.llm_bridge = LLMBridge(mongodb)
        self.mcp_client = MCPClient(mongodb)
        self._cancelled = False

    async def handle(self):
        """Process incoming WebSocket messages in a loop.

        Handles message types: ping, cancel, and chat_request.
        Continues until the connection is closed or an error occurs.
        """
        try:
            while True:
                data = await self.websocket.receive_json()
                msg_type = data.get("type")

                if msg_type == WSMessageType.PING:
                    await self._send({"type": WSMessageType.PONG})

                elif msg_type == WSMessageType.CANCEL:
                    self._cancelled = True

                elif msg_type == WSMessageType.CHAT_REQUEST:
                    self._cancelled = False
                    await self._handle_chat_request(data)

                else:
                    await self._send_error(f"Unknown message type: {msg_type}")

        except WebSocketDisconnect:
            logger.info("websocket_disconnected", user_id=self.user_id)
        except Exception as e:
            logger.exception("websocket_error", user_id=self.user_id, error=str(e))
            await self._send_error(str(e))

    async def _handle_chat_request(self, data: dict):
        """Process a chat request with LLM completion and MCP tool support.

        Args:
            data: Request data containing sessionId, content, and optional providerId.
        """
        session_id = data.get("sessionId")
        message_content = data.get("content", "")
        provider_id = data.get("providerId")

        if not session_id:
            await self._send_error("sessionId is required")
            return

        if not message_content:
            await self._send_error("content is required")
            return

        try:
            session = await self.chat_service.get_session(session_id, self.user_id)

            active_provider_id = provider_id or session.get("llm_provider_id")
            if not active_provider_id:
                await self._send_error("No LLM provider configured for session")
                return

            provider_config = await self.llm_bridge.get_provider_config(
                active_provider_id, self.user_id
            )

            mcp_server_ids = session.get("mcp_server_ids", [])
            tools = []
            if mcp_server_ids:
                tools = await self.mcp_client.get_all_tools_for_session(
                    mcp_server_ids, self.user_id
                )

            history_result = await self.chat_service.list_messages(
                session_id, self.user_id, limit=100, order="asc"
            )
            history = self._format_history(history_result.get("messages", []))
            history.append({"role": "user", "content": message_content})

            await self._save_message(session_id, "user", message_content)

            system_prompt = self._build_system_prompt(tools)

            await self._stream_llm_response(
                session_id=session_id,
                provider_config=provider_config,
                messages=history,
                tools=tools,
                system_prompt=system_prompt,
                mcp_server_ids=mcp_server_ids,
            )

        except ChatSessionNotFoundError:
            await self._send_error(f"Session not found: {session_id}")
        except LLMProviderError as e:
            await self._send_error(f"LLM provider error: {e.message}")
        except MCPClientError as e:
            await self._send_error(f"MCP error: {e.message}")
        except Exception as e:
            logger.exception("chat_request_error", session_id=session_id, error=str(e))
            await self._send_error(f"Internal error: {str(e)}")

    async def _stream_llm_response(
        self,
        session_id: str,
        provider_config: dict,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
        mcp_server_ids: list[str],
    ):
        """Stream LLM response with iterative tool execution support.

        Handles multiple rounds of tool calls up to max_tool_rounds limit.

        Args:
            session_id: Chat session identifier.
            provider_config: LLM provider configuration.
            messages: Conversation history.
            tools: Available MCP tools.
            system_prompt: System prompt for the LLM.
            mcp_server_ids: Connected MCP server IDs.
        """
        full_response = ""
        tool_calls: list[dict] = []
        max_tool_rounds = 10

        current_messages = messages.copy()

        for _ in range(max_tool_rounds):
            if self._cancelled:
                await self._send({"type": WSMessageType.ERROR, "error": "Cancelled"})
                return

            round_text = ""
            round_tool_calls: list[dict] = []

            async for event in self.llm_bridge.stream_completion(
                provider_config=provider_config,
                messages=current_messages,
                tools=tools if tools else None,
                system_prompt=system_prompt,
            ):
                if self._cancelled:
                    break

                event_type = event.get("type")

                if event_type == "text_delta":
                    text = event.get("text", "")
                    round_text += text
                    full_response += text
                    await self._send({
                        "type": WSMessageType.TEXT_DELTA,
                        "text": text,
                    })

                elif event_type == "tool_use":
                    tool_call = {
                        "id": event.get("id", f"tc_{secrets.token_urlsafe(4)}"),
                        "name": event.get("name", ""),
                        "input": event.get("input", {}),
                        "server_id": self._find_tool_server(event.get("name"), tools),
                    }
                    round_tool_calls.append(tool_call)
                    tool_calls.append(tool_call)

                    await self._send({
                        "type": WSMessageType.TOOL_CALL_START,
                        "toolCall": {
                            "id": tool_call["id"],
                            "name": tool_call["name"],
                            "arguments": tool_call["input"],
                        },
                    })

                elif event_type == "error":
                    await self._send_error(event.get("error", "Unknown error"))
                    return

                elif event_type == "done":
                    break

            if not round_tool_calls:
                break

            for tool_call in round_tool_calls:
                result = await self.mcp_client.execute_tool_call(
                    tool_call, mcp_server_ids, self.user_id
                )

                tool_call["result"] = result["content"]
                tool_call["error"] = result["content"] if result["is_error"] else None
                tool_call["status"] = (
                    ToolCallStatus.ERROR.value if result["is_error"]
                    else ToolCallStatus.SUCCESS.value
                )

                await self._send({
                    "type": WSMessageType.TOOL_CALL_RESULT,
                    "toolCall": {
                        "id": tool_call["id"],
                        "name": tool_call["name"],
                        "result": result["content"],
                        "isError": result["is_error"],
                    },
                })

            if round_text or round_tool_calls:
                current_messages.append({
                    "role": "assistant",
                    "content": round_text,
                    "tool_calls": [
                        {"id": tc["id"], "name": tc["name"], "input": tc["input"]}
                        for tc in round_tool_calls
                    ],
                })

            for tc in round_tool_calls:
                current_messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tc.get("result", ""),
                })

        await self._save_message(
            session_id,
            "assistant",
            full_response,
            tool_calls=tool_calls if tool_calls else None,
        )

        await self._send({
            "type": WSMessageType.MESSAGE_COMPLETE,
            "messageId": f"msg_{secrets.token_urlsafe(8)}",
            "content": full_response,
            "toolCalls": [
                {
                    "id": tc["id"],
                    "name": tc["name"],
                    "arguments": tc["input"],
                    "result": tc.get("result"),
                    "error": tc.get("error"),
                    "status": tc.get("status", ToolCallStatus.SUCCESS.value),
                }
                for tc in tool_calls
            ] if tool_calls else None,
        })

    def _find_tool_server(self, tool_name: str, tools: list[dict]) -> str | None:
        """Find which MCP server provides a specific tool.

        Args:
            tool_name: Name of the tool to find.
            tools: List of available tools with server metadata.

        Returns:
            Server ID that provides the tool, or None if not found.
        """
        for tool in tools:
            if tool.get("name") == tool_name:
                return tool.get("server_id")
        return None

    def _format_history(self, messages: list[dict]) -> list[dict]:
        """Format message history for LLM consumption.

        Handles both camelCase (from database) and snake_case formats,
        normalizing tool call structures for the LLM bridge.

        Args:
            messages: Raw message history from the database.

        Returns:
            Formatted message history for LLM API calls.
        """
        formatted = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "tool":
                tool_call_id = msg.get("toolCallId") or msg.get("tool_call_id", "")
                formatted.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": content,
                })
            elif msg.get("toolCalls") or msg.get("tool_calls"):
                tool_calls = msg.get("toolCalls") or msg.get("tool_calls", [])
                normalized_tool_calls = [
                    {
                        "id": tc.get("id", ""),
                        "name": tc.get("name", ""),
                        "input": tc.get("arguments") or tc.get("input", {}),
                    }
                    for tc in tool_calls
                ]
                formatted.append({
                    "role": role,
                    "content": content,
                    "tool_calls": normalized_tool_calls,
                })
            else:
                formatted.append({"role": role, "content": content})

        return formatted

    def _build_system_prompt(self, tools: list[dict]) -> str:
        """Build the system prompt with MCP tool context.

        Args:
            tools: List of available MCP tools.

        Returns:
            System prompt string with tool information appended.
        """
        prompt = """You are an AI assistant helping manage infrastructure through Hydra.
You have access to tools that let you query and control infrastructure.

When using tools:
- Be precise with parameters
- Check results before making changes
- Explain what you're doing

Available tools are from connected MCP servers for infrastructure management."""

        if tools:
            tool_names = [t.get("name") for t in tools if t.get("name")]
            if tool_names:
                prompt += f"\n\nAvailable tools: {', '.join(tool_names)}"

        return prompt

    async def _save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_calls: list[dict] | None = None,
    ):
        """Persist a message to the database.

        Args:
            session_id: Chat session identifier.
            role: Message role (user, assistant, tool).
            content: Message content text.
            tool_calls: Optional list of tool calls made in this message.
        """
        now = datetime.now(timezone.utc)
        message_id = f"msg_{secrets.token_urlsafe(8)}"

        last_message = await self.mongodb.chat_messages.find_one(
            {"sessionId": session_id},
            sort=[("order", -1)],
        )
        next_order = (last_message["order"] + 1) if last_message else 0

        doc = {
            "messageId": message_id,
            "sessionId": session_id,
            "role": role,
            "content": content,
            "toolCalls": (
                [
                    {
                        "id": tc["id"],
                        "serverId": tc.get("server_id", ""),
                        "serverName": tc.get("server_name"),
                        "name": tc["name"],
                        "arguments": tc["input"],
                        "result": tc.get("result"),
                        "error": tc.get("error"),
                        "status": tc.get("status", ToolCallStatus.PENDING.value),
                    }
                    for tc in tool_calls
                ]
                if tool_calls
                else None
            ),
            "order": next_order,
            "createdAt": now,
        }

        await self.mongodb.chat_messages.insert_one(doc)

        await self.mongodb.chat_sessions.update_one(
            {"sessionId": session_id},
            {"$set": {"lastMessageAt": now, "updatedAt": now}},
        )

    async def _send(self, data: dict):
        """Send a JSON message to the WebSocket client.

        Args:
            data: Message data to send.
        """
        await self.websocket.send_json(data)

    async def _send_error(self, error: str):
        """Send an error message to the WebSocket client.

        Args:
            error: Error message string.
        """
        await self._send({"type": WSMessageType.ERROR, "error": error})


async def get_user_from_token(websocket: WebSocket) -> dict | None:
    """Extract and verify user from WebSocket authentication.

    Checks for JWT token in query parameters or Authorization header.

    Args:
        websocket: The WebSocket connection instance.

    Returns:
        Decoded user payload if valid, None otherwise.
    """
    token = websocket.query_params.get("token")

    if not token:
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if not token:
        return None

    try:
        payload = decode_token(token)
        return payload
    except Exception:
        return None


@router.websocket("/chat/ws")
async def chat_websocket(
    websocket: WebSocket,
    mongodb: MongoDB = Depends(get_mongodb),
):
    """WebSocket endpoint for real-time chat with streaming LLM responses.

    Authenticates via JWT token in query parameter or Authorization header.
    Supports bidirectional communication for chat requests, cancellation, and ping/pong.

    Args:
        websocket: The WebSocket connection instance.
        mongodb: MongoDB database dependency.

    Connection:
        - Query param: ws://host/api/v1/chat/ws?token=<jwt>
        - Header: Authorization: Bearer <jwt>

    Client Messages:
        - chat_request: {type, sessionId, content, providerId?}
        - cancel: {type: "cancel"}
        - ping: {type: "ping"}

    Server Messages:
        - text_delta: Streaming text chunks
        - tool_call_start: Tool execution started
        - tool_call_result: Tool execution completed
        - message_complete: Full message with all tool calls
        - error: Error occurred
        - pong: Response to ping
    """
    user = await get_user_from_token(websocket)

    if not user:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    if user.get("type") == "agent":
        await websocket.close(code=4003, reason="Agents cannot use chat")
        return

    await websocket.accept()

    handler = ChatWebSocketHandler(
        websocket=websocket,
        user_id=user["user_id"],
        mongodb=mongodb,
    )

    logger.info("websocket_connected", user_id=user["user_id"])

    await handler.handle()
