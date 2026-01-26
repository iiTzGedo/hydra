"""AI/LLM provider management service."""

import secrets
from datetime import datetime, timezone

import httpx
import structlog

from hydra.api.v1.core.crypto import decrypt_value, encrypt_value, mask_api_key
from hydra.api.v1.core.exceptions import NotFoundError, ValidationError
from hydra.api.v1.models.ai import (
    LLMProviderCreate,
    LLMProviderType,
    LLMProviderUpdate,
)
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)


class LLMProviderNotFoundError(NotFoundError):
    """LLM provider not found."""

    def __init__(self, provider_id: str):
        super().__init__("llm_provider", provider_id)


class AIService:
    """AI/LLM provider management service."""

    def __init__(self, mongodb: MongoDB):
        self.db = mongodb

    async def list_providers(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """List LLM providers configured by a user.

        Args:
            user_id: The user identifier.
            limit: Maximum number of results to return.
            offset: Number of results to skip for pagination.

        Returns:
            Dict containing 'providers' list and 'total' count.
        """
        cursor = (
            self.db.ai_models.find({"createdBy": user_id})
            .sort("createdAt", -1)
            .skip(offset)
            .limit(limit)
        )

        providers = []
        async for doc in cursor:
            providers.append(self._doc_to_response(doc))

        total = await self.db.ai_models.count_documents({"createdBy": user_id})

        return {
            "providers": providers,
            "total": total,
        }

    async def get_provider(self, provider_id: str, user_id: str) -> dict:
        """Get a specific LLM provider by ID.

        Args:
            provider_id: The unique provider identifier.
            user_id: The owner's user identifier.

        Returns:
            The provider configuration as a dict.

        Raises:
            LLMProviderNotFoundError: If the provider does not exist or is not owned by user.
        """
        doc = await self.db.ai_models.find_one({
            "providerId": provider_id,
            "createdBy": user_id,
        })

        if not doc:
            raise LLMProviderNotFoundError(provider_id)

        return self._doc_to_response(doc)

    async def create_provider(
        self,
        request: LLMProviderCreate,
        user_id: str,
    ) -> dict:
        """Create a new LLM provider configuration.

        Args:
            request: Provider creation payload with name, type, API key, etc.
            user_id: The owner's user identifier.

        Returns:
            The created provider configuration.
        """
        now = datetime.now(timezone.utc)
        provider_id = f"llm_{secrets.token_urlsafe(8)}"

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
            "providerId": provider_id,
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
            "llm_provider_created",
            provider_id=provider_id,
            type=request.type.value,
            user_id=user_id,
        )

        return self._doc_to_response(doc)

    async def update_provider(
        self,
        provider_id: str,
        request: LLMProviderUpdate,
        user_id: str,
    ) -> dict:
        """Update an LLM provider configuration.

        Args:
            provider_id: The unique provider identifier.
            request: Update payload with optional name, API key, base URL, model.
            user_id: The owner's user identifier.

        Returns:
            The updated provider configuration.

        Raises:
            LLMProviderNotFoundError: If the provider does not exist or is not owned by user.
        """
        doc = await self.db.ai_models.find_one({
            "providerId": provider_id,
            "createdBy": user_id,
        })

        if not doc:
            raise LLMProviderNotFoundError(provider_id)

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
                    {"createdBy": user_id, "isDefault": True, "providerId": {"$ne": provider_id}},
                    {"$set": {"isDefault": False, "updatedAt": now}},
                )
            update_fields["isDefault"] = request.is_default

        await self.db.ai_models.update_one(
            {"providerId": provider_id},
            {"$set": update_fields},
        )

        updated_doc = await self.db.ai_models.find_one({"providerId": provider_id})

        logger.info(
            "llm_provider_updated",
            provider_id=provider_id,
            user_id=user_id,
        )

        return self._doc_to_response(updated_doc)

    async def delete_provider(self, provider_id: str, user_id: str) -> dict:
        """Delete an LLM provider configuration.

        Args:
            provider_id: The unique provider identifier.
            user_id: The owner's user identifier.

        Returns:
            Dict with 'deleted' status and 'providerId'.

        Raises:
            LLMProviderNotFoundError: If the provider does not exist or is not owned by user.
        """
        doc = await self.db.ai_models.find_one({
            "providerId": provider_id,
            "createdBy": user_id,
        })

        if not doc:
            raise LLMProviderNotFoundError(provider_id)

        await self.db.ai_models.delete_one({"providerId": provider_id})

        logger.info(
            "llm_provider_deleted",
            provider_id=provider_id,
            user_id=user_id,
        )

        return {"deleted": True, "providerId": provider_id}

    async def validate_provider(self, provider_id: str, user_id: str) -> dict:
        """Validate an LLM provider by testing the API connection.

        Makes a request to the provider's API to verify the configuration is valid.

        Args:
            provider_id: The unique provider identifier.
            user_id: The owner's user identifier.

        Returns:
            Validation result with 'is_valid', 'message', 'validated_at', and optional 'models' list.

        Raises:
            LLMProviderNotFoundError: If the provider does not exist or is not owned by user.
        """
        doc = await self.db.ai_models.find_one({
            "providerId": provider_id,
            "createdBy": user_id,
        })

        if not doc:
            raise LLMProviderNotFoundError(provider_id)

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
            else:
                message = f"Unsupported provider type: {provider_type}"
        except Exception as e:
            logger.error("provider_validation_error", provider_id=provider_id, error=str(e))
            message = f"Validation failed: {str(e)}"

        await self.db.ai_models.update_one(
            {"providerId": provider_id},
            {"$set": {"isValid": is_valid, "lastValidatedAt": now, "updatedAt": now}},
        )

        logger.info(
            "llm_provider_validated",
            provider_id=provider_id,
            is_valid=is_valid,
        )

        return {
            "provider_id": provider_id,
            "is_valid": is_valid,
            "message": message,
            "validated_at": now,
            "models": models,
        }

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

    def _doc_to_response(self, doc: dict) -> dict:
        """Convert a database document to an API response dictionary."""
        return {
            "provider_id": doc["providerId"],
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
