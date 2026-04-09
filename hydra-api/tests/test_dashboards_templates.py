"""Tests for dashboard templates, sharing, and export/import endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from hydra.api.v1.main import app as v1_app
from hydra.api.v1.routers.dashboards import router as dashboards_router
from tests.conftest import create_mock_collection
from tests.utils import create_mock_cursor

# Register the dashboards router (idempotent)
_registered = False
if not _registered:
    v1_app.include_router(dashboards_router)
    _registered = True


@pytest.fixture
def mock_dashboards_collection():
    """Create a mock dashboards collection."""
    return create_mock_collection()


@pytest.fixture
def mock_templates_collection():
    """Create a mock dashboard_templates collection."""
    return create_mock_collection()


@pytest.fixture(autouse=True)
def _patch_dashboard_collections(
    mock_mongodb, mock_dashboards_collection, mock_templates_collection,
):
    """Patch mock_mongodb.db to return controlled mock collections."""
    collections = {
        "dashboards": mock_dashboards_collection,
        "dashboard_templates": mock_templates_collection,
    }
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(side_effect=lambda key: collections[key])
    mock_mongodb.db = mock_db


@pytest.fixture
def now():
    return datetime.now(UTC)


@pytest.fixture
def sample_board(now):
    """Sample dashboard board document."""
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
                "config": {"title": "Node Count"},
                "dataBinding": None,
            }
        ],
        "settings": {
            "theme": "inherit",
            "autoRefresh": True,
            "refreshInterval": 30,
            "showHeader": True,
            "kioskMode": False,
        },
        "tags": ["infrastructure"],
        "isHome": False,
        "version": 1,
        "clonedFrom": None,
        "createdAt": now,
        "updatedAt": now,
        "archivedAt": None,
    }


@pytest.fixture
def sample_template(now):
    """Sample dashboard template document."""
    return {
        "templateId": "tmpl_abc123def456",
        "name": "Ops Template",
        "description": "Standard operations dashboard",
        "boardType": "custom",
        "layout": {
            "columns": 12,
            "rowHeight": 80,
            "breakpoints": {},
        },
        "widgets": [
            {
                "widgetType": "hydra::stats-cards",
                "position": {"x": 0, "y": 0, "w": 12, "h": 2},
                "config": {"title": "Stats"},
                "dataBinding": None,
            }
        ],
        "settings": {"theme": "inherit"},
        "tags": ["operations"],
        "widgetCount": 1,
        "createdBy": "user_admin123",
        "sourceBoard": "board_abc123def456",
        "createdAt": now,
        "updatedAt": now,
    }


# ── Template Tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_save_as_template(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    mock_templates_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """Test saving a board as a template."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.find_one = AsyncMock(return_value=sample_board)
    mock_templates_collection.insert_one = AsyncMock()

    response = await client.post(
        "/api/v1/dashboards/board_abc123def456/save-as-template",
        json={"name": "My Template", "description": "A reusable layout", "tags": ["ops"]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["name"] == "My Template"
    assert data["description"] == "A reusable layout"
    assert data["boardType"] == "custom"
    assert data["widgetCount"] == 1
    assert "templateId" in data
    mock_templates_collection.insert_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_templates(
    client: AsyncClient,
    mock_mongodb,
    mock_templates_collection,
    admin_token,
    sample_user,
    sample_template,
):
    """Test listing dashboard templates."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_templates_collection.count_documents = AsyncMock(return_value=1)
    mock_templates_collection.find = MagicMock(
        return_value=create_mock_cursor([sample_template])
    )

    response = await client.get(
        "/api/v1/dashboards/templates",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == "Ops Template"
    assert data[0]["widgetCount"] == 1


@pytest.mark.asyncio
async def test_get_template(
    client: AsyncClient,
    mock_mongodb,
    mock_templates_collection,
    admin_token,
    sample_user,
    sample_template,
):
    """Test retrieving a single template."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_templates_collection.find_one = AsyncMock(return_value=sample_template)

    response = await client.get(
        "/api/v1/dashboards/templates/tmpl_abc123def456",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["templateId"] == "tmpl_abc123def456"
    assert data["name"] == "Ops Template"
    assert len(data["widgets"]) == 1


@pytest.mark.asyncio
async def test_get_template_not_found(
    client: AsyncClient,
    mock_mongodb,
    mock_templates_collection,
    admin_token,
    sample_user,
):
    """Test getting a non-existent template returns 404."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_templates_collection.find_one = AsyncMock(return_value=None)

    response = await client.get(
        "/api/v1/dashboards/templates/tmpl_nonexistent",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_instantiate_template(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    mock_templates_collection,
    admin_token,
    sample_user,
    sample_template,
):
    """Test creating a board from a template."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_templates_collection.find_one = AsyncMock(return_value=sample_template)
    mock_dashboards_collection.insert_one = AsyncMock()

    response = await client.post(
        "/api/v1/dashboards/templates/tmpl_abc123def456/instantiate",
        json={"name": "New From Template"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["name"] == "New From Template"
    assert data["boardType"] == "custom"
    assert data["visibility"] == "private"
    # Widgets should have fresh instance IDs
    assert len(data["widgets"]) == 1
    assert data["widgets"][0]["instanceId"] != ""
    mock_dashboards_collection.insert_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_instantiate_template_not_found(
    client: AsyncClient,
    mock_mongodb,
    mock_templates_collection,
    admin_token,
    sample_user,
):
    """Test instantiating a non-existent template returns 404."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_templates_collection.find_one = AsyncMock(return_value=None)

    response = await client.post(
        "/api/v1/dashboards/templates/tmpl_nonexistent/instantiate",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_template(
    client: AsyncClient,
    mock_mongodb,
    mock_templates_collection,
    admin_token,
    sample_user,
    sample_template,
):
    """Test deleting a template by its creator."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_templates_collection.find_one = AsyncMock(return_value=sample_template)
    mock_templates_collection.delete_one = AsyncMock()

    response = await client.delete(
        "/api/v1/dashboards/templates/tmpl_abc123def456",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["templateId"] == "tmpl_abc123def456"
    mock_templates_collection.delete_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_template_not_owner(
    client: AsyncClient,
    mock_mongodb,
    mock_templates_collection,
    admin_token,
    sample_user,
    sample_template,
):
    """Test deleting a template by non-creator returns 422."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_other999", "role": "admin"}
    )
    template = {**sample_template, "createdBy": "user_admin123"}
    mock_templates_collection.find_one = AsyncMock(return_value=template)

    response = await client.delete(
        "/api/v1/dashboards/templates/tmpl_abc123def456",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 400


# ── Sharing Tests ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_share_board_public(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """Test sharing a board with public visibility."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.find_one = AsyncMock(return_value=sample_board)
    mock_dashboards_collection.update_one = AsyncMock()

    response = await client.post(
        "/api/v1/dashboards/board_abc123def456/share",
        json={"visibility": "public", "allowedUsers": []},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["visibility"] == "public"
    assert data["allowedUsers"] == []
    mock_dashboards_collection.update_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_share_board_with_allowed_users(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """Test sharing a board with specific users."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.find_one = AsyncMock(return_value=sample_board)
    mock_dashboards_collection.update_one = AsyncMock()

    response = await client.post(
        "/api/v1/dashboards/board_abc123def456/share",
        json={"visibility": "shared", "allowedUsers": ["user_bob", "user_alice"]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["visibility"] == "shared"
    assert set(data["allowedUsers"]) == {"user_bob", "user_alice"}


@pytest.mark.asyncio
async def test_share_board_non_owner_rejected(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """Test that non-owner cannot share a board."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_other999", "role": "admin"}
    )
    board = {**sample_board, "ownerId": "user_admin123"}
    mock_dashboards_collection.find_one = AsyncMock(return_value=board)

    response = await client.post(
        "/api/v1/dashboards/board_abc123def456/share",
        json={"visibility": "public"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 400


# ── Export / Import Tests ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_export_board(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """Test exporting a board as portable JSON."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.find_one = AsyncMock(return_value=sample_board)

    response = await client.get(
        "/api/v1/dashboards/board_abc123def456/export",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["exportVersion"] == 1
    assert data["name"] == "Infrastructure Overview"
    assert data["boardType"] == "custom"
    # Widgets should have instanceId stripped (None) in export
    for widget in data["widgets"]:
        assert widget.get("instanceId") is None


@pytest.mark.asyncio
async def test_import_board(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
):
    """Test importing a board from exported JSON."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.insert_one = AsyncMock()

    export_data = {
        "exportVersion": 1,
        "name": "Imported Board",
        "description": "Imported from JSON",
        "boardType": "custom",
        "layout": {"columns": 12, "rowHeight": 80, "breakpoints": {}},
        "widgets": [
            {
                "widgetType": "hydra::stats-cards",
                "position": {"x": 0, "y": 0, "w": 12, "h": 2},
                "config": {},
            }
        ],
        "settings": {},
        "tags": ["imported"],
    }

    response = await client.post(
        "/api/v1/dashboards/import",
        json={"board": export_data},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["name"] == "Imported Board"
    assert data["visibility"] == "private"
    assert len(data["widgets"]) == 1
    assert data["widgets"][0]["instanceId"] != ""
    mock_dashboards_collection.insert_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_import_board_with_name_override(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
):
    """Test importing with a name override."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.insert_one = AsyncMock()

    export_data = {
        "exportVersion": 1,
        "name": "Original Name",
        "boardType": "custom",
        "layout": {"columns": 12, "rowHeight": 80, "breakpoints": {}},
        "widgets": [],
        "settings": {},
        "tags": [],
    }

    response = await client.post(
        "/api/v1/dashboards/import",
        json={"board": export_data, "name": "Renamed Import"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    assert response.json()["data"]["name"] == "Renamed Import"


@pytest.mark.asyncio
async def test_export_import_round_trip(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """Test that export + import preserves board structure."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.find_one = AsyncMock(return_value=sample_board)

    # Export
    export_resp = await client.get(
        "/api/v1/dashboards/board_abc123def456/export",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert export_resp.status_code == 200
    exported = export_resp.json()["data"]

    # Import the export
    mock_dashboards_collection.insert_one = AsyncMock()

    import_resp = await client.post(
        "/api/v1/dashboards/import",
        json={"board": exported},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert import_resp.status_code == 201
    imported = import_resp.json()["data"]

    # Structural parity
    assert imported["name"] == exported["name"]
    assert imported["boardType"] == exported["boardType"]
    assert len(imported["widgets"]) == len(exported["widgets"])
    for orig, imp in zip(exported["widgets"], imported["widgets"], strict=True):
        assert imp["widgetType"] == orig["widgetType"]
        assert imp["position"] == orig["position"]
