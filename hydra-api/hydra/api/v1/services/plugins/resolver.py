"""Plugin execution path resolver.

Determines how a plugin-contributed command should be dispatched to
its target node based on plugin bindings and agent tier.
"""


import structlog

from hydra.api.v1.models.plugins import ExecutionPathType
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)


class PluginResolver:
    """Resolves the execution path for plugin-contributed commands."""

    def __init__(self, mongodb: MongoDB) -> None:
        self.mongodb = mongodb
        self.plugins = mongodb.plugins

    async def resolve_execution_path(
        self,
        registry_id: str,
        node_id: str,
    ) -> ExecutionPathType | None:
        """Determine the execution path for a command via plugin resolution.

        Queries the plugins collection for active plugins that contribute
        the given registry_id and have a binding for the target node.

        Args:
            registry_id: Command registry identifier (e.g. 'reg::docker::restart').
            node_id: Target node identifier.

        Returns:
            The resolved execution path, or None if no plugin handles this command.
        """
        # Find an active plugin that contributes this command
        plugin = await self.plugins.find_one({
            "status": "active",
            "manifest.contributedCommands": registry_id,
            "uninstalledAt": {"$exists": False},
        })

        if not plugin:
            return None

        # Check if the plugin has a binding for this node
        bindings = plugin.get("nodeBindings", [])
        node_binding = next(
            (b for b in bindings if b.get("nodeId") == node_id and b.get("enabled", True)),
            None,
        )

        if not node_binding:
            logger.debug(
                "plugin_no_binding_for_node",
                plugin_id=plugin["pluginId"],
                node_id=node_id,
                registry_id=registry_id,
            )
            return None

        # Check if this specific command is allowed for this binding
        allowed_commands = node_binding.get("allowedCommands", [])
        if allowed_commands and registry_id not in allowed_commands:
            logger.debug(
                "plugin_command_not_allowed_for_node",
                plugin_id=plugin["pluginId"],
                node_id=node_id,
                registry_id=registry_id,
                allowed=allowed_commands,
            )
            return None

        # Determine path based on agent tier
        node = await self.mongodb.nodes.find_one({"nodeId": node_id})
        if not node:
            return None

        tier = node.get("agentTier", "normal")

        if tier == "max":
            return ExecutionPathType.PLUGIN_VIA_AGENT_DIRECT
        if tier == "normal":
            return ExecutionPathType.PLUGIN_VIA_AGENT_POLL
        # lite tier or anything else: plugins cannot dispatch via lite agents
        return None
