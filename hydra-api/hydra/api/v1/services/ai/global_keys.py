"""Global API key management methods for AIService.

Contains mixin class for CRUD and validation of global (per-provider) API keys
that are shared across all of a user's LLM configurations.
"""

from datetime import datetime, timezone

import httpx
import structlog

from hydra.api.v1.core.crypto import decrypt_value, encrypt_value
from hydra.api.v1.core.exceptions import NotFoundError
from hydra.api.v1.models.ai import (
    GlobalAPIKeyCreate,
    LLMProviderType,
)

logger = structlog.get_logger(__name__)


class GlobalKeysMixin:
    """Mixin providing global API key management methods.

    Requires the host class to have:
    - self.db: MongoDB instance with global_api_keys collection
    - self._validate_anthropic(), _validate_openai(), _validate_openrouter(),
      _validate_ollama() methods (from ProviderValidationMixin)
    """

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
        except httpx.TimeoutException:
            logger.warning("global_key_validation_timeout", provider_type=provider_type.value)
            message = "Validation timed out"
        except httpx.ConnectError as e:
            logger.warning("global_key_validation_connection_error", provider_type=provider_type.value, error=str(e))
            message = "Cannot connect to provider API"
        except Exception as e:
            logger.error("global_key_validation_unexpected_error", provider_type=provider_type.value, error=str(e), error_type=type(e).__name__)
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
