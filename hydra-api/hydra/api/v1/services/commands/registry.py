"""Command registry service for managing the command catalog."""

from typing import Any

import structlog

from hydra.api.v1.core.exceptions import CommandRegistryNotFoundError
from hydra.db.mongodb import MongoDB

from .builtin_commands import BUILTIN_COMMANDS

logger = structlog.get_logger(__name__)


class CommandRegistryService:
    """Service for managing the command definition catalog."""

    def __init__(self, mongodb: MongoDB):
        self.mongodb = mongodb
        self.command_definitions = mongodb.command_definitions

    async def seed_builtin_commands(self) -> int:
        """Seed or update all built-in command definitions.

        Idempotent: upserts by registryId, so safe to call on every startup.

        Returns:
            Number of commands seeded/updated.
        """
        count = 0
        for definition in BUILTIN_COMMANDS:
            result = await self.command_definitions.update_one(
                {"registryId": definition["registryId"]},
                {"$set": definition},
                upsert=True,
            )
            if result.upserted_id or result.modified_count:
                count += 1

        logger.info(
            "builtin_commands_seeded",
            total=len(BUILTIN_COMMANDS),
            upserted=count,
        )
        return count

    async def get_definition(self, registry_id: str) -> dict[str, Any]:
        """Get a command definition by its registry ID.

        Args:
            registry_id: The registry identifier (e.g. 'reg::service::restart').

        Returns:
            The command definition document.

        Raises:
            CommandRegistryNotFoundError: If the definition does not exist.
        """
        definition = await self.command_definitions.find_one(
            {"registryId": registry_id}
        )
        if not definition:
            raise CommandRegistryNotFoundError(registry_id)
        return definition  # type: ignore[no-any-return]

    async def list_definitions(
        self,
        category: str | None = None,
        include_deprecated: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List command definitions with optional filtering.

        Args:
            category: Filter by command category (service, node, agent).
            include_deprecated: Include deprecated commands.
            limit: Maximum results.
            offset: Pagination offset.

        Returns:
            Tuple of (definitions list, total count).
        """
        query: dict[str, Any] = {}

        if category:
            query["category"] = category
        if not include_deprecated:
            query["metadata.deprecated"] = {"$ne": True}

        total = await self.command_definitions.count_documents(query)

        cursor = self.command_definitions.find(query)
        cursor = cursor.sort("registryId", 1)
        cursor = cursor.skip(offset).limit(limit)

        definitions = await cursor.to_list(length=limit)

        return definitions, total

    async def list_definitions_with_plugins(
        self,
        category: str | None = None,
        include_deprecated: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List command definitions including plugin-contributed commands.

        Combines built-in definitions from the command_definitions collection
        with contributed commands from active plugins.

        Args:
            category: Filter by command category.
            include_deprecated: Include deprecated commands.
            limit: Maximum results.
            offset: Pagination offset.

        Returns:
            Tuple of (combined definitions list, total count).
        """
        # Get built-in definitions
        definitions, builtin_total = await self.list_definitions(
            category=category,
            include_deprecated=include_deprecated,
            limit=limit,
            offset=offset,
        )

        # Query active plugins for contributed commands
        plugins_collection = self.mongodb.db["plugins"]
        plugin_cursor = plugins_collection.find({
            "status": "active",
            "manifest.contributedCommands": {"$exists": True, "$ne": []},
            "uninstalledAt": {"$exists": False},
        })

        plugin_commands: list[dict[str, Any]] = []
        async for plugin in plugin_cursor:
            manifest = plugin.get("manifest", {})
            plugin_id = plugin.get("pluginId", "")
            contributed = manifest.get("contributedCommands", [])

            for registry_id in contributed:
                # Only include if not already in builtin definitions
                if any(d.get("registryId") == registry_id for d in definitions):
                    continue

                # Apply category filter if specified
                if category and not registry_id.startswith(f"reg::{category}::"):
                    continue

                plugin_commands.append({
                    "registryId": registry_id,
                    "source": "plugin",
                    "pluginId": plugin_id,
                    "pluginName": manifest.get("name", ""),
                    "category": registry_id.split("::")[1] if "::" in registry_id else "custom",
                    "action": registry_id.split("::")[-1] if "::" in registry_id else registry_id,
                })

        combined = definitions + plugin_commands
        total = builtin_total + len(plugin_commands)

        return combined, total
