"""Wave 3 dashboard tests — template variables, version history, RBAC, and spec fields."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from hydra.api.v1.core.security import create_access_token
from hydra.api.v1.main import app as v1_app
from hydra.api.v1.routers.dashboards import router as dashboards_router
from hydra.core.config import get_settings
from tests.conftest import create_mock_collection
from tests.utils import create_mock_cursor

_registered = False
if not _registered:
    v1_app.include_router(dashboards_router)
    _registered = True


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
    mock_mongodb, mock_dashboards_collection, mock_templates_collection, mock_versions_collection,
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
def now():
    return datetime.now(UTC)


@pytest.fixture
def admin_user(sample_user):
    return {**sample_user, "userId": "user_admin123", "role": "admin"}


@pytest.fixture
def operator_user(sample_user):
    return {**sample_user, "userId": "user_op123", "role": "operator"}


@pytest.fixture
def viewer_user(sample_user):
    return {**sample_user, "userId": "user_view123", "role": "viewer"}


@pytest.fixture
def operator_token(test_settings) -> str:
    settings = get_settings()
    return create_access_token(
        subject="user_op123",
        token_type="access",
        additional_claims={
            "sub_type": "user",
            "role": "operator",
            "permissions": [
                "nodes:read", "nodes:write",
                "services:read", "services:write",
                "dashboards:read", "dashboards:write",
            ],
        },
        settings=settings,
    )


@pytest.fixture
def sample_board(now):
    return {
        "boardId": "board_wave3_test",
        "name": "Test Board",
        "description": "Wave 3 test board",
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
                "instanceId": "wi_test001",
                "widgetType": "hydra::stats-cards",
                "position": {"x": 0, "y": 0, "w": 12, "h": 2},
                "config": {"title": "Node Count", "endpoint": "{{apiBase}}/nodes"},
                "dataBinding": {
                    "source": "hydra::",
                    "query": {"endpoint": "{{apiBase}}/nodes", "params": {}},
                },
            },
            {
                "instanceId": "wi_test002",
                "widgetType": "hydra::service-list",
                "position": {"x": 0, "y": 2, "w": 6, "h": 3},
                "config": {"nodeId": "{{targetNode}}"},
                "dataBinding": None,
            },
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
        "tags": ["infrastructure"],
        "isHome": False,
        "version": 3,
        "clonedFrom": None,
        "createdAt": now,
        "updatedAt": now,
        "archivedAt": None,
    }


@pytest.fixture
def sample_template_with_variables(now):
    return {
        "templateId": "tmpl_vars_test",
        "name": "Parameterized Template",
        "description": "Template with variables for testing",
        "boardType": "user",
        "category": "infrastructure",
        "targetRoles": ["admin", "operator"],
        "requiredPlugins": [],
        "optionalPlugins": ["docker"],
        "source": "user",
        "variables": {
            "targetNode": {
                "type": "node-selector",
                "label": "Target Node",
                "description": "Select the node to monitor",
                "default": None,
                "required": True,
                "options": None,
            },
            "apiBase": {
                "type": "text",
                "label": "API Base URL",
                "description": "Base API URL",
                "default": "/api/v1",
                "required": False,
                "options": None,
            },
            "refreshRate": {
                "type": "select",
                "label": "Refresh Rate",
                "description": "How often to refresh data",
                "default": "30",
                "required": False,
                "options": ["10", "30", "60", "300"],
            },
        },
        "layout": {"columns": 12, "rowHeight": 80, "breakpoints": {}},
        "widgets": [
            {
                "widgetType": "hydra::stats-cards",
                "position": {"x": 0, "y": 0, "w": 12, "h": 2},
                "config": {"title": "Stats", "endpoint": "{{apiBase}}/nodes"},
                "dataBinding": {
                    "source": "hydra::",
                    "query": {"endpoint": "{{apiBase}}/nodes", "params": {}},
                },
            },
            {
                "widgetType": "hydra::service-list",
                "position": {"x": 0, "y": 2, "w": 6, "h": 3},
                "config": {"nodeId": "{{targetNode}}"},
                "dataBinding": None,
            },
        ],
        "settings": {"theme": "inherit"},
        "tags": ["parameterized"],
        "widgetCount": 2,
        "createdBy": "user_admin123",
        "sourceBoard": "board_wave3_test",
        "createdAt": now,
        "updatedAt": now,
    }


# ── T023: Template Spec Fields ───────────────────────────────────────


@pytest.mark.asyncio
async def test_save_as_template_with_spec_fields(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    mock_templates_collection,
    admin_token,
    admin_user,
    sample_board,
):
    """Templates include category, targetRoles, requiredPlugins, optionalPlugins."""
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)
    mock_dashboards_collection.find_one = AsyncMock(return_value=sample_board)
    mock_templates_collection.insert_one = AsyncMock()

    response = await client.post(
        "/api/v1/dashboards/board_wave3_test/save-as-template",
        json={
            "name": "Spec-Aligned Template",
            "description": "Has all spec fields",
            "category": "infrastructure",
            "targetRoles": ["admin", "operator"],
            "requiredPlugins": ["docker"],
            "optionalPlugins": ["prometheus"],
            "tags": ["spec-test"],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["name"] == "Spec-Aligned Template"
    assert data["category"] == "infrastructure"
    assert data["targetRoles"] == ["admin", "operator"]
    assert data["requiredPlugins"] == ["docker"]
    assert data["optionalPlugins"] == ["prometheus"]


@pytest.mark.asyncio
async def test_save_as_template_variables_field(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    mock_templates_collection,
    admin_token,
    admin_user,
    sample_board,
):
    """Templates can include variable definitions."""
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)
    mock_dashboards_collection.find_one = AsyncMock(return_value=sample_board)
    mock_templates_collection.insert_one = AsyncMock()

    response = await client.post(
        "/api/v1/dashboards/board_wave3_test/save-as-template",
        json={
            "name": "Variable Template",
            "variables": {
                "nodeId": {
                    "type": "node-selector",
                    "label": "Target Node",
                    "required": True,
                },
                "interval": {
                    "type": "select",
                    "label": "Refresh Interval",
                    "default": "30",
                    "required": False,
                    "options": ["10", "30", "60"],
                },
            },
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert "variables" in data
    assert "nodeId" in data["variables"]
    assert data["variables"]["nodeId"]["type"] == "node-selector"
    assert data["variables"]["nodeId"]["required"] is True
    assert data["variables"]["interval"]["options"] == ["10", "30", "60"]


# ── T024 + T040: Template Variables & Clone with Variables ───────────


@pytest.mark.asyncio
async def test_instantiate_template_with_variables(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    mock_templates_collection,
    admin_token,
    admin_user,
    sample_template_with_variables,
):
    """Template instantiation resolves {{variable}} placeholders."""
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)
    mock_templates_collection.find_one = AsyncMock(return_value=sample_template_with_variables)
    mock_dashboards_collection.insert_one = AsyncMock()

    response = await client.post(
        "/api/v1/dashboards/templates/tmpl_vars_test/instantiate",
        json={
            "name": "My Node Board",
            "variables": {
                "targetNode": "proxmox-01",
                "apiBase": "/api/v2",
            },
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["name"] == "My Node Board"
    # Verify variable substitution in widget config
    widgets = data["widgets"]
    assert len(widgets) == 2
    # Widget 1: endpoint should have {{apiBase}} replaced
    assert widgets[0]["config"]["endpoint"] == "/api/v2/nodes"
    # Widget 2: nodeId should have {{targetNode}} replaced
    assert widgets[1]["config"]["nodeId"] == "proxmox-01"


@pytest.mark.asyncio
async def test_instantiate_template_missing_required_variable(
    client: AsyncClient,
    mock_mongodb,
    mock_templates_collection,
    admin_token,
    admin_user,
    sample_template_with_variables,
):
    """Instantiation fails when required variable is not provided."""
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)
    mock_templates_collection.find_one = AsyncMock(return_value=sample_template_with_variables)

    response = await client.post(
        "/api/v1/dashboards/templates/tmpl_vars_test/instantiate",
        json={
            "name": "Missing Required",
            "variables": {
                "apiBase": "/api/v1",
                # targetNode is required but not provided
            },
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_instantiate_template_defaults_applied(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    mock_templates_collection,
    admin_token,
    admin_user,
    sample_template_with_variables,
):
    """Optional variables with defaults are applied when not provided."""
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)
    mock_templates_collection.find_one = AsyncMock(return_value=sample_template_with_variables)
    mock_dashboards_collection.insert_one = AsyncMock()

    response = await client.post(
        "/api/v1/dashboards/templates/tmpl_vars_test/instantiate",
        json={
            "name": "Defaults Board",
            "variables": {
                "targetNode": "ha-core",
                # apiBase has default "/api/v1", should be used
            },
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    # Default apiBase should be applied
    assert data["widgets"][0]["config"]["endpoint"] == "/api/v1/nodes"


@pytest.mark.asyncio
async def test_clone_with_variables(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    mock_versions_collection,
    admin_token,
    admin_user,
    sample_board,
):
    """Clone endpoint accepts variables for substitution."""
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)
    mock_dashboards_collection.find_one = AsyncMock(return_value=sample_board)
    mock_dashboards_collection.insert_one = AsyncMock()
    mock_versions_collection.insert_one = AsyncMock()

    response = await client.post(
        "/api/v1/dashboards/board_wave3_test/clone",
        json={
            "name": "Cloned with Vars",
            "variables": {
                "apiBase": "/api/v2",
                "targetNode": "opnsense.gw",
            },
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["name"] == "Cloned with Vars"
    # Variables should be substituted in cloned widgets
    assert data["widgets"][0]["config"]["endpoint"] == "/api/v2/nodes"
    assert data["widgets"][1]["config"]["nodeId"] == "opnsense.gw"


# ── T005: Version History ────────────────────────────────────────────


@pytest.fixture
def sample_version_snapshot(now, sample_board):
    return {
        "boardId": "board_wave3_test",
        "version": 2,
        "snapshot": sample_board,
        "savedBy": "user_admin123",
        "savedAt": now,
        "changeDescription": "Updated layout",
    }


@pytest.mark.asyncio
async def test_list_versions(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    mock_versions_collection,
    admin_token,
    admin_user,
    sample_board,
    sample_version_snapshot,
):
    """List version history for a board."""
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)
    mock_dashboards_collection.find_one = AsyncMock(return_value=sample_board)
    mock_versions_collection.count_documents = AsyncMock(return_value=1)
    mock_versions_collection.find = MagicMock(
        return_value=create_mock_cursor([sample_version_snapshot])
    )

    response = await client.get(
        "/api/v1/dashboards/board_wave3_test/versions",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["version"] == 2
    assert data[0]["savedBy"] == "user_admin123"
    assert data[0]["changeDescription"] == "Updated layout"


@pytest.mark.asyncio
async def test_get_version_snapshot(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    mock_versions_collection,
    admin_token,
    admin_user,
    sample_board,
    sample_version_snapshot,
):
    """Retrieve a specific version snapshot."""
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)
    mock_dashboards_collection.find_one = AsyncMock(return_value=sample_board)
    mock_versions_collection.find_one = AsyncMock(return_value=sample_version_snapshot)

    response = await client.get(
        "/api/v1/dashboards/board_wave3_test/versions/2",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["version"] == 2
    assert "snapshot" in data
    assert data["snapshot"]["boardId"] == "board_wave3_test"


@pytest.mark.asyncio
async def test_restore_version(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    mock_versions_collection,
    admin_token,
    admin_user,
    sample_board,
    sample_version_snapshot,
):
    """Restore a board to a previous version creates a new version."""
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)
    mock_dashboards_collection.find_one = AsyncMock(return_value=sample_board)
    mock_versions_collection.find_one = AsyncMock(return_value=sample_version_snapshot)
    mock_dashboards_collection.update_one = AsyncMock()
    mock_versions_collection.insert_one = AsyncMock()

    response = await client.post(
        "/api/v1/dashboards/board_wave3_test/restore/2",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["boardId"] == "board_wave3_test"
    # Version snapshots should be created (pre-restore + post-restore)
    assert mock_versions_collection.insert_one.await_count >= 1


# ── T025: Role-Based Access Controls ────────────────────────────────


@pytest.mark.asyncio
async def test_save_template_admin_only(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    operator_token,
    operator_user,
    sample_board,
):
    """Non-admin users cannot create templates."""
    mock_mongodb.users.find_one = AsyncMock(return_value=operator_user)
    mock_dashboards_collection.find_one = AsyncMock(return_value=sample_board)

    response = await client.post(
        "/api/v1/dashboards/board_wave3_test/save-as-template",
        json={"name": "Operator Template"},
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_template_role_filtering(
    client: AsyncClient,
    mock_mongodb,
    mock_templates_collection,
    admin_token,
    admin_user,
    sample_template_with_variables,
    now,
):
    """Templates filtered by user role via targetRoles."""
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    # The template has targetRoles: ["admin", "operator"]
    mock_templates_collection.count_documents = AsyncMock(return_value=1)
    mock_templates_collection.find = MagicMock(
        return_value=create_mock_cursor([sample_template_with_variables])
    )

    response = await client.get(
        "/api/v1/dashboards/templates",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) >= 1
    assert data[0]["targetRoles"] == ["admin", "operator"]


@pytest.mark.asyncio
async def test_share_requires_admin_or_operator(
    client: AsyncClient,
    mock_mongodb,
    mock_dashboards_collection,
    viewer_token,
    viewer_user,
    sample_board,
):
    """Viewers cannot share dashboards."""
    mock_mongodb.users.find_one = AsyncMock(return_value=viewer_user)
    mock_dashboards_collection.find_one = AsyncMock(return_value=sample_board)

    response = await client.post(
        "/api/v1/dashboards/board_wave3_test/share",
        json={"scope": "public"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403
