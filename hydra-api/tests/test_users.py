"""Tests for user management endpoints."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from hydra.api.v1.core.security import create_access_token
from hydra.core.config import get_settings
from tests.utils import create_mock_cursor


@pytest.mark.asyncio
async def test_list_users_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test listing users as admin."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)
    mock_mongodb.users.count_documents = AsyncMock(return_value=2)
    mock_mongodb.users.find.return_value = create_mock_cursor([admin_user, sample_user])

    response = await client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_list_users_forbidden_for_agent(
    client: AsyncClient,
    mock_mongodb,
    agent_token,
    sample_node,
):
    """Test that agents cannot list users."""
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)

    response = await client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {agent_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_users_forbidden_for_operator(
    client: AsyncClient,
    mock_mongodb,
    sample_user,
):
    """Test that operators cannot list users without users:read."""
    operator_user = sample_user.copy()
    operator_user["userId"] = "user_operator123"
    operator_user["role"] = "operator"
    operator_user["permissions"] = ["nodes:*", "services:*"]
    mock_mongodb.users.find_one = AsyncMock(return_value=operator_user)

    operator_token = create_access_token(
        subject="user_operator123",
        token_type="access",
        additional_claims={
            "sub_type": "user",
            "role": "operator",
            "permissions": ["nodes:*", "services:*"],
        },
        settings=get_settings(),
    )

    response = await client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_users_pagination(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test users pagination."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)
    mock_mongodb.users.count_documents = AsyncMock(return_value=100)
    mock_mongodb.users.find.return_value = create_mock_cursor([admin_user])

    response = await client.get(
        "/api/v1/users?limit=10&offset=20",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 10
    assert data["offset"] == 20


@pytest.mark.asyncio
async def test_archive_user_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test archiving a user as admin."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"

    archived_user = sample_user.copy()
    archived_user["status"] = "archived"

    mock_mongodb.users.find_one = AsyncMock(side_effect=[admin_user, admin_user, sample_user, archived_user])
    mock_mongodb.users.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_mongodb.users.update_many = AsyncMock(return_value=MagicMock(modified_count=1))

    response = await client.delete(
        f"/api/v1/users/{sample_user['userId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "archived"


@pytest.mark.asyncio
async def test_archive_user_forbidden_for_non_admin(
    client: AsyncClient,
    mock_mongodb,
    viewer_token,
    sample_user,
):
    """Test that non-admin cannot archive users."""
    viewer_user = sample_user.copy()
    viewer_user["userId"] = "user_viewer123"
    viewer_user["role"] = "viewer"
    mock_mongodb.users.find_one = AsyncMock(return_value=viewer_user)

    response = await client.delete(
        f"/api/v1/users/{sample_user['userId']}",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_elevate_user_role(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test elevating a user's role."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"

    elevated_user = sample_user.copy()
    elevated_user["role"] = "operator"

    mock_mongodb.users.find_one = AsyncMock(side_effect=[admin_user, admin_user, sample_user, elevated_user])
    mock_mongodb.users.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_mongodb.audit_log.insert_one = AsyncMock()

    response = await client.post(
        f"/api/v1/users/{sample_user['userId']}/roles/elevate",
        json={"newRole": "operator", "reason": "Promotion"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["newRole"] == "operator"


@pytest.mark.asyncio
async def test_grant_temporary_role(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test granting a temporary role."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"

    user_with_temp_role = sample_user.copy()
    user_with_temp_role["temporaryRoles"] = [
        {
            "role": "operator",
            "expiresAt": datetime.now(UTC) + timedelta(hours=24),
            "grantedBy": "user_admin123",
            "grantedAt": datetime.now(UTC),
            "reason": "Emergency access",
        }
    ]

    mock_mongodb.users.find_one = AsyncMock(side_effect=[admin_user, sample_user, user_with_temp_role])
    mock_mongodb.users.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_mongodb.audit_log.insert_one = AsyncMock()

    response = await client.post(
        f"/api/v1/users/{sample_user['userId']}/roles/grant-temporary",
        json={
            "role": "operator",
            "expiresAt": (datetime.now(UTC) + timedelta(hours=24)).isoformat(),
            "reason": "Emergency access",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["baseRole"] == "viewer"


@pytest.mark.asyncio
async def test_revoke_temporary_role(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test revoking a temporary role."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"

    user_with_temp_role = sample_user.copy()
    user_with_temp_role["temporaryRoles"] = [
        {
            "role": "operator",
            "expiresAt": datetime.now(UTC) + timedelta(hours=24),
            "grantedBy": "user_admin123",
            "grantedAt": datetime.now(UTC),
        }
    ]

    user_after_revoke = sample_user.copy()
    user_after_revoke["temporaryRoles"] = []

    mock_mongodb.users.find_one = AsyncMock(
        side_effect=[admin_user, admin_user, user_with_temp_role, user_after_revoke]
    )
    mock_mongodb.users.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_mongodb.audit_log.insert_one = AsyncMock()

    response = await client.delete(
        f"/api/v1/users/{sample_user['userId']}/roles/temporary/operator",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_role_management_forbidden_for_non_admin(
    client: AsyncClient,
    mock_mongodb,
    viewer_token,
    sample_user,
):
    """Test that non-admin cannot manage roles."""
    viewer_user = sample_user.copy()
    viewer_user["userId"] = "user_viewer123"
    viewer_user["role"] = "viewer"
    mock_mongodb.users.find_one = AsyncMock(return_value=viewer_user)

    response = await client.post(
        f"/api/v1/users/{sample_user['userId']}/roles/elevate",
        json={"newRole": "operator", "reason": "Promotion"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_viewer_cannot_list_users(
    client: AsyncClient,
    mock_mongodb,
    viewer_token,
    sample_user,
):
    """Test that viewers cannot list users without users:read."""
    viewer_user = sample_user.copy()
    viewer_user["userId"] = "user_viewer123"
    viewer_user["role"] = "viewer"
    mock_mongodb.users.find_one = AsyncMock(return_value=viewer_user)
    mock_mongodb.users.count_documents = AsyncMock(return_value=1)
    mock_mongodb.users.find.return_value = create_mock_cursor([viewer_user])

    response = await client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403
