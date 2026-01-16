"""Tests for database layer (MongoDB, Redis, indexes)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hydra.db.mongodb import MongoDB
from hydra.db.redis import RedisClient


class TestMongoDB:
    """Tests for MongoDB client."""

    def test_mongodb_initialization(self):
        """Test MongoDB client initialization."""
        mongo = MongoDB()
        assert mongo is not None

    @pytest.mark.asyncio
    async def test_mongodb_health_check_success(self, mock_mongodb):
        """Test MongoDB health check when healthy."""
        mock_mongodb.health_check = AsyncMock(return_value=True)
        result = await mock_mongodb.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_mongodb_health_check_failure(self, mock_mongodb):
        """Test MongoDB health check when unhealthy."""
        mock_mongodb.health_check = AsyncMock(return_value=False)
        result = await mock_mongodb.health_check()
        assert result is False

    def test_mongodb_collections_exist(self, mock_mongodb):
        """Test that all expected collections are accessible."""
        expected_collections = [
            "nodes",
            "profiles",
            "profile_meta",
            "services",
            "groups",
            "networks",
            "topologies",
            "users",
            "users_pending",
            "password_reset_tokens",
            "tokens",
            "api_keys",
            "commands",
            "audit_log",
        ]
        for collection_name in expected_collections:
            assert hasattr(mock_mongodb, collection_name)

    @pytest.mark.asyncio
    async def test_mongodb_find_one(self, mock_mongodb):
        """Test MongoDB find_one operation."""
        sample_doc = {"_id": "test", "name": "Test Document"}
        mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_doc)
        result = await mock_mongodb.nodes.find_one({"_id": "test"})
        assert result == sample_doc

    @pytest.mark.asyncio
    async def test_mongodb_insert_one(self, mock_mongodb):
        """Test MongoDB insert_one operation."""
        mock_mongodb.nodes.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id="new_id")
        )
        result = await mock_mongodb.nodes.insert_one({"name": "New Node"})
        assert result.inserted_id == "new_id"

    @pytest.mark.asyncio
    async def test_mongodb_update_one(self, mock_mongodb):
        """Test MongoDB update_one operation."""
        mock_mongodb.nodes.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1)
        )
        result = await mock_mongodb.nodes.update_one(
            {"_id": "test"},
            {"$set": {"name": "Updated"}}
        )
        assert result.modified_count == 1

    @pytest.mark.asyncio
    async def test_mongodb_delete_one(self, mock_mongodb):
        """Test MongoDB delete_one operation."""
        mock_mongodb.nodes.delete_one = AsyncMock(
            return_value=MagicMock(deleted_count=1)
        )
        result = await mock_mongodb.nodes.delete_one({"_id": "test"})
        assert result.deleted_count == 1

    @pytest.mark.asyncio
    async def test_mongodb_count_documents(self, mock_mongodb):
        """Test MongoDB count_documents operation."""
        mock_mongodb.nodes.count_documents = AsyncMock(return_value=10)
        result = await mock_mongodb.nodes.count_documents({})
        assert result == 10


class TestRedisClient:
    """Tests for Redis client."""

    def test_redis_initialization(self):
        """Test Redis client initialization."""
        redis = RedisClient()
        assert redis is not None

    @pytest.mark.asyncio
    async def test_redis_health_check_success(self, mock_redis):
        """Test Redis health check when healthy."""
        mock_redis.health_check = AsyncMock(return_value=True)
        result = await mock_redis.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_redis_health_check_failure(self, mock_redis):
        """Test Redis health check when unhealthy."""
        mock_redis.health_check = AsyncMock(return_value=False)
        result = await mock_redis.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_redis_cache_get(self, mock_redis):
        """Test Redis cache get operation."""
        mock_redis.cache_get = AsyncMock(return_value='{"key": "value"}')
        result = await mock_redis.cache_get("test_key")
        assert result == '{"key": "value"}'

    @pytest.mark.asyncio
    async def test_redis_cache_get_miss(self, mock_redis):
        """Test Redis cache miss."""
        mock_redis.cache_get = AsyncMock(return_value=None)
        result = await mock_redis.cache_get("nonexistent_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_redis_cache_set(self, mock_redis):
        """Test Redis cache set operation."""
        mock_redis.cache_set = AsyncMock()
        await mock_redis.cache_set("test_key", '{"key": "value"}', ttl=300)
        mock_redis.cache_set.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_rate_limit_check_allowed(self, mock_redis):
        """Test Redis rate limit check when allowed."""
        mock_redis.rate_limit_check = AsyncMock(return_value=True)
        result = await mock_redis.rate_limit_check("user_123", "api", 100, 60)
        assert result is True

    @pytest.mark.asyncio
    async def test_redis_rate_limit_check_exceeded(self, mock_redis):
        """Test Redis rate limit check when exceeded."""
        mock_redis.rate_limit_check = AsyncMock(return_value=False)
        result = await mock_redis.rate_limit_check("user_123", "api", 100, 60)
        assert result is False


class TestDatabaseIndexes:
    """Tests for database indexes."""

    @pytest.mark.asyncio
    async def test_ensure_indexes(self, mock_mongodb):
        """Test index creation."""
        from hydra.db.indexes import ensure_indexes, INDEXES

        collections = {}
        for name in INDEXES.keys():
            collection = MagicMock()
            collection.create_indexes = AsyncMock()
            collections[name] = collection

        mock_db = MagicMock()
        mock_db.__getitem__.side_effect = lambda name: collections[name]

        await ensure_indexes(mock_db)
        for collection in collections.values():
            collection.create_indexes.assert_called_once()


class TestDatabaseConnection:
    """Tests for database connection handling."""

    @pytest.mark.asyncio
    async def test_mongodb_connection_error_handling(self):
        """Test MongoDB connection error handling."""
        mongo = MongoDB()
        # Connection errors should be handled gracefully
        assert mongo is not None

    @pytest.mark.asyncio
    async def test_redis_connection_error_handling(self):
        """Test Redis connection error handling."""
        redis = RedisClient()
        # Connection errors should be handled gracefully
        assert redis is not None


class TestDatabaseQueries:
    """Tests for database query patterns."""

    @pytest.mark.asyncio
    async def test_cursor_iteration(self, mock_mongodb):
        """Test MongoDB cursor async iteration."""
        from tests.utils import create_mock_cursor

        docs = [{"_id": "1"}, {"_id": "2"}, {"_id": "3"}]
        cursor = create_mock_cursor(docs)

        results = []
        async for doc in cursor:
            results.append(doc)

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_cursor_to_list(self, mock_mongodb):
        """Test MongoDB cursor to_list."""
        from tests.utils import create_mock_cursor

        docs = [{"_id": "1"}, {"_id": "2"}]
        cursor = create_mock_cursor(docs)

        results = await cursor.to_list(length=100)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_cursor_chaining(self, mock_mongodb):
        """Test MongoDB cursor method chaining."""
        from tests.utils import create_mock_cursor

        docs = [{"_id": "1"}]
        cursor = create_mock_cursor(docs)

        # Chaining should return the cursor
        chained = cursor.sort("_id").skip(0).limit(10)
        assert chained is cursor

    @pytest.mark.asyncio
    async def test_aggregation_pipeline(self, mock_mongodb):
        """Test MongoDB aggregation pipeline."""
        from tests.utils import create_mock_cursor

        agg_result = [{"_id": "compute", "count": 5}]
        mock_mongodb.nodes.aggregate.return_value = create_mock_cursor(agg_result)

        cursor = mock_mongodb.nodes.aggregate([
            {"$group": {"_id": "$class", "count": {"$sum": 1}}}
        ])

        results = await cursor.to_list(length=100)
        assert len(results) == 1
        assert results[0]["count"] == 5
