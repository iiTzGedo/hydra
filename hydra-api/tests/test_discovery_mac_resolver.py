"""Tests for MAC resolution and IP→MAC migration."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hydra.api.v1.services.discovery.mac_resolver import (
    migrate_ip_to_mac,
    normalize_mac,
    resolve_mac,
    resolve_via_local_arp,
    resolve_via_router_snmp,
)


class TestNormalizeMac:
    def test_colon_to_hyphen(self):
        assert normalize_mac("AA:BB:CC:DD:EE:FF") == "aa-bb-cc-dd-ee-ff"

    def test_already_normalized(self):
        assert normalize_mac("aa-bb-cc-dd-ee-ff") == "aa-bb-cc-dd-ee-ff"

    def test_uppercase(self):
        assert normalize_mac("DC-A6-32-AB-CD-EF") == "dc-a6-32-ab-cd-ef"


class TestResolveViaLocalArp:
    def test_finds_resolved_entry(self, tmp_path):
        arp_content = (
            "IP address       HW type     Flags       HW address            Mask     Device\n"
            "192.168.1.1      0x1         0x2         aa:bb:cc:dd:ee:ff     *        eth0\n"
            "192.168.1.5      0x1         0x2         11:22:33:44:55:66     *        eth0\n"
        )
        arp_file = tmp_path / "arp"
        arp_file.write_text(arp_content)
        with patch(
            "hydra.api.v1.services.discovery.mac_resolver._PROC_ARP", arp_file
        ):
            assert resolve_via_local_arp("192.168.1.5") == "11:22:33:44:55:66"

    def test_skips_incomplete_entries(self, tmp_path):
        # Flag 0x0 = incomplete
        arp_content = (
            "IP address       HW type     Flags       HW address            Mask     Device\n"
            "192.168.1.5      0x1         0x0         00:00:00:00:00:00     *        eth0\n"
        )
        arp_file = tmp_path / "arp"
        arp_file.write_text(arp_content)
        with patch(
            "hydra.api.v1.services.discovery.mac_resolver._PROC_ARP", arp_file
        ):
            assert resolve_via_local_arp("192.168.1.5") is None

    def test_missing_ip(self, tmp_path):
        arp_content = (
            "IP address       HW type     Flags       HW address            Mask     Device\n"
            "192.168.1.1      0x1         0x2         aa:bb:cc:dd:ee:ff     *        eth0\n"
        )
        arp_file = tmp_path / "arp"
        arp_file.write_text(arp_content)
        with patch(
            "hydra.api.v1.services.discovery.mac_resolver._PROC_ARP", arp_file
        ):
            assert resolve_via_local_arp("10.0.0.1") is None

    def test_unreadable_file(self, tmp_path):
        with patch(
            "hydra.api.v1.services.discovery.mac_resolver._PROC_ARP",
            tmp_path / "missing",
        ):
            assert resolve_via_local_arp("192.168.1.5") is None


class TestResolveViaRouterSnmp:
    @pytest.mark.asyncio
    async def test_no_network(self):
        db = {"networks": MagicMock(), "nodes": MagicMock()}
        db["networks"].find_one = AsyncMock(return_value=None)
        result = await resolve_via_router_snmp("192.168.1.5", "missing-net", db)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_router(self):
        db = {"networks": MagicMock(), "nodes": MagicMock()}
        db["networks"].find_one = AsyncMock(
            return_value={"networkId": "n1", "routerNodeId": None}
        )
        result = await resolve_via_router_snmp("192.168.1.5", "n1", db)
        assert result is None

    @pytest.mark.asyncio
    async def test_calls_snmp_when_router_present(self):
        db = {"networks": MagicMock(), "nodes": MagicMock()}
        db["networks"].find_one = AsyncMock(
            return_value={
                "networkId": "n1",
                "routerNodeId": "router-1",
                "gatewayV4": "192.168.1.1",
            }
        )
        db["nodes"].find_one = AsyncMock(
            return_value={
                "nodeId": "router-1",
                "primaryIp": "192.168.1.1",
                "metadata": {},
            }
        )
        with patch(
            "hydra.api.v1.services.discovery.mac_resolver._snmp_query_arp",
            AsyncMock(return_value="aa:bb:cc:dd:ee:ff"),
        ) as mock_snmp:
            mac = await resolve_via_router_snmp("192.168.1.5", "n1", db)
        assert mac == "aa:bb:cc:dd:ee:ff"
        mock_snmp.assert_called_once_with(
            "192.168.1.1", "192.168.1.5", community="public"
        )


class TestResolveMac:
    @pytest.mark.asyncio
    async def test_local_arp_short_circuits(self):
        with patch(
            "hydra.api.v1.services.discovery.mac_resolver.resolve_via_local_arp",
            return_value="11:22:33:44:55:66",
        ), patch(
            "hydra.api.v1.services.discovery.mac_resolver.resolve_via_router_snmp",
            AsyncMock(),
        ) as mock_snmp:
            mac = await resolve_mac("192.168.1.5", "n1", db={})
        assert mac == "11:22:33:44:55:66"
        mock_snmp.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_through_to_snmp(self):
        with patch(
            "hydra.api.v1.services.discovery.mac_resolver.resolve_via_local_arp",
            return_value=None,
        ), patch(
            "hydra.api.v1.services.discovery.mac_resolver.resolve_via_router_snmp",
            AsyncMock(return_value="ee:ff:00:11:22:33"),
        ):
            mac = await resolve_mac("192.168.1.5", "n1", db={})
        assert mac == "ee:ff:00:11:22:33"

    @pytest.mark.asyncio
    async def test_falls_through_to_agent_when_present(self):
        commands_service = MagicMock()
        with patch(
            "hydra.api.v1.services.discovery.mac_resolver.resolve_via_local_arp",
            return_value=None,
        ), patch(
            "hydra.api.v1.services.discovery.mac_resolver.resolve_via_router_snmp",
            AsyncMock(return_value=None),
        ), patch(
            "hydra.api.v1.services.discovery.mac_resolver.resolve_via_agent",
            AsyncMock(return_value=None),
        ) as mock_agent:
            mac = await resolve_mac(
                "192.168.1.5", "n1", db={}, commands_service=commands_service
            )
        assert mac is None
        mock_agent.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_network_skips_remote_strategies(self):
        with patch(
            "hydra.api.v1.services.discovery.mac_resolver.resolve_via_local_arp",
            return_value=None,
        ), patch(
            "hydra.api.v1.services.discovery.mac_resolver.resolve_via_router_snmp",
            AsyncMock(),
        ) as mock_snmp:
            mac = await resolve_mac("192.168.1.5", None, db={})
        assert mac is None
        mock_snmp.assert_not_called()


class TestMigrateIpToMac:
    @pytest.mark.asyncio
    async def test_no_existing_record_is_noop(self):
        devices = MagicMock()
        devices.find_one = AsyncMock(return_value=None)
        result = await migrate_ip_to_mac(devices, "192.168.1.5", "aa:bb:cc:dd:ee:ff", "n1")
        assert result is None

    @pytest.mark.asyncio
    async def test_rekey_when_no_mac_record_exists(self):
        old = {
            "_id": "doc1",
            "discoveryId": "disc::ip::n1::192.168.1.5",
            "identity": {"primaryMac": None},
        }
        merged = {**old, "discoveryId": "disc::mac::aa-bb-cc-dd-ee-ff"}
        devices = MagicMock()
        # 1. find_one(old_id) → old; 2. find_one(new_id) → None; 3. find_one(_id) → merged
        devices.find_one = AsyncMock(side_effect=[old, None, merged])
        devices.update_one = AsyncMock()
        devices.delete_one = AsyncMock()

        result = await migrate_ip_to_mac(
            devices,
            "192.168.1.5",
            "AA:BB:CC:DD:EE:FF",
            "n1",
            now=datetime(2026, 4, 16, tzinfo=UTC),
        )

        assert result is merged
        update_doc = devices.update_one.call_args.args[1]["$set"]
        assert update_doc["discoveryId"] == "disc::mac::aa-bb-cc-dd-ee-ff"
        assert update_doc["identity.primaryMac"] == "AA:BB:CC:DD:EE:FF"
        assert update_doc["identity.macResolved"] is True
        devices.delete_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_merge_when_mac_record_exists(self):
        old = {
            "_id": "doc-old",
            "discoveryId": "disc::ip::n1::192.168.1.5",
            "openPorts": [80],
            "protocols": ["http"],
            "seenCount": 3,
            "lastSeen": datetime(2026, 4, 14, tzinfo=UTC),
            "identity": {"observedIps": [{"address": "192.168.1.5"}]},
        }
        new = {
            "_id": "doc-new",
            "discoveryId": "disc::mac::aa-bb-cc-dd-ee-ff",
            "openPorts": [22, 80],
            "protocols": ["ssh"],
            "seenCount": 5,
            "lastSeen": datetime(2026, 4, 15, tzinfo=UTC),
            "identity": {
                "primaryMac": "aa:bb:cc:dd:ee:ff",
                "observedIps": [{"address": "192.168.10.5"}],
            },
        }
        merged_doc = {**new, "openPorts": [22, 80], "seenCount": 8}
        devices = MagicMock()
        devices.find_one = AsyncMock(side_effect=[old, new, merged_doc])
        devices.update_one = AsyncMock()
        devices.delete_one = AsyncMock()

        result = await migrate_ip_to_mac(
            devices, "192.168.1.5", "aa:bb:cc:dd:ee:ff", "n1",
            now=datetime(2026, 4, 16, tzinfo=UTC),
        )

        assert result is merged_doc
        # Old record deleted
        devices.delete_one.assert_called_once_with({"_id": "doc-old"})
        # New record updated with unioned ports/protocols
        update_call = devices.update_one.call_args.args[1]["$set"]
        assert sorted(update_call["openPorts"]) == [22, 80]
        assert sorted(update_call["protocols"]) == ["http", "ssh"]
        assert update_call["seenCount"] == 8
        assert update_call["_mergedFrom"] == "disc::ip::n1::192.168.1.5"

    @pytest.mark.asyncio
    async def test_idempotent_after_rekey(self):
        # Second call: the IP-only record no longer exists → no-op.
        devices = MagicMock()
        devices.find_one = AsyncMock(return_value=None)
        devices.update_one = AsyncMock()

        result = await migrate_ip_to_mac(devices, "192.168.1.5", "aa:bb:cc:dd:ee:ff", "n1")
        assert result is None
        devices.update_one.assert_not_called()
