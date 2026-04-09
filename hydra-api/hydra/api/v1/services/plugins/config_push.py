"""Plugin configuration push service.

Handles pushing plugin configuration to agent nodes via direct HTTP
(max-tier) or embedding in poll responses (normal-tier).
"""

from typing import Any

import httpx
import structlog

from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)


class PluginConfigPush:
    """Pushes plugin configuration to agent nodes."""

    def __init__(self, mongodb: MongoDB) -> None:
        self.mongodb = mongodb
        self.plugins = mongodb.plugins

    async def build_config_payload(
        self,
        plugin_id: str,
        node_id: str,
    ) -> dict[str, Any]:
        """Build the configuration payload for a specific plugin-node pair.

        Args:
            plugin_id: Plugin identifier.
            node_id: Target node identifier.

        Returns:
            Configuration payload dict ready for delivery.
        """
        plugin = await self.plugins.find_one({"pluginId": plugin_id})
        if not plugin:
            return {}

        manifest = plugin.get("manifest", {})
        config = plugin.get("config", {})

        # Find the specific binding for this node
        bindings = plugin.get("nodeBindings", [])
        node_binding = next(
            (b for b in bindings if b.get("nodeId") == node_id),
            None,
        )

        return {
            "pluginId": plugin_id,
            "pluginName": manifest.get("name", ""),
            "version": manifest.get("version", ""),
            "config": config,
            "binding": {
                "nodeId": node_id,
                "enabled": node_binding.get("enabled", True) if node_binding else False,
                "allowedCommands": node_binding.get("allowedCommands", []) if node_binding else [],
            },
        }

    async def push_to_max_tier(
        self,
        node_doc: dict[str, Any],
        payload: dict[str, Any],
    ) -> bool:
        """Push configuration directly to a max-tier agent's HTTP server.

        Args:
            node_doc: Node document with serverAddress and serverPort.
            payload: Configuration payload to push.

        Returns:
            True if the push succeeded, False otherwise.
        """
        server_address = node_doc.get("serverAddress")
        server_port = node_doc.get("serverPort")
        api_key = node_doc.get("agentApiKey")

        if not server_address or not server_port:
            logger.warning(
                "plugin_config_push_missing_address",
                node_id=node_doc.get("nodeId"),
            )
            return False

        url = f"http://{server_address}:{server_port}/config"
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code < 400:
                    logger.info(
                        "plugin_config_pushed",
                        node_id=node_doc.get("nodeId"),
                        plugin_id=payload.get("pluginId"),
                    )
                    return True
                logger.warning(
                    "plugin_config_push_failed",
                    node_id=node_doc.get("nodeId"),
                    status_code=resp.status_code,
                )
                return False
        except httpx.HTTPError as exc:
            logger.warning(
                "plugin_config_push_error",
                node_id=node_doc.get("nodeId"),
                error=str(exc),
            )
            return False

    async def embed_in_poll_response(
        self,
        node_id: str,
        payload: dict[str, Any],
    ) -> bool:
        """Store config payload for delivery in the next agent poll response.

        Uses the commands collection to queue a config delivery command
        that the agent will pick up on its next poll cycle.

        Args:
            node_id: Target node identifier.
            payload: Configuration payload to embed.

        Returns:
            True if the payload was stored successfully.
        """
        from datetime import UTC, datetime

        doc = {
            "type": "plugin_config",
            "nodeId": node_id,
            "payload": payload,
            "createdAt": datetime.now(UTC),
            "delivered": False,
        }

        try:
            commands = self.mongodb.commands
            await commands.insert_one(doc)
            logger.info(
                "plugin_config_queued_for_poll",
                node_id=node_id,
                plugin_id=payload.get("pluginId"),
            )
            return True
        except Exception:
            logger.exception(
                "plugin_config_queue_failed",
                node_id=node_id,
            )
            return False
