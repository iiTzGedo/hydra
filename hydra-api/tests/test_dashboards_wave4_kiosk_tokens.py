"""Tests for kiosk token backend — T037 (P2DASH Wave 4 closeout).

Covers:
 - POST /dashboards/{id}/kiosk-tokens  → 201 with raw token (once)
 - GET  /dashboards/{id}/kiosk-tokens  → list without hash/raw token
 - DELETE /dashboards/{id}/kiosk-tokens/{token_id} → 204 + sets revokedAt
 - GET /dashboards/kiosk/{id}?token=X  → sanitized board or 401
 - Admin/operator bypass for kiosk token management on any board
 - Double-revoke → 404
 - Valid token + deleted board → 404
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from hydra.api.v1.core.security import create_access_token
from hydra.api.v1.main import app as v1_app
from hydra.api.v1.routers.dashboards import router as dashboards_router
from hydra.api.v1.services.dashboards.kiosk_service import (
    _generate_raw_token,
    _hash_token,
    _verify_token,
)
from hydra.api.v1.services.dashboards.sanitizer import sanitize_for_kiosk
from hydra.api.v1.services.dashboards.widget_registry import widget_registry
from hydra.core.config import get_settings
from tests.conftest import create_mock_collection
from tests.utils import create_mock_cursor

# Idempotent router registration
_registered = False
if not _registered:
    v1_app.include_router(dashboards_router)
    _registered = True


# ── Helpers ───────────────────────────────────────────────────────────


def _make_board(
    board_id: str = "board_kiosk01",
    owner_id: str = "user_admin123",
    widgets: list[dict] | None = None,
) -> dict:
    """Return a minimal board document suitable for mocking MongoDB finds."""
    now = datetime.now(UTC)
    return {
        "boardId": board_id,
        "name": "Kiosk Test Board",
        "description": None,
        "icon": None,
        "ownerId": owner_id,
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
        "widgets": widgets or [],
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


def _make_token_doc(
    token_id: str = "kt_aabbccdd11223344",
    board_id: str = "board_kiosk01",
    raw: str | None = None,
    expires_at: datetime | None = None,
    revoked_at: datetime | None = None,
    last_used_at: datetime | None = None,
) -> dict:
    """Build a kiosk_tokens collection document with a bcrypt hash."""
    actual_raw = raw or _generate_raw_token()
    now = datetime.now(UTC)
    if expires_at is None:
        expires_at = now + timedelta(hours=168)  # 7 days default
    return {
        "_id": "mongo_oid_placeholder",
        "tokenId": token_id,
        "boardId": board_id,
        "tokenHash": _hash_token(actual_raw),
        "label": "Test token",
        "createdBy": "user_admin123",
        "createdAt": now,
        "expiresAt": expires_at,
        "revokedAt": revoked_at,
        "lastUsedAt": last_used_at,
        "_raw": actual_raw,  # convenience; not stored in DB
    }


# ── Collection Fixtures ───────────────────────────────────────────────


@pytest.fixture
def mock_dashboards_collection():
    return create_mock_collection()


@pytest.fixture
def mock_kiosk_collection():
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
    mock_kiosk_collection,
    mock_templates_collection,
    mock_versions_collection,
):
    """Wire mock collections into mock_mongodb.db."""
    collections = {
        "dashboards": mock_dashboards_collection,
        "kiosk_tokens": mock_kiosk_collection,
        "dashboard_templates": mock_templates_collection,
        "dashboard_versions": mock_versions_collection,
    }
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(side_effect=lambda key: collections.get(key, MagicMock()))
    mock_mongodb.db = mock_db


@pytest.fixture
def async_client(client: AsyncClient) -> AsyncClient:
    return client


@pytest.fixture
def admin_headers(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}


# ── Board with control widget ─────────────────────────────────────────


@pytest.fixture
def board_with_control_widget():
    """Board containing a hydra::quick-action widget (kioskMode='readonly')."""
    return _make_board(
        widgets=[
            {
                "instanceId": "wi_ctrl001",
                "widgetType": "hydra::quick-action",
                "config": {"actionId": "restart-nginx", "label": "Restart NGINX"},
                "position": {"x": 0, "y": 0, "w": 3, "h": 2},
                "placements": {
                    "xl": {"x": 0, "y": 0, "w": 3, "h": 2},
                    "lg": {"x": 0, "y": 0, "w": 3, "h": 2},
                    "md": {"x": 0, "y": 0, "w": 3, "h": 2},
                    "sm": {"x": 0, "y": 0, "w": 3, "h": 2},
                    "xs": {"x": 0, "y": 0, "w": 2, "h": 2},
                },
                "dataBinding": None,
            }
        ]
    )


@pytest.fixture
def board_with_hidden_widget():
    """Board containing a widget type that should be hidden in kiosk mode."""
    # We register a temporary widget with kioskMode='hide' for this test.
    return _make_board(
        widgets=[
            {
                "instanceId": "wi_hidden001",
                "widgetType": "test::hidden-widget",
                "config": {},
                "position": {"x": 0, "y": 0, "w": 3, "h": 2},
                "placements": {
                    "xl": {"x": 0, "y": 0, "w": 3, "h": 2},
                    "lg": {"x": 0, "y": 0, "w": 3, "h": 2},
                    "md": {"x": 0, "y": 0, "w": 3, "h": 2},
                    "sm": {"x": 0, "y": 0, "w": 3, "h": 2},
                    "xs": {"x": 0, "y": 0, "w": 2, "h": 2},
                },
                "dataBinding": None,
            }
        ]
    )


# ── Task 4/5 unit tests: KioskService ────────────────────────────────


async def test_create_kiosk_token_returns_raw_once(
    async_client: AsyncClient,
    admin_headers,
    mock_mongodb,
    mock_dashboards_collection,
    mock_kiosk_collection,
    sample_user,
):
    """POST /dashboards/{id}/kiosk-tokens → 201 with 'token' field in response."""
    board = _make_board()
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    # _get_owned_board calls find_one on dashboards collection
    mock_dashboards_collection.find_one = AsyncMock(return_value=board)

    inserted: dict = {}

    async def _capture_insert(doc):
        inserted.update(doc)

    mock_kiosk_collection.insert_one = AsyncMock(side_effect=_capture_insert)

    resp = await async_client.post(
        "/api/v1/dashboards/board_kiosk01/kiosk-tokens",
        json={"label": "Test kiosk token", "ttlHours": 24},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]

    # raw token must be present and non-empty
    assert "token" in data
    assert len(data["token"]) > 0

    # tokenHash must NOT be in the response
    assert "tokenHash" not in data

    # DB document must contain a hash, not the raw token
    assert "tokenHash" in inserted
    assert inserted["tokenHash"] != data["token"]

    # Basic bcrypt verification
    assert _verify_token(data["token"], inserted["tokenHash"])

    # Other fields
    assert data["boardId"] == "board_kiosk01"
    assert data["label"] == "Test kiosk token"
    assert data["createdBy"] == "user_admin123"
    assert data["revokedAt"] is None
    assert data["lastUsedAt"] is None
    assert data["expiresAt"] is not None  # ttlHours=24 set expiry


async def test_never_expire_token(
    async_client: AsyncClient,
    admin_headers,
    mock_mongodb,
    mock_dashboards_collection,
    mock_kiosk_collection,
    sample_user,
):
    """POST with ttlHours=null → expiresAt is null in response and DB."""
    board = _make_board()
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.find_one = AsyncMock(return_value=board)

    inserted: dict = {}

    async def _capture_insert(doc):
        inserted.update(doc)

    mock_kiosk_collection.insert_one = AsyncMock(side_effect=_capture_insert)

    resp = await async_client.post(
        "/api/v1/dashboards/board_kiosk01/kiosk-tokens",
        json={"label": "Never-expire token", "ttlHours": None},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["expiresAt"] is None
    assert inserted["expiresAt"] is None


async def test_list_kiosk_tokens_omits_raw_token(
    async_client: AsyncClient,
    admin_headers,
    mock_mongodb,
    mock_dashboards_collection,
    mock_kiosk_collection,
    sample_user,
):
    """GET /dashboards/{id}/kiosk-tokens → list omits 'token' and 'tokenHash'."""
    board = _make_board()
    tok_doc = _make_token_doc()
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.find_one = AsyncMock(return_value=board)
    # Simulate cursor.sort().find() → cursor with one document
    mock_kiosk_collection.find = MagicMock(
        return_value=create_mock_cursor([tok_doc])
    )

    resp = await async_client.get(
        "/api/v1/dashboards/board_kiosk01/kiosk-tokens",
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]
    assert len(items) == 1

    item = items[0]
    assert "token" not in item
    assert "tokenHash" not in item
    assert item["tokenId"] == tok_doc["tokenId"]
    assert item["boardId"] == tok_doc["boardId"]
    assert item["label"] == tok_doc["label"]


async def test_revoke_kiosk_token_sets_revoked_at(
    async_client: AsyncClient,
    admin_headers,
    mock_mongodb,
    mock_dashboards_collection,
    mock_kiosk_collection,
    sample_user,
):
    """DELETE /dashboards/{id}/kiosk-tokens/{token_id} → 204; revokedAt set in DB."""
    board = _make_board()
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.find_one = AsyncMock(return_value=board)

    update_result = MagicMock()
    update_result.modified_count = 1
    mock_kiosk_collection.update_one = AsyncMock(return_value=update_result)

    resp = await async_client.delete(
        "/api/v1/dashboards/board_kiosk01/kiosk-tokens/kt_aabbccdd11223344",
        headers=admin_headers,
    )
    assert resp.status_code == 204, resp.text

    # The update_one was called with revokedAt filter and $set revokedAt
    mock_kiosk_collection.update_one.assert_called_once()
    call_args = mock_kiosk_collection.update_one.call_args
    query_filter = call_args[0][0]
    update_doc = call_args[0][1]
    assert query_filter["revokedAt"] is None
    assert "revokedAt" in update_doc["$set"]


async def test_revoke_nonexistent_token_returns_404(
    async_client: AsyncClient,
    admin_headers,
    mock_mongodb,
    mock_dashboards_collection,
    mock_kiosk_collection,
    sample_user,
):
    """DELETE for a token that doesn't exist (or is already revoked) → 404."""
    board = _make_board()
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.find_one = AsyncMock(return_value=board)

    update_result = MagicMock()
    update_result.modified_count = 0
    mock_kiosk_collection.update_one = AsyncMock(return_value=update_result)

    resp = await async_client.delete(
        "/api/v1/dashboards/board_kiosk01/kiosk-tokens/kt_doesnotexist",
        headers=admin_headers,
    )
    assert resp.status_code == 404, resp.text


# ── Kiosk route tests ─────────────────────────────────────────────────


async def test_kiosk_route_strips_control_widgets(
    async_client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    mock_kiosk_collection,
    board_with_control_widget,
):
    """GET /dashboards/kiosk/{id}?token=X → control widget has readonly=True."""
    raw_token = _generate_raw_token()
    tok_doc = _make_token_doc(raw=raw_token)
    tok_doc.pop("_raw", None)

    mock_dashboards_collection.find_one = AsyncMock(return_value=board_with_control_widget)
    mock_kiosk_collection.find = MagicMock(
        return_value=create_mock_cursor([tok_doc])
    )
    mock_kiosk_collection.update_one = AsyncMock()

    resp = await async_client.get(
        f"/api/v1/dashboards/kiosk/board_kiosk01?token={raw_token}"
    )
    assert resp.status_code == 200, resp.text

    widgets = resp.json()["data"]["widgets"]
    assert len(widgets) == 1
    assert widgets[0]["widgetType"] == "hydra::quick-action"
    # quick-action has kioskMode='readonly' → readonly=True
    assert widgets[0]["readonly"] is True


async def test_kiosk_route_rejects_invalid_token(
    async_client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    mock_kiosk_collection,
):
    """GET /dashboards/kiosk/{id}?token=BOGUS → 401."""
    mock_kiosk_collection.find = MagicMock(
        return_value=create_mock_cursor([])  # no matching tokens
    )

    resp = await async_client.get(
        "/api/v1/dashboards/kiosk/board_kiosk01?token=definitely-not-valid"
    )
    assert resp.status_code == 401, resp.text


async def test_kiosk_route_rejects_revoked_token(
    async_client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    mock_kiosk_collection,
):
    """GET /dashboards/kiosk/{id}?token=X after revocation → 401.

    Revoked tokens have revokedAt set, so the validate query filter
    (revokedAt: null) excludes them — the cursor returns no candidates.
    """
    # Revoked token documents are excluded by the query filter, so
    # simulate the cursor returning no candidates.
    mock_kiosk_collection.find = MagicMock(
        return_value=create_mock_cursor([])
    )

    resp = await async_client.get(
        "/api/v1/dashboards/kiosk/board_kiosk01?token=sometoken"
    )
    assert resp.status_code == 401, resp.text


async def test_kiosk_route_rejects_expired_token(
    async_client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    mock_kiosk_collection,
):
    """GET /dashboards/kiosk/{id}?token=X past expiry → 401.

    Expired tokens are excluded by the ($or expiresAt > now) query filter.
    Simulate by returning an empty cursor (as the DB would).
    """
    # Expired tokens are filtered server-side; simulate empty cursor.
    mock_kiosk_collection.find = MagicMock(
        return_value=create_mock_cursor([])
    )

    resp = await async_client.get(
        "/api/v1/dashboards/kiosk/board_kiosk01?token=expiredtoken"
    )
    assert resp.status_code == 401, resp.text


async def test_kiosk_route_strips_hidden_widgets(
    async_client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    mock_kiosk_collection,
    board_with_hidden_widget,
):
    """Widgets with kioskMode='hide' are absent from the kiosk response.

    We temporarily register a test widget type with kioskMode='hide' so the
    sanitizer can look it up, then clean up via reset_to_builtins.
    """
    widget_registry.register(
        {
            "widgetType": "test::hidden-widget",
            "displayName": "Hidden Test Widget",
            "description": "Only for test",
            "category": "external-embed",
            "icon": "eye-off",
            "source": "test",
            "version": "1.0.0",
            "supportedDataShapes": [],
            "tags": [],
            "permissions": {"view": ["admin"], "interact": []},
            "defaultSize": {"w": 3, "h": 2},
            "minSize": {"w": 2, "h": 2},
            "maxSize": {"w": 6, "h": 4},
            "configSchema": [],
            "kioskMode": "hide",
            "isAvailable": True,
            "capabilities": {"configurable": False, "supportsVisibilityToggle": True, "repeatable": True},
        }
    )

    raw_token = _generate_raw_token()
    tok_doc = _make_token_doc(
        board_id=board_with_hidden_widget["boardId"],
        raw=raw_token,
    )
    tok_doc.pop("_raw", None)

    mock_dashboards_collection.find_one = AsyncMock(return_value=board_with_hidden_widget)
    mock_kiosk_collection.find = MagicMock(
        return_value=create_mock_cursor([tok_doc])
    )
    mock_kiosk_collection.update_one = AsyncMock()

    try:
        resp = await async_client.get(
            f"/api/v1/dashboards/kiosk/{board_with_hidden_widget['boardId']}?token={raw_token}"
        )
        assert resp.status_code == 200, resp.text
        widgets = resp.json()["data"]["widgets"]
        # The hidden widget must be absent
        assert all(w["widgetType"] != "test::hidden-widget" for w in widgets)
        assert len(widgets) == 0
    finally:
        widget_registry.unregister("test::hidden-widget")


async def test_kiosk_last_used_at_updated(
    async_client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    mock_kiosk_collection,
    board_with_control_widget,
):
    """After a successful GET, update_one is called to set lastUsedAt."""
    raw_token = _generate_raw_token()
    tok_doc = _make_token_doc(raw=raw_token)
    tok_doc.pop("_raw", None)

    mock_dashboards_collection.find_one = AsyncMock(return_value=board_with_control_widget)
    mock_kiosk_collection.find = MagicMock(
        return_value=create_mock_cursor([tok_doc])
    )
    mock_kiosk_collection.update_one = AsyncMock()

    resp = await async_client.get(
        f"/api/v1/dashboards/kiosk/board_kiosk01?token={raw_token}"
    )
    assert resp.status_code == 200, resp.text

    # update_one must have been called with lastUsedAt in the $set
    mock_kiosk_collection.update_one.assert_called_once()
    call_args = mock_kiosk_collection.update_one.call_args
    update_doc = call_args[0][1]
    assert "lastUsedAt" in update_doc["$set"]


# ── Sanitizer unit tests ──────────────────────────────────────────────


def test_sanitizer_readonly_widget():
    """Widgets with kioskMode='readonly' get readonly=True."""
    board = _make_board(
        widgets=[
            {
                "instanceId": "wi_001",
                "widgetType": "hydra::quick-action",
                "config": {},
                "position": {"x": 0, "y": 0, "w": 3, "h": 2},
                "placements": {"lg": {"x": 0, "y": 0, "w": 3, "h": 2}},
                "dataBinding": None,
            }
        ]
    )
    result = sanitize_for_kiosk(board)
    assert len(result["widgets"]) == 1
    assert result["widgets"][0]["readonly"] is True


def test_sanitizer_render_widget():
    """Widgets with kioskMode='render' get readonly=False."""
    board = _make_board(
        widgets=[
            {
                "instanceId": "wi_002",
                "widgetType": "hydra::stats-cards",
                "config": {},
                "position": {"x": 0, "y": 0, "w": 12, "h": 2},
                "placements": {"lg": {"x": 0, "y": 0, "w": 12, "h": 2}},
                "dataBinding": None,
            }
        ]
    )
    result = sanitize_for_kiosk(board)
    assert len(result["widgets"]) == 1
    assert result["widgets"][0]["readonly"] is False


def test_sanitizer_unknown_widget_defaults_to_readonly():
    """Widgets not in the registry get readonly=True (fail closed)."""
    board = _make_board(
        widgets=[
            {
                "instanceId": "wi_unknown",
                "widgetType": "plugin::unknown-future-type",
                "config": {},
                "position": {"x": 0, "y": 0, "w": 4, "h": 2},
                "placements": {"lg": {"x": 0, "y": 0, "w": 4, "h": 2}},
                "dataBinding": None,
            }
        ]
    )
    result = sanitize_for_kiosk(board)
    assert len(result["widgets"]) == 1
    assert result["widgets"][0]["readonly"] is True


def test_sanitizer_empty_board():
    """Empty widgets list returns empty widgets list."""
    board = _make_board(widgets=[])
    result = sanitize_for_kiosk(board)
    assert result["widgets"] == []
    assert result["boardId"] == board["boardId"]


# ── KioskService unit tests ───────────────────────────────────────────


def test_verify_token_wrong_hash():
    """_verify_token returns False for mismatched token."""
    raw = _generate_raw_token()
    hashed = _hash_token(raw)
    other = _generate_raw_token()
    assert _verify_token(other, hashed) is False


def test_verify_token_correct():
    """_verify_token returns True for correct pairing."""
    raw = _generate_raw_token()
    hashed = _hash_token(raw)
    assert _verify_token(raw, hashed) is True


def test_verify_token_bad_hash_string():
    """_verify_token returns False (no exception) for a corrupt hash string."""
    assert _verify_token("any_token", "not-a-valid-bcrypt-hash") is False


# ── New tests: admin bypass, double-revoke, deleted board ────────────


@pytest.fixture
def operator_token(test_settings) -> str:
    """Create an operator JWT token for cross-board kiosk management tests."""
    settings = get_settings()
    return create_access_token(
        subject="user_op456",
        token_type="access",
        additional_claims={
            "sub_type": "user",
            "role": "operator",
            "permissions": [
                "dashboards:read",
                "dashboards:write",
            ],
        },
        settings=settings,
    )


@pytest.fixture
def operator_headers(operator_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {operator_token}"}


@pytest.fixture
def test_board():
    """A board owned by the admin user, used for token management tests."""
    return _make_board(board_id="board_testmgmt01", owner_id="user_admin123")


async def test_kiosk_route_returns_404_for_deleted_board(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
    mock_mongodb,
    mock_dashboards_collection,
    mock_kiosk_collection,
    sample_user,
):
    """Kiosk route with valid token but board soft-deleted returns 404.

    The validate step succeeds (token is still active), but the subsequent
    get_board call filters {archivedAt: None} and finds nothing → 404.
    """
    raw_token = _generate_raw_token()
    tok_doc = _make_token_doc(raw=raw_token)
    tok_doc.pop("_raw", None)

    # First find_one: kiosk validate does NOT use dashboards collection, so
    # dashboards collection find_one returns None (board is archived).
    mock_dashboards_collection.find_one = AsyncMock(return_value=None)

    # kiosk_tokens cursor returns the valid (not revoked/expired) token
    mock_kiosk_collection.find = MagicMock(
        return_value=create_mock_cursor([tok_doc])
    )
    mock_kiosk_collection.update_one = AsyncMock()

    resp = await async_client.get(
        f"/api/v1/dashboards/kiosk/board_kiosk01?token={raw_token}"
    )
    # validate() succeeds; get_board() filters {archivedAt: None} → DashboardNotFoundError → 404
    assert resp.status_code == 404, (
        f"Expected 404 after board soft-deletion, got {resp.status_code}: {resp.text}"
    )


async def test_revoke_already_revoked_token_returns_404(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
    mock_mongodb,
    mock_dashboards_collection,
    mock_kiosk_collection,
    test_board,
    sample_user,
):
    """Revoking an already-revoked token returns 404.

    The revoke() method filters {revokedAt: None}; if modified_count == 0
    the router raises NotFoundError → 404.
    """
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_dashboards_collection.find_one = AsyncMock(return_value=test_board)

    # First revoke: succeeds
    first_result = MagicMock()
    first_result.modified_count = 1
    # Second revoke: token already revoked, modified_count == 0
    second_result = MagicMock()
    second_result.modified_count = 0

    mock_kiosk_collection.update_one = AsyncMock(
        side_effect=[first_result, second_result]
    )

    first = await async_client.delete(
        "/api/v1/dashboards/board_testmgmt01/kiosk-tokens/kt_aabbccdd11223344",
        headers=admin_headers,
    )
    assert first.status_code == 204, f"First revoke should succeed: {first.text}"

    # Second call: board find_one still needed (access check runs again)
    mock_dashboards_collection.find_one = AsyncMock(return_value=test_board)

    second = await async_client.delete(
        "/api/v1/dashboards/board_testmgmt01/kiosk-tokens/kt_aabbccdd11223344",
        headers=admin_headers,
    )
    assert second.status_code == 404, (
        f"Second revoke of already-revoked token should return 404, got {second.status_code}"
    )


async def test_admin_can_manage_kiosk_tokens_on_other_users_board(
    async_client: AsyncClient,
    admin_headers: dict[str, str],
    mock_mongodb,
    mock_dashboards_collection,
    mock_kiosk_collection,
    sample_user,
):
    """Admin can create, list, and revoke kiosk tokens on a board they do not own.

    The admin bypass in _get_board_for_kiosk_management skips the owner check
    and fetches the board directly, so all three operations succeed.
    """
    # Board owned by a different user (user_op456), not the admin
    other_users_board = _make_board(board_id="board_othersboard01", owner_id="user_op456")

    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    # ── CREATE ──
    mock_dashboards_collection.find_one = AsyncMock(return_value=other_users_board)

    inserted: dict = {}

    async def _capture_insert(doc):
        inserted.update(doc)

    mock_kiosk_collection.insert_one = AsyncMock(side_effect=_capture_insert)

    create_resp = await async_client.post(
        "/api/v1/dashboards/board_othersboard01/kiosk-tokens",
        json={"label": "Admin-managed token", "ttlHours": 2},
        headers=admin_headers,
    )
    assert create_resp.status_code == 201, (
        f"Admin should be able to create kiosk token on other's board: {create_resp.text}"
    )
    token_id = create_resp.json()["data"]["tokenId"]

    # ── LIST ──
    tok_doc = _make_token_doc(token_id=token_id, board_id="board_othersboard01")
    mock_dashboards_collection.find_one = AsyncMock(return_value=other_users_board)
    mock_kiosk_collection.find = MagicMock(
        return_value=create_mock_cursor([tok_doc])
    )

    list_resp = await async_client.get(
        "/api/v1/dashboards/board_othersboard01/kiosk-tokens",
        headers=admin_headers,
    )
    assert list_resp.status_code == 200, (
        f"Admin should be able to list kiosk tokens on other's board: {list_resp.text}"
    )
    assert len(list_resp.json()["data"]) >= 1

    # ── REVOKE ──
    revoke_result = MagicMock()
    revoke_result.modified_count = 1
    mock_dashboards_collection.find_one = AsyncMock(return_value=other_users_board)
    mock_kiosk_collection.update_one = AsyncMock(return_value=revoke_result)

    revoke_resp = await async_client.delete(
        f"/api/v1/dashboards/board_othersboard01/kiosk-tokens/{token_id}",
        headers=admin_headers,
    )
    assert revoke_resp.status_code == 204, (
        f"Admin should be able to revoke kiosk token on other's board: {revoke_resp.text}"
    )


async def test_operator_can_manage_kiosk_tokens_on_other_users_board(
    async_client: AsyncClient,
    operator_headers: dict[str, str],
    mock_mongodb,
    mock_dashboards_collection,
    mock_kiosk_collection,
    sample_user,
):
    """Operator role should ALSO be able to manage kiosk tokens on other users' boards.

    The operator bypass in DashboardService.get_board_for_management skips the
    owner check and fetches the board directly, so all three operations succeed.
    """
    # Board owned by admin (user_admin123), not the operator (user_op456)
    other_users_board = _make_board(board_id="board_opother01", owner_id="user_admin123")

    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_op456", "role": "operator"}
    )

    # ── CREATE ──
    mock_dashboards_collection.find_one = AsyncMock(return_value=other_users_board)

    inserted: dict = {}

    async def _capture_insert(doc):
        inserted.update(doc)

    mock_kiosk_collection.insert_one = AsyncMock(side_effect=_capture_insert)

    create_resp = await async_client.post(
        "/api/v1/dashboards/board_opother01/kiosk-tokens",
        json={"label": "Operator-managed token", "ttlHours": 4},
        headers=operator_headers,
    )
    assert create_resp.status_code == 201, (
        f"Operator should be able to create kiosk token on other's board: {create_resp.text}"
    )
    token_id = create_resp.json()["data"]["tokenId"]

    # ── LIST ──
    tok_doc = _make_token_doc(token_id=token_id, board_id="board_opother01")
    mock_dashboards_collection.find_one = AsyncMock(return_value=other_users_board)
    mock_kiosk_collection.find = MagicMock(
        return_value=create_mock_cursor([tok_doc])
    )

    list_resp = await async_client.get(
        "/api/v1/dashboards/board_opother01/kiosk-tokens",
        headers=operator_headers,
    )
    assert list_resp.status_code == 200, (
        f"Operator should be able to list kiosk tokens on other's board: {list_resp.text}"
    )
    assert len(list_resp.json()["data"]) >= 1

    # ── REVOKE ──
    revoke_result = MagicMock()
    revoke_result.modified_count = 1
    mock_dashboards_collection.find_one = AsyncMock(return_value=other_users_board)
    mock_kiosk_collection.update_one = AsyncMock(return_value=revoke_result)

    revoke_resp = await async_client.delete(
        f"/api/v1/dashboards/board_opother01/kiosk-tokens/{token_id}",
        headers=operator_headers,
    )
    assert revoke_resp.status_code == 204, (
        f"Operator should be able to revoke kiosk token on other's board: {revoke_resp.text}"
    )
