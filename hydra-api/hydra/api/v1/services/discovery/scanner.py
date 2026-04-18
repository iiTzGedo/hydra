"""API-direct network scanner — TCP connect plus optional ARP/ICMP layers.

Layer 4 (TCP connect) works without elevated privileges. Layers 1
(ARP scan, ICMP echo sweep) are optional: enabled when the requested
``ScanMethod`` set includes them and the process holds ``CAP_NET_RAW``.
When the capability is missing the scanner silently degrades to TCP-only
and surfaces this through the returned ``capability_status``.

``python-nmap`` is intentionally not used: the asyncio TCP scanner
matches the spec §2.9.3 perf budget without requiring an external
``nmap`` binary on every API host.
"""

from __future__ import annotations

import asyncio
from ipaddress import IPv4Network, ip_network
from typing import Any

import structlog

from hydra.api.v1.models.discovery.enums import ScanMethod
from hydra.api.v1.services.discovery.capabilities import (
    capability_status,
    has_cap_net_raw,
)
from hydra.api.v1.services.discovery.layer1 import (
    CapabilityError,
    arp_scan,
    icmp_sweep,
)

logger = structlog.get_logger(__name__)

# Default port lists aligned with spec §2.3.1.
# MUST stay in lock-step with:
#   hydra-agent/src/executor/network_handler.rs :: ports_for_tier()
#   hydra-api/hydra/api/v1/services/discovery/fingerprint.py :: TIER1_PORTS / TIER2_PORTS
TIER1_PORTS: list[int] = [
    22, 23, 25, 53, 80, 110, 143, 161, 389, 443, 445,
    554, 623, 993, 995, 1194, 1433, 1883, 1900, 2375,
    2376, 3306, 3389, 5353, 5432, 5683, 5900, 6379,
    8006, 8080, 8123, 8443,
]

TIER2_PORTS: list[int] = [
    21, 69, 111, 135, 179, 427, 500, 514, 515, 548,
    587, 631, 636, 873, 902, 1080, 1521, 1723,
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
    *,
    mac: str | None = None,
    force_alive: bool = False,
) -> dict[str, Any] | None:
    """Scan a single host for open ports and grab banners.

    Args:
        host: IPv4 address.
        ports: Ports to probe.
        timeout: Per-port TCP connect timeout.
        semaphore: Bounds concurrent host scans.
        mac: Pre-resolved MAC address from a Layer 1 scan, if any.
        force_alive: When True (host known alive via ARP/ICMP), return a
            result dict even if no TCP ports are open.

    Returns a result dict with ``ip``, ``openPorts``, ``banners``, and
    optional ``mac``; or ``None`` when the host appears down and was not
    independently confirmed alive.
    """
    from .banners import grab_banners

    async with semaphore:
        tasks = [_check_port(host, port, timeout) for port in ports]
        results = await asyncio.gather(*tasks)
        open_ports = sorted(p for p in results if p is not None)

        if not open_ports and not force_alive:
            return None

        # Grab protocol-specific banners from open ports
        banners = (
            await grab_banners(host, open_ports, timeout=min(timeout, 2.0))
            if open_ports
            else {}
        )

        result: dict[str, Any] = {
            "ip": host,
            "openPorts": open_ports,
            "banners": banners,
        }
        if mac:
            result["mac"] = mac
        return result


async def scan_subnet(
    cidr: str,
    *,
    port_tier: str = "tier1",
    concurrency: int = 64,
    port_timeout: float = 1.5,
    scan_methods: list[ScanMethod] | None = None,
) -> dict[str, Any]:
    """Scan a subnet, optionally combining Layer 1 (ARP/ICMP) + TCP probing.

    Args:
        cidr: Subnet in CIDR notation (e.g. ``192.168.1.0/24``).
        port_tier: ``tier1`` (~32 ports) or ``tier2`` (~100 ports).
        concurrency: Maximum concurrent connection attempts.
        port_timeout: Timeout in seconds per TCP connect attempt.
        scan_methods: Methods to attempt. ``ARP`` and ``ICMP`` require
            ``CAP_NET_RAW``; when missing they are silently skipped and
            the result's ``capabilities`` block reflects the degradation.
            Defaults to ``[TCP_PORT]`` for backward compatibility.

    Returns:
        Dict with ``hosts`` (list of alive host dicts) and ``capabilities``
        (privilege snapshot for the scan). Each host dict carries ``ip``,
        ``openPorts``, ``banners`` and an optional ``mac`` (when ARP found one).
    """
    network = ip_network(cidr, strict=False)

    if not isinstance(network, IPv4Network):
        logger.warning("scanner.ipv6_not_supported", cidr=cidr)
        return {"hosts": [], "capabilities": capability_status()}

    methods = set(scan_methods or [ScanMethod.TCP_PORT])
    ports = TIER1_PORTS if port_tier == "tier1" else TIER1_PORTS + TIER2_PORTS
    hosts = [str(host) for host in network.hosts()]

    # Layer 1: ARP scan for IP→MAC and host liveness
    ip_to_mac: dict[str, str] = {}
    if ScanMethod.ARP in methods and has_cap_net_raw():
        try:
            ip_to_mac = await arp_scan(cidr)
        except (CapabilityError, OSError, ValueError) as exc:
            logger.warning("scanner.arp_skipped", cidr=cidr, error=str(exc))

    # Layer 1: ICMP echo sweep for additional liveness signal
    icmp_alive: set[str] = set()
    if ScanMethod.ICMP in methods and has_cap_net_raw():
        try:
            icmp_alive = await icmp_sweep(cidr)
        except (CapabilityError, OSError, ValueError) as exc:
            logger.warning("scanner.icmp_skipped", cidr=cidr, error=str(exc))

    layer1_alive = set(ip_to_mac.keys()) | icmp_alive

    logger.info(
        "scanner.scan_started",
        cidr=cidr,
        host_count=len(hosts),
        port_count=len(ports),
        concurrency=concurrency,
        methods=sorted(m.value for m in methods),
        layer1_alive=len(layer1_alive),
    )

    semaphore = asyncio.Semaphore(concurrency)
    tasks = [
        _scan_host(
            host,
            ports,
            port_timeout,
            semaphore,
            mac=ip_to_mac.get(host),
            force_alive=host in layer1_alive,
        )
        for host in hosts
    ]
    results = await asyncio.gather(*tasks)

    alive_hosts = [r for r in results if r is not None]

    logger.info(
        "scanner.scan_completed",
        cidr=cidr,
        hosts_alive=len(alive_hosts),
        hosts_total=len(hosts),
    )

    return {
        "hosts": alive_hosts,
        "capabilities": capability_status(),
    }
