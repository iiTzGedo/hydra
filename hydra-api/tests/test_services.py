"""Tests for service management endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from tests.utils import create_mock_cursor


@pytest.fixture
def sample_service():
    """Sample service document."""
    now = datetime.now(UTC)
    return {
        "serviceId": "svc-nginx-a1b2",
        "nodeId": "test-server-01",
        "profileId": "prof_abc123",
        "name": "nginx",
        "displayName": "Nginx Web Server",
        "description": "HTTP and reverse proxy server",
        "runtime": "systemd",
        "status": "running",
        "version": "1.24.0",
        "image": None,
        "exposure": {
            "ports": [{"port": 80, "protocol": "tcp"}],
            "endpoints": [],
        },
        "resources": None,
        "attachments": None,
        "origin": {
            "nativeId": "nginx.service",
            "discoveredBy": "agent",
            "collectedAt": now,
        },
        "health": None,
        "tags": ["web", "proxy"],
        "firstSeen": now,
        "lastSeen": now,
    }


@pytest.mark.asyncio
async def test_list_services_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_service,
    sample_user,
):
    """Test listing services."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.services.count_documents = AsyncMock(return_value=1)
    mock_mongodb.services.find.return_value = create_mock_cursor([sample_service])

    response = await client.get(
        "/api/v1/services",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert len(data["data"]) == 1
    assert data["data"][0]["serviceId"] == sample_service["serviceId"]
    assert data["meta"]["total"] == 1


@pytest.mark.asyncio
async def test_list_services_with_filters(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_service,
    sample_user,
):
    """Test listing services with filters."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.services.count_documents = AsyncMock(return_value=1)
    mock_mongodb.services.find.return_value = create_mock_cursor([sample_service])

    response = await client.get(
        "/api/v1/services?runtime=systemd&status=running&nodeId=test-server-01",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1


@pytest.mark.asyncio
async def test_list_services_with_search(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_service,
    sample_user,
):
    """Test listing services with search filter."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.services.count_documents = AsyncMock(return_value=1)
    mock_mongodb.services.find.return_value = create_mock_cursor([sample_service])

    response = await client.get(
        "/api/v1/services?search=nginx",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1


@pytest.mark.asyncio
async def test_get_service_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_service,
    sample_user,
):
    """Test getting a single service."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.services.find_one = AsyncMock(return_value=sample_service)

    response = await client.get(
        f"/api/v1/services/{sample_service['serviceId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["serviceId"] == sample_service["serviceId"]
    assert data["data"]["name"] == "nginx"
    assert data["data"]["runtime"] == "systemd"


@pytest.mark.asyncio
async def test_get_service_not_found(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test getting a non-existent service."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.services.find_one = AsyncMock(return_value=None)

    response = await client.get(
        "/api/v1/services/svc-nonexistent-1234",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "SERVICE_NOT_FOUND"


@pytest.mark.asyncio
async def test_update_service_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_service,
    sample_user,
):
    """Test updating a service."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    updated_service = sample_service.copy()
    updated_service["displayName"] = "Updated Nginx"
    updated_service["description"] = "Updated description"
    updated_service["tags"] = ["web", "proxy", "updated"]

    mock_mongodb.services.find_one = AsyncMock(side_effect=[sample_service, updated_service])
    mock_mongodb.services.update_one = AsyncMock(return_value=MagicMock(modified_count=1))

    response = await client.patch(
        f"/api/v1/services/{sample_service['serviceId']}",
        json={
            "displayName": "Updated Nginx",
            "description": "Updated description",
            "tags": ["web", "proxy", "updated"],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["displayName"] == "Updated Nginx"


@pytest.mark.asyncio
async def test_archive_service_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_service,
    sample_user,
):
    """Test archiving a service."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    archived_service = sample_service.copy()
    archived_service["status"] = "archived"

    mock_mongodb.services.find_one = AsyncMock(side_effect=[sample_service, archived_service])
    mock_mongodb.services.update_one = AsyncMock(return_value=MagicMock(modified_count=1))

    response = await client.delete(
        f"/api/v1/services/{sample_service['serviceId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["status"] == "archived"


@pytest.mark.asyncio
async def test_get_services_by_node(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_service,
    sample_user,
):
    """Test getting services for a specific node via nodeId filter."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.services.count_documents = AsyncMock(return_value=1)
    mock_mongodb.services.find.return_value = create_mock_cursor([sample_service])

    response = await client.get(
        "/api/v1/services?nodeId=test-server-01",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["nodeId"] == "test-server-01"


@pytest.mark.asyncio
async def test_get_services_by_node_with_filters(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_service,
    sample_user,
):
    """Test getting services for a node with runtime filter."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.services.count_documents = AsyncMock(return_value=1)
    mock_mongodb.services.find.return_value = create_mock_cursor([sample_service])

    response = await client.get(
        "/api/v1/services?nodeId=test-server-01&runtime=systemd&status=running",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1


@pytest.mark.asyncio
async def test_services_forbidden_for_viewer_update(
    client: AsyncClient,
    mock_mongodb,
    viewer_token,
    sample_service,
    sample_user,
):
    """Test that viewer cannot update services."""
    viewer_user = sample_user.copy()
    viewer_user["userId"] = "user_viewer123"
    viewer_user["role"] = "viewer"
    mock_mongodb.users.find_one = AsyncMock(return_value=viewer_user)

    response = await client.patch(
        f"/api/v1/services/{sample_service['serviceId']}",
        json={"displayName": "Should Fail"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_services_forbidden_for_viewer_delete(
    client: AsyncClient,
    mock_mongodb,
    viewer_token,
    sample_service,
    sample_user,
):
    """Test that viewer cannot delete services."""
    viewer_user = sample_user.copy()
    viewer_user["userId"] = "user_viewer123"
    viewer_user["role"] = "viewer"
    mock_mongodb.users.find_one = AsyncMock(return_value=viewer_user)

    response = await client.delete(
        f"/api/v1/services/{sample_service['serviceId']}",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_services_pagination(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_service,
    sample_user,
):
    """Test services pagination."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.services.count_documents = AsyncMock(return_value=100)
    mock_mongodb.services.find.return_value = create_mock_cursor([sample_service])

    response = await client.get(
        "/api/v1/services?limit=10&offset=20",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total"] == 100
    assert data["meta"]["limit"] == 10
    assert data["meta"]["offset"] == 20


@pytest.mark.asyncio
async def test_list_services_sorting(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_service,
    sample_user,
):
    """Test services sorting."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.services.count_documents = AsyncMock(return_value=1)
    mock_mongodb.services.find.return_value = create_mock_cursor([sample_service])

    response = await client.get(
        "/api/v1/services?sortBy=name&sortOrder=asc",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_services_by_port(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_service,
    sample_user,
):
    """Test filtering services by port."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.services.count_documents = AsyncMock(return_value=1)
    mock_mongodb.services.find.return_value = create_mock_cursor([sample_service])

    response = await client.get(
        "/api/v1/services?port=80",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1


@pytest.mark.asyncio
async def test_list_services_by_tags(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_service,
    sample_user,
):
    """Test filtering services by tags."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.services.count_documents = AsyncMock(return_value=1)
    mock_mongodb.services.find.return_value = create_mock_cursor([sample_service])

    response = await client.get(
        "/api/v1/services?tags=web&tags=proxy",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
