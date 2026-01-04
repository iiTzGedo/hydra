"""Tests for authentication endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_node_success(
    client: AsyncClient,
    mock_mongodb,
    sample_registration_token,
):
    """Test successful node registration."""
    # Mock token lookup
    mock_mongodb.tokens.find_one = AsyncMock(return_value=sample_registration_token)
    mock_mongodb.nodes.find_one = AsyncMock(return_value=None)  # Node doesn't exist
    mock_mongodb.nodes.insert_one = AsyncMock()
    mock_mongodb.tokens.update_one = AsyncMock()

    response = await client.post(
        "/node/register",
        json={
            "nodeId": "new-test-node",
            "class": "compute",
            "type": "physical",
            "displayName": "New Test Node",
            "tags": ["test"],
        },
        headers={"X-Registration-Token": sample_registration_token["token"]},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["nodeId"] == "new-test-node"
    assert "apiKey" in data
    assert "apiKeyId" in data
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_register_node_duplicate(
    client: AsyncClient,
    mock_mongodb,
    sample_registration_token,
    sample_node,
):
    """Test registration fails for duplicate node."""
    mock_mongodb.tokens.find_one = AsyncMock(return_value=sample_registration_token)
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)

    response = await client.post(
        "/node/register",
        json={
            "nodeId": sample_node["nodeId"],
            "class": "compute",
            "type": "physical",
            "displayName": "Test",
        },
        headers={"X-Registration-Token": sample_registration_token["token"]},
    )

    assert response.status_code == 409
    data = response.json()
    assert data["error"]["code"] == "NODE_ALREADY_REGISTERED"


@pytest.mark.asyncio
async def test_register_node_invalid_token(
    client: AsyncClient,
    mock_mongodb,
):
    """Test registration fails with invalid token."""
    mock_mongodb.tokens.find_one = AsyncMock(return_value=None)

    response = await client.post(
        "/node/register",
        json={
            "nodeId": "test-node",
            "class": "compute",
            "type": "physical",
            "displayName": "Test",
        },
        headers={"X-Registration-Token": "invalid_token"},
    )

    assert response.status_code == 401
    data = response.json()
    assert "invalid" in data["detail"].lower()


@pytest.mark.asyncio
async def test_register_node_expired_token(
    client: AsyncClient,
    mock_mongodb,
    sample_registration_token,
):
    """Test registration fails with expired token."""
    expired_token = sample_registration_token.copy()
    expired_token["expiresAt"] = datetime(2020, 1, 1, tzinfo=timezone.utc)
    mock_mongodb.tokens.find_one = AsyncMock(return_value=expired_token)

    response = await client.post(
        "/node/register",
        json={
            "nodeId": "test-node",
            "class": "compute",
            "type": "physical",
            "displayName": "Test",
        },
        headers={"X-Registration-Token": sample_registration_token["token"]},
    )

    assert response.status_code == 401
    data = response.json()
    assert "expired" in data["detail"].lower()


@pytest.mark.asyncio
async def test_get_current_user(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test getting current user info."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "user"
    assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_get_current_agent(
    client: AsyncClient,
    mock_mongodb,
    agent_token,
    sample_node,
):
    """Test getting current agent info."""
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)

    response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {agent_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "agent"
    assert data["nodeId"] == "test-node-01"


@pytest.mark.asyncio
async def test_access_without_token(client: AsyncClient):
    """Test accessing protected endpoint without token."""
    response = await client.get("/auth/me")

    assert response.status_code == 401
