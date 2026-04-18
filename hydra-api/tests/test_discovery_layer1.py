"""Tests for Layer 1 ARP and ICMP scanning."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from hydra.api.v1.services.discovery.layer1 import (
    CapabilityError,
    arp_scan,
    icmp_sweep,
)


class TestArpScan:
    @pytest.mark.asyncio
    async def test_capability_required(self):
        with patch(
            "hydra.api.v1.services.discovery.layer1.has_cap_net_raw",
            return_value=False,
        ), pytest.raises(CapabilityError):
            await arp_scan("192.168.1.0/24")

    @pytest.mark.asyncio
    async def test_ipv6_rejected(self):
        with patch(
            "hydra.api.v1.services.discovery.layer1.has_cap_net_raw",
            return_value=True,
        ), pytest.raises(ValueError, match="IPv4"):
            await arp_scan("fe80::/10")

    @pytest.mark.asyncio
    async def test_returns_ip_mac_map(self):
        # Mock scapy reply tuple structure: (sent, received) pairs.
        reply1 = MagicMock(psrc="192.168.1.1", hwsrc="AA:BB:CC:DD:EE:01")
        reply2 = MagicMock(psrc="192.168.1.2", hwsrc="AA:BB:CC:DD:EE:02")
        answered = [(MagicMock(), reply1), (MagicMock(), reply2)]

        with patch(
            "hydra.api.v1.services.discovery.layer1.has_cap_net_raw",
            return_value=True,
        ), patch("scapy.all.srp", return_value=(answered, [])) as mock_srp:
            result = await arp_scan("192.168.1.0/24", timeout=1.0)

        assert result == {
            "192.168.1.1": "aa:bb:cc:dd:ee:01",
            "192.168.1.2": "aa:bb:cc:dd:ee:02",
        }
        mock_srp.assert_called_once()
        # Verify timeout was forwarded
        assert mock_srp.call_args.kwargs["timeout"] == 1.0
        assert mock_srp.call_args.kwargs["verbose"] is False

    @pytest.mark.asyncio
    async def test_no_replies(self):
        with patch(
            "hydra.api.v1.services.discovery.layer1.has_cap_net_raw",
            return_value=True,
        ), patch("scapy.all.srp", return_value=([], [])):
            result = await arp_scan("192.168.99.0/30")
        assert result == {}


class TestIcmpSweep:
    @pytest.mark.asyncio
    async def test_capability_required(self):
        with patch(
            "hydra.api.v1.services.discovery.layer1.has_cap_net_raw",
            return_value=False,
        ), pytest.raises(CapabilityError):
            await icmp_sweep("192.168.1.0/24")

    @pytest.mark.asyncio
    async def test_returns_alive_set(self):
        reply1 = MagicMock(src="192.168.1.5")
        reply2 = MagicMock(src="192.168.1.7")
        answered = [(MagicMock(), reply1), (MagicMock(), reply2)]

        with patch(
            "hydra.api.v1.services.discovery.layer1.has_cap_net_raw",
            return_value=True,
        ), patch("scapy.all.sr", return_value=(answered, [])):
            alive = await icmp_sweep("192.168.1.0/29", timeout=0.5)

        assert alive == {"192.168.1.5", "192.168.1.7"}

    @pytest.mark.asyncio
    async def test_chunks_large_subnets(self):
        # /22 = 1022 hosts → should chunk
        with patch(
            "hydra.api.v1.services.discovery.layer1.has_cap_net_raw",
            return_value=True,
        ), patch("scapy.all.sr", return_value=([], [])) as mock_sr:
            await icmp_sweep("192.168.0.0/22", chunk_size=256)
        # 1022 hosts / 256 chunk = 4 calls (256 + 256 + 256 + 254)
        assert mock_sr.call_count == 4
