"""LLM Bridge service for streaming LLM provider calls."""

import json
from typing import Any, AsyncIterator

import httpx
import structlog

from hydra.api.v1.core.crypto import decrypt_value
from hydra.api.v1.core.exceptions import ValidationError
from hydra.api.v1.models.ai import LLMProviderType
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)


class LLMProviderError(ValidationError):
    """LLM provider error."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, details or {})


class LLMBridge:
    """Bridge for streaming LLM API calls."""

    def __init__(self, mongodb: MongoDB):
        self.db = mongodb

    async def get_provider_config(self, provider_id: str, user_id: str) -> dict:
        """Get and prepare provider configuration for API calls.

        Args:
            provider_id: The LLM provider identifier.
            user_id: The owner's user identifier.

        Returns:
            Provider config dict with type, api_key, base_url, and model.

        Raises:
            LLMProviderError: If provider not found.
        """
        doc = await self.db.ai_models.find_one({
            "providerId": provider_id,
            "createdBy": user_id,
        })

        if not doc:
            raise LLMProviderError(f"LLM provider not found: {provider_id}")

        api_key = None
        if doc.get("apiKeyEncrypted"):
            api_key = decrypt_value(doc["apiKeyEncrypted"])

        return {
            "provider_id": doc["providerId"],
            "type": LLMProviderType(doc["type"]),
            "api_key": api_key,
            "base_url": doc.get("baseUrl"),
            "model": doc["model"],
        }

    async def stream_completion(
        self,
        provider_config: dict,
        messages: list[dict],
        tools: list[dict] | None = None,
        system_prompt: str | None = None,
        max_tokens: int = 4096,
    ) -> AsyncIterator[dict]:
        """Stream a completion from the configured LLM provider.

        Routes the request to the appropriate provider-specific streaming method
        based on the provider type in the configuration.

        Args:
            provider_config: Provider configuration from get_provider_config.
            messages: Conversation messages in the internal format.
            tools: Optional list of tools available for the model.
            system_prompt: Optional system prompt to prepend.
            max_tokens: Maximum tokens in the response.

        Yields:
            Normalized event dicts with one of:
            - {"type": "text_delta", "text": "..."} for content chunks
            - {"type": "tool_use", "id": "...", "name": "...", "input": {...}} for tool calls
            - {"type": "done", "stop_reason": "..."} when complete
            - {"type": "error", "error": "..."} on failure
        """
        provider_type = provider_config["type"]

        if provider_type == LLMProviderType.ANTHROPIC:
            async for event in self._stream_anthropic(
                provider_config, messages, tools, system_prompt, max_tokens
            ):
                yield event
        elif provider_type == LLMProviderType.OPENAI:
            async for event in self._stream_openai(
                provider_config, messages, tools, system_prompt, max_tokens
            ):
                yield event
        elif provider_type == LLMProviderType.OLLAMA:
            async for event in self._stream_ollama(
                provider_config, messages, system_prompt, max_tokens
            ):
                yield event
        else:
            yield {"type": "error", "error": f"Unsupported provider type: {provider_type}"}

    async def _stream_anthropic(
        self,
        config: dict,
        messages: list[dict],
        tools: list[dict] | None,
        system_prompt: str | None,
        max_tokens: int,
    ) -> AsyncIterator[dict]:
        """Stream from Anthropic's Messages API."""
        if not config.get("api_key"):
            yield {"type": "error", "error": "API key required for Anthropic"}
            return

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": config["api_key"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        body: dict[str, Any] = {
            "model": config["model"],
            "messages": self._format_messages_anthropic(messages),
            "max_tokens": max_tokens,
            "stream": True,
        }

        if system_prompt:
            body["system"] = system_prompt

        if tools:
            body["tools"] = self._format_tools_anthropic(tools)

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                async with client.stream("POST", url, headers=headers, json=body) as response:
                    if response.status_code != 200:
                        error_body = await response.aread()
                        yield {"type": "error", "error": f"Anthropic API error: {error_body.decode()}"}
                        return

                    current_tool_use = None
                    tool_input_buffer = ""

                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue

                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        event_type = data.get("type")

                        if event_type == "content_block_start":
                            block = data.get("content_block", {})
                            if block.get("type") == "tool_use":
                                current_tool_use = {
                                    "id": block.get("id"),
                                    "name": block.get("name"),
                                }
                                tool_input_buffer = ""

                        elif event_type == "content_block_delta":
                            delta = data.get("delta", {})
                            if delta.get("type") == "text_delta":
                                yield {"type": "text_delta", "text": delta.get("text", "")}
                            elif delta.get("type") == "input_json_delta":
                                tool_input_buffer += delta.get("partial_json", "")

                        elif event_type == "content_block_stop":
                            if current_tool_use:
                                try:
                                    tool_input = json.loads(tool_input_buffer) if tool_input_buffer else {}
                                except json.JSONDecodeError:
                                    tool_input = {}
                                yield {
                                    "type": "tool_use",
                                    "id": current_tool_use["id"],
                                    "name": current_tool_use["name"],
                                    "input": tool_input,
                                }
                                current_tool_use = None
                                tool_input_buffer = ""

                        elif event_type == "message_stop":
                            stop_reason = data.get("message", {}).get("stop_reason", "end_turn")
                            yield {"type": "done", "stop_reason": stop_reason}

                        elif event_type == "message_delta":
                            stop_reason = data.get("delta", {}).get("stop_reason")
                            if stop_reason:
                                yield {"type": "done", "stop_reason": stop_reason}

            except httpx.TimeoutException:
                yield {"type": "error", "error": "Request timed out"}
            except Exception as e:
                logger.exception("anthropic_stream_error", error=str(e))
                yield {"type": "error", "error": str(e)}

    async def _stream_openai(
        self,
        config: dict,
        messages: list[dict],
        tools: list[dict] | None,
        system_prompt: str | None,
        max_tokens: int,
    ) -> AsyncIterator[dict]:
        """Stream from OpenAI's Chat Completions API."""
        if not config.get("api_key"):
            yield {"type": "error", "error": "API key required for OpenAI"}
            return

        base_url = config.get("base_url") or "https://api.openai.com/v1"
        url = f"{base_url.rstrip('/')}/chat/completions"

        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        }

        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})
        formatted_messages.extend(self._format_messages_openai(messages))

        body: dict[str, Any] = {
            "model": config["model"],
            "messages": formatted_messages,
            "max_tokens": max_tokens,
            "stream": True,
        }

        if tools:
            body["tools"] = self._format_tools_openai(tools)

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                async with client.stream("POST", url, headers=headers, json=body) as response:
                    if response.status_code != 200:
                        error_body = await response.aread()
                        yield {"type": "error", "error": f"OpenAI API error: {error_body.decode()}"}
                        return

                    tool_calls: dict[int, dict] = {}

                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue

                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        choices = data.get("choices", [])
                        if not choices:
                            continue

                        choice = choices[0]
                        delta = choice.get("delta", {})
                        finish_reason = choice.get("finish_reason")

                        if "content" in delta and delta["content"]:
                            yield {"type": "text_delta", "text": delta["content"]}

                        if "tool_calls" in delta:
                            for tc in delta["tool_calls"]:
                                idx = tc.get("index", 0)
                                if idx not in tool_calls:
                                    tool_calls[idx] = {
                                        "id": tc.get("id", ""),
                                        "name": tc.get("function", {}).get("name", ""),
                                        "arguments": "",
                                    }
                                else:
                                    if tc.get("id"):
                                        tool_calls[idx]["id"] = tc["id"]
                                    if tc.get("function", {}).get("name"):
                                        tool_calls[idx]["name"] = tc["function"]["name"]

                                if tc.get("function", {}).get("arguments"):
                                    tool_calls[idx]["arguments"] += tc["function"]["arguments"]

                        if finish_reason:
                            for tc in tool_calls.values():
                                try:
                                    input_data = json.loads(tc["arguments"]) if tc["arguments"] else {}
                                except json.JSONDecodeError:
                                    input_data = {}
                                yield {
                                    "type": "tool_use",
                                    "id": tc["id"],
                                    "name": tc["name"],
                                    "input": input_data,
                                }
                            yield {"type": "done", "stop_reason": finish_reason}

            except httpx.TimeoutException:
                yield {"type": "error", "error": "Request timed out"}
            except Exception as e:
                logger.exception("openai_stream_error", error=str(e))
                yield {"type": "error", "error": str(e)}

    async def _stream_ollama(
        self,
        config: dict,
        messages: list[dict],
        system_prompt: str | None,
        max_tokens: int,
    ) -> AsyncIterator[dict]:
        """Stream from Ollama's Chat API."""
        base_url = config.get("base_url")
        if not base_url:
            yield {"type": "error", "error": "Base URL required for Ollama"}
            return

        url = f"{base_url.rstrip('/')}/api/chat"

        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})
        formatted_messages.extend(self._format_messages_ollama(messages))

        body = {
            "model": config["model"],
            "messages": formatted_messages,
            "stream": True,
            "options": {
                "num_predict": max_tokens,
            },
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                async with client.stream("POST", url, json=body) as response:
                    if response.status_code != 200:
                        error_body = await response.aread()
                        yield {"type": "error", "error": f"Ollama API error: {error_body.decode()}"}
                        return

                    async for line in response.aiter_lines():
                        if not line:
                            continue

                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        if data.get("done"):
                            yield {"type": "done", "stop_reason": "stop"}
                        elif "message" in data:
                            content = data["message"].get("content", "")
                            if content:
                                yield {"type": "text_delta", "text": content}

            except httpx.TimeoutException:
                yield {"type": "error", "error": "Request timed out"}
            except Exception as e:
                logger.exception("ollama_stream_error", error=str(e))
                yield {"type": "error", "error": str(e)}

    def _format_messages_anthropic(self, messages: list[dict]) -> list[dict]:
        """Format messages for Anthropic API.

        Converts internal message format to Anthropic's expected structure,
        handling tool results and tool use messages appropriately.

        Args:
            messages: Messages in internal format.

        Returns:
            Messages formatted for Anthropic's Messages API.
        """
        formatted = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "tool":
                formatted.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.get("tool_call_id", ""),
                        "content": content,
                    }],
                })
            elif role == "assistant" and msg.get("tool_calls"):
                content_blocks: list[dict] = []
                if content:
                    content_blocks.append({"type": "text", "text": content})
                for tc in msg["tool_calls"]:
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc.get("id", ""),
                        "name": tc.get("name", ""),
                        "input": tc.get("input", {}),
                    })
                formatted.append({"role": "assistant", "content": content_blocks})
            else:
                api_role = "assistant" if role == "assistant" else "user"
                formatted.append({"role": api_role, "content": content})

        return formatted

    def _format_messages_openai(self, messages: list[dict]) -> list[dict]:
        """Format messages for OpenAI API.

        Converts internal message format to OpenAI's expected structure,
        handling tool calls and tool results appropriately.

        Args:
            messages: Messages in internal format.

        Returns:
            Messages formatted for OpenAI's Chat Completions API.
        """
        formatted = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "tool":
                formatted.append({
                    "role": "tool",
                    "tool_call_id": msg.get("tool_call_id", ""),
                    "content": content,
                })
            elif role == "assistant" and msg.get("tool_calls"):
                formatted.append({
                    "role": "assistant",
                    "content": content if content else None,
                    "tool_calls": [
                        {
                            "id": tc.get("id"),
                            "type": "function",
                            "function": {
                                "name": tc.get("name"),
                                "arguments": json.dumps(tc.get("input", {})),
                            },
                        }
                        for tc in msg["tool_calls"]
                    ],
                })
            else:
                formatted.append({"role": role, "content": content})

        return formatted

    def _format_messages_ollama(self, messages: list[dict]) -> list[dict]:
        """Format messages for Ollama API.

        Converts internal message format to Ollama's simple role/content structure.
        Tool results are included as user messages since Ollama lacks native tool support.

        Args:
            messages: Messages in internal format.

        Returns:
            Messages formatted for Ollama's Chat API.
        """
        formatted = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "tool":
                formatted.append({
                    "role": "user",
                    "content": f"Tool result: {content}",
                })
            else:
                formatted.append({"role": role, "content": content})

        return formatted

    def _format_tools_anthropic(self, tools: list[dict]) -> list[dict]:
        """Format tools for Anthropic API.

        Args:
            tools: Tools in internal format with name, description, and inputSchema.

        Returns:
            Tools formatted for Anthropic's tool use feature.
        """
        return [
            {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "input_schema": tool.get("inputSchema", tool.get("input_schema", {})),
            }
            for tool in tools
        ]

    def _format_tools_openai(self, tools: list[dict]) -> list[dict]:
        """Format tools for OpenAI API.

        Args:
            tools: Tools in internal format with name, description, and inputSchema.

        Returns:
            Tools formatted for OpenAI's function calling feature.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("inputSchema", tool.get("input_schema", {})),
                },
            }
            for tool in tools
        ]
