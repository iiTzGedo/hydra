"""Tests for HTTP transport endpoints."""

import pytest
from unittest.mock import patch, AsyncMock

# Import will be patched
pytestmark = pytest.mark.asyncio


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    async def test_health_returns_status(self):
        """Health endpoint should return server status."""
        # This test verifies the health endpoint structure
        # Full integration tests require running the actual server
        from hydra.server import create_http_app
        from fastapi.testclient import TestClient

        with patch("hydra.server.list_tools") as mock_tools, \
             patch("hydra.server.list_resources") as mock_resources:

            # Mock the tool and resource lists
            mock_tools_result = AsyncMock()
            mock_tools_result.tools = []
            mock_tools.return_value = mock_tools_result

            mock_resources_result = AsyncMock()
            mock_resources_result.resources = []
            mock_resources.return_value = mock_resources_result

            app = create_http_app()
            client = TestClient(app)

            response = client.get("/health")
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
        from hydra.server import create_http_app
        from fastapi.testclient import TestClient

        app = create_http_app()
        client = TestClient(app)

        response = client.get("/tools")
        assert response.status_code == 200

        data = response.json()
        assert "tools" in data
        assert isinstance(data["tools"], list)


class TestResourcesEndpoint:
    """Tests for /resources endpoints."""

    async def test_list_resources_returns_array(self):
        """Resources endpoint should return list of resources."""
        from hydra.server import create_http_app
        from fastapi.testclient import TestClient

        app = create_http_app()
        client = TestClient(app)

        response = client.get("/resources")
        assert response.status_code == 200

        data = response.json()
        assert "resources" in data
        assert isinstance(data["resources"], list)


class TestPromptsEndpoint:
    """Tests for /prompts endpoint."""

    async def test_list_prompts_returns_array(self):
        """Prompts endpoint should return list of prompts."""
        from hydra.server import create_http_app
        from fastapi.testclient import TestClient

        app = create_http_app()
        client = TestClient(app)

        response = client.get("/prompts")
        assert response.status_code == 200

        data = response.json()
        assert "prompts" in data
        assert isinstance(data["prompts"], list)
