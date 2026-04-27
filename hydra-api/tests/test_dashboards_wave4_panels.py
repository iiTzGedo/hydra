"""Tests for entity panel backend — Tasks 8–10 (P2DASH Wave 4 closeout).

Covers:
 - Task 8: Entity template variable resolver (templating.py)
 - Task 9: System panel seeder (seed_panels.py)
 - Task 10: PanelService + 3 REST endpoints
   - GET  /dashboards/panel/{entity_type}
   - POST /dashboards/panel/{entity_type}/customize
   - DELETE /dashboards/panel/{entity_type}/override
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from hydra.api.v1.core.security import create_access_token
from hydra.api.v1.main import app as v1_app
from hydra.api.v1.routers.dashboards import router as dashboards_router
from hydra.core.config import get_settings
from tests.conftest import create_mock_collection

# Idempotent router registration
_registered = False
if not _registered:
    v1_app.include_router(dashboards_router)
    _registered = True

pytestmark = pytest.mark.asyncio


# ── Helpers ───────────────────────────────────────────────────────────


def _make_system_panel(entity_type: str) -> dict[str, Any]:
    """Return a minimal system-default panel document for a given entity type."""
    now = datetime.now(UTC)
    return {
        "boardId": f"panel-default-{entity_type}",
        "name": f"{entity_type.title()} Panel",
        "description": f"Default panel for {entity_type}.",
        "icon": "server",
        "ownerId": "__system__",
        "ownerType": "system",
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
        "scope": "entity-panel",
        "entityTypeFilter": entity_type,
        "isSystemDefault": True,
        "widgets": [
            {
                "instanceId": "wi_abcd1234",
                "widgetType": f"hydra::{entity_type}-summary",
                "config": {},
                "binding": {
                    "source": f"hydra::{entity_type}s",
                    "query": f"{entity_type}Id={{{{entity.id}}}}",
                },
                "position": {"x": 0, "y": 0, "w": 12, "h": 3},
                "placements": {
                    "xl": {"x": 0, "y": 0, "w": 12, "h": 3},
                    "lg": {"x": 0, "y": 0, "w": 12, "h": 3},
                    "md": {"x": 0, "y": 0, "w": 12, "h": 3},
                    "sm": {"x": 0, "y": 0, "w": 4, "h": 3},
                    "xs": {"x": 0, "y": 0, "w": 2, "h": 3},
                },
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
        "tags": ["system", "entity-panel", entity_type],
        "isHome": False,
        "version": 1,
        "clonedFrom": None,
        "createdAt": now,
        "updatedAt": now,
        "archivedAt": None,
    }


def _make_user_override(entity_type: str, user_id: str) -> dict[str, Any]:
    """Return a minimal user-override panel document."""
    panel = _make_system_panel(entity_type)
    panel["boardId"] = f"panel-{entity_type}-{user_id}-override01"
    panel["ownerId"] = user_id
    panel["ownerType"] = "user"
    panel["isSystemDefault"] = False
    panel["name"] = f"My {entity_type.title()} Panel"
    return panel


# ── Collection Fixtures ───────────────────────────────────────────────


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
def _patch_collections(
    mock_mongodb,
    mock_dashboards_collection,
    mock_templates_collection,
    mock_versions_collection,
):
    """Wire mock collections into mock_mongodb.db and seed user lookups."""
    collections: dict[str, Any] = {
        "dashboards": mock_dashboards_collection,
        "dashboard_templates": mock_templates_collection,
        "dashboard_versions": mock_versions_collection,
    }
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(side_effect=lambda key: collections.get(key, MagicMock()))
    mock_mongodb.db = mock_db

    # Auth middleware looks up users by userId.  Provide minimal valid user docs
    # so that every token sub maps to a real user and does not 404.
    now = datetime.now(UTC)

    def _make_user(user_id: str, role: str, permissions: list[str]) -> dict[str, Any]:
        return {
            "userId": user_id,
            "username": user_id,
            "email": f"{user_id}@test.example",
            "role": role,
            "permissions": permissions,
            "status": "active",
            "createdAt": now,
            "updatedAt": now,
        }

    user_map: dict[str, dict[str, Any]] = {
        "user_viewer123": _make_user("user_viewer123", "viewer", ["dashboards:read", "nodes:read"]),
        "user_op456": _make_user("user_op456", "operator", ["dashboards:read", "dashboards:write"]),
        "user_admin123": _make_user("user_admin123", "admin", ["*:*"]),
    }

    async def _users_find_one(query: dict, *args: Any, **kwargs: Any) -> dict | None:
        user_id = query.get("userId") or query.get("username")
        return user_map.get(str(user_id)) if user_id else None

    mock_mongodb.users.find_one = AsyncMock(side_effect=_users_find_one)


@pytest.fixture
def async_client(client: AsyncClient) -> AsyncClient:
    return client


# ── Token / Header Fixtures ───────────────────────────────────────────


@pytest.fixture
def viewer_token_headers(test_settings) -> dict[str, str]:
    """Authorization headers for a viewer-role user (dashboards:read only)."""
    settings = get_settings()
    token = create_access_token(
        subject="user_viewer123",
        token_type="access",
        additional_claims={
            "sub_type": "user",
            "role": "viewer",
            "permissions": ["dashboards:read", "nodes:read"],
        },
        settings=settings,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def operator_token_headers(test_settings) -> dict[str, str]:
    """Authorization headers for an operator-role user (dashboards:read + write)."""
    settings = get_settings()
    token = create_access_token(
        subject="user_op456",
        token_type="access",
        additional_claims={
            "sub_type": "user",
            "role": "operator",
            "permissions": ["dashboards:read", "dashboards:write"],
        },
        settings=settings,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_token_headers(test_settings) -> dict[str, str]:
    """Authorization headers for an admin-role user."""
    settings = get_settings()
    token = create_access_token(
        subject="user_admin123",
        token_type="access",
        additional_claims={
            "sub_type": "user",
            "role": "admin",
            "permissions": ["*:*"],
        },
        settings=settings,
    )
    return {"Authorization": f"Bearer {token}"}


# ── seed_panels fixture ───────────────────────────────────────────────


@pytest.fixture
def seed_panels(mock_dashboards_collection: MagicMock):
    """Pre-seed the mock dashboards collection with system-default panels.

    Configures mock_dashboards_collection.find_one so that queries for the
    reserved board IDs return the correct system-default documents, simulating
    the real seeder having run.
    """
    panels = {
        "panel-default-node": _make_system_panel("node"),
        "panel-default-service": _make_system_panel("service"),
        "panel-default-network": _make_system_panel("network"),
    }

    async def _find_one(query: dict, *args: Any, **kwargs: Any) -> dict | None:
        # Match by boardId
        board_id = query.get("boardId")
        if board_id in panels:
            return panels[board_id]
        # No user override for fresh users by default
        if query.get("ownerType") == "user":
            return None
        return None

    mock_dashboards_collection.find_one = AsyncMock(side_effect=_find_one)

    # update_one for seed_system_panels (upsert=True; return no-op result)
    upsert_result = MagicMock()
    upsert_result.upserted_id = None
    mock_dashboards_collection.update_one = AsyncMock(return_value=upsert_result)


# ═════════════════════════════════════════════════════════════════════
# Task 8 — Template resolver unit tests
# ═════════════════════════════════════════════════════════════════════


def test_resolve_entity_id_in_query_string():
    from hydra.api.v1.services.dashboards.templating import resolve_entity_vars

    binding = {"source": "hydra::services", "query": "nodeId={{entity.id}}"}
    resolved = resolve_entity_vars(binding, entity_type="node", entity_id="node-abc")
    assert resolved["query"] == "nodeId=node-abc"


def test_resolve_entity_type():
    from hydra.api.v1.services.dashboards.templating import resolve_entity_vars

    binding = {"source": "hydra::{{entity.type}}s"}
    resolved = resolve_entity_vars(binding, entity_type="service", entity_id="svc-1")
    assert resolved["source"] == "hydra::services"


def test_no_vars_pass_through():
    from hydra.api.v1.services.dashboards.templating import resolve_entity_vars

    binding = {"source": "hydra::nodes", "query": ""}
    resolved = resolve_entity_vars(binding, entity_type="node", entity_id="node-abc")
    assert resolved == binding


def test_nested_config_deep_resolve():
    from hydra.api.v1.services.dashboards.templating import resolve_entity_vars_deep

    widget = {
        "widgetType": "hydra::metric-card",
        "config": {"label": "Services for {{entity.id}}"},
        "binding": {"source": "hydra::services", "query": "nodeId={{entity.id}}"},
    }
    out = resolve_entity_vars_deep(widget, entity_type="node", entity_id="node-abc")
    assert out["config"]["label"] == "Services for node-abc"
    assert out["binding"]["query"] == "nodeId=node-abc"


def test_deep_resolve_handles_lists():
    from hydra.api.v1.services.dashboards.templating import resolve_entity_vars_deep

    data = {"items": ["{{entity.id}}/1", "{{entity.id}}/2", "static"]}
    resolved = resolve_entity_vars_deep(data, entity_type="node", entity_id="n1")
    assert resolved["items"] == ["n1/1", "n1/2", "static"]


def test_deep_resolve_preserves_non_strings():
    from hydra.api.v1.services.dashboards.templating import resolve_entity_vars_deep

    data = {"x": 42, "y": True, "z": None, "s": "{{entity.id}}"}
    resolved = resolve_entity_vars_deep(data, entity_type="node", entity_id="nX")
    assert resolved == {"x": 42, "y": True, "z": None, "s": "nX"}


def test_whitespace_tolerant_pattern():
    """Pattern should accept {{ entity.id }} with extra spaces."""
    from hydra.api.v1.services.dashboards.templating import resolve_entity_vars

    binding = {"q": "id={{  entity.id  }}"}
    resolved = resolve_entity_vars(binding, entity_type="node", entity_id="n1")
    assert resolved["q"] == "id=n1"


# ═════════════════════════════════════════════════════════════════════
# Task 9 — System panel seeder tests
# ═════════════════════════════════════════════════════════════════════


async def test_seed_system_panels_is_idempotent(mock_dashboards_collection: MagicMock):
    """seed_system_panels is idempotent (upsert-by-ID)."""
    from hydra.api.v1.services.dashboards.seed_panels import seed_system_panels

    # Track upserted vs skipped calls
    upserted_result = MagicMock()
    upserted_result.upserted_id = "some_oid"

    skipped_result = MagicMock()
    skipped_result.upserted_id = None

    # First call: all three get inserted
    mock_dashboards_collection.update_one = AsyncMock(return_value=upserted_result)

    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_dashboards_collection)

    await seed_system_panels(mock_db)
    first_call_count = mock_dashboards_collection.update_one.call_count
    assert first_call_count == 3, "Expected 3 upsert calls for node, service, network"

    # Second call: all three are already present (upserted_id=None)
    mock_dashboards_collection.update_one = AsyncMock(return_value=skipped_result)

    await seed_system_panels(mock_db)
    second_call_count = mock_dashboards_collection.update_one.call_count
    assert second_call_count == 3, "Expected 3 upsert calls on second run too"


async def test_seed_system_panels_correct_ids(mock_dashboards_collection: MagicMock):
    """Seeder upserts with the reserved board IDs."""
    from hydra.api.v1.services.dashboards.seed_panels import PANEL_IDS, seed_system_panels

    result = MagicMock()
    result.upserted_id = "oid"
    mock_dashboards_collection.update_one = AsyncMock(return_value=result)

    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_dashboards_collection)

    await seed_system_panels(mock_db)

    calls = mock_dashboards_collection.update_one.call_args_list
    seen_ids = {call.args[0]["boardId"] for call in calls}
    assert seen_ids == set(PANEL_IDS.values())


async def test_seeded_panels_contain_template_vars(
    async_client: AsyncClient,
    viewer_token_headers: dict[str, str],
    seed_panels: None,
    mock_dashboards_collection: MagicMock,
):
    """GET /panel/{entity_type} must return widgets with dataBinding.query templates intact.

    Verifies that the seeder stores bindings under the Pydantic alias ``dataBinding``
    (not the legacy ``binding`` key that is silently dropped by the model).  All
    widgets in every panel type must have a non-null ``dataBinding`` with at least
    one query field containing ``{{entity.id}}``.
    """
    from hydra.api.v1.services.dashboards.seed_panels import (
        _network_panel,
        _node_panel,
        _service_panel,
    )

    factory_map = {
        "node": _node_panel,
        "service": _service_panel,
        "network": _network_panel,
    }

    now = datetime.now(UTC)
    for entity_type, factory in factory_map.items():
        seeded_doc = factory(now)

        # Point the mock collection at the freshly-built seeded document so the
        # endpoint reads exactly what the seeder would have written.
        async def _find_one(query: dict, *args: Any, doc: dict = seeded_doc, **kwargs: Any) -> dict | None:
            if query.get("ownerType") == "user":
                return None  # no user override
            return doc

        mock_dashboards_collection.find_one = AsyncMock(side_effect=_find_one)

        resp = await async_client.get(
            f"/api/v1/dashboards/panel/{entity_type}",
            headers=viewer_token_headers,
        )
        assert resp.status_code == 200, (
            f"GET /panel/{entity_type} returned {resp.status_code}: {resp.text}"
        )
        data = resp.json()["data"]
        widgets = data["widgets"]
        assert widgets, f"Panel {entity_type} returned no widgets"

        for w in widgets:
            binding = w.get("dataBinding")
            assert binding is not None, (
                f"Widget {w['widgetType']} in panel '{entity_type}' lost its dataBinding "
                f"(was silently dropped — likely stored under wrong key in seeder)"
            )
            query_str = str(binding.get("query", {}))
            assert "{{entity.id}}" in query_str, (
                f"Widget {w['widgetType']} in panel '{entity_type}' dataBinding.query "
                f"lost template vars: {binding}"
            )


async def test_seeded_panels_have_correct_scope_and_type():
    """Seeded panels must have scope=entity-panel, ownerType=system, isSystemDefault=True."""
    from datetime import UTC, datetime

    from hydra.api.v1.services.dashboards.seed_panels import (
        _network_panel,
        _node_panel,
        _service_panel,
    )

    now = datetime.now(UTC)
    panels = [_node_panel(now), _service_panel(now), _network_panel(now)]
    expected_types = ["node", "service", "network"]

    for panel, entity_type in zip(panels, expected_types, strict=True):
        assert panel["scope"] == "entity-panel", f"{panel['boardId']} has wrong scope"
        assert panel["entityTypeFilter"] == entity_type
        assert panel["ownerType"] == "system"
        assert panel["ownerId"] == "__system__"
        assert panel["isSystemDefault"] is True


# ═════════════════════════════════════════════════════════════════════
# Task 9 — PanelService unit tests
# ═════════════════════════════════════════════════════════════════════


async def test_panel_service_get_returns_system_default_when_no_override(
    mock_dashboards_collection: MagicMock,
):
    """PanelService.get_active_panel returns system default for fresh user."""
    from hydra.api.v1.services.dashboards.panel_service import PanelService

    node_default = _make_system_panel("node")

    async def _find_one(query: dict, *args: Any, **kwargs: Any) -> dict | None:
        if query.get("ownerType") == "user":
            return None  # no override
        return node_default

    mock_dashboards_collection.find_one = AsyncMock(side_effect=_find_one)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_dashboards_collection)

    svc = PanelService(mock_db)
    result = await svc.get_active_panel("node", "user_fresh")
    assert result["boardId"] == "panel-default-node"
    assert result["isSystemDefault"] is True


async def test_panel_service_get_returns_user_override_when_exists(
    mock_dashboards_collection: MagicMock,
):
    """PanelService.get_active_panel returns user override when present."""
    from hydra.api.v1.services.dashboards.panel_service import PanelService

    override = _make_user_override("node", "user_op456")

    mock_dashboards_collection.find_one = AsyncMock(return_value=override)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_dashboards_collection)

    svc = PanelService(mock_db)
    result = await svc.get_active_panel("node", "user_op456")
    assert result["ownerType"] == "user"
    assert result["ownerId"] == "user_op456"


async def test_panel_service_get_raises_if_no_default_seeded(
    mock_dashboards_collection: MagicMock,
):
    """PanelService.get_active_panel raises RuntimeError when panel not seeded."""
    from hydra.api.v1.services.dashboards.panel_service import PanelService

    mock_dashboards_collection.find_one = AsyncMock(return_value=None)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_dashboards_collection)

    svc = PanelService(mock_db)
    with pytest.raises(RuntimeError, match="not seeded"):
        await svc.get_active_panel("node", "user_fresh")


async def test_panel_service_customize_clones_default(
    mock_dashboards_collection: MagicMock,
):
    """PanelService.customize clones system default into user override."""
    from hydra.api.v1.services.dashboards.panel_service import PanelService

    node_default = _make_system_panel("node")

    call_count = 0

    async def _find_one(query: dict, *args: Any, **kwargs: Any) -> dict | None:
        nonlocal call_count
        call_count += 1
        if query.get("ownerType") == "user":
            return None  # no existing override
        return node_default

    mock_dashboards_collection.find_one = AsyncMock(side_effect=_find_one)
    mock_dashboards_collection.insert_one = AsyncMock()
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_dashboards_collection)

    svc = PanelService(mock_db)
    override = await svc.customize("node", "user_op456")

    assert override["ownerType"] == "user"
    assert override["ownerId"] == "user_op456"
    assert override["isSystemDefault"] is False
    assert not override["boardId"].startswith("panel-default-")
    assert override["scope"] == "entity-panel"
    assert override["entityTypeFilter"] == "node"
    mock_dashboards_collection.insert_one.assert_called_once()


async def test_panel_service_customize_is_idempotent(
    mock_dashboards_collection: MagicMock,
):
    """PanelService.customize returns existing override without inserting again."""
    from hydra.api.v1.services.dashboards.panel_service import PanelService

    existing = _make_user_override("node", "user_op456")
    mock_dashboards_collection.find_one = AsyncMock(return_value=existing)
    mock_dashboards_collection.insert_one = AsyncMock()
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_dashboards_collection)

    svc = PanelService(mock_db)
    result = await svc.customize("node", "user_op456")
    assert result["boardId"] == existing["boardId"]
    mock_dashboards_collection.insert_one.assert_not_called()


async def test_panel_service_delete_returns_true_when_found(
    mock_dashboards_collection: MagicMock,
):
    """PanelService.delete_override returns True when document is deleted."""
    from hydra.api.v1.services.dashboards.panel_service import PanelService

    delete_result = MagicMock()
    delete_result.deleted_count = 1
    mock_dashboards_collection.delete_one = AsyncMock(return_value=delete_result)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_dashboards_collection)

    svc = PanelService(mock_db)
    assert await svc.delete_override("node", "user_op456") is True


async def test_panel_service_delete_returns_false_when_not_found(
    mock_dashboards_collection: MagicMock,
):
    """PanelService.delete_override returns False when no document to delete."""
    from hydra.api.v1.services.dashboards.panel_service import PanelService

    delete_result = MagicMock()
    delete_result.deleted_count = 0
    mock_dashboards_collection.delete_one = AsyncMock(return_value=delete_result)
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_dashboards_collection)

    svc = PanelService(mock_db)
    assert await svc.delete_override("node", "user_op456") is False


async def test_customize_race_produces_single_override(
    mock_dashboards_collection: MagicMock,
):
    """Concurrent customize calls: DuplicateKeyError path is handled gracefully.

    This test directly exercises the ``DuplicateKeyError`` handler in
    ``PanelService.customize`` — the code path that fires when the DB-level
    partial unique index rejects a duplicate insert.

    Because asyncio is single-threaded, true concurrency cannot occur within a
    unit test.  Instead, we simulate the race by calling ``customize`` twice in
    sequence where the *first* call succeeds (winner) and the *second* call's
    initial ``find_one`` guard still returns ``None`` (simulating a race-lost
    caller that saw the empty state before the winner committed), then hits
    ``DuplicateKeyError`` on ``insert_one``.  The service must resolve this by
    fetching the winner document and returning it — not raising an exception.
    """
    from pymongo.errors import DuplicateKeyError

    from hydra.api.v1.services.dashboards.panel_service import PanelService

    node_default = _make_system_panel("node")

    # Track what the winner inserted
    winner_doc: dict[str, Any] | None = None

    # insert_call_count drives the mock behaviour
    insert_call_count = 0

    async def _insert_one(doc: dict, *args: Any, **kwargs: Any) -> MagicMock:
        nonlocal insert_call_count, winner_doc
        insert_call_count += 1
        if insert_call_count == 1:
            # First call: wins the race, record the inserted doc
            winner_doc = dict(doc)
            winner_doc.pop("_id", None)
            return MagicMock()
        else:
            # Subsequent calls: rejected by the partial unique index
            raise DuplicateKeyError("E11000 duplicate key error")

    mock_dashboards_collection.insert_one = AsyncMock(side_effect=_insert_one)

    # find_one_call_count distinguishes the "guard" check from the "race recovery" check
    find_one_call_count = 0

    async def _find_one(query: dict, *args: Any, **kwargs: Any) -> dict | None:
        nonlocal find_one_call_count
        find_one_call_count += 1

        if query.get("ownerType") == "user":
            # During the guard check (calls 1 and 3 when simulating two calls):
            # both callers see no existing override initially — the race.
            # During recovery after DuplicateKeyError (call 5+): return winner.
            if winner_doc is not None and insert_call_count >= 2:
                return dict(winner_doc)
            return None

        # System default lookup
        if query.get("boardId") == "panel-default-node":
            return node_default
        return None

    mock_dashboards_collection.find_one = AsyncMock(side_effect=_find_one)

    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_dashboards_collection)

    svc = PanelService(mock_db)

    # --- Winner call ---
    result_winner = await svc.customize("node", "user-race-1")
    assert result_winner is not None
    assert result_winner["ownerType"] == "user"
    assert insert_call_count == 1, "Winner should have inserted once"
    assert winner_doc is not None

    # --- Loser call (simulates a caller that also passed the guard before the
    #     winner committed, but hits DuplicateKeyError on insert) ---
    result_loser = await svc.customize("node", "user-race-1")
    assert result_loser is not None
    assert result_loser["ownerType"] == "user"
    assert insert_call_count == 2, "Loser should have attempted insert and hit DuplicateKeyError"

    # Both must return the same board
    assert result_winner["boardId"] == result_loser["boardId"], (
        f"Winner and loser must return the same board; "
        f"winner={result_winner['boardId']}, loser={result_loser['boardId']}"
    )


# ═════════════════════════════════════════════════════════════════════
# Task 10 — REST endpoint integration tests
# ═════════════════════════════════════════════════════════════════════


async def test_get_panel_returns_system_default_when_no_override(
    async_client: AsyncClient,
    viewer_token_headers: dict[str, str],
    seed_panels: None,
    mock_dashboards_collection: MagicMock,
):
    """GET /dashboards/panel/node returns the system default for a fresh user."""
    resp = await async_client.get(
        "/api/v1/dashboards/panel/node",
        headers=viewer_token_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["boardId"] == "panel-default-node"
    assert data["scope"] == "entity-panel"
    assert data["entityTypeFilter"] == "node"


async def test_get_panel_returns_user_override_when_present(
    async_client: AsyncClient,
    operator_token_headers: dict[str, str],
    mock_dashboards_collection: MagicMock,
):
    """GET /dashboards/panel/node returns user override when one exists."""
    override = _make_user_override("node", "user_op456")

    mock_dashboards_collection.find_one = AsyncMock(return_value=override)

    resp = await async_client.get(
        "/api/v1/dashboards/panel/node",
        headers=operator_token_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["ownerType"] == "user"
    assert data["entityTypeFilter"] == "node"


async def test_customize_clones_default_into_user_override(
    async_client: AsyncClient,
    operator_token_headers: dict[str, str],
    seed_panels: None,
    mock_dashboards_collection: MagicMock,
):
    """POST /dashboards/panel/node/customize creates a personal override."""
    node_default = _make_system_panel("node")

    async def _find_one(query: dict, *args: Any, **kwargs: Any) -> dict | None:
        if query.get("ownerType") == "user":
            return None  # no existing override
        return node_default

    mock_dashboards_collection.find_one = AsyncMock(side_effect=_find_one)
    mock_dashboards_collection.insert_one = AsyncMock()

    resp = await async_client.post(
        "/api/v1/dashboards/panel/node/customize",
        headers=operator_token_headers,
    )
    assert resp.status_code == 201
    override = resp.json()["data"]
    assert override["scope"] == "entity-panel"
    assert override["entityTypeFilter"] == "node"
    assert override["ownerType"] == "user"
    assert override["isSystemDefault"] is False
    assert not override["boardId"].startswith("panel-default-")


async def test_customize_is_idempotent(
    async_client: AsyncClient,
    operator_token_headers: dict[str, str],
    mock_dashboards_collection: MagicMock,
):
    """POST /dashboards/panel/node/customize is idempotent: returns existing override."""
    existing = _make_user_override("node", "user_op456")
    mock_dashboards_collection.find_one = AsyncMock(return_value=existing)
    mock_dashboards_collection.insert_one = AsyncMock()

    resp1 = await async_client.post(
        "/api/v1/dashboards/panel/node/customize",
        headers=operator_token_headers,
    )
    resp2 = await async_client.post(
        "/api/v1/dashboards/panel/node/customize",
        headers=operator_token_headers,
    )
    assert resp1.status_code == 201
    assert resp2.status_code == 201
    assert resp1.json()["data"]["boardId"] == resp2.json()["data"]["boardId"]
    mock_dashboards_collection.insert_one.assert_not_called()


async def test_delete_override_success(
    async_client: AsyncClient,
    operator_token_headers: dict[str, str],
    mock_dashboards_collection: MagicMock,
):
    """DELETE /dashboards/panel/node/override returns 204 when override exists."""
    delete_result = MagicMock()
    delete_result.deleted_count = 1
    mock_dashboards_collection.delete_one = AsyncMock(return_value=delete_result)

    resp = await async_client.delete(
        "/api/v1/dashboards/panel/node/override",
        headers=operator_token_headers,
    )
    assert resp.status_code == 204


async def test_delete_override_restores_default(
    async_client: AsyncClient,
    operator_token_headers: dict[str, str],
    seed_panels: None,
    mock_dashboards_collection: MagicMock,
):
    """After deleting override, GET returns system default again."""
    node_default = _make_system_panel("node")

    delete_result = MagicMock()
    delete_result.deleted_count = 1
    mock_dashboards_collection.delete_one = AsyncMock(return_value=delete_result)

    del_resp = await async_client.delete(
        "/api/v1/dashboards/panel/node/override",
        headers=operator_token_headers,
    )
    assert del_resp.status_code == 204

    # Now GET should return system default (no override for this user)
    async def _find_one(query: dict, *args: Any, **kwargs: Any) -> dict | None:
        if query.get("ownerType") == "user":
            return None
        if query.get("boardId") == "panel-default-node":
            return node_default
        return None

    mock_dashboards_collection.find_one = AsyncMock(side_effect=_find_one)

    get_resp = await async_client.get(
        "/api/v1/dashboards/panel/node",
        headers=operator_token_headers,
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["boardId"] == "panel-default-node"


async def test_viewer_cannot_customize(
    async_client: AsyncClient,
    viewer_token_headers: dict[str, str],
):
    """POST /dashboards/panel/node/customize requires dashboards:write → 403 for viewer."""
    resp = await async_client.post(
        "/api/v1/dashboards/panel/node/customize",
        headers=viewer_token_headers,
    )
    assert resp.status_code == 403


async def test_viewer_cannot_delete_override(
    async_client: AsyncClient,
    viewer_token_headers: dict[str, str],
):
    """DELETE /dashboards/panel/node/override requires dashboards:write → 403 for viewer."""
    resp = await async_client.delete(
        "/api/v1/dashboards/panel/node/override",
        headers=viewer_token_headers,
    )
    assert resp.status_code == 403


async def test_delete_nonexistent_override_returns_404(
    async_client: AsyncClient,
    operator_token_headers: dict[str, str],
    mock_dashboards_collection: MagicMock,
):
    """DELETE /dashboards/panel/node/override returns 404 when no override exists."""
    delete_result = MagicMock()
    delete_result.deleted_count = 0
    mock_dashboards_collection.delete_one = AsyncMock(return_value=delete_result)

    resp = await async_client.delete(
        "/api/v1/dashboards/panel/node/override",
        headers=operator_token_headers,
    )
    assert resp.status_code == 404


@pytest.mark.parametrize("bad_type", [
    "invalid_type", "Node", "node2", "group", "service ", "", "1",
])
async def test_invalid_entity_type_rejected(
    async_client: AsyncClient,
    viewer_token_headers: dict[str, str],
    bad_type: str,
):
    """GET /dashboards/panel/{entity_type} rejects unknown entity types.

    Empty string causes a redirect (307) since the trailing-slash router
    redirects before validation can fire. Other invalid values produce
    400 or 422. None should return 200 with valid data.
    """
    resp = await async_client.get(
        f"/api/v1/dashboards/panel/{bad_type}",
        headers=viewer_token_headers,
    )
    assert resp.status_code not in (200,), (
        f"Expected non-200 for bad_type={bad_type!r}, got {resp.status_code}"
    )


async def test_all_three_entity_types_accepted(
    async_client: AsyncClient,
    viewer_token_headers: dict[str, str],
    mock_dashboards_collection: MagicMock,
):
    """All three entity types (node, service, network) return valid responses."""
    for entity_type in ("node", "service", "network"):
        panel_doc = _make_system_panel(entity_type)

        def _make_find_one(doc: dict):  # noqa: ANN202
            async def _find_one(query: dict, *args: Any, **kwargs: Any) -> dict | None:
                return None if query.get("ownerType") == "user" else doc
            return _find_one

        mock_dashboards_collection.find_one = AsyncMock(side_effect=_make_find_one(panel_doc))
        resp = await async_client.get(
            f"/api/v1/dashboards/panel/{entity_type}",
            headers=viewer_token_headers,
        )
        assert resp.status_code == 200, f"Failed for entity type: {entity_type}"
        assert resp.json()["data"]["entityTypeFilter"] == entity_type


async def test_get_panel_service_entity_type_for_service(
    async_client: AsyncClient,
    viewer_token_headers: dict[str, str],
    mock_dashboards_collection: MagicMock,
):
    """GET /dashboards/panel/service returns the service panel."""
    service_panel = _make_system_panel("service")

    async def _find_one(query: dict, *args: Any, **kwargs: Any) -> dict | None:
        if query.get("ownerType") == "user":
            return None
        return service_panel

    mock_dashboards_collection.find_one = AsyncMock(side_effect=_find_one)

    resp = await async_client.get(
        "/api/v1/dashboards/panel/service",
        headers=viewer_token_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["entityTypeFilter"] == "service"


async def test_get_panel_service_entity_type_for_network(
    async_client: AsyncClient,
    viewer_token_headers: dict[str, str],
    mock_dashboards_collection: MagicMock,
):
    """GET /dashboards/panel/network returns the network panel."""
    network_panel = _make_system_panel("network")

    async def _find_one(query: dict, *args: Any, **kwargs: Any) -> dict | None:
        if query.get("ownerType") == "user":
            return None
        return network_panel

    mock_dashboards_collection.find_one = AsyncMock(side_effect=_find_one)

    resp = await async_client.get(
        "/api/v1/dashboards/panel/network",
        headers=viewer_token_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["entityTypeFilter"] == "network"


async def test_user_cannot_access_or_delete_another_users_override(
    async_client: AsyncClient,
    operator_token_headers: dict[str, str],
    admin_token_headers: dict[str, str],
    seed_panels: None,
    mock_dashboards_collection: MagicMock,
):
    """User A's override is invisible to User B.

    Specifically:
    - Operator creates an override (POST customize).
    - Admin GETs panel/node — sees the system default, not operator's override.
    - Admin DELETEs their own override → 404 (they have none).
    - Operator's override is unaffected.
    """
    op_board_id_container: list[str] = []

    node_default = _make_system_panel("node")

    # State: operator's override once created
    operator_override: dict[str, Any] | None = None

    async def _find_one_for_operator_customize(
        query: dict, *args: Any, **kwargs: Any
    ) -> dict | None:
        """First customize call: no existing override → return default."""
        if query.get("ownerType") == "user" and query.get("ownerId") == "user_op456":
            return None  # operator has no override yet
        if query.get("boardId") == "panel-default-node":
            return node_default
        return None

    mock_dashboards_collection.find_one = AsyncMock(
        side_effect=_find_one_for_operator_customize
    )
    inserted_docs: list[dict[str, Any]] = []

    async def _insert_one(doc: dict, *args: Any, **kwargs: Any) -> MagicMock:
        inserted_docs.append(dict(doc))
        return MagicMock()

    mock_dashboards_collection.insert_one = AsyncMock(side_effect=_insert_one)

    op_create = await async_client.post(
        "/api/v1/dashboards/panel/node/customize",
        headers=operator_token_headers,
    )
    assert op_create.status_code == 201, f"Operator customize failed: {op_create.text}"
    op_board_id = op_create.json()["data"]["boardId"]
    op_board_id_container.append(op_board_id)
    assert op_board_id != "panel-default-node"

    # Save the inserted override for later lookups
    assert inserted_docs, "Expected insert_one to have been called"
    operator_override = inserted_docs[0]

    # Admin GETs panel/node — should see system default (has no personal override)
    async def _find_one_for_admin_get(
        query: dict, *args: Any, **kwargs: Any
    ) -> dict | None:
        owner_id = query.get("ownerId")
        if query.get("ownerType") == "user":
            # Admin (user_admin123) has no override; operator's override is per-user
            if owner_id == "user_admin123":
                return None
            if owner_id == "user_op456":
                return operator_override
        if query.get("boardId") == "panel-default-node":
            return node_default
        return None

    mock_dashboards_collection.find_one = AsyncMock(side_effect=_find_one_for_admin_get)

    admin_get = await async_client.get(
        "/api/v1/dashboards/panel/node",
        headers=admin_token_headers,
    )
    assert admin_get.status_code == 200
    admin_board_id = admin_get.json()["data"]["boardId"]
    assert admin_board_id == "panel-default-node", (
        f"Admin should see system default, got {admin_board_id}"
    )
    assert admin_board_id != op_board_id

    # Admin DELETEs their override → 404 (they have none)
    admin_delete_result = MagicMock()
    admin_delete_result.deleted_count = 0  # nothing to delete for admin
    mock_dashboards_collection.delete_one = AsyncMock(return_value=admin_delete_result)

    admin_del = await async_client.delete(
        "/api/v1/dashboards/panel/node/override",
        headers=admin_token_headers,
    )
    assert admin_del.status_code == 404, (
        f"Admin delete should be 404 (no override exists), got {admin_del.status_code}"
    )

    # Operator's override still exists — GET returns their board
    mock_dashboards_collection.find_one = AsyncMock(side_effect=_find_one_for_admin_get)

    op_get = await async_client.get(
        "/api/v1/dashboards/panel/node",
        headers=operator_token_headers,
    )
    assert op_get.status_code == 200
    assert op_get.json()["data"]["boardId"] == op_board_id, (
        "Operator's override should still exist after admin's failed delete"
    )
