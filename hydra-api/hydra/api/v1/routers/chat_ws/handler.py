"""Chat request handling and streaming for the chat WebSocket endpoint."""


import contextlib
import secrets
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import WebSocket, WebSocketDisconnect
from pymongo import ReturnDocument

from hydra.api.v1.models.chat import ToolCallStatus
from hydra.api.v1.models.notifications import NotificationSource, NotificationType, SourceComponent
from hydra.api.v1.services.chat import ChatService, ChatSessionNotFoundError
from hydra.api.v1.services.chat_cache import ChatCacheService
from hydra.api.v1.services.conversation import ConversationBuilder
from hydra.api.v1.services.llm_bridge import LLMBridge, LLMConfigError
from hydra.api.v1.services.mcp_client import MCPClient, MCPClientError
from hydra.api.v1.services.notifications import emit_notification
from hydra.db.mongodb import MongoDB
from hydra.db.redis import get_redis

from .types import WSMessageType

logger = structlog.get_logger(__name__)


class ChatWebSocketHandler:
    """Handle chat WebSocket messages, streaming, and persistence."""

    def __init__(
        self,
        websocket: WebSocket,
        user_id: str,
        mongodb: MongoDB,
    ):
        self.websocket = websocket
        self.user_id = user_id
        self.mongodb = mongodb
        self.chat_service = ChatService(mongodb)
        self.llm_bridge = LLMBridge(mongodb)
        self.mcp_client = MCPClient(mongodb)
        self.cache_service = ChatCacheService(mongodb=mongodb)
        self._cancelled = False

    async def handle(self) -> None:
        """Process incoming WebSocket messages until the connection closes."""
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
        except Exception as exc:
            logger.exception("websocket_error", user_id=self.user_id, error=str(exc))
            with contextlib.suppress(Exception):
                await emit_notification(
                    NotificationType.WEBSOCKET_FAILURE,
                    NotificationSource(component=SourceComponent.HYDRA_API, service="chat_ws"),
                    "WebSocket failure",
                    f"WebSocket error: {str(exc)}",
                )
            await self._send_error(str(exc))

    @staticmethod
    def _parse_request_config(data: dict[str, Any]) -> tuple[dict[str, Any], str, bool]:
        """Parse model configuration and feature flags from a request."""
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
        session: dict[str, Any],
        provider_id: str | None,
        model_config: dict[str, Any],
        reasoning_level: str,
        web_search_enabled: bool,
    ) -> None:
        """Prepare conversation context and stream an LLM response."""
        active_provider_id = provider_id or session.get("llm_provider_id")
        if not active_provider_id:
            await self._send_error("No LLM provider configured for session")
            return

        provider_config = await self.llm_bridge.get_config(active_provider_id, self.user_id)

        mcp_server_ids = session.get("mcp_server_ids", [])
        tools: list[dict[str, Any]] = []
        if mcp_server_ids:
            tools = await self.mcp_client.get_all_tools_for_session(mcp_server_ids, self.user_id)

        system_prompt = self._build_system_prompt(tools)

        thread, _total = await self.chat_service.list_messages(
            session_id,
            self.user_id,
            limit=1000,
            order="asc",
        )

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

        formatted_messages = self._format_history(conversation.messages)

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

    async def _handle_chat_request(self, data: dict[str, Any]) -> None:
        """Process a chat request with LLM completion and MCP tool support."""
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
        except LLMConfigError as exc:
            await self._send_error(f"LLM config error: {exc.message}")
            with contextlib.suppress(Exception):
                await emit_notification(
                    NotificationType.LLM_PROVIDER_FAILURE,
                    NotificationSource(component=SourceComponent.HYDRA_API, service="chat_ws"),
                    "LLM provider failure",
                    f"LLM provider error: {str(exc)}",
                )
        except MCPClientError as exc:
            await self._send_error(f"MCP error: {exc.message}")
        except Exception as exc:
            logger.exception("chat_request_error", session_id=session_id, error=str(exc))
            await self._send_error(f"Internal error: {str(exc)}")

    async def _handle_retry_request(self, data: dict[str, Any]) -> None:
        """Retry generating a response for an orphaned user message."""
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
        except LLMConfigError as exc:
            await self._send_error(f"LLM config error: {exc.message}")
            with contextlib.suppress(Exception):
                await emit_notification(
                    NotificationType.LLM_PROVIDER_FAILURE,
                    NotificationSource(component=SourceComponent.HYDRA_API, service="chat_ws"),
                    "LLM provider failure",
                    f"LLM provider error: {str(exc)}",
                )
        except MCPClientError as exc:
            await self._send_error(f"MCP error: {exc.message}")
        except Exception as exc:
            logger.exception(
                "retry_request_error",
                session_id=session_id,
                message_id=message_id,
                error=str(exc),
            )
            await self._send_error(f"Internal error: {str(exc)}")

    async def _stream_llm_response(
        self,
        session_id: str,
        provider_config: dict[str, Any],
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system_prompt: str,
        mcp_server_ids: list[str],
        model_config: dict[str, Any] | None = None,
        reasoning_level: str = "none",
        web_search_enabled: bool = False,
        conversation_token_count: int = 0,
        context_window: int = 0,
    ) -> None:
        """Stream an LLM response with iterative tool execution support."""
        full_response = ""
        tool_calls: list[dict[str, Any]] = []
        max_tool_rounds = 10
        total_tool_calls = 0

        current_messages = messages.copy()

        for _ in range(max_tool_rounds):
            if self._cancelled:
                await self._send({"type": WSMessageType.ERROR, "error": "Cancelled"})
                return

            round_text = ""
            round_tool_calls: list[dict[str, Any]] = []
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
                        "server_id": self._find_tool_server(event.get("name"), tools),  # type: ignore[arg-type]
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
                    with contextlib.suppress(Exception):
                        await emit_notification(
                            NotificationType.LLM_PROVIDER_FAILURE,
                            NotificationSource(component=SourceComponent.HYDRA_API, service="chat_ws"),
                            "LLM provider failure",
                            f"LLM provider error: {error_msg}",
                        )
                    return
                elif event_type == "done":
                    break

            if not round_tool_calls:
                if round_text:
                    await self._save_message(session_id, "assistant", round_text)
                break

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
                    tool_call,
                    mcp_server_ids,
                    self.user_id,
                )
                tool_call["result"] = result["content"]
                tool_call["error"] = result["content"] if result["is_error"] else None
                tool_call["status"] = (
                    ToolCallStatus.ERROR.value
                    if result["is_error"]
                    else ToolCallStatus.SUCCESS.value
                )

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

        output_tokens = len(full_response) // 4 + 1 if full_response else 0
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

    def _find_tool_server(self, tool_name: str, tools: list[dict[str, Any]]) -> str | None:
        """Find which MCP server provides a specific tool."""
        for tool in tools:
            if tool.get("name") == tool_name:
                return tool.get("server_id")
        return None

    def _format_history(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Format message history for LLM consumption."""
        tool_response_ids: set[str] = set()
        for msg in messages:
            if msg.get("role") == "tool":
                tool_call_id = msg.get("toolCallId") or msg.get("tool_call_id", "")
                if tool_call_id:
                    tool_response_ids.add(tool_call_id)

        included_tool_call_ids: set[str] = set()
        formatted = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "tool":
                continue

            if msg.get("toolCalls") or msg.get("tool_calls"):
                tool_calls = msg.get("toolCalls") or msg.get("tool_calls", [])
                valid_tool_calls = []
                for tool_call in tool_calls:
                    tool_call_id = tool_call.get("id", "")
                    if tool_call_id in tool_response_ids:
                        valid_tool_calls.append({
                            "id": tool_call_id,
                            "name": tool_call.get("name", ""),
                            "input": tool_call.get("arguments") or tool_call.get("input", {}),
                        })
                        included_tool_call_ids.add(tool_call_id)

                if valid_tool_calls:
                    formatted.append({
                        "role": role,
                        "content": content,
                        "tool_calls": valid_tool_calls,
                    })
                elif content:
                    formatted.append({"role": role, "content": content})
            else:
                formatted.append({"role": role, "content": content})

        result = []
        tool_messages = [
            msg for msg in messages
            if msg.get("role") == "tool"
            and (msg.get("toolCallId") or msg.get("tool_call_id", "")) in included_tool_call_ids
        ]
        tool_msg_index = 0

        for formatted_message in formatted:
            result.append(formatted_message)
            if formatted_message.get("tool_calls"):
                tool_call_ids_in_msg = {tool_call["id"] for tool_call in formatted_message["tool_calls"]}
                while tool_msg_index < len(tool_messages):
                    tool_message = tool_messages[tool_msg_index]
                    tool_call_id = tool_message.get("toolCallId") or tool_message.get("tool_call_id", "")
                    if tool_call_id in tool_call_ids_in_msg:
                        result.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": tool_message.get("content", ""),
                        })
                        tool_msg_index += 1
                    else:
                        break

        return result

    def _build_system_prompt(self, tools: list[dict[str, Any]]) -> str:
        """Build the system prompt with MCP tool context."""
        prompt = """You are an AI assistant helping manage infrastructure through Hydra.
You have access to tools that let you query and control infrastructure.

When using tools:
- Be precise with parameters
- Check results before making changes
- Explain what you're doing

Available tools are from connected MCP servers for infrastructure management."""

        if tools:
            tool_names = [tool.get("name") for tool in tools if tool.get("name")]
            if tool_names:
                prompt += f"\n\nAvailable tools: {', '.join(tool_names)}"  # type: ignore[arg-type]

        return prompt

    async def _save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_call_id: str | None = None,
    ) -> None:
        """Persist a message and append it to the cache."""
        now = datetime.now(UTC)
        message_id = f"msg_{secrets.token_urlsafe(8)}"

        session_result = await self.mongodb.chat_sessions.find_one_and_update(
            {"sessionId": session_id},
            {
                "$set": {"lastMessageAt": now, "updatedAt": now},
                "$push": {"sessionContext.thread": message_id},
                "$inc": {"sessionContext.messageCount": 1},
            },
            return_document=ReturnDocument.BEFORE,
        )
        next_order = session_result.get("sessionContext", {}).get("messageCount", 0) if session_result else 0

        doc = {
            "messageId": message_id,
            "sessionId": session_id,
            "role": role,
            "content": content,
            "toolCalls": (
                [
                    {
                        "id": tool_call["id"],
                        "serverId": tool_call.get("server_id", ""),
                        "serverName": tool_call.get("server_name"),
                        "name": tool_call["name"],
                        "arguments": tool_call["input"],
                        "result": tool_call.get("result"),
                        "error": tool_call.get("error"),
                        "status": tool_call.get("status", ToolCallStatus.PENDING.value),
                    }
                    for tool_call in tool_calls
                ]
                if tool_calls
                else None
            ),
            "toolCallId": tool_call_id,
            "order": next_order,
            "createdAt": now,
        }

        await self.mongodb.chat_messages.insert_one(doc)

        await self.cache_service.append_message_to_cache(session_id, {
            "message_id": message_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "tool_calls": doc.get("toolCalls"),
            "order": next_order,
            "created_at": now.isoformat(),
        })

    async def _send(self, data: dict[str, Any]) -> None:
        """Send a JSON message to the WebSocket client."""
        await self.websocket.send_json(data)

    async def _send_error(self, error: str) -> None:
        """Send an error message to the WebSocket client."""
        await self._send({"type": WSMessageType.ERROR, "error": error})

    async def _update_session_context(
        self,
        session_id: str,
        provider_config: dict[str, Any],
        tool_calls_count: int,
        conversation_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        """Update session context and lock the chosen LLM config."""
        now = datetime.now(UTC)
        update_ops: dict[str, Any] = {
            "$set": {
                "llmConfigLocked": True,
                "sessionContext.modelUsed": provider_config.get("model"),
                "sessionContext.providerType": provider_config.get("type"),
                "sessionContext.inputTokens": conversation_tokens,
                "sessionContext.totalTokens": conversation_tokens,
                "updatedAt": now,
            },
        }

        inc_ops = {}
        if tool_calls_count > 0:
            inc_ops["sessionContext.toolCallsCount"] = tool_calls_count
        if output_tokens > 0:
            inc_ops["sessionContext.outputTokens"] = output_tokens

        if inc_ops:
            update_ops["$inc"] = inc_ops

        await self.mongodb.chat_sessions.update_one({"sessionId": session_id}, update_ops)
