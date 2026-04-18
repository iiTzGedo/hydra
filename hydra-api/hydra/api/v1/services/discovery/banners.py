"""Protocol-specific banner grabbing for network discovery.

Provides asyncio-based banner grabbers for SSH, SNMP, MQTT, and HTTP.
All grabbers use pure Python — no external libraries (pysnmp, paho, etc.).
Each grabber returns a banner string or ``None`` on timeout/failure.
"""

from __future__ import annotations

import asyncio
import re
import socket
import struct
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# ── SNMP v1 helpers ──────────────────────────────────────────────────

# Pre-built SNMPv1 GET-REQUEST PDU for sysDescr.0 (1.3.6.1.2.1.1.1.0)
# BER-encoded:
#   SEQUENCE {
#     INTEGER version (0 = v1)
#     OCTET STRING community ("public")
#     GetRequest-PDU {
#       INTEGER request-id (1)
#       INTEGER error-status (0)
#       INTEGER error-index (0)
#       SEQUENCE OF { SEQUENCE { OID sysDescr.0, NULL } }
#     }
#   }
_SNMP_SYSDESCR_OID = bytes([
    0x06, 0x08, 0x2b, 0x06, 0x01, 0x02, 0x01, 0x01, 0x01, 0x00,
])

_SNMP_SYSNAME_OID = bytes([
    0x06, 0x08, 0x2b, 0x06, 0x01, 0x02, 0x01, 0x01, 0x05, 0x00,
])

_SNMP_SYSOBJECTID_OID = bytes([
    0x06, 0x08, 0x2b, 0x06, 0x01, 0x02, 0x01, 0x01, 0x02, 0x00,
])


def _ber_length(length: int) -> bytes:
    """Encode a BER definite-length value."""
    if length < 0x80:
        return bytes([length])
    if length < 0x100:
        return bytes([0x81, length])
    return bytes([0x82, (length >> 8) & 0xFF, length & 0xFF])


def _ber_sequence(tag: int, contents: bytes) -> bytes:
    """Wrap contents in a BER tag + length."""
    return bytes([tag]) + _ber_length(len(contents)) + contents


def _ber_integer(value: int) -> bytes:
    """Encode a BER INTEGER."""
    if value == 0:
        return b"\x02\x01\x00"
    data = value.to_bytes((value.bit_length() + 8) // 8, "big", signed=True)
    return bytes([0x02, len(data)]) + data


def _ber_octet_string(value: bytes) -> bytes:
    """Encode a BER OCTET STRING."""
    return bytes([0x04]) + _ber_length(len(value)) + value


def _build_snmp_get(community: str, oid_bytes: bytes, request_id: int = 1) -> bytes:
    """Build an SNMPv1 GET-REQUEST PDU."""
    # VarBind: SEQUENCE { OID, NULL }
    varbind = _ber_sequence(0x30, oid_bytes + b"\x05\x00")
    # VarBindList: SEQUENCE OF VarBind
    varbind_list = _ber_sequence(0x30, varbind)
    # GetRequest-PDU (tag 0xA0)
    pdu_body = (
        _ber_integer(request_id)
        + _ber_integer(0)  # error-status
        + _ber_integer(0)  # error-index
        + varbind_list
    )
    pdu = _ber_sequence(0xA0, pdu_body)
    # Full message: SEQUENCE { version, community, PDU }
    message_body = (
        _ber_integer(0)  # version 0 = SNMPv1
        + _ber_octet_string(community.encode())
        + pdu
    )
    return _ber_sequence(0x30, message_body)


def _parse_snmp_response(data: bytes) -> str | None:
    """Extract the first OCTET STRING value from an SNMP response.

    Performs minimal BER parsing — walks to the first VarBind value
    and extracts its OCTET STRING content.  Returns ``None`` if the
    response cannot be parsed.
    """
    try:
        # Walk into: SEQUENCE -> skip version, community -> GetResponse-PDU
        # -> skip request-id, error-status, error-index -> VarBindList
        # -> VarBind -> skip OID -> value (OCTET STRING)
        pos = 0

        def _read_tag_length(buf: bytes, offset: int) -> tuple[int, int, int]:
            tag = buf[offset]
            offset += 1
            length_byte = buf[offset]
            offset += 1
            if length_byte < 0x80:
                return tag, length_byte, offset
            num_bytes = length_byte & 0x7F
            length = int.from_bytes(buf[offset:offset + num_bytes], "big")
            return tag, length, offset + num_bytes

        # Outer SEQUENCE
        _, _, pos = _read_tag_length(data, pos)
        # version INTEGER
        _, vlen, pos = _read_tag_length(data, pos)
        pos += vlen
        # community OCTET STRING
        _, clen, pos = _read_tag_length(data, pos)
        pos += clen
        # GetResponse-PDU (0xA2)
        tag, _, pos = _read_tag_length(data, pos)
        if tag != 0xA2:
            return None
        # request-id
        _, rlen, pos = _read_tag_length(data, pos)
        pos += rlen
        # error-status
        _, elen, pos = _read_tag_length(data, pos)
        pos += elen
        # error-index
        _, ilen, pos = _read_tag_length(data, pos)
        pos += ilen
        # VarBindList SEQUENCE
        _, _, pos = _read_tag_length(data, pos)
        # First VarBind SEQUENCE
        _, _, pos = _read_tag_length(data, pos)
        # OID
        _, oid_len, pos = _read_tag_length(data, pos)
        pos += oid_len
        # Value (expect OCTET STRING 0x04 or OID 0x06)
        value_tag, value_len, pos = _read_tag_length(data, pos)
        if value_tag == 0x04:  # OCTET STRING
            return data[pos:pos + value_len].decode("utf-8", errors="replace")
        if value_tag == 0x06:  # OID — return dotted notation
            return _decode_oid(data[pos:pos + value_len])
        return None
    except (IndexError, ValueError):
        return None


def _decode_oid(data: bytes) -> str:
    """Decode a BER-encoded OID into dotted notation."""
    if not data:
        return ""
    parts = [str(data[0] // 40), str(data[0] % 40)]
    value = 0
    for byte in data[1:]:
        value = (value << 7) | (byte & 0x7F)
        if not (byte & 0x80):
            parts.append(str(value))
            value = 0
    return ".".join(parts)


# ── MQTT helpers ─────────────────────────────────────────────────────

def _build_mqtt_connect() -> bytes:
    """Build a minimal MQTT 3.1.1 CONNECT packet."""
    # Variable header
    protocol_name = b"\x00\x04MQTT"
    protocol_level = b"\x04"  # MQTT 3.1.1
    connect_flags = b"\x02"  # Clean session
    keep_alive = struct.pack("!H", 60)
    # Payload: client ID
    client_id = b"hydra-probe"
    client_id_field = struct.pack("!H", len(client_id)) + client_id

    variable_header = protocol_name + protocol_level + connect_flags + keep_alive
    payload = client_id_field
    remaining = variable_header + payload

    # Fixed header: CONNECT (0x10) + remaining length
    header = bytes([0x10]) + _encode_remaining_length(len(remaining))
    return header + remaining


def _encode_remaining_length(length: int) -> bytes:
    """Encode MQTT remaining length (variable-length encoding)."""
    encoded = bytearray()
    while True:
        byte = length % 128
        length = length // 128
        if length > 0:
            byte |= 0x80
        encoded.append(byte)
        if length == 0:
            break
    return bytes(encoded)


# ── Banner Grabbers ──────────────��───────────────────────────────────


async def grab_ssh_banner(host: str, timeout: float = 2.0) -> str | None:
    """Read the SSH version banner from port 22.

    SSH servers send their identification string immediately upon TCP
    connection (RFC 4253 §4.2).  Returns the raw banner string, e.g.
    ``SSH-2.0-OpenSSH_9.6``.
    """
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, 22),
            timeout=timeout,
        )
        try:
            line = await asyncio.wait_for(reader.readline(), timeout=timeout)
            return line.decode("utf-8", errors="replace").strip() or None
        finally:
            writer.close()
            await writer.wait_closed()
    except (OSError, TimeoutError, ConnectionRefusedError, ConnectionResetError):
        return None


async def grab_snmp_info(
    host: str,
    community: str = "public",
    timeout: float = 2.0,
) -> dict[str, str | None] | None:
    """Query SNMP sysDescr, sysName, and sysObjectID via raw SNMPv1.

    Constructs BER-encoded GET-REQUEST PDUs and sends them via UDP.
    Returns a dict with ``sysDescr``, ``sysName``, ``sysObjectID`` keys.
    """
    results: dict[str, str | None] = {}
    queries = [
        ("sysDescr", _SNMP_SYSDESCR_OID, 1),
        ("sysName", _SNMP_SYSNAME_OID, 2),
        ("sysObjectID", _SNMP_SYSOBJECTID_OID, 3),
    ]

    loop = asyncio.get_running_loop()

    for field_name, oid_bytes, request_id in queries:
        try:
            pdu = _build_snmp_get(community, oid_bytes, request_id)
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            sock.setblocking(False)

            transport, protocol = await loop.create_datagram_endpoint(
                lambda: asyncio.DatagramProtocol(),
                sock=sock,
            )
            try:
                transport.sendto(pdu, (host, 161))
                data = await asyncio.wait_for(
                    _recv_udp(loop, sock),
                    timeout=timeout,
                )
                results[field_name] = _parse_snmp_response(data)
            finally:
                transport.close()
        except (OSError, TimeoutError):
            results[field_name] = None

    if not any(results.values()):
        return None
    return results


async def _recv_udp(loop: asyncio.AbstractEventLoop, sock: socket.socket) -> bytes:
    """Receive a UDP datagram asynchronously."""
    future: asyncio.Future[bytes] = loop.create_future()

    def _reader() -> None:
        try:
            data = sock.recv(4096)
            if not future.done():
                future.set_result(data)
        except Exception as exc:
            if not future.done():
                future.set_exception(exc)
        finally:
            loop.remove_reader(sock.fileno())

    loop.add_reader(sock.fileno(), _reader)
    return await future


async def grab_mqtt_banner(
    host: str,
    port: int = 1883,
    timeout: float = 2.0,
) -> str | None:
    """Send an MQTT CONNECT and read the CONNACK response.

    Returns a string like ``mqtt:connack:0`` (return code) or ``None``.
    """
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
        try:
            writer.write(_build_mqtt_connect())
            await writer.drain()
            data = await asyncio.wait_for(reader.read(4), timeout=timeout)
            if len(data) >= 4 and data[0] == 0x20:  # CONNACK
                return_code = data[3]
                return f"mqtt:connack:{return_code}"
            return None
        finally:
            writer.close()
            await writer.wait_closed()
    except (OSError, TimeoutError, ConnectionRefusedError, ConnectionResetError):
        return None


_HTTP_TITLE_TAG_RE = re.compile(
    rb"<title[^>]*>([^<]+)</title>",
    re.IGNORECASE | re.DOTALL,
)


async def _http_get_title(
    host: str,
    port: int,
    timeout: float,
) -> str | None:
    """GET / and pull the first ``<title>`` value, if any.

    Caps the read at 8 KiB so a giant SPA payload can't hang the scanner.
    """
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
        try:
            request = (
                f"GET / HTTP/1.0\r\n"
                f"Host: {host}\r\n"
                f"Accept: text/html\r\n"
                f"Connection: close\r\n"
                f"\r\n"
            )
            writer.write(request.encode())
            await writer.drain()
            body = await asyncio.wait_for(reader.read(8192), timeout=timeout)
        finally:
            writer.close()
            await writer.wait_closed()
    except (OSError, TimeoutError, ConnectionRefusedError, ConnectionResetError):
        return None

    match = _HTTP_TITLE_TAG_RE.search(body)
    if not match:
        return None
    try:
        title = match.group(1).decode("utf-8", errors="replace").strip()
    except (UnicodeDecodeError, AttributeError):
        return None
    # Collapse internal whitespace (titles often span lines).
    title = " ".join(title.split())
    return title or None


async def grab_http_banner(
    host: str,
    port: int,
    timeout: float = 2.0,
) -> str | None:
    """Send an HTTP HEAD request, extract the Server header and `<title>`.

    Returns a semicolon-separated banner string with `server=...` and
    optionally `; title=...`. Falls back to the status line if no Server
    header is present.
    """
    server: str | None = None
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
        try:
            request = (
                f"HEAD / HTTP/1.0\r\n"
                f"Host: {host}\r\n"
                f"Connection: close\r\n"
                f"\r\n"
            )
            writer.write(request.encode())
            await writer.drain()
            response = await asyncio.wait_for(
                reader.read(2048),
                timeout=timeout,
            )
            text = response.decode("utf-8", errors="replace")
            for line in text.split("\r\n"):
                if line.lower().startswith("server:"):
                    server = line.split(":", 1)[1].strip()
                    break
            if server is None:
                # Fallback: status line provides a coarse identity hint
                first_line = text.split("\r\n", 1)[0]
                if first_line.startswith("HTTP/"):
                    server = first_line
        finally:
            writer.close()
            await writer.wait_closed()
    except (OSError, TimeoutError, ConnectionRefusedError, ConnectionResetError):
        server = None

    title = await _http_get_title(host, port, timeout)

    if server and title:
        return f"server={server}; title={title}"
    if server:
        return server
    if title:
        return f"title={title}"
    return None


# ── HTTP Ports ───────────────────────────────────────────────────────

_HTTP_PORTS = frozenset({
    80, 443, 3000, 5000, 5001, 8000, 8006, 8008,
    8080, 8081, 8088, 8090, 8123, 8181, 8291,
    8443, 8444, 8500, 8834, 8888, 8983,
    9000, 9001, 9090, 9100, 9200, 9443, 15672,
})


# ── Orchestrator ─────────────────────────────────────────────────────


async def grab_banners(
    host: str,
    open_ports: list[int],
    timeout: float = 2.0,
) -> dict[str, str]:
    """Grab banners from all applicable open ports concurrently.

    Dispatches to protocol-specific grabbers based on port number.
    Returns a dict mapping port number (as string) to banner string.
    """
    tasks: dict[str, asyncio.Task[str | None | dict[str, Any]]] = {}
    port_set = frozenset(open_ports)

    if 22 in port_set:
        tasks["22"] = asyncio.create_task(grab_ssh_banner(host, timeout))

    if 161 in port_set:
        tasks["161"] = asyncio.create_task(grab_snmp_info(host, timeout=timeout))

    if 1883 in port_set:
        tasks["1883"] = asyncio.create_task(grab_mqtt_banner(host, 1883, timeout))
    if 8883 in port_set:
        tasks["8883"] = asyncio.create_task(grab_mqtt_banner(host, 8883, timeout))

    for port in port_set:
        port_str = str(port)
        if port in _HTTP_PORTS and port_str not in tasks:
            tasks[port_str] = asyncio.create_task(
                grab_http_banner(host, port, timeout),
            )

    banners: dict[str, str] = {}
    for port_str, task in tasks.items():
        try:
            result = await task
            if result is None:
                continue
            if isinstance(result, dict):
                # SNMP info → serialize to combined banner string
                parts = []
                for key in ("sysDescr", "sysName", "sysObjectID"):
                    val = result.get(key)
                    if val:
                        parts.append(f"{key}={val}")
                if parts:
                    banners[port_str] = "; ".join(parts)
            elif isinstance(result, str):
                banners[port_str] = result
        except Exception:
            logger.debug("banner_grab_failed", host=host, port=port_str)

    return banners
