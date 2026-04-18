"""Pick a canonical hostname for a discovered device from multiple sources.

Spec §2.5.1 — `identity.hostname` and `identity.hostnameSources` track the
device's name and where it was learned. Discovery probes already extract
candidate names from several places (mDNS, SNMP sysName, LLDP system_name,
HTTP `<title>`, reverse DNS); this module picks the most authoritative
non-empty one and records every source that contributed.

Priority order (most → least authoritative):

1. **mDNS** — the device announces its own name; gold standard for IoT.
2. **SNMP sysName** — admin-configured on managed network gear.
3. **LLDP system_name** — admin-configured on managed switches.
4. **HTTP `<title>`** — admin UIs (Proxmox, OPNsense, OpenWRT) commonly
   embed the host name in the title.
5. **Reverse DNS (PTR)** — falls back to whatever the network's DNS says.

SSH banners and NetBIOS are not used today: SSH banners rarely contain a
hostname (`SSH-2.0-OpenSSH_9.6p1 Debian-2+deb12u3` is typical) and
NetBIOS isn't a probe Hydra runs.
"""

from __future__ import annotations

import asyncio
import re
import socket
from typing import Any

import structlog

from hydra.api.v1.models.discovery.enums import HostnameSource

logger = structlog.get_logger(__name__)

# A valid DNS-style hostname label per RFC 1123.
_HOSTNAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
# Permits dotted FQDNs too (e.g. `bedroom-pi.local`).
_FQDN_RE = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$"
)


def _is_plausible_hostname(value: str | None) -> bool:
    """Reject empty, IP-looking, or invalid hostname candidates."""
    if not value:
        return False
    value = value.strip().rstrip(".")
    if not value:
        return False
    # Reject pure IP addresses (the resolver should never pick these).
    if re.fullmatch(r"\d+(?:\.\d+){3}", value):
        return False
    return _FQDN_RE.fullmatch(value) is not None


def _normalize_hostname(value: str) -> str:
    """Strip trailing dot, lowercase, remove `.local` mDNS suffix only when bare."""
    cleaned = value.strip().rstrip(".").lower()
    return cleaned


# ── Per-source extractors ────────────────────────────────────────────


def _from_mdns(protocol_details: dict[str, Any]) -> str | None:
    mdns = protocol_details.get("mdns") or {}
    candidate = mdns.get("hostname") or mdns.get("instanceName")
    if isinstance(candidate, str) and _is_plausible_hostname(candidate):
        return _normalize_hostname(candidate)
    return None


def _from_snmp(
    banners: dict[str, str],
    protocol_details: dict[str, Any],
) -> str | None:
    # 1. Structured protocol_details from query_snmp_device
    snmp = protocol_details.get("snmp") or {}
    candidate = snmp.get("sysName")
    if isinstance(candidate, str) and _is_plausible_hostname(candidate):
        return _normalize_hostname(candidate)
    # 2. Fallback: parse banners[161] (`sysDescr=...; sysName=...`)
    raw = banners.get("161")
    if not raw:
        return None
    for part in raw.split(";"):
        key, sep, value = part.strip().partition("=")
        if sep and key == "sysName" and _is_plausible_hostname(value):
            return _normalize_hostname(value)
    return None


def _from_lldp(protocol_details: dict[str, Any]) -> str | None:
    lldp = protocol_details.get("lldp") or {}
    candidate = lldp.get("systemName")
    if isinstance(candidate, str) and _is_plausible_hostname(candidate):
        return _normalize_hostname(candidate)
    return None


_HTTP_TITLE_RE = re.compile(r"<title[^>]*>([^<]+)</title>", re.IGNORECASE | re.DOTALL)
# Common decorations admin UIs append after a hostname (separator + product name).
_TITLE_TRIM_RE = re.compile(r"\s*[-—|·:]\s*.*$")


def extract_hostname_from_title(title: str) -> str | None:
    """Pull a likely hostname out of an HTML `<title>` value.

    Many homelab admin UIs embed the device name with a separator:
        ``"pve - Proxmox Virtual Environment"``
        ``"OPNsense.lan - Dashboard"``
    Strip everything after the first separator, normalize, and validate.
    """
    cleaned = title.strip()
    cleaned = _TITLE_TRIM_RE.sub("", cleaned)
    cleaned = cleaned.strip()
    if _is_plausible_hostname(cleaned):
        return _normalize_hostname(cleaned)
    return None


def _from_http_title(banners: dict[str, str]) -> str | None:
    """Parse an HTTP banner for an embedded `title=...` segment.

    `grab_http_banner` is extended to append `; title=<text>` when an
    HTML title was extracted. This helper unpacks that.
    """
    for raw in banners.values():
        if not raw or "title=" not in raw:
            continue
        for part in raw.split(";"):
            key, sep, value = part.strip().partition("=")
            if sep and key == "title":
                hint = extract_hostname_from_title(value)
                if hint:
                    return hint
    return None


async def reverse_dns(ip: str, *, timeout: float = 2.0) -> str | None:
    """Async wrapper around ``socket.gethostbyaddr``.

    Returns the primary hostname or ``None`` on lookup failure / timeout.
    Runs the blocking call in a worker thread so the event loop is not
    stalled by slow PTR resolvers.
    """
    try:
        host, _aliases, _addrs = await asyncio.wait_for(
            asyncio.to_thread(socket.gethostbyaddr, ip),
            timeout=timeout,
        )
    except (TimeoutError, OSError, socket.herror, socket.gaierror):
        return None
    if _is_plausible_hostname(host):
        return _normalize_hostname(host)
    return None


# ── Orchestrator ────────────────────────────────────────────────────


_PRIORITY: tuple[HostnameSource, ...] = (
    HostnameSource.MDNS,
    HostnameSource.SNMP,
    HostnameSource.HTTP_TITLE,
    HostnameSource.DNS_REVERSE,
)


async def resolve_hostname(
    *,
    ip: str | None,
    banners: dict[str, str] | None = None,
    protocol_details: dict[str, Any] | None = None,
    do_dns_reverse: bool = True,
    dns_timeout: float = 2.0,
) -> tuple[str | None, list[HostnameSource]]:
    """Pick the best hostname and return every source that contributed.

    Returns a tuple ``(chosen, sources)``:
        - ``chosen``: the highest-priority non-empty candidate
        - ``sources``: every source that produced a usable candidate,
          ordered by priority

    The caller can persist ``chosen`` to ``identity.hostname`` and
    ``sources`` to ``identity.hostnameSources``. Storing every source
    lets the UI surface where the name came from and surface conflicts.
    """
    banners = banners or {}
    protocol_details = protocol_details or {}

    candidates: dict[HostnameSource, str] = {}

    mdns_name = _from_mdns(protocol_details)
    if mdns_name:
        candidates[HostnameSource.MDNS] = mdns_name

    snmp_name = _from_snmp(banners, protocol_details)
    if snmp_name:
        candidates[HostnameSource.SNMP] = snmp_name

    lldp_name = _from_lldp(protocol_details)
    if lldp_name:
        # LLDP rolls into the SNMP slot for priority since both come from
        # admin-managed gear. We keep the source distinct in the list.
        candidates.setdefault(HostnameSource.SNMP, lldp_name)

    title_name = _from_http_title(banners)
    if title_name:
        candidates[HostnameSource.HTTP_TITLE] = title_name

    if do_dns_reverse and ip and not candidates:
        # Only spend on the PTR lookup when no other source produced a name.
        ptr = await reverse_dns(ip, timeout=dns_timeout)
        if ptr:
            candidates[HostnameSource.DNS_REVERSE] = ptr

    if not candidates:
        return None, []

    chosen_source = next((s for s in _PRIORITY if s in candidates), None)
    if chosen_source is None:
        return None, []

    chosen = candidates[chosen_source]
    sources = [s for s in _PRIORITY if s in candidates]

    # If LLDP contributed a hostname distinct from SNMP, surface it too.
    if lldp_name and lldp_name != candidates.get(HostnameSource.SNMP):
        # Already represented under SNMP slot; no extra entry needed.
        pass
    elif lldp_name and HostnameSource.SNMP not in sources:
        sources.append(HostnameSource.SNMP)

    logger.debug(
        "hostname_resolved",
        ip=ip,
        chosen=chosen,
        source=chosen_source.value,
        all_sources=[s.value for s in sources],
    )
    return chosen, sources
