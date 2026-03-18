"""Tests for node management endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from tests.utils import create_mock_cursor


@pytest.mark.asyncio
async def test_list_nodes_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_node,
    sample_user,
):
    """Test listing nodes."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.nodes.count_documents = AsyncMock(return_value=1)
    mock_mongodb.nodes.find.return_value = create_mock_cursor([sample_node])

    response = await client.get(
        "/api/v1/nodes",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert len(data["data"]) == 1
    assert data["data"][0]["nodeId"] == sample_node["nodeId"]
    assert data["meta"]["total"] == 1


@pytest.mark.asyncio
async def test_list_nodes_with_filters(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_node,
    sample_user,
):
    """Test listing nodes with filters."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.nodes.count_documents = AsyncMock(return_value=1)
    mock_mongodb.nodes.find.return_value = create_mock_cursor([sample_node])

    response = await client.get(
        "/api/v1/nodes?class=compute&status=active&tags=test",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1


@pytest.mark.asyncio
async def test_get_node_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_node,
    sample_user,
):
    """Test getting a single node."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)

    response = await client.get(
        f"/api/v1/nodes/{sample_node['nodeId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["nodeId"] == sample_node["nodeId"]
    assert data["data"]["class"] == "compute"
    assert data["data"]["displayName"] == sample_node["displayName"]


@pytest.mark.asyncio
async def test_get_node_includes_server_tls_metadata(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_node,
    sample_user,
):
    """Test node detail responses expose direct-control server metadata."""
    max_tier_node = {
        **sample_node,
        "agentTier": "max",
        "serverAddress": "agent.internal.example",
        "serverPort": 9443,
        "serverTlsEnabled": True,
        "serverReachable": True,
        "failedDirectAttempts": 0,
        "lastDirectContact": None,
        "lastPollContact": None,
    }
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.nodes.find_one = AsyncMock(return_value=max_tier_node)

    response = await client.get(
        f"/api/v1/nodes/{sample_node['nodeId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["agentTier"] == "max"
    assert data["data"]["serverAddress"] == "agent.internal.example"
    assert data["data"]["serverPort"] == 9443
    assert data["data"]["serverTlsEnabled"] is True


@pytest.mark.asyncio
async def test_get_node_not_found(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test getting a non-existent node."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.nodes.find_one = AsyncMock(return_value=None)

    response = await client.get(
        "/api/v1/nodes/non-existent-node",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "NODE_NOT_FOUND"


@pytest.mark.asyncio
async def test_update_node_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_node,
    sample_user,
):
    """Test updating a node."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)
    mock_mongodb.nodes.update_one = AsyncMock(return_value=MagicMock(modified_count=1))

    updated_node = sample_node.copy()
    updated_node["displayName"] = "Updated Name"
    updated_node["description"] = "Updated description"
    mock_mongodb.nodes.find_one = AsyncMock(side_effect=[sample_node, updated_node])

    response = await client.patch(
        f"/api/v1/nodes/{sample_node['nodeId']}",
        json={
            "displayName": "Updated Name",
            "description": "Updated description",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["displayName"] == "Updated Name"


@pytest.mark.asyncio
async def test_archive_node_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_node,
    sample_user,
):
    """Test archiving a node."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    archived_node = sample_node.copy()
    archived_node["status"] = "archived"
    mock_mongodb.nodes.find_one = AsyncMock(side_effect=[sample_node, archived_node])
    mock_mongodb.nodes.update_one = AsyncMock(return_value=MagicMock(modified_count=1))

    response = await client.delete(
        f"/api/v1/nodes/{sample_node['nodeId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["status"] == "archived"


@pytest.mark.asyncio
async def test_get_node_children(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_node,
    sample_user,
):
    """Test getting child nodes."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)

    child_node = sample_node.copy()
    child_node["nodeId"] = "child-vm-01"
    child_node["parentNodeId"] = sample_node["nodeId"]
    child_node["type"] = "logical"
    child_node["kind"] = "vm"

    mock_mongodb.nodes.find.return_value = create_mock_cursor([child_node])

    response = await client.get(
        f"/api/v1/nodes/{sample_node['nodeId']}/children",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["nodeId"] == "child-vm-01"


@pytest.mark.asyncio
async def test_nodes_forbidden_for_viewer(
    client: AsyncClient,
    mock_mongodb,
    viewer_token,
    sample_node,
    sample_user,
):
    """Test that viewer cannot update nodes."""
    viewer_user = sample_user.copy()
    viewer_user["userId"] = "user_viewer123"
    viewer_user["role"] = "viewer"
    mock_mongodb.users.find_one = AsyncMock(return_value=viewer_user)

    response = await client.patch(
        f"/api/v1/nodes/{sample_node['nodeId']}",
        json={"displayName": "Should Fail"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403
