"""Entity panel service — lookup user override, clone default, delete override.

Each user has at most one personal override per entity type (node, service,
network). When no override exists, the system default is returned.
"""

from __future__ import annotations

import secrets
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, Literal

import structlog
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

logger = structlog.get_logger(__name__)

EntityPanelType = Literal["node", "service", "network"]


class PanelService:
    """Manage entity-panel board lookups and user overrides."""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        self._db = db

    async def get_active_panel(self, entity_type: EntityPanelType, user_id: str) -> dict[str, Any]:
        """Return the user's personal override if one exists, else the system default.

        Raises:
            RuntimeError: If the system default panel has not been seeded.
        """
        override = await self._db["dashboards"].find_one(
            {
                "scope": "entity-panel",
                "entityTypeFilter": entity_type,
                "ownerId": user_id,
                "ownerType": "user",
                "archivedAt": None,
            }
        )
        if override:
            return dict(override)

        default = await self._db["dashboards"].find_one(
            {"boardId": f"panel-default-{entity_type}"}
        )
        if default is None:
            raise RuntimeError(f"System default panel for '{entity_type}' not seeded")
        return dict(default)

    async def customize(self, entity_type: EntityPanelType, user_id: str) -> dict[str, Any]:
        """Clone the system default into a user-owned override.

        Idempotent: if the user already has an override for this entity type,
        the existing override is returned without modification.

        Raises:
            RuntimeError: If the system default panel has not been seeded.
        """
        existing = await self._db["dashboards"].find_one(
            {
                "scope": "entity-panel",
                "entityTypeFilter": entity_type,
                "ownerId": user_id,
                "ownerType": "user",
                "archivedAt": None,
            }
        )
        if existing:
            return dict(existing)

        default = await self._db["dashboards"].find_one(
            {"boardId": f"panel-default-{entity_type}"}
        )
        if default is None:
            raise RuntimeError(f"System default panel for '{entity_type}' not seeded")

        now = datetime.now(UTC)
        override = deepcopy(dict(default))
        override.pop("_id", None)
        override["boardId"] = f"panel-{entity_type}-{user_id}-{secrets.token_hex(4)}"
        override["ownerId"] = user_id
        override["ownerType"] = "user"
        override["isSystemDefault"] = False
        override["name"] = f"My {entity_type.title()} Panel"
        override["createdAt"] = now
        override["updatedAt"] = now
        override["version"] = 1

        try:
            await self._db["dashboards"].insert_one(override)
        except DuplicateKeyError:
            # Two concurrent customize calls raced past the find_one check.
            # The DB rejected our insert (partial unique index enforces one
            # override per user+entity_type). Fetch the winner and return it.
            winner = await self._db["dashboards"].find_one(
                {
                    "scope": "entity-panel",
                    "entityTypeFilter": entity_type,
                    "ownerId": user_id,
                    "ownerType": "user",
                    "archivedAt": None,
                }
            )
            if winner is None:
                raise RuntimeError(
                    "Race condition on entity panel customize: duplicate key but no winner found"
                )
            logger.info(
                "entity_panel_override_race_resolved",
                entity_type=entity_type,
                user_id=user_id,
                board_id=winner["boardId"],
            )
            return dict(winner)

        override.pop("_id", None)

        logger.info(
            "entity_panel_override_created",
            entity_type=entity_type,
            user_id=user_id,
            board_id=override["boardId"],
        )
        return override

    async def delete_override(self, entity_type: EntityPanelType, user_id: str) -> bool:
        """Delete the user's personal override for the given entity type.

        Returns:
            True if an override was found and deleted; False otherwise.
        """
        result = await self._db["dashboards"].delete_one(
            {
                "scope": "entity-panel",
                "entityTypeFilter": entity_type,
                "ownerId": user_id,
                "ownerType": "user",
                "archivedAt": None,
            }
        )
        deleted = result.deleted_count == 1
        if deleted:
            logger.info(
                "entity_panel_override_deleted",
                entity_type=entity_type,
                user_id=user_id,
            )
        return deleted
