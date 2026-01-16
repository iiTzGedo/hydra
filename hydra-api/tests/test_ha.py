"""Tests for Home Assistant integration endpoints."""

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from hydra.api.v1.services.ha import HomeAssistantService


@pytest.fixture
def sample_ha_device():
    """Sample Home Assistant device."""
    return {
        "entityId": "light.living_room",
        "name": "Living Room Light",
        "state": "on",
        "domain": "light",
        "area": "living_room",
        "attributes": {
            "brightness": 255,
            "color_mode": "rgb",
        },
    }


@pytest.mark.asyncio
async def test_get_ha_status(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    monkeypatch,
):
    """Test getting Home Assistant status."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    monkeypatch.setattr(
        HomeAssistantService,
        "get_status",
        AsyncMock(return_value={
            "enabled": True,
            "connected": True,
            "url": "http://ha.local",
            "lastSync": None,
            "entityCount": 1,
            "mappedNodes": 0,
        }),
    )

    response = await client.get(
        "/api/v1/ha/status",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["enabled"] is True
    assert data["data"]["connected"] is True


@pytest.mark.asyncio
async def test_list_ha_devices(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_ha_device,
    monkeypatch,
):
    """Test listing Home Assistant devices."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    monkeypatch.setattr(
        HomeAssistantService,
        "list_devices",
        AsyncMock(return_value=([sample_ha_device], 1)),
    )

    response = await client.get(
        "/api/v1/ha/devices",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["total"] == 1


@pytest.mark.asyncio
async def test_list_ha_devices_by_domain(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    monkeypatch,
):
    """Test listing Home Assistant devices by domain."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    monkeypatch.setattr(
        HomeAssistantService,
        "list_devices",
        AsyncMock(return_value=([], 0)),
    )

    response = await client.get(
        "/api/v1/ha/devices?domain=light",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_ha_sync(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    monkeypatch,
):
    """Test syncing Home Assistant."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    monkeypatch.setattr(
        HomeAssistantService,
        "sync_devices",
        AsyncMock(return_value={
            "jobId": "job-ha-sync-1234",
            "status": "running",
            "startedAt": sample_user["createdAt"],
        }),
    )

    response = await client.post(
        "/api/v1/ha/sync",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 202


@pytest.mark.asyncio
async def test_ha_control(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    monkeypatch,
):
    """Test controlling a Home Assistant device."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    monkeypatch.setattr(
        HomeAssistantService,
        "control_device",
        AsyncMock(return_value={
            "entityId": "light.living_room",
            "service": "turn_on",
            "success": True,
            "newState": {"state": "on"},
        }),
    )

    response = await client.post(
        "/api/v1/ha/control",
        json={
            "entityId": "light.living_room",
            "service": "turn_on",
            "data": {"brightness": 128},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_ha_areas(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    monkeypatch,
):
    """Test listing Home Assistant areas."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    monkeypatch.setattr(
        HomeAssistantService,
        "list_areas",
        AsyncMock(return_value=([{"areaId": "living_room", "name": "Living Room"}], 1)),
    )

    response = await client.get(
        "/api/v1/ha/areas",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_ha_family_role_access(
    client: AsyncClient,
    mock_mongodb,
    sample_user,
    test_settings,
    monkeypatch,
):
    """Test that family role can access HA controls."""
    from hydra.api.v1.core.security import create_access_token
    from hydra.core.config import get_settings

    settings = get_settings()
    family_token = create_access_token(
        subject="user_family123",
        token_type="access",
        additional_claims={
            "sub_type": "user",
            "role": "family",
            "permissions": ["iot:control", "ha:control"],
        },
        settings=settings,
    )

    family_user = sample_user.copy()
    family_user["userId"] = "user_family123"
    family_user["role"] = "family"
    mock_mongodb.users.find_one = AsyncMock(return_value=family_user)

    monkeypatch.setattr(
        HomeAssistantService,
        "list_devices",
        AsyncMock(return_value=([], 0)),
    )

    response = await client.get(
        "/api/v1/ha/devices",
        headers={"Authorization": f"Bearer {family_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_ha_forbidden_for_agent(
    client: AsyncClient,
    mock_mongodb,
    agent_token,
    sample_node,
):
    """Test that agents cannot access HA endpoints."""
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)

    response = await client.get(
        "/api/v1/ha/devices",
        headers={"Authorization": f"Bearer {agent_token}"},
    )

    assert response.status_code == 403
