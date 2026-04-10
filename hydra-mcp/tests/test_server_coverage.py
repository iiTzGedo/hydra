"""Tests for server.py functions: auth context building, call_tool, resources, prompts."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from hydra_mcp.auth import (
    AuthorizationError,
    SourceRestrictionError,
)
from hydra_mcp.client import HydraAPIError
from hydra_mcp.server import (
    _build_auth_error_response,
    _build_internal_context,
    _build_request_auth_context,
    _build_text_resource_result,
    _map_hydra_api_error,
    _parse_internal_permissions,
    _read_resource,
    call_tool,
    list_prompts,
    list_resources,
    list_tools,
    read_resource,
)
from hydra_mcp.tools import ToolValidationError

# ---------------------------------------------------------------------------
# _parse_internal_permissions
# ---------------------------------------------------------------------------

class TestParseInternalPermissions:
    def test_valid_json_list(self):
        result = _parse_internal_permissions('["nodes:read","services:write"]')
        assert result == ["nodes:read", "services:write"]

    def test_comma_separated_string(self):
        result = _parse_internal_permissions("nodes:read, services:write")
        assert result == ["nodes:read", "services:write"]

    def test_empty_string(self):
        assert _parse_internal_permissions("") == []

    def test_none_value(self):
        assert _parse_internal_permissions(None) == []

    def test_invalid_json_falls_back_to_comma(self):
        result = _parse_internal_permissions("{not-json}")
        assert result == ["{not-json}"]

    def test_json_list_with_non_strings_filtered(self):
        result = _parse_internal_permissions('[1, "nodes:read", null, "services:*"]')
        assert result == ["nodes:read", "services:*"]


# ---------------------------------------------------------------------------
# _build_internal_context
# ---------------------------------------------------------------------------

class TestBuildInternalContext:
    def test_returns_none_when_not_internal(self):
        headers = {"x-hydra-internal-request": "false"}
        assert _build_internal_context(headers) is None

    def test_returns_none_when_header_missing(self):
        assert _build_internal_context({}) is None

    def test_raises_when_secret_not_configured(self):
        headers = {"x-hydra-internal-request": "true"}
        with patch("hydra_mcp.server.get_settings", return_value=SimpleNamespace(internal_secret=None)), \
             pytest.raises(PermissionError, match="not configured"):
            _build_internal_context(headers)

    def test_raises_when_secret_wrong(self):
        headers = {
            "x-hydra-internal-request": "true",
            "x-hydra-internal-secret": "wrong-secret",
        }
        with patch(
            "hydra_mcp.server.get_settings",
            return_value=SimpleNamespace(
                internal_secret="correct-secret-that-is-long-enough-32chars",
            ),
        ), pytest.raises(PermissionError, match="Invalid"):
            _build_internal_context(headers)

    def test_raises_when_user_or_role_missing(self):
        secret = "correct-secret-that-is-long-enough-32chars"
        headers = {
            "x-hydra-internal-request": "1",
            "x-hydra-internal-secret": secret,
            "x-hydra-user-id": "user1",
            # missing role
        }
        with patch(
            "hydra_mcp.server.get_settings",
            return_value=SimpleNamespace(internal_secret=secret),
        ), pytest.raises(PermissionError, match="must include"):
            _build_internal_context(headers)

    def test_success(self):
        secret = "correct-secret-that-is-long-enough-32chars"
        headers = {
            "x-hydra-internal-request": "yes",
            "x-hydra-internal-secret": secret,
            "x-hydra-user-id": "user1",
            "x-hydra-role": "admin",
            "x-hydra-permissions": '["*:*"]',
        }
        with patch("hydra_mcp.server.get_settings", return_value=SimpleNamespace(internal_secret=secret)):
            ctx = _build_internal_context(headers)
            assert ctx is not None
            assert ctx.user_id == "user1"
            assert ctx.role == "admin"
            assert ctx.source_type == "internal"


# ---------------------------------------------------------------------------
# _build_request_auth_context (combines internal + external)
# ---------------------------------------------------------------------------

class TestBuildRequestAuthContext:
    async def test_prefers_internal_over_external(self):
        secret = "correct-secret-that-is-long-enough-32chars"
        headers = {
            "x-hydra-internal-request": "true",
            "x-hydra-internal-secret": secret,
            "x-hydra-user-id": "user1",
            "x-hydra-role": "admin",
            "x-hydra-permissions": '["*:*"]',
        }
        with patch("hydra_mcp.server.get_settings", return_value=SimpleNamespace(internal_secret=secret)):
            ctx = await _build_request_auth_context(headers)
            assert ctx is not None
            assert ctx.source_type == "internal"

    async def test_falls_back_to_external(self):
        with patch("hydra_mcp.server._build_internal_context", return_value=None), \
             patch("hydra_mcp.server._build_external_context", AsyncMock(return_value=None)) as mock_ext:
            result = await _build_request_auth_context({})
            mock_ext.assert_called_once()
            assert result is None


# ---------------------------------------------------------------------------
# _build_auth_error_response
# ---------------------------------------------------------------------------

class TestBuildAuthErrorResponse:
    def test_returns_401_json(self):
        resp = _build_auth_error_response()
        assert resp.status_code == 401
        body = json.loads(resp.body)
        assert body["error"]["code"] == "UNAUTHORIZED"


# ---------------------------------------------------------------------------
# _map_hydra_api_error
# ---------------------------------------------------------------------------

class TestMapHydraApiError:
    def test_safe_error_passthrough(self):
        err = HydraAPIError("NOT_FOUND", "Node not found", {"id": "n1"})
        code, msg, details = _map_hydra_api_error(err, fallback_code="X", fallback_message="Y")
        assert code == "NOT_FOUND"
        assert msg == "Node not found"
        assert details == {"id": "n1"}

    def test_validation_error_passthrough(self):
        err = HydraAPIError("VALIDATION_ERROR", "Bad input")
        code, msg, _ = _map_hydra_api_error(err, fallback_code="X", fallback_message="Y")
        assert code == "VALIDATION_ERROR"

    def test_forbidden_sanitized(self):
        err = HydraAPIError("FORBIDDEN", "You shall not pass")
        code, msg, details = _map_hydra_api_error(err, fallback_code="X", fallback_message="Y")
        assert code == "FORBIDDEN"
        assert "rejected" in msg
        assert details is None

    def test_connection_error_uses_fallback(self):
        err = HydraAPIError("CONNECTION_ERROR", "Connection refused")
        code, msg, details = _map_hydra_api_error(err, fallback_code="TOOL_ERROR", fallback_message="Internal error")
        assert code == "TOOL_ERROR"
        assert msg == "Internal error"

    def test_unknown_code_uses_fallback(self):
        err = HydraAPIError("WEIRD_ERROR", "Something weird")
        code, msg, details = _map_hydra_api_error(err, fallback_code="FB", fallback_message="Fallback")
        assert code == "FB"
        assert msg == "Fallback"


# ---------------------------------------------------------------------------
# _build_text_resource_result
# ---------------------------------------------------------------------------

class TestBuildTextResourceResult:
    def test_builds_result(self):
        result = _build_text_resource_result("infrastructure://nodes", "hello")
        assert len(result.contents) == 1
        assert result.contents[0].text == "hello"


# ---------------------------------------------------------------------------
# call_tool
# ---------------------------------------------------------------------------

class TestCallTool:
    async def test_successful_tool_call(self):
        with patch("hydra_mcp.server.registry_execute_tool", AsyncMock(return_value="result-text")):
            result = await call_tool("list_nodes", {"limit": 10})
            assert result.content[0].text == "result-text"
            assert not getattr(result, "isError", False)

    async def test_validation_error(self):
        exc = ToolValidationError("test_tool", "bad input", ["error1"])
        with patch("hydra_mcp.server.registry_execute_tool", AsyncMock(side_effect=exc)):
            result = await call_tool("test_tool", {})
            assert result.isError is True
            assert "VALIDATION_ERROR" in result.content[0].text

    async def test_authorization_error(self):
        exc = AuthorizationError("list_nodes", "nodes:read")
        with patch("hydra_mcp.server.registry_execute_tool", AsyncMock(side_effect=exc)):
            result = await call_tool("list_nodes", {})
            assert result.isError is True
            assert "AUTHORIZATION_DENIED" in result.content[0].text

    async def test_source_restriction_error(self):
        exc = SourceRestrictionError(
            "control_service", "restart",
            {"guidance": "Use web UI", "alternativeActions": []},
        )
        with patch("hydra_mcp.server.registry_execute_tool", AsyncMock(side_effect=exc)):
            result = await call_tool("control_service", {"action": "restart"})
            assert result.isError is True
            assert "CLIENT_NOT_AUTHORIZED" in result.content[0].text

    async def test_api_error_safe_code(self):
        exc = HydraAPIError("NOT_FOUND", "Node not found")
        with patch("hydra_mcp.server.registry_execute_tool", AsyncMock(side_effect=exc)):
            result = await call_tool("get_node", {"nodeId": "missing"})
            assert result.isError is True
            assert "NOT_FOUND" in result.content[0].text

    async def test_api_error_unsafe_code(self):
        exc = HydraAPIError("CONNECTION_ERROR", "Cannot connect")
        with patch("hydra_mcp.server.registry_execute_tool", AsyncMock(side_effect=exc)):
            result = await call_tool("list_nodes", {})
            assert result.isError is True
            assert "TOOL_ERROR" in result.content[0].text

    async def test_api_error_write_tool_emits_notification(self):
        exc = HydraAPIError("INTERNAL_ERROR", "DB failure")
        with patch("hydra_mcp.server.registry_execute_tool", AsyncMock(side_effect=exc)), \
             patch("hydra_mcp.server._emit_mcp_notification", AsyncMock()):
            result = await call_tool("control_service", {"serviceId": "s1", "action": "restart"})
            assert result.isError is True

    async def test_generic_exception(self):
        with patch("hydra_mcp.server.registry_execute_tool", AsyncMock(side_effect=RuntimeError("boom"))):
            result = await call_tool("list_nodes", {})
            assert result.isError is True
            assert "TOOL_ERROR" in result.content[0].text

    async def test_generic_exception_write_tool(self):
        with patch("hydra_mcp.server.registry_execute_tool", AsyncMock(side_effect=RuntimeError("boom"))):
            result = await call_tool("control_service", {"serviceId": "s1", "action": "stop"})
            assert result.isError is True

    async def test_successful_write_tool_notification(self):
        with patch("hydra_mcp.server.registry_execute_tool", AsyncMock(return_value="ok")):
            result = await call_tool("control_service", {"serviceId": "s1", "action": "start"})
            assert result.content[0].text == "ok"


# ---------------------------------------------------------------------------
# list_tools / list_resources / list_prompts
# ---------------------------------------------------------------------------

class TestListEndpoints:
    async def test_list_tools_returns_tools(self):
        result = await list_tools()
        assert len(result.tools) > 0

    async def test_list_resources_returns_resources(self):
        result = await list_resources()
        assert len(result.resources) == 6
        uris = [str(r.uri) for r in result.resources]
        assert "infrastructure://overview" in uris

    async def test_list_prompts_returns_prompts(self):
        result = await list_prompts()
        assert len(result.prompts) == 6
        names = [p.name for p in result.prompts]
        assert "capacity_planning" in names
        assert "troubleshoot_network" in names


# ---------------------------------------------------------------------------
# _read_resource
# ---------------------------------------------------------------------------

class TestReadResource:
    async def test_overview_resource(self):
        with patch("hydra_mcp.server.client") as mock_client:
            mock_client.get_info = AsyncMock(return_value={"version": "0.5.0"})
            result = await _read_resource("infrastructure://overview")
            assert isinstance(result, str)

    async def test_nodes_resource(self):
        with patch("hydra_mcp.server.client") as mock_client:
            mock_client.list_nodes = AsyncMock(return_value=([{"nodeId": "n1"}], 1))
            result = await _read_resource("infrastructure://nodes")
            assert isinstance(result, str)

    async def test_services_resource(self):
        with patch("hydra_mcp.server.client") as mock_client:
            mock_client.list_services = AsyncMock(return_value=([{"serviceId": "s1"}], 1))
            result = await _read_resource("infrastructure://services")
            assert isinstance(result, str)

    async def test_networks_resource(self):
        with patch("hydra_mcp.server.client") as mock_client:
            mock_client.list_networks = AsyncMock(return_value=([{"networkId": "net1"}], 1))
            result = await _read_resource("infrastructure://networks")
            assert isinstance(result, str)

    async def test_network_topology_resource(self):
        with patch("hydra_mcp.server.client") as mock_client:
            mock_client.get_topology = AsyncMock(return_value={"nodes": [], "edges": []})
            result = await _read_resource("infrastructure://topology/network")
            assert isinstance(result, str)

    async def test_infrastructure_topology_resource(self):
        with patch("hydra_mcp.server.client") as mock_client:
            mock_client.get_topology = AsyncMock(return_value={"nodes": [], "edges": []})
            result = await _read_resource("infrastructure://topology/infrastructure")
            assert isinstance(result, str)

    async def test_specific_node_resource(self):
        with patch("hydra_mcp.server.client") as mock_client:
            mock_client.get_node = AsyncMock(return_value={"nodeId": "n1"})
            result = await _read_resource("infrastructure://node/n1")
            assert isinstance(result, str)

    async def test_specific_service_resource(self):
        with patch("hydra_mcp.server.client") as mock_client:
            mock_client.get_service = AsyncMock(return_value={"serviceId": "svc-1"})
            result = await _read_resource("infrastructure://service/svc-1")
            assert isinstance(result, str)

    async def test_unknown_resource_raises(self):
        with pytest.raises(ValueError, match="Unknown resource"):
            await _read_resource("infrastructure://invalid")


# ---------------------------------------------------------------------------
# read_resource (wrapper with error handling)
# ---------------------------------------------------------------------------

class TestReadResourceWrapper:
    async def test_success(self):
        with patch("hydra_mcp.server._read_resource", AsyncMock(return_value="data")):
            result = await read_resource("infrastructure://overview")
            assert result.contents[0].text == "data"

    async def test_value_error(self):
        with patch("hydra_mcp.server._read_resource", AsyncMock(side_effect=ValueError("bad uri"))):
            result = await read_resource("infrastructure://bad")
            assert "INVALID_RESOURCE" in result.contents[0].text

    async def test_api_error(self):
        exc = HydraAPIError("NOT_FOUND", "Not found")
        with patch("hydra_mcp.server._read_resource", AsyncMock(side_effect=exc)):
            result = await read_resource("infrastructure://nodes")
            assert "NOT_FOUND" in result.contents[0].text

    async def test_generic_error(self):
        with patch("hydra_mcp.server._read_resource", AsyncMock(side_effect=RuntimeError("boom"))):
            result = await read_resource("infrastructure://nodes")
            assert "RESOURCE_ERROR" in result.contents[0].text
