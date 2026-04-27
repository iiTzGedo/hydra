"""System-default entity panel seeder.

Inserts three system-default entity panel boards (node, service, network)
at startup if they are not already present. Idempotent — uses $setOnInsert
so existing documents are never overwritten.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = structlog.get_logger(__name__)

# Reserved IDs for the three system-default entity panels.
PANEL_IDS = {
    "node": "panel-default-node",
    "service": "panel-default-service",
    "network": "panel-default-network",
}


def _default_layout() -> dict[str, Any]:
    """Standard 5-breakpoint grid layout for entity panels."""
    return {
        "mode": "grid",
        "grid": {
            "columns": 12,
            "rowHeight": 80,
            "breakpoints": {
                "xl": {"columns": 12, "width": 1536},
                "lg": {"columns": 12, "width": 1200},
                "md": {"columns": 8, "width": 996},
                "sm": {"columns": 4, "width": 480},
                "xs": {"columns": 2, "width": 0},
            },
            "compaction": "vertical",
            "margin": [16, 16],
            "padding": [0, 0],
        },
    }


def _default_settings() -> dict[str, Any]:
    return {
        "theme": "inherit",
        "autoRefresh": True,
        "refreshInterval": 30,
        "showHeader": True,
        "kioskMode": False,
        "kioskAutoScroll": False,
        "kioskScrollSpeed": 30,
        "backgroundImage": None,
        "customCss": None,
    }


def _parse_query(raw: str) -> dict[str, Any]:
    """Convert a query string like ``"nodeId={{entity.id}}&latest=true"`` into a dict.

    Each ``key=value`` pair becomes a string entry.  Template variables such as
    ``{{entity.id}}`` are preserved verbatim so that the resolver can substitute
    them at runtime.
    """
    result: dict[str, Any] = {}
    for part in raw.split("&"):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            key, _, value = part.partition("=")
            result[key.strip()] = value.strip()
        else:
            result[part] = ""
    return result


def _widget(
    widget_type: str,
    x: int,
    y: int,
    w: int,
    h: int,
    source: str,
    query: str,
    extra_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a fully-specified widget instance for a seeded panel."""
    instance_id = f"wi_{uuid.uuid4().hex[:8]}"
    config: dict[str, Any] = extra_config or {}
    return {
        "instanceId": instance_id,
        "widgetType": widget_type,
        "config": config,
        "dataBinding": {"source": source, "query": _parse_query(query)},
        "position": {"x": x, "y": y, "w": w, "h": h},
        "placements": {
            "xl": {"x": x, "y": y, "w": w, "h": h},
            "lg": {"x": x, "y": y, "w": w, "h": h},
            "md": {"x": x, "y": y, "w": w, "h": h},
            "sm": {"x": 0, "y": y, "w": 4, "h": h},
            "xs": {"x": 0, "y": y, "w": 2, "h": h},
        },
    }


def _node_panel(now: datetime) -> dict[str, Any]:
    """System-default entity panel for node detail pages."""
    return {
        "boardId": PANEL_IDS["node"],
        "name": "Node Panel",
        "description": "Default embedded panel for node detail pages.",
        "icon": "server",
        "ownerId": "__system__",
        "ownerType": "system",
        "boardType": "user",
        "visibility": {"scope": "private", "sharedWith": {"roles": [], "users": []}},
        "layout": _default_layout(),
        "layoutMode": "grid",
        "scope": "entity-panel",
        "entityTypeFilter": "node",
        "isSystemDefault": True,
        "widgets": [
            _widget(
                "hydra::node-summary",
                x=0, y=0, w=12, h=3,
                source="hydra::nodes",
                query="nodeId={{entity.id}}",
            ),
            _widget(
                "hydra::stats-cards",
                x=0, y=3, w=12, h=2,
                source="hydra::profiles",
                query="nodeId={{entity.id}}&latest=true",
                extra_config={"metrics": ["cpu", "mem", "disk"]},
            ),
            _widget(
                "hydra::recent-activity",
                x=0, y=5, w=6, h=4,
                source="hydra::audit",
                query="nodeId={{entity.id}}",
                extra_config={"limit": 10},
            ),
            _widget(
                "hydra::service-list",
                x=6, y=5, w=6, h=4,
                source="hydra::services",
                query="nodeId={{entity.id}}",
            ),
        ],
        "settings": _default_settings(),
        "tags": ["system", "entity-panel", "node"],
        "isHome": False,
        "version": 1,
        "clonedFrom": None,
        "createdAt": now,
        "updatedAt": now,
        "archivedAt": None,
    }


def _service_panel(now: datetime) -> dict[str, Any]:
    """System-default entity panel for service detail pages."""
    return {
        "boardId": PANEL_IDS["service"],
        "name": "Service Panel",
        "description": "Default embedded panel for service detail pages.",
        "icon": "layers",
        "ownerId": "__system__",
        "ownerType": "system",
        "boardType": "user",
        "visibility": {"scope": "private", "sharedWith": {"roles": [], "users": []}},
        "layout": _default_layout(),
        "layoutMode": "grid",
        "scope": "entity-panel",
        "entityTypeFilter": "service",
        "isSystemDefault": True,
        "widgets": [
            _widget(
                "hydra::service-status-bar",
                x=0, y=0, w=12, h=2,
                source="hydra::services",
                query="serviceId={{entity.id}}",
            ),
            _widget(
                "hydra::uptime-bar",
                x=0, y=2, w=12, h=2,
                source="hydra::services",
                query="serviceId={{entity.id}}",
            ),
            _widget(
                "hydra::recent-activity",
                x=0, y=4, w=6, h=4,
                source="hydra::audit",
                query="serviceId={{entity.id}}",
                extra_config={"limit": 10},
            ),
            _widget(
                "hydra::profile-diff",
                x=6, y=4, w=6, h=4,
                source="hydra::profiles",
                query="serviceId={{entity.id}}",
            ),
        ],
        "settings": _default_settings(),
        "tags": ["system", "entity-panel", "service"],
        "isHome": False,
        "version": 1,
        "clonedFrom": None,
        "createdAt": now,
        "updatedAt": now,
        "archivedAt": None,
    }


def _network_panel(now: datetime) -> dict[str, Any]:
    """System-default entity panel for network detail pages."""
    return {
        "boardId": PANEL_IDS["network"],
        "name": "Network Panel",
        "description": "Default embedded panel for network detail pages.",
        "icon": "network",
        "ownerId": "__system__",
        "ownerType": "system",
        "boardType": "user",
        "visibility": {"scope": "private", "sharedWith": {"roles": [], "users": []}},
        "layout": _default_layout(),
        "layoutMode": "grid",
        "scope": "entity-panel",
        "entityTypeFilter": "network",
        "isSystemDefault": True,
        "widgets": [
            _widget(
                "hydra::network-summary",
                x=0, y=0, w=12, h=3,
                source="hydra::networks",
                query="networkId={{entity.id}}",
            ),
            _widget(
                "hydra::node-status-grid",
                x=0, y=3, w=8, h=4,
                source="hydra::nodes",
                query="networkId={{entity.id}}",
            ),
            _widget(
                "hydra::mini-topology",
                x=8, y=3, w=4, h=4,
                source="hydra::topology",
                query="networkId={{entity.id}}",
            ),
        ],
        "settings": _default_settings(),
        "tags": ["system", "entity-panel", "network"],
        "isHome": False,
        "version": 1,
        "clonedFrom": None,
        "createdAt": now,
        "updatedAt": now,
        "archivedAt": None,
    }


async def seed_system_panels(db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
    """Insert the three system-default entity panel boards if not already present.

    Uses $setOnInsert so this is completely idempotent — calling it multiple
    times never overwrites a panel that was previously seeded.

    Args:
        db: Motor database instance (e.g. ``mongodb.db``).
    """
    now = datetime.now(UTC)
    panels = [
        _node_panel(now),
        _service_panel(now),
        _network_panel(now),
    ]

    seeded = 0
    for panel in panels:
        board_id = panel["boardId"]
        result = await db["dashboards"].update_one(
            {"boardId": board_id},
            {"$setOnInsert": panel},
            upsert=True,
        )
        if result.upserted_id is not None:
            seeded += 1
            logger.info("entity_panel_seeded", board_id=board_id)

    if seeded:
        logger.info("entity_panels_seeded", count=seeded)
    else:
        logger.debug("entity_panels_already_present", count=len(panels))
