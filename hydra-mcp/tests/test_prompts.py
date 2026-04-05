"""Tests for MCP prompt generation functionality."""

from unittest.mock import AsyncMock, patch

import pytest

from hydra_mcp.server import get_prompt

pytestmark = pytest.mark.asyncio


class TestCapacityPlanningPrompt:
    """Tests for capacity_planning prompt."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Hydra API client."""
        with patch("hydra_mcp.server.client") as mock:
            yield mock

    async def test_capacity_planning_with_required_args(self, mock_client):
        """Test capacity_planning prompt with required workload argument."""
        mock_client.get_capacity = AsyncMock(return_value={
            "totalNodes": 10,
            "activeNodes": 8,
            "totalCPU": 80,
            "totalMemory": 256,
        })

        args = {"workload": "New web application"}
        result = await get_prompt("capacity_planning", args)

        assert result.description == "Analyze capacity for new workload"
        assert len(result.messages) == 1
        assert result.messages[0].role == "user"
        assert "New web application" in result.messages[0].content.text
        mock_client.get_capacity.assert_called_once()

    async def test_capacity_planning_with_all_args(self, mock_client):
        """Test capacity_planning prompt with all arguments."""
        mock_client.get_capacity = AsyncMock(return_value={
            "totalNodes": 10,
            "activeNodes": 8,
        })

        args = {
            "workload": "Database cluster",
            "requirements": "8 CPU cores, 32GB RAM, 500GB SSD",
        }
        result = await get_prompt("capacity_planning", args)

        text = result.messages[0].content.text
        assert "Database cluster" in text
        assert "8 CPU cores, 32GB RAM, 500GB SSD" in text
        assert "Assessment of available resources" in text
        assert "Recommended placement" in text

    async def test_capacity_planning_without_optional_args(self, mock_client):
        """Test capacity_planning prompt without optional arguments."""
        mock_client.get_capacity = AsyncMock(return_value={})

        args = {"workload": "Test workload"}
        result = await get_prompt("capacity_planning", args)

        text = result.messages[0].content.text
        assert "Not specified" in text  # Should show for missing requirements


class TestTroubleshootNetworkPrompt:
    """Tests for troubleshoot_network prompt."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Hydra API client."""
        with patch("hydra_mcp.server.client") as mock:
            yield mock

    async def test_troubleshoot_network_with_required_args(self, mock_client):
        """Test troubleshoot_network prompt with required symptoms argument."""
        mock_client.list_networks = AsyncMock(return_value=(
            [{"networkId": "net-1", "cidr": "192.168.1.0/24"}],
            {}
        ))
        mock_client.get_topology = AsyncMock(return_value={
            "mode": "network",
            "nodes": [],
            "edges": [],
        })

        args = {"symptoms": "Cannot connect to web server"}
        result = await get_prompt("troubleshoot_network", args)

        assert result.description == "Diagnose network issues"
        assert len(result.messages) == 1
        text = result.messages[0].content.text
        assert "Cannot connect to web server" in text
        mock_client.list_networks.assert_called_once()
        mock_client.get_topology.assert_called_once_with(mode="network")

    async def test_troubleshoot_network_with_all_args(self, mock_client):
        """Test troubleshoot_network prompt with all arguments."""
        mock_client.list_networks = AsyncMock(return_value=([], {}))
        mock_client.get_topology = AsyncMock(return_value={"mode": "network"})

        args = {
            "symptoms": "Intermittent packet loss",
            "affected_nodes": "node-1, node-2, node-3",
        }
        result = await get_prompt("troubleshoot_network", args)

        text = result.messages[0].content.text
        assert "Intermittent packet loss" in text
        assert "node-1, node-2, node-3" in text
        assert "Likely causes" in text
        assert "Diagnostic steps" in text

    async def test_troubleshoot_network_without_optional_args(self, mock_client):
        """Test troubleshoot_network prompt without optional arguments."""
        mock_client.list_networks = AsyncMock(return_value=([], {}))
        mock_client.get_topology = AsyncMock(return_value={})

        args = {"symptoms": "Network timeout"}
        result = await get_prompt("troubleshoot_network", args)

        text = result.messages[0].content.text
        assert "Not specified" in text  # Should show for missing affected_nodes


class TestInfrastructureAuditPrompt:
    """Tests for infrastructure_audit prompt."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Hydra API client."""
        with patch("hydra_mcp.server.client") as mock:
            yield mock

    async def test_infrastructure_audit_no_required_args(self, mock_client):
        """Test infrastructure_audit prompt with no required arguments."""
        mock_client.list_nodes = AsyncMock(return_value=(
            [{"nodeId": "node-1", "status": "active"}],
            {}
        ))
        mock_client.list_services = AsyncMock(return_value=(
            [{"serviceId": "svc-nginx-a1b2", "status": "running"}],
            {}
        ))

        result = await get_prompt("infrastructure_audit", {})

        assert result.description == "Infrastructure audit"
        assert len(result.messages) == 1
        mock_client.list_nodes.assert_called_once()
        mock_client.list_services.assert_called_once()

    async def test_infrastructure_audit_with_scope(self, mock_client):
        """Test infrastructure_audit prompt with scope argument."""
        mock_client.list_nodes = AsyncMock(return_value=([], {}))
        mock_client.list_services = AsyncMock(return_value=([], {}))

        args = {"scope": "compute"}
        result = await get_prompt("infrastructure_audit", args)

        text = result.messages[0].content.text
        assert "compute" in text
        assert "Security considerations" in text
        assert "Configuration issues" in text

    async def test_infrastructure_audit_with_all_args(self, mock_client):
        """Test infrastructure_audit prompt with all arguments."""
        mock_client.list_nodes = AsyncMock(return_value=([], {}))
        mock_client.list_services = AsyncMock(return_value=([], {}))

        args = {"scope": "networking", "focus": "security"}
        result = await get_prompt("infrastructure_audit", args)

        text = result.messages[0].content.text
        assert "networking" in text
        assert "security" in text
        assert "Best practice deviations" in text

    async def test_infrastructure_audit_defaults(self, mock_client):
        """Test infrastructure_audit prompt uses defaults for missing args."""
        mock_client.list_nodes = AsyncMock(return_value=([], {}))
        mock_client.list_services = AsyncMock(return_value=([], {}))

        result = await get_prompt("infrastructure_audit", None)

        text = result.messages[0].content.text
        assert "all" in text  # Default scope
        assert "general" in text  # Default focus


class TestServiceDependencyMapPrompt:
    """Tests for service_dependency_map prompt."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Hydra API client."""
        with patch("hydra_mcp.server.client") as mock:
            yield mock

    async def test_service_dependency_map_no_required_args(self, mock_client):
        """Test service_dependency_map prompt with no required arguments."""
        mock_client.list_services = AsyncMock(return_value=(
            [{"serviceId": "svc-nginx-a1b2", "name": "nginx"}],
            {}
        ))

        result = await get_prompt("service_dependency_map", {})

        assert result.description == "Map service dependencies"
        assert len(result.messages) == 1
        mock_client.list_services.assert_called_once()

    async def test_service_dependency_map_with_service(self, mock_client):
        """Test service_dependency_map prompt with service argument."""
        mock_client.list_services = AsyncMock(return_value=([], {}))

        args = {"service": "svc-nginx-a1b2"}
        result = await get_prompt("service_dependency_map", args)

        text = result.messages[0].content.text
        assert "svc-nginx-a1b2" in text
        assert "Service dependencies" in text
        assert "single points of failure" in text

    async def test_service_dependency_map_with_all_args(self, mock_client):
        """Test service_dependency_map prompt with all arguments."""
        mock_client.list_services = AsyncMock(return_value=([], {}))

        args = {"service": "svc-database-xyz9", "depth": "3"}
        result = await get_prompt("service_dependency_map", args)

        text = result.messages[0].content.text
        assert "svc-database-xyz9" in text
        assert "3" in text
        assert "Dependency chain risks" in text

    async def test_service_dependency_map_defaults(self, mock_client):
        """Test service_dependency_map prompt uses defaults for missing args."""
        mock_client.list_services = AsyncMock(return_value=([], {}))

        result = await get_prompt("service_dependency_map", None)

        text = result.messages[0].content.text
        assert "All services" in text  # Default service
        assert "Full" in text  # Default depth


class TestMigrationPlanningPrompt:
    """Tests for migration_planning prompt."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Hydra API client."""
        with patch("hydra_mcp.server.client") as mock:
            yield mock

    async def test_migration_planning_with_required_args(self, mock_client):
        """Test migration_planning prompt with required arguments."""
        mock_client.get_node = AsyncMock(return_value={
            "nodeId": "source-node",
            "name": "Source Server",
            "status": "active",
        })

        args = {"source": "source-node", "target": "target-node"}
        result = await get_prompt("migration_planning", args)

        assert result.description == "Plan infrastructure migration"
        assert len(result.messages) == 1
        text = result.messages[0].content.text
        assert "Source Server" in text or "source-node" in text
        assert "target-node" in text
        assert "Pre-migration checklist" in text
        assert "Migration steps" in text
        assert "Rollback plan" in text
        mock_client.get_node.assert_called_once_with("source-node")

    async def test_migration_planning_handles_api_error(self, mock_client):
        """Test migration_planning prompt when source node not found."""
        mock_client.get_node = AsyncMock(side_effect=Exception("Node not found"))

        args = {"source": "nonexistent-node", "target": "target-node"}
        result = await get_prompt("migration_planning", args)

        text = result.messages[0].content.text
        assert "nonexistent-node" in text
        assert "details unavailable" in text or "nonexistent-node" in text
        assert "target-node" in text

    async def test_migration_planning_message_structure(self, mock_client):
        """Test migration_planning prompt has proper message structure."""
        mock_client.get_node = AsyncMock(return_value={"nodeId": "src"})

        args = {"source": "src", "target": "dst"}
        result = await get_prompt("migration_planning", args)

        text = result.messages[0].content.text
        assert "Pre-migration checklist" in text
        assert "Service dependencies" in text
        assert "Verification steps" in text
        assert "Estimated impact and downtime" in text


class TestDocumentationGeneratorPrompt:
    """Tests for documentation_generator prompt."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Hydra API client."""
        with patch("hydra_mcp.server.client") as mock:
            yield mock

    async def test_documentation_generator_for_node(self, mock_client):
        """Test documentation_generator prompt for node entity."""
        mock_client.get_node = AsyncMock(return_value={
            "nodeId": "test-node",
            "name": "Test Node",
            "class": "compute",
            "status": "active",
        })

        args = {"entity_type": "node", "entity_id": "test-node"}
        result = await get_prompt("documentation_generator", args)

        assert result.description == "Generate documentation"
        assert len(result.messages) == 1
        text = result.messages[0].content.text
        assert "Test Node" in text or "test-node" in text
        assert "Overview and purpose" in text
        assert "Technical specifications" in text
        assert "Troubleshooting guide" in text
        mock_client.get_node.assert_called_once_with("test-node")

    async def test_documentation_generator_for_service(self, mock_client):
        """Test documentation_generator prompt for service entity."""
        mock_client.get_service = AsyncMock(return_value={
            "serviceId": "svc-nginx-a1b2",
            "name": "nginx",
            "runtime": "systemd",
            "status": "running",
        })

        args = {"entity_type": "service", "entity_id": "svc-nginx-a1b2"}
        result = await get_prompt("documentation_generator", args)

        text = result.messages[0].content.text
        assert "nginx" in text or "svc-nginx-a1b2" in text
        assert "Configuration details" in text
        assert "Dependencies and relationships" in text
        mock_client.get_service.assert_called_once_with("svc-nginx-a1b2")

    async def test_documentation_generator_for_network(self, mock_client):
        """Test documentation_generator prompt for network entity."""
        mock_client.get_network = AsyncMock(return_value={
            "networkId": "net-1",
            "name": "Main Network",
            "cidr": "192.168.1.0/24",
        })

        args = {"entity_type": "network", "entity_id": "net-1"}
        result = await get_prompt("documentation_generator", args)

        text = result.messages[0].content.text
        assert "Main Network" in text or "net-1" in text
        assert "Operational procedures" in text
        assert "Maintenance schedule" in text
        mock_client.get_network.assert_called_once_with("net-1", include_nodes=True)

    async def test_documentation_generator_unsupported_type(self, mock_client):
        """Test documentation_generator prompt with unsupported entity type."""
        args = {"entity_type": "unsupported", "entity_id": "some-id"}
        result = await get_prompt("documentation_generator", args)

        text = result.messages[0].content.text
        assert "not supported" in text

    async def test_documentation_generator_requires_both_args(self, mock_client):
        """Test documentation_generator prompt requires entity_type and entity_id."""
        # Missing entity_id - mock should return empty result
        mock_client.get_node = AsyncMock(return_value={})

        args = {"entity_type": "node", "entity_id": ""}
        result = await get_prompt("documentation_generator", args)

        # Should still generate a prompt but with empty/default values
        assert result.description == "Generate documentation"
        assert len(result.messages) == 1
        mock_client.get_node.assert_called_once_with("")


class TestPromptErrorHandling:
    """Tests for prompt error handling."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Hydra API client."""
        with patch("hydra_mcp.server.client") as mock:
            yield mock

    async def test_unknown_prompt_name_raises(self, mock_client):
        """Test that unknown prompt name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown prompt"):
            await get_prompt("nonexistent_prompt", {})

    async def test_empty_prompt_name_raises(self, mock_client):
        """Test that empty prompt name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown prompt"):
            await get_prompt("", {})


class TestPromptMessagesStructure:
    """Tests for prompt message structure and format."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Hydra API client."""
        with patch("hydra_mcp.server.client") as mock:
            # Setup default mocks for all prompts
            mock.get_capacity = AsyncMock(return_value={})
            mock.list_networks = AsyncMock(return_value=([], {}))
            mock.get_topology = AsyncMock(return_value={})
            mock.list_nodes = AsyncMock(return_value=([], {}))
            mock.list_services = AsyncMock(return_value=([], {}))
            mock.get_node = AsyncMock(return_value={})
            mock.get_service = AsyncMock(return_value={})
            mock.get_network = AsyncMock(return_value={})
            yield mock

    @pytest.mark.parametrize("prompt_name,args", [
        ("capacity_planning", {"workload": "test"}),
        ("troubleshoot_network", {"symptoms": "test"}),
        ("infrastructure_audit", {}),
        ("service_dependency_map", {}),
        ("migration_planning", {"source": "src", "target": "dst"}),
        ("documentation_generator", {"entity_type": "node", "entity_id": "test"}),
    ])
    async def test_all_prompts_return_messages(self, mock_client, prompt_name, args):
        """Test that all prompts return proper GetPromptResult with messages."""
        result = await get_prompt(prompt_name, args)

        assert hasattr(result, "description")
        assert hasattr(result, "messages")
        assert len(result.messages) > 0
        assert result.messages[0].role == "user"
        assert hasattr(result.messages[0].content, "text")
        assert isinstance(result.messages[0].content.text, str)
        assert len(result.messages[0].content.text) > 0
