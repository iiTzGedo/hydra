"""Tests for command execution endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from bson import ObjectId
from httpx import AsyncClient

from tests.utils import create_mock_cursor


def _mock_insert_one_result() -> MagicMock:
    """Return a mock that mimics pymongo InsertOneResult."""
    result = MagicMock()
    result.inserted_id = ObjectId()
    result.acknowledged = True
    return result


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def sample_definition():
    """Sample command definition (registry entry)."""
    return {
        "registryId": "reg::service::restart",
        "category": "service",
        "action": "restart",
        "displayName": "Restart Service",
        "description": "Restart a service",
        "targetSchema": {"required": ["nodeId", "serviceId"]},
        "parametersSchema": None,
        "execution": {
            "runtimes": {"systemd": "systemctl restart {service}"},
            "handler": None,
            "timeout": 60,
            "deliveryMode": "poll_only",
            "retryable": True,
            "maxRetries": 1,
        },
        "rbac": {
            "minimumRole": "operator",
            "requiresConfirmation": False,
            "confirmationMessage": None,
        },
        "audit": {"logLevel": "standard", "captureOutput": True, "sensitiveParameters": []},
        "metadata": {
            "version": "0.5.0",
            "addedAt": datetime.now(UTC),
            "builtIn": True,
            "deprecated": False,
        },
    }


@pytest.fixture
def sample_managed_service():
    """Sample service doc used for command target normalization."""
    now = datetime.now(UTC)
    return {
        "serviceId": "svc-nginx-a1b2",
        "nodeId": "server-01",
        "profileId": "prof_abc123",
        "name": "nginx",
        "displayName": "Nginx",
        "runtime": "systemd",
        "status": "running",
        "image": None,
        "origin": {
            "nativeId": "nginx.service",
            "discoveredBy": "agent",
            "collectedAt": now,
        },
        "firstSeen": now,
        "lastSeen": now,
    }


@pytest.fixture
def sample_container_service():
    """Sample container service for update-command normalization tests."""
    now = datetime.now(UTC)
    return {
        "serviceId": "svc-app-c3d4",
        "nodeId": "server-01",
        "profileId": "prof_abc123",
        "name": "app",
        "displayName": "App",
        "runtime": "docker",
        "status": "running",
        "image": "ghcr.io/acme/app:1.4.2",
        "origin": {
            "nativeId": "app",
            "discoveredBy": "agent",
            "collectedAt": now,
        },
        "firstSeen": now,
        "lastSeen": now,
    }


@pytest.fixture
def sample_command():
    """Sample command document."""
    now = datetime.now(UTC)
    return {
        "commandId": "cmd-abc123",
        "registryId": "reg::service::restart",
        "type": "service",
        "target": {"nodeId": "server-01", "serviceId": "svc-nginx-a1b2"},
        "action": "restart",
        "parameters": {},
        "status": "queued",
        "executionMethod": "agent-poll",
        "requestedBy": {"userId": "user_admin123", "source": "api"},
        "timeoutSeconds": 60,
        "retryCount": 0,
        "queuePosition": 1,
        "chain": None,
        "error": None,
        "result": None,
        "createdAt": now,
        "queuedAt": now,
        "startedAt": None,
        "completedAt": None,
        "cancelledAt": None,
        "cancelledBy": None,
    }


@pytest.fixture
def operator_token(test_settings):
    """Create an operator JWT token."""
    from hydra.api.v1.core.security import create_access_token
    from hydra.core.config import get_settings

    settings = get_settings()
    return create_access_token(
        subject="user_operator123",
        token_type="access",
        additional_claims={
            "sub_type": "user",
            "role": "operator",
            "permissions": [
                "nodes:read",
                "nodes:write",
                "profiles:read",
                "services:read",
                "commands:read",
                "commands:execute",
            ],
        },
        settings=settings,
    )


class DummyResponse:
    """Minimal HTTP response stub for direct-agent execution tests."""

    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload


def make_dummy_async_client(
    *,
    response: DummyResponse | None = None,
    error: Exception | None = None,
    capture: dict | None = None,
):
    """Build a dummy httpx.AsyncClient replacement for direct execution tests."""

    class _DummyAsyncClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, headers: dict | None = None, json: dict | None = None):
            if capture is not None:
                capture["url"] = url
                capture["headers"] = headers
                capture["json"] = json
            if error is not None:
                raise error
            return response or DummyResponse(200, {})

    return _DummyAsyncClient


def _setup_command_mocks(mock_mongodb, sample_user, sample_definition, *, role="admin"):
    """Common mock setup for command tests that need registry validation."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": role}
    )
    mock_mongodb.command_definitions.find_one = AsyncMock(return_value=sample_definition)
    mock_mongodb.commands.insert_one = AsyncMock()
    mock_mongodb.commands.count_documents = AsyncMock(return_value=0)


def trusted_write_headers(
    *,
    user_id: str = "user_admin123",
    role: str = "admin",
    client_id: str = "hydra-web",
) -> dict[str, str]:
    """Build trusted internal-request headers for write-path tests."""
    return {
        "X-Hydra-Internal-Request": "true",
        "X-Hydra-Internal-Secret": "internal-secret-for-tests-0123456789",
        "X-Hydra-User-Id": user_id,
        "X-Hydra-Role": role,
        "X-Hydra-Client-Id": client_id,
    }


# ── Command Creation ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_command_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_command,
    sample_user,
    sample_definition,
    sample_managed_service,
):
    """Test creating a new command with registryId."""
    _setup_command_mocks(mock_mongodb, sample_user, sample_definition)
    mock_mongodb.nodes.find_one = AsyncMock(
        return_value={"nodeId": "server-01", "status": "active"}
    )
    mock_mongodb.services.find_one = AsyncMock(return_value=sample_managed_service)

    response = await client.post(
        "/api/v1/commands",
        json={
            "registryId": "reg::service::restart",
            "target": {"nodeId": "server-01", "serviceId": "svc-nginx-a1b2"},
        },
        headers=trusted_write_headers(),
    )

    assert response.status_code == 202
    data = response.json()
    assert data["data"]["target"]["nodeId"] == "server-01"
    assert data["data"]["status"] == "queued"
    assert data["data"]["executionMethod"] == "agent-poll"
    inserted = mock_mongodb.commands.insert_one.await_args.args[0]
    assert inserted["parameters"]["serviceId"] == "svc-nginx-a1b2"
    assert inserted["parameters"]["name"] == "nginx"
    assert inserted["parameters"]["runtime"] == "systemd"


@pytest.mark.asyncio
async def test_create_command_unknown_registry_id(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test that unknown registryId is rejected."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.command_definitions.find_one = AsyncMock(return_value=None)
    mock_mongodb.commands.insert_one = AsyncMock()

    response = await client.post(
        "/api/v1/commands",
        json={
            "registryId": "reg::service::nonexistent",
            "target": {"nodeId": "server-01"},
        },
        headers=trusted_write_headers(),
    )

    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "COMMAND_DEFINITION_NOT_FOUND"


@pytest.mark.asyncio
async def test_create_command_rejects_bearer_write_origin(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test bearer-authenticated writes are rejected for command execution."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.commands.insert_one = AsyncMock()

    response = await client.post(
        "/api/v1/commands",
        json={
            "registryId": "reg::service::restart",
            "target": {"nodeId": "server-01", "serviceId": "svc-nginx-a1b2"},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 403
    data = response.json()
    assert data["error"]["code"] == "CLIENT_NOT_AUTHORIZED"
    mock_mongodb.commands.insert_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_command_insufficient_role(
    client: AsyncClient,
    mock_mongodb,
    operator_token,
    sample_user,
):
    """Test that insufficient role is rejected."""
    # Admin-only command, operator tries to execute
    admin_only_def = {
        "registryId": "reg::node::reboot",
        "category": "node",
        "action": "reboot",
        "execution": {"timeout": 120},
        "rbac": {"minimumRole": "admin", "requiresConfirmation": True},
        "metadata": {"builtIn": True},
    }
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_operator123", "role": "operator"}
    )
    mock_mongodb.command_definitions.find_one = AsyncMock(return_value=admin_only_def)
    mock_mongodb.commands.insert_one = AsyncMock()

    response = await client.post(
        "/api/v1/commands",
        json={
            "registryId": "reg::node::reboot",
            "target": {"nodeId": "server-01"},
        },
        headers=trusted_write_headers(user_id="user_operator123", role="operator"),
    )

    assert response.status_code == 403
    data = response.json()
    assert data["error"]["code"] == "COMMAND_REJECTED"


@pytest.mark.asyncio
async def test_create_command_rejects_lite_tier(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_definition,
    sample_managed_service,
):
    """Test lite-tier nodes reject command execution."""
    _setup_command_mocks(mock_mongodb, sample_user, sample_definition)
    mock_mongodb.nodes.find_one = AsyncMock(
        return_value={
            "nodeId": "server-01",
            "status": "active",
            "agentTier": "lite",
        }
    )
    mock_mongodb.services.find_one = AsyncMock(return_value=sample_managed_service)

    response = await client.post(
        "/api/v1/commands",
        json={
            "registryId": "reg::service::restart",
            "target": {"nodeId": "server-01", "serviceId": "svc-nginx-a1b2"},
        },
        headers=trusted_write_headers(),
    )

    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "COMMAND_NOT_SUPPORTED"


@pytest.mark.asyncio
async def test_create_command_normal_tier_queues_for_poll(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_definition,
    sample_managed_service,
):
    """Test normal-tier nodes queue commands for polling."""
    _setup_command_mocks(mock_mongodb, sample_user, sample_definition)
    mock_mongodb.nodes.find_one = AsyncMock(
        return_value={
            "nodeId": "server-01",
            "status": "active",
            "agentTier": "normal",
        }
    )
    mock_mongodb.services.find_one = AsyncMock(return_value=sample_managed_service)

    response = await client.post(
        "/api/v1/commands",
        json={
            "registryId": "reg::service::restart",
            "target": {"nodeId": "server-01", "serviceId": "svc-nginx-a1b2"},
        },
        headers=trusted_write_headers(),
    )

    assert response.status_code == 202
    data = response.json()
    assert data["data"]["executionMethod"] == "agent-poll"
    assert data["data"]["status"] == "queued"
    inserted = mock_mongodb.commands.insert_one.await_args.args[0]
    assert inserted["parameters"]["name"] == "nginx"
    mock_mongodb.commands.insert_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_command_max_tier_poll_only_skips_direct_execution(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_definition,
    sample_managed_service,
    monkeypatch,
):
    """Test poll-only commands do not attempt direct execution on max tier."""
    _setup_command_mocks(mock_mongodb, sample_user, sample_definition)
    mock_mongodb.nodes.find_one = AsyncMock(
        return_value={
            "nodeId": "server-01",
            "status": "active",
            "agentTier": "max",
            "serverAddress": "agent.internal.example",
            "serverPort": 9443,
            "serverTlsEnabled": True,
            "agentServerSecret": "hsk_api_secret_123",
        }
    )
    mock_mongodb.services.find_one = AsyncMock(return_value=sample_managed_service)

    def fail_if_called(**kwargs):
        raise AssertionError("direct execution should not be attempted for poll-only commands")

    monkeypatch.setattr(
        "hydra.api.v1.services.commands.service.httpx.AsyncClient",
        fail_if_called,
    )

    response = await client.post(
        "/api/v1/commands",
        json={
            "registryId": "reg::service::restart",
            "target": {"nodeId": "server-01", "serviceId": "svc-nginx-a1b2"},
        },
        headers=trusted_write_headers(),
    )

    assert response.status_code == 202
    data = response.json()
    assert data["data"]["executionMethod"] == "agent-poll"
    mock_mongodb.commands.insert_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_command_max_tier_transport_failure_falls_back(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_managed_service,
    monkeypatch,
):
    """Test transport errors fall back to polling and count against reachability."""
    direct_definition = {
        "registryId": "reg::service::logs",
        "category": "service",
        "action": "logs",
        "targetSchema": {"required": ["nodeId", "serviceId"]},
        "execution": {"timeout": 30, "deliveryMode": "direct_or_poll"},
        "rbac": {"minimumRole": "operator", "requiresConfirmation": False},
        "metadata": {"builtIn": True},
    }
    _setup_command_mocks(mock_mongodb, sample_user, direct_definition)
    mock_mongodb.nodes.find_one = AsyncMock(
        return_value={
            "nodeId": "server-01",
            "status": "active",
            "agentTier": "max",
            "serverAddress": "agent.internal.example",
            "serverPort": 9443,
            "serverTlsEnabled": True,
            "agentServerSecret": "hsk_api_secret_123",
            "serverReachable": True,
            "failedDirectAttempts": 2,
        }
    )
    mock_mongodb.services.find_one = AsyncMock(return_value=sample_managed_service)
    mock_mongodb.nodes.find_one_and_update = AsyncMock(
        return_value={"nodeId": "server-01", "failedDirectAttempts": 3}
    )
    mock_mongodb.nodes.update_one = AsyncMock()

    capture: dict = {}
    request = httpx.Request("POST", "https://agent.internal.example:9443/execute")
    monkeypatch.setattr(
        "hydra.api.v1.services.commands.service.httpx.AsyncClient",
        make_dummy_async_client(
            error=httpx.ConnectError("connect failed", request=request),
            capture=capture,
        ),
    )

    response = await client.post(
        "/api/v1/commands",
        json={
            "registryId": "reg::service::logs",
            "target": {
                "nodeId": "server-01",
                "serviceId": "svc-nginx-a1b2",
            },
            "parameters": {"lines": 250},
            "timeoutSeconds": 120,
        },
        headers=trusted_write_headers(),
    )

    assert response.status_code == 202
    data = response.json()
    assert data["data"]["executionMethod"] == "agent-poll"
    assert capture["url"] == "https://agent.internal.example:9443/execute"
    assert capture["json"]["registryId"] == "reg::service::logs"
    assert capture["json"]["parameters"]["name"] == "nginx"
    mock_mongodb.nodes.find_one_and_update.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_command_max_tier_http_501_falls_back(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_managed_service,
    monkeypatch,
):
    """Test agent HTTP errors fall back to polling without poisoning reachability."""
    direct_definition = {
        "registryId": "reg::service::logs",
        "category": "service",
        "action": "logs",
        "targetSchema": {"required": ["nodeId", "serviceId"]},
        "execution": {"timeout": 30, "deliveryMode": "direct_or_poll"},
        "rbac": {"minimumRole": "operator", "requiresConfirmation": False},
        "metadata": {"builtIn": True},
    }
    _setup_command_mocks(mock_mongodb, sample_user, direct_definition)
    mock_mongodb.nodes.find_one = AsyncMock(
        return_value={
            "nodeId": "server-01",
            "status": "active",
            "agentTier": "max",
            "serverAddress": "agent.internal.example",
            "serverPort": 9443,
            "serverTlsEnabled": True,
            "agentServerSecret": "hsk_api_secret_123",
            "serverReachable": True,
            "failedDirectAttempts": 2,
        }
    )
    mock_mongodb.services.find_one = AsyncMock(return_value=sample_managed_service)
    mock_mongodb.nodes.find_one_and_update = AsyncMock()
    mock_mongodb.nodes.update_one = AsyncMock()

    monkeypatch.setattr(
        "hydra.api.v1.services.commands.service.httpx.AsyncClient",
        make_dummy_async_client(
            response=DummyResponse(501, {"error": {"code": "NOT_IMPLEMENTED"}}),
        ),
    )

    response = await client.post(
        "/api/v1/commands",
        json={
            "registryId": "reg::service::logs",
            "target": {
                "nodeId": "server-01",
                "serviceId": "svc-nginx-a1b2",
            },
        },
        headers=trusted_write_headers(),
    )

    assert response.status_code == 202
    data = response.json()
    assert data["data"]["executionMethod"] == "agent-poll"
    mock_mongodb.nodes.find_one_and_update.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_service_update_derives_image_from_version(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_container_service,
):
    """Test service update requests derive the execution image from version."""
    update_definition = {
        "registryId": "reg::service::update",
        "category": "service",
        "action": "update",
        "targetSchema": {"required": ["nodeId", "serviceId"]},
        "execution": {"timeout": 300, "deliveryMode": "poll_only"},
        "rbac": {"minimumRole": "admin", "requiresConfirmation": True},
        "metadata": {"builtIn": True},
    }
    _setup_command_mocks(mock_mongodb, sample_user, update_definition)
    mock_mongodb.nodes.find_one = AsyncMock(
        return_value={"nodeId": "server-01", "status": "active", "agentTier": "normal"}
    )
    mock_mongodb.services.find_one = AsyncMock(return_value=sample_container_service)

    response = await client.post(
        "/api/v1/commands",
        json={
            "registryId": "reg::service::update",
            "target": {"nodeId": "server-01", "serviceId": "svc-app-c3d4"},
            "parameters": {"version": "2.0.0"},
        },
        headers=trusted_write_headers(),
    )

    assert response.status_code == 202
    inserted = mock_mongodb.commands.insert_one.await_args.args[0]
    assert inserted["parameters"]["serviceId"] == "svc-app-c3d4"
    assert inserted["parameters"]["runtime"] == "docker"
    assert inserted["parameters"]["image"] == "ghcr.io/acme/app:2.0.0"


@pytest.mark.asyncio
async def test_create_command_rejects_service_node_mismatch(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_definition,
    sample_managed_service,
):
    """Test service commands reject targets when the service belongs to another node."""
    _setup_command_mocks(mock_mongodb, sample_user, sample_definition)
    mock_mongodb.nodes.find_one = AsyncMock(
        return_value={"nodeId": "server-01", "status": "active", "agentTier": "normal"}
    )
    mock_mongodb.services.find_one = AsyncMock(
        return_value={**sample_managed_service, "nodeId": "server-02"}
    )

    response = await client.post(
        "/api/v1/commands",
        json={
            "registryId": "reg::service::restart",
            "target": {"nodeId": "server-01", "serviceId": "svc-nginx-a1b2"},
        },
        headers=trusted_write_headers(),
    )

    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "belongs to node" in data["error"]["message"]


# ── List / Get / Cancel ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_commands_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_command,
    sample_user,
):
    """Test listing commands."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.commands.count_documents = AsyncMock(return_value=1)
    mock_mongodb.commands.find.return_value = create_mock_cursor([sample_command])

    response = await client.get(
        "/api/v1/commands",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["commandId"] == sample_command["commandId"]


@pytest.mark.asyncio
async def test_list_commands_with_filters(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_command,
    sample_user,
):
    """Test listing commands with filters."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.commands.count_documents = AsyncMock(return_value=1)
    mock_mongodb.commands.find.return_value = create_mock_cursor([sample_command])

    response = await client.get(
        "/api/v1/commands?nodeId=server-01&serviceId=svc-nginx-a1b2&type=service&status=queued",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    query = mock_mongodb.commands.count_documents.await_args.args[0]
    assert query["target.nodeId"] == "server-01"
    assert query["target.serviceId"] == "svc-nginx-a1b2"
    assert query["type"] == "service"
    assert query["status"] == "queued"


@pytest.mark.asyncio
async def test_get_command_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_command,
    sample_user,
):
    """Test getting a specific command."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.commands.find_one = AsyncMock(return_value=sample_command)

    response = await client.get(
        f"/api/v1/commands/{sample_command['commandId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["commandId"] == sample_command["commandId"]
    assert data["data"]["registryId"] == "reg::service::restart"


@pytest.mark.asyncio
async def test_get_command_not_found(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test getting a non-existent command."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.commands.find_one = AsyncMock(return_value=None)

    response = await client.get(
        "/api/v1/commands/cmd-nonexistent",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cancel_command_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_command,
    sample_user,
):
    """Test cancelling a command."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.commands.find_one = AsyncMock(return_value=sample_command)
    mock_mongodb.commands.update_one = AsyncMock(return_value=MagicMock(modified_count=1))

    response = await client.post(
        f"/api/v1/commands/{sample_command['commandId']}/cancel",
        headers=trusted_write_headers(),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["status"] == "cancelled"
    assert "cancelledAt" in data["data"]


@pytest.mark.asyncio
async def test_cancel_cascade_cancels_chain_siblings(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_command,
    sample_user,
):
    """Cascade cancel cancels sibling commands in the same chain."""
    chain_id = "chain-abc-001"
    chained_command = {
        **sample_command,
        "chain": {"chainId": chain_id, "step": 1},
    }
    sibling = {
        "commandId": "cmd-sibling-001",
        "status": "queued",
        "chain": {"chainId": chain_id, "step": 2},
    }
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.commands.find_one = AsyncMock(return_value=chained_command)
    mock_mongodb.commands.update_one = AsyncMock(return_value=MagicMock(modified_count=1))

    async def _fake_find(query, **kwargs):
        """Yield siblings matching the chain query."""
        for doc in [sibling]:
            yield doc

    mock_mongodb.commands.find = MagicMock(side_effect=_fake_find)

    response = await client.post(
        f"/api/v1/commands/{chained_command['commandId']}/cancel?confirmCascade=true",
        headers=trusted_write_headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["cascadeCancelledIds"] == ["cmd-sibling-001"]
    # Primary + sibling = 2 update_one calls
    assert mock_mongodb.commands.update_one.call_count == 2


@pytest.mark.asyncio
async def test_cancel_without_cascade_does_not_cancel_siblings(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_command,
    sample_user,
):
    """Default cancel (no cascade) leaves siblings untouched."""
    chained_command = {
        **sample_command,
        "chain": {"chainId": "chain-xyz", "step": 1},
    }
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.commands.find_one = AsyncMock(return_value=chained_command)
    mock_mongodb.commands.update_one = AsyncMock(return_value=MagicMock(modified_count=1))

    response = await client.post(
        f"/api/v1/commands/{chained_command['commandId']}/cancel",
        headers=trusted_write_headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data.get("cascadeCancelledIds") is None
    # Only primary command cancelled
    assert mock_mongodb.commands.update_one.call_count == 1


@pytest.mark.asyncio
async def test_cancel_cascade_noop_for_unchained_command(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_command,
    sample_user,
):
    """Cascade on a command without a chain is a no-op."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    # sample_command has chain: None
    mock_mongodb.commands.find_one = AsyncMock(return_value=sample_command)
    mock_mongodb.commands.update_one = AsyncMock(return_value=MagicMock(modified_count=1))

    response = await client.post(
        f"/api/v1/commands/{sample_command['commandId']}/cancel?confirmCascade=true",
        headers=trusted_write_headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data.get("cascadeCancelledIds") is None
    assert mock_mongodb.commands.update_one.call_count == 1


@pytest.mark.asyncio
async def test_confirm_command_rejects_cross_user(
    client: AsyncClient,
    mock_mongodb,
    sample_command,
    sample_user,
):
    """Test only the original requester can confirm a pending command."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_operator456", "role": "operator"}
    )
    pending_command = {
        **sample_command,
        "status": "pending_confirmation",
        "requestedBy": {"userId": "user_admin123", "source": "web"},
        "confirmationExpiresAt": datetime.now(UTC),
    }
    mock_mongodb.commands.find_one = AsyncMock(return_value=pending_command)

    response = await client.post(
        f"/api/v1/commands/{sample_command['commandId']}/confirm",
        headers=trusted_write_headers(user_id="user_operator456", role="operator"),
    )

    assert response.status_code == 403
    data = response.json()
    assert data["error"]["code"] == "COMMAND_REJECTED"
    assert "Only the user who requested this command may confirm it" in data["error"]["message"]


@pytest.mark.asyncio
async def test_confirm_command_rechecks_control_permission(
    client: AsyncClient,
    mock_mongodb,
    sample_user,
):
    """Test confirmation re-applies command control permissions."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_operator123", "role": "operator"}
    )
    mock_mongodb.commands.find_one = AsyncMock(
        return_value={
            "commandId": "cmd-pending-001",
            "registryId": "reg::node::reboot",
            "type": "node",
            "target": {"nodeId": "server-01"},
            "action": "reboot",
            "parameters": {},
            "status": "pending_confirmation",
            "executionMethod": None,
            "requestedBy": {"userId": "user_operator123", "source": "web"},
            "timeoutSeconds": 120,
            "retryCount": 0,
            "queuePosition": None,
            "chain": None,
            "error": None,
            "result": None,
            "createdAt": datetime.now(UTC),
            "queuedAt": None,
            "startedAt": None,
            "completedAt": None,
            "cancelledAt": None,
            "cancelledBy": None,
            "confirmationExpiresAt": datetime.now(UTC),
        }
    )
    mock_mongodb.command_definitions.find_one = AsyncMock(
        return_value={
            "registryId": "reg::node::reboot",
            "category": "node",
            "action": "reboot",
            "targetSchema": {"required": ["nodeId"]},
            "execution": {"timeout": 120},
            "rbac": {
                "minimumRole": "operator",
                "requiresConfirmation": True,
                "controlPermission": "nodes:control:reboot",
            },
            "metadata": {"builtIn": True},
        }
    )

    response = await client.post(
        "/api/v1/commands/cmd-pending-001/confirm",
        headers=trusted_write_headers(user_id="user_operator123", role="operator"),
    )

    assert response.status_code == 403
    data = response.json()
    assert data["error"]["code"] == "COMMAND_REJECTED"
    assert "nodes:control:reboot" in data["error"]["message"]


# ── Agent Endpoints ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_poll_commands_returns_typed_target(
    client: AsyncClient,
    mock_mongodb,
    agent_token,
    sample_command,
    sample_node,
):
    """Test polling returns the typed target contract and resets failures."""
    command_for_node = sample_command.copy()
    command_for_node["target"] = {
        "nodeId": sample_node["nodeId"],
        "serviceId": "svc-nginx-a1b2",
    }
    node_with_failures = {
        **sample_node,
        "serverReachable": True,
        "failedDirectAttempts": 2,
    }

    mock_mongodb.nodes.find_one = AsyncMock(return_value=node_with_failures)
    mock_mongodb.commands.find_one_and_update = AsyncMock(side_effect=[command_for_node, None])

    response = await client.get(
        f"/api/v1/nodes/{sample_node['nodeId']}/commands/poll",
        headers={"Authorization": f"Bearer {agent_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]["commands"]) == 1
    assert data["data"]["commands"][0]["target"] == {
        "nodeId": sample_node["nodeId"],
        "serviceId": "svc-nginx-a1b2",
    }
    assert data["data"]["commands"][0].get("registryId") == "reg::service::restart"
    poll_update = mock_mongodb.nodes.update_one.await_args.args[1]["$set"]
    assert poll_update["serverReachable"] is True
    assert poll_update["failedDirectAttempts"] == 0


@pytest.mark.asyncio
async def test_poll_commands_marks_network_scan_running(
    client: AsyncClient,
    mock_mongodb,
    agent_token,
    sample_node,
    monkeypatch,
):
    """Polling a delegated network scan updates the linked discovery scan."""
    command_for_node = {
        "commandId": "cmd-network-scan-001",
        "registryId": "reg::agent::network-scan",
        "type": "agent",
        "action": "network-scan",
        "target": {"nodeId": sample_node["nodeId"]},
        "parameters": {
            "scanId": "scan_delegated001",
            "targetSpecs": [{"subnet": "192.168.1.0/24"}],
        },
        "timeoutSeconds": 180,
        "status": "queued",
    }
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)
    mock_mongodb.commands.find_one_and_update = AsyncMock(
        side_effect=[command_for_node, None]
    )
    mark_running = AsyncMock()
    monkeypatch.setattr(
        "hydra.api.v1.services.discovery.DiscoveryService.mark_delegated_scan_running",
        mark_running,
    )

    response = await client.get(
        f"/api/v1/nodes/{sample_node['nodeId']}/commands/poll",
        headers={"Authorization": f"Bearer {agent_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]["commands"]
    assert len(data) == 1
    assert data[0]["registryId"] == "reg::agent::network-scan"
    await_args = mark_running.await_args
    assert await_args.args[0] == "scan_delegated001"


@pytest.mark.asyncio
async def test_submit_command_result(
    client: AsyncClient,
    mock_mongodb,
    agent_token,
    sample_command,
    sample_node,
):
    """Test submitting command result (agent endpoint)."""
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)

    command_for_node = sample_command.copy()
    command_for_node["target"] = {**sample_command["target"], "nodeId": sample_node["nodeId"]}
    mock_mongodb.commands.find_one = AsyncMock(return_value=command_for_node)
    mock_mongodb.commands.update_one = AsyncMock(return_value=MagicMock(modified_count=1))

    response = await client.post(
        f"/api/v1/nodes/{sample_node['nodeId']}/commands/{sample_command['commandId']}/result",
        json={
            "success": True,
            "output": "service restarted",
            "exitCode": 0,
            "error": None,
        },
        headers={"Authorization": f"Bearer {agent_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["status"] == "completed"


@pytest.mark.asyncio
async def test_submit_network_scan_result_triggers_discovery_ingest(
    client: AsyncClient,
    mock_mongodb,
    agent_token,
    sample_node,
    monkeypatch,
):
    """Submitting a network scan result hands the payload back to discovery."""
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)
    command_for_node = {
        "commandId": "cmd-network-scan-001",
        "registryId": "reg::agent::network-scan",
        "type": "agent",
        "action": "network-scan",
        "target": {"nodeId": sample_node["nodeId"]},
        "parameters": {"scanId": "scan_delegated001"},
        "status": "executing",
        "timeoutSeconds": 180,
    }
    mock_mongodb.commands.find_one = AsyncMock(return_value=command_for_node)
    mock_mongodb.commands.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    ingest = AsyncMock()
    monkeypatch.setattr(
        "hydra.api.v1.services.discovery.DiscoveryService.handle_scan_command_result",
        ingest,
    )

    response = await client.post(
        f"/api/v1/nodes/{sample_node['nodeId']}/commands/{command_for_node['commandId']}/result",
        json={
            "success": True,
            "output": "scan complete",
            "exitCode": 0,
            "error": None,
            "data": {
                "scanId": "scan_delegated001",
                "summary": {
                    "hostsScanned": 254,
                    "hostsAlive": 4,
                    "newDiscoveries": 2,
                    "returningDevices": 1,
                    "errors": [],
                },
                "results": [],
            },
        },
        headers={"Authorization": f"Bearer {agent_token}"},
    )

    assert response.status_code == 200
    await_args = ingest.await_args
    assert await_args.args[0]["commandId"] == "cmd-network-scan-001"
    assert await_args.args[1] is True
    assert await_args.args[2]["scanId"] == "scan_delegated001"


# ── Permission Tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_commands_forbidden_for_viewer(
    client: AsyncClient,
    mock_mongodb,
    viewer_token,
    sample_user,
):
    """Test that viewer cannot execute commands."""
    viewer_user = sample_user.copy()
    viewer_user["userId"] = "user_viewer123"
    viewer_user["role"] = "viewer"
    mock_mongodb.users.find_one = AsyncMock(return_value=viewer_user)

    response = await client.post(
        "/api/v1/commands",
        json={
            "registryId": "reg::service::restart",
            "target": {"nodeId": "server-01", "serviceId": "svc-nginx-a1b2"},
        },
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_commands_viewer_can_list(
    client: AsyncClient,
    mock_mongodb,
    viewer_token,
    sample_command,
    sample_user,
):
    """Test that viewer can list commands (has commands:read via P2C-001)."""
    viewer_user = sample_user.copy()
    viewer_user["userId"] = "user_viewer123"
    viewer_user["role"] = "viewer"
    mock_mongodb.users.find_one = AsyncMock(return_value=viewer_user)
    mock_mongodb.commands.count_documents = AsyncMock(return_value=1)
    mock_mongodb.commands.find.return_value = create_mock_cursor([sample_command])

    response = await client.get(
        "/api/v1/commands",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 200


# ── Pagination ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_commands_pagination(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_command,
    sample_user,
):
    """Test commands pagination."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.commands.count_documents = AsyncMock(return_value=100)
    mock_mongodb.commands.find.return_value = create_mock_cursor([sample_command])

    response = await client.get(
        "/api/v1/commands?limit=10&offset=20",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total"] == 100
    assert data["meta"]["limit"] == 10
    assert data["meta"]["offset"] == 20


@pytest.mark.asyncio
async def test_list_commands_since_filter(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_command,
    sample_user,
):
    """Test listing commands with since filter."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.commands.count_documents = AsyncMock(return_value=1)
    mock_mongodb.commands.find.return_value = create_mock_cursor([sample_command])

    response = await client.get(
        "/api/v1/commands?since=2024-01-01T00:00:00Z",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


# ── Queue View ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_queue_view(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_command,
    sample_user,
):
    """Test viewing the command queue."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.commands.count_documents = AsyncMock(return_value=1)
    mock_mongodb.commands.find_one = AsyncMock(return_value=sample_command)
    mock_mongodb.commands.find.return_value = create_mock_cursor([sample_command])

    response = await client.get(
        "/api/v1/commands/queue",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "queue" in data["data"]
    assert "stats" in data["data"]
    assert "totalQueued" in data["data"]["stats"]
    assert "totalExecuting" in data["data"]["stats"]


# ── Command Catalog ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_command_catalog(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_definition,
):
    """Test listing the command catalog."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.command_definitions.count_documents = AsyncMock(return_value=1)
    mock_mongodb.command_definitions.find.return_value = create_mock_cursor([sample_definition])

    response = await client.get(
        "/api/v1/command-catalog",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["registryId"] == "reg::service::restart"
    assert data["data"][0]["category"] == "service"
    assert data["data"][0]["minimumRole"] == "operator"
    assert data["data"][0]["deliveryMode"] == "poll_only"


@pytest.mark.asyncio
async def test_get_command_definition(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_definition,
):
    """Test getting a single command definition."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.command_definitions.find_one = AsyncMock(return_value=sample_definition)

    response = await client.get(
        "/api/v1/command-catalog/reg::service::restart",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["registryId"] == "reg::service::restart"
    assert data["data"]["action"] == "restart"
    assert data["data"]["rbac"]["minimumRole"] == "operator"
    assert data["data"]["execution"]["deliveryMode"] == "poll_only"


@pytest.mark.asyncio
async def test_get_command_definition_not_found(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test getting a non-existent command definition."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.command_definitions.find_one = AsyncMock(return_value=None)

    response = await client.get(
        "/api/v1/command-catalog/reg::service::nonexistent",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404


# ── Command Retries (P2B-002) ──────────────────────────────────────────


@pytest.fixture
def failed_command():
    """Sample failed command document."""
    now = datetime.now(UTC)
    return {
        "commandId": "cmd-failed-001",
        "registryId": "reg::service::restart",
        "type": "service",
        "target": {"nodeId": "server-01", "serviceId": "svc-nginx-a1b2"},
        "action": "restart",
        "parameters": {"serviceId": "svc-nginx-a1b2", "name": "nginx", "runtime": "systemd"},
        "status": "failed",
        "executionMethod": "agent-poll",
        "requestedBy": {"userId": "user_admin123", "source": "web", "clientId": "hydra-web"},
        "timeoutSeconds": 60,
        "retryCount": 0,
        "maxRetries": 3,
        "retriedFrom": None,
        "queuePosition": None,
        "chain": None,
        "error": {
            "code": "EXECUTION_FAILED",
            "message": "Service restart failed",
            "details": {"exitCode": 1},
        },
        "result": {
            "success": False,
            "output": None,
            "exitCode": 1,
            "error": "Service restart failed",
            "data": None,
        },
        "createdAt": now,
        "queuedAt": now,
        "startedAt": now,
        "completedAt": now,
        "cancelledAt": None,
        "cancelledBy": None,
    }


@pytest.fixture
def retryable_definition(sample_definition):
    """Definition with retryable enabled and maxRetries > 0."""
    defn = dict(sample_definition)
    defn["execution"] = {
        **defn["execution"],
        "retryable": True,
        "maxRetries": 3,
    }
    return defn


@pytest.mark.asyncio
async def test_retry_failed_command_succeeds(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    failed_command,
    retryable_definition,
    sample_user,
    sample_managed_service,
):
    """Test retrying a failed command creates a new queued command."""
    # First call returns the failed command; subsequent calls return updated docs
    mock_mongodb.commands.find_one = AsyncMock(
        side_effect=[
            failed_command,                # get_command (retry_command)
            retryable_definition,          # command_definitions.find_one -> handled separately
            failed_command,                # get original (same id)
            None,                          # Not used
        ]
    )
    mock_mongodb.command_definitions.find_one = AsyncMock(return_value=retryable_definition)
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.commands.update_one = AsyncMock()
    mock_mongodb.commands.insert_one = AsyncMock(return_value=_mock_insert_one_result())
    mock_mongodb.commands.count_documents = AsyncMock(return_value=0)
    mock_mongodb.nodes.find_one = AsyncMock(
        return_value={"nodeId": "server-01", "status": "active", "agentTier": "normal"}
    )
    mock_mongodb.services.find_one = AsyncMock(return_value=sample_managed_service)

    response = await client.post(
        "/api/v1/commands/cmd-failed-001/retry",
        headers=trusted_write_headers(),
    )

    assert response.status_code == 202
    data = response.json()
    assert data["data"]["originalCommandId"] == "cmd-failed-001"
    assert data["data"]["retryCount"] == 1
    assert data["data"]["maxRetries"] == 3
    assert data["data"]["status"] == "queued"
    # Verify insert_one was called (new command created)
    mock_mongodb.commands.insert_one.assert_awaited_once()
    # Verify retryCount was incremented on original (2 update_one calls:
    # 1) increment retryCount on original, 2) patch retriedFrom on new command)
    assert mock_mongodb.commands.update_one.await_count == 2


@pytest.mark.asyncio
async def test_retry_non_failed_command_rejected(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_command,
    sample_user,
):
    """Test that a completed/queued command cannot be retried."""
    # sample_command has status "queued" which is not retriable
    mock_mongodb.commands.find_one = AsyncMock(return_value=sample_command)
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    response = await client.post(
        f"/api/v1/commands/{sample_command['commandId']}/retry",
        headers=trusted_write_headers(),
    )

    assert response.status_code == 409
    data = response.json()
    assert data["error"]["code"] == "COMMAND_NOT_RETRIABLE"


@pytest.mark.asyncio
async def test_retry_completed_command_rejected(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_command,
    sample_user,
):
    """Test that a completed command cannot be retried."""
    completed_command = {**sample_command, "status": "completed"}
    mock_mongodb.commands.find_one = AsyncMock(return_value=completed_command)
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    response = await client.post(
        f"/api/v1/commands/{completed_command['commandId']}/retry",
        headers=trusted_write_headers(),
    )

    assert response.status_code == 409
    data = response.json()
    assert data["error"]["code"] == "COMMAND_NOT_RETRIABLE"


@pytest.mark.asyncio
async def test_retry_exceeds_max_retries(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    failed_command,
    retryable_definition,
    sample_user,
):
    """Test that retrying beyond maxRetries is rejected."""
    # Already at max retries
    maxed_command = {**failed_command, "retryCount": 3}
    mock_mongodb.commands.find_one = AsyncMock(return_value=maxed_command)
    mock_mongodb.command_definitions.find_one = AsyncMock(return_value=retryable_definition)
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    response = await client.post(
        "/api/v1/commands/cmd-failed-001/retry",
        headers=trusted_write_headers(),
    )

    assert response.status_code == 409
    data = response.json()
    assert data["error"]["code"] == "COMMAND_MAX_RETRIES_EXCEEDED"
    assert data["error"]["details"]["maxRetries"] == 3
    assert data["error"]["details"]["retryCount"] == 3


@pytest.mark.asyncio
async def test_retry_links_to_original(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    failed_command,
    retryable_definition,
    sample_user,
    sample_managed_service,
):
    """Test that the retry command is linked to the original via retriedFrom."""
    mock_mongodb.commands.find_one = AsyncMock(return_value=failed_command)
    mock_mongodb.command_definitions.find_one = AsyncMock(return_value=retryable_definition)
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.commands.update_one = AsyncMock()
    mock_mongodb.commands.insert_one = AsyncMock(return_value=_mock_insert_one_result())
    mock_mongodb.commands.count_documents = AsyncMock(return_value=0)
    mock_mongodb.nodes.find_one = AsyncMock(
        return_value={"nodeId": "server-01", "status": "active", "agentTier": "normal"}
    )
    mock_mongodb.services.find_one = AsyncMock(return_value=sample_managed_service)

    response = await client.post(
        "/api/v1/commands/cmd-failed-001/retry",
        headers=trusted_write_headers(),
    )

    assert response.status_code == 202
    data = response.json()
    assert data["data"]["originalCommandId"] == "cmd-failed-001"

    # Verify insert_one was called (new command created)
    mock_mongodb.commands.insert_one.assert_awaited_once()

    # Verify the retry command was patched with retriedFrom
    update_calls = mock_mongodb.commands.update_one.await_args_list
    # There should be exactly 2 update_one calls:
    # 1) increment retryCount on original
    # 2) patch retriedFrom on new command
    assert len(update_calls) == 2
    # The second update should set retriedFrom
    patch_call = update_calls[1]
    patch_set = patch_call.args[1]["$set"]
    assert patch_set["retriedFrom"] == "cmd-failed-001"
    assert patch_set["retryCount"] == 1
    assert patch_set["maxRetries"] == 3


@pytest.mark.asyncio
async def test_retry_requires_permission(
    client: AsyncClient,
    mock_mongodb,
    viewer_token,
    failed_command,
    sample_user,
):
    """Test that viewers without commands:execute cannot retry commands."""
    viewer_user = sample_user.copy()
    viewer_user["userId"] = "user_viewer123"
    viewer_user["role"] = "viewer"
    mock_mongodb.users.find_one = AsyncMock(return_value=viewer_user)
    mock_mongodb.commands.find_one = AsyncMock(return_value=failed_command)

    response = await client.post(
        f"/api/v1/commands/{failed_command['commandId']}/retry",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    # Viewer lacks commands:execute permission, should get 403
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_retry_timeout_command_succeeds(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    failed_command,
    retryable_definition,
    sample_user,
    sample_managed_service,
):
    """Test retrying a timed-out command succeeds."""
    timeout_command = {**failed_command, "status": "timeout"}
    mock_mongodb.commands.find_one = AsyncMock(return_value=timeout_command)
    mock_mongodb.command_definitions.find_one = AsyncMock(return_value=retryable_definition)
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.commands.update_one = AsyncMock()
    mock_mongodb.commands.insert_one = AsyncMock(return_value=_mock_insert_one_result())
    mock_mongodb.commands.count_documents = AsyncMock(return_value=0)
    mock_mongodb.nodes.find_one = AsyncMock(
        return_value={"nodeId": "server-01", "status": "active", "agentTier": "normal"}
    )
    mock_mongodb.services.find_one = AsyncMock(return_value=sample_managed_service)

    response = await client.post(
        "/api/v1/commands/cmd-failed-001/retry",
        headers=trusted_write_headers(),
    )

    assert response.status_code == 202
    data = response.json()
    assert data["data"]["originalCommandId"] == "cmd-failed-001"
    assert data["data"]["retryCount"] == 1
    assert data["data"]["maxRetries"] == 3
    assert data["data"]["status"] == "queued"
    # Verify insert_one was called (new command created)
    mock_mongodb.commands.insert_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_retry_non_retryable_definition_rejected(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    failed_command,
    sample_definition,
    sample_user,
):
    """Test that a command whose definition has retryable=false is rejected."""
    # sample_definition has retryable=True but maxRetries=1; override to False
    non_retryable_def = dict(sample_definition)
    non_retryable_def["execution"] = {
        **non_retryable_def["execution"],
        "retryable": False,
        "maxRetries": 0,
    }
    mock_mongodb.commands.find_one = AsyncMock(return_value=failed_command)
    mock_mongodb.command_definitions.find_one = AsyncMock(return_value=non_retryable_def)
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    response = await client.post(
        f"/api/v1/commands/{failed_command['commandId']}/retry",
        headers=trusted_write_headers(),
    )

    assert response.status_code == 409
    data = response.json()
    assert data["error"]["code"] == "COMMAND_NOT_RETRIABLE"


@pytest.mark.asyncio
async def test_get_command_includes_retry_fields(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    failed_command,
    sample_user,
):
    """Test that GET /commands/{id} includes retry-related fields."""
    retried_cmd = {
        **failed_command,
        "status": "queued",
        "retriedFrom": "cmd-original-001",
        "retryCount": 2,
        "maxRetries": 3,
    }
    mock_mongodb.commands.find_one = AsyncMock(return_value=retried_cmd)
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    response = await client.get(
        f"/api/v1/commands/{retried_cmd['commandId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["retriedFrom"] == "cmd-original-001"
    assert data["data"]["retryCount"] == 2
    assert data["data"]["maxRetries"] == 3
