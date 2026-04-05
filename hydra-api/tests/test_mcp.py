"""Tests for MCP (Model Context Protocol) endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from hydra.api.v1.services.mcp import MCPService
from tests.utils import create_mock_cursor


@pytest.fixture
def sample_mcp_server():
    """Sample MCP server configuration."""
    now = datetime.now(UTC)
    return {
        "serverId": "mcp-server-test123",
        "name": "Test MCP Server",
        "endpoint": "http://localhost:8081/mcp",
        "description": "Test MCP server for testing",
        "category": "infrastructure",
        "authType": "none",
        "authConfigured": False,
        "enabled": True,
        "status": "unknown",
        "lastHealthCheck": None,
        "docsUrl": None,
        "ownerId": "user_admin123",
        "createdAt": now,
        "updatedAt": now,
    }


@pytest.mark.asyncio
async def test_list_mcp_servers(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_mcp_server,
):
    """Test listing MCP servers."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)
    mock_mongodb.mcp_servers = MagicMock()
    mock_mongodb.mcp_servers.find_one = AsyncMock(return_value=sample_mcp_server)
    mock_mongodb.mcp_servers.find.return_value = create_mock_cursor([sample_mcp_server])
    mock_mongodb.mcp_servers.count_documents = AsyncMock(return_value=1)

    response = await client.get(
        "/api/v1/mcp/servers",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_get_mcp_server(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_mcp_server,
):
    """Test getting a specific MCP server."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)
    mock_mongodb.mcp_servers = MagicMock()
    mock_mongodb.mcp_servers.find_one = AsyncMock(return_value=sample_mcp_server)
    mock_mongodb.mcp_servers.find.return_value = create_mock_cursor([sample_mcp_server])
    mock_mongodb.mcp_servers.count_documents = AsyncMock(return_value=1)

    response = await client.get(
        "/api/v1/mcp/servers/mcp-server-test123",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["serverId"] == sample_mcp_server["serverId"]


@pytest.mark.asyncio
async def test_create_mcp_server(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_mcp_server,
):
    """Test creating an MCP server."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)
    mock_mongodb.mcp_servers = MagicMock()
    mock_mongodb.mcp_servers.find_one = AsyncMock(side_effect=[None, sample_mcp_server])
    mock_mongodb.mcp_servers.insert_one = AsyncMock()
    mock_mongodb.mcp_servers.find.return_value = create_mock_cursor([sample_mcp_server])
    mock_mongodb.mcp_servers.count_documents = AsyncMock(return_value=1)

    response = await client.post(
        "/api/v1/mcp/servers",
        json={
            "name": "Test MCP Server",
            "transport": "http",
            "endpoint": "http://localhost:8081/mcp",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test MCP Server"


@pytest.mark.asyncio
async def test_mcp_forbidden_for_agent(
    client: AsyncClient,
    mock_mongodb,
    agent_token,
    sample_node,
):
    """Test that agent cannot access MCP endpoints."""
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)

    response = await client.get(
        "/api/v1/mcp/servers",
        headers={"Authorization": f"Bearer {agent_token}"},
    )

    # Agent should get 403
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_mcp_server(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_mcp_server,
    sample_user,
):
    """Test updating an MCP server configuration."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    updated_server = sample_mcp_server.copy()
    updated_server["name"] = "Updated Name"

    mock_mongodb.mcp_servers.find_one = AsyncMock(side_effect=[sample_mcp_server, updated_server])
    mock_mongodb.mcp_servers.update_one = AsyncMock()

    response = await client.put(
        f"/api/v1/mcp/servers/{sample_mcp_server['serverId']}",
        json={"name": "Updated Name"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_delete_mcp_server(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_mcp_server,
    sample_user,
):
    """Test deleting an MCP server configuration."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_mongodb.mcp_servers.find_one = AsyncMock(return_value=sample_mcp_server)
    mock_mongodb.mcp_servers.delete_one = AsyncMock()

    response = await client.delete(
        f"/api/v1/mcp/servers/{sample_mcp_server['serverId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] is True


@pytest.mark.asyncio
async def test_mcp_server_health_check(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_mcp_server,
    sample_user,
    monkeypatch,
):
    """Test checking MCP server health."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_mongodb.mcp_servers.find_one = AsyncMock(return_value=sample_mcp_server)
    mock_mongodb.mcp_servers.update_one = AsyncMock()

    monkeypatch.setattr(
        MCPService,
        "check_health",
        AsyncMock(return_value={
            "server_id": sample_mcp_server["serverId"],
            "status": "healthy",
            "message": "Server is reachable",
            "checked_at": sample_mcp_server["createdAt"],
            "tools": [],
            "resources": [],
        }),
    )

    response = await client.get(
        f"/api/v1/mcp/servers/{sample_mcp_server['serverId']}/health",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_list_mcp_server_tools(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_mcp_server,
    sample_user,
    monkeypatch,
):
    """Test listing tools from an MCP server."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_mongodb.mcp_servers.find_one = AsyncMock(return_value=sample_mcp_server)

    monkeypatch.setattr(
        MCPService,
        "list_tools",
        AsyncMock(return_value={
            "server_id": sample_mcp_server["serverId"],
            "tools": [{"name": "search", "description": "Search docs"}],
        }),
    )

    response = await client.get(
        f"/api/v1/mcp/servers/{sample_mcp_server['serverId']}/tools",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tools"][0]["name"] == "search"


@pytest.mark.asyncio
async def test_list_mcp_servers_by_category(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_mcp_server,
    sample_user,
):
    """Test listing MCP servers filtered by category."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)
    mock_mongodb.mcp_servers.find.return_value = create_mock_cursor([sample_mcp_server])
    mock_mongodb.mcp_servers.count_documents = AsyncMock(return_value=1)

    response = await client.get(
        "/api/v1/mcp/servers?category=infrastructure",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_mcp_servers_enabled_only(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_mcp_server,
    sample_user,
):
    """Test listing only enabled MCP servers."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)
    mock_mongodb.mcp_servers.find.return_value = create_mock_cursor([sample_mcp_server])
    mock_mongodb.mcp_servers.count_documents = AsyncMock(return_value=1)

    response = await client.get(
        "/api/v1/mcp/servers?enabled=true",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_mcp_agent_cannot_create(
    client: AsyncClient,
    mock_mongodb,
    agent_token,
    sample_node,
):
    """Test that agent cannot create MCP servers."""
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)

    response = await client.post(
        "/api/v1/mcp/servers",
        json={
            "name": "Test",
            "endpoint": "http://localhost/mcp",
        },
        headers={"Authorization": f"Bearer {agent_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_mcp_agent_cannot_update(
    client: AsyncClient,
    mock_mongodb,
    agent_token,
    sample_node,
):
    """Test that agent cannot update MCP servers."""
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)

    response = await client.put(
        "/api/v1/mcp/servers/some-server",
        json={"name": "Updated"},
        headers={"Authorization": f"Bearer {agent_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_mcp_agent_cannot_delete(
    client: AsyncClient,
    mock_mongodb,
    agent_token,
    sample_node,
):
    """Test that agent cannot delete MCP servers."""
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)

    response = await client.delete(
        "/api/v1/mcp/servers/some-server",
        headers={"Authorization": f"Bearer {agent_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_mcp_server_not_found(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test getting a non-existent MCP server."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)
    mock_mongodb.mcp_servers.find_one = AsyncMock(return_value=None)

    response = await client.get(
        "/api/v1/mcp/servers/nonexistent-server",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404
