"""Tests for Proxmox PVE API-based remote agent installation."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hydra.api.v1.models.installations import InstallationStatus, ProxmoxInstallRequest
from hydra.api.v1.services.installations.proxmox import (
    PluginNotFoundError,
    ProxmoxInstallationError,
    ProxmoxInstallationService,
)
from tests.conftest import create_mock_collection

# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def mock_mongodb() -> MagicMock:
    """Create a mock MongoDB instance with required collections."""
    mock = MagicMock()

    collections: dict[str, MagicMock] = {}

    def get_collection(name: str) -> MagicMock:
        if name not in collections:
            collections[name] = create_mock_collection()
        return collections[name]

    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(side_effect=get_collection)
    mock.db = mock_db
    return mock


@pytest.fixture
def service(mock_mongodb: MagicMock) -> ProxmoxInstallationService:
    """Create a ProxmoxInstallationService with mocked MongoDB."""
    return ProxmoxInstallationService(mock_mongodb)


@pytest.fixture
def sample_proxmox_plugin() -> dict:
    """Sample Proxmox plugin document as stored in MongoDB."""
    now = datetime.now(UTC)
    return {
        "pluginId": "plg::proxmox",
        "manifest": {
            "pluginId": "plg::proxmox",
            "name": "Proxmox VE",
            "version": "1.0.0",
            "classification": "core",
            "category": "infrastructure",
        },
        "status": "active",
        "config": {
            "host": "10.0.0.1",
            "port": 8006,
            "verifySsl": False,
        },
        "credentials": {
            "apiToken": "root@pam!hydra=aaaabbbb-cccc-dddd-eeee-ffffffffffff",
        },
        "nodeBindings": [],
        "health": {"status": "healthy"},
        "createdAt": now,
        "updatedAt": now,
    }


@pytest.fixture
def sample_request() -> ProxmoxInstallRequest:
    """Sample Proxmox installation request."""
    return ProxmoxInstallRequest(
        plugin_id="plg::proxmox",
        vmid=100,
        proxmox_node="pve-node-01",
        vm_type="qemu",
        agent_tier="normal",
        tags=["test"],
    )


@pytest.fixture
def sample_lxc_request() -> ProxmoxInstallRequest:
    """Sample Proxmox LXC installation request."""
    return ProxmoxInstallRequest(
        plugin_id="plg::proxmox",
        vmid=200,
        proxmox_node="pve-node-01",
        vm_type="lxc",
        agent_tier="lite",
        tags=[],
    )


# ── Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@patch(
    "hydra.api.v1.services.installations.proxmox.ProxmoxInstallationService._execute_proxmox_installation"
)
async def test_start_proxmox_installation_creates_record(
    mock_execute: AsyncMock,
    service: ProxmoxInstallationService,
    sample_proxmox_plugin: dict,
    sample_request: ProxmoxInstallRequest,
) -> None:
    """Starting a Proxmox installation creates a record and returns it."""
    mock_execute.return_value = None

    service.plugins.find_one = AsyncMock(return_value=sample_proxmox_plugin)
    service.installations.insert_one = AsyncMock()

    # After insert, find_one returns the created document
    now = datetime.now(UTC)
    created_doc = {
        "installationId": "inst_placeholder",
        "discoveryId": None,
        "targetIp": "10.0.0.1",
        "targetHostname": None,
        "status": InstallationStatus.PENDING,
        "progress": {
            "phase": InstallationStatus.PENDING,
            "percentComplete": 0,
            "message": "Proxmox installation queued",
            "startedAt": None,
            "updatedAt": now,
        },
        "nodeId": None,
        "error": None,
        "agentTier": "normal",
        "tags": ["test"],
        "installMethod": "proxmox",
        "proxmox": {
            "pluginId": "plg::proxmox",
            "proxmoxNode": "pve-node-01",
            "vmid": 100,
            "vmType": "qemu",
        },
        "createdBy": "user_admin123",
        "createdAt": now,
        "updatedAt": now,
        "completedAt": None,
    }
    service.installations.find_one = AsyncMock(return_value=created_doc)

    result = await service.start_proxmox_installation(
        sample_request,
        user_id="user_admin123",
        user_role="admin",
        user_permissions=["*:*"],
    )

    # Verify record was inserted
    service.installations.insert_one.assert_awaited_once()
    inserted = service.installations.insert_one.call_args[0][0]
    assert inserted["installMethod"] == "proxmox"
    assert inserted["proxmox"]["vmid"] == 100
    assert inserted["proxmox"]["vmType"] == "qemu"
    assert inserted["status"] == InstallationStatus.PENDING

    # Verify the returned document
    assert result["installationId"] == "inst_placeholder"
    assert result["status"] == InstallationStatus.PENDING


@pytest.mark.asyncio
async def test_missing_plugin_config_raises_error(
    service: ProxmoxInstallationService,
    sample_request: ProxmoxInstallRequest,
) -> None:
    """Starting installation with a non-existent plugin raises PluginNotFoundError."""
    service.plugins.find_one = AsyncMock(return_value=None)

    with pytest.raises(PluginNotFoundError):
        await service.start_proxmox_installation(
            sample_request,
            user_id="user_admin123",
            user_role="admin",
            user_permissions=["*:*"],
        )


@pytest.mark.asyncio
async def test_vm_not_found_sets_failed(
    service: ProxmoxInstallationService,
    sample_proxmox_plugin: dict,
    sample_request: ProxmoxInstallRequest,
) -> None:
    """When PVE returns 404 for the VM, the installation is marked FAILED."""
    service.plugins.find_one = AsyncMock(return_value=sample_proxmox_plugin)
    service.installations.insert_one = AsyncMock()

    # The background task will find the installation document
    now = datetime.now(UTC)
    pending_doc = {
        "installationId": "inst_test123",
        "discoveryId": None,
        "status": InstallationStatus.PENDING,
        "progress": {
            "phase": InstallationStatus.PENDING,
            "percentComplete": 0,
            "message": "Proxmox installation queued",
            "startedAt": None,
            "updatedAt": now,
        },
    }
    service.installations.find_one = AsyncMock(return_value=pending_doc)
    service.installations.update_one = AsyncMock()

    # Mock httpx to return 404 for the VM status check
    mock_response_404 = MagicMock()
    mock_response_404.status_code = 404
    mock_response_404.text = "VM not found"

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response_404)

    with patch("httpx.AsyncClient") as mock_async_client:
        mock_async_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_async_client.return_value.__aexit__ = AsyncMock(return_value=False)

        # Run the background task directly
        await service._execute_proxmox_installation(
            installation_id="inst_test123",
            pve_config={
                "host": "10.0.0.1",
                "port": 8006,
                "verify_ssl": False,
                "api_token": "root@pam!hydra=token",
                "username": None,
                "password": None,
            },
            proxmox_node="pve-node-01",
            vmid=100,
            vm_type="qemu",
        )

    # Verify the installation was marked as failed
    update_calls = service.installations.update_one.call_args_list
    # The last update_one call should set FAILED status
    final_update = update_calls[-1]
    set_fields = final_update[0][1]["$set"]
    assert set_fields["status"] == InstallationStatus.FAILED
    assert "not found" in set_fields["error"].lower()


@pytest.mark.asyncio
async def test_installation_phases_progress_correctly(
    service: ProxmoxInstallationService,
    sample_proxmox_plugin: dict,
) -> None:
    """Background execution progresses through all phases and ends COMPLETED."""
    now = datetime.now(UTC)
    running_doc = {
        "installationId": "inst_progress",
        "discoveryId": None,
        "status": InstallationStatus.PENDING,
        "progress": {
            "phase": InstallationStatus.PENDING,
            "percentComplete": 0,
            "message": "",
            "startedAt": None,
            "updatedAt": now,
        },
    }
    service.installations.find_one = AsyncMock(return_value=running_doc)
    service.installations.update_one = AsyncMock()

    # Mock all httpx responses as successful
    mock_status_response = MagicMock()
    mock_status_response.status_code = 200
    mock_status_response.json.return_value = {"data": {"status": "running"}}

    mock_exec_response = MagicMock()
    mock_exec_response.status_code = 200
    mock_exec_response.json.return_value = {"data": {"pid": 1234}}

    mock_agent_ping = MagicMock()
    mock_agent_ping.status_code = 200

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_status_response)
    mock_client.post = AsyncMock(side_effect=[mock_agent_ping, mock_exec_response, mock_exec_response, mock_exec_response, mock_exec_response])

    with patch("httpx.AsyncClient") as mock_async_client:
        mock_async_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_async_client.return_value.__aexit__ = AsyncMock(return_value=False)

        await service._execute_proxmox_installation(
            installation_id="inst_progress",
            pve_config={
                "host": "10.0.0.1",
                "port": 8006,
                "verify_ssl": False,
                "api_token": "root@pam!hydra=token",
                "username": None,
                "password": None,
            },
            proxmox_node="pve-node-01",
            vmid=100,
            vm_type="qemu",
        )

    # Collect all update_one calls and verify phase progression
    update_calls = service.installations.update_one.call_args_list
    phases_seen: list[str] = []
    for call in update_calls:
        set_fields = call[0][1]["$set"]
        if "progress.phase" in set_fields:
            phases_seen.append(set_fields["progress.phase"])
        elif "status" in set_fields:
            phases_seen.append(set_fields["status"])

    # Should have gone through all phases ending in COMPLETED
    assert InstallationStatus.CONNECTING in phases_seen
    assert InstallationStatus.TRANSFERRING in phases_seen
    assert InstallationStatus.CONFIGURING in phases_seen
    assert InstallationStatus.REGISTERING in phases_seen
    assert InstallationStatus.RUNNING in phases_seen
    assert InstallationStatus.COMPLETED in phases_seen


@pytest.mark.asyncio
async def test_lxc_vs_qemu_routing(
    service: ProxmoxInstallationService,
) -> None:
    """LXC and QEMU installations use different PVE API endpoints."""
    # Verify URL builders produce correct paths
    qemu_status = service._guest_status_url("node1", 100, "qemu")
    lxc_status = service._guest_status_url("node1", 200, "lxc")

    assert "/qemu/100/status/current" in qemu_status
    assert "/lxc/200/status/current" in lxc_status
    assert "node1" in qemu_status
    assert "node1" in lxc_status

    qemu_exec = service._guest_exec_url("node1", 100, "qemu")
    lxc_exec = service._guest_exec_url("node1", 200, "lxc")

    assert "/qemu/100/agent/exec" in qemu_exec
    assert "/lxc/200/exec" in lxc_exec
    assert "agent" not in lxc_exec  # LXC does NOT use /agent/


@pytest.mark.asyncio
async def test_failure_handling_marks_installation_failed(
    service: ProxmoxInstallationService,
) -> None:
    """When httpx raises a connection error, the installation is marked FAILED."""
    now = datetime.now(UTC)
    pending_doc = {
        "installationId": "inst_fail",
        "discoveryId": None,
        "status": InstallationStatus.PENDING,
        "progress": {
            "phase": InstallationStatus.PENDING,
            "percentComplete": 0,
            "message": "",
            "startedAt": None,
            "updatedAt": now,
        },
    }
    service.installations.find_one = AsyncMock(return_value=pending_doc)
    service.installations.update_one = AsyncMock()

    # Make httpx raise a connection error
    with patch("httpx.AsyncClient") as mock_async_client:
        mock_async_client.return_value.__aenter__ = AsyncMock(
            side_effect=ConnectionError("PVE host unreachable")
        )
        mock_async_client.return_value.__aexit__ = AsyncMock(return_value=False)

        await service._execute_proxmox_installation(
            installation_id="inst_fail",
            pve_config={
                "host": "10.0.0.1",
                "port": 8006,
                "verify_ssl": False,
                "api_token": "root@pam!hydra=token",
                "username": None,
                "password": None,
            },
            proxmox_node="pve-node-01",
            vmid=100,
            vm_type="qemu",
        )

    # Verify the installation was marked as failed
    update_calls = service.installations.update_one.call_args_list
    final_update = update_calls[-1]
    set_fields = final_update[0][1]["$set"]
    assert set_fields["status"] == InstallationStatus.FAILED
    assert "unreachable" in set_fields["error"].lower()


@pytest.mark.asyncio
@patch(
    "hydra.api.v1.services.installations.proxmox.ProxmoxInstallationService._execute_proxmox_installation"
)
async def test_plugin_missing_credentials_raises_error(
    mock_execute: AsyncMock,
    service: ProxmoxInstallationService,
    sample_request: ProxmoxInstallRequest,
) -> None:
    """A plugin document with no valid auth credentials raises an error."""
    mock_execute.return_value = None

    bad_plugin = {
        "pluginId": "plg::proxmox",
        "config": {"host": "10.0.0.1"},
        "credentials": {},  # No apiToken, no username/password
    }
    service.plugins.find_one = AsyncMock(return_value=bad_plugin)

    with pytest.raises(ProxmoxInstallationError, match="apiToken"):
        await service.start_proxmox_installation(
            sample_request,
            user_id="user_admin123",
            user_role="admin",
            user_permissions=["*:*"],
        )


@pytest.mark.asyncio
@patch(
    "hydra.api.v1.services.installations.proxmox.ProxmoxInstallationService._execute_proxmox_installation"
)
async def test_plugin_missing_host_raises_error(
    mock_execute: AsyncMock,
    service: ProxmoxInstallationService,
    sample_request: ProxmoxInstallRequest,
) -> None:
    """A plugin document with no host configured raises an error."""
    mock_execute.return_value = None

    bad_plugin = {
        "pluginId": "plg::proxmox",
        "config": {},  # No host
        "credentials": {"apiToken": "some-token"},
    }
    service.plugins.find_one = AsyncMock(return_value=bad_plugin)

    with pytest.raises(ProxmoxInstallationError, match="host"):
        await service.start_proxmox_installation(
            sample_request,
            user_id="user_admin123",
            user_role="admin",
            user_permissions=["*:*"],
        )
