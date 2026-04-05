"""Tests for topology management endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from tests.utils import create_mock_cursor


@pytest.fixture
def sample_topology():
    """Sample topology document."""
    now = datetime.now(UTC)
    return {
        "topologyId": "topo-abc123",
        "mode": "infrastructure",
        "version": 1,
        "scope": None,
        "validFrom": now,
        "validUntil": None,
        "generatedAt": now,
        "previousTopologyId": None,
        "diff": None,
        "stats": {
            "nodeCount": 10,
            "edgeCount": 15,
            "serviceCount": 25,
            "networkCount": 3,
            "computeTimeMs": 100,
        },
        "graph": {
            "nodes": [
                {
                    "id": "server-01",
                    "type": "compute",
                    "label": "Server 01",
                    "data": {"status": "active"},
                    "position": {"x": 0, "y": 0, "layer": 1},
                }
            ],
            "edges": [
                {
                    "id": "edge-server01-router01",
                    "source": "server-01",
                    "target": "router-01",
                    "type": "network-connection",
                    "data": {},
                }
            ],
        },
    }


@pytest.mark.asyncio
async def test_list_topologies_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_topology,
    sample_user,
):
    """Test listing topologies."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.topologies.count_documents = AsyncMock(return_value=1)
    mock_mongodb.topologies.find.return_value = create_mock_cursor([sample_topology])

    response = await client.get(
        "/api/v1/topologies",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert len(data["data"]) == 1
    assert data["data"][0]["topologyId"] == sample_topology["topologyId"]


@pytest.mark.asyncio
async def test_list_topologies_with_mode_filter(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_topology,
    sample_user,
):
    """Test listing topologies with mode filter."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.topologies.count_documents = AsyncMock(return_value=1)
    mock_mongodb.topologies.find.return_value = create_mock_cursor([sample_topology])

    response = await client.get(
        "/api/v1/topologies?mode=infrastructure",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1


@pytest.mark.asyncio
async def test_list_topologies_with_time_range(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_topology,
    sample_user,
):
    """Test listing topologies with time range filter."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.topologies.count_documents = AsyncMock(return_value=1)
    mock_mongodb.topologies.find.return_value = create_mock_cursor([sample_topology])

    response = await client.get(
        "/api/v1/topologies?since=2024-01-01T00:00:00Z&until=2024-12-31T23:59:59Z",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1


@pytest.mark.asyncio
async def test_get_latest_topology(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_topology,
    sample_user,
):
    """Test getting the latest topology."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.topologies.find_one = AsyncMock(return_value=sample_topology)

    response = await client.get(
        "/api/v1/topologies/latest?mode=infrastructure",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["topologyId"] == sample_topology["topologyId"]


@pytest.mark.asyncio
async def test_get_latest_topology_without_graph(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_topology,
    sample_user,
):
    """Test getting the latest topology without graph data."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    topology_no_graph = sample_topology.copy()
    del topology_no_graph["graph"]
    mock_mongodb.topologies.find_one = AsyncMock(return_value=topology_no_graph)

    response = await client.get(
        "/api/v1/topologies/latest?mode=infrastructure&includeGraph=false",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_topology_by_id(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_topology,
    sample_user,
):
    """Test getting a specific topology by ID."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.topologies.find_one = AsyncMock(return_value=sample_topology)

    response = await client.get(
        f"/api/v1/topologies/{sample_topology['topologyId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["topologyId"] == sample_topology["topologyId"]


@pytest.mark.asyncio
async def test_get_topology_not_found(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test getting a non-existent topology."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.topologies.find_one = AsyncMock(return_value=None)

    response = await client.get(
        "/api/v1/topologies/topo-nonexistent",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "TOPOLOGY_NOT_FOUND"


@pytest.mark.asyncio
async def test_diff_topologies(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_topology,
    sample_user,
):
    """Test comparing two topologies."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    old_topology = sample_topology.copy()
    old_topology["topologyId"] = "topo-old123"
    old_topology["nodeCount"] = 8

    new_topology = sample_topology.copy()
    new_topology["topologyId"] = "topo-new123"
    new_topology["nodeCount"] = 10

    mock_mongodb.topologies.find_one = AsyncMock(side_effect=[old_topology, new_topology])

    response = await client.get(
        "/api/v1/topologies/diff?fromId=topo-old123&toId=topo-new123",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_diff_topologies_by_mode(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_topology,
    sample_user,
):
    """Test comparing topologies by mode (latest two)."""
    # Create two different topologies for comparison
    old_topology = sample_topology.copy()
    old_topology["topologyId"] = "topo-old123"

    new_topology = sample_topology.copy()
    new_topology["topologyId"] = "topo-new123"

    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    # find().sort().limit().to_list() returns the two topologies
    mock_mongodb.topologies.find.return_value = create_mock_cursor([new_topology, old_topology])
    # find_one is called to get to_topo (latest for mode)
    mock_mongodb.topologies.find_one = AsyncMock(return_value=new_topology)

    response = await client.get(
        "/api/v1/topologies/diff?mode=infrastructure",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_generate_topology(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_topology,
    sample_user,
):
    """Test generating a new topology."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.nodes.find.return_value = create_mock_cursor([])
    mock_mongodb.services.find.return_value = create_mock_cursor([])
    mock_mongodb.networks.find.return_value = create_mock_cursor([])
    mock_mongodb.topologies.find_one = AsyncMock(return_value=None)
    mock_mongodb.topologies.insert_one = AsyncMock()
    mock_mongodb.topologies.update_one = AsyncMock()

    # Return the new topology after generation
    mock_mongodb.topologies.find_one = AsyncMock(side_effect=[None, sample_topology])

    response = await client.post(
        "/api/v1/topologies/generate",
        json={
            "mode": "infrastructure",
            "force": True,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201


@pytest.mark.asyncio
async def test_get_subgraph(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_topology,
    sample_user,
    sample_node,
):
    """Test getting a subgraph centered on a node."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.topologies.find_one = AsyncMock(return_value=sample_topology)
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)
    mock_mongodb.nodes.find.return_value = create_mock_cursor([sample_node])
    mock_mongodb.services.find.return_value = create_mock_cursor([])
    mock_mongodb.networks.find.return_value = create_mock_cursor([])

    response = await client.get(
        "/api/v1/topologies/subgraph?nodeId=server-01&depth=1",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_subgraph_with_options(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_topology,
    sample_user,
    sample_node,
):
    """Test getting a subgraph with options."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.topologies.find_one = AsyncMock(return_value=sample_topology)
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)
    mock_mongodb.nodes.find.return_value = create_mock_cursor([sample_node])
    mock_mongodb.services.find.return_value = create_mock_cursor([])
    mock_mongodb.networks.find.return_value = create_mock_cursor([])

    response = await client.get(
        "/api/v1/topologies/subgraph?nodeId=server-01&depth=2&includeServices=true&includeNetworks=true",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_topologies_forbidden_for_viewer_generate(
    client: AsyncClient,
    mock_mongodb,
    viewer_token,
    sample_user,
):
    """Test that viewer cannot generate topologies."""
    viewer_user = sample_user.copy()
    viewer_user["userId"] = "user_viewer123"
    viewer_user["role"] = "viewer"
    mock_mongodb.users.find_one = AsyncMock(return_value=viewer_user)

    response = await client.post(
        "/api/v1/topologies/generate",
        json={"mode": "infrastructure"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_topologies_pagination(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_topology,
    sample_user,
):
    """Test topologies pagination."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.topologies.count_documents = AsyncMock(return_value=50)
    mock_mongodb.topologies.find.return_value = create_mock_cursor([sample_topology])

    response = await client.get(
        "/api/v1/topologies?limit=10&offset=20",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total"] == 50
    assert data["meta"]["limit"] == 10
    assert data["meta"]["offset"] == 20
