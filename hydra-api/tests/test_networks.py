"""Tests for network management endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from tests.utils import create_mock_cursor


@pytest.fixture
def sample_network():
    """Sample network document."""
    now = datetime.now(timezone.utc)
    return {
        "networkId": "homenet",
        "name": "Home LAN",
        "description": "Primary home network",
        "type": "physical",
        "cidr": "192.168.1.0/24",
        "cidrV6": None,
        "gatewayV4": "192.168.1.1",
        "gatewayV6": None,
        "vlanId": None,
        "parentNetworkId": None,
        "subnetIds": [],
        "routerNodeId": "opnsense-01",
        "dhcp": {"enabled": True},
        "dns": {"servers": ["8.8.8.8", "8.8.4.4"]},
        "origin": {
            "createdBy": "auto",
            "sourceNodeId": None,
            "sourceProfileId": None,
        },
        "tags": ["production", "primary"],
        "nodeCount": 10,
        "createdAt": now,
        "updatedAt": now,
    }


@pytest.mark.asyncio
async def test_list_networks_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_network,
    sample_user,
):
    """Test listing networks."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.networks.count_documents = AsyncMock(return_value=1)
    mock_mongodb.networks.find.return_value = create_mock_cursor([sample_network])

    response = await client.get(
        "/api/v1/networks",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert len(data["data"]) == 1
    assert data["data"][0]["networkId"] == sample_network["networkId"]
    assert data["meta"]["total"] == 1


@pytest.mark.asyncio
async def test_list_networks_with_filters(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_network,
    sample_user,
):
    """Test listing networks with filters."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.networks.count_documents = AsyncMock(return_value=1)
    mock_mongodb.networks.find.return_value = create_mock_cursor([sample_network])

    response = await client.get(
        "/api/v1/networks?type=physical&routerNodeId=opnsense-01",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1


@pytest.mark.asyncio
async def test_list_networks_with_search(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_network,
    sample_user,
):
    """Test listing networks with search filter."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.networks.count_documents = AsyncMock(return_value=1)
    mock_mongodb.networks.find.return_value = create_mock_cursor([sample_network])

    response = await client.get(
        "/api/v1/networks?search=home",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1


@pytest.mark.asyncio
async def test_create_network_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_network,
    sample_user,
):
    """Test creating a new network."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.networks.find_one = AsyncMock(return_value=None)  # Network doesn't exist
    mock_mongodb.networks.insert_one = AsyncMock()

    # After insert, return the created network
    created_network = sample_network.copy()
    created_network["networkId"] = "test-net"
    mock_mongodb.networks.find_one = AsyncMock(side_effect=[None, created_network])

    response = await client.post(
        "/api/v1/networks",
        json={
            "networkId": "test-net",
            "name": "Test Network",
            "type": "physical",
            "cidr": "10.0.0.0/24",
            "gatewayV4": "10.0.0.1",
            "description": "A test network",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert "data" in data


@pytest.mark.asyncio
async def test_get_network_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_network,
    sample_user,
):
    """Test getting a single network."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.networks.find_one = AsyncMock(return_value=sample_network)

    response = await client.get(
        f"/api/v1/networks/{sample_network['networkId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["networkId"] == sample_network["networkId"]
    assert data["data"]["name"] == "Home LAN"
    assert data["data"]["cidr"] == "192.168.1.0/24"


@pytest.mark.asyncio
async def test_get_network_not_found(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test getting a non-existent network."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.networks.find_one = AsyncMock(return_value=None)

    response = await client.get(
        "/api/v1/networks/nonexistent-net",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "NETWORK_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_network_with_nodes(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_network,
    sample_user,
):
    """Test getting a network with included nodes."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    network_with_nodes = sample_network.copy()
    network_with_nodes["nodes"] = [
        {"nodeId": "server-01", "displayName": "Server 01", "ipAddress": "192.168.1.10"}
    ]
    mock_mongodb.networks.find_one = AsyncMock(return_value=network_with_nodes)
    mock_mongodb.nodes.find.return_value = create_mock_cursor([])

    response = await client.get(
        f"/api/v1/networks/{sample_network['networkId']}?includeNodes=true",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_network_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_network,
    sample_user,
):
    """Test updating a network."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    updated_network = sample_network.copy()
    updated_network["name"] = "Updated Network"
    updated_network["description"] = "Updated description"

    mock_mongodb.networks.find_one = AsyncMock(side_effect=[sample_network, updated_network])
    mock_mongodb.networks.update_one = AsyncMock(return_value=MagicMock(modified_count=1))

    response = await client.put(
        f"/api/v1/networks/{sample_network['networkId']}",
        json={
            "name": "Updated Network",
            "description": "Updated description",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["name"] == "Updated Network"


@pytest.mark.asyncio
async def test_delete_network_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_network,
    sample_user,
):
    """Test deleting a network."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    # Network has no nodes
    network_no_nodes = sample_network.copy()
    network_no_nodes["nodeCount"] = 0
    mock_mongodb.networks.find_one = AsyncMock(return_value=network_no_nodes)
    mock_mongodb.networks.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))
    mock_mongodb.networks.update_one = AsyncMock()
    mock_mongodb.nodes.update_many = AsyncMock()
    mock_mongodb.nodes.count_documents = AsyncMock(return_value=0)

    response = await client.delete(
        f"/api/v1/networks/{sample_network['networkId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_delete_network_with_force(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_network,
    sample_user,
):
    """Test force deleting a network with nodes."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.networks.find_one = AsyncMock(return_value=sample_network)
    mock_mongodb.networks.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))
    mock_mongodb.nodes.update_many = AsyncMock()

    response = await client.delete(
        f"/api/v1/networks/{sample_network['networkId']}?force=true",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_network_nodes(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_network,
    sample_user,
    sample_node,
):
    """Test getting nodes in a network."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.networks.find_one = AsyncMock(return_value=sample_network)

    node_in_network = sample_node.copy()
    node_in_network["networkIds"] = [sample_network["networkId"]]
    mock_mongodb.nodes.find.return_value = create_mock_cursor([node_in_network])

    response = await client.get(
        f"/api/v1/networks/{sample_network['networkId']}/nodes",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "data" in data


@pytest.mark.asyncio
async def test_networks_forbidden_for_viewer_create(
    client: AsyncClient,
    mock_mongodb,
    viewer_token,
    sample_user,
):
    """Test that viewer cannot create networks."""
    viewer_user = sample_user.copy()
    viewer_user["userId"] = "user_viewer123"
    viewer_user["role"] = "viewer"
    mock_mongodb.users.find_one = AsyncMock(return_value=viewer_user)

    response = await client.post(
        "/api/v1/networks",
        json={
            "networkId": "viewernet",
            "name": "Test Network",
            "type": "physical",
            "cidr": "10.0.0.0/24",
        },
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_networks_forbidden_for_viewer_update(
    client: AsyncClient,
    mock_mongodb,
    viewer_token,
    sample_network,
    sample_user,
):
    """Test that viewer cannot update networks."""
    viewer_user = sample_user.copy()
    viewer_user["userId"] = "user_viewer123"
    viewer_user["role"] = "viewer"
    mock_mongodb.users.find_one = AsyncMock(return_value=viewer_user)

    response = await client.put(
        f"/api/v1/networks/{sample_network['networkId']}",
        json={"name": "Should Fail"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_networks_forbidden_for_viewer_delete(
    client: AsyncClient,
    mock_mongodb,
    viewer_token,
    sample_network,
    sample_user,
):
    """Test that viewer cannot delete networks."""
    viewer_user = sample_user.copy()
    viewer_user["userId"] = "user_viewer123"
    viewer_user["role"] = "viewer"
    mock_mongodb.users.find_one = AsyncMock(return_value=viewer_user)

    response = await client.delete(
        f"/api/v1/networks/{sample_network['networkId']}",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_networks_pagination(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_network,
    sample_user,
):
    """Test networks pagination."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.networks.count_documents = AsyncMock(return_value=50)
    mock_mongodb.networks.find.return_value = create_mock_cursor([sample_network])

    response = await client.get(
        "/api/v1/networks?limit=10&offset=20",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total"] == 50
    assert data["meta"]["limit"] == 10
    assert data["meta"]["offset"] == 20


@pytest.mark.asyncio
async def test_list_networks_sorting(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_network,
    sample_user,
):
    """Test networks sorting."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.networks.count_documents = AsyncMock(return_value=1)
    mock_mongodb.networks.find.return_value = create_mock_cursor([sample_network])

    response = await client.get(
        "/api/v1/networks?sortBy=name&sortOrder=asc",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_networks_by_cidr(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_network,
    sample_user,
):
    """Test filtering networks by CIDR."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.networks.count_documents = AsyncMock(return_value=1)
    mock_mongodb.networks.find.return_value = create_mock_cursor([sample_network])

    response = await client.get(
        "/api/v1/networks?cidr=192.168.1.0/24",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1


@pytest.mark.asyncio
async def test_list_networks_by_tags(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_network,
    sample_user,
):
    """Test filtering networks by tags."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.networks.count_documents = AsyncMock(return_value=1)
    mock_mongodb.networks.find.return_value = create_mock_cursor([sample_network])

    response = await client.get(
        "/api/v1/networks?tags=production&tags=primary",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1


@pytest.mark.asyncio
async def test_list_networks_by_parent(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_network,
    sample_user,
):
    """Test filtering networks by parent network ID."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.networks.count_documents = AsyncMock(return_value=1)
    mock_mongodb.networks.find.return_value = create_mock_cursor([sample_network])

    response = await client.get(
        "/api/v1/networks?parentNetworkId=net-parent",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
