"""Tests for settings management endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient


@pytest.fixture
def sample_user_settings():
    """Sample user settings document."""
    return {
        "userId": "user_test123",
        "ui": {
            "theme": "dark",
            "sidebarCollapsed": False,
            "animationsEnabled": True,
        },
        "views": {},
        "notifications": {
            "emailEnabled": True,
            "browserEnabled": True,
            "nodeNotifications": True,
            "serviceNotifications": True,
            "profileNotifications": False,
        },
        "updatedAt": datetime.now(timezone.utc),
    }


@pytest.fixture
def sample_system_settings():
    """Sample system settings document."""
    return {
        "_id": "system",
        "smtp": {
            "enabled": True,
            "host": "smtp.example.com",
            "port": 587,
            "fromAddress": "noreply@example.com",
            "fromName": "Hydra",
            "useTls": True,
        },
        "objectStorage": {
            "enabled": False,
            "endpoint": None,
            "bucket": "hydra-bucket",
            "region": "garage",
        },
        "defaults": {
            "nodeStatus": "active",
            "profileRetentionDays": 90,
            "sessionTimeoutMinutes": 60,
        },
        "updatedBy": "user_admin123",
        "updatedAt": datetime.now(timezone.utc),
    }


@pytest.mark.asyncio
async def test_get_user_settings_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_user_settings,
):
    """Test getting user settings."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    settings_with_user_id = sample_user_settings.copy()
    settings_with_user_id["userId"] = "user_admin123"

    # Second call for settings service
    mock_mongodb.users.find_one = AsyncMock(side_effect=[admin_user, admin_user, settings_with_user_id, settings_with_user_id])
    mock_mongodb.user_settings = MagicMock()
    mock_mongodb.user_settings.find_one = AsyncMock(return_value=settings_with_user_id)

    response = await client.get(
        "/api/v1/settings",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["userId"] == "user_admin123"


@pytest.mark.asyncio
async def test_update_user_settings_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_user_settings,
):
    """Test updating user settings."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"

    updated_settings = sample_user_settings.copy()
    updated_settings["ui"] = {
        **sample_user_settings["ui"],
        "theme": "light",
    }

    mock_mongodb.users.find_one = AsyncMock(side_effect=[admin_user, admin_user, admin_user, admin_user])
    mock_mongodb.users.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_mongodb.user_settings = MagicMock()
    mock_mongodb.user_settings.find_one = AsyncMock(side_effect=[sample_user_settings, updated_settings])
    mock_mongodb.user_settings.update_one = AsyncMock(return_value=MagicMock(modified_count=1))

    response = await client.put(
        "/api/v1/settings",
        json={
            "ui": {"theme": "light"},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ui"]["theme"] == "light"


@pytest.mark.asyncio
async def test_settings_forbidden_for_agent(
    client: AsyncClient,
    mock_mongodb,
    agent_token,
    sample_node,
):
    """Test that agents cannot access settings."""
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)

    response = await client.get(
        "/api/v1/settings",
        headers={"Authorization": f"Bearer {agent_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_system_settings_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_system_settings,
):
    """Test getting system settings as admin."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    # Mock the settings collection
    mock_settings = MagicMock()
    mock_settings.find_one = AsyncMock(return_value=sample_system_settings)
    mock_mongodb.settings = mock_settings
    mock_mongodb.system_settings = mock_settings

    response = await client.get(
        "/api/v1/settings/system",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_system_settings_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_system_settings,
):
    """Test updating system settings as admin."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    updated_settings = sample_system_settings.copy()
    updated_settings["defaults"] = {
        **sample_system_settings["defaults"],
        "profileRetentionDays": 120,
    }

    mock_settings = MagicMock()
    mock_settings.find_one = AsyncMock(side_effect=[sample_system_settings, updated_settings])
    mock_settings.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_mongodb.settings = mock_settings
    mock_mongodb.system_settings = mock_settings
    mock_mongodb.audit_log.insert_one = AsyncMock()

    response = await client.put(
        "/api/v1/settings/system",
        json={"defaults": {"profileRetentionDays": 120}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_system_settings_forbidden_for_viewer(
    client: AsyncClient,
    mock_mongodb,
    viewer_token,
    sample_user,
):
    """Test that viewer cannot access system settings."""
    viewer_user = sample_user.copy()
    viewer_user["userId"] = "user_viewer123"
    viewer_user["role"] = "viewer"
    mock_mongodb.users.find_one = AsyncMock(return_value=viewer_user)

    response = await client.get(
        "/api/v1/settings/system",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_system_settings_forbidden_for_viewer(
    client: AsyncClient,
    mock_mongodb,
    viewer_token,
    sample_user,
):
    """Test that viewer cannot update system settings."""
    viewer_user = sample_user.copy()
    viewer_user["userId"] = "user_viewer123"
    viewer_user["role"] = "viewer"
    mock_mongodb.users.find_one = AsyncMock(return_value=viewer_user)

    response = await client.put(
        "/api/v1/settings/system",
        json={"instanceName": "Should Fail"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403
