"""Tests for network discovery scanning endpoints."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from hydra.api.v1.main import app as v1_app
from hydra.api.v1.routers.discovery import router as discovery_router
from hydra.api.v1.services.discovery.fingerprint import FingerprintService
from hydra.api.v1.services.docs import DocsService
from tests.conftest import create_mock_collection
from tests.utils import create_mock_cursor

# Register the discovery router on the v1 app so the test client can reach it.
_registered = False
if not _registered:
    v1_app.include_router(discovery_router)
    _registered = True


NETWORK_SCAN_DEFINITION = {
    "registryId": "reg::agent::network-scan",
    "category": "agent",
    "action": "network-scan",
    "displayName": "Run Delegated Network Scan",
    "description": "Run a delegated network discovery scan on an agent",
    "targetSchema": {"required": ["nodeId"]},
    "parametersSchema": {
        "type": "object",
        "required": ["scanId", "targetSpecs"],
    },
    "execution": {
        "timeout": 180,
        "deliveryMode": "poll_only",
        "retryable": False,
        "maxRetries": 0,
    },
    "rbac": {
        "minimumRole": "admin",
        "requiresConfirmation": False,
        "controlPermission": "agent:control:probe-network",
    },
    "metadata": {
        "version": "0.5.0",
        "builtIn": True,
    },
}


@pytest.fixture
def mock_scans_collection():
    """Create a mock discovery_scans collection."""
    return create_mock_collection()


@pytest.fixture
def mock_devices_collection():
    """Create a mock discovered_nodes collection."""
    return create_mock_collection()


@pytest.fixture
def mock_nodes_collection():
    """Create a mock nodes collection."""
    return create_mock_collection()


@pytest.fixture
def mock_exclusions_collection():
    """Create a mock discovery_exclusions collection."""
    return create_mock_collection()


@pytest.fixture(autouse=True)
def _patch_discovery_collections(
    mock_mongodb,
    mock_scans_collection,
    mock_devices_collection,
    mock_nodes_collection,
    mock_exclusions_collection,
):
    """Patch mock_mongodb.db to return discovery collections."""
    mock_db = MagicMock()

    def _getitem(name: str) -> MagicMock:
        if name == "discovery_scans":
            return mock_scans_collection
        if name == "discovered_nodes":
            return mock_devices_collection
        if name == "nodes":
            return mock_nodes_collection
        if name == "discovery_exclusions":
            return mock_exclusions_collection
        return create_mock_collection()

    mock_db.__getitem__ = MagicMock(side_effect=_getitem)
    mock_mongodb.db = mock_db


@pytest.fixture
def sample_scan():
    """Sample scan document."""
    now = datetime.now(UTC)
    return {
        "scanId": "scan_aabbccdd11223344",
        "status": "running",
        "targets": [{"networkId": "net-192-168-1", "subnet": "192.168.1.0/24", "delegateToNodeId": None}],
        "options": {
            "methods": ["arp", "tcp_port", "mdns", "ssdp", "snmp"],
            "portTier": "tier1",
            "timeoutSeconds": 60,
            "includeIoTProtocols": False,
        },
        "delegateToNodeId": None,
        "summary": None,
        "progress": {
            "phase": "running",
            "hostsTotal": 254,
            "hostsScanned": 0,
            "hostsAlive": 0,
            "percentComplete": 0.0,
        },
        "delegation": None,
        "error": None,
        "resultCount": 0,
        "startedBy": "user_admin123",
        "startedAt": now,
        "completedAt": None,
        "createdAt": now,
        "updatedAt": now,
    }


@pytest.fixture
def sample_device():
    """Sample discovered device document."""
    now = datetime.now(UTC)
    return {
        "discoveryId": "disc::mac::aa-bb-cc-dd-ee-ff",
        "identity": {
            "primaryMac": "aa:bb:cc:dd:ee:ff",
            "observedMacs": ["aa:bb:cc:dd:ee:ff"],
            "macVendor": None,
            "macResolved": True,
            "currentIp": "192.168.1.42",
            "observedIps": [{"address": "192.168.1.42", "seenAt": now.isoformat(), "seenInScan": None}],
            "hostname": "unknown-device",
            "hostnameSources": [],
        },
        "networkId": "net-192-168-1",
        "probe": {
            "scannedBy": "test-server-01",
            "method": "arp",
            "scannedAt": now.isoformat(),
            "sourceSubnet": "192.168.1.0/24",
        },
        "status": "pending",
        "firstSeen": now,
        "lastSeen": now,
        "seenCount": 1,
        "openPorts": [22, 80],
        "protocols": ["ssh", "http"],
        "rawEvidence": {
            "vendor": "Acme Devices",
            "macOui": "AABBCC",
            "dnsNames": ["unknown-device.local"],
            "banners": {"80": "Server: nginx"},
            "protocolDetails": {"http": {"paths": ["/"]}},
            "signals": ["ssh", "http"],
        },
        "dismissedAt": None,
        "dismissedBy": None,
        "dismissReason": None,
        "approvedAt": None,
        "approvedBy": None,
        "rejectedAt": None,
        "rejectedBy": None,
        "rejectReason": None,
        "matchedNodeId": None,
    }


def _mock_network_scan_command_setup(
    mock_mongodb,
    mock_nodes_collection: MagicMock | None = None,
    *,
    node_id: str = "scanner-node-01",
    agent_tier: str = "max",
) -> None:
    """Set up command-catalog and node mocks for delegated scan creation."""
    node_doc = {
        "nodeId": node_id,
        "status": "active",
        "agentTier": agent_tier,
        "serverAddress": "scanner.internal.example",
        "serverPort": 9443,
        "serverTlsEnabled": True,
        "agentServerSecret": "hsk_api_secret_123",
    }
    mock_mongodb.command_definitions.find_one = AsyncMock(
        return_value=NETWORK_SCAN_DEFINITION
    )
    mock_mongodb.nodes.find_one = AsyncMock(return_value=node_doc)
    if mock_nodes_collection is not None:
        mock_nodes_collection.find_one = AsyncMock(return_value=node_doc)
    mock_mongodb.commands.insert_one = AsyncMock()
    mock_mongodb.commands.count_documents = AsyncMock(return_value=0)


# ── Scan Tests ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_start_scan(
    client: AsyncClient,
    mock_mongodb,
    mock_scans_collection,
    admin_token,
    sample_user,
    sample_scan,
):
    """Test starting a new discovery scan returns 201 with scanId."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_scans_collection.insert_one = AsyncMock()

    response = await client.post(
        "/api/v1/discovery/scans",
        json={
            "targets": [{"subnet": "192.168.1.0/24"}],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert "data" in data
    assert data["data"]["scanId"].startswith("scan_")
    assert data["data"]["status"] == "running"
    mock_scans_collection.insert_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_scan_requires_permission(
    client: AsyncClient,
    mock_mongodb,
    sample_user,
    viewer_token,
):
    """Test that starting a scan requires discovery:scan permission."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_viewer123", "role": "viewer"}
    )

    response = await client.post(
        "/api/v1/discovery/scans",
        json={
            "targets": [{"subnet": "10.0.0.0/24"}],
        },
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_start_scan_with_delegation(
    client: AsyncClient,
    mock_mongodb,
    mock_scans_collection,
    mock_nodes_collection,
    admin_token,
    sample_user,
):
    """Test that a delegated scan starts in PENDING status."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_scans_collection.insert_one = AsyncMock()
    _mock_network_scan_command_setup(
        mock_mongodb,
        mock_nodes_collection,
    )
    queued_scan = {
        "scanId": "scan_delegated001",
        "status": "pending",
        "targets": [{"subnet": "192.168.1.0/24", "delegateToNodeId": None}],
        "options": {
            "methods": ["arp", "tcp_port", "mdns", "ssdp", "snmp"],
            "portTier": "tier1",
            "timeoutSeconds": 60,
            "includeIoTProtocols": False,
        },
        "delegateToNodeId": "scanner-node-01",
        "summary": None,
        "progress": {
            "phase": "queued",
            "hostsTotal": 254,
            "hostsScanned": 0,
            "hostsAlive": 0,
            "percentComplete": 0.0,
        },
        "delegation": {
            "delegatedTo": "scanner-node-01",
            "commandId": "cmd_delegated001",
            "executionMethod": "agent-poll",
            "commandStatus": "queued",
            "notes": ["Delegated network scan queued for agent execution."],
        },
        "error": None,
        "resultCount": 0,
        "startedBy": "user_admin123",
        "startedAt": None,
        "completedAt": None,
        "createdAt": datetime.now(UTC),
        "updatedAt": datetime.now(UTC),
    }
    mock_scans_collection.find_one = AsyncMock(return_value=queued_scan)

    response = await client.post(
        "/api/v1/discovery/scans",
        json={
            "targets": [{"subnet": "192.168.1.0/24"}],
            "delegateToNodeId": "scanner-node-01",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["status"] == "pending"
    assert data["delegateToNodeId"] == "scanner-node-01"
    assert data["delegation"]["commandId"] is not None
    assert data["delegation"]["delegatedTo"] == "scanner-node-01"
    created_command = mock_mongodb.commands.insert_one.await_args.args[0]
    assert created_command["registryId"] == "reg::agent::network-scan"
    assert created_command["target"]["nodeId"] == "scanner-node-01"
    assert created_command["parameters"]["scanId"].startswith("scan_")
    assert created_command["parameters"]["targetSpecs"][0]["subnet"] == "192.168.1.0/24"


@pytest.mark.asyncio
async def test_start_scan_with_delegation_requires_max_tier(
    client: AsyncClient,
    mock_mongodb,
    mock_scans_collection,
    mock_nodes_collection,
    admin_token,
    sample_user,
):
    """Delegated scans must target a max-tier scanner node."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_scans_collection.insert_one = AsyncMock()
    _mock_network_scan_command_setup(
        mock_mongodb,
        mock_nodes_collection,
        agent_tier="normal",
    )

    response = await client.post(
        "/api/v1/discovery/scans",
        json={
            "targets": [{"subnet": "192.168.1.0/24"}],
            "delegateToNodeId": "scanner-node-01",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "COMMAND_NOT_SUPPORTED"
    mock_scans_collection.insert_one.assert_not_awaited()
    mock_mongodb.commands.insert_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_scans(
    client: AsyncClient,
    mock_mongodb,
    mock_scans_collection,
    admin_token,
    sample_user,
    sample_scan,
):
    """Test listing scans returns paginated list."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_scans_collection.count_documents = AsyncMock(return_value=1)
    mock_scans_collection.find.return_value = create_mock_cursor([sample_scan])

    response = await client.get(
        "/api/v1/discovery/scans",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["scanId"] == sample_scan["scanId"]
    assert data["meta"]["total"] == 1


@pytest.mark.asyncio
async def test_list_scans_filter_by_status(
    client: AsyncClient,
    mock_mongodb,
    mock_scans_collection,
    admin_token,
    sample_user,
    sample_scan,
):
    """Test listing scans with status filter."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_scans_collection.count_documents = AsyncMock(return_value=1)
    mock_scans_collection.find.return_value = create_mock_cursor([sample_scan])

    response = await client.get(
        "/api/v1/discovery/scans?status=running",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    # Verify filter was passed to count_documents
    call_args = mock_scans_collection.count_documents.call_args
    filter_query = call_args[0][0]
    assert filter_query.get("status") == "running"


@pytest.mark.asyncio
async def test_get_scan(
    client: AsyncClient,
    mock_mongodb,
    mock_scans_collection,
    admin_token,
    sample_user,
    sample_scan,
):
    """Test getting a specific scan by ID."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_scans_collection.find_one = AsyncMock(return_value=sample_scan)

    response = await client.get(
        f"/api/v1/discovery/scans/{sample_scan['scanId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["scanId"] == sample_scan["scanId"]
    assert data["status"] == "running"


@pytest.mark.asyncio
async def test_get_scan_not_found(
    client: AsyncClient,
    mock_mongodb,
    mock_scans_collection,
    admin_token,
    sample_user,
):
    """Test getting a non-existent scan returns 404."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_scans_collection.find_one = AsyncMock(return_value=None)

    response = await client.get(
        "/api/v1/discovery/scans/scan_nonexistent",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_submit_scan_results(
    client: AsyncClient,
    mock_mongodb,
    mock_scans_collection,
    mock_devices_collection,
    admin_token,
    sample_user,
    sample_scan,
):
    """Test submitting scan results updates scan and creates discoveries."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    completed_scan = {
        **sample_scan,
        "status": "completed",
        "completedAt": datetime.now(UTC),
        "resultCount": 1,
        "progress": {
            "phase": "completed",
            "hostsTotal": 254,
            "hostsScanned": 254,
            "hostsAlive": 5,
            "percentComplete": 100.0,
        },
    }

    # First find_one for get_scan (verify exists), second for get_scan after update
    mock_scans_collection.find_one = AsyncMock(
        side_effect=[sample_scan, completed_scan]
    )
    mock_scans_collection.update_one = AsyncMock()

    # Device find_one calls: 1) upsert check (None = new), 2) enrich_discovery->get_discovery
    enriched_device = {
        "discoveryId": "disc::mac::aa-bb-cc-dd-ee-ff",
        "identity": {
            "primaryMac": "aa:bb:cc:dd:ee:ff",
            "currentIp": "192.168.1.42",
            "hostname": "new-device",
        },
        "openPorts": [22, 80],
        "protocols": ["ssh"],
        "status": "pending",
        "firstSeen": datetime.now(UTC),
        "lastSeen": datetime.now(UTC),
        "seenCount": 1,
        "fingerprint": None,
        "classification": None,
    }
    mock_devices_collection.find_one = AsyncMock(
        side_effect=[None, enriched_device]
    )
    mock_devices_collection.insert_one = AsyncMock()
    mock_devices_collection.update_one = AsyncMock()

    response = await client.post(
        f"/api/v1/discovery/scans/{sample_scan['scanId']}/results",
        json={
            "results": [
                {
                    "identity": {
                        "primaryMac": "aa:bb:cc:dd:ee:ff",
                        "currentIp": "192.168.1.42",
                        "hostname": "new-device",
                    },
                    "openPorts": [22, 80],
                    "protocols": ["ssh"],
                    "probe": {
                        "scannedBy": "test-server-01",
                        "method": "arp",
                        "scannedAt": datetime.now(UTC).isoformat(),
                    },
                }
            ],
            "summary": {
                "hostsScanned": 254,
                "hostsAlive": 5,
                "newDiscoveries": 1,
                "returningDevices": 0,
                "errors": [],
            },
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "completed"
    assert data["resultCount"] == 1
    assert data["progress"]["phase"] == "completed"
    mock_devices_collection.insert_one.assert_awaited_once()
    mock_scans_collection.update_one.assert_awaited_once()
    # Enrichment should have been triggered for the new device with open ports
    mock_devices_collection.update_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_submit_results_to_completed_scan(
    client: AsyncClient,
    mock_mongodb,
    mock_scans_collection,
    admin_token,
    sample_user,
    sample_scan,
):
    """Test submitting results to an already completed scan returns 409."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    completed_scan = {**sample_scan, "status": "completed"}
    mock_scans_collection.find_one = AsyncMock(return_value=completed_scan)

    response = await client.post(
        f"/api/v1/discovery/scans/{sample_scan['scanId']}/results",
        json={
            "results": [],
            "summary": {
                "hostsScanned": 0,
                "hostsAlive": 0,
                "newDiscoveries": 0,
                "returningDevices": 0,
                "errors": [],
            },
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 409


# ── Discovery Device Tests ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_discoveries(
    client: AsyncClient,
    mock_mongodb,
    mock_devices_collection,
    admin_token,
    sample_user,
    sample_device,
):
    """Test listing discovered devices returns paginated list."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_devices_collection.count_documents = AsyncMock(return_value=1)
    mock_devices_collection.find.return_value = create_mock_cursor([sample_device])

    response = await client.get(
        "/api/v1/discovery/devices",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["discoveryId"] == sample_device["discoveryId"]
    assert data["meta"]["total"] == 1


@pytest.mark.asyncio
async def test_list_discoveries_search(
    client: AsyncClient,
    mock_mongodb,
    mock_devices_collection,
    admin_token,
    sample_user,
    sample_device,
):
    """Test searching discovered devices with re.escape safety."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_devices_collection.count_documents = AsyncMock(return_value=0)
    mock_devices_collection.find.return_value = create_mock_cursor([])

    # Use a string containing regex special characters
    dangerous_search = "(a+)+b.*"

    response = await client.get(
        "/api/v1/discovery/devices",
        params={"search": dangerous_search},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200

    # Verify the filter passed to count_documents uses escaped string
    call_args = mock_devices_collection.count_documents.call_args
    filter_query = call_args[0][0]
    assert "$or" in filter_query

    escaped = re.escape(dangerous_search)
    for condition in filter_query["$or"]:
        field_key = next(iter(condition))
        regex_value = condition[field_key]["$regex"]
        assert regex_value == escaped


@pytest.mark.asyncio
async def test_get_discovery(
    client: AsyncClient,
    mock_mongodb,
    mock_devices_collection,
    admin_token,
    sample_user,
    sample_device,
):
    """Test getting a specific discovered device by ID."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_devices_collection.find_one = AsyncMock(return_value=sample_device)

    response = await client.get(
        f"/api/v1/discovery/devices/{sample_device['discoveryId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["discoveryId"] == sample_device["discoveryId"]
    assert data["identity"]["currentIp"] == "192.168.1.42"


@pytest.mark.asyncio
async def test_get_discovery_not_found(
    client: AsyncClient,
    mock_mongodb,
    mock_devices_collection,
    admin_token,
    sample_user,
):
    """Test getting a non-existent discovery returns 404."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_devices_collection.find_one = AsyncMock(return_value=None)

    response = await client.get(
        "/api/v1/discovery/devices/disc_nonexistent",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_dismiss_discovery(
    client: AsyncClient,
    mock_mongodb,
    mock_devices_collection,
    admin_token,
    sample_user,
    sample_device,
):
    """Test dismissing a discovered device sets dismissed status."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    dismissed_device = {
        **sample_device,
        "status": "dismissed",
        "dismissedAt": datetime.now(UTC),
        "dismissedBy": "user_admin123",
        "dismissReason": "Known printer",
    }

    # First find_one for get (verify exists), second for get after update
    mock_devices_collection.find_one = AsyncMock(
        side_effect=[sample_device, dismissed_device]
    )
    mock_devices_collection.update_one = AsyncMock()

    response = await client.post(
        f"/api/v1/discovery/devices/{sample_device['discoveryId']}/dismiss",
        json={"reason": "Known printer"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "dismissed"
    assert data["dismissReason"] == "Known printer"
    mock_devices_collection.update_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_dismiss_already_dismissed(
    client: AsyncClient,
    mock_mongodb,
    mock_devices_collection,
    admin_token,
    sample_user,
    sample_device,
):
    """Test dismissing an already dismissed device returns 409."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    dismissed_device = {**sample_device, "status": "dismissed"}
    mock_devices_collection.find_one = AsyncMock(return_value=dismissed_device)

    response = await client.post(
        f"/api/v1/discovery/devices/{sample_device['discoveryId']}/dismiss",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_dismiss_registered_device(
    client: AsyncClient,
    mock_mongodb,
    mock_devices_collection,
    admin_token,
    sample_user,
    sample_device,
):
    """Test dismissing a registered device returns 409."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    registered_device = {**sample_device, "status": "registered", "matchedNodeId": "test-node"}
    mock_devices_collection.find_one = AsyncMock(return_value=registered_device)

    response = await client.post(
        f"/api/v1/discovery/devices/{sample_device['discoveryId']}/dismiss",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 409


# ── Fingerprint & Classification Tests ─────────────────────────────────


class TestFingerprintService:
    """Unit tests for FingerprintService."""

    def setup_method(self) -> None:
        self.fp_service = FingerprintService()

    def test_fingerprint_compute_device(self) -> None:
        """SSH + HTTP ports produce compute classification."""
        fp = self.fp_service.fingerprint_device([22, 80, 443, 9090], [])
        assert "ssh" in fp.service_hints
        assert "http" in fp.service_hints
        assert "https" in fp.service_hints
        assert "prometheus" in fp.service_hints
        assert fp.port_numbers == [22, 80, 443, 9090]
        assert len(fp.open_ports) == 4
        assert fp.open_ports[0].port == 22
        assert fp.open_ports[0].service == "ssh"

        cls = self.fp_service.classify_device(fp)
        assert cls.suggested_class == "compute"
        assert cls.confidence > 0
        assert cls.suggested_type == "server"
        assert cls.suggested_kind == "server"

    def test_fingerprint_networking_device(self) -> None:
        """BGP + SNMP ports produce networking classification."""
        fp = self.fp_service.fingerprint_device([179, 161, 22], ["snmp"])
        cls = self.fp_service.classify_device(fp)
        assert cls.suggested_class == "networking"
        assert cls.suggested_type == "router"

    def test_fingerprint_iot_device(self) -> None:
        """MQTT + HA ports produce iot classification."""
        fp = self.fp_service.fingerprint_device([1883, 8123], ["mqtt"])
        cls = self.fp_service.classify_device(fp)
        assert cls.suggested_class == "iot"
        assert cls.suggested_type == "home-automation"

    def test_fingerprint_unknown_device(self) -> None:
        """No known ports produce unknown classification."""
        fp = self.fp_service.fingerprint_device([12345], [])
        cls = self.fp_service.classify_device(fp)
        assert cls.suggested_class == "unknown"
        assert cls.confidence == 0.0
        assert "no-classification-signals" in cls.signals

    def test_fingerprint_empty_ports(self) -> None:
        """Empty ports produce unknown classification."""
        fp = self.fp_service.fingerprint_device([], [])
        assert fp.open_ports == []
        assert fp.port_numbers == []
        assert fp.service_hints == []
        cls = self.fp_service.classify_device(fp)
        assert cls.suggested_class == "unknown"
        assert cls.confidence == 0.0

    def test_fingerprint_os_hint_linux(self) -> None:
        """Port 22 without 3389 suggests linux."""
        fp = self.fp_service.fingerprint_device([22], [])
        assert fp.os_hint == "linux"

    def test_fingerprint_os_hint_windows(self) -> None:
        """Port 3389 suggests windows even with 22 present."""
        fp = self.fp_service.fingerprint_device([3389, 22], [])
        assert fp.os_hint == "windows"

    def test_fingerprint_os_hint_embedded(self) -> None:
        """Home Assistant port suggests embedded."""
        fp = self.fp_service.fingerprint_device([8123], [])
        assert fp.os_hint == "embedded"

    def test_fingerprint_os_hint_none(self) -> None:
        """Unknown ports produce no OS hint."""
        fp = self.fp_service.fingerprint_device([12345], [])
        assert fp.os_hint is None

    def test_suggested_type_hypervisor(self) -> None:
        """Proxmox port classifies as hypervisor."""
        fp = self.fp_service.fingerprint_device([22, 8006], [])
        cls = self.fp_service.classify_device(fp)
        assert cls.suggested_class == "compute"
        assert cls.suggested_type == "hypervisor"

    def test_suggested_type_kubernetes(self) -> None:
        """K8s API port classifies as kubernetes-node."""
        fp = self.fp_service.fingerprint_device([22, 6443], [])
        cls = self.fp_service.classify_device(fp)
        assert cls.suggested_type == "kubernetes-node"

    def test_suggested_type_docker_host(self) -> None:
        """Docker API port classifies as docker-host."""
        fp = self.fp_service.fingerprint_device([22, 2375], [])
        cls = self.fp_service.classify_device(fp)
        assert cls.suggested_type == "docker-host"

    def test_suggested_type_mikrotik(self) -> None:
        """MikroTik API port classifies as mikrotik."""
        fp = self.fp_service.fingerprint_device([8291], [])
        cls = self.fp_service.classify_device(fp)
        assert cls.suggested_class == "networking"
        assert cls.suggested_type == "mikrotik"

    def test_suggested_type_mqtt_device(self) -> None:
        """MQTT-only device classifies as mqtt-device."""
        fp = self.fp_service.fingerprint_device([1883], [])
        cls = self.fp_service.classify_device(fp)
        assert cls.suggested_class == "iot"
        assert cls.suggested_type == "mqtt-device"

    def test_service_hints_deduplication(self) -> None:
        """Duplicate ports produce unique service hints."""
        fp = self.fp_service.fingerprint_device([22, 22, 80, 80], [])
        assert fp.service_hints == ["http", "ssh"]
        # port_numbers are deduped and sorted
        assert fp.port_numbers == [22, 80]

    def test_protocol_signals(self) -> None:
        """Protocol-based signals boost classification scores."""
        fp = self.fp_service.fingerprint_device([22], ["snmp", "bgp"])
        cls = self.fp_service.classify_device(fp)
        # snmp and bgp each add 2 to networking; port 22 adds 1 to compute
        assert cls.suggested_class == "networking"

    def test_fingerprint_serialization(self) -> None:
        """Fingerprint serializes with camelCase aliases."""
        fp = self.fp_service.fingerprint_device([22, 80], ["mdns"])
        data = fp.model_dump(by_alias=True)
        assert "openPorts" in data
        assert "portNumbers" in data
        assert "serviceHints" in data
        assert "osHint" in data
        assert data["portNumbers"] == [22, 80]
        assert isinstance(data["openPorts"], list)
        assert len(data["openPorts"]) == 2
        assert data["openPorts"][0]["port"] == 22

    def test_classification_serialization(self) -> None:
        """Classification serializes with camelCase aliases."""
        fp = self.fp_service.fingerprint_device([22, 80], [])
        cls = self.fp_service.classify_device(fp)
        data = cls.model_dump(by_alias=True)
        assert "suggestedClass" in data
        assert "suggestedType" in data
        assert "suggestedKind" in data
        assert data["suggestedClass"] == "compute"


# ── Enrichment Integration Tests ───────────────────────────────────────


@pytest.mark.asyncio
async def test_enrich_discovery(
    client: AsyncClient,
    mock_mongodb: MagicMock,
    mock_devices_collection: MagicMock,
    admin_token: str,
    sample_user: dict,  # noqa: ARG001
    sample_device: dict,
) -> None:
    """Enrichment adds fingerprint and classification to a discovered device."""
    from hydra.api.v1.services.discovery.service import DiscoveryService

    service = DiscoveryService(mock_mongodb)

    mock_devices_collection.find_one = AsyncMock(return_value=sample_device)
    mock_devices_collection.update_one = AsyncMock()

    result = await service.enrich_discovery(sample_device["discoveryId"])

    assert "fingerprint" in result
    assert "classification" in result
    assert "eligibility" in result
    fp = result["fingerprint"]
    cls = result["classification"]
    elig = result["eligibility"]
    assert "openPorts" in fp
    assert "portNumbers" in fp
    assert "serviceHints" in fp
    assert "suggestedClass" in cls
    assert cls["suggestedClass"] == "compute"
    assert cls["confidence"] > 0
    assert "registerable" in elig
    assert elig["registerable"] is True

    mock_devices_collection.update_one.assert_awaited_once()
    call_args = mock_devices_collection.update_one.call_args
    update_set = call_args[0][1]["$set"]
    assert "fingerprint" in update_set
    assert "classification" in update_set
    assert "eligibility" in update_set
    assert "updatedAt" in update_set


@pytest.mark.asyncio
async def test_enrich_discovery_not_found(
    mock_mongodb: MagicMock,
    mock_devices_collection: MagicMock,
) -> None:
    """Enrichment raises NotFoundError for missing device."""
    from hydra.api.v1.services.discovery.service import (
        DiscoveryNotFoundError,
        DiscoveryService,
    )

    service = DiscoveryService(mock_mongodb)
    mock_devices_collection.find_one = AsyncMock(return_value=None)

    with pytest.raises(DiscoveryNotFoundError):
        await service.enrich_discovery("disc::mac::00-00-00-00-00-00")


@pytest.mark.asyncio
async def test_submit_results_triggers_enrichment(
    client: AsyncClient,
    mock_mongodb: MagicMock,
    mock_scans_collection: MagicMock,
    mock_devices_collection: MagicMock,
    admin_token: str,
    sample_user: dict,
    sample_scan: dict,
) -> None:
    """Submitting scan results with open ports triggers device enrichment."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )

    completed_scan = {**sample_scan, "status": "completed", "completedAt": datetime.now(UTC)}

    # Scan: first call for get_scan (verify), second for get_scan after update
    mock_scans_collection.find_one = AsyncMock(
        side_effect=[sample_scan, completed_scan]
    )
    mock_scans_collection.update_one = AsyncMock()

    # Device: first find_one for upsert (no match = new),
    # second find_one for enrich_discovery (get_discovery)
    new_device_doc = {
        "discoveryId": "disc::mac::ee-ee-ee-ee-ee-ee",
        "identity": {
            "primaryMac": "11:22:33:44:55:66",
            "currentIp": "192.168.1.100",
            "hostname": "new-server",
        },
        "openPorts": [22, 80, 443],
        "protocols": [],
        "status": "pending",
        "firstSeen": datetime.now(UTC),
        "lastSeen": datetime.now(UTC),
        "seenCount": 1,
        "fingerprint": None,
        "classification": None,
    }
    mock_devices_collection.find_one = AsyncMock(
        side_effect=[None, new_device_doc]
    )
    mock_devices_collection.insert_one = AsyncMock()
    mock_devices_collection.update_one = AsyncMock()

    response = await client.post(
        f"/api/v1/discovery/scans/{sample_scan['scanId']}/results",
        json={
            "results": [
                {
                    "identity": {
                        "primaryMac": "11:22:33:44:55:66",
                        "currentIp": "192.168.1.100",
                        "hostname": "new-server",
                    },
                    "openPorts": [22, 80, 443],
                    "protocols": [],
                    "probe": {
                        "scannedBy": "test-server-01",
                        "method": "arp",
                        "scannedAt": datetime.now(UTC).isoformat(),
                    },
                }
            ],
            "summary": {
                "hostsScanned": 254,
                "hostsAlive": 1,
                "newDiscoveries": 1,
                "returningDevices": 0,
                "errors": [],
            },
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    # insert_one for new device, then update_one for enrichment
    mock_devices_collection.insert_one.assert_awaited_once()
    mock_devices_collection.update_one.assert_awaited_once()
    # Verify the enrichment update contains fingerprint/classification
    enrich_call = mock_devices_collection.update_one.call_args
    update_set = enrich_call[0][1]["$set"]
    assert "fingerprint" in update_set
    assert "classification" in update_set
    assert update_set["classification"]["suggestedClass"] == "compute"


# ── Approval / Rejection Tests ────────────────────────────────────────


@pytest.fixture
def sample_device_with_classification(sample_device):
    """Sample device with fingerprint and classification data."""
    return {
        **sample_device,
        "fingerprint": {
            "openPorts": [22, 80],
            "serviceHints": ["ssh", "http"],
            "protocols": [],
            "osHint": "linux",
        },
        "classification": {
            "suggestedClass": "compute",
            "suggestedType": "server",
            "confidence": 0.8,
            "signals": ["ssh", "http"],
        },
    }


@pytest.mark.asyncio
async def test_approve_device_auto_register(
    client: AsyncClient,
    mock_mongodb: MagicMock,
    mock_devices_collection: MagicMock,
    mock_nodes_collection: MagicMock,
    admin_token: str,
    sample_user: dict,
    sample_device_with_classification: dict,
) -> None:
    """Approve pending device with auto-register creates a node."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_devices_collection.find_one = AsyncMock(
        return_value=sample_device_with_classification
    )
    mock_devices_collection.update_one = AsyncMock()
    mock_nodes_collection.insert_one = AsyncMock()

    response = await client.post(
        f"/api/v1/discovery/devices/{sample_device_with_classification['discoveryId']}/approve",
        json={"autoRegister": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "registered"
    assert data["matchedNodeId"] is not None
    # Derived from hostname "unknown-device"
    assert data["matchedNodeId"] == "unknown-device"
    mock_nodes_collection.insert_one.assert_awaited_once()
    mock_devices_collection.update_one.assert_awaited_once()

    # Verify node document structure
    node_doc = mock_nodes_collection.insert_one.call_args[0][0]
    assert node_doc["nodeId"] == "unknown-device"
    assert node_doc["class"] == "compute"
    assert node_doc["registeredVia"] == "discovery"
    assert node_doc["status"] == "active"


@pytest.mark.asyncio
async def test_approve_device_auto_register_refreshes_docs(
    client: AsyncClient,
    mock_mongodb: MagicMock,
    mock_devices_collection: MagicMock,
    mock_nodes_collection: MagicMock,
    admin_token: str,
    sample_user: dict,
    sample_device_with_classification: dict,
    monkeypatch,
) -> None:
    """Auto-registration refreshes docs for the new node and related network."""
    refresh_mock = AsyncMock(
        return_value={
            "flagged": 2,
            "regenerated": 1,
            "warningCount": 0,
            "errors": 0,
            "entityCount": 2,
        }
    )
    monkeypatch.setattr(DocsService, "refresh_documents_for_entities", refresh_mock)

    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_devices_collection.find_one = AsyncMock(
        return_value=sample_device_with_classification
    )
    mock_devices_collection.update_one = AsyncMock()
    mock_nodes_collection.insert_one = AsyncMock()

    response = await client.post(
        f"/api/v1/discovery/devices/{sample_device_with_classification['discoveryId']}/approve",
        json={"autoRegister": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    refresh_mock.assert_awaited_once_with(
        [
            ("node", "unknown-device"),
            ("network", sample_device_with_classification["networkId"]),
        ],
        user_id="user_admin123",
    )


@pytest.mark.asyncio
async def test_approve_device_auto_register_requires_nodes_create(
    client: AsyncClient,
    mock_mongodb: MagicMock,
    mock_devices_collection: MagicMock,
    viewer_token: str,
    sample_user: dict,
    sample_device_with_classification: dict,
) -> None:
    """Auto-registering through approve still requires nodes:create."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={
            **sample_user,
            "userId": "user_viewer123",
            "role": "viewer",
            "permissions": ["discovery:scan"],
        }
    )
    mock_devices_collection.find_one = AsyncMock(
        return_value=sample_device_with_classification
    )

    response = await client.post(
        f"/api/v1/discovery/devices/{sample_device_with_classification['discoveryId']}/approve",
        json={"autoRegister": True},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["details"]["required_permission"] == "nodes:create"


@pytest.mark.asyncio
async def test_approve_device_without_auto_register(
    client: AsyncClient,
    mock_mongodb: MagicMock,
    mock_devices_collection: MagicMock,
    mock_nodes_collection: MagicMock,
    admin_token: str,
    sample_user: dict,
    sample_device: dict,
) -> None:
    """Approve without auto-registration sets status to approved only."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_devices_collection.find_one = AsyncMock(return_value=sample_device)
    mock_devices_collection.update_one = AsyncMock()

    response = await client.post(
        f"/api/v1/discovery/devices/{sample_device['discoveryId']}/approve",
        json={"autoRegister": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "approved"
    assert data["matchedNodeId"] is None
    # No node should have been created
    mock_nodes_collection.insert_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_approve_device_custom_node_id(
    client: AsyncClient,
    mock_mongodb: MagicMock,
    mock_devices_collection: MagicMock,
    mock_nodes_collection: MagicMock,
    admin_token: str,
    sample_user: dict,
    sample_device_with_classification: dict,
) -> None:
    """Approve with custom nodeId override uses that ID."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_devices_collection.find_one = AsyncMock(
        return_value=sample_device_with_classification
    )
    mock_devices_collection.update_one = AsyncMock()
    mock_nodes_collection.insert_one = AsyncMock()

    response = await client.post(
        f"/api/v1/discovery/devices/{sample_device_with_classification['discoveryId']}/approve",
        json={"autoRegister": True, "nodeId": "my-custom-node"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["matchedNodeId"] == "my-custom-node"

    node_doc = mock_nodes_collection.insert_one.call_args[0][0]
    assert node_doc["nodeId"] == "my-custom-node"


@pytest.mark.asyncio
async def test_approve_device_custom_class(
    client: AsyncClient,
    mock_mongodb: MagicMock,
    mock_devices_collection: MagicMock,
    mock_nodes_collection: MagicMock,
    admin_token: str,
    sample_user: dict,
    sample_device_with_classification: dict,
) -> None:
    """Approve with custom nodeClass override uses that class."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_devices_collection.find_one = AsyncMock(
        return_value=sample_device_with_classification
    )
    mock_devices_collection.update_one = AsyncMock()
    mock_nodes_collection.insert_one = AsyncMock()

    response = await client.post(
        f"/api/v1/discovery/devices/{sample_device_with_classification['discoveryId']}/approve",
        json={"autoRegister": True, "nodeClass": "networking"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    node_doc = mock_nodes_collection.insert_one.call_args[0][0]
    assert node_doc["class"] == "networking"


@pytest.mark.asyncio
async def test_approve_non_pending_returns_409(
    client: AsyncClient,
    mock_mongodb: MagicMock,
    mock_devices_collection: MagicMock,
    admin_token: str,
    sample_user: dict,
    sample_device: dict,
) -> None:
    """Approving a non-pending device returns 409."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    rejected_device = {**sample_device, "status": "rejected"}
    mock_devices_collection.find_one = AsyncMock(return_value=rejected_device)

    response = await client.post(
        f"/api/v1/discovery/devices/{sample_device['discoveryId']}/approve",
        json={"autoRegister": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_reject_device(
    client: AsyncClient,
    mock_mongodb: MagicMock,
    mock_devices_collection: MagicMock,
    admin_token: str,
    sample_user: dict,
    sample_device: dict,
) -> None:
    """Reject pending device with reason."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_devices_collection.find_one = AsyncMock(return_value=sample_device)
    mock_devices_collection.update_one = AsyncMock()

    response = await client.post(
        f"/api/v1/discovery/devices/{sample_device['discoveryId']}/reject",
        json={"reason": "Not part of our network"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "rejected"
    assert data["matchedNodeId"] is None

    # Verify the update included the reason
    update_call = mock_devices_collection.update_one.call_args
    update_set = update_call[0][1]["$set"]
    assert update_set["status"] == "rejected"
    assert update_set["rejectReason"] == "Not part of our network"
    assert update_set["rejectedBy"] == "user_admin123"


@pytest.mark.asyncio
async def test_reject_non_pending_returns_409(
    client: AsyncClient,
    mock_mongodb: MagicMock,
    mock_devices_collection: MagicMock,
    admin_token: str,
    sample_user: dict,
    sample_device: dict,
) -> None:
    """Rejecting a non-pending device returns 409."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    approved_device = {**sample_device, "status": "approved"}
    mock_devices_collection.find_one = AsyncMock(return_value=approved_device)

    response = await client.post(
        f"/api/v1/discovery/devices/{sample_device['discoveryId']}/reject",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_bulk_approve(
    client: AsyncClient,
    mock_mongodb: MagicMock,
    mock_devices_collection: MagicMock,
    mock_nodes_collection: MagicMock,
    admin_token: str,
    sample_user: dict,
) -> None:
    """Bulk approve multiple pending devices."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    now = datetime.now(UTC)

    def make_device(disc_id: str, hostname: str) -> dict:
        return {
            "discoveryId": disc_id,
            "identity": {
                "primaryMac": None,
                "currentIp": "192.168.1.10",
                "hostname": hostname,
            },
            "networkId": "net-192-168-1",
            "probe": {"scannedBy": "test", "method": "arp", "scannedAt": now.isoformat()},
            "status": "pending",
            "firstSeen": now,
            "lastSeen": now,
            "seenCount": 1,
            "openPorts": [22],
            "protocols": [],
            "fingerprint": None,
            "classification": {"suggestedClass": "compute", "suggestedType": "server", "confidence": 0.5, "signals": []},
            "dismissedAt": None,
            "dismissedBy": None,
            "dismissReason": None,
            "approvedAt": None,
            "approvedBy": None,
            "rejectedAt": None,
            "rejectedBy": None,
            "rejectReason": None,
            "matchedNodeId": None,
        }

    devices = [
        make_device("disc::ip::net-1::192.168.1.10", "host-a"),
        make_device("disc::ip::net-1::192.168.1.11", "host-b"),
        make_device("disc::ip::net-1::192.168.1.12", "host-c"),
    ]

    # find_one is called once per approve_device call
    mock_devices_collection.find_one = AsyncMock(side_effect=devices)
    mock_devices_collection.update_one = AsyncMock()
    mock_nodes_collection.insert_one = AsyncMock()

    response = await client.post(
        "/api/v1/discovery/devices/bulk-approve",
        json={
            "discoveryIds": ["disc::ip::net-1::192.168.1.10", "disc::ip::net-1::192.168.1.11", "disc::ip::net-1::192.168.1.12"],
            "autoRegister": True,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["processed"] == 3
    assert data["succeeded"] == 3
    assert data["failed"] == 0
    assert len(data["results"]) == 3
    assert mock_nodes_collection.insert_one.await_count == 3


@pytest.mark.asyncio
async def test_bulk_reject(
    client: AsyncClient,
    mock_mongodb: MagicMock,
    mock_devices_collection: MagicMock,
    admin_token: str,
    sample_user: dict,
) -> None:
    """Bulk reject multiple pending devices."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    now = datetime.now(UTC)

    def make_pending_device(disc_id: str) -> dict:
        return {
            "discoveryId": disc_id,
            "identity": {"primaryMac": None, "currentIp": "10.0.0.1", "hostname": None},
            "networkId": None,
            "probe": {"scannedBy": "test", "method": "arp", "scannedAt": now.isoformat()},
            "status": "pending",
            "firstSeen": now,
            "lastSeen": now,
            "seenCount": 1,
            "openPorts": [],
            "protocols": [],
            "fingerprint": None,
            "classification": None,
            "dismissedAt": None,
            "dismissedBy": None,
            "dismissReason": None,
            "approvedAt": None,
            "approvedBy": None,
            "rejectedAt": None,
            "rejectedBy": None,
            "rejectReason": None,
            "matchedNodeId": None,
        }

    devices = [make_pending_device("disc::ip::unknown::10.0.0.10"), make_pending_device("disc::ip::unknown::10.0.0.11")]
    mock_devices_collection.find_one = AsyncMock(side_effect=devices)
    mock_devices_collection.update_one = AsyncMock()

    response = await client.post(
        "/api/v1/discovery/devices/bulk-reject",
        json={
            "discoveryIds": ["disc::ip::unknown::10.0.0.10", "disc::ip::unknown::10.0.0.11"],
            "reason": "Unauthorized devices",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["processed"] == 2
    assert data["succeeded"] == 2
    assert data["failed"] == 0


@pytest.mark.asyncio
async def test_bulk_approve_partial_failure(
    client: AsyncClient,
    mock_mongodb: MagicMock,
    mock_devices_collection: MagicMock,
    mock_nodes_collection: MagicMock,
    admin_token: str,
    sample_user: dict,
) -> None:
    """Bulk approve with some non-pending devices results in partial failure."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    now = datetime.now(UTC)

    pending_device = {
        "discoveryId": "disc::ip::unknown::10.0.0.1",
        "identity": {"primaryMac": None, "currentIp": "10.0.0.1", "hostname": "good-host"},
        "networkId": None,
        "probe": {"scannedBy": "test", "method": "arp", "scannedAt": now.isoformat()},
        "status": "pending",
        "firstSeen": now,
        "lastSeen": now,
        "seenCount": 1,
        "openPorts": [],
        "protocols": [],
        "fingerprint": None,
        "classification": None,
        "dismissedAt": None,
        "dismissedBy": None,
        "dismissReason": None,
        "approvedAt": None,
        "approvedBy": None,
        "rejectedAt": None,
        "rejectedBy": None,
        "rejectReason": None,
        "matchedNodeId": None,
    }
    already_approved = {**pending_device, "discoveryId": "disc::ip::unknown::10.0.0.2", "status": "approved"}

    # First call returns pending, second returns already-approved
    mock_devices_collection.find_one = AsyncMock(
        side_effect=[pending_device, already_approved]
    )
    mock_devices_collection.update_one = AsyncMock()
    mock_nodes_collection.insert_one = AsyncMock()

    response = await client.post(
        "/api/v1/discovery/devices/bulk-approve",
        json={
            "discoveryIds": ["disc::ip::unknown::10.0.0.1", "disc::ip::unknown::10.0.0.2"],
            "autoRegister": True,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["processed"] == 2
    assert data["succeeded"] == 1
    assert data["failed"] == 1
    assert len(data["errors"]) == 1
    assert data["errors"][0]["discoveryId"] == "disc::ip::unknown::10.0.0.2"


@pytest.mark.asyncio
async def test_status_lifecycle_pending_to_registered(
    mock_mongodb: MagicMock,
    mock_devices_collection: MagicMock,
    mock_nodes_collection: MagicMock,
    sample_device_with_classification: dict,
) -> None:
    """Full lifecycle: pending -> registered via approve with auto-register."""
    from hydra.api.v1.models.discovery.requests import ApproveDeviceRequest
    from hydra.api.v1.services.discovery.service import DiscoveryService

    service = DiscoveryService(mock_mongodb)
    mock_devices_collection.find_one = AsyncMock(
        return_value=sample_device_with_classification
    )
    mock_devices_collection.update_one = AsyncMock()
    mock_nodes_collection.insert_one = AsyncMock()

    request = ApproveDeviceRequest(auto_register=True)
    result = await service.approve_device(
        sample_device_with_classification["discoveryId"],
        request,
        "user_admin123",
        user_permissions=["*:*"],
    )

    assert result["status"] == "registered"
    assert result["matchedNodeId"] == "unknown-device"

    # Verify node was created
    mock_nodes_collection.insert_one.assert_awaited_once()
    node_doc = mock_nodes_collection.insert_one.call_args[0][0]
    assert node_doc["class"] == "compute"
    assert node_doc["type"] == "server"
    assert node_doc["registeredVia"] == "discovery"


@pytest.mark.asyncio
async def test_node_id_derived_from_hostname(
    mock_mongodb: MagicMock,
    mock_devices_collection: MagicMock,
    mock_nodes_collection: MagicMock,
) -> None:
    """Auto-generated nodeId uses hostname when available."""
    from hydra.api.v1.models.discovery.requests import ApproveDeviceRequest
    from hydra.api.v1.services.discovery.service import DiscoveryService

    service = DiscoveryService(mock_mongodb)
    now = datetime.now(UTC)

    device = {
        "discoveryId": "disc::mac::aa-bb-cc-dd-ee-f0",
        "identity": {
            "primaryMac": "aa:bb:cc:dd:ee:ff",
            "currentIp": "192.168.1.50",
            "hostname": "My_Server.Home",
        },
        "networkId": "net-192-168-1",
        "probe": {"scannedBy": "test", "method": "arp", "scannedAt": now.isoformat()},
        "status": "pending",
        "firstSeen": now,
        "lastSeen": now,
        "seenCount": 1,
        "openPorts": [],
        "protocols": [],
        "fingerprint": None,
        "classification": {"suggestedClass": "compute", "suggestedType": None, "confidence": 0.3, "signals": []},
        "dismissedAt": None,
        "dismissedBy": None,
        "dismissReason": None,
        "approvedAt": None,
        "approvedBy": None,
        "rejectedAt": None,
        "rejectedBy": None,
        "rejectReason": None,
        "matchedNodeId": None,
    }

    mock_devices_collection.find_one = AsyncMock(return_value=device)
    mock_devices_collection.update_one = AsyncMock()
    mock_nodes_collection.insert_one = AsyncMock()

    request = ApproveDeviceRequest(auto_register=True)
    result = await service.approve_device(
        "disc::mac::aa-bb-cc-dd-ee-f0",
        request,
        "user_admin123",
        user_permissions=["*:*"],
    )

    # Hostname "My_Server.Home" -> "my-server.home"
    assert result["matchedNodeId"] == "my-server.home"


@pytest.mark.asyncio
async def test_node_id_derived_from_ip_fallback(
    mock_mongodb: MagicMock,
    mock_devices_collection: MagicMock,
    mock_nodes_collection: MagicMock,
) -> None:
    """NodeId falls back to IP when hostname is absent."""
    from hydra.api.v1.models.discovery.requests import ApproveDeviceRequest
    from hydra.api.v1.services.discovery.service import DiscoveryService

    service = DiscoveryService(mock_mongodb)
    now = datetime.now(UTC)

    device = {
        "discoveryId": "disc::ip::unknown::10.0.0.5",
        "identity": {
            "primaryMac": None,
            "currentIp": "10.0.0.5",
            "hostname": None,
        },
        "networkId": None,
        "probe": {"scannedBy": "test", "method": "arp", "scannedAt": now.isoformat()},
        "status": "pending",
        "firstSeen": now,
        "lastSeen": now,
        "seenCount": 1,
        "openPorts": [],
        "protocols": [],
        "fingerprint": None,
        "classification": None,
        "dismissedAt": None,
        "dismissedBy": None,
        "dismissReason": None,
        "approvedAt": None,
        "approvedBy": None,
        "rejectedAt": None,
        "rejectedBy": None,
        "rejectReason": None,
        "matchedNodeId": None,
    }

    mock_devices_collection.find_one = AsyncMock(return_value=device)
    mock_devices_collection.update_one = AsyncMock()
    mock_nodes_collection.insert_one = AsyncMock()

    request = ApproveDeviceRequest(auto_register=True)
    result = await service.approve_device(
        "disc::ip::unknown::10.0.0.5",
        request,
        "user_admin123",
        user_permissions=["*:*"],
    )

    assert result["matchedNodeId"] == "disc-10-0-0-5"


@pytest.mark.asyncio
async def test_approve_device_with_tags(
    client: AsyncClient,
    mock_mongodb: MagicMock,
    mock_devices_collection: MagicMock,
    mock_nodes_collection: MagicMock,
    admin_token: str,
    sample_user: dict,
    sample_device: dict,
) -> None:
    """Approve with tags passes them to the node document."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_devices_collection.find_one = AsyncMock(return_value=sample_device)
    mock_devices_collection.update_one = AsyncMock()
    mock_nodes_collection.insert_one = AsyncMock()

    response = await client.post(
        f"/api/v1/discovery/devices/{sample_device['discoveryId']}/approve",
        json={"autoRegister": True, "tags": ["discovered", "lab"]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    node_doc = mock_nodes_collection.insert_one.call_args[0][0]
    assert node_doc["tags"] == ["discovered", "lab"]


@pytest.mark.asyncio
async def test_unknown_class_defaults_to_compute(
    mock_mongodb: MagicMock,
    mock_devices_collection: MagicMock,
    mock_nodes_collection: MagicMock,
) -> None:
    """When classification is 'unknown', node class defaults to 'compute'."""
    from hydra.api.v1.models.discovery.requests import ApproveDeviceRequest
    from hydra.api.v1.services.discovery.service import DiscoveryService

    service = DiscoveryService(mock_mongodb)
    now = datetime.now(UTC)

    device = {
        "discoveryId": "disc::ip::unknown::10.0.0.99",
        "identity": {"primaryMac": None, "currentIp": "10.0.0.1", "hostname": "mystery"},
        "networkId": None,
        "probe": {"scannedBy": "test", "method": "arp", "scannedAt": now.isoformat()},
        "status": "pending",
        "firstSeen": now,
        "lastSeen": now,
        "seenCount": 1,
        "openPorts": [],
        "protocols": [],
        "fingerprint": None,
        "classification": {"suggestedClass": "unknown", "suggestedType": None, "confidence": 0.0, "signals": []},
        "dismissedAt": None,
        "dismissedBy": None,
        "dismissReason": None,
        "approvedAt": None,
        "approvedBy": None,
        "rejectedAt": None,
        "rejectedBy": None,
        "rejectReason": None,
        "matchedNodeId": None,
    }

    mock_devices_collection.find_one = AsyncMock(return_value=device)
    mock_devices_collection.update_one = AsyncMock()
    mock_nodes_collection.insert_one = AsyncMock()

    request = ApproveDeviceRequest(auto_register=True)
    await service.approve_device(
        "disc::ip::unknown::10.0.0.99",
        request,
        "user_admin123",
        user_permissions=["*:*"],
    )

    node_doc = mock_nodes_collection.insert_one.call_args[0][0]
    assert node_doc["class"] == "compute"


# ── Discovery ID Generation Tests ─────────────────────────────────────


class TestDiscoveryIdGeneration:
    """Unit tests for spec-format discoveryId generation."""

    def test_mac_based_id(self) -> None:
        """MAC address produces disc::mac:: format with hyphen-separated lowercase."""
        from hydra.api.v1.services.discovery.service import generate_discovery_id

        result = generate_discovery_id("AA:BB:CC:DD:EE:FF", "net-1", "192.168.1.1")
        assert result == "disc::mac::aa-bb-cc-dd-ee-ff"

    def test_mac_based_id_already_hyphens(self) -> None:
        """MAC with hyphens is normalized correctly."""
        from hydra.api.v1.services.discovery.service import generate_discovery_id

        result = generate_discovery_id("aa-bb-cc-dd-ee-ff", None, None)
        assert result == "disc::mac::aa-bb-cc-dd-ee-ff"

    def test_ip_based_id_with_network(self) -> None:
        """No MAC falls back to disc::ip::{networkId}::{ip}."""
        from hydra.api.v1.services.discovery.service import generate_discovery_id

        result = generate_discovery_id(None, "home-lan", "192.168.1.50")
        assert result == "disc::ip::home-lan::192.168.1.50"

    def test_ip_based_id_without_network(self) -> None:
        """No MAC and no networkId uses 'unknown' network."""
        from hydra.api.v1.services.discovery.service import generate_discovery_id

        result = generate_discovery_id(None, None, "10.0.0.5")
        assert result == "disc::ip::unknown::10.0.0.5"

    def test_fallback_id(self) -> None:
        """No MAC and no IP produces a random fallback."""
        from hydra.api.v1.services.discovery.service import generate_discovery_id

        result = generate_discovery_id(None, None, None)
        assert result.startswith("disc::unknown::")


# ── Eligibility Assessment Tests ──────────────────────────────────────


class TestEligibilityAssessment:
    """Unit tests for eligibility assessment logic."""

    def setup_method(self) -> None:
        self.fp_service = FingerprintService()

    def test_compute_with_ssh_is_agent_compatible(self) -> None:
        """Compute device with SSH is agent-compatible and remote-installable."""
        fp = self.fp_service.fingerprint_device([22, 80, 443], [])
        cls = self.fp_service.classify_device(fp)
        from hydra.api.v1.services.discovery.eligibility import assess_eligibility

        elig = assess_eligibility(fp, cls, [22, 80, 443])
        assert elig.registerable is True
        assert elig.agent_compatible is True
        assert elig.remote_installable is True
        assert elig.remote_install_method == "ssh"
        assert elig.profiling_strategy == "agent"

    def test_compute_without_ssh_not_remote_installable(self) -> None:
        """Compute device without SSH is not remote-installable."""
        fp = self.fp_service.fingerprint_device([80, 443, 8080], [])
        cls = self.fp_service.classify_device(fp)
        from hydra.api.v1.services.discovery.eligibility import assess_eligibility

        elig = assess_eligibility(fp, cls, [80, 443, 8080])
        assert elig.agent_compatible is False
        assert elig.remote_installable is False

    def test_networking_device_uses_snmp_profiling(self) -> None:
        """Networking device with SNMP port uses SNMP profiling strategy."""
        fp = self.fp_service.fingerprint_device([161, 179], ["snmp"])
        cls = self.fp_service.classify_device(fp)
        from hydra.api.v1.services.discovery.eligibility import assess_eligibility

        elig = assess_eligibility(fp, cls, [161, 179])
        assert elig.registerable is True
        assert elig.agent_compatible is False
        assert elig.profiling_strategy == "snmp"

    def test_iot_device_uses_integration_profiling(self) -> None:
        """IoT device uses integration profiling strategy."""
        fp = self.fp_service.fingerprint_device([1883], [])
        cls = self.fp_service.classify_device(fp)
        from hydra.api.v1.services.discovery.eligibility import assess_eligibility

        elig = assess_eligibility(fp, cls, [1883])
        assert elig.registerable is True
        assert elig.agent_compatible is False
        assert elig.profiling_strategy == "integration"

    def test_ha_device_uses_homeassistant_profiling(self) -> None:
        """Home Assistant device uses homeassistant profiling strategy."""
        fp = self.fp_service.fingerprint_device([8123, 1883], [])
        cls = self.fp_service.classify_device(fp)
        from hydra.api.v1.services.discovery.eligibility import assess_eligibility

        elig = assess_eligibility(fp, cls, [8123, 1883])
        assert elig.profiling_strategy == "homeassistant"

    def test_unknown_device_not_registerable(self) -> None:
        """Unknown device is not registerable."""
        fp = self.fp_service.fingerprint_device([12345], [])
        cls = self.fp_service.classify_device(fp)
        from hydra.api.v1.services.discovery.eligibility import assess_eligibility

        elig = assess_eligibility(fp, cls, [12345])
        assert elig.registerable is False
        assert elig.profiling_strategy == "none"
        assert len(elig.blockers) > 0


# ── Exclusion Tests ───────────────────────────────────────────────────


class TestExclusionService:
    """Unit tests for exclusion rules."""

    @pytest.fixture(autouse=True)
    def _setup(
        self, mock_mongodb: MagicMock, mock_exclusions_collection: MagicMock,
    ) -> None:
        from hydra.api.v1.services.discovery.exclusions import ExclusionService

        self.service = ExclusionService(mock_mongodb)
        self.collection = mock_exclusions_collection

    @pytest.mark.asyncio
    async def test_create_mac_exclusion(self) -> None:
        """Creating a MAC exclusion normalizes the value to lowercase colon format."""
        from hydra.api.v1.models.discovery.requests import CreateExclusionRequest

        self.collection.insert_one = AsyncMock()

        request = CreateExclusionRequest(
            type="mac", value="AA-BB-CC-DD-EE-FF", label="Test device", reason="Personal",
        )
        result = await self.service.create_exclusion(request, "user_admin")

        assert result["type"] == "mac"
        assert result["value"] == "aa:bb:cc:dd:ee:ff"
        assert result["label"] == "Test device"
        self.collection.insert_one.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_is_excluded_by_mac(self) -> None:
        """MAC exclusion matches regardless of format."""
        self.collection.find.return_value.to_list = AsyncMock(
            return_value=[{"type": "mac", "value": "aa:bb:cc:dd:ee:ff"}]
        )
        assert await self.service.is_excluded("AA:BB:CC:DD:EE:FF", "192.168.1.1") is True
        assert await self.service.is_excluded("11:22:33:44:55:66", "192.168.1.1") is False

    @pytest.mark.asyncio
    async def test_is_excluded_by_ip(self) -> None:
        """IP exclusion matches exact IP."""
        self.collection.find.return_value.to_list = AsyncMock(
            return_value=[{"type": "ip", "value": "192.168.1.50"}]
        )
        assert await self.service.is_excluded(None, "192.168.1.50") is True
        assert await self.service.is_excluded(None, "192.168.1.51") is False

    @pytest.mark.asyncio
    async def test_is_excluded_by_ip_range(self) -> None:
        """IP range exclusion matches addresses within the range."""
        self.collection.find.return_value.to_list = AsyncMock(
            return_value=[{"type": "ip-range", "value": "192.168.1.200-192.168.1.254"}]
        )
        assert await self.service.is_excluded(None, "192.168.1.200") is True
        assert await self.service.is_excluded(None, "192.168.1.230") is True
        assert await self.service.is_excluded(None, "192.168.1.254") is True
        assert await self.service.is_excluded(None, "192.168.1.199") is False
        assert await self.service.is_excluded(None, "192.168.2.1") is False

    @pytest.mark.asyncio
    async def test_is_excluded_empty_rules(self) -> None:
        """No exclusion rules means nothing is excluded."""
        self.collection.find.return_value.to_list = AsyncMock(return_value=[])
        assert await self.service.is_excluded("aa:bb:cc:dd:ee:ff", "192.168.1.1") is False

    @pytest.mark.asyncio
    async def test_delete_exclusion(self) -> None:
        """Deleting an exclusion removes it from the collection."""
        self.collection.delete_one = AsyncMock(
            return_value=MagicMock(deleted_count=1)
        )
        await self.service.delete_exclusion("excl_abc123")
        self.collection.delete_one.assert_awaited_once_with(
            {"exclusionId": "excl_abc123"}
        )

    @pytest.mark.asyncio
    async def test_delete_exclusion_not_found(self) -> None:
        """Deleting a nonexistent exclusion raises NotFoundError."""
        from hydra.api.v1.services.discovery.exclusions import ExclusionNotFoundError

        self.collection.delete_one = AsyncMock(
            return_value=MagicMock(deleted_count=0)
        )
        with pytest.raises(ExclusionNotFoundError):
            await self.service.delete_exclusion("excl_nonexistent")


# ── Scan Diff Tests ───────────────────────────────────────────────────


class TestScanDiffComputation:
    """Unit tests for device change detection between scans."""

    def test_ip_change_detected(self) -> None:
        """IP address change between scans is detected."""
        from hydra.api.v1.services.discovery.service import DiscoveryService

        old = {"identity": {"currentIp": "192.168.1.10", "hostname": "dev"}, "openPorts": [22]}
        new = {"identity": {"currentIp": "192.168.1.20", "hostname": "dev"}, "openPorts": [22]}
        changes = DiscoveryService._compute_device_changes(old, new)
        assert len(changes) == 1
        assert changes[0]["field"] == "ip"
        assert changes[0]["from"] == "192.168.1.10"
        assert changes[0]["to"] == "192.168.1.20"

    def test_port_change_detected(self) -> None:
        """Added/removed ports between scans are detected."""
        from hydra.api.v1.services.discovery.service import DiscoveryService

        old = {"identity": {"currentIp": "10.0.0.1"}, "openPorts": [22, 80]}
        new = {"identity": {"currentIp": "10.0.0.1"}, "openPorts": [22, 443]}
        changes = DiscoveryService._compute_device_changes(old, new)
        port_change = next(c for c in changes if c["field"] == "openPorts")
        assert 443 in port_change["from"]["added"]
        assert 80 in port_change["from"]["removed"]

    def test_no_changes(self) -> None:
        """Identical devices produce no changes."""
        from hydra.api.v1.services.discovery.service import DiscoveryService

        device = {
            "identity": {"currentIp": "10.0.0.1", "hostname": "dev"},
            "openPorts": [22, 80],
            "classification": {"suggestedClass": "compute"},
        }
        changes = DiscoveryService._compute_device_changes(device, device)
        assert len(changes) == 0

    def test_class_change_detected(self) -> None:
        """Classification change between scans is detected."""
        from hydra.api.v1.services.discovery.service import DiscoveryService

        old = {"identity": {"currentIp": "10.0.0.1"}, "openPorts": [], "classification": {"suggestedClass": "unknown"}}
        new = {"identity": {"currentIp": "10.0.0.1"}, "openPorts": [], "classification": {"suggestedClass": "compute"}}
        changes = DiscoveryService._compute_device_changes(old, new)
        assert any(c["field"] == "suggestedClass" for c in changes)


# ── Wave 2 Tests ──────────────────────────────────────────────────


class TestScannerModule:
    """Tests for the API-direct TCP scanner."""

    @pytest.mark.asyncio
    async def test_scan_subnet_returns_alive_hosts(self, monkeypatch: pytest.MonkeyPatch):
        """Verify scan_subnet returns hosts with open ports."""
        from hydra.api.v1.services.discovery import scanner

        # Mock _scan_host to simulate finding two hosts
        async def mock_scan_host(host, ports, timeout, semaphore):
            if host == "192.168.1.1":
                return {"ip": "192.168.1.1", "openPorts": [22, 80]}
            if host == "192.168.1.2":
                return {"ip": "192.168.1.2", "openPorts": [443]}
            return None

        monkeypatch.setattr(scanner, "_scan_host", mock_scan_host)

        results = await scanner.scan_subnet("192.168.1.0/30", port_tier="tier1")
        assert len(results) == 2
        assert results[0]["ip"] == "192.168.1.1"
        assert 22 in results[0]["openPorts"]
        assert results[1]["ip"] == "192.168.1.2"

    @pytest.mark.asyncio
    async def test_scan_subnet_empty_returns_no_hosts(self, monkeypatch: pytest.MonkeyPatch):
        """Verify scan_subnet returns empty list when no hosts are alive."""
        from hydra.api.v1.services.discovery import scanner

        async def mock_scan_host(host, ports, timeout, semaphore):
            return None

        monkeypatch.setattr(scanner, "_scan_host", mock_scan_host)

        results = await scanner.scan_subnet("192.168.1.0/30")
        assert results == []

    def test_port_lists_match_spec(self):
        """Verify tier1 and tier2 port lists have spec-level coverage."""
        from hydra.api.v1.services.discovery.scanner import TIER1_PORTS, TIER2_PORTS

        assert len(TIER1_PORTS) >= 20  # spec requires ~20 tier1
        assert len(TIER2_PORTS) >= 50  # spec requires +60 tier2
        # Key ports must be in tier1
        assert 22 in TIER1_PORTS  # SSH
        assert 80 in TIER1_PORTS  # HTTP
        assert 443 in TIER1_PORTS  # HTTPS
        assert 8006 in TIER1_PORTS  # Proxmox
        assert 8123 in TIER1_PORTS  # Home Assistant


class TestRegisterService:
    """Tests for the register_device service method."""

    @pytest.mark.asyncio
    async def test_register_device_creates_node(self):
        """Verify register_device creates a node and returns spec-aligned response."""
        from hydra.api.v1.models.discovery.requests import RegisterDeviceRequest
        from hydra.api.v1.services.discovery.service import DiscoveryService

        discovery_id = "disc::mac::aa-bb-cc-dd-ee-ff"
        device_doc = {
            "discoveryId": discovery_id,
            "status": "pending",
            "identity": {
                "primaryMac": "aa:bb:cc:dd:ee:ff",
                "currentIp": "192.168.1.100",
                "hostname": "test-server",
            },
            "networkId": "net-lan",
            "classification": {
                "suggestedClass": "compute",
                "suggestedType": "server",
                "suggestedKind": "generic",
                "suggestedNodeId": "test-server",
                "suggestedDisplayName": "Test Server",
                "confidence": 0.8,
                "explanation": "Port-based classification",
            },
            "openPorts": [22, 80],
            "protocols": [],
            "probe": {"scannedBy": "api", "scannedAt": "2026-04-15T00:00:00Z"},
            "firstSeen": "2026-04-15T00:00:00Z",
            "lastSeen": "2026-04-15T00:00:00Z",
            "seenCount": 1,
            "matchedNodeId": None,
        }

        mock_devices = create_mock_collection()
        mock_devices.find_one = AsyncMock(return_value=device_doc)
        mock_devices.update_one = AsyncMock()
        mock_nodes = create_mock_collection()
        mock_nodes.find_one = AsyncMock(return_value=None)
        mock_nodes.insert_one = AsyncMock()
        mock_docs = MagicMock(spec=DocsService)
        mock_docs.refresh_documents_for_entities = AsyncMock()

        service = DiscoveryService.__new__(DiscoveryService)
        service.devices = mock_devices
        service.nodes = mock_nodes
        service.docs = mock_docs

        request = RegisterDeviceRequest(
            display_name="My Test Server",
            tags=["datacenter"],
        )

        result = await service.register_device(discovery_id, request, user_id="user_admin")

        assert result["nodeId"] == "test-server"
        assert result["status"] == "registered"
        assert result["fromDiscovery"] == discovery_id
        assert "registeredAt" in result
        assert result["registeredBy"] == "user_admin"

        # Verify node was inserted
        mock_nodes.insert_one.assert_called_once()
        inserted = mock_nodes.insert_one.call_args.args[0]
        assert inserted["nodeId"] == "test-server"
        assert inserted["displayName"] == "My Test Server"
        assert inserted["tags"] == ["datacenter"]
        assert inserted["registeredVia"] == "discovery"

    @pytest.mark.asyncio
    async def test_register_rejects_non_pending_device(self):
        """Verify register_device rejects already-registered devices."""
        from hydra.api.v1.models.discovery.requests import RegisterDeviceRequest
        from hydra.api.v1.services.discovery.service import DiscoveryService

        device_doc = {
            "discoveryId": "disc::mac::aa-bb-cc-dd-ee-ff",
            "status": "registered",
            "identity": {"primaryMac": "aa:bb:cc:dd:ee:ff", "currentIp": "10.0.0.1"},
            "matchedNodeId": "existing-node",
        }

        mock_devices = create_mock_collection()
        mock_devices.find_one = AsyncMock(return_value=device_doc)

        service = DiscoveryService.__new__(DiscoveryService)
        service.devices = mock_devices

        request = RegisterDeviceRequest()

        from hydra.api.v1.services.discovery.service import DiscoveryNotPendingError

        with pytest.raises(DiscoveryNotPendingError):
            await service.register_device(
                "disc::mac::aa-bb-cc-dd-ee-ff",
                request,
                user_id="user_admin",
            )


class TestDriftDetection:
    """Tests for post-registration drift detection."""

    @pytest.mark.asyncio
    async def test_check_drift_detects_class_change(self):
        """Verify check_drift generates a report when classification changes."""
        from hydra.api.v1.services.discovery.service import DiscoveryService

        mock_db = MagicMock()
        mock_nodes = create_mock_collection()
        mock_nodes.find_one = AsyncMock(return_value={
            "nodeId": "test-node",
            "lastProfileAt": None,  # No agent profile — allow drift check
        })
        mock_db.db = {
            "nodes": mock_nodes,
            "discovery_drift": create_mock_collection(),
        }
        mock_db.db["discovery_drift"].insert_one = AsyncMock()

        service = DiscoveryService.__new__(DiscoveryService)
        service.nodes = mock_nodes
        service.db = mock_db

        device = {
            "discoveryId": "disc::mac::aa-bb-cc-dd-ee-ff",
            "matchedNodeId": "test-node",
            "classification": {"suggestedClass": "networking"},
            "_previousClassification": "compute",
        }

        result = await service.check_drift("disc::mac::aa-bb-cc-dd-ee-ff", device)

        assert result is not None
        assert result["severity"] == "warning"
        assert result["previousClassification"] == "compute"
        assert result["currentClassification"] == "networking"
        assert len(result["changes"]) == 1

    @pytest.mark.asyncio
    async def test_check_drift_skips_compute_with_agent(self):
        """Verify drift check is skipped for compute nodes with active agent."""
        from hydra.api.v1.services.discovery.service import DiscoveryService

        mock_nodes = create_mock_collection()
        mock_nodes.find_one = AsyncMock(return_value={
            "nodeId": "test-node",
            "lastProfileAt": datetime.now(UTC),  # Has agent profile
        })

        service = DiscoveryService.__new__(DiscoveryService)
        service.nodes = mock_nodes

        device = {
            "discoveryId": "disc::mac::aa-bb-cc-dd-ee-ff",
            "matchedNodeId": "test-node",
            "classification": {"suggestedClass": "compute"},
            "_previousClassification": "unknown",
        }

        result = await service.check_drift("disc::mac::aa-bb-cc-dd-ee-ff", device)
        assert result is None  # Should skip — compute with agent

    @pytest.mark.asyncio
    async def test_check_drift_no_drift_when_same_class(self):
        """Verify no drift report when classification hasn't changed."""
        from hydra.api.v1.services.discovery.service import DiscoveryService

        mock_nodes = create_mock_collection()
        mock_nodes.find_one = AsyncMock(return_value={
            "nodeId": "test-node",
            "lastProfileAt": None,
        })

        service = DiscoveryService.__new__(DiscoveryService)
        service.nodes = mock_nodes

        device = {
            "discoveryId": "disc::mac::aa-bb-cc-dd-ee-ff",
            "matchedNodeId": "test-node",
            "classification": {"suggestedClass": "iot"},
            "_previousClassification": "iot",
        }

        result = await service.check_drift("disc::mac::aa-bb-cc-dd-ee-ff", device)
        assert result is None


class TestScanConfigEndpoint:
    """Tests for the PATCH /networks/{id}/scan-config endpoint."""

    @pytest.mark.asyncio
    async def test_update_scan_config_sets_status(self):
        """Verify update_scan_config persists status and guidance."""
        from hydra.api.v1.models.networks import UpdateScanConfigRequest
        from hydra.api.v1.services.networks import NetworksService

        mock_db = MagicMock()
        mock_networks = create_mock_collection()
        mock_networks.find_one = AsyncMock(return_value={
            "networkId": "net-lan",
            "type": "physical",
            "name": "LAN",
            "scanConfig": {"status": "unreachable"},
            "origin": {"createdBy": "manual"},
            "tags": [],
            "createdAt": datetime.now(UTC),
            "updatedAt": datetime.now(UTC),
        })
        mock_networks.update_one = AsyncMock()
        mock_db.networks = mock_networks
        mock_db.nodes = create_mock_collection()

        service = NetworksService(mock_db)

        request = UpdateScanConfigRequest(
            status="agent-only",
            delegate_agent_node_ids=None,
            user_guidance="Use node-01 to scan this network",
        )

        await service.update_scan_config("net-lan", request)

        mock_networks.update_one.assert_called_once()
        update_args = mock_networks.update_one.call_args
        set_fields = update_args.args[1]["$set"]
        assert set_fields["scanConfig.status"] == "agent-only"
        assert set_fields["scanConfig.userGuidance"] == "Use node-01 to scan this network"
