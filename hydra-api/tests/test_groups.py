"""Tests for group management endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from tests.utils import create_mock_cursor


@pytest.fixture
def sample_group():
    """Sample group document."""
    now = datetime.now(timezone.utc)
    return {
        "groupId": "grp-production",
        "name": "Production",
        "description": "Production infrastructure group",
        "types": ["node", "service"],
        "selectors": {
            "tags": {"isAny": ["production"]},
            "kind": {"isAny": ["compute"]},
        },
        "parentGroupIds": [],
        "tags": ["critical", "monitored"],
        "memberCount": {"nodes": 5, "services": 15, "lastComputed": now},
        "createdAt": now,
        "updatedAt": now,
    }


@pytest.mark.asyncio
async def test_list_groups_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_group,
    sample_user,
):
    """Test listing groups."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.groups.count_documents = AsyncMock(return_value=1)
    mock_mongodb.groups.find.return_value = create_mock_cursor([sample_group])

    response = await client.get(
        "/api/v1/groups",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert len(data["data"]) == 1
    assert data["data"][0]["groupId"] == sample_group["groupId"]
    assert data["meta"]["total"] == 1


@pytest.mark.asyncio
async def test_list_groups_with_filters(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_group,
    sample_user,
):
    """Test listing groups with filters."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.groups.count_documents = AsyncMock(return_value=1)
    mock_mongodb.groups.find.return_value = create_mock_cursor([sample_group])

    response = await client.get(
        "/api/v1/groups?types=node&types=service",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1


@pytest.mark.asyncio
async def test_list_groups_with_search(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_group,
    sample_user,
):
    """Test listing groups with search filter."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.groups.count_documents = AsyncMock(return_value=1)
    mock_mongodb.groups.find.return_value = create_mock_cursor([sample_group])

    response = await client.get(
        "/api/v1/groups?search=production",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1


@pytest.mark.asyncio
async def test_create_group_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_group,
    sample_user,
):
    """Test creating a new group."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.groups.insert_one = AsyncMock()

    created_group = sample_group.copy()
    created_group["groupId"] = "grp-test-group"
    created_group["name"] = "Test Group"

    # Service may call find_one multiple times: existence check, then fetch after create
    mock_mongodb.groups.find_one = AsyncMock(side_effect=[None, None, created_group, created_group])

    response = await client.post(
        "/api/v1/groups",
        json={
            "groupId": "grp-test-group",
            "name": "Test Group",
            "description": "A test group",
            "types": ["node"],
            "selectors": {"tags": {"isAny": ["test"]}},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["data"]["groupId"] == "grp-test-group"


@pytest.mark.asyncio
async def test_get_group_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_group,
    sample_user,
):
    """Test getting a single group."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.groups.find_one = AsyncMock(return_value=sample_group)

    response = await client.get(
        f"/api/v1/groups/{sample_group['groupId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["groupId"] == sample_group["groupId"]
    assert data["data"]["name"] == "Production"


@pytest.mark.asyncio
async def test_get_group_not_found(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test getting a non-existent group."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.groups.find_one = AsyncMock(return_value=None)

    response = await client.get(
        "/api/v1/groups/grp-nonexistent",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "GROUP_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_group_with_resolved_members(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_group,
    sample_user,
):
    """Test getting a group with resolved members."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    group_with_members = sample_group.copy()
    group_with_members["resolvedMembers"] = {
        "nodes": [{"nodeId": "server-01", "displayName": "Server 01"}],
        "services": [],
    }
    mock_mongodb.groups.find_one = AsyncMock(return_value=group_with_members)
    mock_mongodb.nodes.find.return_value = create_mock_cursor([])
    mock_mongodb.services.find.return_value = create_mock_cursor([])

    response = await client.get(
        f"/api/v1/groups/{sample_group['groupId']}?resolveMembers=true&memberLimit=10",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_group_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_group,
    sample_user,
):
    """Test updating a group."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    updated_group = sample_group.copy()
    updated_group["name"] = "Updated Group"
    updated_group["description"] = "Updated description"

    mock_mongodb.groups.find_one = AsyncMock(side_effect=[sample_group, updated_group])
    mock_mongodb.groups.update_one = AsyncMock(return_value=MagicMock(modified_count=1))

    response = await client.patch(
        f"/api/v1/groups/{sample_group['groupId']}",
        json={
            "name": "Updated Group",
            "description": "Updated description",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["name"] == "Updated Group"


@pytest.mark.asyncio
async def test_delete_group_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_group,
    sample_user,
):
    """Test deleting a group."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.groups.find_one = AsyncMock(return_value=sample_group)
    mock_mongodb.groups.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))
    mock_mongodb.audit_log.insert_one = AsyncMock()

    response = await client.delete(
        f"/api/v1/groups/{sample_group['groupId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_group_members(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_group,
    sample_user,
    sample_node,
):
    """Test getting group members."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.groups.find_one = AsyncMock(return_value=sample_group)
    mock_mongodb.nodes.find.return_value = create_mock_cursor([sample_node])
    mock_mongodb.nodes.count_documents = AsyncMock(return_value=1)
    mock_mongodb.services.find.return_value = create_mock_cursor([])
    mock_mongodb.services.count_documents = AsyncMock(return_value=0)

    response = await client.get(
        f"/api/v1/groups/{sample_group['groupId']}/members",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "data" in data


@pytest.mark.asyncio
async def test_get_group_members_filtered(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_group,
    sample_user,
    sample_node,
):
    """Test getting group members filtered by entity type."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.groups.find_one = AsyncMock(return_value=sample_group)
    mock_mongodb.nodes.find.return_value = create_mock_cursor([sample_node])
    mock_mongodb.nodes.count_documents = AsyncMock(return_value=1)

    response = await client.get(
        f"/api/v1/groups/{sample_group['groupId']}/members?entityType=node",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_resolve_group(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_group,
    sample_user,
):
    """Test force resolving group membership."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.groups.find_one = AsyncMock(return_value=sample_group)
    mock_mongodb.groups.update_one = AsyncMock()
    mock_mongodb.nodes.count_documents = AsyncMock(return_value=5)
    mock_mongodb.services.count_documents = AsyncMock(return_value=15)

    response = await client.post(
        f"/api/v1/groups/{sample_group['groupId']}/resolve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_groups_forbidden_for_viewer_create(
    client: AsyncClient,
    mock_mongodb,
    viewer_token,
    sample_user,
):
    """Test that viewer cannot create groups."""
    viewer_user = sample_user.copy()
    viewer_user["userId"] = "user_viewer123"
    viewer_user["role"] = "viewer"
    mock_mongodb.users.find_one = AsyncMock(return_value=viewer_user)

    response = await client.post(
        "/api/v1/groups",
        json={
            "groupId": "grp-test-group",
            "name": "Test Group",
            "types": ["node"],
            "selectors": {"tags": {"isAny": ["test"]}},
        },
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_groups_forbidden_for_viewer_update(
    client: AsyncClient,
    mock_mongodb,
    viewer_token,
    sample_group,
    sample_user,
):
    """Test that viewer cannot update groups."""
    viewer_user = sample_user.copy()
    viewer_user["userId"] = "user_viewer123"
    viewer_user["role"] = "viewer"
    mock_mongodb.users.find_one = AsyncMock(return_value=viewer_user)

    response = await client.patch(
        f"/api/v1/groups/{sample_group['groupId']}",
        json={"name": "Should Fail"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_groups_forbidden_for_viewer_delete(
    client: AsyncClient,
    mock_mongodb,
    viewer_token,
    sample_group,
    sample_user,
):
    """Test that viewer cannot delete groups."""
    viewer_user = sample_user.copy()
    viewer_user["userId"] = "user_viewer123"
    viewer_user["role"] = "viewer"
    mock_mongodb.users.find_one = AsyncMock(return_value=viewer_user)

    response = await client.delete(
        f"/api/v1/groups/{sample_group['groupId']}",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_groups_pagination(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_group,
    sample_user,
):
    """Test groups pagination."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.groups.count_documents = AsyncMock(return_value=50)
    mock_mongodb.groups.find.return_value = create_mock_cursor([sample_group])

    response = await client.get(
        "/api/v1/groups?limit=10&offset=20",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total"] == 50
    assert data["meta"]["limit"] == 10
    assert data["meta"]["offset"] == 20


@pytest.mark.asyncio
async def test_list_groups_sorting(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_group,
    sample_user,
):
    """Test groups sorting."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.groups.count_documents = AsyncMock(return_value=1)
    mock_mongodb.groups.find.return_value = create_mock_cursor([sample_group])

    response = await client.get(
        "/api/v1/groups?sortBy=name&sortOrder=asc",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_groups_by_tags(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_group,
    sample_user,
):
    """Test filtering groups by tags."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.groups.count_documents = AsyncMock(return_value=1)
    mock_mongodb.groups.find.return_value = create_mock_cursor([sample_group])

    response = await client.get(
        "/api/v1/groups?tags=critical&tags=monitored",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1


@pytest.mark.asyncio
async def test_list_groups_by_parent(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_group,
    sample_user,
):
    """Test filtering groups by parent group ID."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.groups.count_documents = AsyncMock(return_value=1)
    mock_mongodb.groups.find.return_value = create_mock_cursor([sample_group])

    response = await client.get(
        "/api/v1/groups?parentGroupId=grp-parent",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
