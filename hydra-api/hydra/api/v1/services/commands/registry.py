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
