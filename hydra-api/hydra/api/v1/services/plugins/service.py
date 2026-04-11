"""Plugin lifecycle service for registration, configuration, and health management."""

import json
import re
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog
from pymongo import ASCENDING, DESCENDING

from hydra.api.v1.core.crypto import decrypt_value, encrypt_value
from hydra.api.v1.core.exceptions import ConflictError, NotFoundError, ValidationError
from hydra.api.v1.models.plugins import (
    BindNodeRequest,
    PluginListParams,
    PluginStatus,
    RegisterPluginRequest,
    UpdatePluginConfigRequest,
)
from hydra.api.v1.models.query import AuditAction
from hydra.api.v1.services.icons import resolve_icon_descriptor
from hydra.api.v1.services.query import log_audit
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)

# Health check failure threshold before marking plugin as errored
HEALTH_FAILURE_THRESHOLD = 3


class PluginNotFoundError(NotFoundError):
    """Plugin not found."""

    def __init__(self, plugin_id: str) -> None:
        super().__init__("plugin", plugin_id)


class PluginService:
    """Service for managing plugin lifecycle operations."""

    def __init__(self, mongodb: MongoDB) -> None:
        self.mongodb = mongodb
        self.collection = mongodb.plugins

    @staticmethod
    def _encrypt_credentials(credentials: dict[str, str]) -> str:
        """Encrypt credentials using Fernet symmetric encryption."""
        raw = json.dumps(credentials, sort_keys=True)
        return encrypt_value(raw)

    @staticmethod
    def _decrypt_credentials(encrypted: str) -> dict[str, str]:
        """Decrypt credentials from Fernet-encrypted storage."""
        raw = decrypt_value(encrypted)
        result: dict[str, str] = json.loads(raw)
        return result

    async def register_plugin(
        self,
        request: RegisterPluginRequest,
        user_id: str,
    ) -> dict[str, Any]:
        """Register a new plugin.

        Args:
            request: Plugin registration details.
            user_id: User performing the registration.

        Returns:
            The created plugin document (formatted for response).

        Raises:
            ConflictError: If a plugin with the same ID already exists.
        """
        plugin_id = request.manifest.plugin_id
        now = datetime.now(UTC)

        existing = await self.collection.find_one({"pluginId": plugin_id})
        if existing:
            raise ConflictError("plugin", plugin_id)

        doc: dict[str, Any] = {
            "pluginId": plugin_id,
            "manifest": request.manifest.model_dump(by_alias=True),
            "status": PluginStatus.INSTALLED.value,
            "config": request.config,
            "nodeBindings": [],
            "health": {
                "status": "unknown",
                "lastCheck": None,
                "consecutiveFailures": 0,
                "lastError": None,
                "responseTimeMs": None,
            },
            "createdAt": now,
            "updatedAt": now,
        }

        if request.credentials:
            doc["credentials"] = self._encrypt_credentials(request.credentials)

        await self.collection.insert_one(doc)

        logger.info("plugin_registered", plugin_id=plugin_id, user_id=user_id)

        await log_audit(
            AuditAction.CREATE,
            "plugin",
            plugin_id,
            "user",
            user_id,
            True,
            details={"name": request.manifest.name, "classification": request.manifest.classification.value},
        )

        return self._format_plugin(doc)

    async def configure_plugin(
        self,
        plugin_id: str,
        request: UpdatePluginConfigRequest,
        user_id: str,
    ) -> dict[str, Any]:
        """Update plugin configuration.

        Transitions an installed plugin to configured status.

        Args:
            plugin_id: Plugin identifier.
            request: Configuration update details.
            user_id: User performing the update.

        Returns:
            Updated plugin document.
        """
        doc = await self.collection.find_one({"pluginId": plugin_id})
        if not doc:
            raise PluginNotFoundError(plugin_id)

        now = datetime.now(UTC)
        update_fields: dict[str, Any] = {"updatedAt": now}

        if request.config is not None:
            update_fields["config"] = request.config
        if request.credentials is not None:
            update_fields["credentials"] = self._encrypt_credentials(request.credentials)

        # Transition installed → configured
        current_status = doc.get("status", PluginStatus.INSTALLED.value)
        if current_status == PluginStatus.INSTALLED.value:
            update_fields["status"] = PluginStatus.CONFIGURED.value

        await self.collection.update_one(
            {"pluginId": plugin_id},
            {"$set": update_fields},
        )

        logger.info(
            "plugin_configured",
            plugin_id=plugin_id,
            fields=list(update_fields.keys()),
        )

        await log_audit(
            AuditAction.UPDATE,
            "plugin",
            plugin_id,
            "user",
            user_id,
            True,
            details={"fields": list(update_fields.keys())},
        )

        updated = await self.collection.find_one({"pluginId": plugin_id})
        return self._format_plugin(updated)  # type: ignore[arg-type]

    async def enable_plugin(
        self,
        plugin_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """Enable a plugin and optionally activate it via health check.

        Args:
            plugin_id: Plugin identifier.
            user_id: User performing the action.

        Returns:
            Updated plugin document.
        """
        doc = await self.collection.find_one({"pluginId": plugin_id})
        if not doc:
            raise PluginNotFoundError(plugin_id)

        current_status = doc.get("status", PluginStatus.INSTALLED.value)
        if current_status == PluginStatus.ACTIVE.value:
            return self._format_plugin(doc)

        now = datetime.now(UTC)
        update_fields: dict[str, Any] = {
            "status": PluginStatus.ENABLED.value,
            "updatedAt": now,
        }

        # If the plugin has a health check endpoint, try to activate it.
        # Plugins without a healthCheckEndpoint (CLI tools, config-driven
        # plugins) are activated directly — the user's explicit enable
        # action is sufficient.
        health_endpoint = doc.get("manifest", {}).get("healthCheckEndpoint")
        if health_endpoint:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    start = datetime.now(UTC)
                    resp = await client.get(health_endpoint)
                    elapsed_ms = (datetime.now(UTC) - start).total_seconds() * 1000

                    if resp.status_code < 400:
                        update_fields["status"] = PluginStatus.ACTIVE.value
                        update_fields["health"] = {
                            "status": "healthy",
                            "lastCheck": now,
                            "consecutiveFailures": 0,
                            "lastError": None,
                            "responseTimeMs": elapsed_ms,
                        }
                    else:
                        update_fields["health.lastCheck"] = now
                        update_fields["health.lastError"] = f"HTTP {resp.status_code}"
            except httpx.HTTPError as exc:
                logger.warning(
                    "plugin_health_check_failed_on_enable",
                    plugin_id=plugin_id,
                    error=str(exc),
                )
                update_fields["health.lastCheck"] = now
                update_fields["health.lastError"] = str(exc)
        else:
            # No health endpoint: activate directly
            update_fields["status"] = PluginStatus.ACTIVE.value
            update_fields["health"] = {
                "status": "healthy",
                "lastCheck": now,
                "consecutiveFailures": 0,
                "lastError": None,
                "responseTimeMs": None,
            }

        await self.collection.update_one(
            {"pluginId": plugin_id},
            {"$set": update_fields},
        )

        # Push config to all bound nodes if plugin became active
        if update_fields["status"] == PluginStatus.ACTIVE.value:
            await self._push_config_to_bound_nodes(plugin_id, doc)

        logger.info("plugin_enabled", plugin_id=plugin_id, status=update_fields["status"])

        await log_audit(
            AuditAction.UPDATE,
            "plugin",
            plugin_id,
            "user",
            user_id,
            True,
            details={"action": "enable", "status": update_fields["status"]},
        )

        updated = await self.collection.find_one({"pluginId": plugin_id})
        return self._format_plugin(updated)  # type: ignore[arg-type]

    async def disable_plugin(
        self,
        plugin_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """Disable a plugin.

        Args:
            plugin_id: Plugin identifier.
            user_id: User performing the action.

        Returns:
            Updated plugin document.
        """
        doc = await self.collection.find_one({"pluginId": plugin_id})
        if not doc:
            raise PluginNotFoundError(plugin_id)

        now = datetime.now(UTC)
        await self.collection.update_one(
            {"pluginId": plugin_id},
            {"$set": {"status": PluginStatus.DISABLED.value, "updatedAt": now}},
        )

        logger.info("plugin_disabled", plugin_id=plugin_id)

        await log_audit(
            AuditAction.UPDATE,
            "plugin",
            plugin_id,
            "user",
            user_id,
            True,
            details={"action": "disable"},
        )

        updated = await self.collection.find_one({"pluginId": plugin_id})
        return self._format_plugin(updated)  # type: ignore[arg-type]

    async def uninstall_plugin(
        self,
        plugin_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """Uninstall a plugin (soft delete).

        Args:
            plugin_id: Plugin identifier.
            user_id: User performing the action.

        Returns:
            The uninstalled plugin document.
        """
        doc = await self.collection.find_one({"pluginId": plugin_id})
        if not doc:
            raise PluginNotFoundError(plugin_id)

        now = datetime.now(UTC)
        await self.collection.update_one(
            {"pluginId": plugin_id},
            {"$set": {
                "status": PluginStatus.DISABLED.value,
                "uninstalledAt": now,
                "updatedAt": now,
            }},
        )

        logger.info("plugin_uninstalled", plugin_id=plugin_id, user_id=user_id)

        await log_audit(
            AuditAction.DELETE,
            "plugin",
            plugin_id,
            "user",
            user_id,
            True,
        )

        doc["status"] = PluginStatus.DISABLED.value
        doc["uninstalledAt"] = now
        doc["updatedAt"] = now
        return self._format_plugin(doc)

    async def get_plugin(self, plugin_id: str) -> dict[str, Any]:
        """Retrieve a single plugin by its identifier.

        Args:
            plugin_id: Plugin identifier.

        Returns:
            Formatted plugin document.

        Raises:
            PluginNotFoundError: If no plugin exists with the given ID.
        """
        doc = await self.collection.find_one({"pluginId": plugin_id})
        if not doc:
            raise PluginNotFoundError(plugin_id)
        return self._format_plugin(doc)

    async def list_plugins(
        self,
        params: PluginListParams,
        user_id: str,
    ) -> tuple[list[dict[str, Any]], int]:
        """List plugins with filtering, sorting, and pagination.

        Args:
            params: Filter and pagination parameters.
            user_id: The requesting user's ID.

        Returns:
            A tuple of (list of plugin summaries, total count).
        """
        filter_query: dict[str, Any] = {"uninstalledAt": {"$exists": False}}

        if params.status:
            filter_query["status"] = params.status.value
        if params.classification:
            filter_query["manifest.classification"] = params.classification.value
        if params.category:
            filter_query["manifest.category"] = params.category.value
        if params.search:
            escaped = re.escape(params.search)
            filter_query["$or"] = [
                {"manifest.name": {"$regex": escaped, "$options": "i"}},
                {"manifest.description": {"$regex": escaped, "$options": "i"}},
                {"pluginId": {"$regex": escaped, "$options": "i"}},
            ]

        sort_field_map = {
            "createdAt": "createdAt",
            "name": "manifest.name",
            "status": "status",
        }
        sort_field = sort_field_map.get(params.sort_by, "createdAt")
        sort_direction = DESCENDING if params.sort_order == "desc" else ASCENDING

        total = await self.collection.count_documents(filter_query)

        cursor = (
            self.collection.find(filter_query)
            .sort(sort_field, sort_direction)
            .skip(params.offset)
            .limit(params.limit)
        )

        plugins: list[dict[str, Any]] = []
        async for doc in cursor:
            plugins.append(self._format_plugin_summary(doc))

        logger.info(
            "plugins_listed",
            total=total,
            returned=len(plugins),
            user_id=user_id,
        )

        return plugins, total

    async def get_health(self, plugin_id: str) -> dict[str, Any]:
        """Get the current health status of a plugin.

        Args:
            plugin_id: Plugin identifier.

        Returns:
            Health status subdocument.
        """
        doc = await self.collection.find_one({"pluginId": plugin_id})
        if not doc:
            raise PluginNotFoundError(plugin_id)
        return doc.get("health", {  # type: ignore[no-any-return]
            "status": "unknown",
            "lastCheck": None,
            "consecutiveFailures": 0,
            "lastError": None,
            "responseTimeMs": None,
        })

    async def test_connection(self, plugin_id: str) -> dict[str, Any]:
        """Test plugin connectivity without changing state.

        Args:
            plugin_id: Plugin identifier.

        Returns:
            Connection test results.
        """
        doc = await self.collection.find_one({"pluginId": plugin_id})
        if not doc:
            raise PluginNotFoundError(plugin_id)

        health_endpoint = doc.get("manifest", {}).get("healthCheckEndpoint")
        if not health_endpoint:
            # CLI/config-driven plugins don't have an HTTP endpoint to test.
            # Report as reachable if the plugin is currently active.
            is_active = doc.get("status") == PluginStatus.ACTIVE.value
            return {
                "reachable": is_active,
                "error": None if is_active else "No health check endpoint — enable the plugin to activate it",
                "responseTimeMs": None,
            }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                start = datetime.now(UTC)
                resp = await client.get(health_endpoint)
                elapsed_ms = (datetime.now(UTC) - start).total_seconds() * 1000

                return {
                    "reachable": resp.status_code < 400,
                    "statusCode": resp.status_code,
                    "responseTimeMs": round(elapsed_ms, 2),
                    "error": None if resp.status_code < 400 else f"HTTP {resp.status_code}",
                }
        except httpx.HTTPError as exc:
            return {
                "reachable": False,
                "error": str(exc),
                "responseTimeMs": None,
            }

    async def bind_node(
        self,
        plugin_id: str,
        node_id: str,
        request: BindNodeRequest,
        user_id: str,
    ) -> dict[str, Any]:
        """Bind a node to a plugin.

        Args:
            plugin_id: Plugin identifier.
            node_id: Node to bind.
            request: Binding configuration.
            user_id: User performing the action.

        Returns:
            Updated plugin document.

        Raises:
            PluginNotFoundError: If the plugin does not exist.
            ValidationError: If the node does not exist.
        """
        doc = await self.collection.find_one({"pluginId": plugin_id})
        if not doc:
            raise PluginNotFoundError(plugin_id)

        # Validate the node exists
        node = await self.mongodb.nodes.find_one({"nodeId": node_id})
        if not node:
            raise ValidationError(
                f"Node '{node_id}' not found",
                {"nodeId": node_id},
            )

        # Check for existing binding
        for binding in doc.get("nodeBindings", []):
            if binding.get("nodeId") == node_id:
                raise ValidationError(
                    f"Node '{node_id}' is already bound to plugin '{plugin_id}'",
                    {"pluginId": plugin_id, "nodeId": node_id},
                )

        now = datetime.now(UTC)
        binding_doc: dict[str, Any] = {
            "nodeId": node_id,
            "enabled": True,
            "allowedCommands": request.allowed_commands,
            "boundAt": now,
        }

        await self.collection.update_one(
            {"pluginId": plugin_id},
            {
                "$push": {"nodeBindings": binding_doc},
                "$set": {"updatedAt": now},
            },
        )

        # If plugin is active, push config to the newly bound node
        if doc.get("status") == PluginStatus.ACTIVE.value:
            await self._push_config_to_single_node(plugin_id, node_id, node)

        logger.info(
            "plugin_node_bound",
            plugin_id=plugin_id,
            node_id=node_id,
        )

        await log_audit(
            AuditAction.UPDATE,
            "plugin",
            plugin_id,
            "user",
            user_id,
            True,
            details={"action": "bind_node", "nodeId": node_id},
        )

        updated = await self.collection.find_one({"pluginId": plugin_id})
        return self._format_plugin(updated)  # type: ignore[arg-type]

    async def unbind_node(
        self,
        plugin_id: str,
        node_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """Remove a node binding from a plugin.

        Args:
            plugin_id: Plugin identifier.
            node_id: Node to unbind.
            user_id: User performing the action.

        Returns:
            Updated plugin document.
        """
        doc = await self.collection.find_one({"pluginId": plugin_id})
        if not doc:
            raise PluginNotFoundError(plugin_id)

        now = datetime.now(UTC)
        await self.collection.update_one(
            {"pluginId": plugin_id},
            {
                "$pull": {"nodeBindings": {"nodeId": node_id}},
                "$set": {"updatedAt": now},
            },
        )

        logger.info(
            "plugin_node_unbound",
            plugin_id=plugin_id,
            node_id=node_id,
        )

        await log_audit(
            AuditAction.UPDATE,
            "plugin",
            plugin_id,
            "user",
            user_id,
            True,
            details={"action": "unbind_node", "nodeId": node_id},
        )

        updated = await self.collection.find_one({"pluginId": plugin_id})
        return self._format_plugin(updated)  # type: ignore[arg-type]

    async def check_health(self, plugin_id: str) -> dict[str, Any]:
        """Run a health check and update plugin state.

        Consecutive failures above the threshold transition the plugin to error.
        A successful check transitions an enabled/error plugin to active.

        Args:
            plugin_id: Plugin identifier.

        Returns:
            Updated health status.
        """
        doc = await self.collection.find_one({"pluginId": plugin_id})
        if not doc:
            raise PluginNotFoundError(plugin_id)

        health_endpoint = doc.get("manifest", {}).get("healthCheckEndpoint")
        if not health_endpoint:
            # CLI/config-driven plugins report healthy when active
            current_status = doc.get("status")
            if current_status == PluginStatus.ACTIVE.value:
                return {
                    "status": "healthy",
                    "lastCheck": datetime.now(UTC),
                    "consecutiveFailures": 0,
                    "lastError": None,
                    "responseTimeMs": None,
                }
            return doc.get("health", {"status": "unknown"})  # type: ignore[no-any-return]

        now = datetime.now(UTC)
        current_failures = doc.get("health", {}).get("consecutiveFailures", 0)
        update_fields: dict[str, Any] = {"updatedAt": now}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                start = datetime.now(UTC)
                resp = await client.get(health_endpoint)
                elapsed_ms = (datetime.now(UTC) - start).total_seconds() * 1000

                if resp.status_code < 400:
                    # Success: reset failures, transition to active
                    update_fields["health"] = {
                        "status": "healthy",
                        "lastCheck": now,
                        "consecutiveFailures": 0,
                        "lastError": None,
                        "responseTimeMs": elapsed_ms,
                    }
                    current_status = doc.get("status")
                    if current_status in (
                        PluginStatus.ENABLED.value,
                        PluginStatus.ERROR.value,
                    ):
                        update_fields["status"] = PluginStatus.ACTIVE.value
                else:
                    new_failures = current_failures + 1
                    health_status = "degraded" if new_failures < HEALTH_FAILURE_THRESHOLD else "unhealthy"
                    update_fields["health"] = {
                        "status": health_status,
                        "lastCheck": now,
                        "consecutiveFailures": new_failures,
                        "lastError": f"HTTP {resp.status_code}",
                        "responseTimeMs": elapsed_ms,
                    }
                    if new_failures >= HEALTH_FAILURE_THRESHOLD:
                        update_fields["status"] = PluginStatus.ERROR.value

        except httpx.HTTPError as exc:
            new_failures = current_failures + 1
            health_status = "degraded" if new_failures < HEALTH_FAILURE_THRESHOLD else "unhealthy"
            update_fields["health"] = {
                "status": health_status,
                "lastCheck": now,
                "consecutiveFailures": new_failures,
                "lastError": str(exc),
                "responseTimeMs": None,
            }
            if new_failures >= HEALTH_FAILURE_THRESHOLD:
                update_fields["status"] = PluginStatus.ERROR.value

        await self.collection.update_one(
            {"pluginId": plugin_id},
            {"$set": update_fields},
        )

        return update_fields.get("health", doc.get("health", {}))  # type: ignore[no-any-return]

    def _format_plugin(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Format a plugin document for API response.

        Strips _id and credentials, formats dates.
        """
        manifest = doc.get("manifest", {})
        return {
            "pluginId": doc["pluginId"],
            "manifest": manifest,
            "status": doc["status"],
            "icon": resolve_icon_descriptor(
                name=manifest.get("name"),
                provider=str(doc.get("pluginId", "")).removeprefix("plg::"),
                fallback="plug",
            ),
            "config": doc.get("config", {}),
            "nodeBindings": doc.get("nodeBindings", []),
            "health": doc.get("health", {
                "status": "unknown",
                "lastCheck": None,
                "consecutiveFailures": 0,
                "lastError": None,
                "responseTimeMs": None,
            }),
            "createdAt": doc["createdAt"],
            "updatedAt": doc["updatedAt"],
        }

    def _format_plugin_summary(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Format a plugin document for list response."""
        manifest = doc.get("manifest", {})
        return {
            "pluginId": doc["pluginId"],
            "name": manifest.get("name", ""),
            "status": doc["status"],
            "icon": resolve_icon_descriptor(
                name=manifest.get("name"),
                provider=str(doc.get("pluginId", "")).removeprefix("plg::"),
                fallback="plug",
            ),
            "classification": manifest.get("classification", "community"),
            "category": manifest.get("category", "other"),
            "healthStatus": doc.get("health", {}).get("status", "unknown"),
            "nodeCount": len(doc.get("nodeBindings", [])),
            "createdAt": doc["createdAt"],
        }

    async def _push_config_to_bound_nodes(
        self,
        plugin_id: str,
        plugin_doc: dict[str, Any],
    ) -> None:
        """Push plugin config to all bound nodes based on their tier."""
        from hydra.api.v1.services.plugins.config_push import PluginConfigPush

        push = PluginConfigPush(self.mongodb)

        for binding in plugin_doc.get("nodeBindings", []):
            node_id = binding.get("nodeId")
            if not node_id or not binding.get("enabled", True):
                continue
            node = await self.mongodb.nodes.find_one({"nodeId": node_id})
            if not node:
                continue
            payload = await push.build_config_payload(plugin_id, node_id)
            tier = node.get("agentTier", "normal")
            if tier == "max":
                await push.push_to_max_tier(node, payload)
            elif tier in ("normal", "max"):
                await push.embed_in_poll_response(node_id, payload)

    async def _push_config_to_single_node(
        self,
        plugin_id: str,
        node_id: str,
        node_doc: dict[str, Any],
    ) -> None:
        """Push plugin config to a single newly-bound node."""
        from hydra.api.v1.services.plugins.config_push import PluginConfigPush

        push = PluginConfigPush(self.mongodb)
        payload = await push.build_config_payload(plugin_id, node_id)
        tier = node_doc.get("agentTier", "normal")
        if tier == "max":
            await push.push_to_max_tier(node_doc, payload)
        elif tier in ("normal", "max"):
            await push.embed_in_poll_response(node_id, payload)
