"""Additional coverage tests for tool_handlers.py — untested handler paths."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

import hydra_mcp.tool_handlers  # noqa: F401  # Ensure tool_handlers are imported/registered
from hydra_mcp.auth import AuthContext, set_auth_context
from hydra_mcp.tools import execute_tool

# Patch allow_missing_auth_context globally so that None context is allowed
# (simulates stdio transport for test purposes)
pytestmark = pytest.mark.usefixtures("_allow_missing_auth")


@pytest.fixture(autouse=True)
def _allow_missing_auth(monkeypatch):
    """Make allow_missing_auth_context return True for all tests in this module."""
    monkeypatch.setattr(
        "hydra_mcp.auth.get_settings",
        lambda: SimpleNamespace(transport="stdio", allow_unauthenticated=False),
    )


def _set_admin_context():
    """Set an admin auth context so permission checks pass (stdio fallback)."""
    set_auth_context(None)  # stdio transport allows missing context


def _set_internal_admin_context():
    """Set an internal admin auth context for internal-only tools."""
    set_auth_context(AuthContext(
        user_id="admin1",
        permissions=["*:*"],
        role="admin",
        source_type="internal",
        client_id="hydra-api",
        metadata={
            "forward_auth": {"Authorization": "Bearer test"},
        },
    ))


class TestGetNodeProfile:
    """Tests for get_node_profile handler."""

    async def test_get_node_profile(self):
        _set_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.get_node_profile = AsyncMock(return_value={
                "profileId": "p1", "hardware": {"cpu": {"cores": 4}},
            })
            result = await execute_tool("get_node_profile", {"nodeId": "n1", "sections": ["hardware"]})
            assert isinstance(result, str)
        set_auth_context(None)


class TestControlService:
    """Tests for control_service handler."""

    async def test_control_service_success(self):
        _set_internal_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.get_service = AsyncMock(return_value={"serviceId": "svc-1", "nodeId": "n1"})
            mock_client.control_service = AsyncMock(return_value={"commandId": "cmd1", "status": "queued"})
            result = await execute_tool("control_service", {"serviceId": "svc-1", "action": "restart"})
            assert isinstance(result, str)
        set_auth_context(None)


class TestControlNode:
    """Tests for control_node handler."""

    async def test_control_node_success(self):
        _set_internal_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.control_node = AsyncMock(return_value={"commandId": "cmd2", "status": "queued"})
            result = await execute_tool("control_node", {"nodeId": "n1", "action": "reboot"})
            assert isinstance(result, str)
        set_auth_context(None)


class TestControlAgent:
    """Tests for control_agent handler."""

    async def test_control_agent_success(self):
        _set_internal_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.control_agent = AsyncMock(return_value={"commandId": "cmd3"})
            result = await execute_tool("control_agent", {"nodeId": "n1", "action": "status"})
            assert isinstance(result, str)
        set_auth_context(None)


class TestListCommandCatalog:
    """Tests for list_command_catalog handler."""

    async def test_list_catalog(self):
        _set_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.list_command_catalog = AsyncMock(return_value=[
                {"registryId": "reg::service::restart"},
            ])
            result = await execute_tool("list_command_catalog", {"category": "service"})
            assert isinstance(result, str)
        set_auth_context(None)


class TestListCommands:
    """Tests for list_commands handler."""

    async def test_list_commands_with_filters(self):
        _set_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.list_commands = AsyncMock(return_value=[{"commandId": "c1"}])
            result = await execute_tool("list_commands", {"nodeId": "n1", "status": "completed"})
            assert isinstance(result, str)
        set_auth_context(None)


class TestGetQueueStatus:
    """Tests for get_queue_status handler."""

    async def test_queue_status(self):
        _set_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.get_queue_status = AsyncMock(return_value={"pending": 2})
            result = await execute_tool("get_queue_status", {"nodeId": "n1"})
            assert isinstance(result, str)
        set_auth_context(None)


class TestQueryInfrastructure:
    """Tests for query_infrastructure handler (admin only)."""

    async def test_query_with_blocked_operator(self):
        _set_admin_context()
        result = await execute_tool("query_infrastructure", {
            "collection": "nodes",
            "filter": {"$where": "1==1"},
        })
        assert "VALIDATION_ERROR" in result
        set_auth_context(None)

    async def test_query_success(self):
        _set_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.query = AsyncMock(return_value={"results": [{"nodeId": "n1"}]})
            result = await execute_tool("query_infrastructure", {
                "collection": "nodes",
                "filter": {"status": "active"},
            })
            assert isinstance(result, str)
        set_auth_context(None)


class TestServiceDependencyMap:
    """Tests for service_dependency_map handler."""

    async def test_dependency_map_all_services(self):
        _set_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.list_services = AsyncMock(return_value=([
                {"serviceId": "svc-nginx-a1", "name": "nginx", "nodeId": "n1", "runtime": "docker",
                 "ports": [80], "status": "running"},
            ], 1))
            mock_client.get_topology = AsyncMock(return_value={"nodes": [], "edges": []})
            result = await execute_tool("service_dependency_map", {})
            assert isinstance(result, str)
        set_auth_context(None)

    async def test_dependency_map_single_service(self):
        _set_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.get_service = AsyncMock(return_value={
                "serviceId": "svc-nginx-a1", "name": "nginx", "nodeId": "n1",
                "runtime": "systemd", "ports": [80], "status": "running",
            })
            mock_client.get_topology = AsyncMock(return_value={"nodes": [], "edges": []})
            result = await execute_tool("service_dependency_map", {"serviceId": "svc-nginx-a1"})
            assert isinstance(result, str)
        set_auth_context(None)

    async def test_dependency_map_network_failure(self):
        _set_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.list_services = AsyncMock(return_value=([], 0))
            mock_client.get_topology = AsyncMock(side_effect=Exception("network error"))
            result = await execute_tool("service_dependency_map", {"includeNetworkAnalysis": True})
            assert isinstance(result, str)
        set_auth_context(None)


class TestListNotifications:
    """Tests for list_notifications handler."""

    async def test_list_notifications(self):
        _set_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.list_notifications = AsyncMock(return_value=([
                {"notificationId": "n1", "title": "Test"},
            ], 1))
            result = await execute_tool("list_notifications", {"tier": 3, "status": "active"})
            assert isinstance(result, str)
        set_auth_context(None)


class TestGetNotificationStats:
    """Tests for get_notification_stats handler."""

    async def test_notification_stats(self):
        _set_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.get_notification_stats = AsyncMock(return_value={"total": 5, "unread": 2})
            result = await execute_tool("get_notification_stats", {})
            assert isinstance(result, str)
        set_auth_context(None)


class TestListAuditEntries:
    """Tests for list_audit_entries handler."""

    async def test_list_audit_entries(self):
        _set_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.list_audit_entries = AsyncMock(return_value=[
                {"action": "create", "resourceType": "node"},
            ])
            result = await execute_tool("list_audit_entries", {
                "action": "create",
                "resourceType": "node",
            })
            assert isinstance(result, str)
        set_auth_context(None)


class TestDeleteAuditEntries:
    """Tests for delete_audit_entries handler."""

    async def test_delete_audit_entries(self):
        _set_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.delete_audit_entries = AsyncMock(return_value={"deleted": 3})
            result = await execute_tool("delete_audit_entries", {
                "since": "2025-01-01T00:00:00Z",
                "until": "2025-06-01T00:00:00Z",
            })
            assert isinstance(result, str)
        set_auth_context(None)


class TestControlDevice:
    """Tests for control_device handler."""

    async def test_control_device(self):
        _set_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.control_device = AsyncMock(return_value={"status": "ok"})
            result = await execute_tool("control_device", {
                "entityId": "light.living_room",
                "service": "turn_on",
            })
            assert isinstance(result, str)
        set_auth_context(None)


class TestTimeMachineHandlers:
    """Tests for time machine tool handlers."""

    async def test_time_machine_node(self):
        _set_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.get_node_at_time = AsyncMock(return_value={"nodeId": "n1", "state": "active"})
            result = await execute_tool("time_machine_node", {
                "nodeId": "n1",
                "timestamp": "2025-01-01T00:00:00Z",
            })
            assert isinstance(result, str)
        set_auth_context(None)

    async def test_time_machine_topology(self):
        _set_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.get_topology_at_time = AsyncMock(return_value={"nodes": [], "edges": []})
            result = await execute_tool("time_machine_topology", {
                "mode": "network",
                "timestamp": "2025-06-15T12:00:00Z",
            })
            assert isinstance(result, str)
        set_auth_context(None)


class TestRemoteInstallAgent:
    """Tests for the remote_install_agent handler (P2E-T06)."""

    async def test_remote_install_with_target_ip(self):
        _set_internal_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.start_installation = AsyncMock(
                return_value={"installationId": "inst_1", "status": "pending"}
            )
            result = await execute_tool(
                "remote_install_agent",
                {
                    "targetIp": "10.0.0.5",
                    "credentials": {"host": "10.0.0.5", "username": "root", "password": "x"},
                },
            )
            assert isinstance(result, str)
            mock_client.start_installation.assert_awaited_once()
        set_auth_context(None)

    async def test_remote_install_requires_exactly_one_target(self):
        _set_internal_admin_context()
        with patch("hydra_mcp.tool_handlers.client"):
            with pytest.raises(ValueError, match="exactly one"):
                await execute_tool(
                    "remote_install_agent",
                    {
                        "targetIp": "10.0.0.5",
                        "discoveryId": "disc_1",
                        "credentials": {"host": "10.0.0.5", "username": "root", "password": "x"},
                    },
                )
        set_auth_context(None)


class TestDashboardTools:
    """Tests for dashboard MCP tools (P2DASH-T036)."""

    async def test_list_dashboards(self):
        _set_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.list_dashboards = AsyncMock(
                return_value=[{"boardId": "b1", "name": "Ops"}]
            )
            result = await execute_tool("list_dashboards", {"limit": 10})
            assert isinstance(result, str)
        set_auth_context(None)

    async def test_get_dashboard(self):
        _set_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.get_dashboard = AsyncMock(
                return_value={"boardId": "b1", "widgets": []}
            )
            result = await execute_tool("get_dashboard", {"boardId": "b1"})
            assert isinstance(result, str)
        set_auth_context(None)

    async def test_create_dashboard(self):
        _set_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.create_dashboard = AsyncMock(
                return_value={"boardId": "b2", "name": "New"}
            )
            result = await execute_tool(
                "create_dashboard", {"name": "New", "widgets": []}
            )
            assert isinstance(result, str)
            mock_client.create_dashboard.assert_awaited_once()
        set_auth_context(None)

    async def test_update_dashboard(self):
        _set_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.update_dashboard = AsyncMock(return_value={"boardId": "b1"})
            result = await execute_tool(
                "update_dashboard", {"boardId": "b1", "updates": {"name": "X"}}
            )
            assert isinstance(result, str)
        set_auth_context(None)

    async def test_delete_dashboard(self):
        _set_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.delete_dashboard = AsyncMock(return_value={"deleted": True})
            result = await execute_tool("delete_dashboard", {"boardId": "b1"})
            assert isinstance(result, str)
        set_auth_context(None)

    async def test_clone_dashboard(self):
        _set_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.clone_dashboard = AsyncMock(return_value={"boardId": "b3"})
            result = await execute_tool(
                "clone_dashboard", {"boardId": "b1", "name": "Copy"}
            )
            assert isinstance(result, str)
        set_auth_context(None)

    async def test_list_dashboard_templates(self):
        _set_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.list_dashboard_templates = AsyncMock(
                return_value=[{"templateId": "t1"}]
            )
            result = await execute_tool("list_dashboard_templates", {})
            assert isinstance(result, str)
        set_auth_context(None)

    async def test_create_dashboard_from_template(self):
        _set_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.create_dashboard_from_template = AsyncMock(
                return_value={"boardId": "b4"}
            )
            result = await execute_tool(
                "create_dashboard_from_template",
                {"templateId": "t1", "name": "From Template"},
            )
            assert isinstance(result, str)
        set_auth_context(None)
