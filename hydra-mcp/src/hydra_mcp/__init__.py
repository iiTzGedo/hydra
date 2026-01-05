"""Hydra MCP Service - AI interface layer for infrastructure queries."""

from hydra_mcp.client import HydraAPIError, HydraClient
from hydra_mcp.config import Settings, get_settings
from hydra_mcp.server import main, run, server
from hydra_mcp.toon import TOONFormatter

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "HydraAPIError",
    "HydraClient",
    "Settings",
    "get_settings",
    "TOONFormatter",
    "server",
    "main",
    "run",
]
