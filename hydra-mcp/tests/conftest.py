"""Pytest configuration and fixtures for Hydra MCP tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = MagicMock()
    settings.api_url = "http://localhost:8080/api/v1"
    settings.api_key = None
    settings.api_timeout = 30
    settings.server_name = "hydra-mcp"
    settings.server_version = "0.1.0"
    settings.transport = "stdio"
    settings.http_host = "0.0.0.0"
    settings.http_port = 8081
    settings.cors_origins = ["*"]
    settings.toon_indent = 2
    settings.toon_delimiter = ","
    settings.toon_length_marker = ""
    settings.log_level = "INFO"
    return settings


@pytest.fixture
def mock_client():
    """Create mock Hydra API client."""
    client = AsyncMock()

    # Mock list_nodes response — return type is tuple[list[dict], int]
    client.list_nodes.return_value = (
        [
            {"nodeId": "node-1", "name": "Server 1", "class": "compute", "status": "active", "agentTier": "normal"},
            {"nodeId": "node-2", "name": "Server 2", "class": "compute", "status": "active", "agentTier": "max"},
        ],
        2,
    )

    # Mock get_node response
    client.get_node.return_value = {
        "nodeId": "node-1",
        "name": "Server 1",
        "class": "compute",
        "type": "physical",
        "status": "active",
        "agentTier": "normal",
        "services": [],
        "children": [],
    }

    # Mock list_services response — return type is tuple[list[dict], int]
    client.list_services.return_value = (
        [
            {"serviceId": "svc-nginx-a1b2", "name": "nginx", "status": "running"},
        ],
        1,
    )

    # Mock list_networks response — return type is tuple[list[dict], int]
    client.list_networks.return_value = (
        [
            {"networkId": "net-1", "name": "Main Network", "cidr": "192.168.1.0/24"},
        ],
        1,
    )

    # Mock list_groups response — return type is tuple[list[dict], int]
    client.list_groups.return_value = (
        [
            {"groupId": "grp-1", "name": "Production", "type": "node"},
        ],
        1,
    )

    # Mock list_notifications response — return type is tuple[list[dict], int]
    client.list_notifications.return_value = ([], 0)

    # Mock list_audit_entries response — return type is list[dict]
    client.list_audit_entries.return_value = []

    # Mock get_topology response
    client.get_topology.return_value = {
        "mode": "network",
        "nodes": [],
        "edges": [],
    }

    # Mock get_capacity response
    client.get_capacity.return_value = {
        "totalNodes": 2,
        "activeNodes": 2,
        "totalServices": 5,
        "runningServices": 4,
    }

    return client
