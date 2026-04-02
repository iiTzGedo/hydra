"""URL validation utilities for SSRF protection.

Blocks requests to private/internal IP ranges to prevent Server-Side
Request Forgery attacks via user-controlled URLs.
"""

import ipaddress
import socket

import structlog

logger = structlog.get_logger(__name__)

# Private and reserved IP networks that should not be reachable via
# user-controlled URLs.
_BLOCKED_NETWORKS = [
    # IPv4 private
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    # Loopback
    ipaddress.ip_network("127.0.0.0/8"),
    # Link-local
    ipaddress.ip_network("169.254.0.0/16"),
    # IPv6 private / loopback / link-local
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("fc00::/7"),
]

# Cloud metadata endpoints
_BLOCKED_HOSTS = frozenset({"metadata.google.internal"})


def validate_external_url(url: str, *, allow_private: bool = False) -> str:
    """Validate that a URL does not resolve to a private/internal IP.

    Args:
        url: The URL to validate.
        allow_private: If True, skip IP range checks (for dev environments).

    Returns:
        The validated URL (unchanged).

    Raises:
        ValueError: If the URL resolves to a blocked IP range.
    """
    if allow_private:
        return url

    from urllib.parse import urlparse

    parsed = urlparse(url)
    hostname = parsed.hostname

    if not hostname:
        raise ValueError("URL has no hostname")

    if hostname in _BLOCKED_HOSTS:
        raise ValueError(f"URL hostname is blocked: {hostname}")

    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise ValueError(f"Cannot resolve hostname: {hostname}")

    for _, _, _, _, sockaddr in addr_infos:
        ip = ipaddress.ip_address(sockaddr[0])
        for network in _BLOCKED_NETWORKS:
            if ip in network:
                logger.warning(
                    "ssrf_blocked",
                    url=url,
                    hostname=hostname,
                    resolved_ip=str(ip),
                    blocked_network=str(network),
                )
                raise ValueError(
                    f"URL resolves to a private/reserved IP range ({network})"
                )

    return url
