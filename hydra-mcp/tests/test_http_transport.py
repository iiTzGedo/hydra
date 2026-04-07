"""Tests for HTTP transport endpoints."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

# Import will be patched
pytestmark = pytest.mark.asyncio


def _get_test_client(app):
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    async def test_health_returns_status(self):
        """Health endpoint should return server status."""
        from hydra_mcp.server import create_http_app

        with patch("hydra_mcp.server.list_tools") as mock_tools, \
             patch("hydra_mcp.server.list_resources") as mock_resources, \
             patch("hydra_mcp.server._build_request_auth_context", AsyncMock(return_value=None)):

            # Mock the tool and resource lists
            mock_tools_result = AsyncMock()
            mock_tools_result.tools = []
            mock_tools.return_value = mock_tools_result

            mock_resources_result = AsyncMock()
            mock_resources_result.resources = []
            mock_resources.return_value = mock_resources_result

            app = create_http_app()
            async with _get_test_client(app) as client:
                response = await client.get("/health")

            assert response.status_code == 200

            data = response.json()
            assert "status" in data
            assert data["status"] == "healthy"
            assert "transport" in data
            assert data["transport"] == "http"


class TestToolsEndpoint:
    """Tests for /tools endpoints."""

    async def test_list_tools_returns_array(self):
        """Tools endpoint should return list of tools."""
        from hydra_mcp.server import create_http_app

        app = create_http_app()
        async with _get_test_client(app) as client:
            with patch(
                "hydra_mcp.server._build_request_auth_context",
                AsyncMock(return_value=None),
            ):
                response = await client.get("/tools")
        assert response.status_code == 200

        data = response.json()
        assert "tools" in data
        assert isinstance(data["tools"], list)

    async def test_auth_failures_return_sanitized_message(self):
        """HTTP auth failures should not expose internal details."""
        from hydra_mcp.server import create_http_app

        app = create_http_app()
        async with _get_test_client(app) as client:
            with patch(
                "hydra_mcp.server._build_request_auth_context",
                AsyncMock(side_effect=PermissionError("Invalid internal request secret")),
            ):
                response = await client.get("/tools")

        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "UNAUTHORIZED"
        assert data["error"]["message"] == "Authentication failed for this MCP request"
        assert "secret" not in data["error"]["message"].lower()


class TestResourcesEndpoint:
    """Tests for /resources endpoints."""

    async def test_list_resources_returns_array(self):
        """Resources endpoint should return list of resources."""
        from hydra_mcp.server import create_http_app

        app = create_http_app()
        async with _get_test_client(app) as client:
            with patch(
                "hydra_mcp.server._build_request_auth_context",
                AsyncMock(return_value=None),
            ):
                response = await client.get("/resources")
        assert response.status_code == 200

        data = response.json()
        assert "resources" in data
        assert isinstance(data["resources"], list)


class TestPromptsEndpoint:
    """Tests for /prompts endpoint."""

    async def test_list_prompts_returns_array(self):
        """Prompts endpoint should return list of prompts."""
        from hydra_mcp.server import create_http_app

        app = create_http_app()
        async with _get_test_client(app) as client:
            with patch(
                "hydra_mcp.server._build_request_auth_context",
                AsyncMock(return_value=None),
            ):
                response = await client.get("/prompts")
        assert response.status_code == 200

        data = response.json()
        assert "prompts" in data
        assert isinstance(data["prompts"], list)
