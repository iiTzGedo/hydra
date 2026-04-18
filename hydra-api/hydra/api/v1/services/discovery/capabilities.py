"""Linux capability detection for raw-socket scanning.

ARP and ICMP scanning require ``CAP_NET_RAW`` on Linux. This module
detects whether the running process holds that capability so the scanner
can choose between privileged (Layer 1) and unprivileged (TCP-only) paths.
"""

from __future__ import annotations

import platform
import sys
from functools import lru_cache
from pathlib import Path
from typing import Literal, TypedDict

import structlog

logger = structlog.get_logger(__name__)

# Capability bit positions per ``include/uapi/linux/capability.h``
_CAP_NET_RAW = 13
_CAP_NET_ADMIN = 12

_PROC_STATUS = Path("/proc/self/status")


class CapabilityStatus(TypedDict):
    """Privilege status reported alongside scan results."""

    capNetRaw: bool
    capNetAdmin: bool
    platform: str
    fallbackMode: Literal["full", "tcp-only"]


def _read_cap_eff() -> int | None:
    """Read the effective capability bitmask from ``/proc/self/status``.

    Returns the bitmask as an int, or ``None`` if the file cannot be read
    (non-Linux platforms, restricted environments, etc.).
    """
    if sys.platform != "linux":
        return None
    try:
        for line in _PROC_STATUS.read_text().splitlines():
            if line.startswith("CapEff:"):
                return int(line.split()[1], 16)
    except (OSError, ValueError, IndexError) as exc:
        logger.debug("capabilities.read_failed", error=str(exc))
    return None


@lru_cache(maxsize=1)
def has_cap_net_raw() -> bool:
    """Return True if the process holds ``CAP_NET_RAW``.

    Always False on non-Linux platforms. Cached for the life of the process —
    capabilities cannot be acquired at runtime without ``execve``.
    """
    cap = _read_cap_eff()
    if cap is None:
        return False
    return bool(cap & (1 << _CAP_NET_RAW))


@lru_cache(maxsize=1)
def has_cap_net_admin() -> bool:
    """Return True if the process holds ``CAP_NET_ADMIN``."""
    cap = _read_cap_eff()
    if cap is None:
        return False
    return bool(cap & (1 << _CAP_NET_ADMIN))


def capability_status() -> CapabilityStatus:
    """Snapshot of relevant capabilities for inclusion in scan responses."""
    return {
        "capNetRaw": has_cap_net_raw(),
        "capNetAdmin": has_cap_net_admin(),
        "platform": platform.system().lower(),
        "fallbackMode": "full" if has_cap_net_raw() else "tcp-only",
    }


def reset_capability_cache() -> None:
    """Clear the cached capability lookups (test-only)."""
    has_cap_net_raw.cache_clear()
    has_cap_net_admin.cache_clear()
