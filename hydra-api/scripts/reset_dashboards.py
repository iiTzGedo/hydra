"""Reset the dashboards collections for Phase 2 Wave 1 migration.

Per the P2DASH plan (see `.claude/plans/indexed-waddling-willow.md`), the
Phase 2 wave 1 refactor changes the board model shape (boardType enum,
structured visibility, ownerType, new settings fields). The pre-live
development guidance says no backward-compatibility shims — so this script
drops the affected collections, re-creates the new indexes, and re-seeds the
built-in templates.

Usage (from the hydra-api project root):

    uv run python scripts/reset_dashboards.py
    uv run python scripts/reset_dashboards.py --yes   # skip interactive prompt
    uv run python scripts/reset_dashboards.py --yes --keep-templates

Safe to re-run: the script only touches the three dashboard collections.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import structlog

from hydra.api.v1.services.dashboards import DashboardService
from hydra.db.indexes import INDEXES, ensure_indexes
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)

TARGET_COLLECTIONS = ("dashboards", "dashboard_templates", "dashboard_versions")


async def _reset(skip_confirm: bool, keep_templates: bool) -> int:
    mongodb = MongoDB()
    await mongodb.connect()

    db = mongodb.db
    logger.info("reset_dashboards_started", keep_templates=keep_templates)

    if not skip_confirm:
        confirm = input(
            f"This will drop {', '.join(TARGET_COLLECTIONS)} in "
            f"'{mongodb.settings.mongodb_database}'. Type 'yes' to continue: "
        )
        if confirm.strip().lower() != "yes":
            print("Aborted.")
            return 1

    collections_to_drop = list(TARGET_COLLECTIONS)
    if keep_templates:
        collections_to_drop.remove("dashboard_templates")

    existing = set(await db.list_collection_names())
    for name in collections_to_drop:
        if name in existing:
            await db[name].drop()
            logger.info("collection_dropped", collection=name)
        else:
            logger.info("collection_missing", collection=name)

    # Recreate indexes for the affected collections.
    for name in TARGET_COLLECTIONS:
        if name in INDEXES:
            await db[name].create_indexes(INDEXES[name])
            logger.info("indexes_created", collection=name, count=len(INDEXES[name]))

    # Ensure the full index set is consistent.
    await ensure_indexes(db)

    # Re-seed built-in templates unless the caller explicitly kept them.
    if not keep_templates:
        service = DashboardService(mongodb)
        seeded = await service.seed_builtin_templates()
        logger.info("builtin_templates_seeded", count=seeded)

    await mongodb.close()
    logger.info("reset_dashboards_complete")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset Hydra dashboard collections.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the interactive confirmation prompt.",
    )
    parser.add_argument(
        "--keep-templates",
        action="store_true",
        help="Do not drop or re-seed the dashboard_templates collection.",
    )
    args = parser.parse_args()

    return asyncio.run(_reset(skip_confirm=args.yes, keep_templates=args.keep_templates))


if __name__ == "__main__":
    sys.exit(main())
