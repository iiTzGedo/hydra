"""Integration tests for command dispatch through the plugin resolver.

Verifies:
- Plugin command creation with correct metadata
- Tier-based routing (normal → poll, max → direct, lite → rejected)
- Multi-node plugin command dispatch
- Plugin config delivery and status transitions
- Dry-run plugin commands
- Unknown plugin rejection
- Plugin lifecycle effects on command acceptance
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from tests.utils import create_mock_cursor

# ── Helpers ─────────────────────────────────────────────────────────────


def _mock_insert_one_result() -> MagicMock:
    """Return a mock that mimics pymongo InsertOneResult."""
    from bson import ObjectId

    result = MagicMock()
    result.inserted_id = ObjectId()
    result.acknowledged = True
    return result


def trusted_write_headers(
    *,
    user_id: str = "user_admin123",
    role: str = "admin",
    client_id: str = "hydra-web",
) -> dict[str, str]:
    """Build trusted internal-request headers for write-path tests."""
    return {
        "X-Hydra-Internal-Request": "true",
        "X-Hydra-Internal-Secret": "internal-secret-for-tests-0123456789",
        "X-Hydra-User-Id": user_id,
        "X-Hydra-Role": role,
        "X-Hydra-Client-Id": client_id,
    }


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def sample_user():
    """Sample admin user document."""
    now = datetime.now(UTC)
    return {
        "userId": "user_admin123",
        "username": "testadmin",
        "email": "admin@example.com",
        "passwordHash": "$2b$12$test",
        "role": "admin",
        "permissions": ["*:*"],
        "status": "active",
        "createdAt": now,
        "updatedAt": now,
    }


@pytest.fixture
def docker_plugin_doc():
    """Sample active Docker plugin document with node bindings."""
    now = datetime.now(UTC)
    return {
        "pluginId": "plg::docker",
        "manifest": {
            "pluginId": "plg::docker",
            "name": "Docker Engine",
            "version": "0.5.0",
            "description": "Docker container management",
            "author": "Hydra Team",
            "classification": "core",
            "category": "infrastructure",
            "touchpoints": {
                "profileEnrichment": True,
                "commandProvider": True,
                "executionHandler": True,
            },
            "supportedTiers": ["normal", "max"],
            "healthCheckEndpoint": None,
            "contributedCommands": [
                "reg::node::docker-list-containers",
                "reg::node::docker-pull-image",
            ],
        },
        "status": "active",
        "config": {"socketPath": "/var/run/docker.sock"},
        "nodeBindings": [
            {
                "nodeId": "server-01",
                "enabled": True,
                "allowedCommands": [],
                "boundAt": now,
            },
            {
                "nodeId": "server-02",
                "enabled": True,
                "allowedCommands": [],
                "boundAt": now,
            },
            {
                "nodeId": "server-03",
                "enabled": True,
                "allowedCommands": [],
                "boundAt": now,
            },
        ],
        "health": {
            "status": "healthy",
            "lastCheck": now,
            "consecutiveFailures": 0,
            "lastError": None,
            "responseTimeMs": None,
        },
        "createdAt": now,
        "updatedAt": now,
    }


@pytest.fixture
def docker_list_definition():
    """Command definition for docker list-containers."""
    return {
        "registryId": "reg::node::docker-list-containers",
        "category": "node",
        "action": "docker::list-containers",
        "displayName": "List Docker Containers",
        "description": "List all Docker containers on a node",
        "targetSchema": {"required": ["nodeId"]},
        "parametersSchema": None,
        "execution": {
            "runtimes": {},
            "handler": "plugin",
            "timeout": 30,
            "deliveryMode": "poll_only",
            "retryable": False,
            "maxRetries": 0,
        },
        "rbac": {
            "minimumRole": "operator",
            "requiresConfirmation": False,
            "dangerLevel": "safe",
        },
        "audit": {"logLevel": "standard", "captureOutput": True, "sensitiveParameters": []},
        "metadata": {
            "version": "0.5.0",
            "addedAt": datetime.now(UTC),
            "builtIn": True,
            "deprecated": False,
        },
    }


@pytest.fixture
def docker_direct_definition():
    """Command definition with direct_or_poll delivery for max-tier test."""
    return {
        "registryId": "reg::node::docker-list-containers",
        "category": "node",
        "action": "docker::list-containers",
        "displayName": "List Docker Containers",
        "description": "List all Docker containers on a node",
        "targetSchema": {"required": ["nodeId"]},
        "parametersSchema": None,
        "execution": {
            "runtimes": {},
            "handler": "plugin",
            "timeout": 30,
            "deliveryMode": "direct_or_poll",
            "retryable": False,
            "maxRetries": 0,
        },
        "rbac": {
            "minimumRole": "operator",
            "requiresConfirmation": False,
            "dangerLevel": "safe",
        },
        "audit": {"logLevel": "standard", "captureOutput": True, "sensitiveParameters": []},
        "metadata": {
            "version": "0.5.0",
            "addedAt": datetime.now(UTC),
            "builtIn": True,
            "deprecated": False,
        },
    }


@pytest.fixture
def normal_tier_node():
    """Node with normal (poll-based) agent tier."""
    return {
        "nodeId": "server-01",
        "status": "active",
        "agentTier": "normal",
    }


@pytest.fixture
def max_tier_node():
    """Node with max (direct-capable) agent tier."""
    return {
        "nodeId": "server-01",
        "status": "active",
        "agentTier": "max",
        "serverAddress": "10.0.0.1",
        "serverPort": 9100,
        "serverTlsEnabled": False,
        "agentServerSecret": "test-secret-abc",
        "serverReachable": True,
    }


@pytest.fixture
def lite_tier_node():
    """Node with lite agent tier."""
    return {
        "nodeId": "server-01",
        "status": "active",
        "agentTier": "lite",
    }


def _setup_plugin_mocks(
    mock_mongodb,
    sample_user,
    definition,
    plugin_doc,
    node,
):
    """Set up common mocks for plugin command integration tests."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.command_definitions.find_one = AsyncMock(return_value=definition)
    mock_mongodb.commands.insert_one = AsyncMock(return_value=_mock_insert_one_result())
    mock_mongodb.commands.count_documents = AsyncMock(return_value=0)
    mock_mongodb.commands.update_one = AsyncMock()
    mock_mongodb.plugins.find_one = AsyncMock(return_value=plugin_doc)
    mock_mongodb.nodes.find_one = AsyncMock(return_value=node)
    mock_mongodb.services.find_one = AsyncMock(return_value=None)


# ── Test 1: Plugin Command Creation ────────────────────────────────────


@pytest.mark.asyncio
async def test_plugin_command_creation(
    client: AsyncClient,
    mock_mongodb,
    admin_token,  # noqa: ARG002
    sample_user,
    docker_list_definition,
    docker_plugin_doc,
    normal_tier_node,
):
    """Create a command with pluginId: plg::docker, verify correct plugin metadata."""
    _setup_plugin_mocks(
        mock_mongodb, sample_user, docker_list_definition,
        docker_plugin_doc, normal_tier_node,
    )

    response = await client.post(
        "/api/v1/commands",
        json={
            "registryId": "reg::node::docker-list-containers",
            "target": {"nodeId": "server-01"},
        },
        headers=trusted_write_headers(),
    )

    assert response.status_code == 202
    data = response.json()["data"]
    assert data["status"] == "queued"
    assert data["executionMethod"] == "agent-poll"
    assert data["target"]["nodeId"] == "server-01"

    # Verify the command doc was inserted
    inserted = mock_mongodb.commands.insert_one.await_args.args[0]
    assert inserted["registryId"] == "reg::node::docker-list-containers"
    assert inserted["type"] == "node"

    # Verify plugin execution context was stored
    mock_mongodb.commands.update_one.assert_awaited_once()
    update_call = mock_mongodb.commands.update_one.await_args
    update_set = update_call.args[1]["$set"]
    assert "executionContext.pluginPath" in update_set
    assert update_set["executionContext.pluginPath"] == "plugin_via_agent_poll"


# ── Test 2: Plugin Command Tier Dispatch ───────────────────────────────


@pytest.mark.asyncio
async def test_plugin_command_tier_dispatch_max_tier(
    client: AsyncClient,
    mock_mongodb,
    admin_token,  # noqa: ARG002
    sample_user,
    docker_direct_definition,
    docker_plugin_doc,
    max_tier_node,
):
    """Create a Docker command targeting a max-tier node.

    With direct_or_poll delivery, max-tier nodes should attempt direct execution.
    We mock the httpx call to simulate a successful direct response.
    """
    _setup_plugin_mocks(
        mock_mongodb, sample_user, docker_direct_definition,
        docker_plugin_doc, max_tier_node,
    )

    # The direct execution path uses httpx.AsyncClient internally.
    # Mock it to return a success response from the agent.
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "completed",
        "result": {
            "output": '{"containers": []}',
            "exitCode": 0,
            "error": None,
            "data": None,
        },
    }

    mock_http_client = MagicMock()
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)
    mock_http_client.post = AsyncMock(return_value=mock_response)

    with patch("hydra.api.v1.services.commands.service.httpx.AsyncClient", return_value=mock_http_client):
        response = await client.post(
            "/api/v1/commands",
            json={
                "registryId": "reg::node::docker-list-containers",
                "target": {"nodeId": "server-01"},
            },
            headers=trusted_write_headers(),
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "completed"
    assert data["executionMethod"] == "agent-direct"

    # Verify plugin path was stored as direct
    mock_mongodb.commands.update_one.assert_awaited()
    update_call = mock_mongodb.commands.update_one.await_args
    update_set = update_call.args[1]["$set"]
    assert update_set["executionContext.pluginPath"] == "plugin_via_agent_direct"


# ── Test 3: Multi-Node Plugin Command ──────────────────────────────────


@pytest.mark.asyncio
async def test_multi_node_plugin_command(
    client: AsyncClient,
    mock_mongodb,
    admin_token,  # noqa: ARG002
    sample_user,
    docker_list_definition,
    docker_plugin_doc,
):
    """Execute same plugin command targeting 3 different nodes.

    Each invocation creates a separate execution record.
    """
    node_ids = ["server-01", "server-02", "server-03"]
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.command_definitions.find_one = AsyncMock(return_value=docker_list_definition)
    mock_mongodb.commands.insert_one = AsyncMock(return_value=_mock_insert_one_result())
    mock_mongodb.commands.count_documents = AsyncMock(return_value=0)
    mock_mongodb.commands.update_one = AsyncMock()
    mock_mongodb.plugins.find_one = AsyncMock(return_value=docker_plugin_doc)
    mock_mongodb.services.find_one = AsyncMock(return_value=None)

    for node_id in node_ids:
        mock_mongodb.nodes.find_one = AsyncMock(
            return_value={
                "nodeId": node_id,
                "status": "active",
                "agentTier": "normal",
            }
        )

        response = await client.post(
            "/api/v1/commands",
            json={
                "registryId": "reg::node::docker-list-containers",
                "target": {"nodeId": node_id},
            },
            headers=trusted_write_headers(),
        )

        assert response.status_code == 202
        data = response.json()["data"]
        assert data["target"]["nodeId"] == node_id

    # Verify 3 separate insert_one calls were made
    assert mock_mongodb.commands.insert_one.await_count == 3


# ── Test 4: Plugin Config Delivery ─────────────────────────────────────


@pytest.mark.asyncio
async def test_plugin_config_delivery_and_status_transitions(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    docker_plugin_doc,
):
    """GET /plugins returns correct structure. Enable a plugin and verify status transition."""
    # List plugins
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    now = datetime.now(UTC)
    summary_doc = {
        "pluginId": "plg::docker",
        "manifest": docker_plugin_doc["manifest"],
        "status": "installed",
        "config": docker_plugin_doc["config"],
        "nodeBindings": [],
        "health": {"status": "unknown"},
        "createdAt": now,
        "updatedAt": now,
    }
    mock_mongodb.plugins.find = MagicMock(return_value=create_mock_cursor([summary_doc]))
    mock_mongodb.plugins.count_documents = AsyncMock(return_value=1)

    response = await client.get(
        "/api/v1/plugins",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"][0]["pluginId"] == "plg::docker"
    assert data["data"][0]["status"] == "installed"
    assert data["meta"]["total"] == 1

    # Enable the plugin (no health endpoint → direct activation)
    installed_doc = {**docker_plugin_doc, "status": "installed"}
    installed_doc["manifest"]["healthCheckEndpoint"] = None
    mock_mongodb.plugins.find_one = AsyncMock(
        side_effect=[
            installed_doc,  # First call: get plugin
            {**installed_doc, "status": "active"},  # Second call: after update
        ]
    )
    mock_mongodb.plugins.update_one = AsyncMock()
    mock_mongodb.audit_log.insert_one = AsyncMock()

    response = await client.post(
        "/api/v1/plugins/plg::docker/enable",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "active"


# ── Test 5: Dry-Run Plugin Command ─────────────────────────────────────


@pytest.mark.asyncio
async def test_dry_run_plugin_command(
    client: AsyncClient,
    mock_mongodb,
    admin_token,  # noqa: ARG002
    sample_user,
    docker_list_definition,
    normal_tier_node,
):
    """Execute a plugin command with dryRun: true.

    Should return validation result without creating an execution record.
    """
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.command_definitions.find_one = AsyncMock(return_value=docker_list_definition)
    mock_mongodb.nodes.find_one = AsyncMock(return_value=normal_tier_node)
    mock_mongodb.services.find_one = AsyncMock(return_value=None)

    response = await client.post(
        "/api/v1/commands",
        json={
            "registryId": "reg::node::docker-list-containers",
            "target": {"nodeId": "server-01"},
            "dryRun": True,
        },
        headers=trusted_write_headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["permissionCheckPassed"] is True
    assert data["estimatedDeliveryMode"] == "poll"
    assert data["targetNodeTier"] == "normal"
    assert data["registryId"] == "reg::node::docker-list-containers"
    assert data["targetNodeId"] == "server-01"
    assert data["dangerLevel"] == "safe"

    # Verify no command document was persisted
    mock_mongodb.commands.insert_one.assert_not_awaited()


# ── Test 6: Unknown Plugin Rejected ────────────────────────────────────


@pytest.mark.asyncio
async def test_unknown_plugin_rejected(
    client: AsyncClient,
    mock_mongodb,
    admin_token,  # noqa: ARG002
    sample_user,
):
    """Execute command with unknown registryId. Verify appropriate error."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.command_definitions.find_one = AsyncMock(return_value=None)
    mock_mongodb.commands.insert_one = AsyncMock(return_value=_mock_insert_one_result())

    response = await client.post(
        "/api/v1/commands",
        json={
            "registryId": "reg::node::nonexistent",
            "target": {"nodeId": "server-01"},
        },
        headers=trusted_write_headers(),
    )

    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "COMMAND_DEFINITION_NOT_FOUND"


# ── Test 7: Plugin Lifecycle Affects Commands ──────────────────────────


@pytest.mark.asyncio
async def test_plugin_lifecycle_affects_commands(
    client: AsyncClient,
    mock_mongodb,
    admin_token,  # noqa: ARG002
    sample_user,
    docker_list_definition,
    normal_tier_node,
):
    """Disable a plugin, attempt command → still routes (resolver returns None).

    When the plugin is disabled, the plugin resolver won't find an active plugin,
    so the command proceeds without plugin context (no plugin path stored).
    Re-enable → plugin path is stored.
    """
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.command_definitions.find_one = AsyncMock(return_value=docker_list_definition)
    mock_mongodb.nodes.find_one = AsyncMock(return_value=normal_tier_node)
    mock_mongodb.commands.insert_one = AsyncMock(return_value=_mock_insert_one_result())
    mock_mongodb.commands.count_documents = AsyncMock(return_value=0)
    mock_mongodb.commands.update_one = AsyncMock()
    mock_mongodb.services.find_one = AsyncMock(return_value=None)

    # Scenario A: Plugin is disabled (resolver returns None)
    mock_mongodb.plugins.find_one = AsyncMock(return_value=None)

    response = await client.post(
        "/api/v1/commands",
        json={
            "registryId": "reg::node::docker-list-containers",
            "target": {"nodeId": "server-01"},
        },
        headers=trusted_write_headers(),
    )

    assert response.status_code == 202
    data = response.json()["data"]
    assert data["status"] == "queued"

    # Plugin context should NOT be stored (no active plugin)
    mock_mongodb.commands.update_one.assert_not_awaited()

    # Scenario B: Re-enable plugin (resolver finds active plugin with binding)
    mock_mongodb.commands.update_one.reset_mock()
    now = datetime.now(UTC)
    active_plugin = {
        "pluginId": "plg::docker",
        "status": "active",
        "manifest": {
            "contributedCommands": ["reg::node::docker-list-containers"],
        },
        "nodeBindings": [
            {
                "nodeId": "server-01",
                "enabled": True,
                "allowedCommands": [],
                "boundAt": now,
            },
        ],
    }
    mock_mongodb.plugins.find_one = AsyncMock(return_value=active_plugin)

    response = await client.post(
        "/api/v1/commands",
        json={
            "registryId": "reg::node::docker-list-containers",
            "target": {"nodeId": "server-01"},
        },
        headers=trusted_write_headers(),
    )

    assert response.status_code == 202
    data = response.json()["data"]
    assert data["status"] == "queued"

    # Now plugin context SHOULD be stored
    mock_mongodb.commands.update_one.assert_awaited_once()
    update_set = mock_mongodb.commands.update_one.await_args.args[1]["$set"]
    assert update_set["executionContext.pluginPath"] == "plugin_via_agent_poll"


# ── Test: Plugin resolver returns None for no binding ──────────────────


@pytest.mark.asyncio
async def test_plugin_no_binding_for_node(
    client: AsyncClient,
    mock_mongodb,
    admin_token,  # noqa: ARG002
    sample_user,
    docker_list_definition,
    normal_tier_node,
):
    """Plugin exists but has no binding for the target node."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.command_definitions.find_one = AsyncMock(return_value=docker_list_definition)
    mock_mongodb.nodes.find_one = AsyncMock(return_value=normal_tier_node)
    mock_mongodb.commands.insert_one = AsyncMock(return_value=_mock_insert_one_result())
    mock_mongodb.commands.count_documents = AsyncMock(return_value=0)
    mock_mongodb.commands.update_one = AsyncMock()
    mock_mongodb.services.find_one = AsyncMock(return_value=None)

    # Plugin exists but binding is for a different node
    now = datetime.now(UTC)
    plugin_no_binding = {
        "pluginId": "plg::docker",
        "status": "active",
        "manifest": {
            "contributedCommands": ["reg::node::docker-list-containers"],
        },
        "nodeBindings": [
            {
                "nodeId": "different-node",
                "enabled": True,
                "allowedCommands": [],
                "boundAt": now,
            },
        ],
    }
    mock_mongodb.plugins.find_one = AsyncMock(return_value=plugin_no_binding)

    response = await client.post(
        "/api/v1/commands",
        json={
            "registryId": "reg::node::docker-list-containers",
            "target": {"nodeId": "server-01"},
        },
        headers=trusted_write_headers(),
    )

    # Command still succeeds (goes through normal path, no plugin context)
    assert response.status_code == 202
    mock_mongodb.commands.update_one.assert_not_awaited()


# ── Test: Lite tier rejects plugin command ─────────────────────────────


@pytest.mark.asyncio
async def test_lite_tier_rejects_plugin_command(
    client: AsyncClient,
    mock_mongodb,
    admin_token,  # noqa: ARG002
    sample_user,
    docker_list_definition,
    lite_tier_node,
):
    """Lite-tier nodes reject all command execution including plugin commands."""
    _setup_plugin_mocks(
        mock_mongodb, sample_user, docker_list_definition,
        None,  # Plugin doesn't matter for lite rejection
        lite_tier_node,
    )

    response = await client.post(
        "/api/v1/commands",
        json={
            "registryId": "reg::node::docker-list-containers",
            "target": {"nodeId": "server-01"},
        },
        headers=trusted_write_headers(),
    )

    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "COMMAND_NOT_SUPPORTED"
    assert "lite" in data["error"]["message"].lower()
