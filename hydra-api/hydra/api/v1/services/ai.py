"""AI/LLM configuration and provider management service.

Terminology:
- LLMProvider: One of the 4 supported provider types (Anthropic, OpenAI, Ollama, OpenRouter)
- LLMModel: A model available from a provider (fetched dynamically)
- LLMConfig: User's saved configuration (provider + model + API key) for chat sessions
"""

import re
import secrets
from datetime import datetime, timezone

import httpx
import structlog

from hydra.api.v1.core.crypto import decrypt_value, encrypt_value, mask_api_key
from hydra.api.v1.core.exceptions import NotFoundError, ValidationError
from hydra.api.v1.models.ai import (
    GlobalAPIKeyCreate,
    LLMConfigCreate,
    LLMConfigUpdate,
    LLMProviderType,
)
from hydra.api.v1.services.chat_cache import ChatCacheService
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)


class LLMConfigNotFoundError(NotFoundError):
    """LLM configuration not found."""

    def __init__(self, config_id: str):
        super().__init__("llm_config", config_id)


class AIService:
    """AI/LLM configuration and provider management service."""

    def __init__(self, mongodb: MongoDB, cache: ChatCacheService | None = None):
        self.db = mongodb
        self._cache = cache or ChatCacheService()

    # =========================================================================
    # LLM Configuration CRUD (User's saved configurations)
    # =========================================================================

    async def list_configs(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """List LLM configurations created by a user.

        Args:
            user_id: The user identifier.
            limit: Maximum number of results to return.
            offset: Number of results to skip for pagination.

        Returns:
            Dict containing 'configs' list and 'total' count.
        """
        cursor = (
            self.db.ai_models.find({"createdBy": user_id})
            .sort("createdAt", -1)
            .skip(offset)
            .limit(limit)
        )

        configs = []
        async for doc in cursor:
            configs.append(self._doc_to_response(doc))

        total = await self.db.ai_models.count_documents({"createdBy": user_id})

        return {
            "configs": configs,
            "total": total,
        }

    async def get_config(self, config_id: str, user_id: str) -> dict:
        """Get a specific LLM configuration by ID.

        Args:
            config_id: The unique configuration identifier.
            user_id: The owner's user identifier.

        Returns:
            The configuration as a dict.

        Raises:
            LLMConfigNotFoundError: If the config does not exist or is not owned by user.
        """
        doc = await self.db.ai_models.find_one({
            "providerId": config_id,
            "createdBy": user_id,
        })

        if not doc:
            raise LLMConfigNotFoundError(config_id)

        return self._doc_to_response(doc)

    async def create_config(
        self,
        request: LLMConfigCreate,
        user_id: str,
    ) -> dict:
        """Create a new LLM configuration.

        Args:
            request: Configuration creation payload with name, type, API key, etc.
            user_id: The owner's user identifier.

        Returns:
            The created configuration.

        Raises:
            ValidationError: If name is invalid or duplicate.
        """
        # Validate name format: letters only at start, max 2 hyphen-separated segments
        name_pattern = re.compile(r"^[a-zA-Z]+(-[a-zA-Z0-9]+){0,2}$")
        if not name_pattern.match(request.name):
            raise ValidationError(
                "Invalid config name format. Must start with letters and contain "
                "at most 2 hyphen-separated segments (e.g., 'my-config', 'anthropic-claude-1')."
            )

        # Check for duplicate names for this user
        existing = await self.db.ai_models.find_one({
            "name": request.name,
            "createdBy": user_id,
        })
        if existing:
            raise ValidationError(f"A configuration with name '{request.name}' already exists.")

        now = datetime.now(timezone.utc)
        config_id = f"llm_{secrets.token_urlsafe(8)}"

        if request.is_default:
            await self.db.ai_models.update_many(
                {"createdBy": user_id, "isDefault": True},
                {"$set": {"isDefault": False, "updatedAt": now}},
            )

        encrypted_key = None
        api_key_last4 = None
        if request.api_key:
            encrypted_key = encrypt_value(request.api_key)
            api_key_last4 = request.api_key[-4:] if len(request.api_key) >= 4 else request.api_key

        doc = {
            "providerId": config_id,  # Legacy field name in MongoDB
            "name": request.name,
            "type": request.type.value,
            "apiKeyEncrypted": encrypted_key,
            "apiKeyLast4": api_key_last4,
            "baseUrl": request.base_url,
            "model": request.model,
            "isDefault": request.is_default,
            "isValid": None,
            "lastValidatedAt": None,
            "createdBy": user_id,
            "createdAt": now,
            "updatedAt": now,
        }

        await self.db.ai_models.insert_one(doc)

        logger.info(
            "llm_config_created",
            config_id=config_id,
            type=request.type.value,
            user_id=user_id,
        )

        return self._doc_to_response(doc)

    async def update_config(
        self,
        config_id: str,
        request: LLMConfigUpdate,
        user_id: str,
    ) -> dict:
        """Update an LLM configuration.

        Args:
            config_id: The unique configuration identifier.
            request: Update payload with optional name, API key, base URL, model.
            user_id: The owner's user identifier.

        Returns:
            The updated configuration.

        Raises:
            LLMConfigNotFoundError: If the config does not exist or is not owned by user.
        """
        doc = await self.db.ai_models.find_one({
            "providerId": config_id,
            "createdBy": user_id,
        })

        if not doc:
            raise LLMConfigNotFoundError(config_id)

        now = datetime.now(timezone.utc)
        update_fields = {"updatedAt": now}

        if request.name is not None:
            update_fields["name"] = request.name

        if request.api_key is not None:
            update_fields["apiKeyEncrypted"] = encrypt_value(request.api_key)
            update_fields["apiKeyLast4"] = (
                request.api_key[-4:] if len(request.api_key) >= 4 else request.api_key
            )
            update_fields["isValid"] = None
            update_fields["lastValidatedAt"] = None

        if request.base_url is not None:
            update_fields["baseUrl"] = request.base_url

        if request.model is not None:
            update_fields["model"] = request.model

        if request.is_default is not None:
            if request.is_default:
                await self.db.ai_models.update_many(
                    {"createdBy": user_id, "isDefault": True, "providerId": {"$ne": config_id}},
                    {"$set": {"isDefault": False, "updatedAt": now}},
                )
            update_fields["isDefault"] = request.is_default

        await self.db.ai_models.update_one(
            {"providerId": config_id},
            {"$set": update_fields},
        )

        updated_doc = await self.db.ai_models.find_one({"providerId": config_id})

        logger.info(
            "llm_config_updated",
            config_id=config_id,
            user_id=user_id,
        )

        return self._doc_to_response(updated_doc)

    async def delete_config(self, config_id: str, user_id: str) -> dict:
        """Delete an LLM configuration.

        Args:
            config_id: The unique configuration identifier.
            user_id: The owner's user identifier.

        Returns:
            Dict with 'deleted' status and 'configId'.

        Raises:
            LLMConfigNotFoundError: If the config does not exist or is not owned by user.
        """
        doc = await self.db.ai_models.find_one({
            "providerId": config_id,
            "createdBy": user_id,
        })

        if not doc:
            raise LLMConfigNotFoundError(config_id)

        await self.db.ai_models.delete_one({"providerId": config_id})

        logger.info(
            "llm_config_deleted",
            config_id=config_id,
            user_id=user_id,
        )

        return {"deleted": True, "configId": config_id}

    async def validate_config(self, config_id: str, user_id: str) -> dict:
        """Validate an LLM configuration by testing the API connection.

        Makes a request to the provider's API to verify the configuration is valid.

        Args:
            config_id: The unique configuration identifier.
            user_id: The owner's user identifier.

        Returns:
            Validation result with 'is_valid', 'message', 'validated_at', and optional 'models' list.

        Raises:
            LLMConfigNotFoundError: If the config does not exist or is not owned by user.
        """
        doc = await self.db.ai_models.find_one({
            "providerId": config_id,
            "createdBy": user_id,
        })

        if not doc:
            raise LLMConfigNotFoundError(config_id)

        provider_type = LLMProviderType(doc["type"])
        now = datetime.now(timezone.utc)

        api_key = None
        if doc.get("apiKeyEncrypted"):
            api_key = decrypt_value(doc["apiKeyEncrypted"])

        is_valid = False
        message = ""
        models = None

        try:
            if provider_type == LLMProviderType.ANTHROPIC:
                is_valid, message, models = await self._validate_anthropic(api_key)
            elif provider_type == LLMProviderType.OPENAI:
                is_valid, message, models = await self._validate_openai(api_key, doc.get("baseUrl"))
            elif provider_type == LLMProviderType.OLLAMA:
                is_valid, message, models = await self._validate_ollama(doc.get("baseUrl"))
            elif provider_type == LLMProviderType.OPENROUTER:
                is_valid, message, models = await self._validate_openrouter(api_key)
            else:
                message = f"Unsupported provider type: {provider_type}"
        except Exception as e:
            logger.error("config_validation_error", config_id=config_id, error=str(e))
            message = f"Validation failed: {str(e)}"

        await self.db.ai_models.update_one(
            {"providerId": config_id},
            {"$set": {"isValid": is_valid, "lastValidatedAt": now, "updatedAt": now}},
        )

        logger.info(
            "llm_config_validated",
            config_id=config_id,
            is_valid=is_valid,
        )

        return {
            "config_id": config_id,
            "is_valid": is_valid,
            "message": message,
            "validated_at": now,
            "models": models,
        }

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
            except Exception as e:
                return False, f"Request failed: {str(e)}", None

    # =========================================================================
    # Provider Model Fetching (Dynamic model lists from provider APIs)
    # =========================================================================

    async def fetch_provider_models(
        self,
        provider_type: LLMProviderType,
        user_id: str,
        config_id: str | None = None,
        tools_only: bool = True,
        use_cache: bool = True,
    ) -> dict:
        """Fetch available models from an LLM provider API.

        Args:
            provider_type: The LLM provider type.
            user_id: The user identifier.
            config_id: Optional config ID to use its stored API key.
            tools_only: Filter to only show models supporting tool calling.
            use_cache: Whether to use Redis cache (default True).

        Returns:
            Dict with 'models', 'provider', 'fetched_at', 'cached' keys.

        Raises:
            ValidationError: If no API key is available for the provider.
            LLMConfigNotFoundError: If config_id is specified but not found.
        """
        now = datetime.now(timezone.utc)
        cache_key = f"{provider_type.value}:{tools_only}"

        # Try cache first
        if use_cache:
            cached_models = await self._cache.get_cached_models(cache_key)
            if cached_models is not None:
                return {
                    "models": cached_models,
                    "provider": provider_type.value,
                    "fetched_at": now,
                    "cached": True,
                }

        # Resolve API key and base URL
        api_key = None
        base_url = None

        if config_id:
            # Use stored config
            doc = await self.db.ai_models.find_one({
                "providerId": config_id,
                "createdBy": user_id,
            })
            if not doc:
                raise LLMConfigNotFoundError(config_id)

            if doc.get("apiKeyEncrypted"):
                api_key = decrypt_value(doc["apiKeyEncrypted"])
            base_url = doc.get("baseUrl")
        else:
            # Try to get global API key for this provider
            global_key = await self.db.global_api_keys.find_one({
                "userId": user_id,
                "providerType": provider_type.value,
            })
            if global_key and global_key.get("apiKeyEncrypted"):
                api_key = decrypt_value(global_key["apiKeyEncrypted"])

        # Fetch models based on provider type
        models = []
        try:
            if provider_type == LLMProviderType.ANTHROPIC:
                models = await self._fetch_anthropic_models(api_key, tools_only)
            elif provider_type == LLMProviderType.OPENAI:
                models = await self._fetch_openai_models(api_key, base_url, tools_only)
            elif provider_type == LLMProviderType.OLLAMA:
                models = await self._fetch_ollama_models(base_url, tools_only)
            elif provider_type == LLMProviderType.OPENROUTER:
                models = await self._fetch_openrouter_models(api_key, tools_only)
            else:
                raise ValidationError(f"Unsupported provider type: {provider_type}")
        except ValidationError:
            raise
        except Exception as e:
            logger.error(
                "model_fetch_error",
                provider_type=provider_type.value,
                error=str(e),
            )
            raise ValidationError(f"Failed to fetch models: {str(e)}")

        # Cache the results
        if use_cache and models:
            await self._cache.cache_provider_models(cache_key, models)

        logger.info(
            "models_fetched",
            provider_type=provider_type.value,
            model_count=len(models),
            tools_only=tools_only,
        )

        return {
            "models": models,
            "provider": provider_type.value,
            "fetched_at": now,
            "cached": False,
        }

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

    # =========================================================================
    # Global API Key Management
    # =========================================================================

    async def list_global_keys(self, user_id: str) -> dict:
        """List all global API keys for a user.

        Args:
            user_id: The user identifier.

        Returns:
            Dict containing 'keys' list.
        """
        cursor = self.db.global_api_keys.find({"userId": user_id})

        keys = []
        async for doc in cursor:
            keys.append(self._global_key_doc_to_response(doc))

        return {"keys": keys}

    async def get_global_key(
        self, provider_type: LLMProviderType, user_id: str
    ) -> dict:
        """Get the global API key for a specific provider.

        Args:
            provider_type: The LLM provider type.
            user_id: The user identifier.

        Returns:
            Global key response dict.

        Raises:
            NotFoundError: If no global key exists for this provider.
        """
        doc = await self.db.global_api_keys.find_one({
            "userId": user_id,
            "providerType": provider_type.value,
        })

        if not doc:
            raise NotFoundError("global_api_key", provider_type.value)

        return self._global_key_doc_to_response(doc)

    async def set_global_key(
        self,
        provider_type: LLMProviderType,
        request: GlobalAPIKeyCreate,
        user_id: str,
    ) -> dict:
        """Set or update a global API key for a provider.

        Args:
            provider_type: The LLM provider type.
            request: API key and scopes to set.
            user_id: The user identifier.

        Returns:
            Updated global key response dict.
        """
        now = datetime.now(timezone.utc)

        encrypted_key = encrypt_value(request.api_key)
        api_key_last4 = request.api_key[-4:] if len(request.api_key) >= 4 else request.api_key

        doc = await self.db.global_api_keys.find_one({
            "userId": user_id,
            "providerType": provider_type.value,
        })

        if doc:
            # Update existing key
            await self.db.global_api_keys.update_one(
                {"userId": user_id, "providerType": provider_type.value},
                {
                    "$set": {
                        "apiKeyEncrypted": encrypted_key,
                        "apiKeyLast4": api_key_last4,
                        "scopes": [s.value for s in request.scopes],
                        "isValid": None,
                        "lastValidatedAt": None,
                        "updatedAt": now,
                    }
                },
            )
            logger.info(
                "global_key_updated",
                provider_type=provider_type.value,
                user_id=user_id,
            )
        else:
            # Create new key
            new_doc = {
                "userId": user_id,
                "providerType": provider_type.value,
                "apiKeyEncrypted": encrypted_key,
                "apiKeyLast4": api_key_last4,
                "scopes": [s.value for s in request.scopes],
                "isValid": None,
                "lastValidatedAt": None,
                "createdAt": now,
                "updatedAt": now,
            }
            await self.db.global_api_keys.insert_one(new_doc)
            logger.info(
                "global_key_created",
                provider_type=provider_type.value,
                user_id=user_id,
            )

        # Return updated document
        updated_doc = await self.db.global_api_keys.find_one({
            "userId": user_id,
            "providerType": provider_type.value,
        })
        return self._global_key_doc_to_response(updated_doc)

    async def delete_global_key(
        self, provider_type: LLMProviderType, user_id: str
    ) -> dict:
        """Delete a global API key for a provider.

        Args:
            provider_type: The LLM provider type.
            user_id: The user identifier.

        Returns:
            Confirmation dict.

        Raises:
            NotFoundError: If no global key exists for this provider.
        """
        doc = await self.db.global_api_keys.find_one({
            "userId": user_id,
            "providerType": provider_type.value,
        })

        if not doc:
            raise NotFoundError("global_api_key", provider_type.value)

        await self.db.global_api_keys.delete_one({
            "userId": user_id,
            "providerType": provider_type.value,
        })

        logger.info(
            "global_key_deleted",
            provider_type=provider_type.value,
            user_id=user_id,
        )

        return {"deleted": True, "providerType": provider_type.value}

    async def validate_global_key(
        self, provider_type: LLMProviderType, user_id: str
    ) -> dict:
        """Validate a global API key by testing the API connection.

        Args:
            provider_type: The LLM provider type.
            user_id: The user identifier.

        Returns:
            Validation result dict.

        Raises:
            NotFoundError: If no global key exists for this provider.
        """
        doc = await self.db.global_api_keys.find_one({
            "userId": user_id,
            "providerType": provider_type.value,
        })

        if not doc:
            raise NotFoundError("global_api_key", provider_type.value)

        now = datetime.now(timezone.utc)
        api_key = decrypt_value(doc["apiKeyEncrypted"])

        is_valid = False
        message = ""

        try:
            if provider_type == LLMProviderType.ANTHROPIC:
                is_valid, message, _ = await self._validate_anthropic(api_key)
            elif provider_type == LLMProviderType.OPENAI:
                is_valid, message, _ = await self._validate_openai(api_key, None)
            elif provider_type == LLMProviderType.OPENROUTER:
                is_valid, message, _ = await self._validate_openrouter(api_key)
            elif provider_type == LLMProviderType.OLLAMA:
                # Ollama doesn't use API keys, but we can validate connectivity
                # For global key, user should store base URL separately
                is_valid = True
                message = "Ollama does not require API key validation"
            else:
                message = f"Unsupported provider type: {provider_type}"
        except Exception as e:
            logger.error(
                "global_key_validation_error",
                provider_type=provider_type.value,
                error=str(e),
            )
            message = f"Validation failed: {str(e)}"

        # Update validation status
        await self.db.global_api_keys.update_one(
            {"userId": user_id, "providerType": provider_type.value},
            {"$set": {"isValid": is_valid, "lastValidatedAt": now, "updatedAt": now}},
        )

        logger.info(
            "global_key_validated",
            provider_type=provider_type.value,
            is_valid=is_valid,
        )

        return {
            "provider_type": provider_type.value,
            "is_valid": is_valid,
            "message": message,
            "validated_at": now,
        }

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _doc_to_response(self, doc: dict) -> dict:
        """Convert a database document to an API response dictionary."""
        return {
            "config_id": doc["providerId"],  # Map legacy field to new name
            "name": doc["name"],
            "type": doc["type"],
            "api_key_last4": doc.get("apiKeyLast4"),
            "api_key_set": doc.get("apiKeyEncrypted") is not None,
            "base_url": doc.get("baseUrl"),
            "model": doc["model"],
            "is_default": doc.get("isDefault", False),
            "is_valid": doc.get("isValid"),
            "last_validated_at": doc.get("lastValidatedAt"),
            "created_by": doc["createdBy"],
            "created_at": doc["createdAt"],
            "updated_at": doc["updatedAt"],
        }

    def _global_key_doc_to_response(self, doc: dict) -> dict:
        """Convert a global key document to an API response dictionary."""
        return {
            "provider_type": doc["providerType"],
            "api_key_last4": doc.get("apiKeyLast4", ""),
            "api_key_set": doc.get("apiKeyEncrypted") is not None,
            "scopes": doc.get("scopes", ["chat", "meta", "title_gen"]),
            "is_valid": doc.get("isValid"),
            "last_validated_at": doc.get("lastValidatedAt"),
            "created_at": doc["createdAt"],
            "updated_at": doc["updatedAt"],
        }
