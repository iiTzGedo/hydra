"""MAC address resolution strategies for L3-discovered devices.

Implements spec §2.4.3 — when an IP-only discovery is created (the API
scanned a routed subnet so ARP only revealed the gateway's MAC), attempt
to learn the device's true MAC via:

1. Local ARP cache — for devices the API host has spoken to recently
2. Router SNMP — query the gateway's ARP table over SNMP (IF-MIB)
3. Agent dispatch — queue ``network.resolve_mac`` command on an agent
   sitting on the target L2 segment

Strategies run in order; the first to succeed wins. The agent path is
fire-and-forget — when the agent later calls ``POST /discovery/results/_resolve-mac``,
the migration logic in this module rewrites the discovery record's ID
from ``disc::ip::*`` to ``disc::mac::*`` and merges any duplicate.
"""

from __future__ import annotations

import asyncio
import socket
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from hydra.api.v1.services.discovery.banners import _build_snmp_get
from hydra.api.v1.services.discovery.protocols import _recv_snmp_udp

logger = structlog.get_logger(__name__)

_PROC_ARP = Path("/proc/net/arp")

# IF-MIB::ipNetToMediaPhysAddress = 1.3.6.1.2.1.4.22.1.2
_ARP_OID_PREFIX = bytes([
    0x06, 0x0a, 0x2b, 0x06, 0x01, 0x02, 0x01, 0x04, 0x16, 0x01, 0x02,
])


def normalize_mac(mac: str) -> str:
    """Spec §2.4.2 normalization: lowercase, hyphen-separated."""
    return mac.lower().replace(":", "-")


# ── Strategy 1: Local ARP cache ─────────────────────────────────────


def resolve_via_local_arp(ip: str) -> str | None:
    """Look up an IP in the host's ARP cache via ``/proc/net/arp``.

    Returns a colon-separated MAC if a fresh entry exists, else ``None``.
    Returns ``None`` on non-Linux or when the file is unreadable.
    """
    try:
        contents = _PROC_ARP.read_text()
    except OSError:
        return None

    for line in contents.splitlines()[1:]:  # skip header
        parts = line.split()
        if len(parts) < 4:
            continue
        ip_addr, _hw_type, flags, mac = parts[0], parts[1], parts[2], parts[3]
        if ip_addr != ip:
            continue
        # Flags: 0x2 = complete (resolved). Skip incomplete entries.
        if int(flags, 16) & 0x2 == 0:
            continue
        if mac == "00:00:00:00:00:00":
            continue
        return mac
    return None


# ── Strategy 2: Router SNMP query ───────────────────────────────────


def _build_arp_oid(if_index: int, target_ip: str) -> bytes:
    """Encode the ipNetToMediaPhysAddress OID for a specific (ifIndex, IP)."""
    octets = [int(o) for o in target_ip.split(".")]
    # Per-component encoding: ifIndex + 4 IP octets, all under 128 → 1 byte each
    suffix = bytes([if_index] + octets)
    # Rebuild OID with extended length: prefix is "06 0a 2b 06 01 02 01 04 16 01 02"
    # New body: 2b 06 01 02 01 04 16 01 02 + ifIndex + ip-octets (5 extra bytes)
    body = bytes([0x2b, 0x06, 0x01, 0x02, 0x01, 0x04, 0x16, 0x01, 0x02]) + suffix
    return bytes([0x06, len(body)]) + body


def _parse_snmp_octet_value(data: bytes) -> bytes | None:
    """Like ``_parse_snmp_response`` but returns the raw value bytes
    rather than decoding to a string. Used to extract MAC bytes from
    the IF-MIB ARP table, which returns OCTET STRING(6).
    """
    try:
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

        _, _, pos = _read_tag_length(data, pos)  # outer SEQ
        _, vlen, pos = _read_tag_length(data, pos)
        pos += vlen  # version
        _, clen, pos = _read_tag_length(data, pos)
        pos += clen  # community
        tag, _, pos = _read_tag_length(data, pos)  # GetResponse-PDU
        if tag != 0xA2:
            return None
        for _ in range(3):  # request-id, error-status, error-index
            _, length, pos = _read_tag_length(data, pos)
            pos += length
        _, _, pos = _read_tag_length(data, pos)  # VarBindList
        _, _, pos = _read_tag_length(data, pos)  # VarBind
        _, oid_len, pos = _read_tag_length(data, pos)
        pos += oid_len  # OID
        value_tag, value_len, pos = _read_tag_length(data, pos)
        if value_tag != 0x04:
            return None
        return data[pos : pos + value_len]
    except (IndexError, ValueError):
        return None


async def _snmp_query_arp(
    router_ip: str,
    target_ip: str,
    *,
    community: str = "public",
    if_indexes: tuple[int, ...] = (1, 2, 3, 4, 5),
    timeout: float = 2.0,
) -> str | None:
    """Try SNMP-GET on the router for every plausible ifIndex.

    Returns the colon-separated MAC if any GET succeeds, else None.
    Tries common interface indexes (1-5 covers the vast majority of
    homelab routers) without doing a full table walk, which keeps the
    operation fast and bounded.
    """
    loop = asyncio.get_running_loop()

    for request_id, if_index in enumerate(if_indexes, start=1):
        oid = _build_arp_oid(if_index, target_ip)
        try:
            pdu = _build_snmp_get(community, oid, request_id)
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            sock.setblocking(False)

            transport, _ = await loop.create_datagram_endpoint(
                lambda: asyncio.DatagramProtocol(),
                sock=sock,
            )
            try:
                transport.sendto(pdu, (router_ip, 161))
                data = await asyncio.wait_for(
                    _recv_snmp_udp(loop, sock),
                    timeout=timeout,
                )
                mac_bytes = _parse_snmp_octet_value(data)
                if mac_bytes and len(mac_bytes) == 6:
                    return ":".join(f"{b:02x}" for b in mac_bytes)
            finally:
                transport.close()
        except (OSError, TimeoutError):
            continue
    return None


async def resolve_via_router_snmp(
    target_ip: str,
    network_id: str,
    db: Any,
    *,
    community: str = "public",
) -> str | None:
    """Look up the target IP's MAC by querying the network's router via SNMP.

    Requires the network to have a ``routerNodeId`` and the router node
    to expose its primary IP via ``primaryIp`` field.
    """
    network = await db["networks"].find_one({"networkId": network_id})
    if not network:
        return None
    router_id = network.get("routerNodeId")
    if not router_id:
        return None

    router = await db["nodes"].find_one({"nodeId": router_id})
    if not router:
        return None
    # Try common locations for router IP
    router_ip = (
        router.get("primaryIp")
        or router.get("metadata", {}).get("primaryIp")
        or network.get("gatewayV4")
    )
    if not router_ip:
        return None

    snmp_community = (
        router.get("metadata", {}).get("snmp", {}).get("community", community)
    )
    return await _snmp_query_arp(router_ip, target_ip, community=snmp_community)


# ── Strategy 3: Agent-delegated resolution ──────────────────────────


async def resolve_via_agent(
    target_ip: str,
    network_id: str,
    db: Any,
    *,
    commands_service: Any,
    user_id: str = "system",
) -> str | None:
    """Queue a ``network.resolve_mac`` command on an agent attached to the network.

    Always returns ``None`` immediately — this is fire-and-forget. The
    agent reports back asynchronously via ``POST /discovery/results/_resolve-mac``,
    which then triggers ``migrate_ip_to_mac``.
    """
    if commands_service is None:
        return None

    # Find the first compute node that has this network attached.
    target_node = await db["nodes"].find_one(
        {
            "networkIds": network_id,
            "class": "compute",
            "agent.installed": True,
        },
    )
    if not target_node:
        return None

    try:
        from hydra.api.v1.models.commands import (
            CommandSource,
            CreateCommandRequest,
        )
        from hydra.api.v1.models.commands.schemas import CommandTarget

        request = CreateCommandRequest(
            registry_id="reg::agent::resolve-mac",
            target=CommandTarget(
                node_id=target_node["nodeId"],
                service_id=None,
            ),
            parameters={"ip": target_ip, "networkId": network_id},
            timeout_seconds=None,
        )
        await commands_service.create_command(
            request=request,
            user_id=user_id,
            source=CommandSource.AUTOMATION,
        )
        logger.info(
            "mac_resolver.agent_command_queued",
            ip=target_ip,
            network_id=network_id,
            node_id=target_node["nodeId"],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "mac_resolver.agent_command_failed",
            ip=target_ip,
            error=str(exc),
        )

    return None


# ── Orchestrator ────────────────────────────────────────────────────


async def resolve_mac(
    target_ip: str,
    network_id: str | None,
    db: Any,
    *,
    commands_service: Any = None,
    user_id: str = "system",
) -> str | None:
    """Run the spec strategies in order until one returns a MAC."""
    # Strategy 1: local ARP (always available, instant)
    mac = resolve_via_local_arp(target_ip)
    if mac:
        logger.info("mac_resolver.local_arp_hit", ip=target_ip, mac=mac)
        return mac

    if not network_id:
        return None

    # Strategy 2: router SNMP
    try:
        mac = await resolve_via_router_snmp(target_ip, network_id, db)
        if mac:
            logger.info("mac_resolver.router_snmp_hit", ip=target_ip, mac=mac)
            return mac
    except Exception as exc:  # noqa: BLE001
        logger.warning("mac_resolver.router_snmp_failed", ip=target_ip, error=str(exc))

    # Strategy 3: agent delegation (fire-and-forget)
    if commands_service is not None:
        await resolve_via_agent(
            target_ip,
            network_id,
            db,
            commands_service=commands_service,
            user_id=user_id,
        )

    return None


# ── Migration: IP-only → MAC-anchored ───────────────────────────────


async def migrate_ip_to_mac(
    devices: Any,
    target_ip: str,
    mac: str,
    network_id: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Rekey an IP-anchored discovery to its MAC-anchored equivalent.

    If the MAC-anchored record already exists (the device was also seen
    on an L2 segment we scanned directly), merge the two. Otherwise,
    rewrite the IP-only record's ``discoveryId`` to ``disc::mac::*`` and
    set ``identity.primaryMac``.

    Args:
        devices: ``mongodb.discovered_nodes`` collection handle.
        target_ip: IP that the MAC corresponds to.
        mac: Newly learned MAC address (any case/separator).
        network_id: Network the IP lives on (required for the IP key).
        now: Override timestamp (test-only).

    Returns:
        The merged/migrated discovery document, or ``None`` if no
        IP-only record was found.
    """
    timestamp = now or datetime.now(UTC)
    normalized = normalize_mac(mac)
    old_id = f"disc::ip::{network_id}::{target_ip}"
    new_id = f"disc::mac::{normalized}"

    old = await devices.find_one({"discoveryId": old_id})
    if not old:
        logger.debug("mac_resolver.no_ip_record", old_id=old_id)
        return None

    new = await devices.find_one({"discoveryId": new_id})

    if new is None:
        # Simple rekey
        await devices.update_one(
            {"_id": old["_id"]},
            {
                "$set": {
                    "discoveryId": new_id,
                    "identity.primaryMac": mac,
                    "identity.macResolved": True,
                    "updatedAt": timestamp,
                },
            },
        )
        logger.info("mac_resolver.rekeyed", old=old_id, new=new_id)
        result: dict[str, Any] | None = await devices.find_one({"_id": old["_id"]})
        assert result is not None
        return result

    # Merge: the MAC-anchored record wins on identity, but ports/protocols/seenCount union.
    merged_ports = list(set(new.get("openPorts", [])) | set(old.get("openPorts", [])))
    merged_protocols = list(
        set(new.get("protocols", [])) | set(old.get("protocols", []))
    )
    merged_observed_ips = (
        new.get("identity", {}).get("observedIps", [])
        + old.get("identity", {}).get("observedIps", [])
    )
    merged_seen_count = new.get("seenCount", 0) + old.get("seenCount", 0)

    await devices.update_one(
        {"_id": new["_id"]},
        {
            "$set": {
                "openPorts": merged_ports,
                "protocols": merged_protocols,
                "identity.observedIps": merged_observed_ips,
                "seenCount": merged_seen_count,
                "lastSeen": max(
                    new.get("lastSeen", timestamp),
                    old.get("lastSeen", timestamp),
                ),
                "updatedAt": timestamp,
                "_mergedFrom": old_id,
            },
        },
    )
    await devices.delete_one({"_id": old["_id"]})
    logger.info(
        "mac_resolver.merged",
        old=old_id,
        new=new_id,
        seen_count=merged_seen_count,
    )

    merged_result: dict[str, Any] | None = await devices.find_one({"_id": new["_id"]})
    assert merged_result is not None
    return merged_result
