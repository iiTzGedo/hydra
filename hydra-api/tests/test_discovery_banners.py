"""Tests for the banner grabbing module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hydra.api.v1.services.discovery.banners import (
    _SNMP_SYSDESCR_OID,
    _build_mqtt_connect,
    _build_snmp_get,
    _parse_snmp_response,
    grab_banners,
    grab_http_banner,
    grab_mqtt_banner,
    grab_ssh_banner,
)

# ── SNMP PDU Construction ────────────────────────────────────────────


class TestSnmpPduConstruction:
    """Verify BER-encoded SNMP PDU is well-formed."""

    def test_build_snmp_get_returns_bytes(self):
        pdu = _build_snmp_get("public", _SNMP_SYSDESCR_OID, request_id=1)
        assert isinstance(pdu, bytes)
        # Outer tag must be SEQUENCE (0x30)
        assert pdu[0] == 0x30

    def test_build_snmp_get_community_is_embedded(self):
        pdu = _build_snmp_get("public", _SNMP_SYSDESCR_OID)
        assert b"public" in pdu

    def test_build_snmp_get_custom_community(self):
        pdu = _build_snmp_get("private", _SNMP_SYSDESCR_OID)
        assert b"private" in pdu

    def test_parse_snmp_response_invalid_data(self):
        assert _parse_snmp_response(b"\x00\x00") is None

    def test_parse_snmp_response_empty(self):
        assert _parse_snmp_response(b"") is None


# ── MQTT Packet Construction ─────────────────────────────────────────


class TestMqttPacketConstruction:
    """Verify MQTT CONNECT packet structure."""

    def test_build_mqtt_connect_starts_with_connect_type(self):
        packet = _build_mqtt_connect()
        assert packet[0] == 0x10  # CONNECT packet type

    def test_build_mqtt_connect_contains_protocol_name(self):
        packet = _build_mqtt_connect()
        assert b"MQTT" in packet

    def test_build_mqtt_connect_contains_client_id(self):
        packet = _build_mqtt_connect()
        assert b"hydra-probe" in packet


# ── SSH Banner Grabbing ──────────────────────────────────────────────


class TestGrabSshBanner:
    """Tests for grab_ssh_banner."""

    @pytest.mark.asyncio
    async def test_returns_banner_on_success(self):
        mock_reader = AsyncMock()
        mock_reader.readline = AsyncMock(
            return_value=b"SSH-2.0-OpenSSH_9.6\r\n",
        )
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        with patch(
            "hydra.api.v1.services.discovery.banners.asyncio.open_connection",
            return_value=(mock_reader, mock_writer),
        ):
            result = await grab_ssh_banner("192.168.1.1", timeout=1.0)
            assert result == "SSH-2.0-OpenSSH_9.6"

    @pytest.mark.asyncio
    async def test_returns_none_on_connection_refused(self):
        with patch(
            "hydra.api.v1.services.discovery.banners.asyncio.open_connection",
            side_effect=ConnectionRefusedError,
        ):
            result = await grab_ssh_banner("192.168.1.1", timeout=0.5)
            assert result is None


# ── MQTT Banner Grabbing ─────────────────────────────────────────────


class TestGrabMqttBanner:
    """Tests for grab_mqtt_banner."""

    @pytest.mark.asyncio
    async def test_returns_connack_on_success(self):
        mock_reader = AsyncMock()
        # CONNACK: 0x20, remaining=2, session_present=0, return_code=0
        mock_reader.read = AsyncMock(return_value=bytes([0x20, 0x02, 0x00, 0x00]))
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        with patch(
            "hydra.api.v1.services.discovery.banners.asyncio.open_connection",
            return_value=(mock_reader, mock_writer),
        ):
            result = await grab_mqtt_banner("192.168.1.1", 1883, timeout=1.0)
            assert result == "mqtt:connack:0"

    @pytest.mark.asyncio
    async def test_returns_none_on_timeout(self):
        with patch(
            "hydra.api.v1.services.discovery.banners.asyncio.open_connection",
            side_effect=TimeoutError,
        ):
            result = await grab_mqtt_banner("192.168.1.1", 1883, timeout=0.1)
            assert result is None


# ── HTTP Banner Grabbing ─────────────────────────────────────────────


class TestGrabHttpBanner:
    """Tests for grab_http_banner."""

    @pytest.mark.asyncio
    async def test_returns_server_header(self):
        mock_reader = AsyncMock()
        mock_reader.read = AsyncMock(
            return_value=b"HTTP/1.1 200 OK\r\nServer: nginx/1.24\r\n\r\n",
        )
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        with patch(
            "hydra.api.v1.services.discovery.banners.asyncio.open_connection",
            return_value=(mock_reader, mock_writer),
        ):
            result = await grab_http_banner("192.168.1.1", 80, timeout=1.0)
            assert result == "nginx/1.24"

    @pytest.mark.asyncio
    async def test_falls_back_to_status_line(self):
        mock_reader = AsyncMock()
        mock_reader.read = AsyncMock(
            return_value=b"HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n",
        )
        mock_writer = MagicMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        with patch(
            "hydra.api.v1.services.discovery.banners.asyncio.open_connection",
            return_value=(mock_reader, mock_writer),
        ):
            result = await grab_http_banner("192.168.1.1", 80, timeout=1.0)
            assert result == "HTTP/1.0 200 OK"


# ── Banner Orchestrator ──────────────────────────────────────────────


class TestGrabBanners:
    """Tests for the grab_banners orchestrator."""

    @pytest.mark.asyncio
    async def test_dispatches_to_ssh_and_http(self):
        with (
            patch(
                "hydra.api.v1.services.discovery.banners.grab_ssh_banner",
                return_value="SSH-2.0-OpenSSH_9.6",
            ),
            patch(
                "hydra.api.v1.services.discovery.banners.grab_http_banner",
                return_value="Apache/2.4",
            ),
        ):
            result = await grab_banners(
                "192.168.1.1", [22, 80], timeout=1.0,
            )
            assert result["22"] == "SSH-2.0-OpenSSH_9.6"
            assert result["80"] == "Apache/2.4"

    @pytest.mark.asyncio
    async def test_empty_ports_returns_empty_dict(self):
        result = await grab_banners("192.168.1.1", [], timeout=1.0)
        assert result == {}

    @pytest.mark.asyncio
    async def test_none_results_are_excluded(self):
        with (
            patch(
                "hydra.api.v1.services.discovery.banners.grab_ssh_banner",
                return_value=None,
            ),
        ):
            result = await grab_banners("192.168.1.1", [22], timeout=1.0)
            assert "22" not in result

    @pytest.mark.asyncio
    async def test_mqtt_port_dispatched(self):
        with patch(
            "hydra.api.v1.services.discovery.banners.grab_mqtt_banner",
            return_value="mqtt:connack:0",
        ):
            result = await grab_banners(
                "192.168.1.1", [1883], timeout=1.0,
            )
            assert result.get("1883") == "mqtt:connack:0"

    @pytest.mark.asyncio
    async def test_snmp_port_dispatched(self):
        with patch(
            "hydra.api.v1.services.discovery.banners.grab_snmp_info",
            return_value={"sysDescr": "Linux router", "sysName": "gw", "sysObjectID": None},
        ):
            result = await grab_banners(
                "192.168.1.1", [161], timeout=1.0,
            )
            banner = result.get("161", "")
            assert "sysDescr=Linux router" in banner
            assert "sysName=gw" in banner
