"""Tests for RedisClient utility methods and lifecycle."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hydra.core.config import Settings
from hydra.db import redis as redis_module
from hydra.db.redis import RedisClient, get_redis, redis_lifespan


def make_settings() -> Settings:
    return Settings(
        env="development",
        debug=True,
        mongodb_uri="mongodb://localhost:27017",
        mongodb_database="hydra_test",
        redis_url="redis://localhost:6379/1",
        jwt_secret="test-secret-key",
        jwt_expire_minutes=60,
    )


def test_client_property_requires_connect():
    client = RedisClient(settings=make_settings())
    with pytest.raises(RuntimeError):
        _ = client.client


@pytest.mark.asyncio
async def test_connect_initializes_client_and_runs_health_check():
    settings = make_settings()
    client = RedisClient(settings=settings)
    mock_raw_client = MagicMock()

    with (
        patch("hydra.db.redis.redis.from_url", return_value=mock_raw_client) as from_url,
        patch.object(client, "health_check", AsyncMock(return_value=True)) as health_check,
    ):
        await client.connect()

    from_url.assert_called_once()
    health_check.assert_awaited_once()
    assert client.client is mock_raw_client


@pytest.mark.asyncio
async def test_disconnect_closes_client():
    client = RedisClient(settings=make_settings())
    mock_raw_client = MagicMock()
    mock_raw_client.close = AsyncMock()
    client._client = mock_raw_client

    await client.disconnect()

    mock_raw_client.close.assert_awaited_once()
    assert client._client is None


@pytest.mark.asyncio
async def test_health_check_success_returns_true():
    client = RedisClient(settings=make_settings())
    client._client = MagicMock()
    client._client.ping = AsyncMock(return_value=True)

    assert await client.health_check() is True


@pytest.mark.asyncio
async def test_health_check_failure_returns_false_and_schedules_notification():
    client = RedisClient(settings=make_settings())
    client._client = MagicMock()
    client._client.ping = AsyncMock(side_effect=redis_module.redis.RedisError("down"))

    emit_notification = AsyncMock()

    def close_scheduled_coro(coro):
        coro.close()

    with (
        patch("hydra.api.v1.services.notifications.emit_notification", emit_notification),
        patch(
            "hydra.api.v1.core.tasks.safe_create_task",
            side_effect=close_scheduled_coro,
        ) as safe_create_task,
    ):
        result = await client.health_check()

    assert result is False
    safe_create_task.assert_called_once()


@pytest.mark.asyncio
async def test_cache_operations_use_prefixes():
    client = RedisClient(settings=make_settings())
    client._client = MagicMock()
    client._client.get = AsyncMock(return_value="value")
    client._client.setex = AsyncMock()
    client._client.delete = AsyncMock()

    assert await client.cache_get("my-key") == "value"
    await client.cache_set("my-key", "value", ttl_seconds=10)
    await client.cache_delete("my-key")

    client._client.get.assert_awaited_once_with("cache:my-key")
    client._client.setex.assert_awaited_once_with("cache:my-key", 10, "value")
    client._client.delete.assert_awaited_once_with("cache:my-key")


@pytest.mark.asyncio
async def test_queue_operations_use_prefixes():
    client = RedisClient(settings=make_settings())
    client._client = MagicMock()
    client._client.rpush = AsyncMock()
    client._client.blpop = AsyncMock(return_value=("cmd_queue:jobs", "payload"))

    await client.queue_push("jobs", "payload")
    popped = await client.queue_pop("jobs", timeout=5)

    client._client.rpush.assert_awaited_once_with("cmd_queue:jobs", "payload")
    client._client.blpop.assert_awaited_once_with("cmd_queue:jobs", timeout=5)
    assert popped == "payload"


@pytest.mark.asyncio
async def test_queue_pop_timeout_returns_none():
    client = RedisClient(settings=make_settings())
    client._client = MagicMock()
    client._client.blpop = AsyncMock(return_value=None)

    assert await client.queue_pop("jobs", timeout=1) is None


@pytest.mark.asyncio
async def test_rate_limit_check_uses_pipeline_result():
    client = RedisClient(settings=make_settings())
    pipe = MagicMock()
    pipe.incr = MagicMock()
    pipe.expire = MagicMock()
    pipe.execute = AsyncMock(return_value=[3, True])

    client._client = MagicMock()
    client._client.pipeline = MagicMock(return_value=pipe)

    assert await client.rate_limit_check("user-1", max_requests=5, window_seconds=60) is True
    assert await client.rate_limit_check("user-1", max_requests=2, window_seconds=60) is False


@pytest.mark.asyncio
async def test_publish_and_subscribe():
    client = RedisClient(settings=make_settings())
    pubsub = MagicMock()
    pubsub.subscribe = AsyncMock()

    client._client = MagicMock()
    client._client.publish = AsyncMock(return_value=2)
    client._client.pubsub = MagicMock(return_value=pubsub)

    assert await client.publish("events", "{}") == 2
    returned = await client.subscribe("events", "audit")

    assert returned is pubsub
    pubsub.subscribe.assert_awaited_once_with("events", "audit")


def test_get_redis_returns_singleton_instance():
    redis_module._redis = None
    first = get_redis()
    second = get_redis()
    assert first is second


@pytest.mark.asyncio
async def test_redis_lifespan_connects_and_disconnects():
    mock_client = MagicMock()
    mock_client.connect = AsyncMock()
    mock_client.disconnect = AsyncMock()

    with patch("hydra.db.redis.get_redis", return_value=mock_client):
        async with redis_lifespan() as yielded:
            assert yielded is mock_client

    mock_client.connect.assert_awaited_once()
    mock_client.disconnect.assert_awaited_once()
