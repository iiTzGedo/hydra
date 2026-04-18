"""Host network interface introspection.

On API startup the system enumerates locally attached IPv4 networks and
seeds matching ``networks`` collection records. For each interface the
API can directly reach (L2 access), the corresponding Network document
is created or upgraded to ``scanConfig.status = "api-direct"`` per
spec §2.2.1 / §2.2.3.

Idempotent: re-running on every startup updates ``apiReachabilityTest``
without producing duplicate networks.
"""

from __future__ import annotations

import socket
import struct
import sys
from datetime import UTC, datetime
from ipaddress import (
    IPv4Address,
    IPv4Interface,
    IPv4Network,
    IPv6Interface,
    ip_interface,
)
from pathlib import Path
from typing import Any, NamedTuple

import structlog

logger = structlog.get_logger(__name__)

_LOOPBACK = IPv4Network("127.0.0.0/8")


class LocalNetwork(NamedTuple):
    """One attached IPv4 network discovered via host introspection."""

    interface: str
    cidr: str
    address: str
    mac: str | None
    gateway: str | None


def _read_default_gateway() -> dict[str, str]:
    """Parse ``/proc/net/route`` and return ``{interface: gateway-ip}``.

    Returns an empty dict on non-Linux or when the file is unreadable.
    """
    if sys.platform != "linux":
        return {}
    gateways: dict[str, str] = {}
    try:
        for line in Path("/proc/net/route").read_text().splitlines()[1:]:
            fields = line.split()
            if len(fields) < 8:
                continue
            iface, dest_hex, gw_hex = fields[0], fields[1], fields[2]
            # Default route has destination 0.0.0.0
            if dest_hex != "00000000":
                continue
            gw_int = struct.unpack("<I", bytes.fromhex(gw_hex))[0]
            if gw_int == 0:
                continue
            gateways[iface] = str(IPv4Address(gw_int))
    except (OSError, ValueError, struct.error) as exc:
        logger.debug("host_interfaces.route_parse_failed", error=str(exc))
    return gateways


def enumerate_local_networks() -> list[LocalNetwork]:
    """Return every up, non-loopback IPv4 network attached to this host."""
    try:
        import psutil
    except ImportError:
        logger.warning("host_interfaces.psutil_missing")
        return []

    try:
        if_addrs = psutil.net_if_addrs()
        if_stats = psutil.net_if_stats()
    except Exception as exc:  # noqa: BLE001 — third-party libs raise broad
        logger.warning("host_interfaces.enumeration_failed", error=str(exc))
        return []

    gateways = _read_default_gateway()
    results: list[LocalNetwork] = []

    for iface, addrs in if_addrs.items():
        stats = if_stats.get(iface)
        if not stats or not stats.isup:
            continue

        ipv4_addr: str | None = None
        netmask: str | None = None
        link_mac: str | None = None

        for addr in addrs:
            if addr.family == socket.AF_INET:
                ipv4_addr = addr.address
                netmask = addr.netmask
            elif addr.family == getattr(socket, "AF_PACKET", -1):
                link_mac = addr.address.lower() if addr.address else None

        if not ipv4_addr or not netmask:
            continue

        try:
            iface_obj_raw: IPv4Interface | IPv6Interface = ip_interface(
                f"{ipv4_addr}/{netmask}"
            )
        except ValueError:
            continue
        if not isinstance(iface_obj_raw, IPv4Interface):
            continue
        iface_obj: IPv4Interface = iface_obj_raw

        # Skip loopback (127.x) and link-local (169.254.x)
        if iface_obj.network.subnet_of(_LOOPBACK):
            continue
        if iface_obj.ip.is_link_local:
            continue

        results.append(
            LocalNetwork(
                interface=iface,
                cidr=str(iface_obj.network),
                address=str(iface_obj.ip),
                mac=link_mac,
                gateway=gateways.get(iface),
            )
        )

    return results


def _derive_network_id(local: LocalNetwork) -> str:
    """Spec-aligned network ID: ``net-host-{interface}``.

    Stable across restarts. If the operator later renames the network,
    they can update via the standard UpdateNetworkRequest.
    """
    safe_iface = local.interface.lower().replace(":", "-").replace(".", "-")
    return f"net-host-{safe_iface}"


async def seed_or_update_networks(
    db: Any,
    networks: list[LocalNetwork],
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    """Create new or upgrade existing Network records to ``api-direct``.

    Args:
        db: Motor database handle (``mongodb.db``).
        networks: Local networks discovered via ``enumerate_local_networks``.
        now: Override timestamp (for testing).

    Returns:
        ``{"created": int, "updated": int}`` counts.
    """
    timestamp = now or datetime.now(UTC)
    created = 0
    updated = 0

    for local in networks:
        existing = await db["networks"].find_one({"cidr": local.cidr})
        reachability = {
            "lastTested": timestamp,
            "method": "interface",
            "result": "present",
            "gatewayReachable": local.gateway is not None,
            "sampleHostReachable": True,
            "errorDetails": None,
        }

        if existing:
            await db["networks"].update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "scanConfig.status": "api-direct",
                        "scanConfig.apiReachable": True,
                        "scanConfig.apiReachabilityTest": reachability,
                        "updatedAt": timestamp,
                    }
                },
            )
            updated += 1
            continue

        network_id = _derive_network_id(local)
        # Avoid colliding with an existing networkId on a different CIDR.
        if await db["networks"].find_one({"networkId": network_id}):
            logger.warning(
                "host_interfaces.networkid_collision",
                network_id=network_id,
                cidr=local.cidr,
            )
            continue

        doc: dict[str, Any] = {
            "networkId": network_id,
            "type": "physical",
            "name": f"Host network on {local.interface}",
            "description": f"Auto-seeded from API host interface {local.interface}",
            "cidr": local.cidr,
            "cidrV6": None,
            "gatewayV4": local.gateway,
            "gatewayV6": None,
            "vlanId": None,
            "parentNetworkId": None,
            "subnetIds": [],
            "routerNodeId": None,
            "dhcp": None,
            "dns": None,
            "scanConfig": {
                "status": "api-direct",
                "apiReachable": True,
                "apiReachabilityTest": reachability,
                "delegateAgentNodeIds": [],
                "delegateAgentTierRequired": "max",
                "userGuidance": None,
            },
            "nodeCount": 0,
            "origin": {
                "createdBy": "api-host-introspection",
                "sourceNodeId": None,
                "sourceProfileId": None,
            },
            "tags": [],
            "createdAt": timestamp,
            "updatedAt": timestamp,
        }
        await db["networks"].insert_one(doc)
        created += 1

    logger.info(
        "host_interfaces.seeded",
        created=created,
        updated=updated,
        total=len(networks),
    )
    return {"created": created, "updated": updated}


async def heal_invalid_seeded_types(db: Any) -> int:
    """Patch host-introspected Network records whose ``type`` is no longer
    a valid ``NetworkType`` enum value.

    An earlier version of ``seed_or_update_networks`` wrote ``type: "lan"``
    which is not in the enum and causes the ``GET /networks`` list endpoint
    to 500 when Pydantic re-validates the row. This sweep idempotently
    rewrites any such row to ``type: "physical"`` so the system self-heals
    on the next startup without operator intervention.
    """
    try:
        from hydra.api.v1.models.networks import NetworkType
    except Exception as exc:  # noqa: BLE001 — never block startup on imports
        logger.warning("host_interfaces.heal_import_failed", error=str(exc))
        return 0

    valid = {t.value for t in NetworkType}
    try:
        result = await db["networks"].update_many(
            {
                "origin.createdBy": "api-host-introspection",
                "type": {"$nin": list(valid)},
            },
            {"$set": {"type": "physical"}},
        )
        if result.modified_count:
            logger.info(
                "host_interfaces.healed_invalid_types",
                patched=result.modified_count,
            )
        return int(result.modified_count)
    except Exception as exc:  # noqa: BLE001
        logger.warning("host_interfaces.heal_failed", error=str(exc))
        return 0


async def introspect_and_seed(db: Any) -> dict[str, int]:
    """Convenience wrapper used from the FastAPI lifespan handler.

    First runs a one-shot heal pass for any pre-existing host-introspected
    networks that were written with an invalid ``type`` value, then
    enumerates local interfaces and upserts the corresponding records.

    Catches all exceptions internally so a broken host environment never
    blocks API startup.
    """
    try:
        await heal_invalid_seeded_types(db)
        local_networks = enumerate_local_networks()
        return await seed_or_update_networks(db, local_networks)
    except Exception as exc:  # noqa: BLE001 — startup must never fail here
        logger.warning("host_interfaces.introspect_failed", error=str(exc))
        return {"created": 0, "updated": 0}
