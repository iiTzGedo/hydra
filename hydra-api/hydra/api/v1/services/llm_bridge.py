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


class LLMConfigError(ValidationError):
    """LLM configuration error."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, details or {})


class LLMBridge:
    """Bridge for streaming LLM API calls."""

    def __init__(self, mongodb: MongoDB):
        self.db = mongodb

    async def get_config(self, config_id: str, user_id: str) -> dict:
        """Get and prepare LLM configuration for API calls.

        Args:
            config_id: The LLM configuration identifier.
            user_id: The owner's user identifier.

        Returns:
            Config dict with type, api_key, base_url, and model.

        Raises:
            LLMConfigError: If config not found.
        """
        doc = await self.db.ai_models.find_one({
            "providerId": config_id,
            "createdBy": user_id,
        })

        if not doc:
            raise LLMConfigError(f"LLM configuration not found: {config_id}")

        api_key = None
        if doc.get("apiKeyEncrypted"):
            api_key = decrypt_value(doc["apiKeyEncrypted"])

        return {
            "config_id": doc["providerId"],
            "type": LLMProviderType(doc["type"]),
            "api_key": api_key,
            "base_url": doc.get("baseUrl"),
            "model": doc["model"],
        }

    # =========================================================================
    # Model Parameter Helpers
    # =========================================================================

    def _get_openai_token_param(self, model: str) -> str:
        """Determine the correct token limit parameter for an OpenAI model.

        Different OpenAI model families require different parameter names:
        - O-series reasoning models (o1, o3, o4): max_completion_tokens
        - GPT-5 series (5, 5.1, 5.2, etc.): max_output_tokens
        - Standard models (GPT-3.5, GPT-4, GPT-4.1, GPT-4o): max_tokens

        Args:
            model: The OpenAI model identifier.

        Returns:
            The correct parameter name for token limits.
        """
        model_lower = model.lower()

        # O-series reasoning models require max_completion_tokens
        # Covers: o1, o1-mini, o1-preview, o3, o3-mini, o4, o4-mini, etc.
        if any(model_lower.startswith(p) for p in ["o1", "o3", "o4"]):
            return "max_completion_tokens"

        # GPT-5 series uses max_output_tokens
        # Covers: gpt-5, gpt-5-turbo, gpt-5.1, gpt-5.2, gpt-5.1-mini, etc.
        if any(model_lower.startswith(p) for p in ["gpt-5", "gpt-5.1", "gpt-5.2"]):
            return "max_output_tokens"

        # Standard models (GPT-3.5, GPT-4, GPT-4.1, GPT-4o) use max_tokens
        return "max_tokens"

    def _get_openrouter_token_param(self, model: str) -> str:
        """Determine the correct token limit parameter for OpenRouter model.

        OpenRouter routes to various underlying providers. When routing to
        OpenAI models, we need to use the appropriate token parameter.

        Args:
            model: The OpenRouter model identifier (e.g., 'openai/o1-preview').

        Returns:
            The correct parameter name for token limits.
        """
        model_lower = model.lower()

        # OpenAI o-series via OpenRouter
        if any(x in model_lower for x in ["openai/o1", "openai/o3", "openai/o4"]):
            return "max_completion_tokens"

        # OpenAI GPT-5 series via OpenRouter (5, 5.1, 5.2)
        if any(x in model_lower for x in ["openai/gpt-5", "openai/gpt-5.1", "openai/gpt-5.2"]):
            return "max_output_tokens"

        # Most models (including Anthropic, Mistral, etc.) use max_tokens
        return "max_tokens"

    def _is_o_series_model(self, model: str) -> bool:
        """Check if model is an O-series reasoning model.

        O-series models have restrictions: temperature must be 1.0,
        no frequency_penalty, no presence_penalty, etc.

        Args:
            model: The model identifier.

        Returns:
            True if this is an O-series model.
        """
        model_lower = model.lower()
        return any(model_lower.startswith(p) for p in ["o1", "o3", "o4"])

    def _ollama_model_supports_tools(self, model: str) -> bool:
        """Check if an Ollama model supports tool calling.

        Only certain Ollama models support the tool calling feature.
        Note: Original llama3 (without .1+) does NOT support tools.

        Args:
            model: The Ollama model name.

        Returns:
            True if the model supports tool calling.
        """
        tool_capable_models = [
            "llama3.1", "llama3.2", "llama3.3",  # llama3.1+ only
            "mistral", "mixtral",
            "qwen2", "qwen2.5", "qwen3",
            "deepseek", "deepseek-v2", "deepseek-v3",
            "command-r", "command-r-plus",
            "granite",
        ]
        model_lower = model.lower()
        return any(tm in model_lower for tm in tool_capable_models)

    # =========================================================================
    # Shared Streaming Helpers
    # =========================================================================

    async def _parse_openai_sse_stream(
        self,
        response: httpx.Response,
        provider_label: str,
    ) -> AsyncIterator[dict]:
        """Parse an OpenAI-compatible SSE stream into normalized events.

        Handles text deltas, tool call accumulation by index, and finish
        reasons. Used by both OpenAI and OpenRouter streaming methods.

        Args:
            response: The httpx streaming response to parse.
            provider_label: Label for logging (e.g., 'openai', 'openrouter').

        Yields:
            Normalized event dicts (text_delta, tool_use, done).
        """
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

    async def _make_openai_streaming_request(
        self,
        url: str,
        headers: dict,
        body: dict,
        provider_label: str,
    ) -> AsyncIterator[dict]:
        """Make an OpenAI-compatible streaming request with shared error handling.

        Combines httpx client management, status checking, timeout handling,
        and OpenAI SSE parsing into a single method for OpenAI and OpenRouter.

        Args:
            url: The API endpoint URL.
            headers: Request headers.
            body: Request body (will be sent as JSON).
            provider_label: Label for error messages and logging.

        Yields:
            Normalized event dicts (text_delta, tool_use, done, error).
        """
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                async with client.stream("POST", url, headers=headers, json=body) as response:
                    if response.status_code != 200:
                        error_body = await response.aread()
                        yield {"type": "error", "error": f"{provider_label} API error: {error_body.decode()}"}
                        return

                    async for event in self._parse_openai_sse_stream(response, provider_label):
                        yield event

            except httpx.TimeoutException:
                yield {"type": "error", "error": "Request timed out"}
            except Exception as e:
                logger.exception(f"{provider_label.lower()}_stream_error", error=str(e))
                yield {"type": "error", "error": str(e)}

    # =========================================================================
    # Streaming Methods
    # =========================================================================

    async def stream_completion(
        self,
        provider_config: dict,
        messages: list[dict],
        tools: list[dict] | None = None,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
        reasoning_level: str = "none",
        web_search_enabled: bool = False,
    ) -> AsyncIterator[dict]:
        """Stream a completion from the configured LLM provider.

        Routes the request to the appropriate provider-specific streaming method
        based on the provider type in the configuration.

        Args:
            provider_config: Provider configuration from get_provider_config.
            messages: Conversation messages in the internal format.
            tools: Optional list of tools available for the model.
            system_prompt: Optional system prompt to prepend.
            max_tokens: Maximum tokens in the response. Required for Anthropic,
                optional for others. Defaults to 4096 if required and not provided.
            temperature: Sampling temperature. Not supported by O-series models.
            top_p: Nucleus sampling parameter.
            top_k: Top-K sampling (Anthropic/Ollama only).
            frequency_penalty: Reduce repetition (OpenAI only).
            presence_penalty: Encourage new topics (OpenAI only).
            reasoning_level: Extended thinking level ('none', 'low', 'medium', 'high').
            web_search_enabled: Whether to enable web search (provider-dependent).

        Yields:
            Normalized event dicts with one of:
            - {"type": "text_delta", "text": "..."} for content chunks
            - {"type": "tool_use", "id": "...", "name": "...", "input": {...}} for tool calls
            - {"type": "done", "stop_reason": "...", "usage": {...}} when complete
            - {"type": "error", "error": "..."} on failure

        Note:
            Extended thinking (reasoning_level) support is planned for Anthropic
            claude-3.5+ and OpenAI o1/o3 models. Web search (web_search_enabled)
            is primarily supported through OpenRouter.
        """
        # Log feature flag usage for debugging
        if reasoning_level != "none" or web_search_enabled:
            logger.debug(
                "llm_feature_flags",
                reasoning_level=reasoning_level,
                web_search_enabled=web_search_enabled,
                provider_type=str(provider_config.get("type")),
            )
        provider_type = provider_config["type"]

        # Build model config dict for passing to provider methods
        model_config = {
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty,
        }

        if provider_type == LLMProviderType.ANTHROPIC:
            async for event in self._stream_anthropic(
                provider_config, messages, tools, system_prompt, model_config
            ):
                yield event
        elif provider_type == LLMProviderType.OPENAI:
            async for event in self._stream_openai(
                provider_config, messages, tools, system_prompt, model_config
            ):
                yield event
        elif provider_type == LLMProviderType.OLLAMA:
            async for event in self._stream_ollama(
                provider_config, messages, tools, system_prompt, model_config
            ):
                yield event
        elif provider_type == LLMProviderType.OPENROUTER:
            async for event in self._stream_openrouter(
                provider_config, messages, tools, system_prompt, model_config
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
        model_config: dict,
    ) -> AsyncIterator[dict]:
        """Stream from Anthropic's Messages API.

        Args:
            config: Provider configuration with api_key, model, etc.
            messages: Formatted messages for the API.
            tools: Optional tool definitions.
            system_prompt: Optional system prompt.
            model_config: Model parameters (max_tokens, temperature, top_p, top_k).
        """
        if not config.get("api_key"):
            yield {"type": "error", "error": "API key required for Anthropic"}
            return

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": config["api_key"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        # Anthropic REQUIRES max_tokens - use provided value or default to 4096
        max_tokens = model_config.get("max_tokens") or 4096

        body: dict[str, Any] = {
            "model": config["model"],
            "messages": self._format_messages_anthropic(messages),
            "max_tokens": max_tokens,
            "stream": True,
        }

        # Add optional parameters if provided
        if model_config.get("temperature") is not None:
            body["temperature"] = model_config["temperature"]
        if model_config.get("top_p") is not None:
            body["top_p"] = model_config["top_p"]
        if model_config.get("top_k") is not None:
            body["top_k"] = model_config["top_k"]

        if system_prompt:
            body["system"] = system_prompt

        if tools:
            body["tools"] = self._format_tools_anthropic(tools)

        logger.debug(
            "anthropic_request",
            model=config["model"],
            max_tokens=max_tokens,
            has_temperature=model_config.get("temperature") is not None,
            has_tools=bool(tools),
        )

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
        model_config: dict,
    ) -> AsyncIterator[dict]:
        """Stream from OpenAI's Chat Completions API.

        Args:
            config: Provider configuration with api_key, model, base_url.
            messages: Formatted messages for the API.
            tools: Optional tool definitions.
            system_prompt: Optional system prompt.
            model_config: Model parameters (max_tokens, temperature, top_p, etc.).
        """
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

        model = config["model"]
        is_o_series = self._is_o_series_model(model)

        body: dict[str, Any] = {
            "model": model,
            "messages": formatted_messages,
            "stream": True,
        }

        # Add max_tokens with correct parameter name (only if provided)
        max_tokens = model_config.get("max_tokens")
        if max_tokens is not None:
            token_param = self._get_openai_token_param(model)
            body[token_param] = max_tokens

        # Add temperature (not supported by O-series models)
        if model_config.get("temperature") is not None and not is_o_series:
            body["temperature"] = model_config["temperature"]

        # Add top_p (not supported by O-series models)
        if model_config.get("top_p") is not None and not is_o_series:
            body["top_p"] = model_config["top_p"]

        # Add frequency_penalty (not supported by O-series models)
        if model_config.get("frequency_penalty") is not None and not is_o_series:
            body["frequency_penalty"] = model_config["frequency_penalty"]

        # Add presence_penalty (not supported by O-series models)
        if model_config.get("presence_penalty") is not None and not is_o_series:
            body["presence_penalty"] = model_config["presence_penalty"]

        if tools:
            body["tools"] = self._format_tools_openai(tools)

        logger.debug(
            "openai_request",
            model=model,
            is_o_series=is_o_series,
            has_max_tokens=max_tokens is not None,
            has_temperature=model_config.get("temperature") is not None,
            has_tools=bool(tools),
        )

        async for event in self._make_openai_streaming_request(url, headers, body, "OpenAI"):
            yield event

    async def _stream_ollama(
        self,
        config: dict,
        messages: list[dict],
        tools: list[dict] | None,
        system_prompt: str | None,
        model_config: dict,
    ) -> AsyncIterator[dict]:
        """Stream from Ollama's Chat API.

        Supports tool calling for compatible models (llama3.1+, mistral, qwen2+, etc.).
        Note that Ollama does not support streaming tool calls - they are returned
        in the final message when done=true.

        Args:
            config: Provider configuration with base_url, model.
            messages: Formatted messages for the API.
            tools: Optional tool definitions.
            system_prompt: Optional system prompt.
            model_config: Model parameters (max_tokens, temperature, top_p, top_k).
        """
        base_url = config.get("base_url")
        if not base_url:
            yield {"type": "error", "error": "Base URL required for Ollama"}
            return

        url = f"{base_url.rstrip('/')}/api/chat"

        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})
        formatted_messages.extend(self._format_messages_ollama(messages))

        # Build options dict with provided parameters
        options: dict[str, Any] = {}

        # Ollama uses num_predict for max tokens
        max_tokens = model_config.get("max_tokens")
        if max_tokens is not None:
            options["num_predict"] = max_tokens

        if model_config.get("temperature") is not None:
            options["temperature"] = model_config["temperature"]

        if model_config.get("top_p") is not None:
            options["top_p"] = model_config["top_p"]

        if model_config.get("top_k") is not None:
            options["top_k"] = model_config["top_k"]

        body: dict[str, Any] = {
            "model": config["model"],
            "messages": formatted_messages,
            "stream": True,
        }

        # Only add options if we have any
        if options:
            body["options"] = options

        # Add tools if provided and model supports them
        if tools and self._ollama_model_supports_tools(config["model"]):
            body["tools"] = self._format_tools_ollama(tools)
            logger.debug(
                "ollama_tools_enabled",
                model=config["model"],
                tool_count=len(tools),
            )

        logger.debug(
            "ollama_request",
            model=config["model"],
            has_options=bool(options),
            has_tools=bool(tools),
        )

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
                            # Check for tool calls in the final message
                            message = data.get("message", {})
                            tool_calls = message.get("tool_calls", [])

                            # Yield any tool calls before done
                            for tc in tool_calls:
                                func = tc.get("function", {})
                                yield {
                                    "type": "tool_use",
                                    "id": tc.get("id", f"call_{func.get('name', 'unknown')}"),
                                    "name": func.get("name", ""),
                                    "input": func.get("arguments", {}),
                                }

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

    async def _stream_openrouter(
        self,
        config: dict,
        messages: list[dict],
        tools: list[dict] | None,
        system_prompt: str | None,
        model_config: dict,
    ) -> AsyncIterator[dict]:
        """Stream from OpenRouter's Chat Completions API.

        OpenRouter provides access to multiple LLM providers through a unified API.
        It uses an OpenAI-compatible format for requests and responses.

        Args:
            config: Provider configuration with api_key, model.
            messages: Formatted messages for the API.
            tools: Optional tool definitions.
            system_prompt: Optional system prompt.
            model_config: Model parameters (max_tokens, temperature, top_p, etc.).
        """
        if not config.get("api_key"):
            yield {"type": "error", "error": "API key required for OpenRouter"}
            return

        url = "https://openrouter.ai/api/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://hydra.local",  # Required by OpenRouter
            "X-Title": "Hydra Infrastructure Manager",  # Recommended by OpenRouter
        }

        # OpenRouter uses OpenAI-compatible message format
        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})
        formatted_messages.extend(self._format_messages_openai(messages))

        model = config["model"]
        model_lower = model.lower()

        # Detect if this is an O-series model via OpenRouter
        is_o_series = any(x in model_lower for x in ["openai/o1", "openai/o3", "openai/o4"])

        body: dict[str, Any] = {
            "model": model,
            "messages": formatted_messages,
            "stream": True,
        }

        # Add max_tokens with correct parameter name (only if provided)
        max_tokens = model_config.get("max_tokens")
        if max_tokens is not None:
            token_param = self._get_openrouter_token_param(model)
            body[token_param] = max_tokens

        # Add temperature (not supported by O-series models)
        if model_config.get("temperature") is not None and not is_o_series:
            body["temperature"] = model_config["temperature"]

        # Add top_p (not supported by O-series models)
        if model_config.get("top_p") is not None and not is_o_series:
            body["top_p"] = model_config["top_p"]

        # Add frequency_penalty (only for OpenAI models, not O-series)
        if model_config.get("frequency_penalty") is not None and "openai/" in model_lower and not is_o_series:
            body["frequency_penalty"] = model_config["frequency_penalty"]

        # Add presence_penalty (only for OpenAI models, not O-series)
        if model_config.get("presence_penalty") is not None and "openai/" in model_lower and not is_o_series:
            body["presence_penalty"] = model_config["presence_penalty"]

        if tools:
            body["tools"] = self._format_tools_openai(tools)

        logger.debug(
            "openrouter_request",
            model=model,
            is_o_series=is_o_series,
            has_max_tokens=max_tokens is not None,
            has_temperature=model_config.get("temperature") is not None,
            has_tools=bool(tools),
        )

        async for event in self._make_openai_streaming_request(url, headers, body, "OpenRouter"):
            yield event

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

        Converts internal message format to Ollama's expected structure.
        Ollama now supports native tool results via the 'tool' role.

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
                # Ollama supports native tool results
                formatted.append({
                    "role": "tool",
                    "content": content,
                })
            elif role == "assistant" and msg.get("tool_calls"):
                # Assistant message with tool calls
                formatted_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": content if content else "",
                }
                # Format tool calls for Ollama
                formatted_msg["tool_calls"] = [
                    {
                        "function": {
                            "name": tc.get("name"),
                            "arguments": tc.get("input", {}),
                        },
                    }
                    for tc in msg["tool_calls"]
                ]
                formatted.append(formatted_msg)
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

    def _format_tools_ollama(self, tools: list[dict]) -> list[dict]:
        """Format tools for Ollama API.

        Ollama uses an OpenAI-compatible format for tool definitions.

        Args:
            tools: Tools in internal format with name, description, and inputSchema.

        Returns:
            Tools formatted for Ollama's tool calling feature.
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
