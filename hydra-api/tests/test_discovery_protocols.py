"""Tests for the protocol discovery module."""

from __future__ import annotations

import struct
from unittest.mock import patch

import pytest

from hydra.api.v1.services.discovery.protocols import (
    MdnsResult,
    ProtocolDiscoveryResults,
    SnmpDeviceResult,
    SsdpResult,
    _parse_dns_name,
    _parse_dns_txt,
    _parse_lldp_frame,
    _parse_mdns_response,
    discover_lldp,
    run_protocol_discovery,
)

# ── DNS Parsing ──────────────────────────────────────────────────────


class TestDnsParsing:
    """Tests for DNS name and TXT record parsing."""

    def test_parse_simple_name(self):
        # Encode "_http._tcp.local"
        data = b"\x05_http\x04_tcp\x05local\x00"
        name, offset = _parse_dns_name(data, 0)
        assert name == "_http._tcp.local"
        assert offset == len(data)

    def test_parse_empty_name(self):
        data = b"\x00"
        name, offset = _parse_dns_name(data, 0)
        assert name == ""
        assert offset == 1

    def test_parse_txt_key_value(self):
        txt_data = b"\x06key=42\x0banother=yes"
        result = _parse_dns_txt(txt_data, 0, len(txt_data))
        assert result == {"key": "42", "another": "yes"}

    def test_parse_txt_empty(self):
        result = _parse_dns_txt(b"", 0, 0)
        assert result == {}


# ── mDNS Response Parsing ────────────────────────────────────────────


class TestMdnsResponseParsing:
    """Tests for mDNS response packet parsing."""

    def test_parse_mdns_response_too_short(self):
        results: dict[str, MdnsResult] = {}
        _parse_mdns_response(b"\x00" * 5, "192.168.1.1", results)
        assert len(results) == 0

    def test_parse_mdns_response_creates_entry(self):
        # Build a minimal mDNS response with 0 questions, 1 answer (PTR)
        header = struct.pack("!HHHHHH", 0, 0x8400, 0, 1, 0, 0)
        # Answer: name=_services._dns-sd._udp.local, type=PTR, class=IN, TTL=60
        name = b"\x09_services\x07_dns-sd\x04_udp\x05local\x00"
        ptr_target = b"\x05_http\x04_tcp\x05local\x00"
        answer = name + struct.pack("!HHI", 12, 1, 60) + struct.pack("!H", len(ptr_target)) + ptr_target
        data = header + answer

        results: dict[str, MdnsResult] = {}
        _parse_mdns_response(data, "192.168.1.100", results)
        assert "192.168.1.100" in results
        entry = results["192.168.1.100"]
        assert any("_http._tcp.local" in s for s in entry.services)


# ── LLDP Frame Parsing ───────────────────────────────────────────────


class TestLldpFrameParsing:
    """Tests for LLDP TLV parsing."""

    def test_parse_lldp_frame_too_short(self):
        assert _parse_lldp_frame(b"\x00" * 10) is None

    def test_parse_lldp_frame_with_system_name(self):
        # Ethernet header (14 bytes)
        eth = b"\x01\x80\xc2\x00\x00\x0e" + b"\xaa\xbb\xcc\xdd\xee\xff" + b"\x88\xcc"

        # TLV: Chassis ID (type=1, subtype=4 MAC)
        chassis_value = b"\x04\xaa\xbb\xcc\xdd\xee\xff"
        chassis_tlv = struct.pack("!H", (1 << 9) | len(chassis_value)) + chassis_value

        # TLV: Port ID (type=2, subtype=5 interface name)
        port_value = b"\x05eth0"
        port_tlv = struct.pack("!H", (2 << 9) | len(port_value)) + port_value

        # TLV: System Name (type=5)
        sysname = b"switch-01"
        sysname_tlv = struct.pack("!H", (5 << 9) | len(sysname)) + sysname

        # TLV: End (type=0)
        end_tlv = struct.pack("!H", 0)

        data = eth + chassis_tlv + port_tlv + sysname_tlv + end_tlv
        result = _parse_lldp_frame(data)
        assert result is not None
        assert result.system_name == "switch-01"

    def test_parse_lldp_frame_no_useful_data(self):
        eth = b"\x00" * 14
        end_tlv = struct.pack("!H", 0)
        assert _parse_lldp_frame(eth + end_tlv) is None


# ── LLDP Graceful Degradation ────────────────────────────────────────


class TestLldpGracefulDegradation:
    """LLDP should return None when CAP_NET_RAW is unavailable."""

    @pytest.mark.asyncio
    async def test_lldp_returns_none_without_privileges(self):
        with patch(
            "hydra.api.v1.services.discovery.protocols.socket.socket",
            side_effect=PermissionError("Operation not permitted"),
        ):
            result = await discover_lldp(timeout=0.1)
            assert result is None


# ── Protocol Discovery Results ───────────────────────────────────────


class TestProtocolDiscoveryResults:
    """Tests for the ProtocolDiscoveryResults consolidation."""

    def test_results_by_ip_mdns(self):
        results = ProtocolDiscoveryResults(
            mdns=[
                MdnsResult(
                    ip="192.168.1.10",
                    hostname="light.local",
                    services=["_hue._tcp.local"],
                    txt_records={"model": "LCT007"},
                ),
            ],
        )
        by_ip = results.results_by_ip()
        assert "192.168.1.10" in by_ip
        assert by_ip["192.168.1.10"]["mdns"]["hostname"] == "light.local"
        assert "_hue._tcp.local" in by_ip["192.168.1.10"]["mdns"]["services"]

    def test_results_by_ip_ssdp(self):
        results = ProtocolDiscoveryResults(
            ssdp=[
                SsdpResult(
                    ip="192.168.1.20",
                    server="Linux/5.15 UPnP/1.1",
                    device_type="urn:schemas-upnp-org:device:ZonePlayer:1",
                ),
            ],
        )
        by_ip = results.results_by_ip()
        assert "192.168.1.20" in by_ip
        assert "ZonePlayer" in by_ip["192.168.1.20"]["ssdp"]["deviceType"]

    def test_results_by_ip_snmp(self):
        results = ProtocolDiscoveryResults(
            snmp=[
                SnmpDeviceResult(
                    ip="192.168.1.1",
                    sys_descr="RouterOS 7.10",
                    sys_name="gw",
                ),
            ],
        )
        by_ip = results.results_by_ip()
        assert by_ip["192.168.1.1"]["snmp"]["sysDescr"] == "RouterOS 7.10"

    def test_results_by_ip_merges_multiple_protocols(self):
        results = ProtocolDiscoveryResults(
            mdns=[MdnsResult(ip="192.168.1.5", services=["_http._tcp.local"])],
            ssdp=[SsdpResult(ip="192.168.1.5", server="MyDevice/1.0")],
        )
        by_ip = results.results_by_ip()
        entry = by_ip["192.168.1.5"]
        assert "mdns" in entry
        assert "ssdp" in entry

    def test_results_by_ip_empty(self):
        results = ProtocolDiscoveryResults()
        assert results.results_by_ip() == {}


# ── Run Protocol Discovery Orchestrator ──────────────────────────────


class TestRunProtocolDiscovery:
    """Tests for the run_protocol_discovery orchestrator."""

    @pytest.mark.asyncio
    async def test_runs_mdns_and_ssdp(self):
        with (
            patch(
                "hydra.api.v1.services.discovery.protocols.discover_mdns",
                return_value=[MdnsResult(ip="10.0.0.1", services=["_http._tcp"])],
            ),
            patch(
                "hydra.api.v1.services.discovery.protocols.discover_ssdp",
                return_value=[SsdpResult(ip="10.0.0.2", server="UPnP/1.1")],
            ),
        ):
            results = await run_protocol_discovery(
                include_mdns=True,
                include_ssdp=True,
                include_lldp=False,
                timeout=0.1,
            )
            assert len(results.mdns) == 1
            assert len(results.ssdp) == 1
            assert results.mdns[0].ip == "10.0.0.1"
            assert results.ssdp[0].ip == "10.0.0.2"

    @pytest.mark.asyncio
    async def test_skips_disabled_protocols(self):
        with (
            patch(
                "hydra.api.v1.services.discovery.protocols.discover_mdns",
            ) as mock_mdns,
            patch(
                "hydra.api.v1.services.discovery.protocols.discover_ssdp",
            ) as mock_ssdp,
        ):
            await run_protocol_discovery(
                include_mdns=False,
                include_ssdp=False,
                include_lldp=False,
                timeout=0.1,
            )
            mock_mdns.assert_not_awaited()
            mock_ssdp.assert_not_awaited()
