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
        "/api/v1/nodes/register",
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
        "/api/v1/nodes/register",
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
        "/api/v1/nodes/register",
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
        "/api/v1/nodes/register",
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
        "/api/v1/auth/me",
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
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {agent_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "agent"
    assert data["nodeId"] == "test-node-01"


@pytest.mark.asyncio
async def test_access_without_token(client: AsyncClient):
    """Test accessing protected endpoint without token."""
    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401


# ==================== Sub-Account Tests ====================


@pytest.mark.asyncio
async def test_register_agent_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
):
    """Test successful agent account registration."""
    admin_user = {
        "userId": "user_admin123",
        "username": "admin",
        "email": "admin@example.com",
        "role": "admin",
        "status": "active",
        "passwordHash": "$2b$12$test",
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }
    mock_mongodb.users.find_one = AsyncMock(
        side_effect=[admin_user, admin_user, None]
    )
    mock_mongodb.users.insert_one = AsyncMock()
    mock_mongodb.users.update_one = AsyncMock()
    mock_mongodb.api_keys.insert_one = AsyncMock()

    response = await client.post(
        "/api/v1/auth/register",
        json={"role": "agent"},  # Auto-generate username and password
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["role"] == "agent"
    assert data["isSystemAccount"] is True
    assert data["parentUserId"] == "user_admin123"
    assert "apiKey" in data
    assert data["username"].startswith("agent-")


@pytest.mark.asyncio
async def test_register_agent_custom_username(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
):
    """Test agent registration with custom username."""
    admin_user = {
        "userId": "user_admin123",
        "username": "admin",
        "email": "admin@example.com",
        "role": "admin",
        "status": "active",
        "passwordHash": "$2b$12$test",
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }
    mock_mongodb.users.find_one = AsyncMock(
        side_effect=[admin_user, admin_user, None]
    )
    mock_mongodb.users.insert_one = AsyncMock()
    mock_mongodb.users.update_one = AsyncMock()
    mock_mongodb.api_keys.insert_one = AsyncMock()

    response = await client.post(
        "/api/v1/auth/register",
        json={"role": "agent", "username": "my-custom-agent"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "my-custom-agent"


@pytest.mark.asyncio
async def test_register_agent_viewer_forbidden(
    client: AsyncClient,
    mock_mongodb,
    viewer_token,
):
    """Test that viewer cannot register agent accounts."""
    viewer_user = {
        "userId": "user_viewer123",
        "username": "viewer",
        "email": "viewer@example.com",
        "role": "viewer",
        "status": "active",
        "passwordHash": "$2b$12$test",
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }
    mock_mongodb.users.find_one = AsyncMock(side_effect=[viewer_user, viewer_user])

    response = await client.post(
        "/api/v1/auth/register",
        json={"role": "agent"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_sub_accounts(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
):
    """Test listing sub-accounts."""
    admin_user = {
        "userId": "user_admin123",
        "username": "admin",
        "email": "admin@example.com",
        "role": "admin",
        "status": "active",
        "subAccounts": [
            {
                "userId": "user_agent1",
                "username": "agent-ABC123",
                "role": "agent",
                "createdAt": datetime.now(timezone.utc),
            }
        ],
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }
    agent_user = {
        "userId": "user_agent1",
        "username": "agent-ABC123",
        "role": "agent",
        "status": "active",
        "isSystemAccount": True,
        "lastLogin": None,
        "createdAt": datetime.now(timezone.utc),
    }
    mock_mongodb.users.find_one = AsyncMock(
        side_effect=[admin_user, admin_user, agent_user]
    )

    response = await client.get(
        "/api/v1/users/user_admin123/subs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["subAccounts"]) == 1
    assert data["subAccounts"][0]["username"] == "agent-ABC123"


@pytest.mark.asyncio
async def test_link_sub_account_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
):
    """Test linking an existing user as sub-account."""
    from hydra.api.v1.core.security import hash_password

    admin_user = {
        "userId": "user_admin123",
        "username": "admin",
        "email": "admin@example.com",
        "role": "admin",
        "status": "active",
        "passwordHash": hash_password("adminpass"),
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }
    family_user = {
        "userId": "user_family123",
        "username": "family",
        "email": "family@example.com",
        "role": "family",
        "status": "active",
        "passwordHash": hash_password("familypass"),
        "parentUserId": None,  # No parent yet
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }
    mock_mongodb.users.find_one = AsyncMock(
        side_effect=[admin_user, admin_user, family_user]
    )
    mock_mongodb.users.update_one = AsyncMock()

    response = await client.post(
        "/api/v1/auth/register/sub/user_family123",
        json={"password": "familypass"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["parentUserId"] == "user_admin123"
    assert data["subAccountUserId"] == "user_family123"


@pytest.mark.asyncio
async def test_link_sub_account_invalid_role(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
):
    """Test that admin/operator cannot be linked as sub-account."""
    from hydra.api.v1.core.security import hash_password

    admin_user = {
        "userId": "user_admin123",
        "username": "admin",
        "email": "admin@example.com",
        "role": "admin",
        "status": "active",
        "passwordHash": hash_password("adminpass"),
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }
    operator_user = {
        "userId": "user_operator123",
        "username": "operator",
        "email": "operator@example.com",
        "role": "operator",  # Cannot be sub-account
        "status": "active",
        "passwordHash": hash_password("operatorpass"),
        "parentUserId": None,
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }
    mock_mongodb.users.find_one = AsyncMock(
        side_effect=[admin_user, admin_user, operator_user]
    )

    response = await client.post(
        "/api/v1/auth/register/sub/user_operator123",
        json={"password": "operatorpass"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "INVALID_SUB_ACCOUNT_ROLE"


@pytest.mark.asyncio
async def test_unlink_sub_account_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
):
    """Test unlinking a sub-account."""
    admin_user = {
        "userId": "user_admin123",
        "username": "admin",
        "email": "admin@example.com",
        "role": "admin",
        "status": "active",
        "subAccounts": [{"userId": "user_family123"}],
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }
    family_user = {
        "userId": "user_family123",
        "username": "family",
        "email": "family@example.com",
        "role": "family",
        "status": "active",
        "parentUserId": "user_admin123",  # Linked to admin
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }
    mock_mongodb.users.find_one = AsyncMock(
        side_effect=[admin_user, admin_user, family_user]
    )
    mock_mongodb.users.update_one = AsyncMock()

    response = await client.delete(
        "/api/v1/auth/sub/user_family123",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Sub-account unlinked successfully"
