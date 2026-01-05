"""Tests for profile management endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from tests.utils import create_mock_cursor


@pytest.mark.asyncio
async def test_submit_profile_success(
    client: AsyncClient,
    mock_mongodb,
    agent_token,
    sample_node,
):
    """Test submitting a new profile."""
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)
    mock_mongodb.profile_meta.find_one = AsyncMock(return_value=None)  # No previous profile
    mock_mongodb.profiles.insert_one = AsyncMock()
    mock_mongodb.profile_meta.insert_one = AsyncMock()
    mock_mongodb.nodes.update_one = AsyncMock()

    now = datetime.now(timezone.utc)
    response = await client.post(
        "/api/v1/profiles",
        json={
            "nodeId": sample_node["nodeId"],
            "collectedAt": now.isoformat(),
            "agentVersion": "0.1.0",
            "collectionLevel": "neutral",
            "hardware": {
                "cpu": {
                    "model": "Intel Xeon",
                    "coresPhysical": 8,
                    "coresLogical": 16,
                },
                "memory": {"totalBytes": 34359738368},
                "gpus": [],
            },
            "network": {
                "hostname": "test-server",
                "interfaces": [
                    {
                        "name": "eth0",
                        "macAddress": "00:11:22:33:44:55",
                        "ipv4Addresses": ["192.168.1.100"],
                        "ipv6Addresses": [],
                        "state": "up",
                    }
                ],
                "dnsServers": ["8.8.8.8"],
            },
        },
        headers={"Authorization": f"Bearer {agent_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "profileId" in data["data"]
    assert data["data"]["version"] == "E0-0.0.0.1"  # First profile
    assert data["data"]["nodeId"] == sample_node["nodeId"]


@pytest.mark.asyncio
async def test_submit_profile_increments_version(
    client: AsyncClient,
    mock_mongodb,
    agent_token,
    sample_node,
):
    """Test that submitting a changed profile increments version."""
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)

    # Previous profile exists
    previous_meta = {
        "profileId": "prof_previous",
        "nodeId": sample_node["nodeId"],
        "version": "E0-0.0.0.5",
        "sectionFingerprints": {
            "hardware": ["abc123"],
            "network": ["def456"],
        },
        "profileHash": "old_hash",
    }
    mock_mongodb.profile_meta.find_one = AsyncMock(return_value=previous_meta)
    mock_mongodb.profiles.insert_one = AsyncMock()
    mock_mongodb.profile_meta.insert_one = AsyncMock()
    mock_mongodb.nodes.update_one = AsyncMock()

    now = datetime.now(timezone.utc)
    response = await client.post(
        "/api/v1/profiles",
        json={
            "nodeId": sample_node["nodeId"],
            "collectedAt": now.isoformat(),
            "agentVersion": "0.1.0",
            "hardware": {
                "cpu": {"model": "Different CPU", "coresPhysical": 4, "coresLogical": 8},
                "memory": {"totalBytes": 17179869184},  # Different memory
            },
        },
        headers={"Authorization": f"Bearer {agent_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    # Version should be higher than E0-0.0.0.5
    assert data["data"]["version"] > "E0-0.0.0.5"


@pytest.mark.asyncio
async def test_submit_profile_node_not_found(
    client: AsyncClient,
    mock_mongodb,
    agent_token,
):
    """Test submitting profile for non-existent node."""
    mock_mongodb.nodes.find_one = AsyncMock(return_value=None)

    now = datetime.now(timezone.utc)
    response = await client.post(
        "/api/v1/profiles",
        json={
            "nodeId": "non-existent-node",
            "collectedAt": now.isoformat(),
            "agentVersion": "0.1.0",
        },
        headers={"Authorization": f"Bearer {agent_token}"},
    )

    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "NODE_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_profile_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_profile,
    sample_user,
):
    """Test getting a profile by ID."""
    mock_mongodb.users.find_one = AsyncMock(return_value={**sample_user, "userId": "user_admin123", "role": "admin"})
    mock_mongodb.profiles.find_one = AsyncMock(return_value=sample_profile)

    response = await client.get(
        f"/api/v1/profiles/{sample_profile['profileId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["profileId"] == sample_profile["profileId"]
    assert data["data"]["version"] == sample_profile["version"]


@pytest.mark.asyncio
async def test_get_latest_profile(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_node,
    sample_profile,
    sample_user,
):
    """Test getting the latest profile for a node."""
    mock_mongodb.users.find_one = AsyncMock(return_value={**sample_user, "userId": "user_admin123", "role": "admin"})
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)
    mock_mongodb.profiles.find_one = AsyncMock(return_value=sample_profile)

    response = await client.get(
        f"/api/v1/nodes/{sample_node['nodeId']}/profiles/latest",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["profileId"] == sample_profile["profileId"]


@pytest.mark.asyncio
async def test_list_node_profiles(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_node,
    sample_profile,
    sample_user,
):
    """Test listing profiles for a node."""
    mock_mongodb.users.find_one = AsyncMock(return_value={**sample_user, "userId": "user_admin123", "role": "admin"})
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)
    mock_mongodb.profiles.count_documents = AsyncMock(return_value=3)

    # Create multiple profile summaries
    profiles = [
        {**sample_profile, "profileId": f"prof_{i}", "version": f"E0-0.0.0.{i}"}
        for i in range(3)
    ]

    mock_mongodb.profiles.find.return_value = create_mock_cursor(profiles)

    response = await client.get(
        f"/api/v1/nodes/{sample_node['nodeId']}/profiles",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 3
    assert data["meta"]["total"] == 3


@pytest.mark.asyncio
async def test_diff_profiles(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_node,
    sample_profile,
    sample_user,
):
    """Test comparing two profiles."""
    mock_mongodb.users.find_one = AsyncMock(return_value={**sample_user, "userId": "user_admin123", "role": "admin"})
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)

    # Create two profiles for comparison
    profile1 = {**sample_profile, "profileId": "prof_1", "version": "E0-0.0.0.1"}
    profile2 = {**sample_profile, "profileId": "prof_2", "version": "E0-0.0.0.2"}

    mock_cursor = create_mock_cursor([profile2, profile1])
    mock_cursor.to_list = AsyncMock(return_value=[profile2, profile1])
    mock_mongodb.profiles.find.return_value = mock_cursor

    # Mock metadata
    meta1 = {
        "profileId": "prof_1",
        "sectionFingerprints": {"hardware": ["abc"], "network": ["def"]},
    }
    meta2 = {
        "profileId": "prof_2",
        "sectionFingerprints": {"hardware": ["abc"], "network": ["xyz"]},  # network changed
    }
    mock_mongodb.profile_meta.find_one = AsyncMock(side_effect=[meta1, meta2])

    response = await client.get(
        f"/api/v1/nodes/{sample_node['nodeId']}/profiles/diff",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["fromVersion"] == "E0-0.0.0.1"
    assert data["data"]["toVersion"] == "E0-0.0.0.2"
    assert "network" in data["data"]["changedSections"]
