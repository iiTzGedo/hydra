"""Redis-backed caching service for chat data."""

import json
from datetime import datetime
from typing import Any

import redis.exceptions
import structlog

from hydra.db.redis import RedisClient, get_redis

logger = structlog.get_logger(__name__)


def _json_serializer(obj: Any) -> str:
    """JSON serializer for objects not serializable by default json encoder.

    Handles datetime objects by converting to ISO format string.
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class ChatCacheService:
    """Redis-backed caching for chat sessions and provider models."""

    # Cache key prefixes
    MESSAGES_PREFIX = "chat:messages:"
    CONTEXT_PREFIX = "chat:context:"
    MODELS_PREFIX = "chat:models:"

    # TTL values in seconds
    MESSAGES_TTL = 3600  # 1 hour
    CONTEXT_TTL = 300  # 5 minutes
    MODELS_TTL = 3600  # 1 hour

    def __init__(self, redis_client: RedisClient | None = None):
        """Initialize the chat cache service.

        Args:
            redis_client: Redis client instance. Uses global if not provided.
        """
        self._redis = redis_client or get_redis()

    # =========================================================================
    # Session Messages Cache
    # =========================================================================

    async def cache_session_messages(
        self, session_id: str, messages: list[dict[str, Any]]
    ) -> None:
        """Cache messages for a session.

        Args:
            session_id: Chat session identifier.
            messages: List of message documents to cache.
        """
        try:
            key = f"{self.MESSAGES_PREFIX}{session_id}"
            value = json.dumps(messages, default=_json_serializer)
            await self._redis.cache_set(key, value, self.MESSAGES_TTL)
            logger.debug("messages_cached", session_id=session_id, count=len(messages))
        except redis.exceptions.ConnectionError as e:
            logger.warning("cache_messages_failed", session_id=session_id, error=str(e), error_type="redis_connection")
        except redis.exceptions.TimeoutError as e:
            logger.warning("cache_messages_failed", session_id=session_id, error=str(e), error_type="redis_timeout")
        except json.JSONDecodeError as e:
            logger.warning("cache_messages_failed", session_id=session_id, error=str(e), error_type="json_encode")
        except Exception as e:
            logger.error("cache_messages_unexpected_error", session_id=session_id, error=str(e), error_type=type(e).__name__)

    async def get_cached_messages(self, session_id: str) -> list[dict[str, Any]] | None:
        """Get cached messages for a session.

        Args:
            session_id: Chat session identifier.

        Returns:
            Cached messages list or None if cache miss.
        """
        try:
            key = f"{self.MESSAGES_PREFIX}{session_id}"
            value = await self._redis.cache_get(key)
            if value:
                messages = json.loads(value)
                logger.debug(
                    "messages_cache_hit", session_id=session_id, count=len(messages)
                )
                return messages
            logger.debug("messages_cache_miss", session_id=session_id)
            return None
        except redis.exceptions.ConnectionError as e:
            logger.warning("cache_get_messages_failed", session_id=session_id, error=str(e), error_type="redis_connection")
            return None
        except redis.exceptions.TimeoutError as e:
            logger.warning("cache_get_messages_failed", session_id=session_id, error=str(e), error_type="redis_timeout")
            return None
        except json.JSONDecodeError as e:
            logger.warning("cache_get_messages_failed", session_id=session_id, error=str(e), error_type="json_decode")
            return None
        except Exception as e:
            logger.error("cache_get_messages_unexpected_error", session_id=session_id, error=str(e), error_type=type(e).__name__)
            return None

    async def append_message_to_cache(
        self, session_id: str, message: dict[str, Any]
    ) -> None:
        """Append a new message to the cached messages.

        Args:
            session_id: Chat session identifier.
            message: Message document to append.
        """
        try:
            existing = await self.get_cached_messages(session_id)
            if existing is not None:
                existing.append(message)
                await self.cache_session_messages(session_id, existing)
                logger.debug("message_appended_to_cache", session_id=session_id)
        except redis.exceptions.ConnectionError as e:
            logger.warning("cache_append_message_failed", session_id=session_id, error=str(e), error_type="redis_connection")
        except redis.exceptions.TimeoutError as e:
            logger.warning("cache_append_message_failed", session_id=session_id, error=str(e), error_type="redis_timeout")
        except Exception as e:
            logger.error("cache_append_message_unexpected_error", session_id=session_id, error=str(e), error_type=type(e).__name__)

    async def invalidate_session_cache(self, session_id: str) -> None:
        """Invalidate all caches for a session.

        Args:
            session_id: Chat session identifier.
        """
        try:
            messages_key = f"{self.MESSAGES_PREFIX}{session_id}"
            context_key = f"{self.CONTEXT_PREFIX}{session_id}"
            await self._redis.cache_delete(messages_key)
            await self._redis.cache_delete(context_key)
            logger.debug("session_cache_invalidated", session_id=session_id)
        except redis.exceptions.ConnectionError as e:
            logger.warning("cache_invalidate_failed", session_id=session_id, error=str(e), error_type="redis_connection")
        except redis.exceptions.TimeoutError as e:
            logger.warning("cache_invalidate_failed", session_id=session_id, error=str(e), error_type="redis_timeout")
        except Exception as e:
            logger.error("cache_invalidate_unexpected_error", session_id=session_id, error=str(e), error_type=type(e).__name__)

    # =========================================================================
    # Session Context Cache
    # =========================================================================

    async def cache_session_context(
        self, session_id: str, context: dict[str, Any]
    ) -> None:
        """Cache session context.

        Args:
            session_id: Chat session identifier.
            context: Session context data.
        """
        try:
            key = f"{self.CONTEXT_PREFIX}{session_id}"
            value = json.dumps(context, default=_json_serializer)
            await self._redis.cache_set(key, value, self.CONTEXT_TTL)
            logger.debug("context_cached", session_id=session_id)
        except redis.exceptions.ConnectionError as e:
            logger.warning("cache_context_failed", session_id=session_id, error=str(e), error_type="redis_connection")
        except redis.exceptions.TimeoutError as e:
            logger.warning("cache_context_failed", session_id=session_id, error=str(e), error_type="redis_timeout")
        except json.JSONDecodeError as e:
            logger.warning("cache_context_failed", session_id=session_id, error=str(e), error_type="json_encode")
        except Exception as e:
            logger.error("cache_context_unexpected_error", session_id=session_id, error=str(e), error_type=type(e).__name__)

    async def get_cached_context(self, session_id: str) -> dict[str, Any] | None:
        """Get cached session context.

        Args:
            session_id: Chat session identifier.

        Returns:
            Cached context or None if cache miss.
        """
        try:
            key = f"{self.CONTEXT_PREFIX}{session_id}"
            value = await self._redis.cache_get(key)
            if value:
                logger.debug("context_cache_hit", session_id=session_id)
                return json.loads(value)
            logger.debug("context_cache_miss", session_id=session_id)
            return None
        except redis.exceptions.ConnectionError as e:
            logger.warning("cache_get_context_failed", session_id=session_id, error=str(e), error_type="redis_connection")
            return None
        except redis.exceptions.TimeoutError as e:
            logger.warning("cache_get_context_failed", session_id=session_id, error=str(e), error_type="redis_timeout")
            return None
        except json.JSONDecodeError as e:
            logger.warning("cache_get_context_failed", session_id=session_id, error=str(e), error_type="json_decode")
            return None
        except Exception as e:
            logger.error("cache_get_context_unexpected_error", session_id=session_id, error=str(e), error_type=type(e).__name__)
            return None

    # =========================================================================
    # Provider Models Cache
    # =========================================================================

    async def cache_provider_models(
        self, provider_type: str, models: list[dict[str, Any]]
    ) -> None:
        """Cache fetched models for a provider.

        Args:
            provider_type: LLM provider type (anthropic, openai, etc.).
            models: List of model data to cache.
        """
        try:
            key = f"{self.MODELS_PREFIX}{provider_type}"
            value = json.dumps(models, default=_json_serializer)
            await self._redis.cache_set(key, value, self.MODELS_TTL)
            logger.debug(
                "models_cached", provider_type=provider_type, count=len(models)
            )
        except redis.exceptions.ConnectionError as e:
            logger.warning("cache_models_failed", provider_type=provider_type, error=str(e), error_type="redis_connection")
        except redis.exceptions.TimeoutError as e:
            logger.warning("cache_models_failed", provider_type=provider_type, error=str(e), error_type="redis_timeout")
        except json.JSONDecodeError as e:
            logger.warning("cache_models_failed", provider_type=provider_type, error=str(e), error_type="json_encode")
        except Exception as e:
            logger.error("cache_models_unexpected_error", provider_type=provider_type, error=str(e), error_type=type(e).__name__)

    async def get_cached_models(self, provider_type: str) -> list[dict[str, Any]] | None:
        """Get cached models for a provider.

        Args:
            provider_type: LLM provider type.

        Returns:
            Cached models list or None if cache miss.
        """
        try:
            key = f"{self.MODELS_PREFIX}{provider_type}"
            value = await self._redis.cache_get(key)
            if value:
                models = json.loads(value)
                logger.debug(
                    "models_cache_hit", provider_type=provider_type, count=len(models)
                )
                return models
            logger.debug("models_cache_miss", provider_type=provider_type)
            return None
        except redis.exceptions.ConnectionError as e:
            logger.warning("cache_get_models_failed", provider_type=provider_type, error=str(e), error_type="redis_connection")
            return None
        except redis.exceptions.TimeoutError as e:
            logger.warning("cache_get_models_failed", provider_type=provider_type, error=str(e), error_type="redis_timeout")
            return None
        except json.JSONDecodeError as e:
            logger.warning("cache_get_models_failed", provider_type=provider_type, error=str(e), error_type="json_decode")
            return None
        except Exception as e:
            logger.error("cache_get_models_unexpected_error", provider_type=provider_type, error=str(e), error_type=type(e).__name__)
            return None

    async def invalidate_models_cache(self, provider_type: str) -> None:
        """Invalidate cached models for a provider.

        Args:
            provider_type: LLM provider type.
        """
        try:
            key = f"{self.MODELS_PREFIX}{provider_type}"
            await self._redis.cache_delete(key)
            logger.debug("models_cache_invalidated", provider_type=provider_type)
        except redis.exceptions.ConnectionError as e:
            logger.warning("cache_invalidate_models_failed", provider_type=provider_type, error=str(e), error_type="redis_connection")
        except redis.exceptions.TimeoutError as e:
            logger.warning("cache_invalidate_models_failed", provider_type=provider_type, error=str(e), error_type="redis_timeout")
        except Exception as e:
            logger.error("cache_invalidate_models_unexpected_error", provider_type=provider_type, error=str(e), error_type=type(e).__name__)
