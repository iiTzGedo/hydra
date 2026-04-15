"""Network discovery service for scan management and device tracking."""

from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime
from ipaddress import ip_network
from typing import Any, cast

import structlog
from pymongo import ASCENDING, DESCENDING

from hydra.api.v1.core.exceptions import (
    CommandNotSupportedError,
    ConflictError,
    HydraError,
    NodeNotFoundError,
    NotFoundError,
)
from hydra.api.v1.models.commands import CommandSource, CreateCommandRequest
from hydra.api.v1.models.commands.schemas import CommandTarget
from hydra.api.v1.models.discovery.enums import (
    DiscoveryStatus,
    ScanStatus,
    ScanTrigger,
)
from hydra.api.v1.models.discovery.requests import (
    ApproveDeviceRequest,
    BulkApproveRequest,
    BulkRejectRequest,
    DiscoveryListParams,
    RejectDeviceRequest,
    ScanListParams,
    StartScanRequest,
    SubmitScanResultsRequest,
)
from hydra.api.v1.services.commands.service import CommandsService
from hydra.api.v1.services.discovery.eligibility import assess_eligibility
from hydra.api.v1.services.discovery.exclusions import ExclusionService
from hydra.api.v1.services.discovery.fingerprint import FingerprintService
from hydra.api.v1.services.docs import DocsService
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)


# ── Discovery ID Generation ───────────────────────────────────────────


def generate_discovery_id(
    primary_mac: str | None,
    network_id: str | None,
    current_ip: str | None,
) -> str:
    """Generate a spec-format discoveryId.

    Format:
        - With MAC: ``disc::mac::{normalized-mac}`` (hyphen-separated lowercase)
        - Without MAC: ``disc::ip::{networkId}::{ip}``

    Args:
        primary_mac: MAC address (any format: colon or hyphen separated).
        network_id: Network where the device was discovered.
        current_ip: IP address of the device.

    Returns:
        A deterministic discoveryId string.
    """
    if primary_mac:
        normalized = primary_mac.lower().replace(":", "-")
        return f"disc::mac::{normalized}"
    if network_id and current_ip:
        return f"disc::ip::{network_id}::{current_ip}"
    if current_ip:
        return f"disc::ip::unknown::{current_ip}"
    return f"disc::unknown::{secrets.token_hex(8)}"


# ── Exceptions ──────────────────────────────────────────────────────────


class ScanNotFoundError(NotFoundError):
    """Scan not found."""

    def __init__(self, scan_id: str) -> None:
        super().__init__("scan", scan_id)


class DiscoveryNotFoundError(NotFoundError):
    """Discovered device not found."""

    def __init__(self, discovery_id: str) -> None:
        super().__init__("discovery", discovery_id)


class ScanNotModifiableError(HydraError):
    """Scan is not in a modifiable state."""

    def __init__(self, scan_id: str, status: str) -> None:
        super().__init__(
            "SCAN_NOT_MODIFIABLE",
            f"Scan '{scan_id}' cannot be modified (status: {status})",
            status_code=409,
            details={"scanId": scan_id, "status": status},
        )


class DiscoveryNotDismissibleError(HydraError):
    """Discovered device cannot be dismissed in its current state."""

    def __init__(self, discovery_id: str, status: str) -> None:
        super().__init__(
            "DISCOVERY_NOT_DISMISSIBLE",
            f"Discovery '{discovery_id}' cannot be dismissed (status: {status})",
            status_code=409,
            details={"discoveryId": discovery_id, "status": status},
        )


class DiscoveryNotPendingError(HydraError):
    """Discovered device is not in pending state for approval/rejection."""

    def __init__(self, discovery_id: str, status: str) -> None:
        super().__init__(
            "DISCOVERY_NOT_PENDING",
            f"Discovery '{discovery_id}' is not pending (status: {status})",
            status_code=409,
            details={"discoveryId": discovery_id, "status": status},
        )


# ── Service ─────────────────────────────────────────────────────────────


class DiscoveryService:
    """Service for managing network discovery scans and discovered devices."""

    def __init__(self, mongodb: MongoDB) -> None:
        self.db = mongodb
        self.scans = mongodb.db["discovery_scans"]
        self.devices = mongodb.db["discovered_nodes"]
        self.nodes = mongodb.db["nodes"]
        self.commands = CommandsService(mongodb)
        self.docs = DocsService(mongodb)
        self.exclusions = ExclusionService(mongodb)
        self.fingerprinter = FingerprintService()

    # ── Scan Management ────────────────────────────────────────────────

    async def start_scan(
        self,
        request: StartScanRequest,
        user_id: str,
        *,
        user_role: str = "operator",
        user_permissions: list[str] | None = None,
        triggered_via: ScanTrigger = ScanTrigger.API,
    ) -> dict[str, Any]:
        """Start a new network discovery scan.

        Args:
            request: Scan configuration.
            user_id: ID of the user initiating the scan.
            user_role: Caller's RBAC role for delegated command dispatch.
            user_permissions: Caller's permissions for delegated command dispatch.
            triggered_via: How the scan was triggered (api/web/mcp).

        Returns:
            The created scan document.
        """
        now = datetime.now(UTC)
        scan_id = f"scan_{secrets.token_hex(12)}"
        delegate_node_id = request.delegate_to_node_id or next(
            (
                target.delegate_to_node_id
                for target in request.targets
                if target.delegate_to_node_id is not None
            ),
            None,
        )
        if delegate_node_id is not None:
            await self._validate_delegated_scanner(delegate_node_id)

        # If delegated to a node, start as PENDING; otherwise RUNNING
        has_delegate = delegate_node_id is not None
        initial_status = ScanStatus.PENDING if has_delegate else ScanStatus.RUNNING
        estimated_hosts = self._estimate_total_hosts(request)

        scan_doc: dict[str, Any] = {
            "scanId": scan_id,
            "status": initial_status,
            "targets": [t.model_dump(by_alias=True) for t in request.targets],
            "options": request.options.model_dump(by_alias=True),
            "triggeredVia": triggered_via,
            "execution": {
                "scannedBy": delegate_node_id or "api",
                "scannedFrom": None,
                "method": "agent-delegated" if has_delegate else "api-direct",
                "delegatedTo": delegate_node_id,
            },
            "delegateToNodeId": delegate_node_id,
            "summary": None,
            "progress": {
                "phase": "queued" if has_delegate else "running",
                "hostsTotal": estimated_hosts,
                "hostsScanned": 0,
                "hostsAlive": 0,
                "percentComplete": 0.0,
            },
            "delegation": (
                {
                    "delegatedTo": delegate_node_id,
                    "commandId": None,
                    "executionMethod": "agent-poll",
                    "commandStatus": "queued",
                    "notes": [
                        "Delegated network scan queued for agent execution.",
                    ],
                }
                if has_delegate
                else None
            ),
            "error": None,
            "resultCount": 0,
            "startedBy": user_id,
            "startedAt": now if initial_status == ScanStatus.RUNNING else None,
            "completedAt": None,
            "createdAt": now,
            "updatedAt": now,
        }

        await self.scans.insert_one(scan_doc)

        if has_delegate and delegate_node_id is not None:
            command = await self.commands.create_command(
                CreateCommandRequest(
                    registry_id="reg::agent::network-scan",
                    target=CommandTarget(node_id=delegate_node_id, service_id=None),
                    parameters={
                        "scanId": scan_id,
                        "targets": [
                            target.subnet
                            for target in request.targets
                            if target.subnet is not None
                        ],
                        "targetSpecs": [
                            target.model_dump(by_alias=True)
                            for target in request.targets
                        ],
                        "methods": [
                            method.value
                            for method in request.options.methods
                        ],
                        "portTier": request.options.port_tier,
                        "timeoutSeconds": request.options.timeout_seconds,
                        "includeIoTProtocols": request.options.include_iot_protocols,
                    },
                    timeout_seconds=max(request.options.timeout_seconds, 60),
                ),
                user_id=user_id,
                user_role=user_role,
                user_permissions=user_permissions or ["discovery:scan"],
                source=CommandSource.API,
                client_id="hydra-api",
            )
            await self.attach_delegated_command(scan_id, command)
            scan_doc = await self.get_scan(scan_id)

        logger.info("discovery.scan_started", scan_id=scan_id, status=initial_status)
        return scan_doc

    async def get_scan(self, scan_id: str) -> dict[str, Any]:
        """Get a scan by ID.

        Args:
            scan_id: The scan identifier.

        Returns:
            The scan document.

        Raises:
            ScanNotFoundError: If the scan does not exist.
        """
        scan = await self.scans.find_one({"scanId": scan_id})
        if not scan:
            raise ScanNotFoundError(scan_id)
        result: dict[str, Any] = scan
        return result

    async def list_scans(
        self,
        params: ScanListParams,
    ) -> tuple[list[dict[str, Any]], int]:
        """List scans with optional filtering and pagination.

        Args:
            params: Listing parameters.

        Returns:
            Tuple of (scans, total_count).
        """
        query: dict[str, Any] = {}
        if params.status is not None:
            query["status"] = params.status.value

        sort_dir = DESCENDING if params.sort_order == "desc" else ASCENDING
        total = await self.scans.count_documents(query)
        cursor = (
            self.scans.find(query)
            .sort(params.sort_by, sort_dir)
            .skip(params.offset)
            .limit(params.limit)
        )
        scans = await cursor.to_list(length=params.limit)
        return scans, total

    async def submit_scan_results(
        self,
        scan_id: str,
        request: SubmitScanResultsRequest,
    ) -> dict[str, Any]:
        """Submit results from a completed scan.

        Args:
            scan_id: The scan to attach results to.
            request: The scan results payload.

        Returns:
            The updated scan document.

        Raises:
            ScanNotFoundError: If scan does not exist.
            ScanNotModifiableError: If scan is already completed/failed/cancelled.
        """
        scan = await self.get_scan(scan_id)

        if scan["status"] not in (ScanStatus.PENDING, ScanStatus.RUNNING):
            raise ScanNotModifiableError(scan_id, scan["status"])

        now = datetime.now(UTC)

        # Upsert each discovered device, collecting per-device errors
        upsert_errors: list[str] = []
        for device_data in request.results:
            try:
                await self._upsert_device(
                    device_data.model_dump(by_alias=True),
                    now,
                    scan_id=scan_id,
                )
            except (ValueError, Exception) as exc:  # noqa: BLE001
                logger.warning(
                    "discovery.device_upsert_failed",
                    error=str(exc),
                    device=device_data.model_dump(by_alias=True),
                )
                upsert_errors.append(str(exc))

        # Update scan to completed
        summary_dict = request.summary.model_dump(by_alias=True)
        progress = {
            "phase": "completed",
            "hostsTotal": summary_dict["hostsScanned"],
            "hostsScanned": summary_dict["hostsScanned"],
            "hostsAlive": summary_dict["hostsAlive"],
            "percentComplete": 100.0,
        }
        await self.scans.update_one(
            {"scanId": scan_id},
            {
                "$set": {
                    "status": ScanStatus.COMPLETED,
                    "summary": summary_dict,
                    "progress": progress,
                    "resultCount": len(request.results),
                    "error": request.error,
                    "completedAt": now,
                    "updatedAt": now,
                    "delegation.commandStatus": "completed",
                }
            },
        )

        updated = await self.get_scan(scan_id)
        logger.info("discovery.scan_completed", scan_id=scan_id)
        return updated

    # ── Device Upsert ──────────────────────────────────────────────────

    async def _upsert_device(
        self,
        device_data: dict[str, Any],
        now: datetime,
        *,
        scan_id: str | None = None,
    ) -> None:
        """Upsert a discovered device by primaryMac or currentIp.

        If an existing device matches, update lastSeen, increment seenCount,
        and merge openPorts/protocols. Otherwise create a new discovery entry
        with a spec-format discoveryId.
        """
        identity = device_data.get("identity", {})
        primary_mac = identity.get("primaryMac")
        current_ip = identity.get("currentIp")
        network_id = device_data.get("networkId")

        # Build match query: prefer MAC, fall back to IP
        match_query: dict[str, Any]
        if primary_mac:
            match_query = {"identity.primaryMac": primary_mac}
        elif current_ip:
            match_query = {"identity.currentIp": current_ip}
        else:
            msg = "Discovered device has neither primaryMac nor currentIp"
            raise ValueError(msg)

        # Check exclusion rules before upserting
        if await self.exclusions.is_excluded(primary_mac, current_ip):
            return

        existing = await self.devices.find_one(match_query)

        if existing:
            # Skip permanently dismissed devices — they should not reappear
            if existing.get("dismissPermanent"):
                return

            # Merge: update lastSeen, increment seenCount, union ports/protocols
            new_ports = list(
                set(existing.get("openPorts", []))
                | set(device_data.get("openPorts", []))
            )
            new_protocols = list(
                set(existing.get("protocols", []))
                | set(device_data.get("protocols", []))
            )

            # Build observed IP entry for this sighting
            observed_ip_entry = {
                "address": current_ip,
                "seenAt": now,
                "seenInScan": scan_id,
            }
            # Merge observed MACs
            existing_observed_macs = existing.get("identity", {}).get("observedMacs", [])
            new_observed_macs = list(set(existing_observed_macs))
            if primary_mac and primary_mac not in new_observed_macs:
                new_observed_macs.append(primary_mac)

            # Resolve vendor from MAC if not already set
            existing_mac_vendor = existing.get("identity", {}).get("macVendor")
            mac_vendor = existing_mac_vendor
            if not mac_vendor and primary_mac:
                mac_vendor = self.fingerprinter.lookup_vendor(primary_mac)

            update_set: dict[str, Any] = {
                "lastSeen": now,
                "updatedAt": now,
                "openPorts": new_ports,
                "protocols": new_protocols,
                "identity.currentIp": current_ip,
                "identity.observedMacs": new_observed_macs,
                "identity.macResolved": bool(primary_mac),
                "probe": device_data.get("probe", existing.get("probe")),
                "rawEvidence": device_data.get(
                    "rawEvidence",
                    existing.get("rawEvidence"),
                ),
            }
            if mac_vendor:
                update_set["identity.macVendor"] = mac_vendor

            await self.devices.update_one(
                match_query,
                {
                    "$set": update_set,
                    "$inc": {"seenCount": 1},
                    "$push": {"identity.observedIps": observed_ip_entry},
                },
            )
            # Re-enrich if ports changed
            existing_discovery_id = existing.get("discoveryId")
            if existing_discovery_id and set(new_ports) != set(
                existing.get("openPorts", [])
            ):
                await self.enrich_discovery(existing_discovery_id)
        else:
            # Generate spec-format discoveryId
            discovery_id = generate_discovery_id(primary_mac, network_id, current_ip)

            # Resolve vendor from MAC
            mac_vendor = self.fingerprinter.lookup_vendor(primary_mac) if primary_mac else None

            # Build initial observed data
            observed_ips = [
                {"address": current_ip, "seenAt": now, "seenInScan": scan_id},
            ] if current_ip else []
            observed_macs = [primary_mac] if primary_mac else []

            # Populate identity with new fields
            enriched_identity: dict[str, Any] = {
                **identity,
                "observedMacs": observed_macs,
                "macVendor": mac_vendor,
                "macResolved": bool(primary_mac),
                "observedIps": observed_ips,
                "hostnameSources": [],
            }

            doc: dict[str, Any] = {
                "discoveryId": discovery_id,
                "identity": enriched_identity,
                "networkId": network_id,
                "probe": device_data.get("probe", {}),
                "status": DiscoveryStatus.PENDING,
                "firstSeen": now,
                "lastSeen": now,
                "updatedAt": now,
                "seenCount": 1,
                "openPorts": device_data.get("openPorts", []),
                "protocols": device_data.get("protocols", []),
                "rawEvidence": device_data.get("rawEvidence"),
                "fingerprint": None,
                "classification": None,
                "eligibility": None,
                "dismissedAt": None,
                "dismissedBy": None,
                "dismissReason": None,
                "dismissPermanent": False,
                "approvedAt": None,
                "approvedBy": None,
                "rejectedAt": None,
                "rejectedBy": None,
                "rejectReason": None,
                "matchedNodeId": None,
            }
            await self.devices.insert_one(doc)
            # Enrich new devices that have open ports or protocols
            if device_data.get("openPorts") or device_data.get("protocols"):
                await self.enrich_discovery(discovery_id)

    # ── Discovery Listing & Detail ─────────────────────────────────────

    async def list_discoveries(
        self,
        params: DiscoveryListParams,
    ) -> tuple[list[dict[str, Any]], int]:
        """List discovered devices with filtering and pagination.

        Args:
            params: Listing parameters.

        Returns:
            Tuple of (devices, total_count).
        """
        query: dict[str, Any] = {}
        if params.status is not None:
            query["status"] = params.status.value
        if params.network_id is not None:
            query["networkId"] = params.network_id
        if params.device_class is not None:
            query["classification.suggestedClass"] = params.device_class
        if params.agent_compatible is not None:
            query["eligibility.agentCompatible"] = params.agent_compatible
        if params.remote_installable is not None:
            query["eligibility.remoteInstallable"] = params.remote_installable
        if params.min_confidence is not None:
            query["classification.confidence"] = {"$gte": params.min_confidence}
        if params.since is not None:
            query["lastSeen"] = {"$gte": params.since}

        if params.search:
            escaped = re.escape(params.search)
            query["$or"] = [
                {"identity.hostname": {"$regex": escaped, "$options": "i"}},
                {"identity.currentIp": {"$regex": escaped, "$options": "i"}},
                {"identity.primaryMac": {"$regex": escaped, "$options": "i"}},
            ]

        sort_dir = DESCENDING if params.sort_order == "desc" else ASCENDING
        total = await self.devices.count_documents(query)
        cursor = (
            self.devices.find(query)
            .sort(params.sort_by, sort_dir)
            .skip(params.offset)
            .limit(params.limit)
        )
        devices = await cursor.to_list(length=params.limit)
        return devices, total

    async def get_discovery(self, discovery_id: str) -> dict[str, Any]:
        """Get a discovered device by ID.

        Args:
            discovery_id: The discovery identifier.

        Returns:
            The device document.

        Raises:
            DiscoveryNotFoundError: If the device does not exist.
        """
        device = await self.devices.find_one({"discoveryId": discovery_id})
        if not device:
            raise DiscoveryNotFoundError(discovery_id)
        result: dict[str, Any] = device
        return result

    # ── Scan Diff ───────────────────────────────────────────────────────

    async def compute_scan_diff(
        self,
        network_id: str,
        from_scan_id: str | None = None,
        to_scan_id: str | None = None,
    ) -> dict[str, Any]:
        """Compare two scans for a network to find arrived/departed/changed devices.

        If scan IDs are not specified, uses the two most recent completed scans
        for the given network.

        Args:
            network_id: Network to compare scans for.
            from_scan_id: Earlier scan ID (optional — defaults to second-latest).
            to_scan_id: Later scan ID (optional — defaults to latest).

        Returns:
            Diff result with arrived, departed, changed, and unchanged counts.

        Raises:
            ScanNotFoundError: If either scan does not exist.
        """
        if not from_scan_id or not to_scan_id:
            recent = await (
                self.scans.find({
                    "status": ScanStatus.COMPLETED,
                    "targets.networkId": network_id,
                })
                .sort("completedAt", DESCENDING)
                .limit(2)
                .to_list(length=2)
            )
            if len(recent) < 2:
                return {
                    "networkId": network_id,
                    "fromScan": None,
                    "toScan": None,
                    "arrived": [],
                    "departed": [],
                    "changed": [],
                    "unchanged": 0,
                    "error": "Fewer than 2 completed scans for this network",
                }
            to_scan_doc = recent[0]
            from_scan_doc = recent[1]
            from_scan_id = from_scan_doc["scanId"]
            to_scan_id = to_scan_doc["scanId"]
        else:
            from_scan_doc = await self.get_scan(from_scan_id)
            to_scan_doc = await self.get_scan(to_scan_id)

        # Find devices seen in each scan
        from_devices = await self.devices.find(
            {"probe.delegatedByScanId": from_scan_id, "networkId": network_id}
        ).to_list(length=1000)
        to_devices = await self.devices.find(
            {"probe.delegatedByScanId": to_scan_id, "networkId": network_id}
        ).to_list(length=1000)

        # Also check devices whose observedIps.seenInScan matches
        from_by_scan = await self.devices.find(
            {"identity.observedIps.seenInScan": from_scan_id, "networkId": network_id}
        ).to_list(length=1000)
        to_by_scan = await self.devices.find(
            {"identity.observedIps.seenInScan": to_scan_id, "networkId": network_id}
        ).to_list(length=1000)

        # Merge device lists by discoveryId
        def _merge(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
            result: dict[str, dict[str, Any]] = {}
            for d in a:
                result[d["discoveryId"]] = d
            for d in b:
                result[d["discoveryId"]] = d
            return result

        from_map = _merge(from_devices, from_by_scan)
        to_map = _merge(to_devices, to_by_scan)

        from_ids = set(from_map.keys())
        to_ids = set(to_map.keys())

        arrived_ids = to_ids - from_ids
        departed_ids = from_ids - to_ids
        common_ids = from_ids & to_ids

        def _device_summary(d: dict[str, Any]) -> dict[str, Any]:
            identity = d.get("identity", {})
            return {
                "discoveryId": d["discoveryId"],
                "ip": identity.get("currentIp"),
                "mac": identity.get("primaryMac"),
                "hostname": identity.get("hostname"),
                "classification": d.get("classification"),
            }

        arrived = [_device_summary(to_map[did]) for did in sorted(arrived_ids)]
        departed = [_device_summary(from_map[did]) for did in sorted(departed_ids)]

        changed: list[dict[str, Any]] = []
        unchanged = 0
        for did in sorted(common_ids):
            old = from_map[did]
            new = to_map[did]
            changes = self._compute_device_changes(old, new)
            if changes:
                identity = new.get("identity", {})
                changed.append({
                    "discoveryId": did,
                    "ip": identity.get("currentIp"),
                    "hostname": identity.get("hostname"),
                    "changes": changes,
                })
            else:
                unchanged += 1

        return {
            "networkId": network_id,
            "fromScan": {
                "scanId": from_scan_id,
                "completedAt": from_scan_doc.get("completedAt"),
            },
            "toScan": {
                "scanId": to_scan_id,
                "completedAt": to_scan_doc.get("completedAt"),
            },
            "arrived": arrived,
            "departed": departed,
            "changed": changed,
            "unchanged": unchanged,
        }

    @staticmethod
    def _compute_device_changes(
        old: dict[str, Any],
        new: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Compare two versions of the same device and return changed fields."""
        changes: list[dict[str, Any]] = []

        old_ip = old.get("identity", {}).get("currentIp")
        new_ip = new.get("identity", {}).get("currentIp")
        if old_ip != new_ip:
            changes.append({"field": "ip", "from": old_ip, "to": new_ip})

        old_hostname = old.get("identity", {}).get("hostname")
        new_hostname = new.get("identity", {}).get("hostname")
        if old_hostname != new_hostname:
            changes.append({"field": "hostname", "from": old_hostname, "to": new_hostname})

        old_ports = set(old.get("openPorts", []))
        new_ports = set(new.get("openPorts", []))
        if old_ports != new_ports:
            added = sorted(new_ports - old_ports)
            removed = sorted(old_ports - new_ports)
            changes.append({
                "field": "openPorts",
                "from": {"added": added, "removed": removed},
                "to": sorted(new_ports),
            })

        old_class = (old.get("classification") or {}).get("suggestedClass")
        new_class = (new.get("classification") or {}).get("suggestedClass")
        if old_class != new_class and old_class is not None and new_class is not None:
            changes.append({"field": "suggestedClass", "from": old_class, "to": new_class})

        return changes

    # ── Enrichment ─────────────────────────────────────────────────────

    async def enrich_discovery(self, discovery_id: str) -> dict[str, Any]:
        """Enrich a discovered device with fingerprint, classification, and eligibility.

        Args:
            discovery_id: The discovery identifier to enrich.

        Returns:
            The updated device document.

        Raises:
            DiscoveryNotFoundError: If the device does not exist.
        """
        device = await self.get_discovery(discovery_id)

        open_ports: list[int] = device.get("openPorts", [])
        protocols: list[str] = device.get("protocols", [])
        raw_evidence = device.get("rawEvidence") or {}
        identity = device.get("identity", {})
        primary_mac = identity.get("primaryMac")
        hostname = identity.get("hostname")

        fingerprint = self.fingerprinter.fingerprint_device(
            open_ports,
            protocols,
            primary_mac=primary_mac,
            raw_vendor=raw_evidence.get("vendor"),
        )
        classification = self.fingerprinter.classify_device(
            fingerprint,
            primary_mac=primary_mac,
            hostname=hostname,
        )
        eligibility = assess_eligibility(
            fingerprint, classification, open_ports,
        )

        now = datetime.now(UTC)
        update: dict[str, Any] = {
            "fingerprint": fingerprint.model_dump(by_alias=True),
            "classification": classification.model_dump(by_alias=True),
            "eligibility": eligibility.model_dump(by_alias=True),
            "updatedAt": now,
        }

        await self.devices.update_one(
            {"discoveryId": discovery_id},
            {"$set": update},
        )

        device.update(update)
        logger.info(
            "discovery.device_enriched",
            discovery_id=discovery_id,
            suggested_class=classification.suggested_class,
            confidence=classification.confidence,
        )
        return device

    # ── Dismiss ────────────────────────────────────────────────────────

    async def dismiss_discovery(
        self,
        discovery_id: str,
        reason: str | None,
        user_id: str,
        *,
        permanent: bool = False,
    ) -> dict[str, Any]:
        """Dismiss a discovered device.

        Args:
            discovery_id: The discovery to dismiss.
            reason: Optional reason for dismissal.
            user_id: ID of the user dismissing the device.
            permanent: If True, device will not reappear in future scans.

        Returns:
            The updated device document.

        Raises:
            DiscoveryNotFoundError: If device does not exist.
            DiscoveryNotDismissibleError: If device is already dismissed or registered.
        """
        device = await self.get_discovery(discovery_id)

        if device["status"] in (DiscoveryStatus.DISMISSED, DiscoveryStatus.REGISTERED):
            raise DiscoveryNotDismissibleError(discovery_id, device["status"])

        now = datetime.now(UTC)
        await self.devices.update_one(
            {"discoveryId": discovery_id},
            {
                "$set": {
                    "status": DiscoveryStatus.DISMISSED,
                    "dismissedAt": now,
                    "dismissedBy": user_id,
                    "dismissReason": reason,
                    "dismissPermanent": permanent,
                }
            },
        )

        return await self.get_discovery(discovery_id)

    # ── Approval / Rejection ───────────────────────────────────────────

    async def approve_device(
        self,
        discovery_id: str,
        request: ApproveDeviceRequest,
        user_id: str,
    ) -> dict[str, Any]:
        """Approve a discovered device, optionally auto-registering it as a node.

        Args:
            discovery_id: The discovery to approve.
            request: Approval options (auto_register, node_id override, etc.).
            user_id: ID of the approving user.

        Returns:
            Dict with discoveryId, status, and matchedNodeId (if registered).

        Raises:
            DiscoveryNotFoundError: If the device does not exist.
            DiscoveryNotPendingError: If the device is not in pending status.
        """
        device = await self.get_discovery(discovery_id)

        if device["status"] != DiscoveryStatus.PENDING:
            raise DiscoveryNotPendingError(discovery_id, device["status"])

        now = datetime.now(UTC)
        matched_node_id: str | None = None

        if request.auto_register:
            node_id = self._derive_node_id(device, request.node_id)

            # Check for nodeId collision before inserting
            existing_node = await self.nodes.find_one({"nodeId": node_id})
            if existing_node:
                raise ConflictError("node", node_id)

            # Determine node metadata from request overrides or classification
            classification = device.get("classification") or {}
            node_class = request.node_class or classification.get(
                "suggestedClass", "compute"
            )
            if node_class == "unknown":
                node_class = "compute"

            node_type = request.node_type or classification.get("suggestedType")
            kind = request.kind or classification.get("suggestedKind")
            display_name = (
                request.display_name
                or classification.get("suggestedDisplayName")
                or node_id
            )
            description = (
                request.description
                or f"Auto-registered from discovery {discovery_id}"
            )

            node_doc: dict[str, Any] = {
                "nodeId": node_id,
                "class": node_class,
                "type": node_type,
                "kind": kind,
                "displayName": display_name,
                "description": description,
                "tags": request.tags,
                "parentNodeId": None,
                "networkIds": (
                    [device["networkId"]] if device.get("networkId") else []
                ),
                "location": None,
                "agentTier": "normal",
                "registeredAt": now,
                "registeredBy": user_id,
                "registeredVia": "discovery",
                "lastUpdated": now,
                "lastProfileAt": None,
                "status": "active",
            }

            await self.nodes.insert_one(node_doc)
            matched_node_id = node_id

            await self.devices.update_one(
                {"discoveryId": discovery_id},
                {
                    "$set": {
                        "status": DiscoveryStatus.REGISTERED,
                        "approvedAt": now,
                        "approvedBy": user_id,
                        "matchedNodeId": node_id,
                    }
                },
            )
            final_status = DiscoveryStatus.REGISTERED
            logger.info(
                "discovery.device_registered",
                discovery_id=discovery_id,
                node_id=node_id,
            )
        else:
            await self.devices.update_one(
                {"discoveryId": discovery_id},
                {
                    "$set": {
                        "status": DiscoveryStatus.APPROVED,
                        "approvedAt": now,
                        "approvedBy": user_id,
                    }
                },
            )
            final_status = DiscoveryStatus.APPROVED
            logger.info(
                "discovery.device_approved",
                discovery_id=discovery_id,
            )

        refresh_entities: list[tuple[str, str]] = []
        if matched_node_id:
            refresh_entities.append(("node", matched_node_id))
        if device.get("networkId"):
            refresh_entities.append(("network", str(device["networkId"])))

        if refresh_entities:
            try:
                await self.docs.refresh_documents_for_entities(
                    refresh_entities,
                    user_id=user_id,
                )
            except Exception as exc:
                logger.warning(
                    "discovery_docs_refresh_failed",
                    discovery_id=discovery_id,
                    entities=refresh_entities,
                    error=str(exc),
                )

        return {
            "discoveryId": discovery_id,
            "status": final_status,
            "matchedNodeId": matched_node_id,
        }

    async def reject_device(
        self,
        discovery_id: str,
        request: RejectDeviceRequest,
        user_id: str,
    ) -> dict[str, Any]:
        """Reject a discovered device.

        Args:
            discovery_id: The discovery to reject.
            request: Rejection details (optional reason).
            user_id: ID of the rejecting user.

        Returns:
            Dict with discoveryId, status, and matchedNodeId (None).

        Raises:
            DiscoveryNotFoundError: If the device does not exist.
            DiscoveryNotPendingError: If the device is not in pending status.
        """
        device = await self.get_discovery(discovery_id)

        if device["status"] != DiscoveryStatus.PENDING:
            raise DiscoveryNotPendingError(discovery_id, device["status"])

        now = datetime.now(UTC)
        await self.devices.update_one(
            {"discoveryId": discovery_id},
            {
                "$set": {
                    "status": DiscoveryStatus.REJECTED,
                    "rejectedAt": now,
                    "rejectedBy": user_id,
                    "rejectReason": request.reason,
                }
            },
        )

        logger.info(
            "discovery.device_rejected",
            discovery_id=discovery_id,
            reason=request.reason,
        )

        return {
            "discoveryId": discovery_id,
            "status": DiscoveryStatus.REJECTED,
            "matchedNodeId": None,
        }

    async def bulk_approve(
        self,
        request: BulkApproveRequest,
        user_id: str,
    ) -> dict[str, Any]:
        """Bulk approve multiple discovered devices.

        Args:
            request: Bulk approval request with discovery IDs.
            user_id: ID of the approving user.

        Returns:
            Dict with processed/succeeded/failed counts, results, and errors.
        """
        results: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []

        for disc_id in request.discovery_ids:
            try:
                approve_req = ApproveDeviceRequest(
                    auto_register=request.auto_register,
                )
                result = await self.approve_device(disc_id, approve_req, user_id)
                results.append(result)
            except Exception as exc:
                errors.append({
                    "discoveryId": disc_id,
                    "error": str(exc),
                })

        return {
            "processed": len(request.discovery_ids),
            "succeeded": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors,
        }

    async def bulk_reject(
        self,
        request: BulkRejectRequest,
        user_id: str,
    ) -> dict[str, Any]:
        """Bulk reject multiple discovered devices.

        Args:
            request: Bulk rejection request with discovery IDs.
            user_id: ID of the rejecting user.

        Returns:
            Dict with processed/succeeded/failed counts, results, and errors.
        """
        results: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []

        for disc_id in request.discovery_ids:
            try:
                reject_req = RejectDeviceRequest(reason=request.reason)
                result = await self.reject_device(disc_id, reject_req, user_id)
                results.append(result)
            except Exception as exc:
                errors.append({
                    "discoveryId": disc_id,
                    "error": str(exc),
                })

        return {
            "processed": len(request.discovery_ids),
            "succeeded": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors,
        }

    # ── Delegation Lifecycle ───────────────────────────────────────────

    async def attach_delegated_command(
        self,
        scan_id: str,
        command: dict[str, Any],
    ) -> None:
        """Attach the queued command metadata to a delegated scan."""
        now = datetime.now(UTC)
        command_status = command.get("status", "queued")
        scan_status = ScanStatus.RUNNING if command_status == "executing" else ScanStatus.PENDING
        progress = {
            "phase": "running" if command_status == "executing" else "queued",
            "hostsTotal": self._get_scan_progress_total(await self.get_scan(scan_id)),
            "hostsScanned": 0,
            "hostsAlive": 0,
            "percentComplete": 5.0 if command_status == "executing" else 0.0,
        }
        await self.scans.update_one(
            {"scanId": scan_id},
            {
                "$set": {
                    "status": scan_status,
                    "progress": progress,
                    "delegation.commandId": command.get("commandId"),
                    "delegation.commandStatus": command_status,
                    "delegation.executionMethod": command.get("executionMethod", "agent-poll"),
                    "updatedAt": now,
                }
            },
        )

    async def mark_delegated_scan_running(self, scan_id: str) -> None:
        """Move a delegated scan into running state once an agent claims it."""
        scan = await self.get_scan(scan_id)
        now = datetime.now(UTC)
        hosts_total = self._get_scan_progress_total(scan)
        await self.scans.update_one(
            {"scanId": scan_id},
            {
                "$set": {
                    "status": ScanStatus.RUNNING,
                    "startedAt": scan.get("startedAt") or now,
                    "progress": {
                        "phase": "running",
                        "hostsTotal": hosts_total,
                        "hostsScanned": 0,
                        "hostsAlive": 0,
                        "percentComplete": 10.0,
                    },
                    "delegation.commandStatus": "executing",
                    "updatedAt": now,
                }
            },
        )

    async def fail_delegated_scan(
        self,
        scan_id: str,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Mark a delegated scan as failed with structured error information."""
        scan = await self.get_scan(scan_id)
        now = datetime.now(UTC)
        hosts_total = self._get_scan_progress_total(scan)
        await self.scans.update_one(
            {"scanId": scan_id},
            {
                "$set": {
                    "status": ScanStatus.FAILED,
                    "error": {
                        "code": code,
                        "message": message,
                        "details": details,
                    },
                    "progress": {
                        "phase": "failed",
                        "hostsTotal": hosts_total,
                        "hostsScanned": 0,
                        "hostsAlive": 0,
                        "percentComplete": 100.0,
                    },
                    "completedAt": now,
                    "updatedAt": now,
                    "delegation.commandStatus": "failed",
                }
            },
        )

    async def handle_scan_command_result(
        self,
        command: dict[str, Any],
        success: bool,
        result_data: dict[str, Any] | None,
        error_message: str | None = None,
    ) -> None:
        """Ingest a delegated network scan command result back into discovery."""
        if command.get("registryId") != "reg::agent::network-scan":
            return

        parameters = command.get("parameters") or {}
        scan_id = parameters.get("scanId")
        if not scan_id:
            return

        if not success:
            await self.fail_delegated_scan(
                scan_id,
                code="DELEGATED_SCAN_FAILED",
                message=error_message or "Delegated scan execution failed",
                details={
                    "commandId": command.get("commandId"),
                    "nodeId": command.get("target", {}).get("nodeId"),
                },
            )
            return

        payload = result_data or {}
        summary_data = payload.get("summary")
        results_data = payload.get("results")
        if not isinstance(summary_data, dict) or not isinstance(results_data, list):
            await self.fail_delegated_scan(
                scan_id,
                code="DELEGATED_SCAN_INVALID_RESULT",
                message="Delegated scan completed without a valid discovery payload",
                details={"commandId": command.get("commandId")},
            )
            return

        await self.submit_scan_results(
            scan_id,
            SubmitScanResultsRequest(
                summary=cast(Any, summary_data),
                results=cast(Any, results_data),
                error=None,
            ),
        )

    # ── Installation Bridge ─────────────────────────────────────────────

    async def trigger_installation(
        self,
        discovery_id: str,
        credentials_dict: dict[str, Any],
        agent_tier: str,
        user_id: str,
    ) -> dict[str, Any]:
        """Trigger an agent installation for a discovered device.

        Validates the device is in APPROVED status, transitions it to
        INSTALLING, then delegates to the InstallationService.

        Args:
            discovery_id: The discovery device to install on.
            credentials_dict: SSH credentials dict.
            agent_tier: Agent tier to install (lite/normal/max).
            user_id: ID of the initiating user.

        Returns:
            The installation document.

        Raises:
            DiscoveryNotFoundError: If the device does not exist.
            DiscoveryNotPendingError: If the device is not in approved status.
        """
        device = await self.get_discovery(discovery_id)

        if device["status"] != DiscoveryStatus.APPROVED:
            raise DiscoveryNotPendingError(discovery_id, device["status"])

        now = datetime.now(UTC)
        await self.devices.update_one(
            {"discoveryId": discovery_id},
            {"$set": {"status": DiscoveryStatus.INSTALLING, "updatedAt": now}},
        )

        from hydra.api.v1.models.installations import (
            SSHCredentials,
            StartInstallationRequest,
        )
        from hydra.api.v1.services.installations import InstallationService

        install_service = InstallationService(self.db)
        request = StartInstallationRequest(
            discovery_id=discovery_id,
            credentials=SSHCredentials(**credentials_dict),
            agent_tier=agent_tier,
        )
        result = await install_service.start_installation(request, user_id)

        logger.info(
            "discovery.installation_triggered",
            discovery_id=discovery_id,
            installation_id=result.get("installationId"),
        )
        return result

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _estimate_total_hosts(request: StartScanRequest) -> int:
        total = 0
        for target in request.targets:
            if not target.subnet:
                continue
            try:
                network = ip_network(target.subnet, strict=False)
            except ValueError:
                continue
            host_count = max(network.num_addresses - 2, 1)
            total += min(host_count, 1024)
        return total

    async def _validate_delegated_scanner(self, node_id: str) -> dict[str, Any]:
        """Ensure discovery delegation only targets active max-tier agents."""
        node = await self.nodes.find_one({"nodeId": node_id})
        if not node or node.get("status") != "active":
            raise NodeNotFoundError(node_id)
        if node.get("agentTier", "normal") != "max":
            raise CommandNotSupportedError(
                f"Delegated network scans require a max-tier agent. "
                f"Node '{node_id}' is tier '{node.get('agentTier', 'normal')}'."
            )
        return cast(dict[str, Any], node)

    @staticmethod
    def _get_scan_progress_total(scan: dict[str, Any]) -> int:
        progress = scan.get("progress") or {}
        return int(progress.get("hostsTotal", 0))

    @staticmethod
    def _derive_node_id(device: dict[str, Any], override: str | None = None) -> str:
        """Derive a nodeId from a discovered device.

        Uses the override if provided, otherwise falls back to hostname, then IP.

        Args:
            device: The discovery device document.
            override: Optional explicit nodeId.

        Returns:
            A sanitized node ID string.
        """
        if override:
            return override.lower().strip()

        hostname = device.get("identity", {}).get("hostname")
        if hostname:
            node_id = hostname.lower().replace(" ", "-").replace("_", "-")
            node_id = re.sub(r"[^a-z0-9.-]", "", node_id)[:63]
            if node_id:
                return node_id

        ip = device.get("identity", {}).get("currentIp", "unknown")
        return f"disc-{ip.replace('.', '-')}"
