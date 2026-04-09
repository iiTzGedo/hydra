"""Tests for dashboard management endpoints."""

import re
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from hydra.api.v1.main import app as v1_app
from hydra.api.v1.routers.dashboards import router as dashboards_router
from tests.conftest import create_mock_collection
from tests.utils import create_mock_cursor

# Register the dashboards router on the v1 app so the test client can reach it.
# This is idempotent — FastAPI de-duplicates route objects if included multiple times.
_registered = False
if not _registered:
    v1_app.include_router(dashboards_router)
    _registered = True


@pytest.fixture
def mock_dashboards_collection():
    """Create a mock dashboards collection."""
    return create_mock_collection()


@pytest.fixture(autouse=True)
def _patch_dashboard_collection(mock_mongodb, mock_dashboards_collection):
    """Patch mock_mongodb.db to return the dashboards collection.

    The DashboardService accesses ``mongodb.db["dashboards"]`` so we need
    the mock db's __getitem__ to return our controlled mock collection.
    """
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_dashboards_collection)
    mock_mongodb.db = mock_db


@pytest.fixture
def sample_board():
    """Sample dashboard board document."""
    now = datetime.now(UTC)
    return {
        "boardId": "board_abc123def456",
        "name": "Infrastructure Overview",
        "description": "Main operational view",
        "icon": "server",
        "ownerId": "user_admin123",
        "boardType": "custom",
        "visibility": "private",
        "layout": {
            "columns": 12,
            "rowHeight": 80,
            "breakpoints": {
                "lg": {"columns": 12, "width": 1200},
                "md": {"columns": 8, "width": 996},
                "sm": {"columns": 4, "width": 768},
            },
        },
        "widgets": [
            {
                "instanceId": "wi_aabbccdd",
                "widgetType": "hydra::stats-cards",
                "position": {"x": 0, "y": 0, "w": 12, "h": 2},
                "config": {"title": "Node Count", "hidden": False},
                "dataBinding": {
                    "source": "hydra::nodes",
                    "query": {"class": "compute"},
                    "refreshInterval": 60,
                },
            }
        ],
        "settings": {
            "theme": "inherit",
            "autoRefresh": True,
            "refreshInterval": 30,
            "showHeader": True,
            "kioskMode": False,
        },
        "tags": ["infrastructure", "overview"],
        "isHome": True,
        "version": 1,
        "clonedFrom": None,
        "createdAt": now,
        "updatedAt": now,
        "archivedAt": None,
    }


@pytest.mark.asyncio
async def test_create_dashboard(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """Test creating a new dashboard board."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.insert_one = AsyncMock()

    # After insert, the service calls get_board which does find_one
    mock_dashboards_collection.find_one = AsyncMock(return_value=sample_board)

    response = await client.post(
        "/api/v1/dashboards",
        json={
            "name": "Infrastructure Overview",
            "description": "Main operational view",
            "boardType": "custom",
            "visibility": "private",
            "tags": ["infrastructure", "overview"],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert "data" in data
    assert data["data"]["name"] == "Infrastructure Overview"
    assert data["data"]["boardType"] == "custom"
    mock_dashboards_collection.insert_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_dashboards_owner_filtering(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """Test listing dashboards with owner filtering.

    Users should see their own boards plus shared/public boards.
    """
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.count_documents = AsyncMock(return_value=1)
    mock_dashboards_collection.find.return_value = create_mock_cursor([sample_board])

    response = await client.get(
        "/api/v1/dashboards",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert len(data["data"]) == 1
    assert data["data"][0]["boardId"] == sample_board["boardId"]
    assert data["meta"]["total"] == 1

    # Verify the filter includes owner + visibility conditions
    call_args = mock_dashboards_collection.count_documents.call_args
    filter_query = call_args[0][0]
    assert "archivedAt" in filter_query
    assert "$or" in filter_query


@pytest.mark.asyncio
async def test_get_dashboard(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """Test getting a single dashboard by ID."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.find_one = AsyncMock(return_value=sample_board)

    response = await client.get(
        f"/api/v1/dashboards/{sample_board['boardId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["boardId"] == sample_board["boardId"]
    assert data["data"]["name"] == "Infrastructure Overview"
    assert len(data["data"]["widgets"]) == 1
    assert data["data"]["widgets"][0]["widgetType"] == "hydra::stats-cards"


@pytest.mark.asyncio
async def test_get_dashboard_private_hidden_from_non_owner(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """Private dashboards should return 404 to non-owners."""
    private_other_board = {
        **sample_board,
        "ownerId": "user_other456",
        "visibility": "private",
    }
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.find_one = AsyncMock(return_value=None)

    response = await client.get(
        f"/api/v1/dashboards/{private_other_board['boardId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("visibility", ["shared", "public"])
async def test_get_dashboard_visible_to_non_owner(
    visibility: str,
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """Shared and public dashboards should be readable by non-owners."""
    visible_board = {
        **sample_board,
        "ownerId": "user_other456",
        "visibility": visibility,
    }
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.find_one = AsyncMock(return_value=visible_board)

    response = await client.get(
        f"/api/v1/dashboards/{visible_board['boardId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["boardId"] == visible_board["boardId"]
    assert data["visibility"] == visibility


@pytest.mark.asyncio
async def test_get_dashboard_not_found(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
):
    """Test getting a non-existent dashboard returns 404."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.find_one = AsyncMock(return_value=None)

    response = await client.get(
        "/api/v1/dashboards/board_nonexistent",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_dashboard(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """Test updating an existing dashboard."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    updated_board = {**sample_board, "name": "Updated Overview", "version": 2}

    # First find_one for ownership check, then find_one for get_board response
    mock_dashboards_collection.find_one = AsyncMock(
        side_effect=[sample_board, updated_board]
    )
    mock_dashboards_collection.update_one = AsyncMock()

    response = await client.put(
        f"/api/v1/dashboards/{sample_board['boardId']}",
        json={"name": "Updated Overview"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["name"] == "Updated Overview"
    mock_dashboards_collection.update_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_dashboard(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """Test soft deleting a dashboard."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.find_one = AsyncMock(return_value=sample_board)
    mock_dashboards_collection.update_one = AsyncMock()

    response = await client.delete(
        f"/api/v1/dashboards/{sample_board['boardId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["boardId"] == sample_board["boardId"]
    # Should have set archivedAt
    mock_dashboards_collection.update_one.assert_awaited_once()
    update_call = mock_dashboards_collection.update_one.call_args
    set_fields = update_call[0][1]["$set"]
    assert "archivedAt" in set_fields


@pytest.mark.asyncio
async def test_clone_dashboard(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """Test cloning a dashboard creates a new board with new IDs."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    _cloned_board = {
        **sample_board,
        "boardId": "board_newcloned123",
        "name": "My Cloned Board",
        "visibility": "private",
        "isHome": False,
        "version": 1,
        "clonedFrom": sample_board["boardId"],
    }

    # find_one for source lookup, then insert_one (no second find_one because
    # clone_board returns the formatted clone directly without re-fetching)
    mock_dashboards_collection.find_one = AsyncMock(return_value=sample_board)
    mock_dashboards_collection.insert_one = AsyncMock()

    response = await client.post(
        f"/api/v1/dashboards/{sample_board['boardId']}/clone",
        json={"name": "My Cloned Board"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["data"]["clonedFrom"] == sample_board["boardId"]
    assert data["data"]["visibility"] == "private"
    assert data["data"]["isHome"] is False
    mock_dashboards_collection.insert_one.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("visibility", ["shared", "public"])
async def test_clone_dashboard_visible_to_non_owner(
    visibility: str,
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """Shared and public dashboards should be cloneable by non-owners."""
    source_board = {
        **sample_board,
        "ownerId": "user_other456",
        "visibility": visibility,
    }
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.find_one = AsyncMock(return_value=source_board)
    mock_dashboards_collection.insert_one = AsyncMock()

    response = await client.post(
        f"/api/v1/dashboards/{source_board['boardId']}/clone",
        json={"name": f"{visibility.title()} Clone"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["clonedFrom"] == source_board["boardId"]
    assert data["visibility"] == "private"
    mock_dashboards_collection.insert_one.assert_awaited()


@pytest.mark.asyncio
async def test_add_widget_to_dashboard(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """Test adding a widget to a dashboard."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    board_with_new_widget = {
        **sample_board,
        "widgets": [
            *sample_board["widgets"],
            {
                "instanceId": "wi_newone00",
                "widgetType": "hydra::service-summary",
                "position": {"x": 0, "y": 2, "w": 6, "h": 4},
                "config": {"title": "Service Status"},
                "dataBinding": None,
            },
        ],
        "version": 2,
    }

    # find_one for ownership check, then find_one for get_board response
    mock_dashboards_collection.find_one = AsyncMock(
        side_effect=[sample_board, board_with_new_widget]
    )
    mock_dashboards_collection.update_one = AsyncMock()

    response = await client.post(
        f"/api/v1/dashboards/{sample_board['boardId']}/widgets",
        json={
            "widgetType": "hydra::service-summary",
            "position": {"x": 0, "y": 2, "w": 6, "h": 4},
            "config": {"title": "Service Status"},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert len(data["data"]["widgets"]) == 2
    assert data["data"]["widgets"][1]["widgetType"] == "hydra::service-summary"


@pytest.mark.asyncio
async def test_add_widget_rejects_duplicate_non_repeatable_type(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """Adding a non-repeatable widget type twice should fail."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.find_one = AsyncMock(return_value=sample_board)

    response = await client.post(
        f"/api/v1/dashboards/{sample_board['boardId']}/widgets",
        json={
            "widgetType": "hydra::stats-cards",
            "position": {"x": 0, "y": 2, "w": 12, "h": 2},
            "config": {"title": "Duplicate Stats"},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "can only be added once" in response.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_update_widget_on_dashboard(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """Test updating a widget on a dashboard."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    widget_id = sample_board["widgets"][0]["instanceId"]
    updated_board = {
        **sample_board,
        "widgets": [
            {
                **sample_board["widgets"][0],
                "config": {"title": "Updated Title", "color": "blue"},
            }
        ],
        "version": 2,
    }

    # find_one for ownership check, then find_one for get_board response
    mock_dashboards_collection.find_one = AsyncMock(
        side_effect=[sample_board, updated_board]
    )
    mock_dashboards_collection.update_one = AsyncMock()

    response = await client.put(
        f"/api/v1/dashboards/{sample_board['boardId']}/widgets/{widget_id}",
        json={
            "config": {"title": "Updated Title", "color": "blue"},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["widgets"][0]["config"]["title"] == "Updated Title"


@pytest.mark.asyncio
async def test_delete_widget_from_dashboard(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """Test removing a widget from a dashboard."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    widget_id = sample_board["widgets"][0]["instanceId"]
    board_after_removal = {**sample_board, "widgets": [], "version": 2}

    # find_one for ownership check, then find_one for get_board response
    mock_dashboards_collection.find_one = AsyncMock(
        side_effect=[sample_board, board_after_removal]
    )
    mock_dashboards_collection.update_one = AsyncMock()

    response = await client.delete(
        f"/api/v1/dashboards/{sample_board['boardId']}/widgets/{widget_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]["widgets"]) == 0


@pytest.mark.asyncio
async def test_dashboard_write_requires_permission(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    sample_user,
    test_settings,
):
    """Test that dashboard write endpoints require dashboards:write.

    A family-role user has dashboards:read but NOT dashboards:write,
    so creating a dashboard should be denied.
    """
    from hydra.api.v1.core.security import create_access_token
    from hydra.core.config import get_settings

    settings = get_settings()
    family_token = create_access_token(
        subject="user_family123",
        token_type="access",
        additional_claims={
            "sub_type": "user",
            "role": "family",
            "permissions": [
                "iot:read", "iot:control", "ha:read", "ha:control",
                "dashboards:read",
            ],
        },
        settings=settings,
    )

    mock_mongodb.users.find_one = AsyncMock(
        return_value={
            **sample_user,
            "userId": "user_family123",
            "role": "family",
            "permissions": [],
        }
    )

    response = await client.post(
        "/api/v1/dashboards",
        json={
            "name": "Family Board",
            "boardType": "custom",
            "visibility": "private",
        },
        headers={"Authorization": f"Bearer {family_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_dashboard_unauthenticated(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
):
    """Test that dashboard endpoints require authentication."""
    response = await client.get("/api/v1/dashboards")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_dashboard_wrong_owner(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """Test that a user cannot update a board they do not own."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    other_owners_board = {**sample_board, "ownerId": "user_other456"}
    mock_dashboards_collection.find_one = AsyncMock(return_value=other_owners_board)

    response = await client.put(
        f"/api/v1/dashboards/{sample_board['boardId']}",
        json={"name": "Hijacked Board"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_widget_registry(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
):
    """Registry returns all widget types with expected structure."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    response = await client.get(
        "/api/v1/dashboards/widgets/registry",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "data" in data

    registry = data["data"]
    assert registry["total"] == 6
    assert len(registry["widgets"]) == 6
    assert len(registry["categories"]) > 0

    # Verify widget structure
    first_widget = registry["widgets"][0]
    assert "widgetType" in first_widget
    assert "displayName" in first_widget
    assert "description" in first_widget
    assert "category" in first_widget
    assert "icon" in first_widget
    assert "source" in first_widget
    assert "defaultSize" in first_widget
    assert "minSize" in first_widget
    assert "maxSize" in first_widget
    assert "configSchema" in first_widget
    assert "capabilities" in first_widget

    # Verify size structure
    assert "w" in first_widget["defaultSize"]
    assert "h" in first_widget["defaultSize"]
    assert first_widget["capabilities"]["configurable"] is True
    assert first_widget["capabilities"]["repeatable"] is False

    # Verify category structure
    first_category = registry["categories"][0]
    assert "id" in first_category
    assert "name" in first_category
    assert "count" in first_category


@pytest.mark.asyncio
async def test_get_widget_registry_filter_by_category(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
):
    """Filter registry by category returns only matching widgets."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    response = await client.get(
        "/api/v1/dashboards/widgets/registry",
        params={"category": "status"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    registry = data["data"]

    # Only status widgets should be returned
    assert registry["total"] > 0
    for widget in registry["widgets"]:
        assert widget["category"] == "status"

    # Categories should still show all categories (full registry summary)
    assert len(registry["categories"]) > 1


@pytest.mark.asyncio
async def test_get_widget_registry_empty_category(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
):
    """Filter by non-existent category returns empty widgets list."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    response = await client.get(
        "/api/v1/dashboards/widgets/registry",
        params={"category": "nonexistent"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    registry = data["data"]
    assert registry["total"] == 0
    assert len(registry["widgets"]) == 0
    # Categories still show the full summary
    assert len(registry["categories"]) > 0


@pytest.mark.asyncio
async def test_search_escapes_regex_chars(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """Test that search queries with regex special characters are escaped.

    Prevents ReDoS and NoSQL regex injection by ensuring user-supplied search
    strings are passed through ``re.escape()`` before being used in MongoDB
    ``$regex`` queries.
    """
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.count_documents = AsyncMock(return_value=0)
    mock_dashboards_collection.find.return_value = create_mock_cursor([])

    # Use a search string containing regex special characters including a
    # pathological ReDoS pattern.
    dangerous_search = "(a+)+b.*"

    response = await client.get(
        "/api/v1/dashboards",
        params={"search": dangerous_search},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200

    # Verify the filter passed to count_documents uses the escaped string
    call_args = mock_dashboards_collection.count_documents.call_args
    filter_query = call_args[0][0]

    # The query should use $and to combine ownership and search filters
    assert "$and" in filter_query
    search_or = filter_query["$and"][1]["$or"]

    escaped = re.escape(dangerous_search)
    for condition in search_or:
        # Each condition is like {"name": {"$regex": ..., "$options": "i"}}
        field_key = next(iter(condition))
        regex_value = condition[field_key]["$regex"]
        assert regex_value == escaped, (
            f"Expected escaped regex {escaped!r} but got {regex_value!r}"
        )


# ── Template & Sharing & Export/Import Tests ───────────────────────


@pytest.fixture
def sample_template():
    """Sample dashboard template document."""
    now = datetime.now(UTC)
    return {
        "templateId": "tmpl_test123abc",
        "name": "Test Template",
        "description": "A test template",
        "boardType": "custom",
        "layout": {
            "columns": 12,
            "rowHeight": 80,
            "breakpoints": {
                "lg": {"columns": 12, "width": 1200},
                "md": {"columns": 8, "width": 996},
                "sm": {"columns": 4, "width": 768},
            },
        },
        "widgets": [
            {
                "widgetType": "hydra::stats-cards",
                "position": {"x": 0, "y": 0, "w": 12, "h": 2},
                "config": {},
                "dataBinding": None,
            },
            {
                "widgetType": "hydra::node-status-grid",
                "position": {"x": 0, "y": 2, "w": 12, "h": 4},
                "config": {},
                "dataBinding": None,
            },
        ],
        "settings": {
            "theme": "inherit",
            "autoRefresh": True,
            "refreshInterval": 30,
            "showHeader": True,
            "kioskMode": False,
        },
        "tags": ["infrastructure", "builtin"],
        "widgetCount": 2,
        "createdBy": "user_admin123",
        "createdAt": now,
        "updatedAt": now,
    }


@pytest.fixture
def mock_templates_collection():
    """Create a separate mock for the dashboard_templates collection."""
    return create_mock_collection()


@pytest.fixture(autouse=False)
def _patch_templates_collection(mock_mongodb, mock_templates_collection):
    """Patch mock_mongodb.db to also return the templates collection."""
    original_getitem = mock_mongodb.db.__getitem__

    def _getitem(key):
        if key == "dashboard_templates":
            return mock_templates_collection
        return original_getitem(key)

    mock_mongodb.db.__getitem__ = MagicMock(side_effect=_getitem)


@pytest.mark.asyncio
async def test_list_templates(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    mock_templates_collection,
    _patch_templates_collection,
    admin_token,
    sample_user,
    sample_template,
):
    """Test listing dashboard templates."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_templates_collection.count_documents = AsyncMock(return_value=1)
    mock_templates_collection.find.return_value = create_mock_cursor([sample_template])

    response = await client.get(
        "/api/v1/dashboards/templates",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert len(data["data"]) == 1
    assert data["data"][0]["templateId"] == sample_template["templateId"]
    assert data["data"][0]["name"] == "Test Template"
    assert data["meta"]["total"] == 1


@pytest.mark.asyncio
async def test_save_as_template(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    mock_templates_collection,
    _patch_templates_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """Test saving a board as a template. New templateId must start with 'tmpl_'."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.find_one = AsyncMock(return_value=sample_board)
    mock_templates_collection.insert_one = AsyncMock()

    response = await client.post(
        f"/api/v1/dashboards/{sample_board['boardId']}/save-as-template",
        json={"name": "My Template", "description": "Saved from board", "tags": ["test"]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["templateId"].startswith("tmpl_")
    assert data["name"] == "My Template"
    assert data["boardType"] == sample_board["boardType"]
    mock_templates_collection.insert_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_share_board(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """Test sharing a board updates visibility and allowedUsers."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.find_one = AsyncMock(return_value=sample_board)
    mock_dashboards_collection.update_one = AsyncMock()

    response = await client.post(
        f"/api/v1/dashboards/{sample_board['boardId']}/share",
        json={"visibility": "shared", "allowedUsers": ["user_viewer123"]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["visibility"] == "shared"
    assert "user_viewer123" in data["allowedUsers"]
    mock_dashboards_collection.update_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_revoke_shares(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """Test revoking shares resets visibility to private."""
    shared_board = {
        **sample_board,
        "visibility": "shared",
        "allowedUsers": ["user_viewer123"],
        "sharedWith": {"roles": ["viewer"], "users": ["user_viewer123"]},
    }
    revoked_board = {
        **sample_board,
        "visibility": "private",
        "allowedUsers": [],
        "sharedWith": {"roles": [], "users": []},
    }
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    # First find_one for ownership check, second for update_one, third for get_board_for_user
    mock_dashboards_collection.find_one = AsyncMock(
        side_effect=[shared_board, revoked_board]
    )
    mock_dashboards_collection.update_one = AsyncMock()

    response = await client.delete(
        f"/api/v1/dashboards/{sample_board['boardId']}/shares",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["visibility"] == "private"
    mock_dashboards_collection.update_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_export_board(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """Test exporting a board strips boardId, ownerId, and timestamps."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.find_one = AsyncMock(return_value=sample_board)

    response = await client.get(
        f"/api/v1/dashboards/{sample_board['boardId']}/export",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == sample_board["name"]
    assert data["boardType"] == sample_board["boardType"]
    # Exported data should NOT contain user-specific fields
    assert "boardId" not in data
    assert "ownerId" not in data
    assert "createdAt" not in data
    assert "updatedAt" not in data
    assert "archivedAt" not in data
    # Widgets should have instanceId stripped
    for widget in data.get("widgets", []):
        assert "instanceId" not in widget or widget.get("instanceId") is None


@pytest.mark.asyncio
async def test_import_board(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """Test importing a board generates new boardId and sets ownership."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.insert_one = AsyncMock()

    export_payload = {
        "board": {
            "exportVersion": 1,
            "name": "Imported Board",
            "description": "From export",
            "boardType": "custom",
            "layout": sample_board["layout"],
            "widgets": [
                {
                    "widgetType": "hydra::stats-cards",
                    "position": {"x": 0, "y": 0, "w": 12, "h": 2},
                    "config": {},
                }
            ],
            "settings": sample_board["settings"],
            "tags": ["imported"],
        }
    }

    response = await client.post(
        "/api/v1/dashboards/import",
        json=export_payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["boardId"].startswith("board_")
    assert data["name"] == "Imported Board"
    assert data["ownerId"] == "user_admin123"
    assert data["visibility"] == "private"
    mock_dashboards_collection.insert_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_export_import_roundtrip(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """Test that exporting a board and then importing preserves structure."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.find_one = AsyncMock(return_value=sample_board)

    # Export
    export_response = await client.get(
        f"/api/v1/dashboards/{sample_board['boardId']}/export",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert export_response.status_code == 200
    exported = export_response.json()["data"]

    # Import the exported data
    mock_dashboards_collection.insert_one = AsyncMock()

    import_response = await client.post(
        "/api/v1/dashboards/import",
        json={"board": exported, "name": "Re-imported"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert import_response.status_code == 201
    imported = import_response.json()["data"]
    assert imported["name"] == "Re-imported"
    assert imported["boardType"] == exported["boardType"]
    assert len(imported["widgets"]) == len(exported["widgets"])
    # Widget types should match
    imported_types = [w["widgetType"] for w in imported["widgets"]]
    exported_types = [w["widgetType"] for w in exported["widgets"]]
    assert imported_types == exported_types


@pytest.mark.asyncio
async def test_get_shares(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """Test getting share information for a board."""
    board_with_shares = {
        **sample_board,
        "sharedWith": {
            "roles": ["viewer", "operator"],
            "users": ["user_viewer123"],
        },
    }
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.find_one = AsyncMock(return_value=board_with_shares)

    response = await client.get(
        f"/api/v1/dashboards/{sample_board['boardId']}/shares",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert "viewer" in data["roles"]
    assert "operator" in data["roles"]
    assert "user_viewer123" in data["users"]
