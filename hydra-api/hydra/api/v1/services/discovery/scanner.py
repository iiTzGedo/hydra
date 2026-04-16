"""API-direct network scanner using asyncio TCP connect probes.

Provides subnet scanning without requiring an agent — uses pure asyncio
``open_connection`` calls with configurable concurrency and timeout.
No ``CAP_NET_RAW`` or external libraries (scapy/nmap) needed.
"""

from __future__ import annotations

import asyncio
from ipaddress import IPv4Network, ip_network
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Default port lists aligned with spec §2.3.1
TIER1_PORTS: list[int] = [
    22, 23, 25, 53, 80, 110, 143, 161, 389, 443, 445,
    554, 623, 993, 995, 1194, 1433, 1883, 1900, 2375,
    2376, 3306, 3389, 5353, 5432, 5683, 5900, 6379,
    8006, 8080, 8123, 8443,
]

TIER2_PORTS: list[int] = [
    21, 69, 111, 135, 179, 427, 500, 514, 515, 548,
    587, 631, 636, 873, 902, 993, 1080, 1521, 1723,
    2049, 2222, 2379, 2380, 3000, 3260, 3478, 4243,
    4505, 4506, 5000, 5001, 5060, 5222, 5269, 5672,
    5984, 6000, 6443, 6633, 6881, 7001, 7077, 7474,
    8000, 8008, 8081, 8088, 8090, 8139, 8291, 8444,
    8883, 8888, 9000, 9042, 9090, 9100, 9200, 9300,
    9418, 9999, 10000, 10001, 10250, 10255, 11211, 15672,
    25565, 27017, 28017, 50000,
]


async def _check_port(
    host: str,
    port: int,
    timeout: float,
) -> int | None:
    """Attempt a TCP connect to host:port.

    Returns the port number if open, else None.
    """
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
        writer.close()
        await writer.wait_closed()
        return port
    except (
        OSError,
        TimeoutError,
        ConnectionRefusedError,
        ConnectionResetError,
    ):
        return None


async def _scan_host(
    host: str,
    ports: list[int],
    timeout: float,
    semaphore: asyncio.Semaphore,
) -> dict[str, Any] | None:
    """Scan a single host for open ports and grab banners.

    Returns a result dict with ``ip``, ``openPorts``, and ``banners``
    if any ports are open, else ``None``.
    """
    from .banners import grab_banners

    async with semaphore:
        tasks = [_check_port(host, port, timeout) for port in ports]
        results = await asyncio.gather(*tasks)
        open_ports = sorted(p for p in results if p is not None)

        if not open_ports:
            return None

        # Grab protocol-specific banners from open ports
        banners = await grab_banners(host, open_ports, timeout=min(timeout, 2.0))

        return {
            "ip": host,
            "openPorts": open_ports,
            "banners": banners,
        }


async def scan_subnet(
    cidr: str,
    *,
    port_tier: str = "tier1",
    concurrency: int = 64,
    port_timeout: float = 1.5,
) -> list[dict[str, Any]]:
    """Scan a subnet for hosts with open ports.

    Uses asyncio TCP connect probing — no raw sockets or elevated
    privileges required.

    Args:
        cidr: Subnet in CIDR notation (e.g. ``192.168.1.0/24``).
        port_tier: ``tier1`` (~32 ports) or ``tier2`` (~100 ports).
        concurrency: Maximum concurrent connection attempts.
        port_timeout: Timeout in seconds per TCP connect attempt.

    Returns:
        List of dicts with ``ip`` and ``openPorts`` for each alive host.
    """
    network = ip_network(cidr, strict=False)

    if not isinstance(network, IPv4Network):
        logger.warning("scanner.ipv6_not_supported", cidr=cidr)
        return []

    ports = TIER1_PORTS if port_tier == "tier1" else TIER1_PORTS + TIER2_PORTS

    # Enumerate hosts (skip network and broadcast addresses)
    hosts = [str(host) for host in network.hosts()]

    logger.info(
        "scanner.scan_started",
        cidr=cidr,
        host_count=len(hosts),
        port_count=len(ports),
        concurrency=concurrency,
    )

    semaphore = asyncio.Semaphore(concurrency)
    tasks = [_scan_host(host, ports, port_timeout, semaphore) for host in hosts]
    results = await asyncio.gather(*tasks)

    alive_hosts = [r for r in results if r is not None]

    logger.info(
        "scanner.scan_completed",
        cidr=cidr,
        hosts_alive=len(alive_hosts),
        hosts_total=len(hosts),
    )

    return alive_hosts
