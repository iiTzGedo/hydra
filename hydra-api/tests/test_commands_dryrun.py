"""Tests for command dry-run (preview) functionality."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient  # noqa: TC002

# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def sample_definition():
    """Sample command definition (registry entry)."""
    return {
        "registryId": "reg::service::restart",
        "category": "service",
        "action": "restart",
        "displayName": "Restart Service",
        "description": "Restart a service",
        "targetSchema": {"required": ["nodeId", "serviceId"]},
        "parametersSchema": None,
        "execution": {
            "runtimes": {"systemd": "systemctl restart {service}"},
            "handler": None,
            "timeout": 60,
            "deliveryMode": "poll_only",
            "retryable": True,
            "maxRetries": 1,
        },
        "rbac": {
            "minimumRole": "operator",
            "requiresConfirmation": False,
            "dangerLevel": "medium",
        },
        "audit": {"logLevel": "standard", "captureOutput": True, "sensitiveParameters": []},
        "metadata": {
            "version": "0.5.0",
            "addedAt": datetime.now(UTC),
            "builtIn": True,
            "deprecated": False,
        },
    }


@pytest.fixture
def high_danger_definition():
    """Command definition that requires confirmation (high danger)."""
    return {
        "registryId": "reg::node::reboot",
        "category": "node",
        "action": "reboot",
        "displayName": "Reboot Node",
        "description": "Reboot the target node",
        "execution": {
            "handler": "node_reboot",
            "timeout": 120,
            "deliveryMode": "direct_or_poll",
        },
        "rbac": {
            "minimumRole": "operator",
            "requiresConfirmation": True,
            "dangerLevel": "high",
        },
        "audit": {"logLevel": "verbose"},
        "metadata": {
            "version": "0.5.0",
            "addedAt": datetime.now(UTC),
            "builtIn": True,
            "deprecated": False,
        },
    }


def trusted_write_headers(
    *,
    user_id: str = "user_admin123",
    role: str = "admin",
    client_id: str = "hydra-web",
) -> dict[str, str]:
    """Build trusted internal-request headers for write-path tests."""
    return {
        "X-Hydra-Internal-Request": "true",
        "X-Hydra-Internal-Secret": "internal-secret-for-tests-0123456789",
        "X-Hydra-User-Id": user_id,
        "X-Hydra-Role": role,
        "X-Hydra-Client-Id": client_id,
    }


def _setup_dryrun_mocks(mock_mongodb, sample_user, sample_definition, *, role="admin"):
    """Common mock setup for dry-run tests."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": role}
    )
    mock_mongodb.command_definitions.find_one = AsyncMock(return_value=sample_definition)
    mock_mongodb.commands.insert_one = AsyncMock()
    mock_mongodb.commands.count_documents = AsyncMock(return_value=0)


def _mock_service_lookup(
    mock_mongodb,
    *,
    node_id: str = "server-01",
    runtime: str = "systemd",
    image: str | None = None,
):
    """Mock service lookup used by service-targeted commands."""
    mock_mongodb.services.find_one = AsyncMock(
        return_value={
            "serviceId": "svc-nginx-a1b2",
            "nodeId": node_id,
            "name": "nginx",
            "runtime": runtime,
            "image": image,
        }
    )


# ── Dry-Run Tests ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dry_run_returns_preview(
    client: AsyncClient,
    mock_mongodb,
    mock_redis,
    admin_token,
    sample_user,
    sample_definition,
):
    """Test that dry-run returns a DryRunResponse preview."""
    _setup_dryrun_mocks(mock_mongodb, sample_user, sample_definition)
    _mock_service_lookup(mock_mongodb)
    mock_mongodb.nodes.find_one = AsyncMock(
        return_value={"nodeId": "server-01", "status": "active", "agentTier": "normal"}
    )
    # Ensure mock Redis client has ttl support for cooldown peek
    mock_redis.client.ttl = AsyncMock(return_value=-2)

    with patch("hydra.db.redis.get_redis", return_value=mock_redis):
        response = await client.post(
            "/api/v1/commands",
            json={
                "registryId": "reg::service::restart",
                "target": {"nodeId": "server-01", "serviceId": "svc-nginx-a1b2"},
                "dryRun": True,
            },
            headers=trusted_write_headers(),
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["registryId"] == "reg::service::restart"
    assert data["targetNodeId"] == "server-01"
    assert data["targetNodeTier"] == "normal"
    assert data["permissionCheckPassed"] is True
    assert data["rateLimitOk"] is True
    assert data["cooldownOk"] is True
    assert data["dangerLevel"] == "medium"
    assert data["wouldRequireConfirmation"] is False
    assert data["estimatedDeliveryMode"] == "poll"


@pytest.mark.asyncio
async def test_dry_run_no_command_created(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_definition,
):
    """Test that dry-run does NOT insert a command into MongoDB."""
    _setup_dryrun_mocks(mock_mongodb, sample_user, sample_definition)
    _mock_service_lookup(mock_mongodb)
    mock_mongodb.nodes.find_one = AsyncMock(
        return_value={"nodeId": "server-01", "status": "active", "agentTier": "normal"}
    )

    response = await client.post(
        "/api/v1/commands",
        json={
            "registryId": "reg::service::restart",
            "target": {"nodeId": "server-01", "serviceId": "svc-nginx-a1b2"},
            "dryRun": True,
        },
        headers=trusted_write_headers(),
    )

    assert response.status_code == 200
    # Verify no command was inserted
    mock_mongodb.commands.insert_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_dry_run_respects_rbac(
    client: AsyncClient,
    mock_mongodb,
    sample_user,
    test_settings,
):
    """Test dry-run reports permission_check_passed=False for insufficient role.

    Uses an operator user (who has commands:execute permission to reach the endpoint)
    against an admin-only command definition to verify the dry-run RBAC check.
    """
    # Admin-only command definition
    admin_only_def = {
        "registryId": "reg::node::reboot",
        "category": "node",
        "action": "reboot",
        "execution": {"timeout": 120, "deliveryMode": "direct_or_poll"},
        "rbac": {
            "minimumRole": "admin",
            "requiresConfirmation": True,
            "dangerLevel": "high",
        },
        "metadata": {"builtIn": True},
    }
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_operator123", "role": "operator"}
    )
    mock_mongodb.command_definitions.find_one = AsyncMock(return_value=admin_only_def)
    mock_mongodb.nodes.find_one = AsyncMock(
        return_value={"nodeId": "server-01", "status": "active", "agentTier": "normal"}
    )

    response = await client.post(
        "/api/v1/commands",
        json={
            "registryId": "reg::node::reboot",
            "target": {"nodeId": "server-01"},
            "dryRun": True,
        },
        headers=trusted_write_headers(user_id="user_operator123", role="operator"),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["permissionCheckPassed"] is False
    # Verify no command was created
    mock_mongodb.commands.insert_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_dry_run_shows_confirmation_required(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    high_danger_definition,
):
    """Test dry-run correctly reports wouldRequireConfirmation for dangerous commands."""
    _setup_dryrun_mocks(mock_mongodb, sample_user, high_danger_definition)
    mock_mongodb.nodes.find_one = AsyncMock(
        return_value={"nodeId": "server-01", "status": "active", "agentTier": "normal"}
    )

    response = await client.post(
        "/api/v1/commands",
        json={
            "registryId": "reg::node::reboot",
            "target": {"nodeId": "server-01"},
            "dryRun": True,
        },
        headers=trusted_write_headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["wouldRequireConfirmation"] is True
    assert data["dangerLevel"] == "high"


@pytest.mark.asyncio
async def test_dry_run_does_not_increment_rate_limit(
    client: AsyncClient,
    mock_mongodb,
    mock_redis,
    admin_token,
    sample_user,
    sample_definition,
):
    """Test that dry-run does NOT increment rate-limit counters."""
    _setup_dryrun_mocks(mock_mongodb, sample_user, sample_definition)
    _mock_service_lookup(mock_mongodb)
    mock_mongodb.nodes.find_one = AsyncMock(
        return_value={"nodeId": "server-01", "status": "active", "agentTier": "normal"}
    )

    # Track whether rate_limit_check was called (which increments counters)
    mock_redis.rate_limit_check.reset_mock()

    # Patch get_redis where it is imported inside _peek_rate_limits
    with patch("hydra.db.redis.get_redis", return_value=mock_redis):
        response = await client.post(
            "/api/v1/commands",
            json={
                "registryId": "reg::service::restart",
                "target": {"nodeId": "server-01", "serviceId": "svc-nginx-a1b2"},
                "dryRun": True,
            },
            headers=trusted_write_headers(),
        )

    assert response.status_code == 200
    # rate_limit_check increments counters -- it must NOT be called during dry-run
    mock_redis.rate_limit_check.assert_not_awaited()


@pytest.mark.asyncio
async def test_dry_run_shows_delivery_mode_poll_for_normal_tier(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_definition,
):
    """Test dry-run shows 'poll' delivery mode for normal-tier node."""
    _setup_dryrun_mocks(mock_mongodb, sample_user, sample_definition)
    _mock_service_lookup(mock_mongodb)
    mock_mongodb.nodes.find_one = AsyncMock(
        return_value={"nodeId": "server-01", "status": "active", "agentTier": "normal"}
    )

    response = await client.post(
        "/api/v1/commands",
        json={
            "registryId": "reg::service::restart",
            "target": {"nodeId": "server-01", "serviceId": "svc-nginx-a1b2"},
            "dryRun": True,
        },
        headers=trusted_write_headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["estimatedDeliveryMode"] == "poll"
    assert data["targetNodeTier"] == "normal"


@pytest.mark.asyncio
async def test_dry_run_shows_delivery_mode_direct_for_max_tier(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test dry-run shows 'direct' delivery mode for max-tier node with direct_or_poll command."""
    direct_capable_def = {
        "registryId": "reg::service::restart",
        "category": "service",
        "action": "restart",
        "displayName": "Restart Service",
        "execution": {
            "timeout": 60,
            "deliveryMode": "direct_or_poll",
        },
        "rbac": {
            "minimumRole": "operator",
            "requiresConfirmation": False,
            "dangerLevel": "medium",
        },
        "metadata": {"builtIn": True},
    }
    _setup_dryrun_mocks(mock_mongodb, sample_user, direct_capable_def)
    _mock_service_lookup(mock_mongodb)
    mock_mongodb.nodes.find_one = AsyncMock(
        return_value={"nodeId": "server-01", "status": "active", "agentTier": "max"}
    )

    response = await client.post(
        "/api/v1/commands",
        json={
            "registryId": "reg::service::restart",
            "target": {"nodeId": "server-01", "serviceId": "svc-nginx-a1b2"},
            "dryRun": True,
        },
        headers=trusted_write_headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["estimatedDeliveryMode"] == "direct"
    assert data["targetNodeTier"] == "max"


@pytest.mark.asyncio
async def test_dry_run_shows_rejected_for_lite_tier(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    sample_definition,
):
    """Test dry-run reports 'rejected' delivery mode for lite-tier nodes."""
    _setup_dryrun_mocks(mock_mongodb, sample_user, sample_definition)
    _mock_service_lookup(mock_mongodb, node_id="lite-node")
    mock_mongodb.nodes.find_one = AsyncMock(
        return_value={"nodeId": "lite-node", "status": "active", "agentTier": "lite"}
    )

    response = await client.post(
        "/api/v1/commands",
        json={
            "registryId": "reg::service::restart",
            "target": {"nodeId": "lite-node", "serviceId": "svc-nginx-a1b2"},
            "dryRun": True,
        },
        headers=trusted_write_headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["estimatedDeliveryMode"] == "rejected"
    assert data["targetNodeTier"] == "lite"


@pytest.mark.asyncio
async def test_dry_run_unknown_registry_id(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test dry-run returns 404 for unknown registryId."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.command_definitions.find_one = AsyncMock(return_value=None)

    response = await client.post(
        "/api/v1/commands",
        json={
            "registryId": "reg::service::nonexistent",
            "target": {"nodeId": "server-01"},
            "dryRun": True,
        },
        headers=trusted_write_headers(),
    )

    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "COMMAND_DEFINITION_NOT_FOUND"
    # No command record created for dry-run even on 404
    mock_mongodb.commands.insert_one.assert_not_awaited()


# ── Fail-Closed Safety Tests ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dry_run_peek_fails_closed_on_redis_error(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
    high_danger_definition,
):
    """Test that dry-run reports rateLimitOk=False and cooldownOk=False when Redis is down.

    Safety checks that cannot verify their condition must fail-closed (report NOT OK),
    not fail-open (report OK).  Uses a high-danger definition so the cooldown path is
    exercised (cooldown only applies to high/critical danger levels).
    """
    _setup_dryrun_mocks(mock_mongodb, sample_user, high_danger_definition)
    mock_mongodb.nodes.find_one = AsyncMock(
        return_value={"nodeId": "server-01", "status": "active", "agentTier": "normal"}
    )

    # Mock get_redis to raise ConnectionError (simulating Redis outage)
    broken_redis = AsyncMock()
    broken_redis.client.get = AsyncMock(side_effect=ConnectionError("Redis unavailable"))
    broken_redis.client.ttl = AsyncMock(side_effect=ConnectionError("Redis unavailable"))
    broken_redis.RATE_LIMIT_PREFIX = "rl:"

    with patch("hydra.db.redis.get_redis", return_value=broken_redis):
        response = await client.post(
            "/api/v1/commands",
            json={
                "registryId": "reg::node::reboot",
                "target": {"nodeId": "server-01"},
                "dryRun": True,
            },
            headers=trusted_write_headers(),
        )

    assert response.status_code == 200
    data = response.json()["data"]
    # Safety checks must fail-closed when Redis is unreachable
    assert data["rateLimitOk"] is False
    assert data["cooldownOk"] is False
    # Other fields should still be correct
    assert data["registryId"] == "reg::node::reboot"
    assert data["permissionCheckPassed"] is True
    assert data["dangerLevel"] == "high"
    assert data["estimatedDeliveryMode"] == "poll"


@pytest.mark.asyncio
async def test_dry_run_matches_service_normalization_validation(
    client: AsyncClient,
    mock_mongodb,
    sample_user,
):
    """Dry-run should fail on the same service normalization path as execution."""
    update_definition = {
        "registryId": "reg::service::update",
        "category": "service",
        "action": "update",
        "displayName": "Update Service",
        "execution": {
            "timeout": 60,
            "deliveryMode": "poll_only",
        },
        "rbac": {
            "minimumRole": "operator",
            "requiresConfirmation": False,
            "dangerLevel": "medium",
        },
        "metadata": {"builtIn": True},
    }
    _setup_dryrun_mocks(mock_mongodb, sample_user, update_definition)
    mock_mongodb.nodes.find_one = AsyncMock(
        return_value={"nodeId": "server-01", "status": "active", "agentTier": "normal"}
    )
    mock_mongodb.services.find_one = AsyncMock(
        return_value={
            "serviceId": "svc-nginx-a1b2",
            "nodeId": "server-01",
            "name": "nginx",
            "runtime": "systemd",
        }
    )

    dry_run_response = await client.post(
        "/api/v1/commands",
        json={
            "registryId": "reg::service::update",
            "target": {"nodeId": "server-01", "serviceId": "svc-nginx-a1b2"},
            "dryRun": True,
        },
        headers=trusted_write_headers(),
    )
    execute_response = await client.post(
        "/api/v1/commands",
        json={
            "registryId": "reg::service::update",
            "target": {"nodeId": "server-01", "serviceId": "svc-nginx-a1b2"},
        },
        headers=trusted_write_headers(),
    )

    assert dry_run_response.status_code == 400
    assert execute_response.status_code == 400
    assert (
        dry_run_response.json()["error"]["message"]
        == execute_response.json()["error"]["message"]
    )
    mock_mongodb.commands.insert_one.assert_not_awaited()
