"""Tests for dashboard Phase 2 Wave 1 additions.

Covers the spec-aligned endpoints and behaviors introduced in Wave 1:
- POST /dashboards/{boardId}/set-home
- PATCH /dashboards/{boardId} with operations
- GET /dashboards with ownerId filter
- GET /dashboards/{boardId}/export?format=yaml
- Board limits (max 25 boards per user, max 10 shared)
- Role-filtered widget registry
- Import validation warnings
- TTL / dashboard indexes
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml
from httpx import AsyncClient

from hydra.api.v1.core.security import create_access_token
from hydra.api.v1.main import app as v1_app
from hydra.api.v1.routers.dashboards import router as dashboards_router
from hydra.api.v1.services.dashboards import (
    MAX_BOARDS_PER_USER,
    MAX_SHARED_BOARDS_PER_USER,
    widget_registry,
)
from hydra.core.config import get_settings
from hydra.db.indexes import INDEXES
from tests.conftest import create_mock_collection
from tests.utils import create_mock_cursor

# Idempotent router registration
_registered = False
if not _registered:
    v1_app.include_router(dashboards_router)
    _registered = True


@pytest.fixture
def mock_dashboards_collection():
    return create_mock_collection()


@pytest.fixture
def mock_templates_collection():
    return create_mock_collection()


@pytest.fixture(autouse=True)
def _patch_dashboard_collections(
    mock_mongodb, mock_dashboards_collection, mock_templates_collection
):
    collections = {
        "dashboards": mock_dashboards_collection,
        "dashboard_templates": mock_templates_collection,
    }
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(side_effect=lambda key: collections[key])
    mock_mongodb.db = mock_db


@pytest.fixture
def sample_board():
    now = datetime.now(UTC)
    return {
        "boardId": "board_wave1test1",
        "name": "Wave1 Board",
        "description": "Wave 1 test fixture",
        "icon": "server",
        "ownerId": "user_admin123",
        "ownerType": "user",
        "boardType": "user",
        "visibility": {"scope": "private", "sharedWith": {"roles": [], "users": []}},
        "layout": {
            "columns": 12,
            "rowHeight": 80,
            "breakpoints": {
                "xl": {"columns": 12, "width": 1536},
                "lg": {"columns": 12, "width": 1200},
                "md": {"columns": 8, "width": 996},
                "sm": {"columns": 4, "width": 480},
                "xs": {"columns": 2, "width": 0},
            },
        },
        "widgets": [
            {
                "instanceId": "wi_wave1aa",
                "widgetType": "hydra::stats-cards",
                "position": {"x": 0, "y": 0, "w": 12, "h": 2},
                "config": {},
                "dataBinding": None,
            }
        ],
        "settings": {
            "theme": "inherit",
            "autoRefresh": True,
            "refreshInterval": 30,
            "showHeader": True,
            "kioskMode": False,
            "kioskAutoScroll": False,
            "kioskScrollSpeed": 30,
            "backgroundImage": None,
            "customCss": None,
        },
        "tags": [],
        "isHome": False,
        "version": 1,
        "clonedFrom": None,
        "createdAt": now,
        "updatedAt": now,
        "archivedAt": None,
    }


# ── Set Home ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_set_home_board_clears_previous(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """POST /dashboards/{boardId}/set-home flips isHome and clears the previous."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    new_home = {**sample_board, "isHome": True, "version": 2}
    # _get_visible_board, update_many for clearing, update_one for setting,
    # then get_board_for_user.
    mock_dashboards_collection.find_one = AsyncMock(
        side_effect=[sample_board, new_home]
    )
    mock_dashboards_collection.update_many = AsyncMock()
    mock_dashboards_collection.update_one = AsyncMock()

    response = await client.post(
        f"/api/v1/dashboards/{sample_board['boardId']}/set-home",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["isHome"] is True
    mock_dashboards_collection.update_many.assert_awaited_once()
    mock_dashboards_collection.update_one.assert_awaited_once()


# ── PATCH operations ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_patch_update_settings_operation(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """PATCH with update-settings replaces the settings object."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    updated = {
        **sample_board,
        "version": 2,
        "settings": {
            **sample_board["settings"],
            "kioskMode": True,
            "kioskAutoScroll": True,
            "customCss": "body { background: #000; }",
        },
    }
    mock_dashboards_collection.find_one = AsyncMock(
        side_effect=[sample_board, updated]
    )
    mock_dashboards_collection.update_one = AsyncMock()

    response = await client.patch(
        f"/api/v1/dashboards/{sample_board['boardId']}",
        json={
            "operations": [
                {
                    "op": "update-settings",
                    "settings": {
                        "theme": "inherit",
                        "autoRefresh": True,
                        "refreshInterval": 30,
                        "showHeader": True,
                        "kioskMode": True,
                        "kioskAutoScroll": True,
                        "kioskScrollSpeed": 30,
                        "backgroundImage": None,
                        "customCss": "body { background: #000; }",
                    },
                }
            ]
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["settings"]["kioskMode"] is True
    assert data["settings"]["customCss"] == "body { background: #000; }"
    mock_dashboards_collection.update_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_patch_add_and_remove_widget(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """PATCH can add then remove a widget in one request."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    updated = {**sample_board, "version": 2}
    mock_dashboards_collection.find_one = AsyncMock(
        side_effect=[sample_board, updated]
    )
    mock_dashboards_collection.update_one = AsyncMock()

    existing_instance_id = sample_board["widgets"][0]["instanceId"]
    response = await client.patch(
        f"/api/v1/dashboards/{sample_board['boardId']}",
        json={
            "operations": [
                {
                    "op": "add-widget",
                    "widget": {
                        "widgetType": "hydra::clock",
                        "position": {"x": 0, "y": 3, "w": 3, "h": 2},
                        "config": {"timezone": "Europe/London"},
                    },
                },
                {"op": "remove-widget", "instanceId": existing_instance_id},
            ]
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    mock_dashboards_collection.update_one.assert_awaited_once()
    call = mock_dashboards_collection.update_one.call_args
    set_fields = call[0][1]["$set"]
    # After add + remove the widgets list should contain exactly 1 widget (clock)
    assert len(set_fields["widgets"]) == 1
    assert set_fields["widgets"][0]["widgetType"] == "hydra::clock"


@pytest.mark.asyncio
async def test_patch_remove_unknown_widget_returns_404(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """PATCH remove-widget with missing instanceId returns 404."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.find_one = AsyncMock(return_value=sample_board)

    response = await client.patch(
        f"/api/v1/dashboards/{sample_board['boardId']}",
        json={
            "operations": [
                {"op": "remove-widget", "instanceId": "wi_nonexistent"},
            ]
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 404


# ── List boards with ownerId filter ─────────────────────────────────


@pytest.mark.asyncio
async def test_list_dashboards_with_owner_id_filter(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """GET /dashboards?ownerId=... includes ownerId in the Mongo filter."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.count_documents = AsyncMock(return_value=1)
    mock_dashboards_collection.find.return_value = create_mock_cursor([sample_board])

    response = await client.get(
        "/api/v1/dashboards",
        params={"ownerId": "user_other456"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200

    filter_query = mock_dashboards_collection.count_documents.call_args[0][0]
    assert filter_query["ownerId"] == "user_other456"


# ── YAML export ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_export_board_yaml(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """GET /dashboards/{boardId}/export?format=yaml returns YAML content."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.find_one = AsyncMock(return_value=sample_board)

    response = await client.get(
        f"/api/v1/dashboards/{sample_board['boardId']}/export",
        params={"format": "yaml"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/yaml")
    parsed = yaml.safe_load(response.text)
    assert parsed["name"] == sample_board["name"]
    assert parsed["boardType"] == "user"
    assert parsed["exportVersion"] == 1


# ── Board limits ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_board_rejects_when_limit_reached(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
):
    """Creating a board when the user already has MAX_BOARDS_PER_USER fails."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.count_documents = AsyncMock(
        return_value=MAX_BOARDS_PER_USER
    )

    response = await client.post(
        "/api/v1/dashboards",
        json={
            "name": "Over The Limit",
            "boardType": "user",
            "visibility": {"scope": "private", "sharedWith": {"roles": [], "users": []}},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "Maximum board count" in body["error"]["message"]


@pytest.mark.asyncio
async def test_share_board_rejects_when_shared_limit_reached(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    sample_board,
):
    """Setting visibility to shared when MAX_SHARED_BOARDS_PER_USER is reached fails."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.find_one = AsyncMock(return_value=sample_board)
    mock_dashboards_collection.count_documents = AsyncMock(
        return_value=MAX_SHARED_BOARDS_PER_USER
    )

    response = await client.post(
        f"/api/v1/dashboards/{sample_board['boardId']}/share",
        json={
            "scope": "shared",
            "sharedWith": {"roles": ["viewer"], "users": []},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 400
    body = response.json()
    assert "Maximum shared board count" in body["error"]["message"]


# ── Role-filtered widget registry ──────────────────────────────────


@pytest.mark.asyncio
async def test_widget_registry_filtered_for_family_role(
    client: AsyncClient,
    mock_mongodb,
    sample_user,
):
    """The widget registry response is filtered by the authenticated user's role."""
    settings = get_settings()
    family_token = create_access_token(
        subject="user_family123",
        token_type="access",
        additional_claims={
            "sub_type": "user",
            "role": "family",
            "permissions": ["dashboards:read"],
        },
        settings=settings,
    )
    mock_mongodb.users.find_one = AsyncMock(
        return_value={
            **sample_user,
            "userId": "user_family123",
            "role": "family",
            "permissions": ["dashboards:read"],
        }
    )

    response = await client.get(
        "/api/v1/dashboards/widgets/registry",
        headers={"Authorization": f"Bearer {family_token}"},
    )
    assert response.status_code == 200
    data = response.json()["data"]

    # All returned widgets must permit the 'family' role
    for widget in data["widgets"]:
        assert "family" in widget["permissions"]["view"]


# ── Import validation warnings ─────────────────────────────────────


@pytest.mark.asyncio
async def test_import_board_surfaces_unknown_widget_warning(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
):
    """Importing a board with an unknown widget type yields a warning but still imports."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.insert_one = AsyncMock()

    payload = {
        "board": {
            "exportVersion": 1,
            "name": "With Unknown Widget",
            "boardType": "user",
            "layout": {"columns": 12, "rowHeight": 80, "breakpoints": {}},
            "widgets": [
                {
                    "widgetType": "hydra::stats-cards",
                    "position": {"x": 0, "y": 0, "w": 12, "h": 2},
                    "config": {},
                },
                {
                    "widgetType": "plg::docker::containers",
                    "position": {"x": 0, "y": 2, "w": 6, "h": 4},
                    "config": {},
                },
            ],
            "settings": {},
            "tags": [],
        }
    }

    response = await client.post(
        "/api/v1/dashboards/import",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    body = response.json()["data"]
    assert body["board"]["name"] == "With Unknown Widget"
    warnings = body["warnings"]
    assert len(warnings) == 1
    assert warnings[0]["code"] == "unknown_widget_type"
    assert warnings[0]["widgetIndex"] == 1


# ── Index registration ─────────────────────────────────────────────


def test_dashboard_indexes_registered():
    """The dashboards collection has the spec-aligned indexes including TTL."""
    index_models = INDEXES["dashboards"]
    rendered = [
        (list(model.document["key"].items()), model.document)
        for model in index_models
    ]

    # Unique boardId
    assert any(
        keys == [("boardId", 1)] and doc.get("unique") is True
        for keys, doc in rendered
    )
    # TTL on archivedAt
    assert any(
        keys == [("archivedAt", 1)] and doc.get("expireAfterSeconds") == 2592000
        for keys, doc in rendered
    )
    # Composite ownerId + boardType
    assert any(keys == [("ownerId", 1), ("boardType", 1)] for keys, _ in rendered)
    # Visibility scope + sharedWith roles
    assert any(
        keys == [("visibility.scope", 1), ("visibility.sharedWith.roles", 1)]
        for keys, _ in rendered
    )


def test_widget_registry_singleton_has_builtin_widgets():
    """Sanity check: the widget_registry singleton exposes the 12 built-in widgets."""
    all_widgets = widget_registry.list_all()
    assert len(all_widgets) >= 45
    widget_types = {w["widgetType"] for w in all_widgets}
    assert "hydra::stats-cards" in widget_types
    assert "hydra::mini-topology" in widget_types
