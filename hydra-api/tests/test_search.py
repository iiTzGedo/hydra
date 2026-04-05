"""Tests for search endpoints."""

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from tests.utils import create_mock_cursor


@pytest.mark.asyncio
async def test_search_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_node,
    sample_user,
):
    """Test global search."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)
    mock_mongodb.nodes.find.return_value = create_mock_cursor([sample_node])
    mock_mongodb.nodes.count_documents = AsyncMock(return_value=1)
    mock_mongodb.services.find.return_value = create_mock_cursor([])
    mock_mongodb.services.count_documents = AsyncMock(return_value=0)
    mock_mongodb.networks.find.return_value = create_mock_cursor([])
    mock_mongodb.networks.count_documents = AsyncMock(return_value=0)
    mock_mongodb.groups.find.return_value = create_mock_cursor([])
    mock_mongodb.groups.count_documents = AsyncMock(return_value=0)

    response = await client.get(
        "/api/v1/search?q=test",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    # SearchResponse returns query, results, total directly (not wrapped in SuccessResponse)
    assert "query" in data
    assert "results" in data
    assert "total" in data
    assert data["query"] == "test"


@pytest.mark.asyncio
async def test_search_with_type_filter(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_node,
    sample_user,
):
    """Test search with type filter."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)
    mock_mongodb.nodes.find.return_value = create_mock_cursor([sample_node])
    mock_mongodb.nodes.count_documents = AsyncMock(return_value=1)

    response = await client.get(
        "/api/v1/search?q=server&types=nodes",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_search_pagination(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_node,
    sample_user,
):
    """Test search pagination."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)
    mock_mongodb.nodes.find.return_value = create_mock_cursor([sample_node])
    mock_mongodb.nodes.count_documents = AsyncMock(return_value=50)
    mock_mongodb.services.find.return_value = create_mock_cursor([])
    mock_mongodb.services.count_documents = AsyncMock(return_value=0)
    mock_mongodb.networks.find.return_value = create_mock_cursor([])
    mock_mongodb.networks.count_documents = AsyncMock(return_value=0)
    mock_mongodb.groups.find.return_value = create_mock_cursor([])
    mock_mongodb.groups.count_documents = AsyncMock(return_value=0)

    response = await client.get(
        "/api/v1/search?q=test&limit=10&offset=5",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_search_empty_query(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test search with empty query."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    response = await client.get(
        "/api/v1/search?q=",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_search_viewer_access(
    client: AsyncClient,
    mock_mongodb,
    viewer_token,
    sample_node,
    sample_user,
):
    """Test that viewer can search with limited results."""
    viewer_user = sample_user.copy()
    viewer_user["userId"] = "user_viewer123"
    viewer_user["role"] = "viewer"
    mock_mongodb.users.find_one = AsyncMock(return_value=viewer_user)
    mock_mongodb.nodes.find.return_value = create_mock_cursor([sample_node])
    mock_mongodb.nodes.count_documents = AsyncMock(return_value=1)
    mock_mongodb.services.find.return_value = create_mock_cursor([])
    mock_mongodb.services.count_documents = AsyncMock(return_value=0)
    mock_mongodb.networks.find.return_value = create_mock_cursor([])
    mock_mongodb.networks.count_documents = AsyncMock(return_value=0)
    mock_mongodb.groups.find.return_value = create_mock_cursor([])
    mock_mongodb.groups.count_documents = AsyncMock(return_value=0)

    response = await client.get(
        "/api/v1/search?q=test",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 200
