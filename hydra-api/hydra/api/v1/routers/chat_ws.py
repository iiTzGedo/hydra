"""WebSocket endpoint for real-time chat with LLM and MCP integration."""

import asyncio
import inspect
import json
import secrets
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pymongo import ReturnDocument

from hydra.api.v1.core.security import decode_token
from hydra.api.v1.models.chat import ToolCallStatus
from hydra.api.v1.models.notifications import NOTIFICATION_CHANNEL, NotificationSource, NotificationType, SourceComponent
from hydra.api.v1.services.chat import ChatService, ChatSessionNotFoundError
from hydra.api.v1.services.chat_cache import ChatCacheService
from hydra.api.v1.services.conversation import ConversationBuilder
from hydra.api.v1.services.llm_bridge import LLMBridge, LLMConfigError
from hydra.api.v1.services.mcp_client import MCPClient, MCPClientError
from hydra.api.v1.services.notifications import emit_notification, should_deliver
from hydra.api.v1.models.settings import NotificationSettings
from hydra.api.v1.core.role_utils import get_active_temporary_roles
from hydra.db.mongodb import MongoDB, get_mongodb
from hydra.db.redis import RedisClient, get_redis

router = APIRouter(tags=["Chat WebSocket"])
logger = structlog.get_logger(__name__)


class WSMessageType:
    """WebSocket message types for client-server communication."""

    # Client -> Server
    AUTHENTICATE = "authenticate"
    CHAT_REQUEST = "chat_request"
    RETRY_MESSAGE = "retry_message"  # Retry generating response for orphaned user message
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
        self.cache_service = ChatCacheService(mongodb=mongodb)
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

                elif msg_type == WSMessageType.RETRY_MESSAGE:
                    self._cancelled = False
                    await self._handle_retry_request(data)

                else:
                    await self._send_error(f"Unknown message type: {msg_type}")

        except WebSocketDisconnect:
            logger.info("websocket_disconnected", user_id=self.user_id)
        except Exception as e:
            logger.exception("websocket_error", user_id=self.user_id, error=str(e))
            try:
                await emit_notification(
                    NotificationType.WEBSOCKET_FAILURE,
                    NotificationSource(component=SourceComponent.HYDRA_API, service="chat_ws"),
                    "WebSocket failure",
                    f"WebSocket error: {str(e)}",
                )
            except Exception:
                pass
            await self._send_error(str(e))

    @staticmethod
    def _parse_request_config(data: dict) -> tuple[dict, str, bool]:
        """Parse model configuration and feature flags from a request.

        Extracts model parameters, reasoning level (with legacy fallback),
        and web search flag from the incoming WebSocket message data.

        Args:
            data: Raw request data from WebSocket message.

        Returns:
            Tuple of (model_config dict, reasoning_level str, web_search_enabled bool).
        """
        # Support both level-based (new) and boolean (legacy) reasoning config
        reasoning_level = data.get("reasoningLevel", "none")
        if data.get("reasoningEnabled", False) and reasoning_level == "none":
            reasoning_level = "medium"
        web_search_enabled = data.get("webSearchEnabled", False)

        model_config_data = data.get("modelConfig", {})
        model_config = {
            "max_tokens": model_config_data.get("maxTokens"),
            "temperature": model_config_data.get("temperature"),
            "top_p": model_config_data.get("topP"),
            "top_k": model_config_data.get("topK"),
            "frequency_penalty": model_config_data.get("frequencyPenalty"),
            "presence_penalty": model_config_data.get("presencePenalty"),
        }

        return model_config, reasoning_level, web_search_enabled

    async def _prepare_and_stream(
        self,
        session_id: str,
        session: dict,
        provider_id: str | None,
        model_config: dict,
        reasoning_level: str,
        web_search_enabled: bool,
    ):
        """Prepare provider, tools, conversation context and stream LLM response.

        Shared logic between chat requests and retry requests. Handles provider
        lookup, MCP tool gathering, conversation building with summarization,
        and streaming the LLM response.

        Args:
            session_id: Chat session identifier.
            session: Session document from the database.
            provider_id: Optional provider ID override (from request).
            model_config: Model parameters (max_tokens, temperature, etc.).
            reasoning_level: Extended thinking level.
            web_search_enabled: Whether to enable web search.
        """
        active_provider_id = provider_id or session.get("llm_provider_id")
        if not active_provider_id:
            await self._send_error("No LLM provider configured for session")
            return

        provider_config = await self.llm_bridge.get_config(
            active_provider_id, self.user_id
        )

        mcp_server_ids = session.get("mcp_server_ids", [])
        tools = []
        if mcp_server_ids:
            tools = await self.mcp_client.get_all_tools_for_session(
                mcp_server_ids, self.user_id
            )

        system_prompt = self._build_system_prompt(tools)

        # Get all messages (thread) for conversation building
        thread, _total = await self.chat_service.list_messages(
            session_id, self.user_id, limit=1000, order="asc"
        )

        # Build conversation with sliding window and summarization
        provider_type = str(provider_config.get("type", "")).lower()
        model_name = provider_config.get("model", "")

        conversation_builder = ConversationBuilder(
            provider=provider_type,
            model=model_name,
            redis=get_redis(),
            llm_bridge=self.llm_bridge,
        )

        conversation = await conversation_builder.build(
            thread=thread,
            system_prompt=system_prompt,
            session_id=session_id,
        )

        # Format messages for the provider
        formatted_messages = self._format_history(conversation.messages)

        # Use system prompt with summary for Anthropic, otherwise add summary to messages
        effective_system_prompt = system_prompt
        if conversation.summary and provider_type == "anthropic":
            effective_system_prompt = conversation.get_system_prompt_with_summary()
        elif conversation.summary:
            formatted_messages.insert(0, {
                "role": "system",
                "content": f"[Previous conversation summary]\n{conversation.summary}",
            })

        await self._stream_llm_response(
            session_id=session_id,
            provider_config=provider_config,
            messages=formatted_messages,
            tools=tools,
            system_prompt=effective_system_prompt,
            mcp_server_ids=mcp_server_ids,
            model_config=model_config,
            reasoning_level=reasoning_level,
            web_search_enabled=web_search_enabled,
            conversation_token_count=conversation.token_count,
            context_window=conversation.context_window,
        )

    async def _handle_chat_request(self, data: dict):
        """Process a chat request with LLM completion and MCP tool support.

        Args:
            data: Request data containing sessionId, content, providerId, modelConfig, and feature flags.
        """
        session_id = data.get("sessionId")
        message_content = data.get("content", "")
        provider_id = data.get("providerId")
        model_config, reasoning_level, web_search_enabled = self._parse_request_config(data)

        if not session_id:
            await self._send_error("sessionId is required")
            return

        if not message_content:
            await self._send_error("content is required")
            return

        try:
            session = await self.chat_service.get_session(session_id, self.user_id)

            # Save the user message first
            await self._save_message(session_id, "user", message_content)

            await self._prepare_and_stream(
                session_id=session_id,
                session=session,
                provider_id=provider_id,
                model_config=model_config,
                reasoning_level=reasoning_level,
                web_search_enabled=web_search_enabled,
            )

        except ChatSessionNotFoundError:
            await self._send_error(f"Session not found: {session_id}")
        except LLMConfigError as e:
            await self._send_error(f"LLM config error: {e.message}")
            try:
                await emit_notification(
                    NotificationType.LLM_PROVIDER_FAILURE,
                    NotificationSource(component=SourceComponent.HYDRA_API, service="chat_ws"),
                    "LLM provider failure",
                    f"LLM provider error: {str(e)}",
                )
            except Exception:
                pass
        except MCPClientError as e:
            await self._send_error(f"MCP error: {e.message}")
        except Exception as e:
            logger.exception("chat_request_error", session_id=session_id, error=str(e))
            await self._send_error(f"Internal error: {str(e)}")

    async def _handle_retry_request(self, data: dict):
        """Retry generating a response for an orphaned user message.

        This is used when a user message was saved but no assistant response was
        received (e.g., due to network error, timeout, or cancelled request).
        Unlike chat_request, this does NOT create a new user message.

        Args:
            data: Request data containing sessionId, messageId, providerId, modelConfig, and feature flags.
        """
        session_id = data.get("sessionId")
        message_id = data.get("messageId")
        provider_id = data.get("providerId")
        model_config, reasoning_level, web_search_enabled = self._parse_request_config(data)

        if not session_id:
            await self._send_error("sessionId is required")
            return

        if not message_id:
            await self._send_error("messageId is required for retry")
            return

        try:
            session = await self.chat_service.get_session(session_id, self.user_id)

            # Verify the message exists and is from the user
            message = await self.mongodb.chat_messages.find_one({
                "messageId": message_id,
                "sessionId": session_id,
            })

            if not message:
                await self._send_error(f"Message not found: {message_id}")
                return

            if message.get("role") != "user":
                await self._send_error("Can only retry user messages")
                return

            # Verify this is the last message (no assistant response after it)
            message_order = message.get("order", 0)
            later_messages = await self.mongodb.chat_messages.count_documents({
                "sessionId": session_id,
                "order": {"$gt": message_order},
                "role": {"$in": ["assistant", "tool"]},
            })

            if later_messages > 0:
                await self._send_error("Message already has a response - cannot retry")
                return

            await self._prepare_and_stream(
                session_id=session_id,
                session=session,
                provider_id=provider_id,
                model_config=model_config,
                reasoning_level=reasoning_level,
                web_search_enabled=web_search_enabled,
            )

        except ChatSessionNotFoundError:
            await self._send_error(f"Session not found: {session_id}")
        except LLMConfigError as e:
            await self._send_error(f"LLM config error: {e.message}")
            try:
                await emit_notification(
                    NotificationType.LLM_PROVIDER_FAILURE,
                    NotificationSource(component=SourceComponent.HYDRA_API, service="chat_ws"),
                    "LLM provider failure",
                    f"LLM provider error: {str(e)}",
                )
            except Exception:
                pass
        except MCPClientError as e:
            await self._send_error(f"MCP error: {e.message}")
        except Exception as e:
            logger.exception("retry_request_error", session_id=session_id, message_id=message_id, error=str(e))
            await self._send_error(f"Internal error: {str(e)}")

    async def _stream_llm_response(
        self,
        session_id: str,
        provider_config: dict,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
        mcp_server_ids: list[str],
        model_config: dict | None = None,
        reasoning_level: str = "none",
        web_search_enabled: bool = False,
        conversation_token_count: int = 0,
        context_window: int = 0,
    ):
        """Stream LLM response with iterative tool execution support.

        Handles multiple rounds of tool calls up to max_tool_rounds limit.
        Also tracks session context (tokens, costs, tool calls) and locks
        the LLM config after the first assistant response.

        Args:
            session_id: Chat session identifier.
            provider_config: LLM provider configuration.
            messages: Conversation history.
            tools: Available MCP tools.
            system_prompt: System prompt for the LLM.
            mcp_server_ids: Connected MCP server IDs.
            model_config: Optional model parameters (max_tokens, temperature, etc.).
            reasoning_level: Extended thinking level ('none', 'low', 'medium', 'high').
            web_search_enabled: Whether to enable web search capability.
            conversation_token_count: Token count of the input conversation.
            context_window: The model's context window size.
        """
        full_response = ""
        tool_calls: list[dict] = []
        max_tool_rounds = 10
        total_tool_calls = 0

        current_messages = messages.copy()

        for _ in range(max_tool_rounds):
            if self._cancelled:
                await self._send({"type": WSMessageType.ERROR, "error": "Cancelled"})
                return

            round_text = ""
            round_tool_calls: list[dict] = []

            # Unpack model_config parameters (all optional)
            config = model_config or {}
            async for event in self.llm_bridge.stream_completion(
                provider_config=provider_config,
                messages=current_messages,
                tools=tools if tools else None,
                system_prompt=system_prompt,
                max_tokens=config.get("max_tokens"),
                temperature=config.get("temperature"),
                top_p=config.get("top_p"),
                top_k=config.get("top_k"),
                frequency_penalty=config.get("frequency_penalty"),
                presence_penalty=config.get("presence_penalty"),
                reasoning_level=reasoning_level,
                web_search_enabled=web_search_enabled,
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
                    total_tool_calls += 1

                    await self._send({
                        "type": WSMessageType.TOOL_CALL_START,
                        "toolCall": {
                            "id": tool_call["id"],
                            "name": tool_call["name"],
                            "arguments": tool_call["input"],
                        },
                    })

                elif event_type == "error":
                    error_msg = event.get("error", "Unknown error")
                    await self._send_error(error_msg)
                    try:
                        await emit_notification(
                            NotificationType.LLM_PROVIDER_FAILURE,
                            NotificationSource(component=SourceComponent.HYDRA_API, service="chat_ws"),
                            "LLM provider failure",
                            f"LLM provider error: {error_msg}",
                        )
                    except Exception:
                        pass
                    return

                elif event_type == "done":
                    break

            if not round_tool_calls:
                # No tool calls in this round - save final text and break
                # Only save if there's unsaved text
                if round_text:
                    await self._save_message(
                        session_id,
                        "assistant",
                        round_text,
                    )
                break

            # Save intermediate assistant message with tool calls to DB
            # (required so tool responses can reference it in history)
            if round_text or round_tool_calls:
                await self._save_message(
                    session_id,
                    "assistant",
                    round_text,
                    tool_calls=round_tool_calls,
                )
                current_messages.append({
                    "role": "assistant",
                    "content": round_text,
                    "tool_calls": [
                        {"id": tc["id"], "name": tc["name"], "input": tc["input"]}
                        for tc in round_tool_calls
                    ],
                })

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

                # Save tool response message to DB
                await self._save_message(
                    session_id,
                    "tool",
                    result["content"],
                    tool_call_id=tool_call["id"],
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

                current_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": result["content"],
                })

        # Estimate output tokens (rough: ~4 chars per token)
        output_tokens = len(full_response) // 4 + 1 if full_response else 0

        # Lock the LLM config and update session context after first assistant response
        await self._update_session_context(
            session_id=session_id,
            provider_config=provider_config,
            tool_calls_count=total_tool_calls,
            conversation_tokens=conversation_token_count,
            output_tokens=output_tokens,
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
            "usage": {
                "inputTokens": conversation_token_count,
                "outputTokens": output_tokens,
                "totalTokens": conversation_token_count + output_tokens,
                "contextWindow": context_window,
            },
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

        Ensures tool_calls and tool responses are properly paired:
        - Tool calls without responses are stripped
        - Tool responses without matching tool calls are stripped

        Args:
            messages: Raw message history from the database.

        Returns:
            Formatted message history for LLM API calls.
        """
        # First pass: collect all tool_call_ids that have responses
        tool_response_ids: set[str] = set()
        for msg in messages:
            if msg.get("role") == "tool":
                tool_call_id = msg.get("toolCallId") or msg.get("tool_call_id", "")
                if tool_call_id:
                    tool_response_ids.add(tool_call_id)

        # Second pass: format non-tool messages and track which tool_calls are kept
        included_tool_call_ids: set[str] = set()
        formatted = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "tool":
                # Skip tool messages in this pass - we'll add them in the third pass
                continue
            elif msg.get("toolCalls") or msg.get("tool_calls"):
                tool_calls = msg.get("toolCalls") or msg.get("tool_calls", [])

                # Only include tool_calls that have corresponding responses
                valid_tool_calls = []
                for tc in tool_calls:
                    tc_id = tc.get("id", "")
                    if tc_id in tool_response_ids:
                        valid_tool_calls.append({
                            "id": tc_id,
                            "name": tc.get("name", ""),
                            "input": tc.get("arguments") or tc.get("input", {}),
                        })
                        included_tool_call_ids.add(tc_id)

                if valid_tool_calls:
                    # Has valid tool calls with responses
                    formatted.append({
                        "role": role,
                        "content": content,
                        "tool_calls": valid_tool_calls,
                    })
                elif content:
                    # No valid tool calls, but has content - treat as regular message
                    formatted.append({"role": role, "content": content})
                # If no content and no valid tool calls, skip the message entirely
            else:
                formatted.append({"role": role, "content": content})

        # Third pass: insert tool messages at correct positions
        # Only include tool messages whose tool_call_id was actually included
        result = []
        tool_messages = [
            msg for msg in messages
            if msg.get("role") == "tool"
            and (msg.get("toolCallId") or msg.get("tool_call_id", "")) in included_tool_call_ids
        ]
        tool_msg_index = 0

        for fmt_msg in formatted:
            result.append(fmt_msg)

            # After an assistant message with tool_calls, insert corresponding tool responses
            if fmt_msg.get("tool_calls"):
                tool_call_ids_in_msg = {tc["id"] for tc in fmt_msg["tool_calls"]}
                while tool_msg_index < len(tool_messages):
                    tool_msg = tool_messages[tool_msg_index]
                    tool_call_id = tool_msg.get("toolCallId") or tool_msg.get("tool_call_id", "")
                    if tool_call_id in tool_call_ids_in_msg:
                        result.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": tool_msg.get("content", ""),
                        })
                        tool_msg_index += 1
                    else:
                        break

        return result

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
        tool_call_id: str | None = None,
    ):
        """Persist a message to the database.

        Args:
            session_id: Chat session identifier.
            role: Message role (user, assistant, tool).
            content: Message content text.
            tool_calls: Optional list of tool calls made in this message (for assistant).
            tool_call_id: Optional tool call ID this message responds to (for tool role).
        """
        now = datetime.now(timezone.utc)
        message_id = f"msg_{secrets.token_urlsafe(8)}"

        # Atomically increment messageCount and get the new value for ordering
        # This prevents race conditions where concurrent messages get the same order
        session_result = await self.mongodb.chat_sessions.find_one_and_update(
            {"sessionId": session_id},
            {
                "$set": {"lastMessageAt": now, "updatedAt": now},
                "$push": {"sessionContext.thread": message_id},
                "$inc": {"sessionContext.messageCount": 1},
            },
            return_document=ReturnDocument.BEFORE,  # Get value BEFORE increment
        )

        # Use the messageCount before increment as the order (0-indexed)
        next_order = session_result.get("sessionContext", {}).get("messageCount", 0) if session_result else 0

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
            "toolCallId": tool_call_id,  # For tool response messages
            "order": next_order,
            "createdAt": now,
        }

        await self.mongodb.chat_messages.insert_one(doc)

        # Append to Redis cache instead of invalidating
        # This maintains cache consistency while preserving cached data
        message_response = {
            "message_id": message_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "tool_calls": doc.get("toolCalls"),
            "order": next_order,
            "created_at": now.isoformat(),
        }
        await self.cache_service.append_message_to_cache(session_id, message_response)

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

    async def _update_session_context(
        self,
        session_id: str,
        provider_config: dict,
        tool_calls_count: int,
        conversation_tokens: int = 0,
        output_tokens: int = 0,
    ):
        """Update session context and lock the LLM config after first response.

        Uses dot notation to update specific fields without overwriting the
        entire sessionContext (which would destroy the thread array).

        Note on token tracking:
        - conversationTokens (inputTokens): SET to current conversation window size
          This reflects the sliding window - not accumulated, but current state
        - outputTokens: INCREMENT to track total output generated in this session
        - totalTokens: SET to conversationTokens (current context usage)

        Args:
            session_id: Chat session identifier.
            provider_config: LLM provider configuration with model and type.
            tool_calls_count: Number of tool calls made in this response.
            conversation_tokens: Current conversation window token count (sliding window).
            output_tokens: Number of output tokens generated in this response.
        """
        now = datetime.now(timezone.utc)

        # Use dot notation to update specific context fields without overwriting thread array
        # Note: messageCount is already incremented by _save_message via $inc
        update_ops: dict = {
            "$set": {
                "llmConfigLocked": True,
                "sessionContext.modelUsed": provider_config.get("model"),
                "sessionContext.providerType": provider_config.get("type"),
                # SET inputTokens to current conversation window (not accumulated)
                # This reflects the sliding window conversation concept
                "sessionContext.inputTokens": conversation_tokens,
                "sessionContext.totalTokens": conversation_tokens,
                "updatedAt": now,
            },
        }

        # Increment tool calls count and output tokens (these ARE accumulated)
        inc_ops = {}
        if tool_calls_count > 0:
            inc_ops["sessionContext.toolCallsCount"] = tool_calls_count
        if output_tokens > 0:
            inc_ops["sessionContext.outputTokens"] = output_tokens

        if inc_ops:
            update_ops["$inc"] = inc_ops

        await self.mongodb.chat_sessions.update_one(
            {"sessionId": session_id},
            update_ops,
        )


async def _notification_listener(
    websocket: WebSocket,
    redis_client: RedisClient,
    mongodb: MongoDB,
    user_id: str,
    user_roles: list[str],
) -> None:
    """Subscribe to Redis notification channel and push matching notifications to the WebSocket.

    Runs as a concurrent task alongside the chat message handler. Filters
    notifications by the connected user's roles and targeted user ID.

    Args:
        websocket: The WebSocket connection to push notifications to.
        redis_client: Redis client for pub/sub subscription.
        user_id: Connected user's ID.
        user_roles: Connected user's roles for filtering.
    """
    pubsub = None
    settings_doc = await mongodb.user_settings.find_one(
        {"userId": user_id},
        {"notifications": 1, "_id": 0},
    )
    notif_settings = (
        NotificationSettings.model_validate(settings_doc["notifications"])
        if settings_doc and settings_doc.get("notifications") is not None
        else NotificationSettings()
    )
    try:
        pubsub = await redis_client.subscribe(NOTIFICATION_CHANNEL)
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue

            try:
                data = json.loads(message["data"])
            except (json.JSONDecodeError, TypeError):
                continue

            # Filter: check if this notification targets the connected user
            target_roles = data.get("targetRoles", [])
            target_user_id = data.get("targetUserId")

            # Match if: user is explicitly targeted, OR user has a matching role
            user_targeted = target_user_id == user_id if target_user_id else False
            role_match = bool(set(user_roles) & set(target_roles))

            if not user_targeted and not role_match:
                continue

            if not should_deliver(notif_settings, data, "browser"):
                continue

            # Push to WebSocket
            try:
                await websocket.send_json({
                    "type": WSMessageType.NOTIFICATION,
                    "data": data,
                })
            except Exception:
                # WebSocket likely closed; exit the listener
                break
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.debug("notification_listener_stopped", user_id=user_id, exc_info=True)
    finally:
        if pubsub:
            try:
                await pubsub.unsubscribe(NOTIFICATION_CHANNEL)
                await pubsub.close()
            except Exception:
                pass


def _verify_token(token: str) -> dict | None:
    """Verify a JWT token and return the decoded payload.

    Args:
        token: JWT token string.

    Returns:
        Decoded payload if valid, None otherwise.
    """
    try:
        payload = decode_token(token)
        logger.info("ws_auth_success", user_id=payload.get("sub"))
        return payload
    except Exception as e:
        logger.warning("ws_auth_token_invalid", error=str(e))
        return None


async def _authenticate_from_connection(websocket: WebSocket) -> dict | None:
    """Try to authenticate from query parameters or headers (legacy support).

    Args:
        websocket: The WebSocket connection instance.

    Returns:
        Decoded user payload if valid, None if no token found in connection params.
    """
    token = websocket.query_params.get("token")
    if not token:
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if not token:
        return None

    return _verify_token(token)


async def get_user_from_token(websocket: WebSocket) -> dict | None:
    """Extract and verify user from WebSocket query params or Authorization header.

    Public API used by other WebSocket endpoints (e.g., notifications).

    Args:
        websocket: The WebSocket connection instance.

    Returns:
        Decoded user payload if valid, None otherwise.
    """
    return await _authenticate_from_connection(websocket)


async def _authenticate_from_message(websocket: WebSocket) -> dict | None:
    """Wait for an authenticate message from the client after connection.

    Expects the first message to be: { type: 'authenticate', token: '<jwt>' }
    Times out after 10 seconds.

    Args:
        websocket: The accepted WebSocket connection.

    Returns:
        Decoded user payload if valid, None otherwise.
    """
    try:
        data = await asyncio.wait_for(websocket.receive_json(), timeout=10.0)
    except asyncio.TimeoutError:
        logger.warning("ws_auth_timeout")
        return None
    except Exception as e:
        logger.warning("ws_auth_receive_error", error=str(e))
        return None

    if data.get("type") != WSMessageType.AUTHENTICATE:
        logger.warning("ws_auth_unexpected_message", msg_type=data.get("type"))
        return None

    token = data.get("token")
    if not token:
        logger.warning("ws_auth_no_token_in_message")
        return None

    return _verify_token(token)


@router.websocket("/chat/ws")
async def chat_websocket(
    websocket: WebSocket,
    mongodb: MongoDB = Depends(get_mongodb),
):
    """WebSocket endpoint for real-time chat with streaming LLM responses.

    Authenticates via message-based auth (preferred) or legacy query param/header.
    Supports bidirectional communication for chat requests, cancellation, and ping/pong.

    Args:
        websocket: The WebSocket connection instance.
        mongodb: MongoDB database dependency.

    Authentication:
        - Preferred: Connect without token, send { type: 'authenticate', token: '<jwt>' }
        - Legacy: Query param ws://host/api/v1/chat/ws?token=<jwt>
        - Legacy: Header Authorization: Bearer <jwt>

    Client Messages:
        - authenticate: {type, token} (first message for message-based auth)
        - chat_request: {type, sessionId, content, providerId?}
        - cancel: {type: "cancel"}
        - ping: {type: "ping"}

    Server Messages:
        - authenticated: Confirms successful authentication
        - text_delta: Streaming text chunks
        - tool_call_start: Tool execution started
        - tool_call_result: Tool execution completed
        - message_complete: Full message with all tool calls
        - error: Error occurred
        - pong: Response to ping
    """
    # Try legacy auth from query params/headers first
    user = await _authenticate_from_connection(websocket)
    needs_message_auth = user is None

    if user and user.get("sub_type") == "agent":
        await websocket.close(code=4003, reason="Agents cannot use chat")
        return

    if not needs_message_auth and not user:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()

    # If no token in connection, wait for message-based auth
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

    # Send authenticated confirmation
    await websocket.send_json({"type": WSMessageType.AUTHENTICATED})

    handler = ChatWebSocketHandler(
        websocket=websocket,
        user_id=user["sub"],
        mongodb=mongodb,
    )

    logger.info("websocket_connected", user_id=user["sub"])

    # Start concurrent notification listener for real-time push
    redis_client = get_redis()
    user_doc_result = mongodb.users.find_one(
        {"userId": user["sub"]},
        {"role": 1, "roles": 1, "temporaryRoles": 1},
    )
    user_doc = await user_doc_result if inspect.isawaitable(user_doc_result) else user_doc_result
    if user_doc:
        user_roles = [r for r in [user_doc.get("role")] if r]
        user_roles.extend(user_doc.get("roles", []) or [])
        temp_roles = get_active_temporary_roles(user_doc.get("temporaryRoles", []))
        user_roles.extend([r.get("role") for r in temp_roles if r.get("role")])
    else:
        user_roles = user.get("roles", []) or []
        role = user.get("role")
        if role and role not in user_roles:
            user_roles = [role] + user_roles
    notification_task = asyncio.create_task(
        _notification_listener(websocket, redis_client, mongodb, user["sub"], user_roles)
    )

    try:
        await handler.handle()
    finally:
        notification_task.cancel()
        try:
            await notification_task
        except asyncio.CancelledError:
            pass
