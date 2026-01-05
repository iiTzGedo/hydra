"""Tests for health check endpoints."""

import pytest
from httpx import AsyncClient

from tests.utils import create_mock_cursor


@pytest.mark.asyncio
async def test_health_check_healthy(client: AsyncClient, mock_mongodb, mock_redis):
    """Test health check when all services are healthy."""
    mock_mongodb.health_check.return_value = True
    mock_redis.health_check.return_value = True

    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["checks"]["database"] == "ok"
    assert data["checks"]["redis"] == "ok"
    assert "version" in data
    assert "uptimeSeconds" in data


@pytest.mark.asyncio
async def test_health_check_degraded(client: AsyncClient, mock_mongodb, mock_redis):
    """Test health check when a service is down."""
    mock_mongodb.health_check.return_value = True
    mock_redis.health_check.return_value = False

    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["checks"]["database"] == "ok"
    assert data["checks"]["redis"] == "error"


@pytest.mark.asyncio
async def test_service_info(client: AsyncClient, mock_mongodb):
    """Test service info endpoint."""
    # Mock aggregation for stats
    node_stats = [
        {
            "total": [{"count": 10}],
            "active": [{"count": 8}],
            "byClass": [
                {"_id": "compute", "count": 7},
                {"_id": "networking", "count": 2},
                {"_id": "iot", "count": 1},
            ],
        }
    ]
    service_stats = [
        {
            "total": [{"count": 50}],
            "running": [{"count": 45}],
        }
    ]
    mock_mongodb.nodes.aggregate.return_value = create_mock_cursor(node_stats)
    mock_mongodb.services.aggregate.return_value = create_mock_cursor(service_stats)
    mock_mongodb.networks.count_documents.return_value = 5
    mock_mongodb.groups.count_documents.return_value = 3
    mock_mongodb.profiles.count_documents.return_value = 100
    mock_mongodb.users.count_documents.return_value = 2

    response = await client.get("/api/v1/info")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "hydra-api"
    assert "version" in data
    assert data["apiVersion"] == "v1"
    assert "stats" in data
    assert "features" in data
