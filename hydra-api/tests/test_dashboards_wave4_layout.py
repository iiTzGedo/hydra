"""Tests for Wave 4 board model extensions."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from hydra.api.v1.main import app as v1_app
from hydra.api.v1.routers.dashboards import router as dashboards_router
from tests.conftest import create_mock_collection

# Idempotent router registration
_registered = False
if not _registered:
    v1_app.include_router(dashboards_router)
    _registered = True


pytestmark = pytest.mark.asyncio


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def mock_dashboards_collection():
    return create_mock_collection()


@pytest.fixture
def mock_templates_collection():
    return create_mock_collection()


@pytest.fixture
def mock_versions_collection():
    return create_mock_collection()


@pytest.fixture(autouse=True)
def _patch_dashboard_collections(
    mock_mongodb,
    mock_dashboards_collection,
    mock_templates_collection,
    mock_versions_collection,
):
    collections = {
        "dashboards": mock_dashboards_collection,
        "dashboard_templates": mock_templates_collection,
        "dashboard_versions": mock_versions_collection,
    }
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(side_effect=lambda key: collections[key])
    mock_mongodb.db = mock_db


@pytest.fixture
def async_client(client: AsyncClient) -> AsyncClient:
    """Alias for the standard test client; named async_client for clarity."""
    return client


@pytest.fixture
def admin_token_headers(admin_token: str) -> dict[str, str]:
    """Authorization headers for the admin test token."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def test_board():
    """Minimal board document fixture for Wave 4 layout tests."""
    now = datetime.now(UTC)
    return {
        "boardId": "board_wave4layout01",
        "name": "Wave4 Layout Board",
        "description": "Wave 4 layout test fixture",
        "icon": "server",
        "ownerId": "user_admin123",
        "ownerType": "user",
        "boardType": "user",
        "visibility": {"scope": "private", "sharedWith": {"roles": [], "users": []}},
        "layout": {
            "mode": "grid",
            "grid": {
                "columns": 12,
                "rowHeight": 80,
                "breakpoints": {
                    "xl": {"columns": 12, "width": 1536},
                    "lg": {"columns": 12, "width": 1200},
                    "md": {"columns": 8, "width": 996},
                    "sm": {"columns": 4, "width": 480},
                    "xs": {"columns": 2, "width": 0},
                },
                "compaction": "vertical",
                "margin": [16, 16],
                "padding": [0, 0],
            },
        },
        "layoutMode": "grid",
        "scope": "standalone",
        "entityTypeFilter": None,
        "widgets": [],
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


# ── Tests ─────────────────────────────────────────────────────────────


async def test_create_board_defaults_layoutmode_grid(
    async_client: AsyncClient,
    admin_token_headers,
    mock_mongodb,
    mock_dashboards_collection,
    sample_user,
):
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.count_documents = AsyncMock(return_value=0)

    created_doc: dict = {}

    async def _capture_insert(doc):
        created_doc.update(doc)

    mock_dashboards_collection.insert_one = AsyncMock(side_effect=_capture_insert)
    mock_dashboards_collection.find_one = AsyncMock(side_effect=lambda *_a, **_kw: created_doc)

    payload = {"name": "Test Board", "boardType": "user"}
    resp = await async_client.post(
        "/api/v1/dashboards", json=payload, headers=admin_token_headers
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["layoutMode"] == "grid"
    assert data["scope"] == "standalone"
    # entityTypeFilter is None — excluded by response_model_exclude_none
    assert data.get("entityTypeFilter") is None


async def test_create_board_accepts_freeform_layoutmode(
    async_client: AsyncClient,
    admin_token_headers,
    mock_mongodb,
    mock_dashboards_collection,
    sample_user,
):
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.count_documents = AsyncMock(return_value=0)

    created_doc: dict = {}

    async def _capture_insert(doc):
        created_doc.update(doc)

    mock_dashboards_collection.insert_one = AsyncMock(side_effect=_capture_insert)
    mock_dashboards_collection.find_one = AsyncMock(side_effect=lambda *_a, **_kw: created_doc)

    payload = {"name": "Freeform Board", "boardType": "user", "layoutMode": "freeform"}
    resp = await async_client.post(
        "/api/v1/dashboards", json=payload, headers=admin_token_headers
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["layoutMode"] == "freeform"


async def test_create_entity_panel_requires_entitytypefilter(
    async_client: AsyncClient,
    admin_token_headers,
    mock_mongodb,
    sample_user,
):
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    payload = {"name": "Bad Panel", "scope": "entity-panel"}  # missing filter
    resp = await async_client.post(
        "/api/v1/dashboards", json=payload, headers=admin_token_headers
    )
    # The app's custom RequestValidationError handler returns 400 (established project pattern).
    assert resp.status_code == 400


async def test_patch_layoutmode(
    async_client: AsyncClient,
    admin_token_headers,
    mock_mongodb,
    mock_dashboards_collection,
    sample_user,
    test_board,
):
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    updated = {**test_board, "layoutMode": "freeform", "version": 2}
    mock_dashboards_collection.find_one = AsyncMock(
        side_effect=[test_board, updated]
    )
    mock_dashboards_collection.update_one = AsyncMock()

    resp = await async_client.patch(
        f"/api/v1/dashboards/{test_board['boardId']}",
        json={"operations": [{"op": "update-settings", "value": {"layoutMode": "freeform"}}]},
        headers=admin_token_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["layoutMode"] == "freeform"


async def test_create_entity_panel_succeeds_with_filter(
    async_client: AsyncClient,
    admin_token_headers,
    mock_mongodb,
    mock_dashboards_collection,
    sample_user,
):
    """Happy path: valid entity-panel creation with entityTypeFilter succeeds."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.count_documents = AsyncMock(return_value=0)

    created_doc: dict = {}

    async def _capture_insert(doc):
        created_doc.update(doc)

    mock_dashboards_collection.insert_one = AsyncMock(side_effect=_capture_insert)
    mock_dashboards_collection.find_one = AsyncMock(side_effect=lambda *_a, **_kw: created_doc)

    payload = {
        "name": "Node Panel Test", "boardType": "user",
        "scope": "entity-panel", "entityTypeFilter": "node",
    }
    resp = await async_client.post(
        "/api/v1/dashboards", json=payload, headers=admin_token_headers
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["scope"] == "entity-panel"
    assert data["entityTypeFilter"] == "node"


async def test_patch_value_silently_filters_unknown_keys(
    async_client: AsyncClient,
    admin_token_headers,
    mock_mongodb,
    mock_dashboards_collection,
    sample_user,
    test_board,
):
    """Only keys in _ALLOWED_META_KEYS are applied; scope/entityTypeFilter are ignored."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    # After patch, layoutMode is "columns" but scope/entityTypeFilter remain unchanged.
    updated = {**test_board, "layoutMode": "columns", "version": 2}
    mock_dashboards_collection.find_one = AsyncMock(
        side_effect=[test_board, updated]
    )
    mock_dashboards_collection.update_one = AsyncMock()

    resp = await async_client.patch(
        f"/api/v1/dashboards/{test_board['boardId']}",
        json={"operations": [{"op": "update-settings", "value": {
            "layoutMode": "columns",
            "scope": "entity-panel",       # should be silently ignored
            "entityTypeFilter": "node",     # should be silently ignored
            "arbitrary_key": "ignored",     # should be silently ignored
        }}]},
        headers=admin_token_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["layoutMode"] == "columns"
    assert data["scope"] == "standalone"  # unchanged
    # entityTypeFilter is None — excluded by response_model_exclude_none
    assert data.get("entityTypeFilter") is None  # unchanged


async def test_patch_value_invalid_layout_mode_rejected(
    async_client: AsyncClient,
    admin_token_headers,
    mock_mongodb,
    mock_dashboards_collection,
    sample_user,
    test_board,
):
    """Invalid layoutMode value via PATCH value dict must be rejected with 400."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    # Service validates the value before writing; _get_owned_board is the only DB call.
    mock_dashboards_collection.find_one = AsyncMock(return_value=test_board)
    mock_dashboards_collection.update_one = AsyncMock()

    resp = await async_client.patch(
        f"/api/v1/dashboards/{test_board['boardId']}",
        json={"operations": [{"op": "update-settings", "value": {"layoutMode": "carousel"}}]},
        headers=admin_token_headers,
    )
    assert resp.status_code == 400, (
        f"Expected 400 for invalid layoutMode 'carousel', got {resp.status_code}: {resp.text}"
    )


async def test_patch_noop_update_settings_is_guarded(
    async_client: AsyncClient,
    admin_token_headers,
    mock_mongodb,
    mock_dashboards_collection,
    sample_user,
    test_board,
):
    """A no-op update-settings op (no settings, no value) should not bump version."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    initial_version = test_board["version"]
    # No-op path: _get_owned_board + get_board_for_user each call find_one once.
    mock_dashboards_collection.find_one = AsyncMock(
        side_effect=[test_board, test_board]
    )
    mock_dashboards_collection.update_one = AsyncMock()

    resp = await async_client.patch(
        f"/api/v1/dashboards/{test_board['boardId']}",
        json={"operations": [{"op": "update-settings"}]},
        headers=admin_token_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    # Version should NOT have been bumped
    assert data["version"] == initial_version


async def test_update_board_put_persists_layoutmode(
    async_client: AsyncClient,
    admin_token_headers,
    mock_mongodb,
    mock_dashboards_collection,
    sample_user,
    test_board,
):
    """PUT /dashboards/{id} with layoutMode in body actually persists it."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    # After PUT, the board has layoutMode "freeform".
    updated = {**test_board, "layoutMode": "freeform", "version": 2}
    # Calls: _get_owned_board (PUT), get_board_for_user (PUT response), get_board_for_user (GET).
    mock_dashboards_collection.find_one = AsyncMock(
        side_effect=[test_board, updated, updated]
    )
    mock_dashboards_collection.update_one = AsyncMock()
    mock_dashboards_collection.update_many = AsyncMock()

    resp = await async_client.put(
        f"/api/v1/dashboards/{test_board['boardId']}",
        json={"layoutMode": "freeform"},
        headers=admin_token_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["layoutMode"] == "freeform"
    # Verify update_one was called (the field was written)
    mock_dashboards_collection.update_one.assert_called_once()
    # Confirm layoutMode was in the $set payload
    call_args = mock_dashboards_collection.update_one.call_args
    set_doc = call_args[0][1]["$set"]
    assert set_doc.get("layoutMode") == "freeform"
    # Also verify via GET
    get = await async_client.get(
        f"/api/v1/dashboards/{test_board['boardId']}",
        headers=admin_token_headers,
    )
    assert get.json()["data"]["layoutMode"] == "freeform"


async def test_widget_accepts_freeform_position(
    async_client: AsyncClient,
    admin_token_headers,
    mock_mongodb,
    mock_dashboards_collection,
    mock_versions_collection,
    sample_user,
    test_board,
):
    """Widget added via PATCH add-widget stores and returns freeformPosition."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    # After the PATCH, the board contains the added widget with freeformPosition.
    added_widget = {
        "instanceId": "wi_abc12345",
        "widgetType": "hydra::clock",
        "config": {},
        "placements": {"lg": {"x": 0, "y": 0, "w": 2, "h": 2}},
        "freeformPosition": {"x": 120, "y": 240, "w": 280, "h": 180},
        "dataBinding": None,
    }
    board_after = {**test_board, "widgets": [added_widget], "version": 2}

    # First call: _get_owned_board; second call: get_board_for_user after patch.
    mock_dashboards_collection.find_one = AsyncMock(side_effect=[test_board, board_after])
    mock_dashboards_collection.update_one = AsyncMock()
    mock_versions_collection.insert_one = AsyncMock()

    widget = {
        "widgetType": "hydra::clock",
        "config": {},
        "placements": {"lg": {"x": 0, "y": 0, "w": 2, "h": 2}},
        "freeformPosition": {"x": 120, "y": 240, "w": 280, "h": 180},
    }
    resp = await async_client.patch(
        f"/api/v1/dashboards/{test_board['boardId']}",
        json={"operations": [{"op": "add-widget", "widget": widget}]},
        headers=admin_token_headers,
    )
    assert resp.status_code == 200, resp.text
    widgets = resp.json()["data"]["widgets"]
    added = next(w for w in widgets if w["widgetType"] == "hydra::clock")
    assert added["freeformPosition"] == {"x": 120.0, "y": 240.0, "w": 280.0, "h": 180.0}

    # Verify the field was stored in Mongo $set payload.
    call_args = mock_dashboards_collection.update_one.call_args
    set_doc = call_args[0][1]["$set"]
    stored_widget = next(w for w in set_doc["widgets"] if w.get("widgetType") == "hydra::clock")
    assert stored_widget.get("freeformPosition") == {"x": 120.0, "y": 240.0, "w": 280.0, "h": 180.0}


async def test_widget_freeform_position_defaults_to_null(
    async_client: AsyncClient,
    admin_token_headers,
    mock_mongodb,
    mock_dashboards_collection,
    mock_versions_collection,
    sample_user,
    test_board,
):
    """Widget added without freeformPosition should have it as null/absent in response."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    added_widget = {
        "instanceId": "wi_def67890",
        "widgetType": "hydra::clock",
        "config": {},
        "placements": {"lg": {"x": 0, "y": 0, "w": 2, "h": 2}},
        "dataBinding": None,
    }
    board_after = {**test_board, "widgets": [added_widget], "version": 2}

    mock_dashboards_collection.find_one = AsyncMock(side_effect=[test_board, board_after])
    mock_dashboards_collection.update_one = AsyncMock()
    mock_versions_collection.insert_one = AsyncMock()

    widget = {
        "widgetType": "hydra::clock",
        "config": {},
        "placements": {"lg": {"x": 0, "y": 0, "w": 2, "h": 2}},
    }
    resp = await async_client.patch(
        f"/api/v1/dashboards/{test_board['boardId']}",
        json={"operations": [{"op": "add-widget", "widget": widget}]},
        headers=admin_token_headers,
    )
    assert resp.status_code == 200, resp.text
    added = next(w for w in resp.json()["data"]["widgets"] if w["widgetType"] == "hydra::clock")
    # freeformPosition absent from stored doc → should be null or absent in response
    assert added.get("freeformPosition") is None


async def test_freeform_position_validation_rejects_out_of_range(
    async_client: AsyncClient,
    admin_token_headers,
    mock_mongodb,
    mock_dashboards_collection,
    sample_user,
    test_board,
):
    """freeformPosition with values outside allowed ranges must be rejected (400)."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.find_one = AsyncMock(return_value=test_board)

    # w=40 is below the minimum of 80.
    widget_tiny_w = {
        "widgetType": "hydra::clock",
        "config": {},
        "placements": {"lg": {"x": 0, "y": 0, "w": 2, "h": 2}},
        "freeformPosition": {"x": 0, "y": 0, "w": 40, "h": 100},
    }
    resp = await async_client.patch(
        f"/api/v1/dashboards/{test_board['boardId']}",
        json={"operations": [{"op": "add-widget", "widget": widget_tiny_w}]},
        headers=admin_token_headers,
    )
    assert resp.status_code == 400, f"Expected 400 for w<80, got {resp.status_code}: {resp.text}"

    # h=10 is below the minimum of 60.
    widget_tiny_h = {
        "widgetType": "hydra::clock",
        "config": {},
        "placements": {"lg": {"x": 0, "y": 0, "w": 2, "h": 2}},
        "freeformPosition": {"x": 0, "y": 0, "w": 200, "h": 10},
    }
    resp2 = await async_client.patch(
        f"/api/v1/dashboards/{test_board['boardId']}",
        json={"operations": [{"op": "add-widget", "widget": widget_tiny_h}]},
        headers=admin_token_headers,
    )
    assert resp2.status_code == 400, f"Expected 400 for h<60, got {resp2.status_code}: {resp2.text}"

    # x=99999 is above the maximum of 10000.
    widget_huge_x = {
        "widgetType": "hydra::clock",
        "config": {},
        "placements": {"lg": {"x": 0, "y": 0, "w": 2, "h": 2}},
        "freeformPosition": {"x": 99999, "y": 0, "w": 200, "h": 100},
    }
    resp3 = await async_client.patch(
        f"/api/v1/dashboards/{test_board['boardId']}",
        json={"operations": [{"op": "add-widget", "widget": widget_huge_x}]},
        headers=admin_token_headers,
    )
    assert resp3.status_code == 400, f"Expected 400 for x>10000, got {resp3.status_code}: {resp3.text}"

    # y=99999 is above the maximum of 10000.
    widget_huge_y = {
        "widgetType": "hydra::clock",
        "config": {},
        "placements": {"lg": {"x": 0, "y": 0, "w": 2, "h": 2}},
        "freeformPosition": {"x": 0, "y": 99999, "w": 200, "h": 100},
    }
    resp4 = await async_client.patch(
        f"/api/v1/dashboards/{test_board['boardId']}",
        json={"operations": [{"op": "add-widget", "widget": widget_huge_y}]},
        headers=admin_token_headers,
    )
    assert resp4.status_code == 400, f"Expected 400 for y>10000, got {resp4.status_code}: {resp4.text}"

    # w=9999 is above the maximum of 2000.
    widget_huge_w = {
        "widgetType": "hydra::clock",
        "config": {},
        "placements": {"lg": {"x": 0, "y": 0, "w": 2, "h": 2}},
        "freeformPosition": {"x": 0, "y": 0, "w": 9999, "h": 100},
    }
    resp5 = await async_client.patch(
        f"/api/v1/dashboards/{test_board['boardId']}",
        json={"operations": [{"op": "add-widget", "widget": widget_huge_w}]},
        headers=admin_token_headers,
    )
    assert resp5.status_code == 400, f"Expected 400 for w>2000, got {resp5.status_code}: {resp5.text}"

    # h=9999 is above the maximum of 2000.
    widget_huge_h = {
        "widgetType": "hydra::clock",
        "config": {},
        "placements": {"lg": {"x": 0, "y": 0, "w": 2, "h": 2}},
        "freeformPosition": {"x": 0, "y": 0, "w": 200, "h": 9999},
    }
    resp6 = await async_client.patch(
        f"/api/v1/dashboards/{test_board['boardId']}",
        json={"operations": [{"op": "add-widget", "widget": widget_huge_h}]},
        headers=admin_token_headers,
    )
    assert resp6.status_code == 400, f"Expected 400 for h>2000, got {resp6.status_code}: {resp6.text}"

    # x=-1 is below the minimum of 0.
    widget_neg_x = {
        "widgetType": "hydra::clock",
        "config": {},
        "placements": {"lg": {"x": 0, "y": 0, "w": 2, "h": 2}},
        "freeformPosition": {"x": -1, "y": 0, "w": 200, "h": 100},
    }
    resp7 = await async_client.patch(
        f"/api/v1/dashboards/{test_board['boardId']}",
        json={"operations": [{"op": "add-widget", "widget": widget_neg_x}]},
        headers=admin_token_headers,
    )
    assert resp7.status_code == 400, f"Expected 400 for negative x, got {resp7.status_code}: {resp7.text}"

    # y=-1 is below the minimum of 0.
    widget_neg_y = {
        "widgetType": "hydra::clock",
        "config": {},
        "placements": {"lg": {"x": 0, "y": 0, "w": 2, "h": 2}},
        "freeformPosition": {"x": 0, "y": -1, "w": 200, "h": 100},
    }
    resp8 = await async_client.patch(
        f"/api/v1/dashboards/{test_board['boardId']}",
        json={"operations": [{"op": "add-widget", "widget": widget_neg_y}]},
        headers=admin_token_headers,
    )
    assert resp8.status_code == 400, f"Expected 400 for negative y, got {resp8.status_code}: {resp8.text}"


async def test_patch_value_only_unknown_keys_is_noop(
    async_client: AsyncClient,
    admin_token_headers,
    mock_mongodb,
    mock_dashboards_collection,
    sample_user,
    test_board,
):
    """PATCH update-settings with value containing only unrecognized keys should not bump version."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    initial_version = test_board["version"]
    # No real change: _get_owned_board + get_board_for_user each call find_one once.
    mock_dashboards_collection.find_one = AsyncMock(
        side_effect=[test_board, test_board]
    )
    mock_dashboards_collection.update_one = AsyncMock()

    resp = await async_client.patch(
        f"/api/v1/dashboards/{test_board['boardId']}",
        json={"operations": [{"op": "update-settings", "value": {
            "arbitraryKey": "ignored",
            "anotherBadKey": 42,
        }}]},
        headers=admin_token_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["version"] == initial_version


async def test_update_widget_put_persists_freeform_position(
    async_client: AsyncClient,
    admin_token_headers,
    mock_mongodb,
    mock_dashboards_collection,
    mock_versions_collection,
    sample_user,
    test_board,
):
    """PUT widget update with freeformPosition writes it to the $set payload."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    instance_id = "wi_testfp0001"
    existing_widget = {
        "instanceId": instance_id,
        "widgetType": "hydra::clock",
        "config": {},
        "placements": {"lg": {"x": 0, "y": 0, "w": 2, "h": 2}},
        "dataBinding": None,
    }
    board_with_widget = {**test_board, "widgets": [existing_widget]}

    updated_widget = {
        **existing_widget,
        "freeformPosition": {"x": 50.0, "y": 100.0, "w": 300.0, "h": 200.0},
    }
    board_after = {**board_with_widget, "widgets": [updated_widget], "version": 2}

    # Calls: _get_owned_board (update_widget), get_board_for_user (response).
    mock_dashboards_collection.find_one = AsyncMock(
        side_effect=[board_with_widget, board_after]
    )
    mock_dashboards_collection.update_one = AsyncMock()
    mock_versions_collection.insert_one = AsyncMock()

    resp = await async_client.put(
        f"/api/v1/dashboards/{test_board['boardId']}/widgets/{instance_id}",
        json={"freeformPosition": {"x": 50, "y": 100, "w": 300, "h": 200}},
        headers=admin_token_headers,
    )
    assert resp.status_code == 200, resp.text

    # Confirm freeformPosition was included in the MongoDB $set payload.
    mock_dashboards_collection.update_one.assert_called_once()
    call_args = mock_dashboards_collection.update_one.call_args
    set_doc = call_args[0][1]["$set"]
    fp_key = "widgets.0.freeformPosition"
    assert fp_key in set_doc, f"Expected '{fp_key}' in $set, got keys: {list(set_doc.keys())}"
    assert set_doc[fp_key] == {"x": 50.0, "y": 100.0, "w": 300.0, "h": 200.0}

    # Confirm response reflects the updated freeformPosition.
    widgets = resp.json()["data"]["widgets"]
    updated = next(w for w in widgets if w["instanceId"] == instance_id)
    assert updated["freeformPosition"] == {"x": 50.0, "y": 100.0, "w": 300.0, "h": 200.0}


async def test_update_widget_put_without_freeform_position_does_not_overwrite(
    async_client: AsyncClient,
    admin_token_headers,
    mock_mongodb,
    mock_dashboards_collection,
    mock_versions_collection,
    sample_user,
    test_board,
):
    """PUT widget update without freeformPosition must NOT include it in the $set payload."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    instance_id = "wi_testfp0002"
    existing_widget = {
        "instanceId": instance_id,
        "widgetType": "hydra::clock",
        "config": {"key": "original"},
        "placements": {"lg": {"x": 0, "y": 0, "w": 2, "h": 2}},
        "freeformPosition": {"x": 10.0, "y": 20.0, "w": 150.0, "h": 90.0},
        "dataBinding": None,
    }
    board_with_widget = {**test_board, "widgets": [existing_widget]}

    updated_widget = {
        **existing_widget,
        "config": {"key": "updated"},
    }
    board_after = {**board_with_widget, "widgets": [updated_widget], "version": 2}

    mock_dashboards_collection.find_one = AsyncMock(
        side_effect=[board_with_widget, board_after]
    )
    mock_dashboards_collection.update_one = AsyncMock()
    mock_versions_collection.insert_one = AsyncMock()

    # Only updating config — freeformPosition is absent from the request body.
    resp = await async_client.put(
        f"/api/v1/dashboards/{test_board['boardId']}/widgets/{instance_id}",
        json={"config": {"key": "updated"}},
        headers=admin_token_headers,
    )
    assert resp.status_code == 200, resp.text

    # freeformPosition must NOT appear in the $set payload (no overwrite to null).
    mock_dashboards_collection.update_one.assert_called_once()
    call_args = mock_dashboards_collection.update_one.call_args
    set_doc = call_args[0][1]["$set"]
    fp_key = "widgets.0.freeformPosition"
    assert fp_key not in set_doc, (
        f"freeformPosition should NOT be in $set when absent from request, "
        f"but found it with value: {set_doc.get(fp_key)}"
    )


# ── Registry Tests — Wave 4 (configSchema, kioskMode, isAvailable) ───


async def test_widget_registry_returns_configschema_and_kioskmode(
    async_client: AsyncClient,
    admin_token_headers: dict[str, str],
    mock_mongodb: MagicMock,
    sample_user: dict,
) -> None:
    """Widget registry returns configSchema (with FieldSchema entries) and kioskMode/isAvailable."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    resp = await async_client.get(
        "/api/v1/dashboards/widgets/registry", headers=admin_token_headers
    )
    assert resp.status_code == 200, resp.text
    types = resp.json()["data"]["widgets"]

    # ── metric-card assertions ──────────────────────────────────────
    metric_card = next((t for t in types if t["widgetType"] == "hydra::metric-card"), None)
    assert metric_card is not None, "hydra::metric-card must be in the registry"

    assert "configSchema" in metric_card
    schemas = metric_card["configSchema"]
    assert len(schemas) >= 3, (
        f"Expected at least 3 configSchema fields on metric-card, got {len(schemas)}"
    )

    # Verify FieldSchema structure: 'type' (not legacy 'fieldType'), 'default' present
    color_field = next((f for f in schemas if f["key"] == "colorMode"), None)
    assert color_field is not None, "metric-card must have a 'colorMode' configSchema field"
    assert color_field["type"] == "enum", (
        f"colorMode should be type='enum', got {color_field.get('type')!r}"
    )
    assert color_field["default"] == "auto", (
        f"colorMode default should be 'auto', got {color_field.get('default')!r}"
    )
    assert isinstance(color_field.get("options"), list), "enum field must have 'options'"
    assert len(color_field["options"]) >= 2, "colorMode must have at least 2 enum options"
    option_values = {o["value"] for o in color_field["options"]}
    assert "auto" in option_values, "colorMode options must include 'auto'"

    # kioskMode and isAvailable
    assert metric_card["kioskMode"] == "render", (
        f"metric-card kioskMode should be 'render', got {metric_card.get('kioskMode')!r}"
    )
    assert metric_card["isAvailable"] is True, "metric-card should be isAvailable=True"

    # ── quick-action control widget is 'readonly' ───────────────────
    quick_action = next((t for t in types if t["widgetType"] == "hydra::quick-action"), None)
    assert quick_action is not None, "hydra::quick-action must be in the registry"
    assert quick_action["kioskMode"] == "readonly", (
        f"quick-action kioskMode should be 'readonly', got {quick_action.get('kioskMode')!r}"
    )


async def test_widget_registry_hides_tier3_widgets_with_available_only(
    async_client: AsyncClient,
    admin_token_headers: dict[str, str],
    mock_mongodb: MagicMock,
    sample_user: dict,
) -> None:
    """availableOnly=true excludes all 6 Tier 3 gated widgets from the response."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    resp = await async_client.get(
        "/api/v1/dashboards/widgets/registry",
        params={"availableOnly": "true"},
        headers=admin_token_headers,
    )
    assert resp.status_code == 200, resp.text
    types = resp.json()["data"]["widgets"]
    widget_types = {t["widgetType"] for t in types}

    # Tier 3 gated — must NOT appear when availableOnly=true
    tier3_blocked = (
        "hydra::log-viewer",
        "hydra::audit-stream",
        "hydra::mcp-query",
        "hydra::execution-queue",
        "hydra::integration-health",
        "hydra::agent-grid",
    )
    for blocked in tier3_blocked:
        assert blocked not in widget_types, (
            f"{blocked} should be gated (excluded with availableOnly=true) until Wave 5"
        )

    # Available Tier 1/2 widgets must still be visible
    for available in ("hydra::metric-card", "hydra::clock", "hydra::entity-table"):
        assert available in widget_types, (
            f"{available} should be visible with availableOnly=true"
        )


async def test_widget_registry_full_list_includes_tier3(
    async_client: AsyncClient,
    admin_token_headers: dict[str, str],
    mock_mongodb: MagicMock,
    sample_user: dict,
) -> None:
    """Default (availableOnly=false) returns all widgets including Tier 3 with isAvailable=False."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    resp = await async_client.get(
        "/api/v1/dashboards/widgets/registry", headers=admin_token_headers
    )
    assert resp.status_code == 200, resp.text
    types = resp.json()["data"]["widgets"]
    widget_types_map = {t["widgetType"]: t for t in types}

    # Full list must include Tier 3 entries
    for blocked in ("hydra::log-viewer", "hydra::audit-stream", "hydra::mcp-query",
                    "hydra::execution-queue", "hydra::integration-health", "hydra::agent-grid"):
        assert blocked in widget_types_map, (
            f"{blocked} must appear in the full registry listing (without availableOnly)"
        )
        defn = widget_types_map[blocked]
        assert defn["isAvailable"] is False, (
            f"{blocked} must have isAvailable=False; got {defn.get('isAvailable')!r}"
        )
        # Tier 3 widgets have empty configSchema
        assert defn["configSchema"] == [], (
            f"{blocked} configSchema must be empty list (Tier 3 gated); got {defn.get('configSchema')!r}"
        )


@pytest.mark.asyncio
async def test_control_widget_command_id_is_string_type(
    async_client: AsyncClient,
    admin_token_headers: dict[str, str],
    mock_mongodb: MagicMock,
    sample_user: dict,
) -> None:
    """command-trigger and workflow-trigger IDs are plain strings (no entity-ref picker yet)."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    resp = await async_client.get(
        "/api/v1/dashboards/widgets/registry", headers=admin_token_headers,
    )
    assert resp.status_code == 200, resp.text
    types = resp.json()["data"]["widgets"]

    cmd = next(t for t in types if t["widgetType"] == "hydra::command-trigger")
    cmd_id = next(f for f in cmd["configSchema"] if f["key"] == "commandId")
    assert cmd_id["type"] == "string", (
        f"commandId must be type='string', got {cmd_id.get('type')!r}"
    )
    assert cmd_id.get("entityType") is None, (
        "commandId must not have entityType (should not be an entity-ref)"
    )

    wf = next(t for t in types if t["widgetType"] == "hydra::workflow-trigger")
    wf_id = next(f for f in wf["configSchema"] if f["key"] == "workflowId")
    assert wf_id["type"] == "string", (
        f"workflowId must be type='string', got {wf_id.get('type')!r}"
    )
    assert wf_id.get("entityType") is None, (
        "workflowId must not have entityType (should not be an entity-ref)"
    )


async def test_widget_registry_exact_counts(
    async_client: AsyncClient,
    admin_token_headers: dict[str, str],
    mock_mongodb: MagicMock,
    sample_user: dict,
) -> None:
    """Exact count sentinels to catch accidental duplicate or removed widgets.

    Full registry (availableOnly=false) must have 51 widgets.
    Available-only registry (availableOnly=true) must have 45 widgets.
    """
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    full_resp = await async_client.get(
        "/api/v1/dashboards/widgets/registry", headers=admin_token_headers
    )
    assert full_resp.status_code == 200, full_resp.text
    full_widgets = full_resp.json()["data"]["widgets"]
    assert len(full_widgets) == 51, (
        f"Full registry should have 51 widgets, got {len(full_widgets)}"
    )

    avail_resp = await async_client.get(
        "/api/v1/dashboards/widgets/registry",
        params={"availableOnly": "true"},
        headers=admin_token_headers,
    )
    assert avail_resp.status_code == 200, avail_resp.text
    avail_widgets = avail_resp.json()["data"]["widgets"]
    assert len(avail_widgets) == 45, (
        f"Available registry should have 45 widgets, got {len(avail_widgets)}"
    )


async def test_all_enum_fields_have_options(
    async_client: AsyncClient,
    admin_token_headers: dict[str, str],
    mock_mongodb: MagicMock,
    sample_user: dict,
) -> None:
    """Every enum-type field across all widgets must have non-empty options."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    resp = await async_client.get(
        "/api/v1/dashboards/widgets/registry", headers=admin_token_headers
    )
    assert resp.status_code == 200, resp.text
    widgets = resp.json()["data"]["widgets"]

    violations: list[str] = []
    for widget in widgets:
        for field in widget.get("configSchema", []):
            if field.get("type") == "enum":
                opts = field.get("options")
                if not opts or len(opts) == 0:
                    violations.append(f"{widget['widgetType']}.{field['key']}")

    assert not violations, f"Enum fields missing non-empty options list: {violations}"
