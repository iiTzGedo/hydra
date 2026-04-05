"""Tests for query endpoints."""

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from tests.utils import create_mock_cursor


@pytest.mark.asyncio
async def test_query_nodes_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_node,
    sample_user,
):
    """Test querying nodes."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)
    mock_mongodb.nodes.find.return_value = create_mock_cursor([sample_node])
    mock_mongodb.nodes.count_documents = AsyncMock(return_value=1)

    response = await client.post(
        "/api/v1/query",
        json={
            "collection": "nodes",
            "filter": {"status": "active"},
            "limit": 10,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "data" in data


@pytest.mark.asyncio
async def test_query_services_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test querying services."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    sample_service = {
        "serviceId": "svc-nginx-a1b2",
        "nodeId": "server-01",
        "name": "nginx",
        "status": "running",
    }
    mock_mongodb.services.find.return_value = create_mock_cursor([sample_service])
    mock_mongodb.services.count_documents = AsyncMock(return_value=1)

    response = await client.post(
        "/api/v1/query",
        json={
            "collection": "services",
            "filter": {"status": "running"},
            "limit": 10,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_query_with_projection(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_node,
    sample_user,
):
    """Test querying with field projection."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)
    mock_mongodb.nodes.find.return_value = create_mock_cursor([{"nodeId": sample_node["nodeId"]}])
    mock_mongodb.nodes.count_documents = AsyncMock(return_value=1)

    response = await client.post(
        "/api/v1/query",
        json={
            "collection": "nodes",
            "filter": {},
            "projection": {"nodeId": 1, "displayName": 1},
            "limit": 10,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_query_with_sort(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_node,
    sample_user,
):
    """Test querying with sorting."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)
    mock_mongodb.nodes.find.return_value = create_mock_cursor([sample_node])
    mock_mongodb.nodes.count_documents = AsyncMock(return_value=1)

    response = await client.post(
        "/api/v1/query",
        json={
            "collection": "nodes",
            "filter": {},
            "sort": {"registeredAt": -1},
            "limit": 10,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_query_pagination(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_node,
    sample_user,
):
    """Test query pagination."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)
    mock_mongodb.nodes.find.return_value = create_mock_cursor([sample_node])
    mock_mongodb.nodes.count_documents = AsyncMock(return_value=100)

    response = await client.post(
        "/api/v1/query",
        json={
            "collection": "nodes",
            "filter": {},
            "limit": 10,
            "skip": 20,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_query_rejects_disallowed_projection_field(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test query rejects secret-looking projection fields."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    response = await client.post(
        "/api/v1/query",
        json={
            "collection": "nodes",
            "projection": {"serverSecret": 1},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_query_rejects_disallowed_sort_field(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test query rejects sort fields outside the public allowlist."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    response = await client.post(
        "/api/v1/query",
        json={
            "collection": "nodes",
            "sort": {"passwordHash": -1},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_query_invalid_collection(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test query with invalid collection."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    response = await client.post(
        "/api/v1/query",
        json={
            "collection": "invalid_collection",
            "filter": {},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_query_viewer_forbidden(
    client: AsyncClient,
    mock_mongodb,
    viewer_token,
    sample_user,
):
    """Test that viewer cannot use advanced query (requires query:read)."""
    viewer_user = sample_user.copy()
    viewer_user["userId"] = "user_viewer123"
    viewer_user["role"] = "viewer"
    mock_mongodb.users.find_one = AsyncMock(return_value=viewer_user)

    response = await client.post(
        "/api/v1/query",
        json={
            "collection": "nodes",
            "filter": {},
        },
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403
