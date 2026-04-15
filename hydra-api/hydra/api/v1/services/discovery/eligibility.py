"""Eligibility assessment for discovered devices.

Determines agent compatibility, profiling strategy, and remote install
feasibility based on fingerprint, classification, and open ports.
"""

from __future__ import annotations

from hydra.api.v1.models.discovery.enums import ProfilingStrategy
from hydra.api.v1.models.discovery.schemas import (
    Classification,
    Eligibility,
    Fingerprint,
)


def assess_eligibility(
    fingerprint: Fingerprint,
    classification: Classification,
    open_ports: list[int],
) -> Eligibility:
    """Assess agent compatibility and remote install eligibility.

    Args:
        fingerprint: Device fingerprint with ports, OS hint, vendor.
        classification: Device classification result.
        open_ports: Raw open port list from the scan.

    Returns:
        Eligibility assessment with compatibility, strategy, and blockers.
    """
    suggested_class = classification.suggested_class
    is_compute = suggested_class == "compute"
    is_networking = suggested_class == "networking"
    is_iot = suggested_class == "iot"
    is_unknown = suggested_class == "unknown"

    has_ssh = 22 in open_ports
    os_hint = fingerprint.os_hint
    has_docker = 2375 in open_ports or 2376 in open_ports
    has_proxmox = 8006 in open_ports

    # ── Agent Compatibility ────────────────────────────────────────
    # Compute class + SSH + linux/freebsd/unknown OS
    agent_compatible = is_compute and has_ssh and os_hint in ("linux", None)

    # ── Platform Inference ─────────────────────────────────────────
    agent_platform: str | None = None
    if agent_compatible:
        vendor = fingerprint.vendor or ""
        if os_hint == "linux":
            # Default to x86_64; refine from vendor/banner in future waves
            if "Raspberry Pi" in vendor or "ODROID" in vendor or "Hardkernel" in vendor:
                agent_platform = "linux-arm64"
            else:
                agent_platform = "linux-x86_64"
        else:
            # os_hint is None — assume linux-x86_64 as default
            agent_platform = "linux-x86_64"

    # ── Profiling Strategy ─────────────────────────────────────────
    profiling_strategy: ProfilingStrategy | None = None
    if is_compute and agent_compatible:
        profiling_strategy = ProfilingStrategy.AGENT
    elif is_networking and 161 in open_ports:
        profiling_strategy = ProfilingStrategy.SNMP
    elif is_networking:
        profiling_strategy = ProfilingStrategy.MANUAL
    elif is_iot:
        if 8123 in open_ports:
            profiling_strategy = ProfilingStrategy.HOMEASSISTANT
        else:
            profiling_strategy = ProfilingStrategy.INTEGRATION
    elif is_compute and not agent_compatible:
        profiling_strategy = ProfilingStrategy.MANUAL
    elif is_unknown:
        profiling_strategy = ProfilingStrategy.NONE

    # ── Remote Install Assessment ──────────────────────────────────
    remote_installable = agent_compatible and has_ssh
    remote_install_method: str | None = None
    if remote_installable:
        if has_proxmox:
            remote_install_method = "proxmox-exec"
        elif has_docker:
            remote_install_method = "docker-exec"
        else:
            remote_install_method = "ssh"

    # ── Blockers ───────────────────────────────────────────────────
    blockers: list[str] = []
    remote_install_blockers: list[str] = []

    if is_unknown:
        blockers.append(
            "Device class is unknown — cannot determine registration strategy"
        )

    if is_compute and not has_ssh:
        remote_install_blockers.append("SSH (port 22) not detected")

    if is_compute and os_hint == "windows":
        remote_install_blockers.append(
            "Windows requires manual agent installation"
        )
        agent_platform = None

    if is_compute and os_hint == "embedded":
        remote_install_blockers.append(
            "Embedded OS may not support the Hydra agent"
        )
        agent_platform = None

    # ── Notes ──────────────────────────────────────────────────────
    notes: list[str] = []
    if is_iot:
        notes.append(
            "IoT devices are profiled via integrations, not the Hydra agent"
        )
    if is_networking:
        notes.append(
            "Networking devices are profiled via SNMP when available"
        )
    if agent_platform and "arm" in agent_platform:
        notes.append(
            f"ARM platform detected ({agent_platform}); ensure correct agent binary"
        )

    return Eligibility(
        registerable=suggested_class != "unknown",
        agent_compatible=agent_compatible,
        agent_platform=agent_platform,
        profiling_strategy=profiling_strategy,
        remote_installable=remote_installable,
        remote_install_method=remote_install_method,
        remote_install_blockers=remote_install_blockers,
        blockers=blockers,
        notes=notes,
    )
