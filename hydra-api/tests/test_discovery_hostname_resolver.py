"""Tests for the hostname resolver."""

from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from hydra.api.v1.models.discovery.enums import HostnameSource
from hydra.api.v1.services.discovery.hostname_resolver import (
    _is_plausible_hostname,
    extract_hostname_from_title,
    resolve_hostname,
    reverse_dns,
)


class TestIsPlausibleHostname:
    @pytest.mark.parametrize(
        "value",
        ["bedroom-pi", "core-switch.lan", "pve.local", "router1", "a", "x.y.z.example"],
    )
    def test_accepts_valid(self, value):
        assert _is_plausible_hostname(value)

    @pytest.mark.parametrize(
        "value",
        [None, "", "   ", "192.168.1.1", "10.0.0.1", "-foo", "foo-", "foo..bar", "x" * 70],
    )
    def test_rejects_invalid(self, value):
        assert not _is_plausible_hostname(value)


class TestExtractHostnameFromTitle:
    @pytest.mark.parametrize(
        "title,expected",
        [
            ("pve - Proxmox Virtual Environment", "pve"),
            ("OPNsense.lan - Dashboard", "opnsense.lan"),
            ("router1 | Home Assistant", "router1"),
            ("openwrt — LuCI", "openwrt"),
            ("Just a Long Title", None),  # Spaces in candidate → invalid
            ("192.168.1.1 - Router", None),  # IP-like
            ("", None),
        ],
    )
    def test_extraction(self, title, expected):
        assert extract_hostname_from_title(title) == expected


class TestReverseDns:
    @pytest.mark.asyncio
    async def test_returns_hostname_on_success(self):
        with patch(
            "hydra.api.v1.services.discovery.hostname_resolver.socket.gethostbyaddr",
            return_value=("router.lan", [], ["192.168.1.1"]),
        ):
            result = await reverse_dns("192.168.1.1")
        assert result == "router.lan"

    @pytest.mark.asyncio
    async def test_returns_none_on_herror(self):
        with patch(
            "hydra.api.v1.services.discovery.hostname_resolver.socket.gethostbyaddr",
            side_effect=socket.herror("not found"),
        ):
            result = await reverse_dns("192.168.99.99")
        assert result is None

    @pytest.mark.asyncio
    async def test_rejects_implausible_response(self):
        # Pi-hole sometimes returns the IP itself for unknown PTRs
        with patch(
            "hydra.api.v1.services.discovery.hostname_resolver.socket.gethostbyaddr",
            return_value=("192.168.1.1", [], ["192.168.1.1"]),
        ):
            result = await reverse_dns("192.168.1.1")
        assert result is None


class TestResolveHostname:
    @pytest.mark.asyncio
    async def test_picks_mdns_over_snmp(self):
        chosen, sources = await resolve_hostname(
            ip="192.168.1.5",
            banners={"161": "sysName=core-switch"},
            protocol_details={"mdns": {"hostname": "bedroom-pi.local"}},
            do_dns_reverse=False,
        )
        assert chosen == "bedroom-pi.local"
        assert HostnameSource.MDNS in sources
        assert HostnameSource.SNMP in sources

    @pytest.mark.asyncio
    async def test_picks_snmp_when_no_mdns(self):
        chosen, sources = await resolve_hostname(
            ip="192.168.1.5",
            banners={"161": "sysDescr=router; sysName=core-switch"},
            protocol_details={},
            do_dns_reverse=False,
        )
        assert chosen == "core-switch"
        assert sources == [HostnameSource.SNMP]

    @pytest.mark.asyncio
    async def test_picks_snmp_from_protocol_details(self):
        chosen, sources = await resolve_hostname(
            ip="192.168.1.5",
            protocol_details={"snmp": {"sysName": "edge-router"}},
            do_dns_reverse=False,
        )
        assert chosen == "edge-router"
        assert sources == [HostnameSource.SNMP]

    @pytest.mark.asyncio
    async def test_picks_lldp_under_snmp_slot(self):
        chosen, sources = await resolve_hostname(
            ip="192.168.1.5",
            protocol_details={"lldp": {"systemName": "core-switch"}},
            do_dns_reverse=False,
        )
        assert chosen == "core-switch"
        assert HostnameSource.SNMP in sources

    @pytest.mark.asyncio
    async def test_http_title_when_only_source(self):
        chosen, sources = await resolve_hostname(
            ip="192.168.1.5",
            banners={"443": "server=nginx; title=opnsense.lan - Dashboard"},
            do_dns_reverse=False,
        )
        assert chosen == "opnsense.lan"
        assert sources == [HostnameSource.HTTP_TITLE]

    @pytest.mark.asyncio
    async def test_dns_reverse_only_when_nothing_else(self):
        with patch(
            "hydra.api.v1.services.discovery.hostname_resolver.reverse_dns",
            return_value="dhcp-host.lan",
        ) as mock_dns:
            chosen, sources = await resolve_hostname(
                ip="192.168.1.5",
                do_dns_reverse=True,
            )
        assert chosen == "dhcp-host.lan"
        assert sources == [HostnameSource.DNS_REVERSE]
        mock_dns.assert_called_once()

    @pytest.mark.asyncio
    async def test_dns_reverse_skipped_when_other_source_present(self):
        with patch(
            "hydra.api.v1.services.discovery.hostname_resolver.reverse_dns",
        ) as mock_dns:
            chosen, sources = await resolve_hostname(
                ip="192.168.1.5",
                protocol_details={"mdns": {"hostname": "thermo.local"}},
                do_dns_reverse=True,
            )
        assert chosen == "thermo.local"
        mock_dns.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_evidence_returns_none(self):
        chosen, sources = await resolve_hostname(
            ip="192.168.1.5",
            do_dns_reverse=False,
        )
        assert chosen is None
        assert sources == []

    @pytest.mark.asyncio
    async def test_rejects_ip_like_mdns_value(self):
        # mDNS sometimes returns "192.168.1.5.in-addr.arpa" for nameless devices
        chosen, _ = await resolve_hostname(
            ip="192.168.1.5",
            protocol_details={"mdns": {"hostname": "192.168.1.5"}},
            do_dns_reverse=False,
        )
        assert chosen is None
