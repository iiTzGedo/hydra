"""Tests for the Proxmox VE plugin handler."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from hydra.api.v1.services.plugins.proxmox import ProxmoxHandler

# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def pve_config() -> dict[str, Any]:
    """Standard Proxmox config for tests."""
    return {
        "host": "pve.local",
        "port": 8006,
        "verifySsl": False,
    }


@pytest.fixture
def pve_credentials() -> dict[str, str]:
    """Standard Proxmox credentials for tests."""
    return {
        "tokenId": "root@pam!hydra",
        "tokenSecret": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    }


@pytest.fixture
def handler(pve_config: dict[str, Any], pve_credentials: dict[str, str]) -> ProxmoxHandler:
    """Create a ProxmoxHandler with test config and credentials."""
    return ProxmoxHandler(config=pve_config, credentials=pve_credentials)


def _mock_response(
    status_code: int = 200,
    json_data: dict[str, Any] | None = None,
    text: str = "",
) -> httpx.Response:
    """Build a minimal httpx.Response for mocking."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=resp,
        )
    return resp


# ── MANIFEST validation ──────────────────────────────────────────────────


class TestManifest:
    """Test suite for the Proxmox MANIFEST constant."""

    def test_manifest_plugin_id(self) -> None:
        """MANIFEST uses the correct pluginId."""
        assert ProxmoxHandler.MANIFEST["pluginId"] == "plg::proxmox"

    def test_manifest_name_and_version(self) -> None:
        """MANIFEST declares the expected name and version."""
        assert ProxmoxHandler.MANIFEST["name"] == "Proxmox VE"
        assert ProxmoxHandler.MANIFEST["version"] == "1.0.0"

    def test_manifest_classification(self) -> None:
        """MANIFEST is classified as a core infrastructure plugin."""
        assert ProxmoxHandler.MANIFEST["classification"] == "core"
        assert ProxmoxHandler.MANIFEST["category"] == "infrastructure"

    def test_manifest_touchpoints(self) -> None:
        """All expected touchpoints are enabled."""
        tp = ProxmoxHandler.MANIFEST["touchpoints"]
        assert tp["profileEnrichment"] is True
        assert tp["discoveryProvider"] is True
        assert tp["commandProvider"] is True
        assert tp["executionHandler"] is True
        assert tp["topologyProvider"] is True
        assert tp["workflowBlockProvider"] is False

    def test_manifest_supported_tiers(self) -> None:
        """Plugin supports normal and max agent tiers."""
        assert ProxmoxHandler.MANIFEST["supportedTiers"] == ["normal", "max"]

    def test_manifest_contributed_commands(self) -> None:
        """MANIFEST declares exactly 6 contributed commands."""
        cmds = ProxmoxHandler.MANIFEST["contributedCommands"]
        assert len(cmds) == 6
        assert "reg::proxmox::list-vms" in cmds
        assert "reg::proxmox::stop-vm" in cmds


# ── COMMAND_DEFINITIONS validation ───────────────────────────────────────


class TestCommandDefinitions:
    """Test suite for COMMAND_DEFINITIONS."""

    def test_command_count(self) -> None:
        """There are exactly 6 command definitions."""
        assert len(ProxmoxHandler.COMMAND_DEFINITIONS) == 6

    def test_all_registry_ids_match_manifest(self) -> None:
        """Every command registryId appears in the MANIFEST contributedCommands."""
        manifest_cmds = set(ProxmoxHandler.MANIFEST["contributedCommands"])
        for cmd in ProxmoxHandler.COMMAND_DEFINITIONS:
            assert cmd["registryId"] in manifest_cmds

    def test_stop_vm_requires_confirmation(self) -> None:
        """stop-vm is the only command that requires confirmation."""
        stop = next(c for c in ProxmoxHandler.COMMAND_DEFINITIONS if c["registryId"] == "reg::proxmox::stop-vm")
        assert stop["rbac"]["requiresConfirmation"] is True
        assert stop["rbac"]["dangerLevel"] == "high"

    def test_list_vms_is_safe(self) -> None:
        """list-vms is classified as safe."""
        cmd = next(c for c in ProxmoxHandler.COMMAND_DEFINITIONS if c["registryId"] == "reg::proxmox::list-vms")
        assert cmd["rbac"]["dangerLevel"] == "safe"


# ── connect() ────────────────────────────────────────────────────────────


class TestConnect:
    """Test suite for ProxmoxHandler.connect()."""

    @pytest.mark.asyncio
    async def test_connect_success(self, handler: ProxmoxHandler) -> None:
        """connect() returns True when PVE version endpoint responds OK."""
        mock_resp = _mock_response(200, {"data": {"version": "8.1.3", "release": "1"}})

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=mock_resp):
            result = await handler.connect()

        assert result is True

    @pytest.mark.asyncio
    async def test_connect_failure(self, handler: ProxmoxHandler) -> None:
        """connect() returns False when PVE is unreachable."""
        with patch.object(
            httpx.AsyncClient,
            "get",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            result = await handler.connect()

        assert result is False


# ── health_check() ───────────────────────────────────────────────────────


class TestHealthCheck:
    """Test suite for ProxmoxHandler.health_check()."""

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, handler: ProxmoxHandler) -> None:
        """health_check() returns healthy status on success."""
        mock_resp = _mock_response(200, {"data": {"version": "8.1.3"}})

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=mock_resp):
            result = await handler.health_check()

        assert result["status"] == "healthy"
        assert result["consecutiveFailures"] == 0
        assert result["lastError"] is None
        assert result["pveVersion"] == "8.1.3"
        assert isinstance(result["responseTimeMs"], float)

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, handler: ProxmoxHandler) -> None:
        """health_check() returns unhealthy status on connection failure."""
        with patch.object(
            httpx.AsyncClient,
            "get",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("refused"),
        ):
            result = await handler.health_check()

        assert result["status"] == "unhealthy"
        assert result["consecutiveFailures"] == 1
        assert result["lastError"] is not None


# ── enrich_profile() ─────────────────────────────────────────────────────


class TestEnrichProfile:
    """Test suite for ProxmoxHandler.enrich_profile()."""

    @pytest.mark.asyncio
    async def test_enrich_profile_success(self, handler: ProxmoxHandler) -> None:
        """enrich_profile() returns PVE host stats on success."""
        pve_status_data = {
            "data": {
                "uptime": 1234567,
                "kversion": "6.5.13-5-pve",
                "cpu": 0.15,
                "cpuinfo": {
                    "model": "Intel Xeon E-2288G",
                    "cores": 8,
                    "sockets": 1,
                },
                "memory": {
                    "total": 68719476736,
                    "used": 34359738368,
                    "free": 34359738368,
                },
            },
        }
        mock_resp = _mock_response(200, pve_status_data)

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=mock_resp):
            profile = {"network": {"hostname": "pve-01"}}
            result = await handler.enrich_profile("pve-01", profile)

        assert result["pveNode"] == "pve-01"
        assert result["uptime"] == 1234567
        assert result["cpuModel"] == "Intel Xeon E-2288G"
        assert result["cpuCores"] == 8
        assert result["memoryTotal"] == 68719476736
        assert result["memoryUsed"] == 34359738368

    @pytest.mark.asyncio
    async def test_enrich_profile_failure_returns_empty(self, handler: ProxmoxHandler) -> None:
        """enrich_profile() returns empty dict on error."""
        with patch.object(
            httpx.AsyncClient,
            "get",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("refused"),
        ):
            result = await handler.enrich_profile("pve-01", {})

        assert result == {}


# ── discover_nodes() ─────────────────────────────────────────────────────


class TestDiscoverNodes:
    """Test suite for ProxmoxHandler.discover_nodes()."""

    @pytest.mark.asyncio
    async def test_discover_vms_and_nodes(self, handler: ProxmoxHandler) -> None:
        """discover_nodes() returns VMs, LXCs, and hypervisor nodes."""
        vm_response = _mock_response(200, {
            "data": [
                {
                    "vmid": 100,
                    "name": "ubuntu-vm",
                    "type": "qemu",
                    "node": "pve-01",
                    "status": "running",
                    "maxcpu": 4,
                    "maxmem": 8589934592,
                    "maxdisk": 53687091200,
                    "uptime": 86400,
                },
                {
                    "vmid": 200,
                    "name": "alpine-ct",
                    "type": "lxc",
                    "node": "pve-01",
                    "status": "stopped",
                    "maxcpu": 2,
                    "maxmem": 2147483648,
                    "maxdisk": 10737418240,
                    "uptime": 0,
                },
            ],
        })

        node_response = _mock_response(200, {
            "data": [
                {
                    "node": "pve-01",
                    "status": "online",
                    "maxcpu": 16,
                    "maxmem": 68719476736,
                    "uptime": 1234567,
                    "type": "node",
                    "level": "",
                },
            ],
        })

        call_count = 0

        async def mock_get(self_client: Any, path: str) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if "type=vm" in path:
                return vm_response
            if "type=node" in path:
                return node_response
            return _mock_response(404)  # pragma: no cover

        with patch.object(httpx.AsyncClient, "get", new=mock_get):
            results = await handler.discover_nodes()

        # 2 VMs/CTs + 1 hypervisor node = 3
        assert len(results) == 3

        # Check VM
        vm = next(r for r in results if r["identifier"] == "100")
        assert vm["resourceType"] == "vm"
        assert vm["displayName"] == "ubuntu-vm"
        assert vm["metadata"]["type"] == "qemu"

        # Check LXC
        ct = next(r for r in results if r["identifier"] == "200")
        assert ct["resourceType"] == "container"
        assert ct["displayName"] == "alpine-ct"
        assert ct["metadata"]["type"] == "lxc"

        # Check hypervisor node
        hv = next(r for r in results if r["resourceType"] == "hypervisor")
        assert hv["identifier"] == "pve-01"
        assert hv["status"] == "online"


# ── execute_command() ────────────────────────────────────────────────────


class TestExecuteCommand:
    """Test suite for ProxmoxHandler.execute_command()."""

    @pytest.mark.asyncio
    async def test_start_vm(self, handler: ProxmoxHandler) -> None:
        """execute_command dispatches start-vm to the correct PVE endpoint."""
        mock_resp = _mock_response(200, {"data": "UPID:pve-01:001B9D5A:037C5EC4:start"})

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_resp):
            result = await handler.execute_command(
                "reg::proxmox::start-vm",
                {"nodeId": "pve-01"},
                {"vmid": 100, "node": "pve-01", "type": "qemu"},
            )

        assert result["success"] is True
        assert "start" in result["output"].lower()
        assert "taskId" in result["data"]

    @pytest.mark.asyncio
    async def test_stop_vm(self, handler: ProxmoxHandler) -> None:
        """execute_command dispatches stop-vm correctly."""
        mock_resp = _mock_response(200, {"data": "UPID:pve-01:001B9D5B:037C5EC5:stop"})

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_resp):
            result = await handler.execute_command(
                "reg::proxmox::stop-vm",
                {"nodeId": "pve-01"},
                {"vmid": 100, "node": "pve-01", "type": "qemu"},
            )

        assert result["success"] is True
        assert "stop" in result["output"].lower()

    @pytest.mark.asyncio
    async def test_unknown_command(self, handler: ProxmoxHandler) -> None:
        """execute_command returns failure for an unknown command."""
        result = await handler.execute_command("reg::proxmox::unknown", {}, {})
        assert result["success"] is False
        assert "Unknown" in result["output"]

    @pytest.mark.asyncio
    async def test_execute_command_http_error(self, handler: ProxmoxHandler) -> None:
        """execute_command handles HTTP errors gracefully."""
        mock_resp = _mock_response(500, text="Internal Server Error")

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_resp):
            result = await handler.execute_command(
                "reg::proxmox::start-vm",
                {"nodeId": "pve-01"},
                {"vmid": 999, "node": "pve-01", "type": "qemu"},
            )

        assert result["success"] is False
        assert "500" in result["output"]


# ── get_topology_edges() ─────────────────────────────────────────────────


class TestGetTopologyEdges:
    """Test suite for ProxmoxHandler.get_topology_edges()."""

    @pytest.mark.asyncio
    async def test_topology_edges(self, handler: ProxmoxHandler) -> None:
        """get_topology_edges() returns VM-to-host and storage-to-node edges."""
        vm_response = _mock_response(200, {
            "data": [
                {"vmid": 100, "type": "qemu", "node": "pve-01", "status": "running"},
                {"vmid": 200, "type": "lxc", "node": "pve-01", "status": "stopped"},
            ],
        })

        storage_response = _mock_response(200, {
            "data": [
                {
                    "storage": "local-zfs",
                    "node": "pve-01",
                    "plugintype": "zfspool",
                    "status": "available",
                    "maxdisk": 1099511627776,
                    "disk": 549755813888,
                },
            ],
        })

        async def mock_get(self_client: Any, path: str) -> httpx.Response:
            if "type=vm" in path:
                return vm_response
            if "type=storage" in path:
                return storage_response
            return _mock_response(404)  # pragma: no cover

        with patch.object(httpx.AsyncClient, "get", new=mock_get):
            edges = await handler.get_topology_edges("pve-01")

        # 2 VM edges + 1 storage edge = 3
        assert len(edges) == 3

        runs_on = [e for e in edges if e["relationship"] == "runs_on"]
        assert len(runs_on) == 2
        assert runs_on[0]["source"] == "proxmox::qemu::100"
        assert runs_on[0]["target"] == "proxmox::node::pve-01"

        attached = [e for e in edges if e["relationship"] == "attached_to"]
        assert len(attached) == 1
        assert attached[0]["source"] == "proxmox::storage::local-zfs"
        assert attached[0]["metadata"]["plugintype"] == "zfspool"
