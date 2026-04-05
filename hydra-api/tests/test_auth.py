"""Tests for authentication endpoints."""

import asyncio
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from hydra.api.v1.core.auth_session import (
    ACCESS_COOKIE_NAME,
    INTERNAL_CLIENT_ID_HEADER,
    INTERNAL_PERMISSIONS_HEADER,
    INTERNAL_REQUEST_HEADER,
    INTERNAL_ROLE_HEADER,
    INTERNAL_SECRET_HEADER,
    INTERNAL_USER_ID_HEADER,
    session_key,
)
from hydra.api.v1.core.security import create_access_token
from hydra.core.config import get_settings


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
    assert data["apiKey"].startswith("hyk_")
    assert "." in data["apiKey"]
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_register_node_max_tier_persists_server_metadata_and_returns_secret(
    client: AsyncClient,
    mock_mongodb,
    sample_registration_token,
):
    """Test max-tier registration stores server metadata and returns a control secret."""
    mock_mongodb.tokens.find_one = AsyncMock(return_value=sample_registration_token)
    mock_mongodb.nodes.find_one = AsyncMock(return_value=None)
    mock_mongodb.nodes.insert_one = AsyncMock()
    mock_mongodb.tokens.update_one = AsyncMock()

    response = await client.post(
        "/api/v1/nodes/register",
        json={
            "nodeId": "max-test-node",
            "class": "compute",
            "type": "physical",
            "displayName": "Max Test Node",
            "agentTier": "max",
            "serverAddress": "agent.internal.example",
            "serverPort": 9443,
            "serverTlsEnabled": True,
        },
        headers={"X-Registration-Token": sample_registration_token["token"]},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["nodeId"] == "max-test-node"
    assert data["agentServerSecret"].startswith("hsk_api_")

    inserted_node = mock_mongodb.nodes.insert_one.await_args.args[0]
    assert inserted_node["agentTier"] == "max"
    assert inserted_node["serverAddress"] == "agent.internal.example"
    assert inserted_node["serverPort"] == 9443
    assert inserted_node["serverTlsEnabled"] is True
    assert inserted_node["serverReachable"] is True
    assert inserted_node["failedDirectAttempts"] == 0


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
    expired_token["expiresAt"] = datetime(2020, 1, 1, tzinfo=UTC)
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
async def test_register_node_with_bearer_token(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test node registration succeeds with a bearer token and node-create permission."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    admin_user["permissions"] = ["*:*"]
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)
    mock_mongodb.nodes.find_one = AsyncMock(return_value=None)
    mock_mongodb.nodes.insert_one = AsyncMock()
    mock_mongodb.api_keys.insert_one = AsyncMock()
    mock_mongodb.users.update_one = AsyncMock()

    response = await client.post(
        "/api/v1/nodes/register",
        json={
            "nodeId": "bearer-node",
            "class": "compute",
            "type": "physical",
            "displayName": "Bearer Node",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["nodeId"] == "bearer-node"
    assert data["registeredBy"] == "user_admin123"
    assert data["apiKey"].startswith("hyk_")


@pytest.mark.asyncio
async def test_register_node_notification_uses_injected_dependencies(
    client: AsyncClient,
    mock_mongodb,
    sample_registration_token,
    monkeypatch,
):
    """Test node-registration notifications do not resolve global database singletons."""
    scheduled_tasks: list[asyncio.Task[object]] = []
    emit_mock = AsyncMock(return_value="notif_123")

    def _run_immediately(coro):
        task = asyncio.create_task(coro)
        scheduled_tasks.append(task)
        return task

    def _unexpected_mongodb():
        raise AssertionError("emit_notification should use injected MongoDB dependency")

    def _unexpected_redis():
        raise AssertionError("emit_notification should use injected Redis dependency")

    mock_mongodb.tokens.find_one = AsyncMock(return_value=sample_registration_token)
    mock_mongodb.nodes.find_one = AsyncMock(return_value=None)
    mock_mongodb.nodes.insert_one = AsyncMock()
    mock_mongodb.api_keys.insert_one = AsyncMock()
    mock_mongodb.users.update_one = AsyncMock()
    mock_mongodb.tokens.update_one = AsyncMock()

    monkeypatch.setattr(
        "hydra.api.v1.services.auth.nodes.safe_create_task",
        _run_immediately,
    )
    monkeypatch.setattr(
        "hydra.api.v1.services.notifications.service.NotificationService.emit",
        emit_mock,
    )
    monkeypatch.setattr("hydra.db.mongodb.get_mongodb", _unexpected_mongodb)
    monkeypatch.setattr("hydra.db.redis.get_redis", _unexpected_redis)

    response = await client.post(
        "/api/v1/nodes/register",
        json={
            "nodeId": "hermetic-node",
            "class": "compute",
            "type": "physical",
            "displayName": "Hermetic Node",
        },
        headers={"X-Registration-Token": sample_registration_token["token"]},
    )

    assert response.status_code == 201
    assert scheduled_tasks
    await asyncio.gather(*scheduled_tasks)
    assert emit_mock.await_count == 1


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


@pytest.mark.asyncio
async def test_get_current_user_via_session_cookie(
    client: AsyncClient,
    mock_mongodb,
    mock_redis,
    sample_user,
    test_settings,
):
    """Test cookie-backed auth for /auth/me."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    admin_user["permissions"] = ["*:*"]
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    access_token = create_access_token(
        subject="user_admin123",
        token_type="access",
        additional_claims={
            "sub_type": "user",
            "role": "admin",
            "permissions": ["*:*"],
            "sid": "session-cookie-1",
        },
        settings=get_settings(),
    )
    mock_redis.client._store[session_key("session-cookie-1")] = json.dumps(
        {
            "sessionId": "session-cookie-1",
            "subject": "user_admin123",
            "subType": "user",
            "csrfToken": "csrf-cookie-1",
            "currentRefreshJti": "refresh-cookie-1",
            "revoked": False,
        }
    )

    response = await client.get(
        "/api/v1/auth/me",
        cookies={ACCESS_COOKIE_NAME: access_token},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "user"
    assert data["userId"] == "user_admin123"


@pytest.mark.asyncio
async def test_blacklisted_access_token_is_rejected(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test that logout blacklists the current access token."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    admin_user["permissions"] = ["*:*"]
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    logout_response = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert logout_response.status_code == 200
    assert logout_response.json()["loggedOut"] is True

    me_response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert me_response.status_code == 401
    assert "revoked" in me_response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_internal_headers_authorize_as_forwarded_user(
    client: AsyncClient,
    mock_mongodb,
    sample_user,
    test_settings,
):
    """Test internal Hydra headers are only accepted with the shared secret."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    admin_user["permissions"] = ["*:*"]
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    response = await client.get(
        "/api/v1/auth/me",
        headers={
            INTERNAL_REQUEST_HEADER: "true",
            INTERNAL_USER_ID_HEADER: "user_admin123",
            INTERNAL_ROLE_HEADER: "admin",
            INTERNAL_PERMISSIONS_HEADER: json.dumps(["*:*"]),
            INTERNAL_CLIENT_ID_HEADER: "hydra-mcp",
            INTERNAL_SECRET_HEADER: test_settings.mcp_internal_secret,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "user"
    assert data["userId"] == "user_admin123"


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
        "createdAt": datetime.now(UTC),
        "updatedAt": datetime.now(UTC),
    }
    mock_mongodb.users.find_one = AsyncMock(side_effect=[admin_user, admin_user, None])
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
        "createdAt": datetime.now(UTC),
        "updatedAt": datetime.now(UTC),
    }
    mock_mongodb.users.find_one = AsyncMock(side_effect=[admin_user, admin_user, None])
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
        "createdAt": datetime.now(UTC),
        "updatedAt": datetime.now(UTC),
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
                "createdAt": datetime.now(UTC),
            }
        ],
        "createdAt": datetime.now(UTC),
        "updatedAt": datetime.now(UTC),
    }
    agent_user = {
        "userId": "user_agent1",
        "username": "agent-ABC123",
        "role": "agent",
        "status": "active",
        "isSystemAccount": True,
        "lastLogin": None,
        "createdAt": datetime.now(UTC),
    }
    mock_mongodb.users.find_one = AsyncMock(side_effect=[admin_user, admin_user, agent_user])

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
        "createdAt": datetime.now(UTC),
        "updatedAt": datetime.now(UTC),
    }
    family_user = {
        "userId": "user_family123",
        "username": "family",
        "email": "family@example.com",
        "role": "family",
        "status": "active",
        "passwordHash": hash_password("familypass"),
        "parentUserId": None,  # No parent yet
        "createdAt": datetime.now(UTC),
        "updatedAt": datetime.now(UTC),
    }
    mock_mongodb.users.find_one = AsyncMock(side_effect=[admin_user, admin_user, family_user])
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
        "createdAt": datetime.now(UTC),
        "updatedAt": datetime.now(UTC),
    }
    operator_user = {
        "userId": "user_operator123",
        "username": "operator",
        "email": "operator@example.com",
        "role": "operator",  # Cannot be sub-account
        "status": "active",
        "passwordHash": hash_password("operatorpass"),
        "parentUserId": None,
        "createdAt": datetime.now(UTC),
        "updatedAt": datetime.now(UTC),
    }
    mock_mongodb.users.find_one = AsyncMock(side_effect=[admin_user, admin_user, operator_user])

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
        "createdAt": datetime.now(UTC),
        "updatedAt": datetime.now(UTC),
    }
    family_user = {
        "userId": "user_family123",
        "username": "family",
        "email": "family@example.com",
        "role": "family",
        "status": "active",
        "parentUserId": "user_admin123",  # Linked to admin
        "createdAt": datetime.now(UTC),
        "updatedAt": datetime.now(UTC),
    }
    mock_mongodb.users.find_one = AsyncMock(side_effect=[admin_user, admin_user, family_user])
    mock_mongodb.users.update_one = AsyncMock()

    response = await client.delete(
        "/api/v1/auth/sub/user_family123",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Sub-account unlinked successfully"
