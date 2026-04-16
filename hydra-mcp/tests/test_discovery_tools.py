"""Tests for network discovery MCP tool handlers."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

import hydra_mcp.tool_handlers  # noqa: F401  # Ensure all tools are registered
from hydra_mcp.auth import AuthContext, set_auth_context
from hydra_mcp.tools import execute_tool, get_tool

# Allow missing auth context (stdio transport) for all tests
pytestmark = pytest.mark.usefixtures("_allow_missing_auth")


@pytest.fixture(autouse=True)
def _allow_missing_auth(monkeypatch):
    monkeypatch.setattr(
        "hydra_mcp.auth.get_settings",
        lambda: SimpleNamespace(transport="stdio", allow_unauthenticated=False),
    )


def _set_admin_context():
    set_auth_context(None)


def _set_internal_admin_context():
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


# =============================================================================
# Tool Registration Tests
# =============================================================================


class TestDiscoveryToolRegistration:
    """Verify discovery tools are registered with correct metadata."""

    def test_scan_network_registered(self):
        tool_def = get_tool("scan_network")
        assert tool_def is not None
        assert tool_def.required_permission == "discovery:scan"
        assert tool_def.internal_only is True

    def test_list_discoveries_registered(self):
        tool_def = get_tool("list_discoveries")
        assert tool_def is not None
        assert tool_def.required_permission == "discovery:read"
        assert tool_def.internal_only is False

    def test_assess_discovery_registered(self):
        tool_def = get_tool("assess_discovery")
        assert tool_def is not None
        assert tool_def.required_permission == "discovery:read"
        assert tool_def.internal_only is False

    def test_register_discovery_registered(self):
        tool_def = get_tool("register_discovery")
        assert tool_def is not None
        assert tool_def.required_permission == "nodes:create"
        assert tool_def.internal_only is True

    def test_scan_network_schema_has_required_subnet(self):
        tool_def = get_tool("scan_network")
        assert tool_def is not None
        assert "subnet" in tool_def.schema.get("required", [])

    def test_register_discovery_schema_has_required_discovery_id(self):
        tool_def = get_tool("register_discovery")
        assert tool_def is not None
        assert "discoveryId" in tool_def.schema.get("required", [])


# =============================================================================
# scan_network Tool Tests
# =============================================================================


class TestScanNetwork:
    """Tests for the scan_network tool handler."""

    async def test_scan_network_minimal(self):
        _set_internal_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.scan_network = AsyncMock(return_value={
                "scanId": "scan-001",
                "status": "running",
                "targets": [{"subnet": "192.168.1.0/24"}],
            })
            result = await execute_tool("scan_network", {"subnet": "192.168.1.0/24"})
            assert isinstance(result, str)
            assert "scan-001" in result
            mock_client.scan_network.assert_awaited_once_with(
                subnet="192.168.1.0/24",
                network_id=None,
                port_tier="tier1",
                include_iot_protocols=False,
                delegate_to_node_id=None,
            )
        set_auth_context(None)

    async def test_scan_network_full_options(self):
        _set_internal_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.scan_network = AsyncMock(return_value={
                "scanId": "scan-002", "status": "pending",
            })
            result = await execute_tool("scan_network", {
                "subnet": "10.0.0.0/24",
                "networkId": "net-10-0-0-0",
                "portTier": "tier2",
                "includeIoTProtocols": True,
                "delegateToNodeId": "proxmox-01",
            })
            assert isinstance(result, str)
            mock_client.scan_network.assert_awaited_once_with(
                subnet="10.0.0.0/24",
                network_id="net-10-0-0-0",
                port_tier="tier2",
                include_iot_protocols=True,
                delegate_to_node_id="proxmox-01",
            )
        set_auth_context(None)


# =============================================================================
# list_discoveries Tool Tests
# =============================================================================


class TestListDiscoveries:
    """Tests for the list_discoveries tool handler."""

    async def test_list_discoveries_no_filters(self):
        _set_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.list_discoveries = AsyncMock(return_value=(
                [{"discoveryId": "disc-1", "status": "pending"}],
                1,
            ))
            result = await execute_tool("list_discoveries", {})
            assert isinstance(result, str)
            assert "disc-1" in result
        set_auth_context(None)

    async def test_list_discoveries_with_filters(self):
        _set_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.list_discoveries = AsyncMock(return_value=(
                [{"discoveryId": "disc-2", "classification": {"suggestedClass": "compute"}}],
                1,
            ))
            result = await execute_tool("list_discoveries", {
                "status": "pending",
                "deviceClass": "compute",
                "minConfidence": 0.5,
                "networkId": "net-1",
                "agentCompatible": True,
                "limit": 10,
            })
            assert isinstance(result, str)
            mock_client.list_discoveries.assert_awaited_once_with(
                status="pending",
                network_id="net-1",
                device_class="compute",
                min_confidence=0.5,
                agent_compatible=True,
                limit=10,
            )
        set_auth_context(None)


# =============================================================================
# assess_discovery Tool Tests
# =============================================================================


class TestAssessDiscovery:
    """Tests for the assess_discovery tool handler."""

    async def test_assess_discovery(self):
        _set_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.get_discovery = AsyncMock(return_value={
                "discoveryId": "disc-1",
                "identity": {"currentIp": "192.168.1.100"},
                "classification": {
                    "suggestedClass": "compute",
                    "confidence": 0.85,
                },
                "eligibility": {
                    "agentCompatible": True,
                    "profilingStrategy": "agent",
                },
            })
            result = await execute_tool("assess_discovery", {"discoveryId": "disc-1"})
            assert isinstance(result, str)
            assert "disc-1" in result
            mock_client.get_discovery.assert_awaited_once_with("disc-1")
        set_auth_context(None)


# =============================================================================
# register_discovery Tool Tests
# =============================================================================


class TestRegisterDiscovery:
    """Tests for the register_discovery tool handler."""

    async def test_register_discovery_minimal(self):
        _set_internal_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.register_discovery = AsyncMock(return_value={
                "nodeId": "server-a1b2",
                "status": "registered",
            })
            result = await execute_tool("register_discovery", {"discoveryId": "disc-1"})
            assert isinstance(result, str)
            assert "server-a1b2" in result
            mock_client.register_discovery.assert_awaited_once_with(
                discovery_id="disc-1",
                overrides=None,
            )
        set_auth_context(None)

    async def test_register_discovery_with_overrides(self):
        _set_internal_admin_context()
        with patch("hydra_mcp.tool_handlers.client") as mock_client:
            mock_client.register_discovery = AsyncMock(return_value={
                "nodeId": "my-server",
                "status": "registered",
            })
            result = await execute_tool("register_discovery", {
                "discoveryId": "disc-2",
                "nodeId": "my-server",
                "displayName": "My Server",
                "nodeClass": "compute",
                "tags": ["prod", "web"],
            })
            assert isinstance(result, str)
            mock_client.register_discovery.assert_awaited_once_with(
                discovery_id="disc-2",
                overrides={
                    "nodeId": "my-server",
                    "displayName": "My Server",
                    "nodeClass": "compute",
                    "tags": ["prod", "web"],
                },
            )
        set_auth_context(None)
