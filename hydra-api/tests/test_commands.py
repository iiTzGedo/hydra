"""Tests for command execution endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from httpx import AsyncClient

from tests.utils import create_mock_cursor


@pytest.fixture
def sample_command():
    """Sample command document."""
    now = datetime.now(timezone.utc)
    return {
        "commandId": "cmd-abc123",
        "type": "system",
        "target": {"nodeId": "server-01", "serviceId": None},
        "action": "run",
        "parameters": {"command": "uptime"},
        "status": "queued",
        "requestedBy": {"userId": "user_admin123", "source": "api"},
        "timeoutSeconds": 300,
        "createdAt": now,
        "queuedAt": now,
        "startedAt": None,
        "completedAt": None,
        "result": None,
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


@pytest.mark.asyncio
async def test_create_command_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_command,
    sample_user,
):
    """Test creating a new command."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.nodes.find_one = AsyncMock(
        return_value={"nodeId": "server-01", "status": "active"}
    )
    mock_mongodb.commands.insert_one = AsyncMock()
    mock_mongodb.commands.find_one = AsyncMock(return_value=sample_command)

    response = await client.post(
        "/api/v1/commands",
        json={
            "type": "system",
            "target": {"nodeId": "server-01"},
            "action": "run",
            "parameters": {"command": "uptime"},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 202
    data = response.json()
    assert data["data"]["target"]["nodeId"] == "server-01"
    assert data["data"]["status"] == "queued"


@pytest.mark.asyncio
async def test_create_command_rejects_lite_tier(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test lite-tier nodes reject command execution."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
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
            "type": "system",
            "target": {"nodeId": "server-01"},
            "action": "run",
            "parameters": {"command": "uptime"},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "COMMAND_NOT_SUPPORTED"
    mock_mongodb.commands.insert_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_command_normal_tier_queues_for_poll(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test normal-tier nodes queue commands for polling."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.nodes.find_one = AsyncMock(
        return_value={
            "nodeId": "server-01",
            "status": "active",
            "agentTier": "normal",
        }
    )

    response = await client.post(
        "/api/v1/commands",
        json={
            "type": "system",
            "target": {"nodeId": "server-01"},
            "action": "run",
            "parameters": {"command": "uptime"},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 202
    data = response.json()
    assert data["data"]["executionMethod"] == "poll"
    assert data["data"]["status"] == "queued"
    mock_mongodb.commands.insert_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_command_max_tier_transport_failure_falls_back_and_updates_reachability(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    monkeypatch,
):
    """Test transport errors fall back to polling and count against reachability."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
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
    mock_mongodb.nodes.find_one_and_update = AsyncMock(
        return_value={"nodeId": "server-01", "failedDirectAttempts": 3}
    )
    mock_mongodb.nodes.update_one = AsyncMock()

    capture: dict = {}
    request = httpx.Request("POST", "https://agent.internal.example:9443/execute")
    monkeypatch.setattr(
        "hydra.api.v1.services.commands.httpx.AsyncClient",
        make_dummy_async_client(
            error=httpx.ConnectError("connect failed", request=request),
            capture=capture,
        ),
    )

    response = await client.post(
        "/api/v1/commands",
        json={
            "type": "service",
            "target": {
                "nodeId": "server-01",
                "serviceId": "svc-nginx-a1b2",
            },
            "action": "restart",
            "parameters": {"graceful": True},
            "timeoutSeconds": 120,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 202
    data = response.json()
    assert data["data"]["executionMethod"] == "poll"
    assert capture["url"] == "https://agent.internal.example:9443/execute"
    assert capture["json"]["registryId"] == "restart"
    assert capture["json"]["target"] == {
        "nodeId": "server-01",
        "serviceId": "svc-nginx-a1b2",
    }
    assert capture["json"]["timeoutSeconds"] == 120
    mock_mongodb.nodes.find_one_and_update.assert_awaited_once()
    mock_mongodb.nodes.update_one.assert_awaited_once_with(
        {"nodeId": "server-01"},
        {"$set": {"serverReachable": False}},
    )


@pytest.mark.asyncio
async def test_create_command_max_tier_http_501_falls_back_without_changing_reachability(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    monkeypatch,
):
    """Test agent HTTP errors fall back to polling without poisoning reachability state."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
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
    mock_mongodb.nodes.find_one_and_update = AsyncMock()
    mock_mongodb.nodes.update_one = AsyncMock()

    capture: dict = {}
    monkeypatch.setattr(
        "hydra.api.v1.services.commands.httpx.AsyncClient",
        make_dummy_async_client(
            response=DummyResponse(
                501,
                {"error": {"code": "NOT_IMPLEMENTED", "message": "Requires P2B"}},
            ),
            capture=capture,
        ),
    )

    response = await client.post(
        "/api/v1/commands",
        json={
            "type": "service",
            "target": {
                "nodeId": "server-01",
                "serviceId": "svc-nginx-a1b2",
            },
            "action": "restart",
            "parameters": {"graceful": True},
            "timeoutSeconds": 120,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 202
    data = response.json()
    assert data["data"]["executionMethod"] == "poll"
    assert capture["url"] == "https://agent.internal.example:9443/execute"
    mock_mongodb.nodes.find_one_and_update.assert_not_awaited()
    mock_mongodb.nodes.update_one.assert_not_awaited()


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
        "/api/v1/commands?nodeId=server-01&type=system&status=queued",
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

    cancelled_command = sample_command.copy()
    cancelled_command["status"] = "cancelled"
    cancelled_command["cancelledAt"] = datetime.now(timezone.utc)

    mock_mongodb.commands.find_one = AsyncMock(side_effect=[sample_command, cancelled_command])
    mock_mongodb.commands.update_one = AsyncMock(return_value=MagicMock(modified_count=1))

    response = await client.post(
        f"/api/v1/commands/{sample_command['commandId']}/cancel",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_poll_commands_returns_typed_target_and_resets_failures(
    client: AsyncClient,
    mock_mongodb,
    agent_token,
    sample_command,
    sample_node,
):
    """Test polling returns the typed target contract and resets direct failure state."""
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
    poll_update = mock_mongodb.nodes.update_one.await_args.args[1]["$set"]
    assert poll_update["serverReachable"] is True
    assert poll_update["failedDirectAttempts"] == 0
    assert "lastSeenAt" in poll_update
    assert "lastPollContact" in poll_update


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
            "output": "uptime output",
            "exitCode": 0,
            "error": None,
        },
        headers={"Authorization": f"Bearer {agent_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["status"] == "completed"


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
            "type": "system",
            "target": {"nodeId": "server-01"},
            "action": "run",
            "parameters": {"command": "uptime"},
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

    # Viewer doesn't have commands:read permission
    assert response.status_code == 403


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
