"""Network protocol discovery handlers for mDNS, SSDP, SNMP, and LLDP.

Each handler uses raw sockets and asyncio — no external libraries.
LLDP requires ``CAP_NET_RAW`` and gracefully degrades when unavailable.
"""

from __future__ import annotations

import asyncio
import contextlib
import socket
import struct
from dataclasses import dataclass, field
from typing import Any

import structlog

from .banners import (
    _SNMP_SYSDESCR_OID,
    _SNMP_SYSNAME_OID,
    _SNMP_SYSOBJECTID_OID,
    _build_snmp_get,
    _parse_snmp_response,
)

logger = structlog.get_logger(__name__)


# ── Result Types ─────────────────────────────────────────────────────


@dataclass
class MdnsResult:
    """A device discovered via mDNS."""

    ip: str
    hostname: str | None = None
    services: list[str] = field(default_factory=list)
    txt_records: dict[str, str] = field(default_factory=dict)


@dataclass
class SsdpResult:
    """A device discovered via SSDP/UPnP."""

    ip: str
    server: str | None = None
    location: str | None = None
    usn: str | None = None
    device_type: str | None = None


@dataclass
class LldpResult:
    """A neighbor discovered via LLDP."""

    ip: str | None = None
    chassis_id: str | None = None
    port_id: str | None = None
    system_name: str | None = None
    system_description: str | None = None


@dataclass
class SnmpDeviceResult:
    """SNMP query result for a single host."""

    ip: str
    sys_descr: str | None = None
    sys_name: str | None = None
    sys_object_id: str | None = None


@dataclass
class ProtocolDiscoveryResults:
    """Consolidated results from all protocol discovery handlers."""

    mdns: list[MdnsResult] = field(default_factory=list)
    ssdp: list[SsdpResult] = field(default_factory=list)
    lldp: list[LldpResult] = field(default_factory=list)
    snmp: list[SnmpDeviceResult] = field(default_factory=list)

    def results_by_ip(self) -> dict[str, dict[str, Any]]:
        """Index results by IP address for merging into device records."""
        by_ip: dict[str, dict[str, Any]] = {}

        for m in self.mdns:
            entry = by_ip.setdefault(m.ip, {})
            entry["mdns"] = {
                "services": m.services,
                "hostname": m.hostname,
                "txtRecords": m.txt_records,
            }

        for s in self.ssdp:
            entry = by_ip.setdefault(s.ip, {})
            entry["ssdp"] = {
                "server": s.server,
                "location": s.location,
                "usn": s.usn,
                "deviceType": s.device_type,
            }

        for lldp_entry in self.lldp:
            if lldp_entry.ip:
                entry = by_ip.setdefault(lldp_entry.ip, {})
                entry["lldp"] = {
                    "chassisId": lldp_entry.chassis_id,
                    "portId": lldp_entry.port_id,
                    "systemName": lldp_entry.system_name,
                    "systemDescription": lldp_entry.system_description,
                }

        for snmp_entry in self.snmp:
            entry = by_ip.setdefault(snmp_entry.ip, {})
            entry["snmp"] = {
                "sysDescr": snmp_entry.sys_descr,
                "sysName": snmp_entry.sys_name,
                "sysObjectID": snmp_entry.sys_object_id,
            }

        return by_ip


# ── mDNS Discovery ───────────────────────────────────────────────────

_MDNS_ADDR = "224.0.0.251"
_MDNS_PORT = 5353

# DNS query for _services._dns-sd._udp.local (PTR record, type 12)
_MDNS_BROWSE_QUERY = (
    b"\x00\x00"  # Transaction ID
    b"\x00\x00"  # Flags (standard query)
    b"\x00\x01"  # Questions: 1
    b"\x00\x00"  # Answer RRs
    b"\x00\x00"  # Authority RRs
    b"\x00\x00"  # Additional RRs
    # Query: _services._dns-sd._udp.local, type PTR (12), class IN (1)
    b"\x09_services\x07_dns-sd\x04_udp\x05local\x00"
    b"\x00\x0c"  # Type PTR
    b"\x00\x01"  # Class IN
)


def _parse_dns_name(data: bytes, offset: int) -> tuple[str, int]:
    """Parse a DNS name with pointer compression."""
    parts: list[str] = []
    seen_offsets: set[int] = set()
    jump_target: int | None = None

    while offset < len(data):
        if offset in seen_offsets:
            break
        seen_offsets.add(offset)

        length = data[offset]
        if length == 0:
            offset += 1
            break
        if (length & 0xC0) == 0xC0:
            # Pointer: next byte forms the offset
            if offset + 1 >= len(data):
                break
            ptr = ((length & 0x3F) << 8) | data[offset + 1]
            if jump_target is None:
                jump_target = offset + 2
            offset = ptr
            continue
        offset += 1
        if offset + length > len(data):
            break
        parts.append(data[offset:offset + length].decode("utf-8", errors="replace"))
        offset += length

    name = ".".join(parts)
    return name, jump_target if jump_target is not None else offset


def _parse_dns_txt(data: bytes, offset: int, rdlength: int) -> dict[str, str]:
    """Parse DNS TXT record data into key=value pairs."""
    records: dict[str, str] = {}
    end = offset + rdlength
    while offset < end:
        txt_len = data[offset]
        offset += 1
        if offset + txt_len > end:
            break
        txt = data[offset:offset + txt_len].decode("utf-8", errors="replace")
        if "=" in txt:
            key, value = txt.split("=", 1)
            records[key] = value
        offset += txt_len
    return records


async def discover_mdns(timeout: float = 5.0) -> list[MdnsResult]:
    """Send an mDNS browse query and collect service advertisements.

    Joins multicast group 224.0.0.251:5353, sends a PTR query for
    ``_services._dns-sd._udp.local``, and parses responses to extract
    service types, hostnames, and TXT records.
    """
    results: dict[str, MdnsResult] = {}

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        with contextlib.suppress(AttributeError, OSError):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        sock.bind(("", _MDNS_PORT))

        # Join multicast group
        mreq = struct.pack("4s4s", socket.inet_aton(_MDNS_ADDR), socket.inet_aton("0.0.0.0"))
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.setblocking(False)

        loop = asyncio.get_running_loop()

        # Send browse query
        sock.sendto(_MDNS_BROWSE_QUERY, (_MDNS_ADDR, _MDNS_PORT))

        # Collect responses
        end_time = loop.time() + timeout
        while loop.time() < end_time:
            remaining = end_time - loop.time()
            if remaining <= 0:
                break
            try:
                data, addr = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: sock.recvfrom(4096)),
                    timeout=min(remaining, 1.0),
                )
            except (TimeoutError, OSError):
                continue

            ip = addr[0]
            if ip == "0.0.0.0":
                continue

            _parse_mdns_response(data, ip, results)

        sock.close()
    except OSError as exc:
        logger.warning("mdns_discovery_failed", error=str(exc))

    return list(results.values())


def _parse_mdns_response(
    data: bytes,
    source_ip: str,
    results: dict[str, MdnsResult],
) -> None:
    """Parse an mDNS response packet and update results."""
    if len(data) < 12:
        return

    # Header
    _flags = struct.unpack("!H", data[2:4])[0]
    qdcount = struct.unpack("!H", data[4:6])[0]
    ancount = struct.unpack("!H", data[6:8])[0]
    nscount = struct.unpack("!H", data[8:10])[0]
    arcount = struct.unpack("!H", data[10:12])[0]

    offset = 12

    # Skip questions
    for _ in range(qdcount):
        _, offset = _parse_dns_name(data, offset)
        offset += 4  # type + class

    entry = results.setdefault(source_ip, MdnsResult(ip=source_ip))

    # Parse answers + authority + additional
    for _ in range(ancount + nscount + arcount):
        if offset >= len(data):
            break
        name, offset = _parse_dns_name(data, offset)
        if offset + 10 > len(data):
            break
        rtype = struct.unpack("!H", data[offset:offset + 2])[0]
        offset += 8  # type(2) + class(2) + TTL(4)
        rdlength = struct.unpack("!H", data[offset:offset + 2])[0]
        offset += 2

        if rtype == 12:  # PTR
            service_name, _ = _parse_dns_name(data, offset)
            if service_name and service_name not in entry.services:
                entry.services.append(service_name)
        elif rtype == 16:  # TXT
            txt = _parse_dns_txt(data, offset, rdlength)
            entry.txt_records.update(txt)
        elif rtype == 33:  # SRV
            if offset + 6 <= len(data):
                target, _ = _parse_dns_name(data, offset + 6)
                if target:
                    entry.hostname = target

        offset += rdlength


# ── SSDP Discovery ───────────────────────────────────────────────────

_SSDP_ADDR = "239.255.255.250"
_SSDP_PORT = 1900

_SSDP_MSEARCH = (
    "M-SEARCH * HTTP/1.1\r\n"
    f"HOST: {_SSDP_ADDR}:{_SSDP_PORT}\r\n"
    'MAN: "ssdp:discover"\r\n'
    "MX: 3\r\n"
    "ST: ssdp:all\r\n"
    "\r\n"
).encode()


async def discover_ssdp(timeout: float = 5.0) -> list[SsdpResult]:
    """Send an SSDP M-SEARCH and parse device responses.

    Sends a multicast M-SEARCH to 239.255.255.250:1900 and parses
    response headers to extract SERVER, LOCATION, USN, and ST fields.
    """
    results: dict[str, SsdpResult] = {}

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.setblocking(False)
        sock.bind(("", 0))

        loop = asyncio.get_running_loop()

        # Send M-SEARCH
        sock.sendto(_SSDP_MSEARCH, (_SSDP_ADDR, _SSDP_PORT))

        end_time = loop.time() + timeout
        while loop.time() < end_time:
            remaining = end_time - loop.time()
            if remaining <= 0:
                break
            try:
                data, addr = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: sock.recvfrom(4096)),
                    timeout=min(remaining, 1.0),
                )
            except (TimeoutError, OSError):
                continue

            ip = addr[0]
            text = data.decode("utf-8", errors="replace")
            headers: dict[str, str] = {}
            for line in text.split("\r\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    headers[key.strip().upper()] = value.strip()

            entry = results.setdefault(ip, SsdpResult(ip=ip))
            if "SERVER" in headers:
                entry.server = headers["SERVER"]
            if "LOCATION" in headers:
                entry.location = headers["LOCATION"]
            if "USN" in headers:
                entry.usn = headers["USN"]
            if "ST" in headers:
                entry.device_type = headers["ST"]

        sock.close()
    except OSError as exc:
        logger.warning("ssdp_discovery_failed", error=str(exc))

    return list(results.values())


# ── LLDP Discovery ───────────────────────────────────────────────────

_ETH_P_LLDP = 0x88CC


async def discover_lldp(timeout: float = 10.0) -> list[LldpResult] | None:
    """Listen for LLDP frames on a raw socket.

    Requires ``CAP_NET_RAW``.  Returns ``None`` if the socket cannot
    be created (insufficient privileges), allowing graceful degradation.
    """
    try:
        sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(_ETH_P_LLDP))
    except (OSError, PermissionError) as exc:
        logger.info("lldp_discovery_skipped", reason=str(exc))
        return None

    sock.setblocking(False)
    results: list[LldpResult] = []

    try:
        loop = asyncio.get_running_loop()
        end_time = loop.time() + timeout

        while loop.time() < end_time:
            remaining = end_time - loop.time()
            if remaining <= 0:
                break
            try:
                data = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: sock.recv(4096)),
                    timeout=min(remaining, 2.0),
                )
            except (TimeoutError, OSError):
                continue

            result = _parse_lldp_frame(data)
            if result:
                results.append(result)
    finally:
        sock.close()

    return results


def _parse_lldp_frame(data: bytes) -> LldpResult | None:
    """Parse an LLDP frame and extract TLVs."""
    # Skip Ethernet header (14 bytes): dst(6) + src(6) + ethertype(2)
    if len(data) < 14:
        return None

    offset = 14
    result = LldpResult()

    while offset + 2 <= len(data):
        header = struct.unpack("!H", data[offset:offset + 2])[0]
        tlv_type = (header >> 9) & 0x7F
        tlv_length = header & 0x01FF
        offset += 2

        if tlv_type == 0:  # End of LLDPDU
            break
        if offset + tlv_length > len(data):
            break

        value = data[offset:offset + tlv_length]
        offset += tlv_length

        if tlv_type == 1 and tlv_length > 1:  # Chassis ID
            result.chassis_id = value[1:].decode("utf-8", errors="replace")
        elif tlv_type == 2 and tlv_length > 1:  # Port ID
            result.port_id = value[1:].decode("utf-8", errors="replace")
        elif tlv_type == 5:  # System Name
            result.system_name = value.decode("utf-8", errors="replace")
        elif tlv_type == 6:  # System Description
            result.system_description = value.decode("utf-8", errors="replace")

    if result.chassis_id or result.system_name:
        return result
    return None


# ── SNMP Device Query ────────────────────────────────────────────────


async def query_snmp_device(
    host: str,
    community: str = "public",
    timeout: float = 2.0,
) -> SnmpDeviceResult | None:
    """Query sysDescr, sysName, and sysObjectID from a single host.

    Reuses the raw SNMPv1 PDU construction from ``banners.py``.
    """
    result = SnmpDeviceResult(ip=host)
    queries = [
        ("sys_descr", _SNMP_SYSDESCR_OID, 1),
        ("sys_name", _SNMP_SYSNAME_OID, 2),
        ("sys_object_id", _SNMP_SYSOBJECTID_OID, 3),
    ]

    for attr, oid_bytes, request_id in queries:
        try:
            pdu = _build_snmp_get(community, oid_bytes, request_id)
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            sock.setblocking(False)

            loop = asyncio.get_running_loop()
            transport, _protocol = await loop.create_datagram_endpoint(
                lambda: asyncio.DatagramProtocol(),
                sock=sock,
            )
            try:
                transport.sendto(pdu, (host, 161))
                data = await asyncio.wait_for(
                    _recv_snmp_udp(loop, sock),
                    timeout=timeout,
                )
                value = _parse_snmp_response(data)
                setattr(result, attr, value)
            finally:
                transport.close()
        except (OSError, TimeoutError):
            pass

    if not any([result.sys_descr, result.sys_name, result.sys_object_id]):
        return None
    return result


async def _recv_snmp_udp(
    loop: asyncio.AbstractEventLoop,
    sock: socket.socket,
) -> bytes:
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


# ── Orchestrator ─────────────────────────────────────────────────────


async def run_protocol_discovery(
    *,
    include_mdns: bool = True,
    include_ssdp: bool = True,
    include_lldp: bool = False,
    timeout: float = 5.0,
) -> ProtocolDiscoveryResults:
    """Run all enabled protocol discoveries concurrently.

    Args:
        include_mdns: Run mDNS service browse.
        include_ssdp: Run SSDP M-SEARCH.
        include_lldp: Run LLDP listener (requires CAP_NET_RAW).
        timeout: Per-protocol timeout in seconds.

    Returns:
        Consolidated results from all enabled protocols.
    """
    results = ProtocolDiscoveryResults()
    tasks: dict[str, asyncio.Task[Any]] = {}

    if include_mdns:
        tasks["mdns"] = asyncio.create_task(discover_mdns(timeout))
    if include_ssdp:
        tasks["ssdp"] = asyncio.create_task(discover_ssdp(timeout))
    if include_lldp:
        tasks["lldp"] = asyncio.create_task(discover_lldp(timeout))

    for name, task in tasks.items():
        try:
            result = await task
            if name == "mdns" and result:
                results.mdns = result
            elif name == "ssdp" and result:
                results.ssdp = result
            elif name == "lldp" and result is not None:
                results.lldp = result
        except Exception:
            logger.warning("protocol_discovery_failed", protocol=name)

    return results
