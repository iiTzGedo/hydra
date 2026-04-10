"""Integration tests for dashboard widget data binding, board CRUD round-trips,
template instantiation, sharing permissions, widget reordering, and export/import.
"""

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


# ── Shared Fixtures ──────────────────────────────────────────────────


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


def _make_admin_user(sample_user):
    return {**sample_user, "userId": "user_admin123", "role": "admin"}


def _make_board(now, *, widgets=None, name="Test Board", board_id="board_test001"):
    """Build a complete board document with configurable widgets."""
    return {
        "boardId": board_id,
        "name": name,
        "description": "Integration test board",
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
        "widgets": widgets or [],
        "settings": {
            "theme": "inherit",
            "autoRefresh": True,
            "refreshInterval": 30,
            "showHeader": True,
            "kioskMode": False,
        },
        "tags": ["integration-test"],
        "isHome": False,
        "version": 1,
        "clonedFrom": None,
        "createdAt": now,
        "updatedAt": now,
        "archivedAt": None,
    }


def _stat_widget(instance_id="wi_stats01"):
    return {
        "instanceId": instance_id,
        "widgetType": "hydra::stats-cards",
        "position": {"x": 0, "y": 0, "w": 12, "h": 2},
        "config": {"title": "Node Count"},
        "dataBinding": {
            "source": "hydra::nodes",
            "query": {"class": "compute"},
            "refreshInterval": 60,
        },
    }


def _service_widget(instance_id="wi_svc01"):
    return {
        "instanceId": instance_id,
        "widgetType": "hydra::service-summary",
        "position": {"x": 0, "y": 2, "w": 6, "h": 4},
        "config": {"title": "Service Health"},
        "dataBinding": {
            "source": "hydra::services",
            "query": {},
            "refreshInterval": 120,
        },
    }


def _capacity_widget(instance_id="wi_cap01"):
    return {
        "instanceId": instance_id,
        "widgetType": "hydra::capacity-overview",
        "position": {"x": 6, "y": 2, "w": 6, "h": 4},
        "config": {"title": "Capacity"},
        "dataBinding": None,
    }


def _activity_widget(instance_id="wi_act01"):
    return {
        "instanceId": instance_id,
        "widgetType": "hydra::recent-activity",
        "position": {"x": 0, "y": 6, "w": 12, "h": 4},
        "config": {},
        "dataBinding": None,
    }


# ── Test: Board CRUD Round-Trip ──────────────────────────────────────


@pytest.mark.asyncio
async def test_board_crud_round_trip(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    now,
):
    """Create board -> GET -> PUT (update name + widgets) -> GET -> DELETE.

    Each step verifies the response matches expectations.
    """
    admin_user = _make_admin_user(sample_user)
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    created_board = _make_board(now, widgets=[_stat_widget()])
    mock_dashboards_collection.insert_one = AsyncMock()
    mock_dashboards_collection.find_one = AsyncMock(return_value=created_board)

    # 1. CREATE
    response = await client.post(
        "/api/v1/dashboards",
        json={
            "name": "Test Board",
            "description": "Integration test board",
            "boardType": "custom",
            "widgets": [
                {
                    "widgetType": "hydra::stats-cards",
                    "position": {"x": 0, "y": 0, "w": 12, "h": 2},
                    "config": {"title": "Node Count"},
                    "dataBinding": {
                        "source": "hydra::nodes",
                        "query": {"class": "compute"},
                        "refreshInterval": 60,
                    },
                }
            ],
            "tags": ["integration-test"],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    create_data = response.json()["data"]
    assert create_data["name"] == "Test Board"
    assert len(create_data["widgets"]) == 1
    assert create_data["widgets"][0]["widgetType"] == "hydra::stats-cards"
    assert create_data["widgets"][0]["dataBinding"]["source"] == "hydra::nodes"
    # The service generates a random boardId; our mock returns the fixture boardId
    board_id = created_board["boardId"]
    mock_dashboards_collection.insert_one.assert_awaited_once()

    # 2. GET (read back)
    response = await client.get(
        f"/api/v1/dashboards/{board_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    get_data = response.json()["data"]
    assert get_data["boardId"] == board_id
    assert get_data["name"] == "Test Board"
    assert len(get_data["widgets"]) == 1

    # 3. PUT (update name + widgets)
    updated_board = {
        **created_board,
        "name": "Updated Board",
        "widgets": [_stat_widget(), _service_widget()],
        "version": 2,
    }
    mock_dashboards_collection.find_one = AsyncMock(
        side_effect=[created_board, updated_board]
    )
    mock_dashboards_collection.update_one = AsyncMock()

    response = await client.put(
        f"/api/v1/dashboards/{board_id}",
        json={
            "name": "Updated Board",
            "widgets": [
                {
                    "instanceId": "wi_stats01",
                    "widgetType": "hydra::stats-cards",
                    "position": {"x": 0, "y": 0, "w": 12, "h": 2},
                    "config": {"title": "Node Count"},
                    "dataBinding": {
                        "source": "hydra::nodes",
                        "query": {"class": "compute"},
                        "refreshInterval": 60,
                    },
                },
                {
                    "instanceId": "wi_svc01",
                    "widgetType": "hydra::service-summary",
                    "position": {"x": 0, "y": 2, "w": 6, "h": 4},
                    "config": {"title": "Service Health"},
                    "dataBinding": {
                        "source": "hydra::services",
                        "query": {},
                        "refreshInterval": 120,
                    },
                },
            ],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    put_data = response.json()["data"]
    assert put_data["name"] == "Updated Board"
    assert len(put_data["widgets"]) == 2
    mock_dashboards_collection.update_one.assert_awaited_once()

    # 4. GET again (verify update)
    mock_dashboards_collection.find_one = AsyncMock(return_value=updated_board)
    response = await client.get(
        f"/api/v1/dashboards/{board_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    second_get = response.json()["data"]
    assert second_get["name"] == "Updated Board"
    assert second_get["version"] == 2

    # 5. DELETE
    mock_dashboards_collection.find_one = AsyncMock(return_value=updated_board)
    mock_dashboards_collection.update_one = AsyncMock()
    response = await client.delete(
        f"/api/v1/dashboards/{board_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    delete_data = response.json()["data"]
    assert delete_data["boardId"] == board_id
    # Verify archivedAt was set via $set
    update_call = mock_dashboards_collection.update_one.call_args
    assert "archivedAt" in update_call[0][1]["$set"]


# ── Test: Widget Config Schema Validation ────────────────────────────


@pytest.mark.asyncio
async def test_widget_config_schema_validation(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    now,
):
    """Create a board with multiple widget types.

    Verify widget configs, data bindings, and type metadata are stored correctly.
    """
    admin_user = _make_admin_user(sample_user)
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    widgets = [_stat_widget(), _service_widget(), _capacity_widget()]
    board = _make_board(now, widgets=widgets)
    mock_dashboards_collection.insert_one = AsyncMock()
    mock_dashboards_collection.find_one = AsyncMock(return_value=board)

    response = await client.post(
        "/api/v1/dashboards",
        json={
            "name": "Multi-Widget Board",
            "widgets": [
                {
                    "widgetType": "hydra::stats-cards",
                    "position": {"x": 0, "y": 0, "w": 12, "h": 2},
                    "config": {"title": "Node Count"},
                    "dataBinding": {
                        "source": "hydra::nodes",
                        "query": {"class": "compute"},
                        "refreshInterval": 60,
                    },
                },
                {
                    "widgetType": "hydra::service-summary",
                    "position": {"x": 0, "y": 2, "w": 6, "h": 4},
                    "config": {"title": "Service Health"},
                    "dataBinding": {
                        "source": "hydra::services",
                        "query": {},
                        "refreshInterval": 120,
                    },
                },
                {
                    "widgetType": "hydra::capacity-overview",
                    "position": {"x": 6, "y": 2, "w": 6, "h": 4},
                    "config": {"title": "Capacity"},
                },
            ],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert len(data["widgets"]) == 3

    # Verify each widget has correct type and config
    widget_types = {w["widgetType"] for w in data["widgets"]}
    assert widget_types == {
        "hydra::stats-cards",
        "hydra::service-summary",
        "hydra::capacity-overview",
    }

    # Stats-cards: has data binding with source, query, refreshInterval
    stats = next(w for w in data["widgets"] if w["widgetType"] == "hydra::stats-cards")
    assert stats["config"]["title"] == "Node Count"
    assert stats["dataBinding"]["source"] == "hydra::nodes"
    assert stats["dataBinding"]["query"]["class"] == "compute"
    assert stats["dataBinding"]["refreshInterval"] == 60

    # Service-summary: has data binding
    svc = next(w for w in data["widgets"] if w["widgetType"] == "hydra::service-summary")
    assert svc["config"]["title"] == "Service Health"
    assert svc["dataBinding"]["source"] == "hydra::services"

    # Capacity-overview: no data binding
    cap = next(w for w in data["widgets"] if w["widgetType"] == "hydra::capacity-overview")
    assert cap["config"]["title"] == "Capacity"
    assert cap["dataBinding"] is None


# ── Test: Template Instantiation ─────────────────────────────────────


@pytest.mark.asyncio
async def test_template_instantiation(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    mock_templates_collection,
    admin_token,
    sample_user,
    now,
):
    """GET /dashboards/templates to list, then POST to instantiate one.

    Verify the resulting board has template-defined widgets with fresh IDs.
    """
    admin_user = _make_admin_user(sample_user)
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    template = {
        "templateId": "tmpl_infra_overview",
        "name": "Infrastructure Overview",
        "description": "Full infrastructure dashboard template",
        "boardType": "custom",
        "layout": {
            "columns": 12,
            "rowHeight": 80,
            "breakpoints": {
                "lg": {"columns": 12, "width": 1200},
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
        "createdBy": "system",
        "createdAt": now,
        "updatedAt": now,
    }

    # Step 1: List templates
    mock_templates_collection.count_documents = AsyncMock(return_value=1)
    mock_templates_collection.find = MagicMock(return_value=create_mock_cursor([template]))

    response = await client.get(
        "/api/v1/dashboards/templates",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    templates = response.json()["data"]
    assert len(templates) == 1
    assert templates[0]["templateId"] == "tmpl_infra_overview"
    assert templates[0]["widgetCount"] == 2

    # Step 2: Instantiate template
    mock_templates_collection.find_one = AsyncMock(return_value=template)
    mock_dashboards_collection.insert_one = AsyncMock()

    response = await client.post(
        "/api/v1/dashboards/templates/tmpl_infra_overview/instantiate",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    board = response.json()["data"]

    # Board should have template-defined widgets with fresh instance IDs
    assert len(board["widgets"]) == 2
    assert board["widgets"][0]["widgetType"] == "hydra::stats-cards"
    assert board["widgets"][1]["widgetType"] == "hydra::node-status-grid"

    # Instance IDs should be freshly generated (start with wi_)
    for w in board["widgets"]:
        assert w["instanceId"].startswith("wi_")

    # Board inherits template layout and settings
    assert board["boardType"] == "custom"
    assert board["visibility"] == "private"
    assert board["layout"]["columns"] == 12
    mock_dashboards_collection.insert_one.assert_awaited_once()


# ── Test: Template with Custom Overrides ─────────────────────────────


@pytest.mark.asyncio
async def test_template_with_custom_overrides(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    mock_templates_collection,
    admin_token,
    sample_user,
    now,
):
    """Instantiate template with custom name.

    Verify the override is applied while template widgets are preserved.
    """
    admin_user = _make_admin_user(sample_user)
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    template = {
        "templateId": "tmpl_minimal",
        "name": "Minimal Home",
        "description": "A clean, minimal dashboard",
        "boardType": "custom",
        "layout": {"columns": 12, "rowHeight": 80, "breakpoints": {}},
        "widgets": [
            {
                "widgetType": "hydra::stats-cards",
                "position": {"x": 0, "y": 0, "w": 12, "h": 2},
                "config": {"title": "Stats"},
                "dataBinding": None,
            },
        ],
        "settings": {"theme": "inherit"},
        "tags": ["minimal"],
        "widgetCount": 1,
        "createdBy": "system",
        "createdAt": now,
        "updatedAt": now,
    }

    mock_templates_collection.find_one = AsyncMock(return_value=template)
    mock_dashboards_collection.insert_one = AsyncMock()

    response = await client.post(
        "/api/v1/dashboards/templates/tmpl_minimal/instantiate",
        json={"name": "My Custom Dashboard"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    board = response.json()["data"]

    # Custom name applied
    assert board["name"] == "My Custom Dashboard"

    # Template widgets preserved
    assert len(board["widgets"]) == 1
    assert board["widgets"][0]["widgetType"] == "hydra::stats-cards"
    assert board["widgets"][0]["config"]["title"] == "Stats"

    # Template description carried over
    assert board["description"] == "A clean, minimal dashboard"


# ── Test: Board Sharing Permissions ──────────────────────────────────


@pytest.mark.asyncio
async def test_board_sharing_permissions(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    viewer_token,
    sample_user,
    now,
):
    """Share a board, then verify access and ownership constraints.

    - Admin shares the board publicly
    - Viewer (who has dashboards:read via role) can read the public board
    - Viewer cannot update (dashboards:write not in viewer role)
    - A different admin (non-owner) can read but cannot update (ownership check)
    """
    admin_user = _make_admin_user(sample_user)
    board = _make_board(now, widgets=[_stat_widget()])

    # 1. Admin shares the board as public
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)
    mock_dashboards_collection.find_one = AsyncMock(return_value=board)
    mock_dashboards_collection.update_one = AsyncMock()

    response = await client.post(
        f"/api/v1/dashboards/{board['boardId']}/share",
        json={"visibility": "public", "allowedUsers": []},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    share_data = response.json()["data"]
    assert share_data["visibility"] == "public"
    assert share_data["allowedUsers"] == []

    # 2. Viewer can read the public board (viewer role includes dashboards:read)
    viewer_user = {
        **sample_user,
        "userId": "user_viewer123",
        "role": "viewer",
    }
    public_board = {**board, "visibility": "public"}
    mock_mongodb.users.find_one = AsyncMock(return_value=viewer_user)
    mock_dashboards_collection.find_one = AsyncMock(return_value=public_board)

    response = await client.get(
        f"/api/v1/dashboards/{board['boardId']}",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["boardId"] == board["boardId"]

    # 3. Viewer cannot update (viewer role lacks dashboards:write)
    mock_mongodb.users.find_one = AsyncMock(return_value=viewer_user)

    response = await client.put(
        f"/api/v1/dashboards/{board['boardId']}",
        json={"name": "Viewer Edit Attempt"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert response.status_code == 403

    # 4. A different admin (non-owner) can read but cannot update
    other_admin_user = {**sample_user, "userId": "user_other999", "role": "admin"}
    mock_mongodb.users.find_one = AsyncMock(return_value=other_admin_user)
    mock_dashboards_collection.find_one = AsyncMock(return_value=public_board)

    response = await client.get(
        f"/api/v1/dashboards/{board['boardId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200

    # Non-owner admin gets validation error (400) on update
    mock_dashboards_collection.find_one = AsyncMock(return_value=board)

    response = await client.put(
        f"/api/v1/dashboards/{board['boardId']}",
        json={"name": "Unauthorized Edit"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 400


# ── Test: Widget Reordering Persistence ──────────────────────────────


@pytest.mark.asyncio
async def test_widget_reordering_persistence(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    now,
):
    """Create board with 4 widgets, PUT with reordered widget array.

    Verify the new order persists on GET.
    """
    admin_user = _make_admin_user(sample_user)
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    original_widgets = [
        _stat_widget("wi_a"),
        _service_widget("wi_b"),
        _capacity_widget("wi_c"),
        _activity_widget("wi_d"),
    ]
    board = _make_board(now, widgets=original_widgets)

    # Reorder: d, c, b, a
    reordered_widgets = [
        _activity_widget("wi_d"),
        _capacity_widget("wi_c"),
        _service_widget("wi_b"),
        _stat_widget("wi_a"),
    ]
    reordered_board = {**board, "widgets": reordered_widgets, "version": 2}

    # First find_one for ownership check, second for get_board response
    mock_dashboards_collection.find_one = AsyncMock(
        side_effect=[board, reordered_board]
    )
    mock_dashboards_collection.update_one = AsyncMock()

    response = await client.put(
        f"/api/v1/dashboards/{board['boardId']}",
        json={
            "widgets": [
                {
                    "instanceId": "wi_d",
                    "widgetType": "hydra::recent-activity",
                    "position": {"x": 0, "y": 0, "w": 12, "h": 4},
                    "config": {},
                },
                {
                    "instanceId": "wi_c",
                    "widgetType": "hydra::capacity-overview",
                    "position": {"x": 0, "y": 4, "w": 6, "h": 4},
                    "config": {"title": "Capacity"},
                },
                {
                    "instanceId": "wi_b",
                    "widgetType": "hydra::service-summary",
                    "position": {"x": 6, "y": 4, "w": 6, "h": 4},
                    "config": {"title": "Service Health"},
                    "dataBinding": {
                        "source": "hydra::services",
                        "query": {},
                        "refreshInterval": 120,
                    },
                },
                {
                    "instanceId": "wi_a",
                    "widgetType": "hydra::stats-cards",
                    "position": {"x": 0, "y": 8, "w": 12, "h": 2},
                    "config": {"title": "Node Count"},
                    "dataBinding": {
                        "source": "hydra::nodes",
                        "query": {"class": "compute"},
                        "refreshInterval": 60,
                    },
                },
            ]
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data["widgets"]) == 4

    # Verify the new order
    ids_in_order = [w["instanceId"] for w in data["widgets"]]
    assert ids_in_order == ["wi_d", "wi_c", "wi_b", "wi_a"]

    # Verify on subsequent GET
    mock_dashboards_collection.find_one = AsyncMock(return_value=reordered_board)
    response = await client.get(
        f"/api/v1/dashboards/{board['boardId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    get_ids = [w["instanceId"] for w in response.json()["data"]["widgets"]]
    assert get_ids == ["wi_d", "wi_c", "wi_b", "wi_a"]


# ── Test: Export / Import Round-Trip ─────────────────────────────────


@pytest.mark.asyncio
async def test_export_import_round_trip(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    admin_token,
    sample_user,
    now,
):
    """Export board to JSON, import to create new board.

    Verify widgets, configs, and metadata match.
    """
    admin_user = _make_admin_user(sample_user)
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    widgets = [_stat_widget(), _service_widget()]
    board = _make_board(
        now,
        widgets=widgets,
        name="Exportable Board",
        board_id="board_export01",
    )
    board["tags"] = ["export-test", "infrastructure"]

    # Step 1: Export the board
    mock_dashboards_collection.find_one = AsyncMock(return_value=board)

    response = await client.get(
        "/api/v1/dashboards/board_export01/export",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    export_data = response.json()["data"]

    # Export should have correct fields
    assert export_data["exportVersion"] == 1
    assert export_data["name"] == "Exportable Board"
    assert export_data["boardType"] == "custom"
    assert len(export_data["widgets"]) == 2
    assert set(export_data["tags"]) == {"export-test", "infrastructure"}

    # Export strips instance IDs
    for w in export_data["widgets"]:
        assert w.get("instanceId") is None

    # Step 2: Import the exported board with a new name
    mock_dashboards_collection.insert_one = AsyncMock()

    response = await client.post(
        "/api/v1/dashboards/import",
        json={
            "board": export_data,
            "name": "Imported Copy",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    imported = response.json()["data"]

    # Imported board should have a new board ID
    assert imported["boardId"] != "board_export01"
    assert imported["boardId"].startswith("board_")

    # Name overridden
    assert imported["name"] == "Imported Copy"

    # Widgets match in count, types, and configs
    assert len(imported["widgets"]) == 2
    imported_types = {w["widgetType"] for w in imported["widgets"]}
    assert imported_types == {"hydra::stats-cards", "hydra::service-summary"}

    # Fresh instance IDs generated
    for w in imported["widgets"]:
        assert w["instanceId"].startswith("wi_")

    # Data bindings preserved
    stats = next(w for w in imported["widgets"] if w["widgetType"] == "hydra::stats-cards")
    assert stats["dataBinding"]["source"] == "hydra::nodes"
    assert stats["config"]["title"] == "Node Count"

    # Tags preserved
    assert set(imported["tags"]) == {"export-test", "infrastructure"}

    # Imported board is always private
    assert imported["visibility"] == "private"
    mock_dashboards_collection.insert_one.assert_awaited_once()


# ── Test: Widget Registry ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_widget_registry(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """GET /dashboards/widgets/registry returns all registered widget types."""
    admin_user = _make_admin_user(sample_user)
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    response = await client.get(
        "/api/v1/dashboards/widgets/registry",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]

    assert data["total"] >= 6
    assert len(data["widgets"]) >= 6
    assert len(data["categories"]) >= 1

    # Verify widget structure
    for widget in data["widgets"]:
        assert "widgetType" in widget
        assert "displayName" in widget
        assert "category" in widget
        assert "defaultSize" in widget
        assert "minSize" in widget
        assert "maxSize" in widget
        assert "configSchema" in widget
        assert "capabilities" in widget

    # Verify categories have name, id, and count
    for cat in data["categories"]:
        assert "id" in cat
        assert "name" in cat
        assert "count" in cat
        assert cat["count"] > 0


@pytest.mark.asyncio
async def test_widget_registry_category_filter(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """GET /dashboards/widgets/registry?category=status filters by category."""
    admin_user = _make_admin_user(sample_user)
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    response = await client.get(
        "/api/v1/dashboards/widgets/registry?category=status",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]

    # All returned widgets should be in the "status" category
    for widget in data["widgets"]:
        assert widget["category"] == "status"

    # Categories should still show ALL categories (not filtered)
    category_ids = {c["id"] for c in data["categories"]}
    assert "status" in category_ids
