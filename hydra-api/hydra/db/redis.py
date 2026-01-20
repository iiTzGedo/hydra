"""Redis client for caching and command queue."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as redis
import structlog

from hydra.core.config import Settings, get_settings

logger = structlog.get_logger(__name__)


class RedisClient:
    """Redis connection manager."""

    CACHE_PREFIX = "cache:"
    COMMAND_QUEUE_PREFIX = "cmd_queue:"
    SESSION_PREFIX = "session:"
    RATE_LIMIT_PREFIX = "rate:"

    def __init__(self, settings: Settings | None = None):
        """Initialize Redis connection manager.

        Args:
            settings: Application settings (uses global if not provided).
        """
        self.settings = settings or get_settings()
        self._client: redis.Redis | None = None

    @property
    def client(self) -> redis.Redis:
        """Get the Redis client.

        Raises:
            RuntimeError: If client not initialized.
        """
        if self._client is None:
            raise RuntimeError("Redis client not initialized. Call connect() first.")
        return self._client

    async def connect(self) -> None:
        """Establish connection to Redis."""
        logger.info(
            "connecting_to_redis",
            url=str(self.settings.redis_url).replace(
                self.settings.redis_url.host or "", "***"
            ),
        )

        self._client = redis.from_url(
            str(self.settings.redis_url),
            max_connections=self.settings.redis_max_connections,
            decode_responses=True,
        )

        await self.health_check()
        logger.info("redis_connected")

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("redis_disconnected")

    async def health_check(self) -> bool:
        """Check if Redis connection is healthy.

        Returns:
            True if healthy, False otherwise.
        """
        try:
            await self.client.ping()
            return True
        except redis.RedisError as e:
            logger.error("redis_health_check_failed", error=str(e))
            return False

    async def cache_get(self, key: str) -> str | None:
        """Get a cached value.

        Args:
            key: Cache key (without prefix).

        Returns:
            Cached value or None if not found.
        """
        return await self.client.get(f"{self.CACHE_PREFIX}{key}")

    async def cache_set(self, key: str, value: str, ttl_seconds: int = 300) -> None:
        """Set a cached value with TTL.

        Args:
            key: Cache key (without prefix).
            value: Value to cache.
            ttl_seconds: Time-to-live in seconds.
        """
        await self.client.setex(f"{self.CACHE_PREFIX}{key}", ttl_seconds, value)

    async def cache_delete(self, key: str) -> None:
        """Delete a cached value.

        Args:
            key: Cache key (without prefix).
        """
        await self.client.delete(f"{self.CACHE_PREFIX}{key}")

    async def queue_push(self, queue_name: str, value: str) -> None:
        """Push a value to a queue.

        Args:
            queue_name: Queue name (without prefix).
            value: Value to push.
        """
        await self.client.rpush(f"{self.COMMAND_QUEUE_PREFIX}{queue_name}", value)

    async def queue_pop(self, queue_name: str, timeout: int = 0) -> str | None:
        """Pop a value from a queue (blocking).

        Args:
            queue_name: Queue name (without prefix).
            timeout: Block timeout in seconds (0 = indefinite).

        Returns:
            Popped value or None if timeout.
        """
        result = await self.client.blpop(
            f"{self.COMMAND_QUEUE_PREFIX}{queue_name}", timeout=timeout
        )
        return result[1] if result else None

    async def rate_limit_check(self, key: str, max_requests: int, window_seconds: int) -> bool:
        """Check and update rate limit.

        Args:
            key: Rate limit key (e.g., user ID or IP).
            max_requests: Maximum requests allowed in window.
            window_seconds: Time window in seconds.

        Returns:
            True if request is allowed, False if rate limited.
        """
        full_key = f"{self.RATE_LIMIT_PREFIX}{key}"
        pipe = self.client.pipeline()
        pipe.incr(full_key)
        pipe.expire(full_key, window_seconds)
        results = await pipe.execute()
        current_count = results[0]
        return current_count <= max_requests


_redis: RedisClient | None = None


def get_redis() -> RedisClient:
    """Get the global Redis instance.

    Returns:
        Singleton RedisClient instance.
    """
    global _redis
    if _redis is None:
        _redis = RedisClient()
    return _redis


@asynccontextmanager
async def redis_lifespan() -> AsyncGenerator[RedisClient, None]:
    """Context manager for Redis lifecycle.

    Yields:
        Connected RedisClient instance.
    """
    redis_client = get_redis()
    await redis_client.connect()
    try:
        yield redis_client
    finally:
        await redis_client.disconnect()
