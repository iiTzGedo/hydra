"""Idempotent startup migrations for MongoDB collections.

The API's response models are the source of truth for valid enum values.
Because MongoDB doesn't enforce schema, every time we tighten an enum
or rename a value, older documents can stick around with the old
string. The next time a list endpoint tries to materialize them
through Pydantic, the whole request 500s.

The functions in this module run once per startup (from the FastAPI
lifespan handler) and rewrite known-deprecated values to their current
equivalents. Everything is:

- **Idempotent**: rewrites use ``$nin`` filters so a second run is a no-op.
- **Non-destructive**: we only map values to a closest valid replacement
  inside the same enum; we never delete a row.
- **Logged**: the modified count for every collection × field is emitted
  at INFO so operators can watch the heal happen.

Adding a new mapping
--------------------

Append a :class:`FieldMigration` entry to :data:`KNOWN_MIGRATIONS` with
the collection, dotted field path, the current enum class (used to derive
the set of valid values), and a ``mappings`` dict from
deprecated-string → current-enum-value.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import structlog

from hydra.api.v1.models.networks import NetworkType
from hydra.api.v1.models.nodes import (
    NodeClass,
    NodeKind,
    NodeStatus,
    NodeType,
)

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class FieldMigration:
    """One enum-drift heal target.

    ``field`` is a dotted Mongo path (``"identity.primaryMac"``,
    ``"scanConfig.status"``, etc.). ``enum_cls`` is the StrEnum that
    defines the currently valid values; the migration rewrites any row
    whose field is **not** in that set, **and** whose value is in the
    ``mappings`` dict, to the mapped replacement.
    """

    collection: str
    field: str
    enum_cls: type[StrEnum]
    mappings: dict[str, str]
    description: str = ""


# ── Known historical drifts ──────────────────────────────────────────
#
# Each entry came from a real production-or-development incident where
# a row stored a string the current model rejects. New entries should
# include a one-line note about *why* the mapping is correct.

KNOWN_MIGRATIONS: tuple[FieldMigration, ...] = (
    # Pre-Wave-3 host introspection wrote "lan" for the type field. The
    # canonical mapping for a host's directly attached LAN segment is
    # the physical interface that owns it.
    FieldMigration(
        collection="networks",
        field="type",
        enum_cls=NetworkType,
        mappings={
            "lan": "physical",
            "wan": "physical",
            "dmz": "physical",
        },
        description="Legacy free-text network type strings → enum-aligned",
    ),
    # Proxmox/Promox-style imports historically tagged compute hosts as
    # "hypervisor" instead of using class+type+kind. Map to a physical
    # bare-metal compute node which is what such hosts actually are.
    FieldMigration(
        collection="nodes",
        field="type",
        enum_cls=NodeType,
        mappings={
            "hypervisor": "physical",
        },
        description="Hypervisor type → physical (compute host)",
    ),
    FieldMigration(
        collection="nodes",
        field="kind",
        enum_cls=NodeKind,
        mappings={
            "hypervisor": "bare-metal",
            "baremetal": "bare-metal",
            "container": "docker",
            "k8s-pod": "kubernetes-pod",
            "ap": "access-point",
            "lb": "load-balancer",
            "sbc": "bare-metal",  # Single-board computers report as bare-metal
        },
        description="Legacy node kinds → current enum values",
    ),
    # Some early imports used "server" / "workstation" which we never
    # had as canonical values; both are physical compute.
    FieldMigration(
        collection="nodes",
        field="class",
        enum_cls=NodeClass,
        mappings={
            "server": "compute",
            "workstation": "compute",
            "network": "networking",
        },
        description="Legacy node classes → canonical compute/networking/iot",
    ),
    FieldMigration(
        collection="nodes",
        field="status",
        enum_cls=NodeStatus,
        mappings={
            "online": "active",
            "offline": "inactive",
            "deleted": "archived",
        },
        description="Legacy status verbs → lifecycle states",
    ),
)


async def _apply_migration(db: Any, migration: FieldMigration) -> int:
    """Apply a single migration and return the modified document count.

    Builds an ``$or`` query: rewrite when the value is in our explicit
    mapping table OR not in the current enum AND in our mapping table.
    The mapping table is the only thing we ever rewrite — we never blind-
    coerce unknown values, since that would silently mask new drift.
    """
    if not migration.mappings:
        return 0

    valid_values = {v.value for v in migration.enum_cls}
    bulk = []
    for old_value, new_value in migration.mappings.items():
        if old_value in valid_values:
            # Defensive: if a "legacy" value somehow re-entered the enum,
            # don't rewrite it. Mapping is a no-op.
            continue
        bulk.append(
            {
                "filter": {migration.field: old_value},
                "update": {"$set": {migration.field: new_value}},
            }
        )

    total_modified = 0
    for op in bulk:
        try:
            result = await db[migration.collection].update_many(
                op["filter"],
                op["update"],
            )
            modified = int(result.modified_count)
        except Exception as exc:  # noqa: BLE001 — startup must not fail
            logger.warning(
                "migrations.apply_failed",
                collection=migration.collection,
                field=migration.field,
                filter=op["filter"],
                error=str(exc),
            )
            continue

        if modified:
            logger.info(
                "migrations.applied",
                collection=migration.collection,
                field=migration.field,
                from_value=op["filter"][migration.field],
                to_value=op["update"]["$set"][migration.field],
                modified=modified,
            )
        total_modified += modified

    return total_modified


async def heal_enum_drift(db: Any) -> dict[str, int]:
    """Run every migration in :data:`KNOWN_MIGRATIONS` against the database.

    Safe to call from the FastAPI lifespan handler. All exceptions are
    swallowed and logged so a misbehaving collection cannot block API
    startup. Returns a dict of ``{"collection.field": modified_count}``
    for telemetry / test assertion.
    """
    summary: dict[str, int] = {}
    for migration in KNOWN_MIGRATIONS:
        key = f"{migration.collection}.{migration.field}"
        try:
            summary[key] = await _apply_migration(db, migration)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "migrations.unexpected_error",
                collection=migration.collection,
                field=migration.field,
                error=str(exc),
            )
            summary[key] = 0
    total = sum(summary.values())
    if total:
        logger.info("migrations.summary", total_modified=total, breakdown=summary)
    else:
        logger.debug("migrations.summary", total_modified=0)
    return summary
