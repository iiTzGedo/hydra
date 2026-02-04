"""Provider validation and model fetching methods for AIService.

Contains mixin class with all provider-specific API interactions:
- Validation of API keys/connectivity for each provider
- Dynamic model list fetching from provider APIs
"""

import httpx
import structlog

from hydra.api.v1.core.exceptions import ValidationError
from hydra.api.v1.models.ai import LLMProviderType

logger = structlog.get_logger(__name__)


class ProviderValidationMixin:
    """Mixin providing provider validation and model fetching methods."""

    # =========================================================================
    # Provider Validation Methods
    # =========================================================================

    async def _validate_anthropic(self, api_key: str | None) -> tuple[bool, str, list[str] | None]:
        """Validate Anthropic API key by fetching available models."""
        if not api_key:
            return False, "API key is required for Anthropic", None

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    models = [m.get("id") for m in data.get("data", [])]
                    return True, "API key is valid", models
                elif response.status_code == 401:
                    return False, "Invalid API key", None
                else:
                    return False, f"API returned status {response.status_code}", None
            except httpx.TimeoutException:
                return False, "Request timed out", None
            except httpx.ConnectError:
                return False, "Cannot connect to Anthropic API", None
            except Exception as e:
                return False, f"Request failed: {str(e)}", None

    async def _validate_openai(
        self, api_key: str | None, base_url: str | None
    ) -> tuple[bool, str, list[str] | None]:
        """Validate OpenAI API key by fetching available models."""
        if not api_key:
            return False, "API key is required for OpenAI", None

        url = f"{base_url.rstrip('/')}/models" if base_url else "https://api.openai.com/v1/models"

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {api_key}"},
                )

                if response.status_code == 200:
                    data = response.json()
                    models = [m.get("id") for m in data.get("data", [])]
                    return True, "API key is valid", models
                elif response.status_code == 401:
                    return False, "Invalid API key", None
                else:
                    return False, f"API returned status {response.status_code}", None
            except httpx.TimeoutException:
                return False, "Request timed out", None
            except httpx.ConnectError:
                return False, "Cannot connect to OpenAI API", None
            except Exception as e:
                return False, f"Request failed: {str(e)}", None

    async def _validate_ollama(self, base_url: str | None) -> tuple[bool, str, list[str] | None]:
        """Validate Ollama server by checking connectivity and listing models."""
        if not base_url:
            return False, "Base URL is required for Ollama", None

        url = f"{base_url.rstrip('/')}/api/tags"

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(url)

                if response.status_code == 200:
                    data = response.json()
                    models = [m.get("name") for m in data.get("models", [])]
                    return True, "Ollama server is reachable", models
                else:
                    return False, f"Server returned status {response.status_code}", None
            except httpx.TimeoutException:
                return False, "Request timed out", None
            except httpx.ConnectError:
                return False, f"Cannot connect to Ollama server at {base_url}", None
            except Exception as e:
                return False, f"Cannot reach Ollama server: {str(e)}", None

    async def _validate_openrouter(self, api_key: str | None) -> tuple[bool, str, list[str] | None]:
        """Validate OpenRouter API key by fetching available models.

        OpenRouter provides access to multiple LLM providers through a unified API.
        """
        if not api_key:
            return False, "API key is required for OpenRouter", None

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "HTTP-Referer": "https://hydra.local",
                    },
                )

                if response.status_code == 200:
                    data = response.json()
                    models = [m.get("id") for m in data.get("data", [])]
                    return True, "API key is valid", models
                elif response.status_code == 401:
                    return False, "Invalid API key", None
                else:
                    return False, f"API returned status {response.status_code}", None
            except httpx.TimeoutException:
                return False, "Request timed out", None
            except httpx.ConnectError:
                return False, "Cannot connect to OpenRouter API", None
            except Exception as e:
                return False, f"Request failed: {str(e)}", None

    # =========================================================================
    # Provider Model Fetching (Dynamic model lists from provider APIs)
    # =========================================================================

    async def _fetch_anthropic_models(
        self, api_key: str | None, tools_only: bool
    ) -> list[dict]:
        """Fetch models from Anthropic API."""
        if not api_key:
            raise ValidationError("API key is required to fetch Anthropic models")

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://api.anthropic.com/v1/models",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
            )

            if response.status_code == 401:
                raise ValidationError("Invalid API key")
            elif response.status_code != 200:
                raise ValidationError(f"API returned status {response.status_code}")

            data = response.json()
            models = []

            for m in data.get("data", []):
                model_id = m.get("id", "")

                # Claude 3+ and Claude 4+ models support tools
                supports_tools = any(x in model_id for x in ["claude-3", "claude-4"])

                if tools_only and not supports_tools:
                    continue

                # Determine capabilities from model ID
                supports_vision = any(x in model_id for x in ["claude-3", "claude-4"])
                # Claude Opus models and Claude 4 Sonnet support extended thinking
                supports_reasoning = any(
                    x in model_id.lower() for x in ["opus", "sonnet-4"]
                )

                # Context windows based on known models
                context_window = 200000  # Default for Claude 3+
                if "claude-2" in model_id:
                    context_window = 100000

                # Pricing (approximate, per 1K tokens)
                cost_input = 0.003
                cost_output = 0.015
                if "sonnet" in model_id.lower():
                    cost_input = 0.003
                    cost_output = 0.015
                elif "haiku" in model_id.lower():
                    cost_input = 0.00025
                    cost_output = 0.00125
                elif "opus" in model_id.lower():
                    cost_input = 0.015
                    cost_output = 0.075

                models.append({
                    "id": model_id,
                    "name": m.get("display_name", model_id),
                    "context_window": context_window,
                    "supports_tools": supports_tools,
                    "supports_vision": supports_vision,
                    "supports_reasoning": supports_reasoning,
                    "cost_per_1k_input": cost_input,
                    "cost_per_1k_output": cost_output,
                })

            return models

    async def _fetch_openai_models(
        self, api_key: str | None, base_url: str | None, tools_only: bool
    ) -> list[dict]:
        """Fetch models from OpenAI API."""
        if not api_key:
            raise ValidationError("API key is required to fetch OpenAI models")

        url = f"{base_url.rstrip('/')}/models" if base_url else "https://api.openai.com/v1/models"

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
            )

            if response.status_code == 401:
                raise ValidationError("Invalid API key")
            elif response.status_code != 200:
                raise ValidationError(f"API returned status {response.status_code}")

            data = response.json()
            models = []

            # Tool-capable model prefixes (all support function calling)
            tool_capable_prefixes = [
                "gpt-4",        # GPT-4, GPT-4o, GPT-4-turbo
                "gpt-4.1",      # GPT-4.1 series
                "gpt-5",        # GPT-5 series
                "gpt-3.5-turbo",
                "o1",           # o1 reasoning models
                "o3",           # o3 reasoning models
                "o4",           # o4-mini
            ]

            for m in data.get("data", []):
                model_id = m.get("id", "")

                # Check if model supports tools (function calling)
                supports_tools = any(
                    model_id.startswith(prefix) for prefix in tool_capable_prefixes
                )

                if tools_only and not supports_tools:
                    continue

                # Skip non-chat models
                if any(skip in model_id for skip in ["embedding", "whisper", "tts", "dall-e", "davinci", "babbage"]):
                    continue

                # Determine capabilities
                supports_vision = "vision" in model_id or model_id.startswith("gpt-4") or model_id.startswith("gpt-5")
                # O-series are reasoning models
                supports_reasoning = any(model_id.startswith(p) for p in ["o1", "o3", "o4"])

                # Context windows
                context_window = 4096
                if "32k" in model_id:
                    context_window = 32768
                elif "128k" in model_id or model_id.startswith("gpt-4-turbo") or model_id.startswith("gpt-4o"):
                    context_window = 128000
                elif model_id.startswith("gpt-4.1"):
                    context_window = 1000000  # GPT-4.1 has 1M context
                elif model_id.startswith("gpt-5"):
                    context_window = 256000  # GPT-5 series
                elif model_id.startswith("gpt-4"):
                    context_window = 8192
                elif "16k" in model_id:
                    context_window = 16384
                elif model_id.startswith("o1") or model_id.startswith("o3") or model_id.startswith("o4"):
                    context_window = 128000  # Reasoning models

                # Pricing (approximate, per 1K tokens)
                cost_input = 0.0015
                cost_output = 0.002
                if model_id.startswith("gpt-4o"):
                    cost_input = 0.005
                    cost_output = 0.015
                elif model_id.startswith("gpt-4.1"):
                    cost_input = 0.002
                    cost_output = 0.008
                elif model_id.startswith("gpt-4-turbo"):
                    cost_input = 0.01
                    cost_output = 0.03
                elif model_id.startswith("gpt-4"):
                    cost_input = 0.03
                    cost_output = 0.06
                elif model_id.startswith("gpt-5"):
                    cost_input = 0.01
                    cost_output = 0.03
                elif model_id.startswith("o1"):
                    cost_input = 0.015
                    cost_output = 0.06
                elif model_id.startswith("o3") or model_id.startswith("o4"):
                    cost_input = 0.01
                    cost_output = 0.04

                models.append({
                    "id": model_id,
                    "name": model_id,
                    "context_window": context_window,
                    "supports_tools": supports_tools,
                    "supports_vision": supports_vision,
                    "supports_reasoning": supports_reasoning,
                    "cost_per_1k_input": cost_input,
                    "cost_per_1k_output": cost_output,
                })

            return models

    async def _fetch_ollama_models(
        self, base_url: str | None, tools_only: bool
    ) -> list[dict]:
        """Fetch models from Ollama server."""
        if not base_url:
            raise ValidationError("Base URL is required to fetch Ollama models")

        url = f"{base_url.rstrip('/')}/api/tags"

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(url)
            except httpx.ConnectError:
                raise ValidationError(f"Cannot connect to Ollama server at {base_url}")

            if response.status_code != 200:
                raise ValidationError(f"Server returned status {response.status_code}")

            data = response.json()
            models = []

            # Known tool-capable Ollama models
            # Note: Base llama3 and qwen do NOT support tools - only versioned variants
            tool_capable_models = [
                "llama3.1", "llama3.2", "llama3.3",  # llama3.1+ only (not llama3 base)
                "mistral", "mixtral",
                "qwen2", "qwen2.5", "qwen3",  # qwen2+ only (not qwen base)
                "deepseek", "deepseek-v2", "deepseek-v3",
                "command-r", "command-r-plus",
                "granite",
            ]

            for m in data.get("models", []):
                model_name = m.get("name", "")
                model_lower = model_name.lower()

                # Check if model supports tools
                # Use precise matching to avoid llama3 matching llama3.1
                supports_tools = any(tc in model_lower for tc in tool_capable_models)

                # Exclude base llama3 (without .1, .2, .3 suffix) which doesn't support tools
                if "llama3" in model_lower and not any(
                    x in model_lower for x in ["llama3.1", "llama3.2", "llama3.3"]
                ):
                    supports_tools = False

                if tools_only and not supports_tools:
                    continue

                # Get model details if available
                details = m.get("details", {})
                parameter_size = details.get("parameter_size", "")

                # Estimate context window from parameter size
                context_window = 4096
                if "70b" in parameter_size.lower() or "70b" in model_lower:
                    context_window = 8192
                elif "llama3.1" in model_lower or "llama3.2" in model_lower or "llama3.3" in model_lower:
                    context_window = 128000  # Llama 3.1+ has 128K context
                elif "llama3" in model_lower:
                    context_window = 8192

                models.append({
                    "id": model_name,
                    "name": model_name,
                    "context_window": context_window,
                    "supports_tools": supports_tools,
                    "supports_vision": "vision" in model_name.lower() or "llava" in model_name.lower(),
                    "supports_reasoning": False,
                    "cost_per_1k_input": None,  # Local models have no API cost
                    "cost_per_1k_output": None,
                })

            return models

    async def _fetch_openrouter_models(
        self, api_key: str | None, tools_only: bool
    ) -> list[dict]:
        """Fetch models from OpenRouter API."""
        if not api_key:
            raise ValidationError("API key is required to fetch OpenRouter models")

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": "https://hydra.local",
                },
            )

            if response.status_code == 401:
                raise ValidationError("Invalid API key")
            elif response.status_code != 200:
                raise ValidationError(f"API returned status {response.status_code}")

            data = response.json()
            models = []

            for m in data.get("data", []):
                model_id = m.get("id", "")

                # Check if model supports tools via supported_parameters
                supported_params = m.get("supported_parameters", [])
                supports_tools = "tools" in supported_params or "function_calling" in supported_params

                if tools_only and not supports_tools:
                    continue

                # Get pricing (OpenRouter provides per-token pricing)
                pricing = m.get("pricing", {})
                prompt_price = pricing.get("prompt")
                completion_price = pricing.get("completion")

                # Convert to per 1K tokens (OpenRouter uses per-token)
                cost_input = float(prompt_price) * 1000 if prompt_price else None
                cost_output = float(completion_price) * 1000 if completion_price else None

                # Context length
                context_window = m.get("context_length", 4096)

                # Determine additional capabilities
                supports_vision = "vision" in model_id.lower() or m.get("multimodal", False)
                supports_reasoning = "o1" in model_id.lower() or "reasoning" in model_id.lower()

                models.append({
                    "id": model_id,
                    "name": m.get("name", model_id),
                    "context_window": context_window,
                    "supports_tools": supports_tools,
                    "supports_vision": supports_vision,
                    "supports_reasoning": supports_reasoning,
                    "cost_per_1k_input": cost_input,
                    "cost_per_1k_output": cost_output,
                })

            return models
