"""Tests for host network interface introspection."""

from __future__ import annotations

import socket
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hydra.api.v1.services.discovery.host_interfaces import (
    LocalNetwork,
    _derive_network_id,
    enumerate_local_networks,
    heal_invalid_seeded_types,
    introspect_and_seed,
    seed_or_update_networks,
)


def _addr(family: int, address: str, netmask: str | None = None):
    a = MagicMock()
    a.family = family
    a.address = address
    a.netmask = netmask
    return a


def _stats(isup: bool):
    s = MagicMock()
    s.isup = isup
    return s


class TestEnumerateLocalNetworks:
    def test_skips_loopback(self):
        psutil_mock = MagicMock()
        psutil_mock.net_if_addrs.return_value = {
            "lo": [_addr(socket.AF_INET, "127.0.0.1", "255.0.0.0")],
        }
        psutil_mock.net_if_stats.return_value = {"lo": _stats(True)}

        with patch.dict("sys.modules", {"psutil": psutil_mock}):
            assert enumerate_local_networks() == []

    def test_skips_link_local(self):
        psutil_mock = MagicMock()
        psutil_mock.net_if_addrs.return_value = {
            "eth0": [_addr(socket.AF_INET, "169.254.1.5", "255.255.0.0")],
        }
        psutil_mock.net_if_stats.return_value = {"eth0": _stats(True)}

        with patch.dict("sys.modules", {"psutil": psutil_mock}):
            assert enumerate_local_networks() == []

    def test_skips_down_interfaces(self):
        psutil_mock = MagicMock()
        psutil_mock.net_if_addrs.return_value = {
            "eth0": [_addr(socket.AF_INET, "192.168.1.5", "255.255.255.0")],
        }
        psutil_mock.net_if_stats.return_value = {"eth0": _stats(False)}

        with patch.dict("sys.modules", {"psutil": psutil_mock}):
            assert enumerate_local_networks() == []

    def test_returns_normal_interface(self):
        psutil_mock = MagicMock()
        af_packet = getattr(socket, "AF_PACKET", -1)
        psutil_mock.net_if_addrs.return_value = {
            "eth0": [
                _addr(socket.AF_INET, "192.168.1.5", "255.255.255.0"),
                _addr(af_packet, "AA:BB:CC:DD:EE:FF"),
            ],
        }
        psutil_mock.net_if_stats.return_value = {"eth0": _stats(True)}

        with patch.dict("sys.modules", {"psutil": psutil_mock}), patch(
            "hydra.api.v1.services.discovery.host_interfaces._read_default_gateway",
            return_value={"eth0": "192.168.1.1"},
        ):
            networks = enumerate_local_networks()

        assert len(networks) == 1
        assert networks[0] == LocalNetwork(
            interface="eth0",
            cidr="192.168.1.0/24",
            address="192.168.1.5",
            mac="aa:bb:cc:dd:ee:ff",
            gateway="192.168.1.1",
        )

    def test_psutil_missing(self):
        with patch.dict("sys.modules", {"psutil": None}):
            # ImportError path
            assert enumerate_local_networks() == []

    def test_psutil_raises(self):
        psutil_mock = MagicMock()
        psutil_mock.net_if_addrs.side_effect = OSError("boom")
        with patch.dict("sys.modules", {"psutil": psutil_mock}):
            assert enumerate_local_networks() == []


class TestDeriveNetworkId:
    def test_simple_iface(self):
        net = LocalNetwork("eth0", "192.168.1.0/24", "192.168.1.5", None, None)
        assert _derive_network_id(net) == "net-host-eth0"

    def test_vlan_iface(self):
        net = LocalNetwork("eth0.10", "10.0.10.0/24", "10.0.10.5", None, None)
        assert _derive_network_id(net) == "net-host-eth0-10"

    def test_dotted_iface(self):
        net = LocalNetwork("br:1", "10.0.0.0/24", "10.0.0.1", None, None)
        assert _derive_network_id(net) == "net-host-br-1"


class TestSeedOrUpdateNetworks:
    @pytest.mark.asyncio
    async def test_creates_new_network(self):
        db = MagicMock()
        db.__getitem__.return_value.find_one = AsyncMock(return_value=None)
        db.__getitem__.return_value.insert_one = AsyncMock()

        local = LocalNetwork(
            "eth0", "192.168.1.0/24", "192.168.1.5", "aa:bb:cc:dd:ee:ff", "192.168.1.1"
        )
        result = await seed_or_update_networks(db, [local])

        assert result == {"created": 1, "updated": 0}
        db.__getitem__.return_value.insert_one.assert_called_once()
        doc = db.__getitem__.return_value.insert_one.call_args.args[0]
        assert doc["networkId"] == "net-host-eth0"
        assert doc["cidr"] == "192.168.1.0/24"
        assert doc["scanConfig"]["status"] == "api-direct"
        assert doc["scanConfig"]["apiReachable"] is True
        assert doc["origin"]["createdBy"] == "api-host-introspection"
        # Must use a value from the NetworkType enum — `lan` is not valid
        # and would fail validation when later read by the networks router.
        from hydra.api.v1.models.networks import NetworkType
        assert doc["type"] in {t.value for t in NetworkType}

    @pytest.mark.asyncio
    async def test_updates_existing_network(self):
        existing = {"_id": "abc", "networkId": "net-existing", "cidr": "192.168.1.0/24"}
        db = MagicMock()
        db.__getitem__.return_value.find_one = AsyncMock(return_value=existing)
        db.__getitem__.return_value.update_one = AsyncMock()

        local = LocalNetwork("eth0", "192.168.1.0/24", "192.168.1.5", None, None)
        result = await seed_or_update_networks(db, [local])

        assert result == {"created": 0, "updated": 1}
        update_call = db.__getitem__.return_value.update_one.call_args
        update_doc = update_call.args[1]["$set"]
        assert update_doc["scanConfig.status"] == "api-direct"
        assert update_doc["scanConfig.apiReachable"] is True
        assert update_doc["scanConfig.apiReachabilityTest"]["method"] == "interface"

    @pytest.mark.asyncio
    async def test_idempotent_re_run(self):
        # First call → CIDR lookup None, networkId collision check None, insert.
        # Second call → CIDR lookup returns the inserted doc, update.
        existing = {"_id": "abc", "cidr": "192.168.1.0/24"}
        find_results = [None, None, existing]

        db = MagicMock()
        db.__getitem__.return_value.find_one = AsyncMock(side_effect=find_results)
        db.__getitem__.return_value.insert_one = AsyncMock()
        db.__getitem__.return_value.update_one = AsyncMock()

        local = LocalNetwork("eth0", "192.168.1.0/24", "192.168.1.5", None, None)
        await seed_or_update_networks(db, [local])
        await seed_or_update_networks(db, [local])

        # Created once, then updated once — no duplicates.
        assert db.__getitem__.return_value.insert_one.call_count == 1
        assert db.__getitem__.return_value.update_one.call_count == 1

    @pytest.mark.asyncio
    async def test_avoids_id_collision(self):
        # No CIDR match, but the derived networkId already exists on a different CIDR.
        db = MagicMock()
        db.__getitem__.return_value.find_one = AsyncMock(
            side_effect=[None, {"_id": "other"}],
        )
        db.__getitem__.return_value.insert_one = AsyncMock()

        local = LocalNetwork("eth0", "192.168.1.0/24", "192.168.1.5", None, None)
        result = await seed_or_update_networks(db, [local])

        assert result == {"created": 0, "updated": 0}
        db.__getitem__.return_value.insert_one.assert_not_called()


class TestHealInvalidSeededTypes:
    @pytest.mark.asyncio
    async def test_patches_invalid_lan_type(self):
        update_result = MagicMock(modified_count=2)
        db = MagicMock()
        db.__getitem__.return_value.update_many = AsyncMock(return_value=update_result)

        patched = await heal_invalid_seeded_types(db)

        assert patched == 2
        query = db.__getitem__.return_value.update_many.call_args.args[0]
        assert query["origin.createdBy"] == "api-host-introspection"
        # The query targets any row whose type isn't in the enum.
        assert "$nin" in query["type"]
        assert "physical" in query["type"]["$nin"]

        update_doc = db.__getitem__.return_value.update_many.call_args.args[1]
        assert update_doc == {"$set": {"type": "physical"}}

    @pytest.mark.asyncio
    async def test_returns_zero_on_db_failure(self):
        db = MagicMock()
        db.__getitem__.return_value.update_many = AsyncMock(side_effect=RuntimeError("db gone"))
        # Must never propagate during startup
        assert await heal_invalid_seeded_types(db) == 0


class TestIntrospectAndSeed:
    @pytest.mark.asyncio
    async def test_swallows_exceptions(self):
        db = MagicMock()
        with patch(
            "hydra.api.v1.services.discovery.host_interfaces.enumerate_local_networks",
            side_effect=RuntimeError("boom"),
        ):
            result = await introspect_and_seed(db)
        # Must never raise during startup
        assert result == {"created": 0, "updated": 0}
