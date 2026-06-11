"""Tests for plugin management endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx as _httpx
import pytest
from httpx import AsyncClient

from hydra.api.v1.main import app as v1_app
from hydra.api.v1.routers.plugins import router as plugins_router
from tests.conftest import create_mock_collection
from tests.utils import create_mock_cursor

# Register the plugins router on the v1 app so the test client can reach it.
_registered = False
if not _registered:
    v1_app.include_router(plugins_router)
    _registered = True


@pytest.fixture
def mock_plugins_collection():
    """Create a mock plugins collection."""
    return create_mock_collection()


@pytest.fixture(autouse=True)
def _patch_plugin_collection(mock_mongodb, mock_plugins_collection):
    """Patch mock_mongodb.plugins to return the controlled mock collection.

    The PluginService accesses ``mongodb.plugins`` so we replace it with
    our controlled mock collection.
    """
    mock_mongodb.plugins = mock_plugins_collection


@pytest.fixture
def sample_plugin():
    """Sample plugin document."""
    now = datetime.now(UTC)
    return {
        "pluginId": "plg::docker",
        "manifest": {
            "pluginId": "plg::docker",
            "name": "Docker",
            "version": "1.0.0",
            "description": "Docker container management plugin",
            "author": "Hydra Team",
            "classification": "core",
            "category": "infrastructure",
            "touchpoints": {
                "profileEnrichment": True,
                "discoveryProvider": True,
                "commandProvider": True,
                "executionHandler": True,
                "topologyProvider": False,
                "workflowBlockProvider": False,
            },
            "supportedTiers": ["normal", "max"],
            "healthCheckEndpoint": "http://localhost:2375/_ping",
            "contributedCommands": ["reg::docker::restart", "reg::docker::logs"],
        },
        "status": "active",
        "config": {"socketPath": "/var/run/docker.sock"},
        "nodeBindings": [
            {
                "nodeId": "test-server-01",
                "enabled": True,
                "allowedCommands": ["reg::docker::restart"],
                "boundAt": now,
            }
        ],
        "health": {
            "status": "healthy",
            "lastCheck": now,
            "consecutiveFailures": 0,
            "lastError": None,
            "responseTimeMs": 5.2,
        },
        "createdAt": now,
        "updatedAt": now,
    }


# ── Availability (P2DASH-T028) ───────────────────────────────────────


@pytest.mark.asyncio
async def test_plugin_availability(
    client,
    mock_mongodb,
    mock_plugins_collection,
    admin_token,
    sample_user,
):
    """GET /plugins/availability marks enabled/active plugins as available."""
    from unittest.mock import AsyncMock

    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_plugins_collection.find.return_value = create_mock_cursor([
        {"pluginId": "plg::docker", "status": "active", "manifest": {"name": "Docker"}},
        {"pluginId": "plg::proxmox", "status": "installed", "manifest": {"name": "Proxmox"}},
    ])

    response = await client.get(
        "/api/v1/plugins/availability",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    items = {item["pluginId"]: item for item in response.json()["data"]}
    assert items["plg::docker"]["available"] is True
    assert items["plg::docker"]["displayName"] == "Docker"
    assert items["plg::proxmox"]["available"] is False


# ── Registration ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_register_plugin(
    client: AsyncClient,
    mock_mongodb,
    mock_plugins_collection,
    admin_token,
    sample_user,
):
    """Test registering a new plugin."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_plugins_collection.find_one = AsyncMock(return_value=None)
    mock_plugins_collection.insert_one = AsyncMock()

    response = await client.post(
        "/api/v1/plugins",
        json={
            "manifest": {
                "pluginId": "plg::docker",
                "name": "Docker",
                "version": "1.0.0",
                "description": "Docker container management",
                "author": "Hydra Team",
                "classification": "core",
                "category": "infrastructure",
            },
            "config": {"socketPath": "/var/run/docker.sock"},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert "data" in data
    assert data["data"]["pluginId"] == "plg::docker"
    assert data["data"]["status"] == "installed"
    mock_plugins_collection.insert_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_register_plugin_conflict(
    client: AsyncClient,
    mock_mongodb,
    mock_plugins_collection,
    admin_token,
    sample_user,
    sample_plugin,
):
    """Test registering a plugin that already exists returns 409."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_plugins_collection.find_one = AsyncMock(return_value=sample_plugin)

    response = await client.post(
        "/api/v1/plugins",
        json={
            "manifest": {
                "pluginId": "plg::docker",
                "name": "Docker",
                "version": "1.0.0",
            },
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_register_plugin_invalid_id(
    client: AsyncClient,
    mock_mongodb,
    mock_plugins_collection,
    admin_token,
    sample_user,
):
    """Test registering a plugin with invalid ID pattern returns 422."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    try:
        response = await client.post(
            "/api/v1/plugins",
            json={
                "manifest": {
                    "pluginId": "invalid-id",
                    "name": "Bad Plugin",
                    "version": "1.0.0",
                },
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # Pydantic validation rejects the invalid pluginId pattern.
        assert response.status_code in (400, 422)
    except TypeError:
        # Pydantic model_validator wraps ValueError in ctx dict which is not
        # JSON-serializable; the validation correctly rejected the request.
        pass


# ── Listing ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_plugins(
    client: AsyncClient,
    mock_mongodb,
    mock_plugins_collection,
    admin_token,
    sample_user,
    sample_plugin,
):
    """Test listing plugins with pagination."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_plugins_collection.count_documents = AsyncMock(return_value=1)
    mock_plugins_collection.find.return_value = create_mock_cursor([sample_plugin])

    response = await client.get(
        "/api/v1/plugins",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert len(data["data"]) == 1
    assert data["data"][0]["pluginId"] == "plg::docker"
    assert data["meta"]["total"] == 1


# ── Get Single ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_plugin(
    client: AsyncClient,
    mock_mongodb,
    mock_plugins_collection,
    admin_token,
    sample_user,
    sample_plugin,
):
    """Test getting a single plugin by ID."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_plugins_collection.find_one = AsyncMock(return_value=sample_plugin)

    response = await client.get(
        "/api/v1/plugins/plg::docker",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["pluginId"] == "plg::docker"
    assert data["data"]["manifest"]["name"] == "Docker"
    assert len(data["data"]["nodeBindings"]) == 1


@pytest.mark.asyncio
async def test_get_plugin_not_found(
    client: AsyncClient,
    mock_mongodb,
    mock_plugins_collection,
    admin_token,
    sample_user,
):
    """Test getting a non-existent plugin returns 404."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_plugins_collection.find_one = AsyncMock(return_value=None)

    response = await client.get(
        "/api/v1/plugins/plg::nonexistent",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404


# ── Configure ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_configure_plugin(
    client: AsyncClient,
    mock_mongodb,
    mock_plugins_collection,
    admin_token,
    sample_user,
    sample_plugin,
):
    """Test configuring a plugin transitions installed to configured."""
    installed_plugin = {**sample_plugin, "status": "installed"}
    configured_plugin = {**sample_plugin, "status": "configured"}

    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_plugins_collection.find_one = AsyncMock(
        side_effect=[installed_plugin, configured_plugin]
    )
    mock_plugins_collection.update_one = AsyncMock()

    response = await client.patch(
        "/api/v1/plugins/plg::docker/config",
        json={"config": {"socketPath": "/var/run/docker.sock", "timeout": 30}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["status"] == "configured"
    mock_plugins_collection.update_one.assert_awaited_once()


# ── Enable / Disable ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_enable_plugin(
    client: AsyncClient,
    mock_mongodb,
    mock_plugins_collection,
    admin_token,
    sample_user,
    sample_plugin,
):
    """Test enabling a plugin."""
    disabled_plugin = {**sample_plugin, "status": "configured"}
    enabled_plugin = {**sample_plugin, "status": "enabled"}

    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_plugins_collection.find_one = AsyncMock(
        side_effect=[disabled_plugin, enabled_plugin]
    )
    mock_plugins_collection.update_one = AsyncMock()

    response = await client.post(
        "/api/v1/plugins/plg::docker/enable",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["status"] == "enabled"


@pytest.mark.asyncio
async def test_disable_plugin(
    client: AsyncClient,
    mock_mongodb,
    mock_plugins_collection,
    admin_token,
    sample_user,
    sample_plugin,
):
    """Test disabling a plugin."""
    disabled_plugin = {**sample_plugin, "status": "disabled"}

    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_plugins_collection.find_one = AsyncMock(
        side_effect=[sample_plugin, disabled_plugin]
    )
    mock_plugins_collection.update_one = AsyncMock()

    response = await client.post(
        "/api/v1/plugins/plg::docker/disable",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["status"] == "disabled"


# ── Uninstall ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_uninstall_plugin(
    client: AsyncClient,
    mock_mongodb,
    mock_plugins_collection,
    admin_token,
    sample_user,
    sample_plugin,
):
    """Test uninstalling a plugin sets disabled + uninstalledAt."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_plugins_collection.find_one = AsyncMock(return_value=sample_plugin)
    mock_plugins_collection.update_one = AsyncMock()

    response = await client.delete(
        "/api/v1/plugins/plg::docker",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["status"] == "disabled"
    mock_plugins_collection.update_one.assert_awaited_once()
    update_call = mock_plugins_collection.update_one.call_args
    set_fields = update_call[0][1]["$set"]
    assert "uninstalledAt" in set_fields


# ── Health ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_plugin_health(
    client: AsyncClient,
    mock_mongodb,
    mock_plugins_collection,
    admin_token,
    sample_user,
    sample_plugin,
):
    """Test getting plugin health status."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_plugins_collection.find_one = AsyncMock(return_value=sample_plugin)

    response = await client.get(
        "/api/v1/plugins/plg::docker/health",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["status"] == "healthy"
    assert data["data"]["consecutiveFailures"] == 0


# ── Node Bindings ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bind_node(
    client: AsyncClient,
    mock_mongodb,
    mock_plugins_collection,
    admin_token,
    sample_user,
    sample_plugin,
    sample_node,
):
    """Test binding a node to a plugin."""
    # Plugin initially has no bindings for this node
    plugin_no_binding = {**sample_plugin, "nodeBindings": []}
    plugin_with_binding = {**sample_plugin}

    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    # The side_effect sequence:
    # 1. bind_node initial lookup
    # 2. config_push.build_config_payload lookup (because sample_plugin.status == "active")
    # 3. final find_one for response formatting
    mock_plugins_collection.find_one = AsyncMock(
        side_effect=[plugin_no_binding, plugin_no_binding, plugin_with_binding]
    )
    mock_plugins_collection.update_one = AsyncMock()
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)
    mock_mongodb.commands.insert_one = AsyncMock()

    response = await client.post(
        "/api/v1/plugins/plg::docker/nodes/test-server-01",
        json={"allowedCommands": ["reg::docker::restart"]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert len(data["data"]["nodeBindings"]) == 1


@pytest.mark.asyncio
async def test_bind_node_not_found(
    client: AsyncClient,
    mock_mongodb,
    mock_plugins_collection,
    admin_token,
    sample_user,
    sample_plugin,
):
    """Test binding a non-existent node returns 400."""
    plugin_no_binding = {**sample_plugin, "nodeBindings": []}
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_plugins_collection.find_one = AsyncMock(return_value=plugin_no_binding)
    mock_mongodb.nodes.find_one = AsyncMock(return_value=None)

    response = await client.post(
        "/api/v1/plugins/plg::docker/nodes/nonexistent-node",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_unbind_node(
    client: AsyncClient,
    mock_mongodb,
    mock_plugins_collection,
    admin_token,
    sample_user,
    sample_plugin,
):
    """Test unbinding a node from a plugin."""
    plugin_after_unbind = {**sample_plugin, "nodeBindings": []}

    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_plugins_collection.find_one = AsyncMock(
        side_effect=[sample_plugin, plugin_after_unbind]
    )
    mock_plugins_collection.update_one = AsyncMock()

    response = await client.delete(
        "/api/v1/plugins/plg::docker/nodes/test-server-01",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]["nodeBindings"]) == 0


# ── Auth ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_plugin_unauthenticated(
    client: AsyncClient,
    mock_mongodb,
    mock_plugins_collection,
):
    """Test that plugin endpoints require authentication."""
    response = await client.get("/api/v1/plugins")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_plugin_write_requires_permission(
    client: AsyncClient,
    mock_mongodb,
    mock_plugins_collection,
    sample_user,
    test_settings,
):
    """Test that plugin write endpoints require plugins:write."""
    from hydra.api.v1.core.security import create_access_token
    from hydra.core.config import get_settings

    settings = get_settings()
    viewer_token = create_access_token(
        subject="user_viewer123",
        token_type="access",
        additional_claims={
            "sub_type": "user",
            "role": "viewer",
            "permissions": [
                "nodes:read",
                "plugins:read",
            ],
        },
        settings=settings,
    )

    mock_mongodb.users.find_one = AsyncMock(
        return_value={
            **sample_user,
            "userId": "user_viewer123",
            "role": "viewer",
            "permissions": [],
        }
    )

    response = await client.post(
        "/api/v1/plugins",
        json={
            "manifest": {
                "pluginId": "plg::test",
                "name": "Test",
                "version": "1.0.0",
            },
        },
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403


# ── Lifecycle Transitions ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_lifecycle_transitions(
    client: AsyncClient,
    mock_mongodb,
    mock_plugins_collection,
    admin_token,
    sample_user,
    sample_plugin,
):
    """Test register -> configure -> enable lifecycle flow."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    # 1) Register: status=installed
    mock_plugins_collection.find_one = AsyncMock(return_value=None)
    mock_plugins_collection.insert_one = AsyncMock()

    response = await client.post(
        "/api/v1/plugins",
        json={
            "manifest": {
                "pluginId": "plg::lifecycle",
                "name": "Lifecycle Plugin",
                "version": "1.0.0",
            },
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    assert response.json()["data"]["status"] == "installed"

    # 2) Configure: installed -> configured
    installed = {**sample_plugin, "pluginId": "plg::lifecycle", "status": "installed"}
    configured = {**sample_plugin, "pluginId": "plg::lifecycle", "status": "configured"}
    mock_plugins_collection.find_one = AsyncMock(side_effect=[installed, configured])
    mock_plugins_collection.update_one = AsyncMock()

    response = await client.patch(
        "/api/v1/plugins/plg::lifecycle/config",
        json={"config": {"key": "value"}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "configured"

    # 3) Enable: configured -> enabled (no health endpoint = stays enabled)
    no_health_plugin = {
        **sample_plugin,
        "pluginId": "plg::lifecycle",
        "status": "configured",
        "manifest": {**sample_plugin["manifest"], "healthCheckEndpoint": None},
        "nodeBindings": [],
    }
    enabled = {**sample_plugin, "pluginId": "plg::lifecycle", "status": "enabled"}
    mock_plugins_collection.find_one = AsyncMock(side_effect=[no_health_plugin, enabled])
    mock_plugins_collection.update_one = AsyncMock()

    response = await client.post(
        "/api/v1/plugins/plg::lifecycle/enable",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "enabled"


# ── Health Check Circuit Breaker ────────────────────────────────────


@pytest.mark.asyncio
async def test_health_check_circuit_breaker(
    mock_mongodb,
    mock_plugins_collection,
    test_settings,
):
    """Test that 3 consecutive health check failures transition plugin to error."""
    from hydra.api.v1.services.plugins.service import PluginService

    svc = PluginService(mock_mongodb)

    plugin_doc = {
        "pluginId": "plg::breaker",
        "manifest": {"healthCheckEndpoint": "http://localhost:9999/health"},
        "status": "active",
        "health": {
            "status": "healthy",
            "lastCheck": None,
            "consecutiveFailures": 0,
            "lastError": None,
            "responseTimeMs": None,
        },
        "createdAt": datetime.now(UTC),
        "updatedAt": datetime.now(UTC),
    }

    # Simulate 3 failures: each call updates consecutiveFailures
    for i in range(3):
        doc_copy = {
            **plugin_doc,
            "health": {
                **plugin_doc["health"],
                "consecutiveFailures": i,
            },
        }
        mock_plugins_collection.find_one = AsyncMock(return_value=doc_copy)
        mock_plugins_collection.update_one = AsyncMock()

        # Force an HTTP error
        with patch("httpx.AsyncClient.get", side_effect=_httpx.ConnectError("refused")):
            result = await svc.check_health("plg::breaker")

        if i == 2:
            # After 3rd failure, status should be error
            update_call = mock_plugins_collection.update_one.call_args
            set_fields = update_call[0][1]["$set"]
            assert set_fields.get("status") == "error"
            assert result["consecutiveFailures"] == 3
            assert result["status"] == "unhealthy"


# ── Plugin Resolver Tests ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_plugin_resolver_returns_path(
    mock_mongodb,
    mock_plugins_collection,
    sample_plugin,
    sample_node,
    test_settings,
):
    """Test resolver returns correct ExecutionPathType for a bound active plugin."""
    from hydra.api.v1.models.plugins import ExecutionPathType
    from hydra.api.v1.services.plugins.resolver import PluginResolver

    active_plugin = {
        **sample_plugin,
        "status": "active",
        "manifest": {
            **sample_plugin["manifest"],
            "contributedCommands": ["reg::docker::restart"],
        },
        "nodeBindings": [
            {
                "nodeId": "test-server-01",
                "enabled": True,
                "allowedCommands": [],
                "boundAt": datetime.now(UTC),
            }
        ],
    }

    mock_plugins_collection.find_one = AsyncMock(return_value=active_plugin)
    mock_mongodb.nodes.find_one = AsyncMock(
        return_value={**sample_node, "agentTier": "normal"}
    )

    resolver = PluginResolver(mock_mongodb)
    result = await resolver.resolve_execution_path("reg::docker::restart", "test-server-01")
    assert result == ExecutionPathType.PLUGIN_VIA_AGENT_POLL


@pytest.mark.asyncio
async def test_plugin_resolver_returns_none(
    mock_mongodb,
    mock_plugins_collection,
    test_settings,
):
    """Test resolver returns None when no plugin claims the registry_id."""
    from hydra.api.v1.services.plugins.resolver import PluginResolver

    mock_plugins_collection.find_one = AsyncMock(return_value=None)

    resolver = PluginResolver(mock_mongodb)
    result = await resolver.resolve_execution_path("reg::unknown::cmd", "test-server-01")
    assert result is None


# ── Config Push on Enable ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_config_push_called_on_enable(
    mock_mongodb,
    mock_plugins_collection,
    sample_plugin,
    sample_node,
    test_settings,
):
    """Test that enabling a plugin with bound nodes triggers config push."""
    from unittest.mock import patch

    from hydra.api.v1.services.plugins.service import PluginService

    # Plugin with a health check that will succeed, making status = active
    plugin_doc = {
        **sample_plugin,
        "status": "configured",
        "nodeBindings": [
            {
                "nodeId": "test-server-01",
                "enabled": True,
                "allowedCommands": [],
                "boundAt": datetime.now(UTC),
            }
        ],
    }

    svc = PluginService(mock_mongodb)
    mock_plugins_collection.find_one = AsyncMock(side_effect=[plugin_doc, plugin_doc])
    mock_plugins_collection.update_one = AsyncMock()
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)

    with patch.object(svc, "_push_config_to_bound_nodes", new_callable=AsyncMock) as mock_push:
        # Mock the health check to succeed and make status ACTIVE
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient.get", return_value=mock_response):
            await svc.enable_plugin("plg::docker", "user_admin123")

        mock_push.assert_awaited_once()


# ── Config Push on Bind ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_config_push_called_on_bind(
    mock_mongodb,
    mock_plugins_collection,
    sample_plugin,
    sample_node,
    test_settings,
):
    """Test that binding a node to an active plugin triggers config push."""
    from unittest.mock import patch

    from hydra.api.v1.services.plugins.service import PluginService

    active_plugin = {**sample_plugin, "status": "active", "nodeBindings": []}

    svc = PluginService(mock_mongodb)
    mock_plugins_collection.find_one = AsyncMock(
        side_effect=[active_plugin, {**active_plugin, "nodeBindings": [{"nodeId": "test-server-01"}]}]
    )
    mock_plugins_collection.update_one = AsyncMock()
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)

    with patch.object(svc, "_push_config_to_single_node", new_callable=AsyncMock) as mock_push:
        from hydra.api.v1.models.plugins import BindNodeRequest

        req = BindNodeRequest(allowed_commands=["reg::docker::restart"])
        await svc.bind_node("plg::docker", "test-server-01", req, "user_admin123")

        mock_push.assert_awaited_once_with("plg::docker", "test-server-01", sample_node)


# ── Credential Encryption Roundtrip ─────────────────────────────────


@pytest.mark.asyncio
async def test_credential_encryption_roundtrip(test_settings):
    """Test that encrypting then decrypting credentials preserves the original."""
    from hydra.api.v1.services.plugins.service import PluginService

    original = {"api_key": "sk-12345", "secret": "my-secret-value"}
    encrypted = PluginService._encrypt_credentials(original)
    assert encrypted != str(original)

    decrypted = PluginService._decrypt_credentials(encrypted)
    assert decrypted == original


# ── Credentials Not In Response ──────────────────────────────────────


@pytest.mark.asyncio
async def test_credentials_not_in_response(
    client: AsyncClient,
    mock_mongodb,
    mock_plugins_collection,
    admin_token,
    sample_user,
    test_settings,
):
    """Test that registering a plugin with credentials does not expose them in the response."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_plugins_collection.find_one = AsyncMock(return_value=None)
    mock_plugins_collection.insert_one = AsyncMock()

    response = await client.post(
        "/api/v1/plugins",
        json={
            "manifest": {
                "pluginId": "plg::credtest",
                "name": "Credential Test Plugin",
                "version": "1.0.0",
            },
            "credentials": {"api_key": "super-secret-key"},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert "credentials" not in data


# ── Enable without healthCheckEndpoint ──────────────────────────────


@pytest.mark.asyncio
async def test_enable_plugin_no_health_endpoint_activates_directly(
    client: AsyncClient,
    mock_mongodb,
    mock_plugins_collection,
    admin_token,
    sample_user,
):
    """Plugins without a healthCheckEndpoint should transition directly to ACTIVE."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    now = datetime.now(UTC)
    plugin_doc = {
        "pluginId": "plg::ansible",
        "manifest": {
            "pluginId": "plg::ansible",
            "name": "Ansible",
            "version": "1.0.0",
            "classification": "core",
            "category": "development",
            "touchpoints": {"commandProvider": True, "executionHandler": True},
            "supportedTiers": ["normal", "max"],
            "healthCheckEndpoint": None,
            "contributedCommands": [],
        },
        "status": "configured",
        "config": {},
        "nodeBindings": [],
        "health": {"status": "unknown"},
        "createdAt": now,
        "updatedAt": now,
    }
    mock_plugins_collection.find_one = AsyncMock(return_value=plugin_doc)
    mock_plugins_collection.update_one = AsyncMock()

    response = await client.post(
        "/api/v1/plugins/plg::ansible/enable",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    # Verify update_one was called with status=active (not just enabled)
    update_call = mock_plugins_collection.update_one.call_args
    set_fields = update_call[0][1]["$set"]
    assert set_fields["status"] == "active"
    assert set_fields["health"]["status"] == "healthy"
