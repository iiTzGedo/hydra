"""Layer 1 host discovery — ARP scan and ICMP echo sweep.

Implements spec §2.3.1 Layer 1 host-discovery primitives. Both methods
require ``CAP_NET_RAW`` and use ``scapy`` for raw packet I/O. Blocking
scapy calls are dispatched to a thread to keep the event loop responsive.

When the capability is missing, callers must fall back to TCP-only
scanning (see ``capabilities.has_cap_net_raw``).
"""

from __future__ import annotations

import asyncio
from ipaddress import IPv4Network, ip_network
from typing import TYPE_CHECKING

import structlog

from hydra.api.v1.services.discovery.capabilities import has_cap_net_raw

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)


class CapabilityError(RuntimeError):
    """Raised when a Layer 1 operation is attempted without ``CAP_NET_RAW``."""


def _validate_ipv4(cidr: str) -> IPv4Network:
    network = ip_network(cidr, strict=False)
    if not isinstance(network, IPv4Network):
        msg = f"Layer 1 scanning requires an IPv4 subnet, got {cidr}"
        raise ValueError(msg)
    return network


def _arp_scan_blocking(cidr: str, timeout: float) -> dict[str, str]:
    """Blocking ARP broadcast — runs in a worker thread."""
    from scapy.all import ARP, Ether, srp  # type: ignore[attr-defined]

    pkt = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=cidr)
    answered, _ = srp(pkt, timeout=timeout, verbose=False, retry=1)
    results: dict[str, str] = {}
    for _, received in answered:
        ip = str(received.psrc)
        mac = str(received.hwsrc).lower()
        results[ip] = mac
    return results


async def arp_scan(cidr: str, *, timeout: float = 2.0) -> dict[str, str]:
    """Broadcast ARP across the given IPv4 subnet.

    Args:
        cidr: IPv4 subnet in CIDR notation (e.g. ``192.168.1.0/24``).
        timeout: Seconds to wait for ARP replies.

    Returns:
        Mapping of ``{ip: mac}`` for every host that responded.

    Raises:
        CapabilityError: ``CAP_NET_RAW`` is not held.
        ValueError: ``cidr`` is not IPv4.
    """
    _validate_ipv4(cidr)
    if not has_cap_net_raw():
        raise CapabilityError("ARP scan requires CAP_NET_RAW")

    logger.info("layer1.arp_scan_started", cidr=cidr, timeout=timeout)
    results = await asyncio.to_thread(_arp_scan_blocking, cidr, timeout)
    logger.info("layer1.arp_scan_completed", cidr=cidr, hosts_found=len(results))
    return results


def _icmp_sweep_blocking(
    hosts: list[str],
    timeout: float,
) -> set[str]:
    """Blocking ICMP echo sweep — runs in a worker thread."""
    from scapy.all import ICMP, IP, sr  # type: ignore[attr-defined]

    packets = [IP(dst=host) / ICMP() for host in hosts]
    answered, _ = sr(packets, timeout=timeout, verbose=False)
    alive: set[str] = set()
    for _, received in answered:
        alive.add(str(received.src))
    return alive


async def icmp_sweep(
    cidr: str,
    *,
    timeout: float = 2.0,
    chunk_size: int = 256,
) -> set[str]:
    """Send ICMP echo to every host in the subnet and return responders.

    Sends in chunks to avoid overwhelming the kernel send buffer on large
    subnets.
    """
    network = _validate_ipv4(cidr)
    if not has_cap_net_raw():
        raise CapabilityError("ICMP sweep requires CAP_NET_RAW")

    hosts = [str(h) for h in network.hosts()]
    logger.info(
        "layer1.icmp_sweep_started",
        cidr=cidr,
        host_count=len(hosts),
        timeout=timeout,
    )

    alive: set[str] = set()
    for start in range(0, len(hosts), chunk_size):
        chunk = hosts[start : start + chunk_size]
        chunk_alive = await asyncio.to_thread(_icmp_sweep_blocking, chunk, timeout)
        alive.update(chunk_alive)

    logger.info("layer1.icmp_sweep_completed", cidr=cidr, alive=len(alive))
    return alive
