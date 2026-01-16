"""Tests for command execution endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

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
    mock_mongodb.nodes.find_one = AsyncMock(return_value={"nodeId": "server-01", "status": "active"})
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
async def test_poll_commands(
    client: AsyncClient,
    mock_mongodb,
    agent_token,
    sample_command,
    sample_node,
):
    """Test polling commands for a node (agent endpoint)."""
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)
    mock_mongodb.commands.find_one_and_update = AsyncMock(
        side_effect=[sample_command, None]
    )

    response = await client.get(
        f"/api/v1/nodes/{sample_node['nodeId']}/commands/poll",
        headers={"Authorization": f"Bearer {agent_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]["commands"]) == 1


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
