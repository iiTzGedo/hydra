"""Tests for MCP tool execution."""

import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import from the new tool registry module
from hydra_mcp.auth import (
    INTERNAL_CLIENT_ID_HEADER,
    INTERNAL_PERMISSIONS_HEADER,
    INTERNAL_REQUEST_HEADER,
    INTERNAL_ROLE_HEADER,
    INTERNAL_SECRET_HEADER,
    INTERNAL_USER_ID_HEADER,
    AuthContext,
    set_auth_context,
)
from hydra_mcp.client import HydraAPIError, HydraClient

# Import call_tool from server (it uses the registry internally)
from hydra_mcp.server import _build_internal_context, _build_request_auth_context, call_tool
from hydra_mcp.tool_handlers import _format_list_response, _safe_list
from hydra_mcp.tools import (
    ToolValidationError,
    execute_tool,
    validate_tool_args,
)


class TestSafeList:
    """Tests for _safe_list helper function."""

    def test_list_returns_same_list(self):
        """Test that a list input returns the same list."""
        input_list = [1, 2, 3]
        result = _safe_list(input_list)
        assert result == input_list

    def test_empty_list_returns_empty_list(self):
        """Test that an empty list returns empty list."""
        result = _safe_list([])
        assert result == []

    def test_none_returns_empty_list(self):
        """Test that None returns empty list."""
        result = _safe_list(None)
        assert result == []

    def test_dict_returns_empty_list(self):
        """Test that a dict returns empty list."""
        result = _safe_list({"key": "value"})
        assert result == []

    def test_string_returns_empty_list(self):
        """Test that a string returns empty list."""
        result = _safe_list("not a list")
        assert result == []

    def test_int_returns_empty_list(self):
        """Test that an integer returns empty list."""
        result = _safe_list(42)
        assert result == []


class TestFormatListResponse:
    """Tests for _format_list_response helper function."""

    def test_formats_list_data(self):
        """Test formatting valid list data."""
        data = [{"id": 1}, {"id": 2}]
        result = _format_list_response("items", data)

        # Should be a TOON formatted string
        assert isinstance(result, str)
        assert "items" in result or "[" in result  # TOON format

    def test_handles_none_data(self):
        """Test formatting None data returns empty list format."""
        result = _format_list_response("items", None)

        assert isinstance(result, str)

    def test_handles_non_list_data(self):
        """Test formatting non-list data."""
        result = _format_list_response("items", {"not": "a list"})

        assert isinstance(result, str)


class TestValidateToolArgs:
    """Tests for tool argument validation."""

    def test_valid_args_pass_validation(self):
        """Test that valid arguments pass validation without error."""
        schema = {
            "type": "object",
            "properties": {
                "nodeId": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["nodeId"],
        }
        args = {"nodeId": "node-1", "limit": 10}

        # Should not raise
        validate_tool_args("test_tool", args, schema)

    def test_missing_required_field_raises_error(self):
        """Test that missing required field raises ToolValidationError."""
        schema = {
            "type": "object",
            "properties": {
                "nodeId": {"type": "string"},
            },
            "required": ["nodeId"],
        }
        args = {}

        with pytest.raises(ToolValidationError) as exc_info:
            validate_tool_args("get_node", args, schema)

        assert exc_info.value.tool_name == "get_node"
        assert "nodeId" in str(exc_info.value) or "required" in str(exc_info.value).lower()

    def test_wrong_type_raises_error(self):
        """Test that wrong type raises ToolValidationError."""
        schema = {
            "type": "object",
            "properties": {
                "limit": {"type": "integer"},
            },
        }
        args = {"limit": "not-an-integer"}

        with pytest.raises(ToolValidationError) as exc_info:
            validate_tool_args("list_nodes", args, schema)

        assert exc_info.value.tool_name == "list_nodes"
        assert len(exc_info.value.errors) > 0

    def test_invalid_enum_value_raises_error(self):
        """Test that invalid enum value raises ToolValidationError."""
        schema = {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["active", "inactive", "archived"],
                },
            },
        }
        args = {"status": "invalid_status"}

        with pytest.raises(ToolValidationError) as exc_info:
            validate_tool_args("list_nodes", args, schema)

        assert exc_info.value.tool_name == "list_nodes"

    def test_invalid_array_items_raises_error(self):
        """Test that invalid array items raise ToolValidationError."""
        schema = {
            "type": "object",
            "properties": {
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
        }
        args = {"tags": [1, 2, 3]}  # integers instead of strings

        with pytest.raises(ToolValidationError) as exc_info:
            validate_tool_args("list_nodes", args, schema)

        assert exc_info.value.tool_name == "list_nodes"

    def test_empty_args_with_no_required_passes(self):
        """Test that empty args pass when no fields are required."""
        schema = {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 50},
            },
        }
        args = {}

        # Should not raise
        validate_tool_args("list_nodes", args, schema)

    def test_additional_properties_are_rejected_for_tool_inputs(self):
        """Test that top-level unknown properties are rejected."""
        schema = {
            "type": "object",
            "properties": {
                "nodeId": {"type": "string"},
            },
        }
        args = {"nodeId": "node-1", "extraField": "ignored"}

        with pytest.raises(ToolValidationError) as exc_info:
            validate_tool_args("test_tool", args, schema)

        assert "additional properties" in str(exc_info.value).lower()

    def test_identifier_max_length_is_inferred(self):
        """Test that identifier-like strings are capped automatically."""
        schema = {
            "type": "object",
            "properties": {
                "nodeId": {"type": "string"},
            },
            "required": ["nodeId"],
        }

        with pytest.raises(ToolValidationError):
            validate_tool_args("get_node", {"nodeId": "n" * 129}, schema)

    def test_array_max_items_is_inferred(self):
        """Test that array item limits are enforced automatically."""
        schema = {
            "type": "object",
            "properties": {
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
        }

        with pytest.raises(ToolValidationError):
            validate_tool_args("list_nodes", {"tags": [f"tag-{i}" for i in range(26)]}, schema)

    def test_object_max_properties_is_inferred(self):
        """Test that dynamic objects receive property count limits."""
        schema = {
            "type": "object",
            "properties": {
                "projection": {"type": "object"},
            },
        }

        with pytest.raises(ToolValidationError):
            validate_tool_args(
                "query_infrastructure",
                {"projection": {f"field_{i}": 1 for i in range(26)}},
                schema,
            )

    def test_projection_values_must_be_zero_or_one(self):
        """Test that projection values are restricted to include/exclude flags."""
        schema = {
            "type": "object",
            "properties": {
                "projection": {"type": "object"},
            },
        }

        with pytest.raises(ToolValidationError):
            validate_tool_args(
                "query_infrastructure",
                {"projection": {"nodeId": 2}},
                schema,
            )

    def test_validation_error_contains_errors_list(self):
        """Test that ToolValidationError contains list of all errors."""
        schema = {
            "type": "object",
            "properties": {
                "nodeId": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["nodeId"],
        }
        args = {"limit": "not-an-int"}  # Wrong type AND missing required

        with pytest.raises(ToolValidationError) as exc_info:
            validate_tool_args("get_node", args, schema)

        # Should have errors listed
        assert len(exc_info.value.errors) >= 1


@pytest.mark.asyncio
class TestToolValidationIntegration:
    """Integration tests for tool validation in execute_tool."""

    @pytest.fixture(autouse=True)
    def auth_context(self):
        set_auth_context(
            AuthContext(
                user_id="user_admin123",
                permissions=["*:*"],
                role="admin",
                source_type="internal",
            )
        )
        yield
        set_auth_context(None)

    @pytest.fixture
    def mock_client(self):
        """Create a mock Hydra API client."""
        with patch("hydra_mcp.tool_handlers.client") as mock:
            yield mock

    async def test_execute_tool_validates_before_calling_handler(self, mock_client):
        """Test that execute_tool validates args before calling the handler."""
        mock_client.get_node = AsyncMock(return_value={"nodeId": "test"})

        # Missing required nodeId should raise before handler is called
        with pytest.raises(ToolValidationError):
            await execute_tool("get_node", {})

        # Handler should not have been called
        mock_client.get_node.assert_not_called()

    async def test_execute_tool_passes_valid_args_to_handler(self, mock_client):
        """Test that execute_tool passes valid args through to handler."""
        mock_client.get_node = AsyncMock(return_value={"nodeId": "node-1"})

        result = await execute_tool("get_node", {"nodeId": "node-1"})

        assert isinstance(result, str)
        mock_client.get_node.assert_called_once()

    async def test_execute_tool_validates_enum_values(self, mock_client):
        """Test that execute_tool validates enum values."""
        # list_nodes has enum for class: compute, networking, iot
        with pytest.raises(ToolValidationError):
            await execute_tool("list_nodes", {"class": "invalid_class"})

    async def test_execute_tool_validates_array_types(self, mock_client):
        """Test that execute_tool validates array item types."""
        # list_nodes has tags as array of strings
        with pytest.raises(ToolValidationError):
            await execute_tool("list_nodes", {"tags": [123, 456]})

    async def test_execute_tool_rejects_unknown_top_level_args(self, mock_client):
        """Test that unexpected top-level fields are rejected."""
        with pytest.raises(ToolValidationError):
            await execute_tool("get_node", {"nodeId": "node-1", "unexpected": True})

    async def test_execute_tool_rejects_oversized_query_string(self, mock_client):
        """Test that free-text inputs enforce max lengths."""
        with pytest.raises(ToolValidationError):
            await execute_tool("search_infrastructure", {"query": "q" * 257})

    async def test_execute_tool_rejects_excessive_limit(self, mock_client):
        """Test that list limits mirror API-side ceilings."""
        with pytest.raises(ToolValidationError):
            await execute_tool("list_nodes", {"limit": 201})

    async def test_execute_tool_rejects_excessive_dependency_depth(self, mock_client):
        """Test that dependency traversal depth is bounded."""
        with pytest.raises(ToolValidationError):
            await execute_tool("service_dependency_map", {"depth": 11})


@pytest.mark.asyncio
class TestExecuteTool:
    """Tests for _execute_tool function."""

    @pytest.fixture(autouse=True)
    def auth_context(self):
        set_auth_context(
            AuthContext(
                user_id="user_admin123",
                permissions=["*:*"],
                role="admin",
                source_type="internal",
            )
        )
        yield
        set_auth_context(None)

    @pytest.fixture
    def mock_client(self):
        """Create a mock Hydra API client."""
        with patch("hydra_mcp.tool_handlers.client") as mock:
            yield mock

    async def test_list_nodes_tool(self, mock_client):
        """Test list_nodes tool execution."""
        mock_client.list_nodes = AsyncMock(return_value=(
            [{"nodeId": "node-1", "status": "active"}],
            {"total": 1}
        ))

        result = await execute_tool("list_nodes", {"limit": 10})

        assert isinstance(result, str)
        mock_client.list_nodes.assert_called_once_with(
            node_class=None,
            node_type=None,
            status=None,
            tags=None,
            agent_tier=None,
            limit=10,
        )

    async def test_list_nodes_with_filters(self, mock_client):
        """Test list_nodes tool with filter arguments."""
        mock_client.list_nodes = AsyncMock(return_value=([], {}))

        await execute_tool("list_nodes", {
            "class": "compute",
            "type": "physical",
            "status": "active",
            "tags": ["production"],
            "limit": 25,
        })

        mock_client.list_nodes.assert_called_once_with(
            node_class="compute",
            node_type="physical",
            status="active",
            tags=["production"],
            agent_tier=None,
            limit=25,
        )

    async def test_get_node_tool(self, mock_client):
        """Test get_node tool execution."""
        mock_client.get_node = AsyncMock(return_value={
            "nodeId": "test-node",
            "status": "active",
        })

        result = await execute_tool("get_node", {"nodeId": "test-node"})

        assert isinstance(result, str)
        mock_client.get_node.assert_called_once_with(
            "test-node",
            include_children=True,
            include_services=True,
        )

    async def test_get_node_without_includes(self, mock_client):
        """Test get_node tool with include flags set to False."""
        mock_client.get_node = AsyncMock(return_value={"nodeId": "test-node"})

        await execute_tool("get_node", {
            "nodeId": "test-node",
            "includeChildren": False,
            "includeServices": False,
        })

        mock_client.get_node.assert_called_once_with(
            "test-node",
            include_children=False,
            include_services=False,
        )

    async def test_list_services_tool(self, mock_client):
        """Test list_services tool execution."""
        mock_client.list_services = AsyncMock(return_value=(
            [{"serviceId": "svc-nginx-a1b2", "status": "running"}],
            {"total": 1}
        ))

        result = await execute_tool("list_services", {
            "nodeId": "node-1",
            "runtime": "systemd",
            "status": "running",
        })

        assert isinstance(result, str)
        mock_client.list_services.assert_called_once_with(
            node_id="node-1",
            runtime="systemd",
            status="running",
            limit=50,
        )

    async def test_get_service_tool(self, mock_client):
        """Test get_service tool execution."""
        mock_client.get_service = AsyncMock(return_value={
            "serviceId": "svc-nginx-a1b2",
            "name": "nginx",
        })

        result = await execute_tool("get_service", {"serviceId": "svc-nginx-a1b2"})

        assert isinstance(result, str)
        mock_client.get_service.assert_called_once_with("svc-nginx-a1b2")

    async def test_list_groups_tool(self, mock_client):
        """Test list_groups tool execution."""
        mock_client.list_groups = AsyncMock(return_value=(
            [{"groupId": "grp-1", "name": "Production"}],
            {"total": 1}
        ))

        result = await execute_tool("list_groups", {"types": ["node"]})

        assert isinstance(result, str)
        mock_client.list_groups.assert_called_once()

    async def test_get_group_tool(self, mock_client):
        """Test get_group tool execution."""
        mock_client.get_group = AsyncMock(return_value={
            "groupId": "grp-1",
            "name": "Production",
        })

        result = await execute_tool("get_group", {
            "groupId": "grp-1",
            "resolveMembers": True,
        })

        assert isinstance(result, str)
        mock_client.get_group.assert_called_once_with("grp-1", resolve_members=True)

    async def test_list_networks_tool(self, mock_client):
        """Test list_networks tool execution."""
        mock_client.list_networks = AsyncMock(return_value=(
            [{"networkId": "net-1", "cidr": "192.168.1.0/24"}],
            {"total": 1}
        ))

        result = await execute_tool("list_networks", {"type": "physical"})

        assert isinstance(result, str)
        mock_client.list_networks.assert_called_once()

    async def test_get_network_tool(self, mock_client):
        """Test get_network tool execution."""
        mock_client.get_network = AsyncMock(return_value={
            "networkId": "net-1",
            "cidr": "192.168.1.0/24",
        })

        result = await execute_tool("get_network", {
            "networkId": "net-1",
            "includeNodes": True,
        })

        assert isinstance(result, str)
        mock_client.get_network.assert_called_once_with("net-1", include_nodes=True)

    async def test_get_topology_tool(self, mock_client):
        """Test get_topology tool execution."""
        mock_client.get_topology = AsyncMock(return_value={
            "mode": "network",
            "nodes": [],
            "edges": [],
        })

        result = await execute_tool("get_topology", {"mode": "infrastructure"})

        assert isinstance(result, str)
        mock_client.get_topology.assert_called_once_with(
            mode="infrastructure",
            _scope=None,
        )

    async def test_search_infrastructure_tool(self, mock_client):
        """Test search_infrastructure tool execution."""
        mock_client.search = AsyncMock(return_value=[
            {"type": "node", "id": "node-1", "score": 0.95}
        ])

        result = await execute_tool("search_infrastructure", {
            "query": "nginx server",
            "types": ["node", "service"],
            "limit": 10,
        })

        assert isinstance(result, str)
        mock_client.search.assert_called_once_with(
            query="nginx server",
            types=["node", "service"],
            limit=10,
        )

    async def test_compare_profiles_tool(self, mock_client):
        """Test compare_profiles tool execution."""
        mock_client.compare_profiles = AsyncMock(return_value={
            "fromVersion": "E0-0.0.0.1",
            "toVersion": "E0-0.0.0.2",
            "changes": [],
        })

        result = await execute_tool("compare_profiles", {
            "nodeId": "node-1",
            "fromVersion": "E0-0.0.0.1",
            "toVersion": "E0-0.0.0.2",
        })

        assert isinstance(result, str)
        mock_client.compare_profiles.assert_called_once()

    async def test_get_capacity_tool(self, mock_client):
        """Test get_capacity tool execution."""
        mock_client.get_capacity = AsyncMock(return_value={
            "totalNodes": 10,
            "activeNodes": 8,
        })

        result = await execute_tool("get_capacity", {
            "groupBy": "class",
            "includeLogical": True,
        })

        assert isinstance(result, str)
        mock_client.get_capacity.assert_called_once_with(
            group_by="class",
            include_logical=True,
        )

    async def test_time_machine_node_tool(self, mock_client):
        """Test time_machine_node tool execution."""
        mock_client.get_node_at_time = AsyncMock(return_value={
            "nodeId": "node-1",
            "timestamp": "2024-01-01T00:00:00Z",
        })

        result = await execute_tool("time_machine_node", {
            "nodeId": "node-1",
            "timestamp": "2024-01-01T00:00:00Z",
        })

        assert isinstance(result, str)
        mock_client.get_node_at_time.assert_called_once()

    async def test_time_machine_topology_tool(self, mock_client):
        """Test time_machine_topology tool execution."""
        mock_client.get_topology_at_time = AsyncMock(return_value={
            "mode": "network",
            "nodes": [],
        })

        result = await execute_tool("time_machine_topology", {
            "mode": "network",
            "timestamp": "2024-01-01T00:00:00Z",
        })

        assert isinstance(result, str)
        mock_client.get_topology_at_time.assert_called_once()

    async def test_control_service_tool(self, mock_client):
        """Test control_service tool execution."""
        mock_client.get_service = AsyncMock(return_value={
            "serviceId": "svc-nginx-a1b2",
            "nodeId": "node-1",
        })
        mock_client.control_service = AsyncMock(return_value={"status": "queued"})

        result = await execute_tool("control_service", {
            "serviceId": "svc-nginx-a1b2",
            "action": "restart",
        })

        assert isinstance(result, str)
        mock_client.control_service.assert_called_once_with(
            node_id="node-1",
            service_id="svc-nginx-a1b2",
            action="restart",
            parameters=None,
        )

    async def test_control_service_not_found(self, mock_client):
        """Test control_service tool with non-existent service."""
        mock_client.get_service = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="Service not found"):
            await execute_tool("control_service", {
                "serviceId": "svc-nonexistent",
                "action": "restart",
            })

    async def test_control_node_tool(self, mock_client):
        """Test control_node tool execution."""
        mock_client.control_node = AsyncMock(return_value={"status": "queued"})

        result = await execute_tool("control_node", {
            "nodeId": "server-01",
            "action": "reboot",
            "confirm": True,
        })

        assert isinstance(result, str)
        mock_client.control_node.assert_called_once_with(
            node_id="server-01",
            action="reboot",
            parameters={"confirm": True},
        )

    async def test_control_agent_tool(self, mock_client):
        """Test control_agent tool execution."""
        mock_client.control_agent = AsyncMock(return_value={"status": "queued"})

        result = await execute_tool("control_agent", {
            "nodeId": "server-01",
            "action": "collect-now",
        })

        assert isinstance(result, str)
        mock_client.control_agent.assert_called_once_with(
            node_id="server-01",
            action="collect-now",
        )

    async def test_get_command_status_tool(self, mock_client):
        """Test get_command_status tool execution."""
        mock_client.get_command_status = AsyncMock(return_value={
            "commandId": "cmd-abc123",
            "status": "completed",
            "result": {"success": True, "output": "OK"},
        })

        result = await execute_tool("get_command_status", {
            "commandId": "cmd-abc123",
        })

        assert isinstance(result, str)
        mock_client.get_command_status.assert_called_once_with("cmd-abc123")

    async def test_internal_only_tool_blocked_for_external_client(self, mock_client):
        """Test that internal-only tools are blocked for external clients."""
        from hydra_mcp.auth import AuthContext, SourceRestrictionError, set_auth_context

        # Set auth context as external client
        set_auth_context(AuthContext(
            user_id="user_admin123",
            permissions=["*:*"],
            role="admin",
            source_type="external",
            client_id="claude-desktop-abc123",
        ))

        mock_client.get_service = AsyncMock(return_value={
            "serviceId": "svc-nginx-a1b2",
            "nodeId": "node-1",
        })

        try:
            with pytest.raises(SourceRestrictionError) as exc_info:
                await execute_tool("control_service", {
                    "serviceId": "svc-nginx-a1b2",
                    "action": "restart",
                })
            assert exc_info.value.tool == "control_service"
            assert "Hydra web interface" in exc_info.value.message
        finally:
            set_auth_context(None)

    async def test_read_tool_allowed_for_external_client(self, mock_client):
        """Test that read tools (get_command_status) work for external clients."""
        from hydra_mcp.auth import AuthContext, set_auth_context

        set_auth_context(AuthContext(
            user_id="user_admin123",
            permissions=["commands:read"],
            role="admin",
            source_type="external",
        ))

        mock_client.get_command_status = AsyncMock(return_value={
            "commandId": "cmd-abc123",
            "status": "completed",
        })

        try:
            result = await execute_tool("get_command_status", {
                "commandId": "cmd-abc123",
            })
            assert isinstance(result, str)
        finally:
            set_auth_context(None)

    async def test_control_device_tool(self, mock_client):
        """Test control_device tool execution."""
        mock_client.control_device = AsyncMock(return_value={"status": "ok"})

        result = await execute_tool("control_device", {
            "entityId": "light.living_room",
            "service": "turn_on",
            "parameters": {"brightness": 255},
        })

        assert isinstance(result, str)
        mock_client.control_device.assert_called_once_with(
            entity_id="light.living_room",
            service="turn_on",
            data={"brightness": 255},
        )

    async def test_control_device_rejects_excessive_parameters(self, mock_client):
        """Test that flexible object args still have size caps."""
        with pytest.raises(ToolValidationError):
            await execute_tool(
                "control_device",
                {
                    "entityId": "light.living_room",
                    "service": "turn_on",
                    "parameters": {f"key_{i}": i for i in range(21)},
                },
            )

    async def test_unknown_tool_raises(self, mock_client):
        """Test that unknown tool raises ValueError."""
        with pytest.raises(ValueError, match="Unknown tool"):
            await execute_tool("nonexistent_tool", {})


@pytest.mark.asyncio
class TestCallTool:
    """Tests for the call_tool MCP handler."""

    @pytest.fixture
    def mock_execute_tool(self):
        """Mock execute_tool for testing call_tool wrapper."""
        with patch("hydra_mcp.server.registry_execute_tool") as mock:
            yield mock

    async def test_successful_call_returns_text_content(self, mock_execute_tool):
        """Test successful tool call returns TextContent."""
        mock_execute_tool.return_value = "nodes: [node-1, node-2]"

        result = await call_tool("list_nodes", {})

        assert result.isError is None or result.isError is False
        assert len(result.content) == 1
        assert result.content[0].text == "nodes: [node-1, node-2]"

    async def test_api_error_returns_error_result(self, mock_execute_tool):
        """Test API error returns error result."""
        from hydra_mcp.client import HydraAPIError
        mock_execute_tool.side_effect = HydraAPIError(
            code="NOT_FOUND",
            message="Node not found",
            details={"nodeId": "missing"}
        )

        result = await call_tool("get_node", {"nodeId": "missing"})

        assert result.isError is True
        assert "NOT_FOUND" in result.content[0].text or "not found" in result.content[0].text.lower()

    async def test_api_connection_error_is_sanitized(self, mock_execute_tool):
        """Test connection failures return generic MCP-safe text."""
        mock_execute_tool.side_effect = HydraAPIError(
            code="CONNECTION_ERROR",
            message="Failed to connect to API: http://hydra-api.internal:8080",
        )

        result = await call_tool("list_nodes", {})

        assert result.isError is True
        assert "TOOL_ERROR" in result.content[0].text
        assert "hydra-api.internal" not in result.content[0].text
        assert "Failed to connect to API" not in result.content[0].text

    async def test_generic_error_returns_error_result(self, mock_execute_tool):
        """Test generic exception returns sanitized error result (SEC-027)."""
        mock_execute_tool.side_effect = Exception("Something went wrong")

        result = await call_tool("list_nodes", {})

        assert result.isError is True
        assert "TOOL_ERROR" in result.content[0].text
        # Internal details must NOT leak to the client
        assert "Something went wrong" not in result.content[0].text

    async def test_validation_error_returns_error_result(self, mock_execute_tool):
        """Test validation error returns error result with details."""
        mock_execute_tool.side_effect = ToolValidationError(
            tool_name="get_node",
            message="'nodeId' is a required property",
            errors=["'nodeId' is a required property"],
        )

        result = await call_tool("get_node", {})

        assert result.isError is True
        assert "VALIDATION_ERROR" in result.content[0].text or "nodeId" in result.content[0].text


@pytest.mark.asyncio
class TestHydraClientAuthForwarding:
    """Tests for user-auth forwarding from MCP context to hydra-api."""

    @pytest.fixture(autouse=True)
    def clear_auth_context(self):
        set_auth_context(None)
        yield
        set_auth_context(None)

    async def test_request_forwards_context_auth_headers(self, monkeypatch):
        mock_http_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"ok": True}}
        mock_http_client.request = AsyncMock(return_value=mock_response)

        hydra_client = HydraClient(
            settings=SimpleNamespace(
                api_url="http://hydra-api",
                api_key="service-api-key",
                api_timeout=5,
                transport="http",
            )
        )
        monkeypatch.setattr(hydra_client, "_get_client", AsyncMock(return_value=mock_http_client))
        set_auth_context(
            AuthContext(
                user_id="user_123",
                permissions=["nodes:read"],
                metadata={"forward_auth": {"Authorization": "Bearer user-token"}},
            )
        )

        result = await hydra_client._request("GET", "/nodes")

        assert result == {"ok": True}
        assert mock_http_client.request.await_args.kwargs["headers"] == {
            "Authorization": "Bearer user-token"
        }

    async def test_network_request_without_forward_headers_fails_closed(self, monkeypatch):
        mock_http_client = AsyncMock()
        hydra_client = HydraClient(
            settings=SimpleNamespace(
                api_url="http://hydra-api",
                api_key="service-api-key",
                api_timeout=5,
                transport="http",
            )
        )
        monkeypatch.setattr(hydra_client, "_get_client", AsyncMock(return_value=mock_http_client))
        set_auth_context(AuthContext(user_id="user_123", permissions=["nodes:read"]))

        with pytest.raises(HydraAPIError, match="missing forward auth headers"):
            await hydra_client._request("GET", "/nodes")


@pytest.mark.asyncio
class TestHydraClientResponseValidation:
    """Tests for strict response-shape handling in HydraClient list methods."""

    @pytest.mark.parametrize(
        ("method_name", "kwargs", "endpoint"),
        [
            ("list_nodes", {}, "/nodes"),
            ("list_services", {}, "/services"),
            ("list_groups", {}, "/groups"),
            ("list_networks", {}, "/networks"),
            ("list_notifications", {}, "/notifications"),
            ("list_command_catalog", {}, "/command-catalog"),
            ("list_commands", {}, "/commands"),
            ("list_audit_entries", {}, "/audit"),
        ],
    )
    async def test_list_methods_raise_on_non_list_response(
        self,
        monkeypatch,
        method_name,
        kwargs,
        endpoint,
    ):
        hydra_client = HydraClient(
            settings=SimpleNamespace(
                api_url="http://hydra-api",
                api_key="service-api-key",
                api_timeout=5,
                transport="stdio",
            )
        )
        monkeypatch.setattr(
            hydra_client,
            "_request",
            AsyncMock(return_value={"items": []}),
        )
        monkeypatch.setattr(
            hydra_client,
            "_request_with_meta",
            AsyncMock(return_value=({"items": []}, None)),
        )

        with pytest.raises(HydraAPIError) as exc_info:
            await getattr(hydra_client, method_name)(**kwargs)

        assert exc_info.value.code == "INVALID_RESPONSE"
        assert endpoint in exc_info.value.message

    @pytest.mark.parametrize(
        ("method_name", "endpoint"),
        [
            ("list_nodes", "/nodes"),
            ("list_services", "/services"),
            ("list_groups", "/groups"),
            ("list_networks", "/networks"),
            ("list_notifications", "/notifications"),
        ],
    )
    async def test_tuple_list_methods_return_api_totals(
        self,
        monkeypatch,
        method_name,
        endpoint,
    ):
        hydra_client = HydraClient(
            settings=SimpleNamespace(
                api_url="http://hydra-api",
                api_key="service-api-key",
                api_timeout=5,
                transport="stdio",
            )
        )
        monkeypatch.setattr(
            hydra_client,
            "_request_with_meta",
            AsyncMock(return_value=([{"id": "item-1"}], {"total": 7})),
        )

        items, total = await getattr(hydra_client, method_name)()

        assert items == [{"id": "item-1"}]
        assert total == 7
        hydra_client._request_with_meta.assert_awaited_once()
        assert hydra_client._request_with_meta.await_args.args[1] == endpoint


class TestInternalContextForwarding:
    """Tests for internal API-to-MCP auth propagation."""

    def test_internal_context_preserves_forward_headers(self, monkeypatch):
        server_module = importlib.import_module("hydra_mcp.server")
        monkeypatch.setattr(
            server_module,
            "get_settings",
            lambda: SimpleNamespace(internal_secret="internal-secret-for-tests-0123456789"),
        )

        context = _build_internal_context(
            {
                INTERNAL_REQUEST_HEADER: "true",
                INTERNAL_USER_ID_HEADER: "user_admin123",
                INTERNAL_ROLE_HEADER: "admin",
                INTERNAL_PERMISSIONS_HEADER: '["*:*"]',
                INTERNAL_CLIENT_ID_HEADER: "hydra-api",
                INTERNAL_SECRET_HEADER: "internal-secret-for-tests-0123456789",
            }
        )

        assert context is not None
        assert context.user_id == "user_admin123"
        assert context.metadata["forward_auth"] == {
            INTERNAL_REQUEST_HEADER: "true",
            INTERNAL_USER_ID_HEADER: "user_admin123",
            INTERNAL_ROLE_HEADER: "admin",
            INTERNAL_PERMISSIONS_HEADER: '["*:*"]',
            INTERNAL_CLIENT_ID_HEADER: "hydra-api",
            INTERNAL_SECRET_HEADER: "internal-secret-for-tests-0123456789",
        }

    def test_internal_context_requires_configured_secret(self, monkeypatch):
        server_module = importlib.import_module("hydra_mcp.server")
        monkeypatch.setattr(
            server_module,
            "get_settings",
            lambda: SimpleNamespace(internal_secret=None),
        )

        with pytest.raises(PermissionError, match="not configured"):
            _build_internal_context(
                {
                    INTERNAL_REQUEST_HEADER: "true",
                    INTERNAL_USER_ID_HEADER: "user_admin123",
                    INTERNAL_ROLE_HEADER: "admin",
                    INTERNAL_SECRET_HEADER: "internal-secret-for-tests-0123456789",
                }
            )


class TestExternalContextForwarding:
    """Tests for external network auth handling."""

    @pytest.mark.asyncio
    async def test_request_context_falls_back_to_configured_api_key(self, monkeypatch):
        server_module = importlib.import_module("hydra_mcp.server")
        monkeypatch.setattr(
            server_module,
            "settings",
            SimpleNamespace(
                api_url="http://hydra-api/api/v1",
                api_key="server-api-key",
                api_timeout=5,
                server_name="hydra-mcp",
            ),
        )

        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "userId": "svc_hydra_mcp",
            "permissions": ["nodes:read"],
            "role": "operator",
        }
        response.raise_for_status.return_value = None

        class DummyAsyncClient:
            def __init__(self, *, timeout):
                self.timeout = timeout

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, url, headers):
                assert url == "http://hydra-api/api/v1/auth/me"
                assert headers == {"X-API-Key": "server-api-key"}
                return response

        monkeypatch.setattr(server_module.httpx, "AsyncClient", DummyAsyncClient)

        context = await _build_request_auth_context({})

        assert context is not None
        assert context.user_id == "svc_hydra_mcp"
        assert context.source_type == "external"
        assert context.client_id == "hydra-mcp"
        assert context.metadata["source"] == "server_api_key"
        assert context.metadata["forward_auth"] == {"X-API-Key": "server-api-key"}
