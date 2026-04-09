"""Abstract base class for plugin handlers.

Every core/default/community plugin implements this interface. Default
implementations return empty results so plugins only override the
touchpoints they declare in their manifest.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar


class PluginHandler(ABC):
    """Base class for all plugin handler implementations.

    Class-level constants MANIFEST and COMMAND_DEFINITIONS must be
    defined by each concrete handler.  The runtime instance receives
    the persisted config and (decrypted) credentials so it can talk to
    its external system.
    """

    # ── Class-level constants (set by each subclass) ─────────────
    MANIFEST: ClassVar[dict[str, Any]]
    """Static plugin manifest dict matching the PluginManifest schema."""

    COMMAND_DEFINITIONS: ClassVar[list[dict[str, Any]]]
    """Command catalog entries contributed by this plugin."""

    # ── Instance attributes ──────────────────────────────────────

    def __init__(self, config: dict[str, Any], credentials: dict[str, str] | None = None) -> None:
        self.config = config
        self.credentials = credentials

    # ── Lifecycle (required overrides) ───────────────────────────

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the external system.

        Returns True on success, False on failure.
        """

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Return health status dict matching PluginHealthStatus schema."""

    async def disconnect(self) -> None:  # noqa: B027
        """Clean up connections and resources.  Default is a no-op."""

    # ── Touchpoints (optional — default impls return empty) ──────

    async def enrich_profile(
        self,
        node_id: str,  # noqa: ARG002
        profile: dict[str, Any],  # noqa: ARG002
    ) -> dict[str, Any]:
        """Return plugin-specific data to merge into profile.pluginData[pluginId]."""
        return {}

    async def discover_nodes(self) -> list[dict[str, Any]]:
        """Return discovered resources from the external system."""
        return []

    def get_commands(self) -> list[dict[str, Any]]:
        """Return contributed command definitions (mirrors COMMAND_DEFINITIONS)."""
        return self.COMMAND_DEFINITIONS

    async def execute_command(
        self,
        command_id: str,
        target: dict[str, Any],  # noqa: ARG002
        params: dict[str, Any],  # noqa: ARG002
    ) -> dict[str, Any]:
        """Execute a plugin command.  Returns a result dict with at least
        ``success`` (bool) and ``output`` (str) keys."""
        return {
            "success": False,
            "output": f"Command '{command_id}' not implemented by this plugin",
        }

    async def get_topology_edges(
        self,
        node_id: str,  # noqa: ARG002
    ) -> list[dict[str, Any]]:
        """Return relationship edges for the knowledge graph."""
        return []

    def get_workflow_blocks(self) -> list[dict[str, Any]]:
        """Return custom workflow block definitions."""
        return []
