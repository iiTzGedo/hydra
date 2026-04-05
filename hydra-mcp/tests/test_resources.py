"""Tests for MCP resource reading functionality."""

from unittest.mock import AsyncMock, patch

import pytest

from hydra_mcp.client import HydraAPIError
from hydra_mcp.server import _read_resource, read_resource

pytestmark = pytest.mark.asyncio


class TestStaticResources:
    """Tests for static resource URIs."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Hydra API client."""
        with patch("hydra_mcp.server.client") as mock:
            yield mock

    async def test_read_overview_resource(self, mock_client):
        """Test reading infrastructure://overview resource."""
        mock_client.get_info = AsyncMock(return_value={
            "version": "0.3.1",
            "totalNodes": 5,
            "activeNodes": 4,
            "totalServices": 12,
            "runningServices": 10,
        })

        result = await _read_resource("infrastructure://overview")

        assert isinstance(result, str)
        assert len(result) > 0
        mock_client.get_info.assert_called_once()

    async def test_read_nodes_resource(self, mock_client):
        """Test reading infrastructure://nodes resource."""
        mock_nodes = [
            {"nodeId": "node-1", "name": "Server 1", "class": "compute", "status": "active"},
            {"nodeId": "node-2", "name": "Server 2", "class": "networking", "status": "active"},
        ]
        mock_client.list_nodes = AsyncMock(return_value=(mock_nodes, {"total": 2}))

        result = await _read_resource("infrastructure://nodes")

        assert isinstance(result, str)
        assert len(result) > 0
        mock_client.list_nodes.assert_called_once_with(limit=200)

    async def test_read_services_resource(self, mock_client):
        """Test reading infrastructure://services resource."""
        mock_services = [
            {"serviceId": "svc-nginx-a1b2", "name": "nginx", "runtime": "systemd", "status": "running"},
            {"serviceId": "svc-docker-c3d4", "name": "dockerd", "runtime": "systemd", "status": "running"},
        ]
        mock_client.list_services = AsyncMock(return_value=(mock_services, {"total": 2}))

        result = await _read_resource("infrastructure://services")

        assert isinstance(result, str)
        assert len(result) > 0
        mock_client.list_services.assert_called_once_with(limit=200)

    async def test_read_networks_resource(self, mock_client):
        """Test reading infrastructure://networks resource."""
        mock_networks = [
            {"networkId": "net-1", "name": "Main Network", "cidr": "192.168.1.0/24", "type": "physical"},
            {"networkId": "net-2", "name": "Guest Network", "cidr": "192.168.2.0/24", "type": "logical"},
        ]
        mock_client.list_networks = AsyncMock(return_value=(mock_networks, {"total": 2}))

        result = await _read_resource("infrastructure://networks")

        assert isinstance(result, str)
        assert len(result) > 0
        mock_client.list_networks.assert_called_once_with(limit=50)

    async def test_read_network_topology_resource(self, mock_client):
        """Test reading infrastructure://topology/network resource."""
        mock_topology = {
            "mode": "network",
            "nodes": [
                {"id": "node-1", "label": "Server 1"},
                {"id": "node-2", "label": "Server 2"},
            ],
            "edges": [
                {"from": "node-1", "to": "node-2", "label": "connected"},
            ],
        }
        mock_client.get_topology = AsyncMock(return_value=mock_topology)

        result = await _read_resource("infrastructure://topology/network")

        assert isinstance(result, str)
        assert len(result) > 0
        mock_client.get_topology.assert_called_once_with(mode="network")

    async def test_read_infrastructure_topology_resource(self, mock_client):
        """Test reading infrastructure://topology/infrastructure resource."""
        mock_topology = {
            "mode": "infrastructure",
            "nodes": [
                {"id": "node-1", "label": "Server 1", "class": "compute"},
                {"id": "node-2", "label": "Server 2", "class": "compute"},
            ],
            "edges": [
                {"from": "node-1", "to": "node-2", "label": "parent"},
            ],
        }
        mock_client.get_topology = AsyncMock(return_value=mock_topology)

        result = await _read_resource("infrastructure://topology/infrastructure")

        assert isinstance(result, str)
        assert len(result) > 0
        mock_client.get_topology.assert_called_once_with(mode="infrastructure")


class TestDynamicResources:
    """Tests for dynamic resource URIs with parameters."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Hydra API client."""
        with patch("hydra_mcp.server.client") as mock:
            yield mock

    async def test_read_node_resource(self, mock_client):
        """Test reading infrastructure://node/{nodeId} resource."""
        mock_node = {
            "nodeId": "test-node",
            "name": "Test Node",
            "class": "compute",
            "type": "physical",
            "status": "active",
            "services": ["svc-nginx-a1b2", "svc-docker-c3d4"],
            "children": ["child-1", "child-2"],
        }
        mock_client.get_node = AsyncMock(return_value=mock_node)

        result = await _read_resource("infrastructure://node/test-node")

        assert isinstance(result, str)
        assert len(result) > 0
        mock_client.get_node.assert_called_once_with("test-node")

    async def test_read_node_resource_extracts_id(self, mock_client):
        """Test that node ID is properly extracted from URI."""
        mock_node = {"nodeId": "my-special-node", "status": "active"}
        mock_client.get_node = AsyncMock(return_value=mock_node)

        await _read_resource("infrastructure://node/my-special-node")

        # Verify the extracted ID was passed to get_node
        mock_client.get_node.assert_called_once_with("my-special-node")

    async def test_read_service_resource(self, mock_client):
        """Test reading infrastructure://service/{serviceId} resource."""
        mock_service = {
            "serviceId": "svc-nginx-a1b2",
            "name": "nginx",
            "runtime": "systemd",
            "status": "running",
            "nodeId": "node-1",
        }
        mock_client.get_service = AsyncMock(return_value=mock_service)

        result = await _read_resource("infrastructure://service/svc-nginx-a1b2")

        assert isinstance(result, str)
        assert len(result) > 0
        mock_client.get_service.assert_called_once_with("svc-nginx-a1b2")

    async def test_read_service_resource_extracts_id(self, mock_client):
        """Test that service ID is properly extracted from URI."""
        mock_service = {"serviceId": "svc-custom-xyz9", "status": "running"}
        mock_client.get_service = AsyncMock(return_value=mock_service)

        await _read_resource("infrastructure://service/svc-custom-xyz9")

        # Verify the extracted ID was passed to get_service
        mock_client.get_service.assert_called_once_with("svc-custom-xyz9")


class TestResourceErrorHandling:
    """Tests for resource error handling."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Hydra API client."""
        with patch("hydra_mcp.server.client") as mock:
            yield mock

    async def test_unknown_resource_uri_raises(self, mock_client):
        """Test that unknown resource URI raises ValueError."""
        with pytest.raises(ValueError, match="Unknown resource"):
            await _read_resource("infrastructure://unknown")

    async def test_unknown_resource_pattern_raises(self, mock_client):
        """Test that unknown resource pattern raises ValueError."""
        with pytest.raises(ValueError, match="Unknown resource"):
            await _read_resource("infrastructure://invalid/pattern")

    async def test_empty_uri_raises(self, mock_client):
        """Test that empty URI raises ValueError."""
        with pytest.raises(ValueError, match="Unknown resource"):
            await _read_resource("")

    async def test_malformed_uri_raises(self, mock_client):
        """Test that malformed URI raises ValueError."""
        with pytest.raises(ValueError, match="Unknown resource"):
            await _read_resource("not-a-valid-uri")

    async def test_read_resource_returns_explicit_invalid_resource_error(self, mock_client):
        """Test that invalid resource URIs remain explicit but structured."""
        result = await read_resource("infrastructure://unknown")
        text = result.contents[0].text

        assert "INVALID_RESOURCE" in text
        assert "Unknown resource" in text

    async def test_read_resource_sanitizes_backend_failures(self, mock_client):
        """Test that backend/internal resource failures do not leak details."""
        mock_client.get_info = AsyncMock(
            side_effect=HydraAPIError(
                code="CONNECTION_ERROR",
                message="Failed to connect to API: http://hydra-api.internal:8080",
            )
        )

        result = await read_resource("infrastructure://overview")
        text = result.contents[0].text

        assert "RESOURCE_ERROR" in text
        assert "hydra-api.internal" not in text
        assert "Failed to connect to API" not in text


class TestResourceTOONFormatting:
    """Tests for TOON formatting of resource responses."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Hydra API client."""
        with patch("hydra_mcp.server.client") as mock:
            yield mock

    async def test_nodes_list_formatted_as_toon(self, mock_client):
        """Test that nodes list is formatted as TOON."""
        mock_nodes = [
            {"nodeId": "node-1", "name": "Server 1"},
            {"nodeId": "node-2", "name": "Server 2"},
        ]
        mock_client.list_nodes = AsyncMock(return_value=(mock_nodes, {}))

        result = await _read_resource("infrastructure://nodes")

        # TOON format should be present
        assert isinstance(result, str)
        # Should contain the key "nodes"
        assert "nodes" in result or "[" in result  # TOON uses either format

    async def test_node_detail_formatted_as_toon(self, mock_client):
        """Test that node detail is formatted as TOON."""
        mock_node = {
            "nodeId": "test-node",
            "name": "Test Node",
            "status": "active",
        }
        mock_client.get_node = AsyncMock(return_value=mock_node)

        result = await _read_resource("infrastructure://node/test-node")

        # Should be a TOON-formatted string
        assert isinstance(result, str)
        assert len(result) > 0

    async def test_empty_list_formatted_correctly(self, mock_client):
        """Test that empty lists are formatted correctly."""
        mock_client.list_nodes = AsyncMock(return_value=([], {}))

        result = await _read_resource("infrastructure://nodes")

        # Should still return a valid TOON string, not error
        assert isinstance(result, str)
