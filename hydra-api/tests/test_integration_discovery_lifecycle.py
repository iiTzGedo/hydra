"""Cross-feature integration tests for the discovery lifecycle.

Tests the full flow: scan -> fingerprint -> approve -> install -> profile -> topology.
Each test exercises router endpoints via HTTP, not service functions directly.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from hydra.api.v1.main import app as v1_app
from hydra.api.v1.routers.discovery import router as discovery_router
from hydra.api.v1.routers.installations import router as installations_router
from hydra.api.v1.services.docs import DocsService
from tests.conftest import create_mock_collection

# Ensure routers are registered on the v1 app for test client access.
_registered = False
if not _registered:
    v1_app.include_router(discovery_router)
    v1_app.include_router(installations_router)
    _registered = True


# ── Fixtures ───────────────────────────────────────────────────────────


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
def mock_installations_collection():
    """Create a mock installations collection."""
    return create_mock_collection()


@pytest.fixture(autouse=True)
def _patch_collections(
    mock_mongodb,
    mock_scans_collection,
    mock_devices_collection,
    mock_nodes_collection,
    mock_installations_collection,
):
    """Patch mock_mongodb.db to return discovery/installation collections."""
    mock_db = MagicMock()

    def _getitem(name: str) -> MagicMock:
        if name == "discovery_scans":
            return mock_scans_collection
        if name == "discovered_nodes":
            return mock_devices_collection
        if name == "nodes":
            return mock_nodes_collection
        if name == "installations":
            return mock_installations_collection
        return create_mock_collection()

    mock_db.__getitem__ = MagicMock(side_effect=_getitem)
    mock_mongodb.db = mock_db


@pytest.fixture
def admin_user(sample_user):
    """Admin user document matching the admin_token subject."""
    return {**sample_user, "userId": "user_admin123", "role": "admin"}


@pytest.fixture
def _mock_admin(mock_mongodb, admin_user):
    """Set up the admin user lookup used by permission checks."""
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)


@pytest.fixture
def auth_headers(admin_token):
    """Authorization header dict for admin requests."""
    return {"Authorization": f"Bearer {admin_token}"}


def _make_scan_result_device(
    ip: str,
    mac: str,
    hostname: str | None = None,
    open_ports: list[int] | None = None,
    protocols: list[str] | None = None,
) -> dict:
    """Build a scan result device payload matching ScanResultDevice schema."""
    return {
        "identity": {
            "primaryMac": mac,
            "currentIp": ip,
            "hostname": hostname,
        },
        "networkId": "net-192-168-1",
        "probe": {
            "scannedBy": "test-server-01",
            "method": "arp",
            "scannedAt": datetime.now(UTC).isoformat(),
            "sourceSubnet": "192.168.1.0/24",
        },
        "openPorts": open_ports or [],
        "protocols": protocols or [],
    }


def _make_scan_summary(
    hosts_scanned: int = 254,
    hosts_alive: int = 3,
    new_discoveries: int = 3,
    returning_devices: int = 0,
) -> dict:
    """Build a ScanResultSummary payload."""
    return {
        "hostsScanned": hosts_scanned,
        "hostsAlive": hosts_alive,
        "newDiscoveries": new_discoveries,
        "returningDevices": returning_devices,
        "errors": [],
    }


# ── Test 1: Scan Creation and Result Submission ─────────────────────


@pytest.mark.asyncio
@pytest.mark.usefixtures("_mock_admin")
async def test_scan_creation_and_result_submission(
    client: AsyncClient,
    mock_scans_collection: MagicMock,
    mock_devices_collection: MagicMock,
    auth_headers: dict,
):
    """Create a scan via POST /discovery/scans, then submit scan results
    with 3 discovered devices. Verify scan status transitions and devices
    are stored."""
    # Step 1: Create a scan (non-delegated -> starts as running)
    mock_scans_collection.insert_one = AsyncMock()

    response = await client.post(
        "/api/v1/discovery/scans",
        json={"targets": [{"subnet": "192.168.1.0/24"}]},
        headers=auth_headers,
    )

    assert response.status_code == 201
    scan_data = response.json()["data"]
    assert scan_data["scanId"].startswith("scan_")
    assert scan_data["status"] == "running"
    scan_id = scan_data["scanId"]

    # Step 2: Submit results for the scan
    # Mock the scan lookup so submit_scan_results finds the running scan
    now = datetime.now(UTC)
    running_scan = {
        "scanId": scan_id,
        "status": "running",
        "targets": [{"subnet": "192.168.1.0/24", "networkId": None, "delegateToNodeId": None}],
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

    completed_scan = {
        **running_scan,
        "status": "completed",
        "resultCount": 3,
        "summary": _make_scan_summary(),
        "progress": {
            "phase": "completed",
            "hostsTotal": 254,
            "hostsScanned": 254,
            "hostsAlive": 3,
            "percentComplete": 100.0,
        },
        "completedAt": now,
    }

    # First call returns running scan (for get_scan validation),
    # subsequent calls return completed scan (after update)
    mock_scans_collection.find_one = AsyncMock(
        side_effect=[running_scan, completed_scan]
    )
    mock_scans_collection.update_one = AsyncMock()
    mock_devices_collection.find_one = AsyncMock(return_value=None)
    mock_devices_collection.insert_one = AsyncMock()

    devices = [
        _make_scan_result_device("192.168.1.10", "aa:bb:cc:dd:ee:01", "device-a"),
        _make_scan_result_device("192.168.1.11", "aa:bb:cc:dd:ee:02", "device-b"),
        _make_scan_result_device("192.168.1.12", "aa:bb:cc:dd:ee:03", "device-c"),
    ]

    response = await client.post(
        f"/api/v1/discovery/scans/{scan_id}/results",
        json={
            "results": devices,
            "summary": _make_scan_summary(),
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    result_data = response.json()["data"]
    assert result_data["status"] == "completed"
    assert result_data["resultCount"] == 3

    # Verify 3 devices were inserted
    assert mock_devices_collection.insert_one.await_count == 3


# ── Test 2: Device Fingerprinting on Result Submission ──────────────


@pytest.mark.asyncio
@pytest.mark.usefixtures("_mock_admin")
async def test_device_fingerprinting_on_result_submission(
    client: AsyncClient,
    mock_scans_collection: MagicMock,
    mock_devices_collection: MagicMock,
    auth_headers: dict,
):
    """Submit scan results and verify fingerprinting enrichment is applied
    (OUI lookup, classification, confidence scoring)."""
    now = datetime.now(UTC)
    scan_id = "scan_fingerprint_test"

    running_scan = {
        "scanId": scan_id,
        "status": "running",
        "targets": [{"subnet": "192.168.1.0/24", "networkId": None, "delegateToNodeId": None}],
        "options": {
            "methods": ["arp"],
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

    completed_scan = {
        **running_scan,
        "status": "completed",
        "resultCount": 1,
        "summary": _make_scan_summary(hosts_alive=1, new_discoveries=1),
        "progress": {
            "phase": "completed",
            "hostsTotal": 254,
            "hostsScanned": 254,
            "hostsAlive": 1,
            "percentComplete": 100.0,
        },
    }

    mock_scans_collection.find_one = AsyncMock(
        side_effect=[running_scan, completed_scan]
    )
    mock_scans_collection.update_one = AsyncMock()

    # Device with open ports that trigger fingerprinting
    device_with_ports = _make_scan_result_device(
        "192.168.1.42",
        "aa:bb:cc:dd:ee:ff",
        "nas-server",
        open_ports=[22, 80, 443],
        protocols=["ssh", "http", "https"],
    )

    # The _upsert_device path: no existing device -> insert new then enrich
    new_discovery_id = "disc_new_fingerprint"

    # find_one returns None (no existing device), then the newly inserted device
    # for enrichment lookup
    inserted_device = {
        "discoveryId": new_discovery_id,
        "identity": device_with_ports["identity"],
        "networkId": "net-192-168-1",
        "probe": device_with_ports["probe"],
        "status": "pending",
        "firstSeen": now,
        "lastSeen": now,
        "seenCount": 1,
        "openPorts": [22, 80, 443],
        "protocols": ["ssh", "http", "https"],
        "rawEvidence": None,
        "fingerprint": None,
        "classification": None,
    }

    # find_one calls: 1) MAC match (None), 2) enrich_discovery lookup
    mock_devices_collection.find_one = AsyncMock(
        side_effect=[None, inserted_device]
    )
    mock_devices_collection.insert_one = AsyncMock()
    mock_devices_collection.update_one = AsyncMock()

    response = await client.post(
        f"/api/v1/discovery/scans/{scan_id}/results",
        json={
            "results": [device_with_ports],
            "summary": _make_scan_summary(hosts_alive=1, new_discoveries=1),
        },
        headers=auth_headers,
    )

    assert response.status_code == 200

    # Verify insert was called for the new device
    mock_devices_collection.insert_one.assert_awaited_once()

    # Verify enrichment update was called (fingerprint + classification)
    enrich_calls = [
        c for c in mock_devices_collection.update_one.await_args_list
        if any(
            "fingerprint" in str(arg) for arg in c.args
        )
    ]
    assert len(enrich_calls) >= 1, "Expected at least one enrichment update_one call"

    # Verify the fingerprint data includes service hints
    enrich_update = enrich_calls[0].args[1]["$set"]
    assert "fingerprint" in enrich_update
    assert "classification" in enrich_update
    fingerprint = enrich_update["fingerprint"]
    assert 22 in fingerprint["portNumbers"]
    assert 80 in fingerprint["portNumbers"]

    classification = enrich_update["classification"]
    assert "suggestedClass" in classification
    assert 0.0 <= classification["confidence"] <= 1.0


# ── Test 3: Device Approval Creates Node ────────────────────────────


@pytest.mark.asyncio
@pytest.mark.usefixtures("_mock_admin")
async def test_device_approval_creates_node(
    client: AsyncClient,
    mock_devices_collection: MagicMock,
    mock_nodes_collection: MagicMock,
    auth_headers: dict,
    monkeypatch,
):
    """Approve a discovered device via POST /discovery/devices/{id}/approve.
    Verify a node record is created in the nodes collection."""
    now = datetime.now(UTC)
    discovery_id = "disc_approve_test_001"

    pending_device = {
        "discoveryId": discovery_id,
        "identity": {
            "primaryMac": "aa:bb:cc:11:22:33",
            "currentIp": "192.168.1.50",
            "hostname": "my-nas",
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
        "rawEvidence": None,
        "fingerprint": {
            "openPorts": [22, 80],
            "serviceHints": ["ssh", "http"],
            "protocols": [],
            "osHint": "linux",
        },
        "classification": {
            "suggestedClass": "compute",
            "suggestedType": "server",
            "confidence": 0.85,
            "signals": ["ssh", "http"],
        },
        "matchedNodeId": None,
    }

    mock_devices_collection.find_one = AsyncMock(return_value=pending_device)
    mock_devices_collection.update_one = AsyncMock()
    mock_nodes_collection.find_one = AsyncMock(return_value=None)  # No collision
    mock_nodes_collection.insert_one = AsyncMock()

    # Stub DocsService to avoid real doc refresh
    monkeypatch.setattr(
        DocsService, "refresh_documents_for_entities", AsyncMock(return_value={})
    )

    response = await client.post(
        f"/api/v1/discovery/devices/{discovery_id}/approve",
        json={"autoRegister": True},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["discoveryId"] == discovery_id
    assert data["status"] == "registered"
    assert data["matchedNodeId"] is not None

    # Verify node was created
    mock_nodes_collection.insert_one.assert_awaited_once()
    node_doc = mock_nodes_collection.insert_one.call_args[0][0]
    assert node_doc["nodeId"] == "my-nas"
    assert node_doc["class"] == "compute"
    assert node_doc["status"] == "active"
    assert node_doc["registeredVia"] == "discovery"
    assert "net-192-168-1" in node_doc["networkIds"]

    # Verify device status was updated to registered
    mock_devices_collection.update_one.assert_awaited()
    update_call = mock_devices_collection.update_one.call_args
    set_payload = update_call.args[1]["$set"]
    assert set_payload["status"] == "registered"
    assert set_payload["matchedNodeId"] == "my-nas"


# ── Test 4: Device Rejection ───────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.usefixtures("_mock_admin")
async def test_device_rejection(
    client: AsyncClient,
    mock_devices_collection: MagicMock,
    mock_nodes_collection: MagicMock,
    auth_headers: dict,
):
    """Reject a discovered device. Verify status changes to 'rejected'
    and no node is created."""
    now = datetime.now(UTC)
    discovery_id = "disc_reject_test_001"

    pending_device = {
        "discoveryId": discovery_id,
        "identity": {
            "primaryMac": "ff:ee:dd:cc:bb:aa",
            "currentIp": "192.168.1.99",
            "hostname": "unknown-printer",
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
        "openPorts": [9100],
        "protocols": [],
        "rawEvidence": None,
        "fingerprint": None,
        "classification": None,
        "matchedNodeId": None,
    }

    mock_devices_collection.find_one = AsyncMock(return_value=pending_device)
    mock_devices_collection.update_one = AsyncMock()

    response = await client.post(
        f"/api/v1/discovery/devices/{discovery_id}/reject",
        json={"reason": "Not managed infrastructure"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["discoveryId"] == discovery_id
    assert data["status"] == "rejected"
    assert data["matchedNodeId"] is None

    # Verify no node was created
    mock_nodes_collection.insert_one.assert_not_awaited()

    # Verify update was called with rejected status
    mock_devices_collection.update_one.assert_awaited_once()
    update_args = mock_devices_collection.update_one.call_args.args
    set_payload = update_args[1]["$set"]
    assert set_payload["status"] == "rejected"
    assert set_payload["rejectReason"] == "Not managed infrastructure"


# ── Test 5: Bulk Approve and Reject ────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.usefixtures("_mock_admin")
async def test_bulk_approve_and_reject(
    client: AsyncClient,
    mock_devices_collection: MagicMock,
    mock_nodes_collection: MagicMock,
    auth_headers: dict,
    monkeypatch,
):
    """Submit results with 4 devices, bulk approve 2, bulk reject 2.
    Verify correct status for each."""
    now = datetime.now(UTC)

    # Stub DocsService to avoid real doc refresh
    monkeypatch.setattr(
        DocsService, "refresh_documents_for_entities", AsyncMock(return_value={})
    )

    # Create 4 pending device documents
    devices = {}
    for i in range(4):
        disc_id = f"disc_bulk_{i:03d}"
        devices[disc_id] = {
            "discoveryId": disc_id,
            "identity": {
                "primaryMac": f"aa:bb:cc:dd:ee:{i:02x}",
                "currentIp": f"192.168.1.{10 + i}",
                "hostname": f"device-{i}",
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
            "openPorts": [22],
            "protocols": ["ssh"],
            "rawEvidence": None,
            "fingerprint": {
                "openPorts": [22],
                "serviceHints": ["ssh"],
                "protocols": [],
                "osHint": "linux",
            },
            "classification": {
                "suggestedClass": "compute",
                "suggestedType": "virtual",
                "confidence": 0.75,
                "signals": ["ssh"],
            },
            "matchedNodeId": None,
        }

    approve_ids = ["disc_bulk_000", "disc_bulk_001"]
    reject_ids = ["disc_bulk_002", "disc_bulk_003"]

    # For bulk approve: each device is looked up via find_one
    mock_devices_collection.find_one = AsyncMock(
        side_effect=lambda query: devices.get(query.get("discoveryId"))
    )
    mock_devices_collection.update_one = AsyncMock()
    mock_nodes_collection.find_one = AsyncMock(return_value=None)  # No collision
    mock_nodes_collection.insert_one = AsyncMock()

    # Bulk approve 2 devices
    response = await client.post(
        "/api/v1/discovery/devices/bulk-approve",
        json={"discoveryIds": approve_ids, "autoRegister": True},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["processed"] == 2
    assert data["succeeded"] == 2
    assert data["failed"] == 0

    for result in data["results"]:
        assert result["status"] == "registered"
        assert result["matchedNodeId"] is not None

    # Bulk reject 2 devices
    response = await client.post(
        "/api/v1/discovery/devices/bulk-reject",
        json={
            "discoveryIds": reject_ids,
            "reason": "Not needed",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["processed"] == 2
    assert data["succeeded"] == 2
    assert data["failed"] == 0

    for result in data["results"]:
        assert result["status"] == "rejected"
        assert result["matchedNodeId"] is None


# ── Test 6: Approval to Installation Trigger ───────────────────────


@pytest.mark.asyncio
@pytest.mark.usefixtures("_mock_admin")
async def test_approval_to_installation_trigger(
    client: AsyncClient,
    mock_devices_collection: MagicMock,
    mock_nodes_collection: MagicMock,
    mock_installations_collection: MagicMock,
    auth_headers: dict,
    monkeypatch,
):
    """Approve a device, then trigger SSH installation for the resulting node.
    Verify installation record is created with correct phases."""
    now = datetime.now(UTC)
    discovery_id = "disc_install_test_001"

    # Stub DocsService
    monkeypatch.setattr(
        DocsService, "refresh_documents_for_entities", AsyncMock(return_value={})
    )

    # Step 1: Approve the device
    pending_device = {
        "discoveryId": discovery_id,
        "identity": {
            "primaryMac": "11:22:33:44:55:66",
            "currentIp": "192.168.1.75",
            "hostname": "new-server",
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
        "openPorts": [22],
        "protocols": ["ssh"],
        "rawEvidence": None,
        "fingerprint": {
            "openPorts": [22],
            "serviceHints": ["ssh"],
            "protocols": [],
            "osHint": "linux",
        },
        "classification": {
            "suggestedClass": "compute",
            "suggestedType": "virtual",
            "confidence": 0.9,
            "signals": ["ssh"],
        },
        "matchedNodeId": None,
    }

    mock_devices_collection.find_one = AsyncMock(return_value=pending_device)
    mock_devices_collection.update_one = AsyncMock()
    mock_nodes_collection.find_one = AsyncMock(return_value=None)
    mock_nodes_collection.insert_one = AsyncMock()

    approve_resp = await client.post(
        f"/api/v1/discovery/devices/{discovery_id}/approve",
        json={"autoRegister": True},
        headers=auth_headers,
    )

    assert approve_resp.status_code == 200
    approve_data = approve_resp.json()["data"]
    assert approve_data["status"] == "registered"
    assert approve_data["matchedNodeId"] == "new-server"

    # Step 2: Trigger installation via POST /installations
    # The installation service will look up the discovered device by discoveryId
    mock_devices_collection.find_one = AsyncMock(return_value={
        **pending_device,
        "status": "registered",
        "matchedNodeId": "new-server",
    })
    mock_installations_collection.insert_one = AsyncMock()

    # Mock the find_one for the installation get after creation
    install_doc = {
        "installationId": "inst_test_001",
        "discoveryId": discovery_id,
        "targetIp": "192.168.1.75",
        "targetHostname": "new-server",
        "status": "pending",
        "progress": {
            "phase": "pending",
            "percentComplete": 0,
            "message": "Installation queued",
            "startedAt": None,
            "updatedAt": now,
        },
        "nodeId": None,
        "error": None,
        "agentTier": "normal",
        "tags": [],
        "createdBy": "user_admin123",
        "createdAt": now,
        "updatedAt": now,
        "completedAt": None,
    }
    mock_installations_collection.find_one = AsyncMock(return_value=install_doc)

    install_resp = await client.post(
        "/api/v1/installations",
        json={
            "discoveryId": discovery_id,
            "credentials": {
                "host": "192.168.1.75",
                "username": "root",
                "password": "test-password",
            },
            "agentTier": "normal",
        },
        headers=auth_headers,
    )

    assert install_resp.status_code == 201
    install_data = install_resp.json()["data"]
    assert install_data["installationId"].startswith("inst_")
    assert install_data["discoveryId"] == discovery_id
    assert install_data["targetIp"] == "192.168.1.75"
    assert install_data["status"] == "pending"
    assert install_data["agentTier"] == "normal"
    assert install_data["progress"]["phase"] == "pending"
    assert install_data["progress"]["percentComplete"] == 0

    # Verify installation record was persisted
    mock_installations_collection.insert_one.assert_awaited_once()


# ── Test 7: Rediscovery Idempotency ────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.usefixtures("_mock_admin")
async def test_rediscovery_idempotency(
    client: AsyncClient,
    mock_scans_collection: MagicMock,
    mock_devices_collection: MagicMock,
    auth_headers: dict,
):
    """Submit scan results twice for the same subnet. Verify devices are
    upserted (not duplicated) on second submission."""
    now = datetime.now(UTC)
    scan_id = "scan_idempotency_test"

    running_scan = {
        "scanId": scan_id,
        "status": "running",
        "targets": [{"subnet": "192.168.1.0/24", "networkId": None, "delegateToNodeId": None}],
        "options": {
            "methods": ["arp"],
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

    completed_scan = {
        **running_scan,
        "status": "completed",
        "resultCount": 2,
        "summary": _make_scan_summary(hosts_alive=2, new_discoveries=2),
        "progress": {
            "phase": "completed",
            "hostsTotal": 254,
            "hostsScanned": 254,
            "hostsAlive": 2,
            "percentComplete": 100.0,
        },
    }

    devices = [
        _make_scan_result_device("192.168.1.20", "aa:bb:cc:00:00:01", "server-a", [22], ["ssh"]),
        _make_scan_result_device("192.168.1.21", "aa:bb:cc:00:00:02", "server-b", [80], ["http"]),
    ]

    # First submission: no existing devices
    mock_scans_collection.find_one = AsyncMock(
        side_effect=[running_scan, completed_scan]
    )
    mock_scans_collection.update_one = AsyncMock()
    mock_devices_collection.find_one = AsyncMock(return_value=None)
    mock_devices_collection.insert_one = AsyncMock()
    mock_devices_collection.update_one = AsyncMock()

    response1 = await client.post(
        f"/api/v1/discovery/scans/{scan_id}/results",
        json={
            "results": devices,
            "summary": _make_scan_summary(hosts_alive=2, new_discoveries=2),
        },
        headers=auth_headers,
    )

    assert response1.status_code == 200
    # Two new inserts for two new devices
    assert mock_devices_collection.insert_one.await_count == 2

    # Second submission: devices now exist
    existing_device_a = {
        "discoveryId": "disc_existing_a",
        "identity": {"primaryMac": "aa:bb:cc:00:00:01", "currentIp": "192.168.1.20", "hostname": "server-a"},
        "networkId": "net-192-168-1",
        "status": "pending",
        "firstSeen": now,
        "lastSeen": now,
        "seenCount": 1,
        "openPorts": [22],
        "protocols": ["ssh"],
        "rawEvidence": None,
    }
    existing_device_b = {
        "discoveryId": "disc_existing_b",
        "identity": {"primaryMac": "aa:bb:cc:00:00:02", "currentIp": "192.168.1.21", "hostname": "server-b"},
        "networkId": "net-192-168-1",
        "status": "pending",
        "firstSeen": now,
        "lastSeen": now,
        "seenCount": 1,
        "openPorts": [80],
        "protocols": ["http"],
        "rawEvidence": None,
    }

    scan_id_2 = "scan_idempotency_test_2"
    running_scan_2 = {**running_scan, "scanId": scan_id_2}
    completed_scan_2 = {**completed_scan, "scanId": scan_id_2, "resultCount": 2}

    mock_scans_collection.find_one = AsyncMock(
        side_effect=[running_scan_2, completed_scan_2]
    )
    mock_scans_collection.update_one = AsyncMock()

    # find_one returns existing devices (matched by primaryMac)
    mock_devices_collection.find_one = AsyncMock(
        side_effect=[existing_device_a, existing_device_b]
    )
    mock_devices_collection.insert_one = AsyncMock()
    mock_devices_collection.update_one = AsyncMock()

    response2 = await client.post(
        f"/api/v1/discovery/scans/{scan_id_2}/results",
        json={
            "results": devices,
            "summary": _make_scan_summary(hosts_alive=2, new_discoveries=0, returning_devices=2),
        },
        headers=auth_headers,
    )

    assert response2.status_code == 200
    # No new inserts on second submission -- devices were updated instead
    mock_devices_collection.insert_one.assert_not_awaited()
    # update_one should have been called for each existing device (merge)
    assert mock_devices_collection.update_one.await_count >= 2
