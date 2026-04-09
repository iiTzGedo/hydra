"""Installations service package."""

from .proxmox import ProxmoxInstallationService
from .service import InstallationService

__all__ = ["InstallationService", "ProxmoxInstallationService"]
