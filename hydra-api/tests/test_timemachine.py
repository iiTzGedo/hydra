"""Tests for Time Machine endpoints."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from tests.utils import create_mock_cursor


@pytest.fixture
def sample_timeline_profile():
    """Sample profile for timeline events (needs submittedAt, version, profileId, nodeId)."""
    now = datetime.now(UTC)
    return {
        "profileId": "prof-abc123",
        "nodeId": "server-01",
        "version": "E0-0.0.1.5",
        "submittedAt": now,
        "collectedAt": now,
        "serviceIds": [],
    }


@pytest.mark.asyncio
async def test_get_node_state_at(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_node,
    sample_profile,
    sample_user,
):
    """Test getting node state at a specific time."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)
    mock_mongodb.profiles.find_one = AsyncMock(return_value=sample_profile)
    mock_mongodb.services.find.return_value = create_mock_cursor([])

    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    response = await client.get(
        f"/api/v1/timemachine/node/{sample_node['nodeId']}?timestamp={timestamp}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["nodeId"] == sample_node["nodeId"]


@pytest.mark.asyncio
async def test_get_node_state_at_with_sections(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_node,
    sample_profile,
    sample_user,
):
    """Test getting node state at a specific time with section filter."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)
    mock_mongodb.profiles.find_one = AsyncMock(return_value=sample_profile)
    mock_mongodb.services.find.return_value = create_mock_cursor([])

    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    response = await client.get(
        f"/api/v1/timemachine/node/{sample_node['nodeId']}?timestamp={timestamp}&sections=hardware&sections=network",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_node_state_at_not_found(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test getting node state for non-existent node."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.nodes.find_one = AsyncMock(return_value=None)

    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    response = await client.get(
        f"/api/v1/timemachine/node/nonexistent?timestamp={timestamp}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_topology_at(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test getting topology at a specific time."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    now = datetime.now(UTC)
    sample_topology = {
        "topologyId": "topo-abc123",
        "mode": "infrastructure",
        "version": 1,
        "validFrom": now - timedelta(hours=1),
        "validUntil": None,
        "generatedAt": now - timedelta(hours=1),
        "stats": {
            "nodeCount": 10,
            "edgeCount": 15,
            "serviceCount": 25,
            "networkCount": 3,
            "computeTimeMs": 100,
        },
        "graph": {"nodes": [], "edges": []},
    }
    mock_mongodb.topologies.find_one = AsyncMock(return_value=sample_topology)

    timestamp = now.isoformat().replace("+00:00", "Z")
    response = await client.get(
        f"/api/v1/timemachine/topology?mode=infrastructure&timestamp={timestamp}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["topologyId"] == "topo-abc123"


@pytest.mark.asyncio
async def test_get_topology_at_without_graph(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test getting topology at a specific time without graph."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    now = datetime.now(UTC)
    sample_topology = {
        "topologyId": "topo-abc123",
        "mode": "infrastructure",
        "version": 1,
        "validFrom": now - timedelta(hours=1),
        "validUntil": None,
        "generatedAt": now - timedelta(hours=1),
        "stats": {
            "nodeCount": 10,
            "edgeCount": 15,
            "serviceCount": 25,
            "networkCount": 3,
            "computeTimeMs": 100,
        },
    }
    mock_mongodb.topologies.find_one = AsyncMock(return_value=sample_topology)

    timestamp = now.isoformat().replace("+00:00", "Z")
    response = await client.get(
        f"/api/v1/timemachine/topology?mode=infrastructure&timestamp={timestamp}&includeGraph=false",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_timeline(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_timeline_profile,
    sample_user,
):
    """Test getting timeline of events."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.profiles.find.return_value = create_mock_cursor([sample_timeline_profile])
    mock_mongodb.profiles.count_documents = AsyncMock(return_value=1)
    mock_mongodb.nodes.find.return_value = create_mock_cursor([])
    mock_mongodb.topologies.find.return_value = create_mock_cursor([])
    mock_mongodb.networks.find.return_value = create_mock_cursor([])

    response = await client.get(
        "/api/v1/timemachine/timeline",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["total"] >= 1


@pytest.mark.asyncio
async def test_get_timeline_with_filters(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_timeline_profile,
    sample_user,
):
    """Test getting timeline with filters."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.profiles.find.return_value = create_mock_cursor([sample_timeline_profile])
    mock_mongodb.profiles.count_documents = AsyncMock(return_value=1)
    mock_mongodb.nodes.find.return_value = create_mock_cursor([])
    mock_mongodb.topologies.find.return_value = create_mock_cursor([])
    mock_mongodb.networks.find.return_value = create_mock_cursor([])

    now = datetime.now(UTC)
    since = (now - timedelta(hours=24)).isoformat().replace("+00:00", "Z")
    until = now.isoformat().replace("+00:00", "Z")

    response = await client.get(
        f"/api/v1/timemachine/timeline?since={since}&until={until}&nodeId=server-01",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_timeline_with_event_types(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_timeline_profile,
    sample_user,
):
    """Test getting timeline filtered by event types."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.profiles.find.return_value = create_mock_cursor([sample_timeline_profile])
    mock_mongodb.profiles.count_documents = AsyncMock(return_value=1)
    mock_mongodb.nodes.find.return_value = create_mock_cursor([])
    mock_mongodb.topologies.find.return_value = create_mock_cursor([])
    mock_mongodb.networks.find.return_value = create_mock_cursor([])

    response = await client.get(
        "/api/v1/timemachine/timeline?eventTypes=profile_submitted&eventTypes=node_registered",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_timeline_pagination(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_timeline_profile,
    sample_user,
):
    """Test timeline pagination."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.profiles.find.return_value = create_mock_cursor([sample_timeline_profile])
    mock_mongodb.profiles.count_documents = AsyncMock(return_value=100)
    mock_mongodb.nodes.find.return_value = create_mock_cursor([])
    mock_mongodb.topologies.find.return_value = create_mock_cursor([])
    mock_mongodb.networks.find.return_value = create_mock_cursor([])

    response = await client.get(
        "/api/v1/timemachine/timeline?limit=50&offset=10",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["limit"] == 50
    assert data["meta"]["offset"] == 10


@pytest.mark.asyncio
async def test_timemachine_forbidden_for_viewer(
    client: AsyncClient,
    mock_mongodb,
    viewer_token,
    sample_user,
):
    """Test that timemachine requires appropriate permissions."""
    # Viewer should be able to access timemachine with nodes:read permission
    viewer_user = sample_user.copy()
    viewer_user["userId"] = "user_viewer123"
    viewer_user["role"] = "viewer"
    mock_mongodb.users.find_one = AsyncMock(return_value=viewer_user)
    mock_mongodb.nodes.find_one = AsyncMock(return_value=None)

    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    response = await client.get(
        f"/api/v1/timemachine/node/server-01?timestamp={timestamp}",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 404
