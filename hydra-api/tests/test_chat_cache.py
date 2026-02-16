"""Tests for chat cache service."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import redis.exceptions

from hydra.api.v1.services import chat_cache
from hydra.api.v1.services.chat_cache import ChatCacheService, _json_serializer
from tests.utils import create_mock_cursor


@pytest.fixture
def redis_mock():
    mock = MagicMock()
    mock.cache_set = AsyncMock()
    mock.cache_get = AsyncMock(return_value=None)
    mock.cache_delete = AsyncMock()
    return mock


@pytest.mark.asyncio
async def test_json_serializer_handles_datetime():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    assert _json_serializer(now) == now.isoformat()


def test_json_serializer_raises_for_unknown_type():
    with pytest.raises(TypeError):
        _json_serializer(object())


@pytest.mark.asyncio
async def test_cache_session_messages_success(redis_mock):
    service = ChatCacheService(redis_client=redis_mock)
    messages = [{"role": "user", "content": "hello"}]

    await service.cache_session_messages("sess-1", messages)

    redis_mock.cache_set.assert_awaited_once()
    key, value, ttl = redis_mock.cache_set.await_args.args
    assert key == "chat:messages:sess-1"
    assert ttl == service.MESSAGES_TTL
    assert json.loads(value)[0]["content"] == "hello"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        redis.exceptions.ConnectionError("redis down"),
        redis.exceptions.TimeoutError("redis timeout"),
    ],
)
async def test_cache_session_messages_redis_errors_are_swallowed(redis_mock, error):
    service = ChatCacheService(redis_client=redis_mock)
    redis_mock.cache_set.side_effect = error

    await service.cache_session_messages("sess-1", [{"role": "user"}])


@pytest.mark.asyncio
async def test_cache_session_messages_json_error_is_swallowed(redis_mock):
    service = ChatCacheService(redis_client=redis_mock)
    with patch.object(
        chat_cache.json,
        "dumps",
        side_effect=json.JSONDecodeError("bad", "{}", 0),
    ):
        await service.cache_session_messages("sess-1", [{"role": "user"}])


@pytest.mark.asyncio
async def test_get_cached_messages_hit_and_miss(redis_mock):
    service = ChatCacheService(redis_client=redis_mock)
    redis_mock.cache_get.side_effect = [json.dumps([{"message": "hi"}]), None]

    hit = await service.get_cached_messages("sess-1")
    miss = await service.get_cached_messages("sess-2")

    assert hit == [{"message": "hi"}]
    assert miss is None


@pytest.mark.asyncio
async def test_get_cached_messages_invalid_json_returns_none(redis_mock):
    service = ChatCacheService(redis_client=redis_mock)
    redis_mock.cache_get.return_value = "{bad json"

    result = await service.get_cached_messages("sess-1")

    assert result is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        redis.exceptions.ConnectionError("redis down"),
        redis.exceptions.TimeoutError("redis timeout"),
    ],
)
async def test_get_cached_messages_redis_errors_return_none(redis_mock, error):
    service = ChatCacheService(redis_client=redis_mock)
    redis_mock.cache_get.side_effect = error

    result = await service.get_cached_messages("sess-1")

    assert result is None


@pytest.mark.asyncio
async def test_load_messages_from_db_without_mongo_returns_none(redis_mock):
    service = ChatCacheService(redis_client=redis_mock, mongodb=None)

    result = await service._load_messages_from_db("sess-1")

    assert result is None


@pytest.mark.asyncio
async def test_load_messages_from_db_formats_output(redis_mock):
    created_at = datetime(2026, 1, 1, tzinfo=UTC)
    docs = [
        {
            "messageId": "msg-1",
            "sessionId": "sess-1",
            "role": "assistant",
            "content": "ok",
            "toolCalls": [{"name": "x"}],
            "order": 1,
            "createdAt": created_at,
        }
    ]
    mongodb = MagicMock()
    mongodb.chat_messages.find.return_value = create_mock_cursor(docs)
    service = ChatCacheService(redis_client=redis_mock, mongodb=mongodb)

    result = await service._load_messages_from_db("sess-1")

    assert result == [
        {
            "message_id": "msg-1",
            "session_id": "sess-1",
            "role": "assistant",
            "content": "ok",
            "tool_calls": [{"name": "x"}],
            "order": 1,
            "created_at": created_at.isoformat(),
        }
    ]


@pytest.mark.asyncio
async def test_load_messages_from_db_error_returns_none(redis_mock):
    mongodb = MagicMock()
    mongodb.chat_messages.find.side_effect = RuntimeError("db failed")
    service = ChatCacheService(redis_client=redis_mock, mongodb=mongodb)

    result = await service._load_messages_from_db("sess-1")

    assert result is None


@pytest.mark.asyncio
async def test_append_message_to_existing_cache(redis_mock):
    service = ChatCacheService(redis_client=redis_mock)
    with (
        patch.object(service, "get_cached_messages", AsyncMock(return_value=[{"id": 1}])),
        patch.object(service, "cache_session_messages", AsyncMock()) as cache_messages,
    ):
        await service.append_message_to_cache("sess-1", {"id": 2})

    cache_messages.assert_awaited_once_with("sess-1", [{"id": 1}, {"id": 2}])


@pytest.mark.asyncio
async def test_append_message_rebuilds_from_db_on_cache_miss(redis_mock):
    service = ChatCacheService(redis_client=redis_mock)
    with (
        patch.object(service, "get_cached_messages", AsyncMock(return_value=None)),
        patch.object(service, "_load_messages_from_db", AsyncMock(return_value=[{"id": 1}])),
        patch.object(service, "cache_session_messages", AsyncMock()) as cache_messages,
    ):
        await service.append_message_to_cache("sess-1", {"id": 2})

    cache_messages.assert_awaited_once_with("sess-1", [{"id": 1}])


@pytest.mark.asyncio
async def test_append_message_seeds_cache_when_db_empty(redis_mock):
    service = ChatCacheService(redis_client=redis_mock)
    message = {"id": 2}
    with (
        patch.object(service, "get_cached_messages", AsyncMock(return_value=None)),
        patch.object(service, "_load_messages_from_db", AsyncMock(return_value=None)),
        patch.object(service, "cache_session_messages", AsyncMock()) as cache_messages,
    ):
        await service.append_message_to_cache("sess-1", message)

    cache_messages.assert_awaited_once_with("sess-1", [message])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        redis.exceptions.ConnectionError("redis down"),
        redis.exceptions.TimeoutError("redis timeout"),
    ],
)
async def test_append_message_redis_errors_are_swallowed(redis_mock, error):
    service = ChatCacheService(redis_client=redis_mock)
    with patch.object(service, "get_cached_messages", AsyncMock(side_effect=error)):
        await service.append_message_to_cache("sess-1", {"id": 2})


@pytest.mark.asyncio
async def test_invalidate_session_cache_deletes_both_keys(redis_mock):
    service = ChatCacheService(redis_client=redis_mock)

    await service.invalidate_session_cache("sess-1")

    redis_mock.cache_delete.assert_any_await("chat:messages:sess-1")
    redis_mock.cache_delete.assert_any_await("chat:context:sess-1")


@pytest.mark.asyncio
async def test_cache_and_get_context(redis_mock):
    service = ChatCacheService(redis_client=redis_mock)
    context = {"project": "default"}

    await service.cache_session_context("sess-1", context)
    redis_mock.cache_get.return_value = json.dumps(context)

    assert await service.get_cached_context("sess-1") == context


@pytest.mark.asyncio
async def test_get_cached_context_invalid_json_returns_none(redis_mock):
    service = ChatCacheService(redis_client=redis_mock)
    redis_mock.cache_get.return_value = "{bad json"

    result = await service.get_cached_context("sess-1")

    assert result is None


@pytest.mark.asyncio
async def test_context_redis_errors_are_handled(redis_mock):
    service = ChatCacheService(redis_client=redis_mock)
    redis_mock.cache_set.side_effect = redis.exceptions.ConnectionError("down")
    await service.cache_session_context("sess-1", {"x": 1})

    redis_mock.cache_get.side_effect = redis.exceptions.TimeoutError("timeout")
    assert await service.get_cached_context("sess-1") is None


@pytest.mark.asyncio
async def test_cache_get_invalidate_models(redis_mock):
    service = ChatCacheService(redis_client=redis_mock)
    models = [{"id": "gpt-4"}]

    await service.cache_provider_models("openai", models)
    redis_mock.cache_get.return_value = json.dumps(models)

    assert await service.get_cached_models("openai") == models

    await service.invalidate_models_cache("openai")
    redis_mock.cache_delete.assert_awaited_with("chat:models:openai")


@pytest.mark.asyncio
async def test_models_cache_errors_are_handled(redis_mock):
    service = ChatCacheService(redis_client=redis_mock)
    redis_mock.cache_set.side_effect = redis.exceptions.TimeoutError("timeout")
    await service.cache_provider_models("openai", [{"id": "x"}])

    redis_mock.cache_get.side_effect = redis.exceptions.ConnectionError("down")
    assert await service.get_cached_models("openai") is None

    redis_mock.cache_delete.side_effect = redis.exceptions.ConnectionError("down")
    await service.invalidate_models_cache("openai")
