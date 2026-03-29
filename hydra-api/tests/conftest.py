"""Pytest configuration and fixtures."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from hydra.core.config import Settings, clear_settings_cache, get_settings, override_settings
from hydra.api.v1.core.security import create_access_token
from hydra.db.mongodb import MongoDB, get_mongodb
from hydra.db.redis import RedisClient, get_redis
from hydra.main import app
from hydra.api.v1.main import app as v1_app
from tests.utils import create_mock_cursor


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def _clear_settings():
    """Clear settings cache between tests to ensure isolation."""
    clear_settings_cache()
    yield
    clear_settings_cache()


@pytest.fixture
def test_settings() -> Settings:
    """Get test settings and inject as global override."""
    settings = Settings(
        env="development",
        debug=True,
        mongodb_uri="mongodb://localhost:27017",
        mongodb_database="hydra_test",
        redis_url="redis://localhost:6379/1",
        jwt_secret="test-secret-key",
        jwt_expire_minutes=60,
    )
    with override_settings(settings):
        yield settings


def create_mock_collection() -> MagicMock:
    """Create a mock MongoDB collection with common async methods."""
    collection = MagicMock()
    collection.find_one = AsyncMock(return_value=None)
    collection.find_one_and_update = AsyncMock(return_value=None)
    collection.find_one_and_delete = AsyncMock(return_value=None)
    collection.insert_one = AsyncMock()
    collection.insert_many = AsyncMock()
    collection.update_one = AsyncMock()
    collection.update_many = AsyncMock()
    collection.delete_one = AsyncMock()
    collection.delete_many = AsyncMock()
    collection.count_documents = AsyncMock(return_value=0)
    collection.find = MagicMock(return_value=create_mock_cursor([]))
    collection.aggregate = MagicMock(return_value=create_mock_cursor([]))
    return collection


@pytest.fixture
def mock_mongodb():
    """Create a mock MongoDB client."""
    mock = MagicMock(spec=MongoDB)

    # Create mock collections with proper async methods
    mock.nodes = create_mock_collection()
    mock.profiles = create_mock_collection()
    mock.profile_meta = create_mock_collection()
    mock.services = create_mock_collection()
    mock.groups = create_mock_collection()
    mock.networks = create_mock_collection()
    mock.topologies = create_mock_collection()
    mock.users = create_mock_collection()
    mock.users_pending = create_mock_collection()
    mock.password_reset_tokens = create_mock_collection()
    mock.tokens = create_mock_collection()
    mock.api_keys = create_mock_collection()
    mock.commands = create_mock_collection()
    mock.command_definitions = create_mock_collection()
    mock.workflows = create_mock_collection()
    mock.workflow_executions = create_mock_collection()
    mock.audit_log = create_mock_collection()
    mock.docs = create_mock_collection()
    mock.ai_models = create_mock_collection()
    mock.chat_sessions = create_mock_collection()
    mock.chat_messages = create_mock_collection()
    mock.mcp_servers = create_mock_collection()
    mock.user_settings = create_mock_collection()
    mock.system_settings = create_mock_collection()

    # Health check
    mock.health_check = AsyncMock(return_value=True)

    return mock


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    mock = MagicMock(spec=RedisClient)
    mock.health_check = AsyncMock(return_value=True)
    mock.cache_get = AsyncMock(return_value=None)
    mock.cache_set = AsyncMock()
    mock.rate_limit_check = AsyncMock(return_value=True)
    return mock


@pytest_asyncio.fixture
async def client(mock_mongodb, mock_redis) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client with mocked dependencies."""
    v1_app.dependency_overrides[get_mongodb] = lambda: mock_mongodb
    v1_app.dependency_overrides[get_redis] = lambda: mock_redis

    @asynccontextmanager
    async def _test_lifespan(_: FastAPI):
        yield

    app.router.lifespan_context = _test_lifespan

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    v1_app.dependency_overrides.clear()


@pytest.fixture
def admin_token(test_settings) -> str:
    """Create an admin JWT token."""
    settings = get_settings()
    return create_access_token(
        subject="user_admin123",
        token_type="access",
        additional_claims={
            "sub_type": "user",
            "role": "admin",
            "permissions": ["*:*"],
        },
        settings=settings,
    )


@pytest.fixture
def agent_token(test_settings) -> str:
    """Create an agent JWT token."""
    settings = get_settings()
    return create_access_token(
        subject="test-node-01",
        token_type="access",
        additional_claims={
            "sub_type": "agent",
        },
        settings=settings,
    )


@pytest.fixture
def viewer_token(test_settings) -> str:
    """Create a viewer JWT token."""
    settings = get_settings()
    return create_access_token(
        subject="user_viewer123",
        token_type="access",
        additional_claims={
            "sub_type": "user",
            "role": "viewer",
            "permissions": [
                "nodes:read",
                "profiles:read",
                "services:read",
            ],
        },
        settings=settings,
    )


# Sample data fixtures
@pytest.fixture
def sample_node():
    """Sample node document."""
    now = datetime.now(timezone.utc)
    return {
        "nodeId": "test-server-01",
        "class": "compute",
        "type": "physical",
        "kind": "bare-metal",
        "displayName": "Test Server 01",
        "description": "A test server",
        "tags": ["test", "development"],
        "parentNodeId": None,
        "agentTier": "normal",
        "networkIds": ["net-192-168-1"],
        "location": {"site": "home", "room": "server-room"},
        "registeredAt": now,
        "lastUpdated": now,
        "lastProfileAt": now,
        "status": "active",
    }


@pytest.fixture
def sample_profile():
    """Sample profile document."""
    now = datetime.now(timezone.utc)
    return {
        "profileId": "prof_abc123",
        "nodeId": "test-server-01",
        "version": "E0-0.0.0.1",
        "collectedAt": now,
        "submittedAt": now,
        "agentVersion": "0.1.0",
        "collectionLevel": "neutral",
        "serviceIds": ["svc-nginx-a1b2"],
        "hardware": {
            "systemManufacturer": "Dell",
            "systemModel": "PowerEdge R640",
            "cpu": {
                "model": "Intel Xeon Gold 6230",
                "coresPhysical": 20,
                "coresLogical": 40,
                "frequencyMhz": 2100,
            },
            "memory": {"totalBytes": 137438953472},
            "gpus": [],
        },
        "network": {
            "hostname": "test-server-01",
            "interfaces": [
                {
                    "name": "eth0",
                    "macAddress": "00:11:22:33:44:55",
                    "ipv4Addresses": ["192.168.1.100"],
                    "ipv6Addresses": [],
                    "state": "up",
                }
            ],
            "dnsServers": ["8.8.8.8", "8.8.4.4"],
        },
        "storage": {
            "blockDevices": [{"name": "sda", "sizeBytes": 500107862016, "type": "disk"}],
            "filesystems": [
                {
                    "mountPoint": "/",
                    "device": "/dev/sda1",
                    "fsType": "ext4",
                    "sizeBytes": 500107862016,
                    "usedBytes": 100000000000,
                }
            ],
        },
        "software": {
            "os": {
                "name": "Ubuntu",
                "version": "22.04",
                "kernelVersion": "5.15.0-91-generic",
                "family": "linux",
            },
            "packages": [],
            "packageCount": 0,
        },
        "metadata": {},
    }


@pytest.fixture
def sample_user():
    """Sample user document."""
    now = datetime.now(timezone.utc)
    return {
        "userId": "user_test123",
        "username": "testuser",
        "email": "test@example.com",
        "passwordHash": "$2b$12$test",
        "role": "viewer",
        "permissions": [],
        "status": "active",
        "createdAt": now,
        "updatedAt": now,
    }


@pytest.fixture
def sample_registration_token():
    """Sample registration token document."""
    now = datetime.now(timezone.utc)
    return {
        "token": "reg_test_token_abc123",
        "type": "registration",
        "description": "Test token",
        "scope": "node",
        "createdBy": "user_admin123",
        "expiresAt": datetime(2099, 12, 31, tzinfo=timezone.utc),
        "maxUses": 10,
        "usedCount": 0,
        "usedBy": [],
        "createdAt": now,
    }
