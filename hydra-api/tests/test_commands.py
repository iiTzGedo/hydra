"""Tests for command execution endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from httpx import AsyncClient

from tests.utils import create_mock_cursor


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
            "addedAt": datetime.now(timezone.utc),
            "builtIn": True,
            "deprecated": False,
        },
    }


@pytest.fixture
def sample_managed_service():
    """Sample service doc used for command target normalization."""
    now = datetime.now(timezone.utc)
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
    now = datetime.now(timezone.utc)
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
    now = datetime.now(timezone.utc)
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
        headers={"Authorization": f"Bearer {admin_token}"},
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
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "COMMAND_DEFINITION_NOT_FOUND"


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
        headers={"Authorization": f"Bearer {operator_token}"},
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

    response = await client.post(
        "/api/v1/commands",
        json={
            "registryId": "reg::service::restart",
            "target": {"nodeId": "server-01", "serviceId": "svc-nginx-a1b2"},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
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
        headers={"Authorization": f"Bearer {admin_token}"},
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
        headers={"Authorization": f"Bearer {admin_token}"},
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
        headers={"Authorization": f"Bearer {admin_token}"},
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
        headers={"Authorization": f"Bearer {admin_token}"},
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
        headers={"Authorization": f"Bearer {admin_token}"},
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
        headers={"Authorization": f"Bearer {admin_token}"},
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
        "/api/v1/commands?nodeId=server-01&type=service&status=queued",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1


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
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["status"] == "cancelled"
    assert "cancelledAt" in data["data"]


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
async def test_commands_viewer_can_not_list(
    client: AsyncClient,
    mock_mongodb,
    viewer_token,
    sample_command,
    sample_user,
):
    """Test that viewer cannot list commands (no commands:read permission)."""
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

    assert response.status_code == 403


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
