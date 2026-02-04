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
from hydra.api.v1.services.ai.global_keys import GlobalKeysMixin
from hydra.api.v1.services.ai.providers import ProviderValidationMixin
from hydra.api.v1.services.chat_cache import ChatCacheService
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)


class LLMConfigNotFoundError(NotFoundError):
    """LLM configuration not found."""

    def __init__(self, config_id: str):
        super().__init__("llm_config", config_id)


class AIService(ProviderValidationMixin, GlobalKeysMixin):
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
    ) -> tuple[list[dict], int]:
        """List LLM configurations created by a user.

        Args:
            user_id: The user identifier.
            limit: Maximum number of results to return.
            offset: Number of results to skip for pagination.

        Returns:
            Tuple of (configs list, total count).
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

        return configs, total

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
        except httpx.TimeoutException:
            logger.warning("config_validation_timeout", config_id=config_id)
            message = "Validation timed out"
        except httpx.ConnectError as e:
            logger.warning("config_validation_connection_error", config_id=config_id, error=str(e))
            message = "Cannot connect to provider API"
        except Exception as e:
            logger.error("config_validation_unexpected_error", config_id=config_id, error=str(e), error_type=type(e).__name__)
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
    # Provider Model Fetching (Orchestration)
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
        except httpx.TimeoutException:
            logger.warning("model_fetch_timeout", provider_type=provider_type.value)
            raise ValidationError("Request timed out while fetching models")
        except httpx.ConnectError as e:
            logger.warning("model_fetch_connection_error", provider_type=provider_type.value, error=str(e))
            raise ValidationError(f"Cannot connect to {provider_type.value} API")
        except Exception as e:
            logger.error("model_fetch_unexpected_error", provider_type=provider_type.value, error=str(e), error_type=type(e).__name__)
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
