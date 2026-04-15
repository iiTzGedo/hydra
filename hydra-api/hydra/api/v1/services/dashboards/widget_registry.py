"""Widget registry for the dashboard framework.

Implements the WidgetRegistry class per Dashboard Technical Specification §4.3.
Supports dynamic registration (for plugin widgets in later waves), role-based
filtering, and spec-aligned widget categories.
"""

from __future__ import annotations

import copy
from threading import Lock
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# ── Spec Categories (§4.2) ──────────────────────────────────────────

# 11 widget categories from the specification. The display names mirror the
# spec section headings.
SPEC_CATEGORIES: dict[str, str] = {
    "data-display": "Data Display",
    "status-health": "Status & Health",
    "tables-lists": "Tables & Lists",
    "charts-graphs": "Charts & Graphs",
    "topology-maps": "Topology & Maps",
    "controls-actions": "Controls & Actions",
    "infrastructure": "Infrastructure",
    "iot-home": "IoT & Home",
    "time-history": "Time & History",
    "external-embed": "External & Embed",
    "system-meta": "System & Meta",
}


# Legacy → spec category mapping. Used only when migrating saved boards or
# accepting category filters from pre-Phase-2 clients.
LEGACY_CATEGORY_ALIASES: dict[str, str] = {
    "status": "status-health",
    "activity": "system-meta",
    "utility": "external-embed",
    "content": "external-embed",
}


# ── Common config schema used by the built-in widgets ──────────────

COMMON_WIDGET_CONFIG_SCHEMA: list[dict[str, object]] = [
    {
        "key": "title",
        "label": "Title",
        "fieldType": "text",
        "description": "Optional display title override for the widget header.",
        "placeholder": "Leave blank to use the default title",
    },
    {
        "key": "subtitle",
        "label": "Subtitle",
        "fieldType": "text",
        "description": "Short supporting text shown under the title.",
        "placeholder": "Optional supporting context",
    },
    {
        "key": "collapsible",
        "label": "Collapsible",
        "fieldType": "boolean",
        "description": "Allow the widget body to be collapsed from the header.",
    },
    {
        "key": "defaultCollapsed",
        "label": "Start collapsed",
        "fieldType": "boolean",
        "description": "Collapse the widget body when the board first loads.",
    },
]


def _widget_definition(
    *,
    widget_type: str,
    display_name: str,
    description: str,
    category: str,
    icon: str,
    default_size: dict[str, int],
    min_size: dict[str, int],
    max_size: dict[str, int],
    source: str = "hydra",
    version: str = "1.0.0",
    supported_data_shapes: list[str] | None = None,
    tags: list[str] | None = None,
    permissions_view: list[str] | None = None,
    permissions_interact: list[str] | None = None,
    config_schema: list[dict[str, object]] | None = None,
    repeatable: bool = False,
) -> dict[str, object]:
    """Build a widget type definition dict.

    All dicts are deep-copied before being returned from the registry so
    callers cannot mutate the canonical in-memory definitions.
    """
    if category not in SPEC_CATEGORIES:
        raise ValueError(f"Unknown widget category '{category}' (widget {widget_type})")

    return {
        "widgetType": widget_type,
        "displayName": display_name,
        "description": description,
        "category": category,
        "icon": icon,
        "source": source,
        "version": version,
        "supportedDataShapes": list(supported_data_shapes or []),
        "tags": list(tags or []),
        "permissions": {
            "view": list(permissions_view or ["admin", "operator", "viewer", "family"]),
            "interact": list(permissions_interact or []),
        },
        "defaultSize": dict(default_size),
        "minSize": dict(min_size),
        "maxSize": dict(max_size),
        "configSchema": copy.deepcopy(config_schema or COMMON_WIDGET_CONFIG_SCHEMA),
        "capabilities": {
            "configurable": True,
            "supportsVisibilityToggle": True,
            "repeatable": repeatable,
        },
    }


# ── Built-in widget definitions ────────────────────────────────────

BUILTIN_WIDGETS: list[dict[str, object]] = [
    _widget_definition(
        widget_type="hydra::stats-cards",
        display_name="Stats Overview",
        description="Key infrastructure metrics at a glance.",
        category="data-display",
        icon="bar-chart-3",
        default_size={"w": 12, "h": 2},
        min_size={"w": 6, "h": 2},
        max_size={"w": 12, "h": 4},
        supported_data_shapes=["array-of-scalars"],
        tags=["overview", "kpi", "metrics"],
    ),
    _widget_definition(
        widget_type="hydra::capacity-overview",
        display_name="Capacity Overview",
        description="Resource utilization and capacity planning for your fleet.",
        category="infrastructure",
        icon="hard-drive",
        default_size={"w": 12, "h": 4},
        min_size={"w": 6, "h": 3},
        max_size={"w": 12, "h": 6},
        supported_data_shapes=["node-group-resources"],
        tags=["capacity", "cpu", "memory", "disk"],
    ),
    _widget_definition(
        widget_type="hydra::service-summary",
        display_name="Service Summary",
        description="Overview of service health and operational status.",
        category="status-health",
        icon="activity",
        default_size={"w": 6, "h": 4},
        min_size={"w": 4, "h": 3},
        max_size={"w": 12, "h": 6},
        supported_data_shapes=["array-of-service-status"],
        tags=["services", "health"],
    ),
    _widget_definition(
        widget_type="hydra::recent-activity",
        display_name="Recent Activity",
        description="Latest infrastructure events and state changes.",
        category="system-meta",
        icon="clock",
        default_size={"w": 6, "h": 4},
        min_size={"w": 4, "h": 3},
        max_size={"w": 12, "h": 6},
        supported_data_shapes=["event-stream"],
        tags=["audit", "activity", "events"],
    ),
    _widget_definition(
        widget_type="hydra::mini-topology",
        display_name="Infrastructure Topology",
        description="Visual map of the current topology snapshot.",
        category="topology-maps",
        icon="network",
        default_size={"w": 12, "h": 4},
        min_size={"w": 6, "h": 3},
        max_size={"w": 12, "h": 8},
        supported_data_shapes=["topology-graph"],
        tags=["topology", "graph", "network"],
    ),
    _widget_definition(
        widget_type="hydra::node-status-grid",
        display_name="Node Status Grid",
        description="Grid view of node health, reachability, and role.",
        category="status-health",
        icon="server",
        default_size={"w": 12, "h": 4},
        min_size={"w": 6, "h": 3},
        max_size={"w": 12, "h": 6},
        supported_data_shapes=["array-of-status"],
        tags=["nodes", "status"],
    ),
    _widget_definition(
        widget_type="hydra::clock",
        display_name="Clock",
        description="Minimal time and timezone display for glanceable boards.",
        category="external-embed",
        icon="clock-3",
        default_size={"w": 3, "h": 2},
        min_size={"w": 2, "h": 2},
        max_size={"w": 4, "h": 3},
        source="hydra",
        tags=["time", "glance"],
        config_schema=COMMON_WIDGET_CONFIG_SCHEMA + [
            {
                "key": "timezone",
                "label": "Timezone",
                "fieldType": "text",
                "description": "IANA timezone identifier, for example Europe/London.",
                "placeholder": "Europe/London",
            }
        ],
        repeatable=True,
    ),
    _widget_definition(
        widget_type="hydra::rss-feed",
        display_name="RSS Feed",
        description="Render headlines from an RSS or Atom feed.",
        category="external-embed",
        icon="rss",
        default_size={"w": 6, "h": 4},
        min_size={"w": 4, "h": 3},
        max_size={"w": 12, "h": 8},
        source="hydra",
        tags=["rss", "feed", "news"],
        config_schema=COMMON_WIDGET_CONFIG_SCHEMA + [
            {
                "key": "feedUrl",
                "label": "Feed URL",
                "fieldType": "text",
                "description": "Public RSS or Atom feed URL.",
                "placeholder": "https://example.com/feed.xml",
            },
            {
                "key": "maxItems",
                "label": "Items",
                "fieldType": "number",
                "description": "Maximum number of entries to show.",
                "minValue": 1,
                "maxValue": 20,
            },
        ],
        repeatable=True,
    ),
    _widget_definition(
        widget_type="hydra::bookmark-grid",
        display_name="Bookmark Grid",
        description="Pinned links for internal tools and external dashboards.",
        category="external-embed",
        icon="bookmark",
        default_size={"w": 6, "h": 4},
        min_size={"w": 4, "h": 3},
        max_size={"w": 12, "h": 8},
        source="hydra",
        tags=["bookmarks", "links"],
        config_schema=COMMON_WIDGET_CONFIG_SCHEMA + [
            {
                "key": "linksMarkdown",
                "label": "Links",
                "fieldType": "text",
                "description": "One link per line in Markdown format: [Label](https://example.com).",
                "placeholder": "[Glance](https://github.com/glanceapp/glance)",
            }
        ],
        repeatable=True,
    ),
    _widget_definition(
        widget_type="hydra::iframe",
        display_name="Embed / Iframe",
        description="Embed a trusted external dashboard or panel.",
        category="external-embed",
        icon="app-window",
        default_size={"w": 12, "h": 6},
        min_size={"w": 6, "h": 4},
        max_size={"w": 12, "h": 12},
        source="hydra",
        tags=["embed", "iframe"],
        config_schema=COMMON_WIDGET_CONFIG_SCHEMA + [
            {
                "key": "src",
                "label": "Source URL",
                "fieldType": "text",
                "description": "Trusted URL to render in an iframe.",
                "placeholder": "https://grafana.example.com/d/overview",
            },
            {
                "key": "allowFullscreen",
                "label": "Allow fullscreen",
                "fieldType": "boolean",
                "description": "Allow the embedded content to request fullscreen mode.",
            },
        ],
        repeatable=True,
    ),
    _widget_definition(
        widget_type="hydra::markdown",
        display_name="Markdown Block",
        description="Freeform manual notes, runbooks, or callouts rendered inline.",
        category="external-embed",
        icon="square-pen",
        default_size={"w": 6, "h": 4},
        min_size={"w": 4, "h": 3},
        max_size={"w": 12, "h": 10},
        source="hydra",
        tags=["markdown", "notes", "runbook"],
        config_schema=COMMON_WIDGET_CONFIG_SCHEMA + [
            {
                "key": "markdown",
                "label": "Markdown",
                "fieldType": "text",
                "description": "Markdown content rendered inside the widget body.",
                "placeholder": "## Notes\\n\\nRemember to rotate backups on Friday.",
            }
        ],
        repeatable=True,
    ),
    _widget_definition(
        widget_type="hydra::weather",
        display_name="Weather",
        description="Provider-backed weather snapshot for a configured location.",
        category="external-embed",
        icon="cloud-sun",
        default_size={"w": 4, "h": 3},
        min_size={"w": 3, "h": 2},
        max_size={"w": 6, "h": 4},
        source="hydra",
        tags=["weather", "glance"],
        config_schema=COMMON_WIDGET_CONFIG_SCHEMA + [
            {
                "key": "location",
                "label": "Location",
                "fieldType": "text",
                "description": "City or provider-specific location query.",
                "placeholder": "London, UK",
            },
            {
                "key": "units",
                "label": "Units",
                "fieldType": "select",
                "description": "Preferred temperature units.",
                "options": [
                    {"label": "Metric", "value": "metric"},
                    {"label": "Imperial", "value": "imperial"},
                ],
            },
        ],
        repeatable=True,
    ),
    # ── Data Display (6 new) ───────────────────────────────────────
    _widget_definition(
        widget_type="hydra::metric-card",
        display_name="Metric Card",
        description="Single KPI with optional trend sparkline.",
        category="data-display",
        icon="hash",
        default_size={"w": 3, "h": 2},
        min_size={"w": 2, "h": 2},
        max_size={"w": 6, "h": 3},
        supported_data_shapes=["scalar", "scalar-with-trend"],
        tags=["metric", "kpi", "number"],
        repeatable=True,
    ),
    _widget_definition(
        widget_type="hydra::gauge",
        display_name="Gauge",
        description="Circular gauge with configurable thresholds.",
        category="data-display",
        icon="target",
        default_size={"w": 3, "h": 3},
        min_size={"w": 2, "h": 2},
        max_size={"w": 6, "h": 6},
        supported_data_shapes=["scalar-with-range"],
        tags=["gauge", "meter"],
        repeatable=True,
    ),
    _widget_definition(
        widget_type="hydra::progress-bar",
        display_name="Progress Bar",
        description="Horizontal bar showing percentage of a value against a maximum.",
        category="data-display",
        icon="align-left",
        default_size={"w": 4, "h": 2},
        min_size={"w": 3, "h": 1},
        max_size={"w": 12, "h": 3},
        supported_data_shapes=["scalar-with-max"],
        tags=["progress", "percentage"],
        repeatable=True,
    ),
    _widget_definition(
        widget_type="hydra::sparkline",
        display_name="Sparkline",
        description="Minimal line chart showing trend direction without axes.",
        category="data-display",
        icon="trending-up",
        default_size={"w": 3, "h": 2},
        min_size={"w": 2, "h": 1},
        max_size={"w": 6, "h": 3},
        supported_data_shapes=["time-series"],
        tags=["sparkline", "trend"],
        repeatable=True,
    ),
    _widget_definition(
        widget_type="hydra::stat-group",
        display_name="Stat Group",
        description="Row or grid of labeled numbers.",
        category="data-display",
        icon="layout-grid",
        default_size={"w": 6, "h": 2},
        min_size={"w": 4, "h": 2},
        max_size={"w": 12, "h": 4},
        supported_data_shapes=["array-of-scalars"],
        tags=["stat", "group", "numbers"],
        repeatable=True,
    ),
    _widget_definition(
        widget_type="hydra::donut-chart",
        display_name="Donut Chart",
        description="Ring chart showing categorical distribution with legend.",
        category="data-display",
        icon="pie-chart",
        default_size={"w": 4, "h": 4},
        min_size={"w": 3, "h": 3},
        max_size={"w": 6, "h": 6},
        supported_data_shapes=["categorical-distribution"],
        tags=["donut", "pie", "distribution"],
        repeatable=True,
    ),
    # ── Status & Health (4 new, node-status-grid already exists) ───
    _widget_definition(
        widget_type="hydra::status-grid",
        display_name="Status Grid",
        description="Grid of colored status indicators for any entity type.",
        category="status-health",
        icon="grid-3x3",
        default_size={"w": 6, "h": 4},
        min_size={"w": 4, "h": 3},
        max_size={"w": 12, "h": 6},
        supported_data_shapes=["array-of-status"],
        tags=["status", "grid"],
        repeatable=True,
    ),
    _widget_definition(
        widget_type="hydra::health-matrix",
        display_name="Health Matrix",
        description="Rows-by-columns health grid for cross-entity comparison.",
        category="status-health",
        icon="table-2",
        default_size={"w": 6, "h": 4},
        min_size={"w": 4, "h": 3},
        max_size={"w": 12, "h": 8},
        supported_data_shapes=["matrix-of-status"],
        tags=["health", "matrix"],
    ),
    _widget_definition(
        widget_type="hydra::node-status-card",
        display_name="Node Status Card",
        description="Single node card with status, class, specs, and last profile age.",
        category="status-health",
        icon="credit-card",
        default_size={"w": 4, "h": 3},
        min_size={"w": 3, "h": 2},
        max_size={"w": 6, "h": 4},
        supported_data_shapes=["single-node"],
        tags=["node", "card", "status"],
        config_schema=COMMON_WIDGET_CONFIG_SCHEMA + [
            {
                "key": "nodeId",
                "label": "Node",
                "fieldType": "entity",
                "entityType": "node",
                "description": "Target node.",
                "placeholder": "Select a node...",
            }
        ],
        repeatable=True,
    ),
    _widget_definition(
        widget_type="hydra::service-status-bar",
        display_name="Service Status Bar",
        description="Horizontal segmented bar colored by service status.",
        category="status-health",
        icon="equal",
        default_size={"w": 6, "h": 2},
        min_size={"w": 4, "h": 2},
        max_size={"w": 12, "h": 3},
        supported_data_shapes=["array-of-service-status"],
        tags=["service", "bar", "status"],
    ),
    _widget_definition(
        widget_type="hydra::uptime-bar",
        display_name="Uptime Bar",
        description="30/90-day uptime segments per entity.",
        category="status-health",
        icon="bar-chart",
        default_size={"w": 6, "h": 2},
        min_size={"w": 4, "h": 2},
        max_size={"w": 12, "h": 3},
        supported_data_shapes=["uptime-history"],
        tags=["uptime", "availability"],
        repeatable=True,
    ),
    # ── Tables & Lists (4 new, recent-activity already exists) ─────
    _widget_definition(
        widget_type="hydra::entity-table",
        display_name="Entity Table",
        description="Configurable sortable table for any entity type.",
        category="tables-lists",
        icon="table",
        default_size={"w": 12, "h": 6},
        min_size={"w": 6, "h": 4},
        max_size={"w": 12, "h": 10},
        supported_data_shapes=["paginated-entity-list"],
        tags=["table", "entities"],
        config_schema=COMMON_WIDGET_CONFIG_SCHEMA + [
            {
                "key": "entityType",
                "label": "Entity Type",
                "fieldType": "select",
                "description": "Which entity type to display.",
                "options": [
                    {"label": "Nodes", "value": "nodes"},
                    {"label": "Services", "value": "services"},
                    {"label": "Networks", "value": "networks"},
                    {"label": "Groups", "value": "groups"},
                ],
            },
            {
                "key": "pageSize",
                "label": "Page Size",
                "fieldType": "number",
                "description": "Rows per page.",
                "minValue": 5,
                "maxValue": 50,
            },
        ],
        repeatable=True,
    ),
    _widget_definition(
        widget_type="hydra::service-list",
        display_name="Service List",
        description="Compact list of services with status badge and runtime icon.",
        category="tables-lists",
        icon="list",
        default_size={"w": 6, "h": 4},
        min_size={"w": 4, "h": 3},
        max_size={"w": 12, "h": 8},
        supported_data_shapes=["service-array"],
        tags=["service", "list"],
    ),
    _widget_definition(
        widget_type="hydra::activity-feed",
        display_name="Activity Feed",
        description="Chronological feed of Hydra events with navigation links.",
        category="tables-lists",
        icon="activity",
        default_size={"w": 6, "h": 4},
        min_size={"w": 4, "h": 3},
        max_size={"w": 12, "h": 8},
        supported_data_shapes=["event-stream"],
        tags=["activity", "feed", "events"],
    ),
    _widget_definition(
        widget_type="hydra::alert-list",
        display_name="Alert List",
        description="Prioritized list of active alerts and warnings.",
        category="tables-lists",
        icon="bell",
        default_size={"w": 6, "h": 4},
        min_size={"w": 4, "h": 3},
        max_size={"w": 12, "h": 8},
        supported_data_shapes=["alert-array"],
        tags=["alerts", "warnings", "notifications"],
    ),
    _widget_definition(
        widget_type="hydra::log-viewer",
        display_name="Log Viewer",
        description="Scrollable log output with level filtering.",
        category="tables-lists",
        icon="file-text",
        default_size={"w": 12, "h": 6},
        min_size={"w": 6, "h": 4},
        max_size={"w": 12, "h": 10},
        supported_data_shapes=["log-lines"],
        tags=["logs", "viewer"],
    ),
    # ── Charts & Graphs (4 new) ───────────────────────────────────
    _widget_definition(
        widget_type="hydra::line-chart",
        display_name="Line Chart",
        description="Multi-line time-series chart with tooltips and zoom.",
        category="charts-graphs",
        icon="trending-up",
        default_size={"w": 6, "h": 4},
        min_size={"w": 4, "h": 3},
        max_size={"w": 12, "h": 8},
        supported_data_shapes=["multi-time-series"],
        tags=["chart", "line", "time-series"],
        repeatable=True,
    ),
    _widget_definition(
        widget_type="hydra::bar-chart",
        display_name="Bar Chart",
        description="Vertical or horizontal bar chart with labels.",
        category="charts-graphs",
        icon="bar-chart-2",
        default_size={"w": 6, "h": 4},
        min_size={"w": 4, "h": 3},
        max_size={"w": 12, "h": 8},
        supported_data_shapes=["categorical-values"],
        tags=["chart", "bar"],
        repeatable=True,
    ),
    _widget_definition(
        widget_type="hydra::area-chart",
        display_name="Area Chart",
        description="Filled area chart with optional stacked mode.",
        category="charts-graphs",
        icon="mountain",
        default_size={"w": 6, "h": 4},
        min_size={"w": 4, "h": 3},
        max_size={"w": 12, "h": 8},
        supported_data_shapes=["time-series"],
        tags=["chart", "area"],
        repeatable=True,
    ),
    _widget_definition(
        widget_type="hydra::heatmap",
        display_name="Heatmap",
        description="Color-coded intensity grid.",
        category="charts-graphs",
        icon="grip",
        default_size={"w": 6, "h": 4},
        min_size={"w": 4, "h": 3},
        max_size={"w": 12, "h": 8},
        supported_data_shapes=["matrix-values"],
        tags=["heatmap", "intensity"],
        repeatable=True,
    ),
    # ── Topology & Maps (1 new, mini-topology already exists) ─────
    _widget_definition(
        widget_type="hydra::network-map",
        display_name="Network Map",
        description="Network segments with attached node icons.",
        category="topology-maps",
        icon="map",
        default_size={"w": 12, "h": 6},
        min_size={"w": 6, "h": 4},
        max_size={"w": 12, "h": 10},
        supported_data_shapes=["network-with-nodes"],
        tags=["network", "map"],
    ),
    # ── Controls & Actions (4 new — Wave 3 for command wiring) ────
    _widget_definition(
        widget_type="hydra::quick-action",
        display_name="Quick Action",
        description="Button triggering a registered command with pre-bound parameters.",
        category="controls-actions",
        icon="zap",
        default_size={"w": 3, "h": 2},
        min_size={"w": 2, "h": 2},
        max_size={"w": 6, "h": 3},
        supported_data_shapes=["command-ref"],
        tags=["action", "command", "button"],
        permissions_view=["admin", "operator"],
        permissions_interact=["admin", "operator"],
        repeatable=True,
    ),
    _widget_definition(
        widget_type="hydra::command-trigger",
        display_name="Command Trigger",
        description="Button that opens a parameter form before executing a command.",
        category="controls-actions",
        icon="terminal",
        default_size={"w": 4, "h": 3},
        min_size={"w": 3, "h": 2},
        max_size={"w": 6, "h": 4},
        supported_data_shapes=["command-ref-with-form"],
        tags=["command", "trigger", "form"],
        permissions_view=["admin", "operator"],
        permissions_interact=["admin", "operator"],
        repeatable=True,
    ),
    _widget_definition(
        widget_type="hydra::service-control",
        display_name="Service Control",
        description="Start/stop/restart buttons for a specific service.",
        category="controls-actions",
        icon="power",
        default_size={"w": 4, "h": 3},
        min_size={"w": 3, "h": 2},
        max_size={"w": 6, "h": 4},
        supported_data_shapes=["service-ref"],
        tags=["service", "control", "start", "stop"],
        permissions_view=["admin", "operator"],
        permissions_interact=["admin", "operator"],
        config_schema=COMMON_WIDGET_CONFIG_SCHEMA + [
            {
                "key": "serviceId",
                "label": "Service",
                "fieldType": "entity",
                "entityType": "service",
                "description": "Target service.",
                "placeholder": "Select a service...",
            }
        ],
        repeatable=True,
    ),
    _widget_definition(
        widget_type="hydra::workflow-trigger",
        display_name="Workflow Trigger",
        description="Button that triggers a saved workflow chain.",
        category="controls-actions",
        icon="git-branch",
        default_size={"w": 3, "h": 2},
        min_size={"w": 2, "h": 2},
        max_size={"w": 6, "h": 3},
        supported_data_shapes=["workflow-ref"],
        tags=["workflow", "trigger"],
        permissions_view=["admin", "operator"],
        permissions_interact=["admin", "operator"],
        repeatable=True,
    ),
    # ── Infrastructure (3 new, capacity-overview already exists) ──
    _widget_definition(
        widget_type="hydra::node-summary",
        display_name="Node Summary",
        description="Multi-section card with node specs, services count, and status.",
        category="infrastructure",
        icon="server",
        default_size={"w": 6, "h": 4},
        min_size={"w": 4, "h": 3},
        max_size={"w": 12, "h": 6},
        supported_data_shapes=["full-node-with-profile"],
        tags=["node", "summary", "profile"],
        config_schema=COMMON_WIDGET_CONFIG_SCHEMA + [
            {
                "key": "nodeId",
                "label": "Node",
                "fieldType": "entity",
                "entityType": "node",
                "description": "Target node.",
                "placeholder": "Select a node...",
            }
        ],
        repeatable=True,
    ),
    _widget_definition(
        widget_type="hydra::capacity-panel",
        display_name="Capacity Panel",
        description="Grouped resource bars across multiple nodes with utilization.",
        category="infrastructure",
        icon="bar-chart-3",
        default_size={"w": 12, "h": 4},
        min_size={"w": 6, "h": 3},
        max_size={"w": 12, "h": 6},
        supported_data_shapes=["node-group-resources"],
        tags=["capacity", "resources"],
    ),
    _widget_definition(
        widget_type="hydra::network-summary",
        display_name="Network Summary",
        description="Network CIDR, gateway, node count, and VLAN info.",
        category="infrastructure",
        icon="wifi",
        default_size={"w": 4, "h": 3},
        min_size={"w": 3, "h": 2},
        max_size={"w": 6, "h": 4},
        supported_data_shapes=["network-with-stats"],
        tags=["network", "summary"],
        config_schema=COMMON_WIDGET_CONFIG_SCHEMA + [
            {
                "key": "networkId",
                "label": "Network",
                "fieldType": "entity",
                "entityType": "network",
                "description": "Target network.",
                "placeholder": "Select a network...",
            }
        ],
        repeatable=True,
    ),
    _widget_definition(
        widget_type="hydra::profile-diff",
        display_name="Profile Diff",
        description="Side-by-side diff of two profile versions for a node.",
        category="infrastructure",
        icon="git-compare",
        default_size={"w": 12, "h": 6},
        min_size={"w": 6, "h": 4},
        max_size={"w": 12, "h": 10},
        supported_data_shapes=["diff-result"],
        tags=["profile", "diff", "compare"],
    ),
    # ── Time & History (3 new) ────────────────────────────────────
    _widget_definition(
        widget_type="hydra::time-machine-scrubber",
        display_name="Time Machine Scrubber",
        description="Horizontal timeline with event markers for temporal navigation.",
        category="time-history",
        icon="rewind",
        default_size={"w": 12, "h": 2},
        min_size={"w": 6, "h": 2},
        max_size={"w": 12, "h": 3},
        supported_data_shapes=["timeline-events"],
        tags=["time-machine", "timeline"],
    ),
    _widget_definition(
        widget_type="hydra::change-log",
        display_name="Change Log",
        description="Chronological list of infrastructure changes.",
        category="time-history",
        icon="history",
        default_size={"w": 6, "h": 4},
        min_size={"w": 4, "h": 3},
        max_size={"w": 12, "h": 8},
        supported_data_shapes=["change-event-stream"],
        tags=["changelog", "history"],
    ),
    _widget_definition(
        widget_type="hydra::profile-timeline",
        display_name="Profile Timeline",
        description="Version history for a node's profiles with diff links.",
        category="time-history",
        icon="git-commit-vertical",
        default_size={"w": 6, "h": 4},
        min_size={"w": 4, "h": 3},
        max_size={"w": 12, "h": 8},
        supported_data_shapes=["profile-version-list"],
        tags=["profile", "timeline", "versions"],
        config_schema=COMMON_WIDGET_CONFIG_SCHEMA + [
            {
                "key": "nodeId",
                "label": "Node",
                "fieldType": "entity",
                "entityType": "node",
                "description": "Target node.",
                "placeholder": "Select a node...",
            }
        ],
    ),
    # ── External & Embed (1 new — iframe/rss/bookmarks/markdown/clock/weather exist) ──
    _widget_definition(
        widget_type="hydra::html-block",
        display_name="HTML Block",
        description="Raw HTML rendering in a sandboxed container.",
        category="external-embed",
        icon="code",
        default_size={"w": 6, "h": 4},
        min_size={"w": 4, "h": 3},
        max_size={"w": 12, "h": 8},
        source="hydra",
        tags=["html", "embed"],
        config_schema=COMMON_WIDGET_CONFIG_SCHEMA + [
            {
                "key": "html",
                "label": "HTML Content",
                "fieldType": "text",
                "description": "Raw HTML rendered in a sandboxed container.",
                "placeholder": "<p>Hello from an HTML block!</p>",
            }
        ],
        repeatable=True,
    ),
    # ── System & Meta (6 new) ─────────────────────────────────────
    _widget_definition(
        widget_type="hydra::integration-health",
        display_name="Integration Health",
        description="Status indicators for each enabled integration plugin.",
        category="system-meta",
        icon="puzzle",
        default_size={"w": 6, "h": 3},
        min_size={"w": 4, "h": 2},
        max_size={"w": 12, "h": 6},
        supported_data_shapes=["integration-status-array"],
        tags=["integrations", "health", "plugins"],
    ),
    _widget_definition(
        widget_type="hydra::agent-grid",
        display_name="Agent Grid",
        description="Grid of all registered agents with tier, version, and last seen.",
        category="system-meta",
        icon="cpu",
        default_size={"w": 12, "h": 4},
        min_size={"w": 6, "h": 3},
        max_size={"w": 12, "h": 6},
        supported_data_shapes=["agent-status-array"],
        tags=["agents", "grid", "status"],
    ),
    _widget_definition(
        widget_type="hydra::audit-stream",
        display_name="Audit Stream",
        description="Live stream of audit log entries with action filtering.",
        category="system-meta",
        icon="scroll-text",
        default_size={"w": 6, "h": 4},
        min_size={"w": 4, "h": 3},
        max_size={"w": 12, "h": 8},
        supported_data_shapes=["audit-log-entries"],
        tags=["audit", "stream", "log"],
    ),
    _widget_definition(
        widget_type="hydra::api-status",
        display_name="API Status",
        description="Health indicators for the Hydra API (DB, Redis, uptime, version).",
        category="system-meta",
        icon="heart-pulse",
        default_size={"w": 4, "h": 3},
        min_size={"w": 3, "h": 2},
        max_size={"w": 6, "h": 4},
        supported_data_shapes=["api-health"],
        tags=["api", "health", "status"],
    ),
    _widget_definition(
        widget_type="hydra::mcp-query",
        display_name="MCP Query",
        description="Text input for natural language queries to the MCP service.",
        category="system-meta",
        icon="message-square",
        default_size={"w": 6, "h": 4},
        min_size={"w": 4, "h": 3},
        max_size={"w": 12, "h": 8},
        tags=["mcp", "query", "ai"],
    ),
    _widget_definition(
        widget_type="hydra::execution-queue",
        display_name="Execution Queue",
        description="Live view of pending, running, and completed command executions.",
        category="system-meta",
        icon="list-ordered",
        default_size={"w": 6, "h": 4},
        min_size={"w": 4, "h": 3},
        max_size={"w": 12, "h": 8},
        supported_data_shapes=["command-queue"],
        tags=["commands", "queue", "execution"],
    ),
]


# ── Registry class ─────────────────────────────────────────────────


class WidgetRegistry:
    """In-memory widget type registry per spec §4.3.

    Supports dynamic registration, role-based filtering, and category lookup.
    Acts as a singleton (see ``widget_registry`` module attribute below) but
    can be instantiated for unit tests.
    """

    def __init__(self) -> None:
        self._definitions: dict[str, dict[str, object]] = {}
        self._lock = Lock()
        self._populate_builtins()

    def _populate_builtins(self) -> None:
        for definition in BUILTIN_WIDGETS:
            widget_type = str(definition["widgetType"])
            self._definitions[widget_type] = copy.deepcopy(definition)

    # ---- Mutation --------------------------------------------------

    def register(self, definition: dict[str, object]) -> None:
        """Register a widget type definition. Overwrites any existing type."""
        widget_type = str(definition.get("widgetType", "")).strip()
        if not widget_type:
            raise ValueError("Widget definition is missing 'widgetType'")

        category = str(definition.get("category", ""))
        if category not in SPEC_CATEGORIES:
            raise ValueError(
                f"Widget '{widget_type}' has unknown category '{category}'. "
                f"Valid categories: {sorted(SPEC_CATEGORIES.keys())}"
            )

        with self._lock:
            self._definitions[widget_type] = copy.deepcopy(definition)
        logger.info("widget_registered", widget_type=widget_type, source=definition.get("source", "unknown"))

    def unregister(self, widget_type: str) -> bool:
        """Remove a widget type. Returns True if it was present."""
        with self._lock:
            removed = self._definitions.pop(widget_type, None) is not None
        if removed:
            logger.info("widget_unregistered", widget_type=widget_type)
        return removed

    def reset_to_builtins(self) -> None:
        """Reset the registry to built-in widgets only (used by tests)."""
        with self._lock:
            self._definitions.clear()
            self._populate_builtins()

    # ---- Query -----------------------------------------------------

    def get(self, widget_type: str) -> dict[str, object] | None:
        """Return a deep copy of the definition or None if not found."""
        with self._lock:
            definition = self._definitions.get(widget_type)
            return copy.deepcopy(definition) if definition is not None else None

    def has(self, widget_type: str) -> bool:
        with self._lock:
            return widget_type in self._definitions

    def list_all(self) -> list[dict[str, object]]:
        """Return deep copies of all registered definitions."""
        with self._lock:
            return [copy.deepcopy(d) for d in self._definitions.values()]

    def list_for_role(self, role: str | None) -> list[dict[str, object]]:
        """Return definitions visible to the given role.

        If ``role`` is None or the admin role, all widgets are returned.
        Otherwise only widgets whose ``permissions.view`` list includes the
        role are returned.
        """
        all_widgets = self.list_all()
        if role is None:
            return all_widgets
        normalized = role.strip().lower()
        if normalized in {"admin", "*"}:
            return all_widgets
        filtered: list[dict[str, object]] = []
        for widget in all_widgets:
            permissions = widget.get("permissions", {})
            view_roles = permissions.get("view", []) if isinstance(permissions, dict) else []
            if isinstance(view_roles, list) and normalized in {str(r).lower() for r in view_roles}:
                filtered.append(widget)
        return filtered

    def list_for_category(self, category: str) -> list[dict[str, object]]:
        """Return definitions in a given category (accepts legacy alias)."""
        resolved = LEGACY_CATEGORY_ALIASES.get(category, category)
        return [widget for widget in self.list_all() if widget.get("category") == resolved]

    def categories_for_role(self, role: str | None = None) -> list[dict[str, Any]]:
        """Return ``(id, name, count)`` tuples for all spec categories.

        The count reflects the number of widgets in each category that are
        visible to ``role``. Categories with zero visible widgets are still
        included so the picker can render the full taxonomy (with disabled
        entries) in later waves.
        """
        visible = self.list_for_role(role)
        counts: dict[str, int] = dict.fromkeys(SPEC_CATEGORIES, 0)
        for widget in visible:
            cat = str(widget.get("category", ""))
            if cat in counts:
                counts[cat] += 1
        return [
            {"id": cat_id, "name": name, "count": counts.get(cat_id, 0)}
            for cat_id, name in SPEC_CATEGORIES.items()
        ]

    def validate_widget_types(
        self,
        widget_types: list[str],
        *,
        existing_widget_types: list[str] | None = None,
    ) -> tuple[list[str], list[str]]:
        """Validate requested widget types against the registry.

        Returns ``(unknown_types, repeatable_violations)`` rather than raising
        so callers can assemble richer error payloads.

        - ``unknown_types``: types absent from the registry that also exceed
          the count present in ``existing_widget_types`` (so boards with
          legacy saved widgets can keep rendering).
        - ``repeatable_violations``: non-repeatable types appearing more than
          once in ``widget_types`` beyond what already existed.
        """
        existing_counts: dict[str, int] = {}
        for widget_type in existing_widget_types or []:
            existing_counts[widget_type] = existing_counts.get(widget_type, 0) + 1

        requested_counts: dict[str, int] = {}
        for widget_type in widget_types:
            requested_counts[widget_type] = requested_counts.get(widget_type, 0) + 1

        unknown: list[str] = []
        repeatable_violations: list[str] = []

        for widget_type, requested_count in requested_counts.items():
            definition = self.get(widget_type)
            existing_count = existing_counts.get(widget_type, 0)

            if definition is None:
                if requested_count > existing_count:
                    unknown.append(widget_type)
                continue

            capabilities = definition.get("capabilities", {})
            repeatable = True
            if isinstance(capabilities, dict):
                repeatable = bool(capabilities.get("repeatable", True))

            if not repeatable and requested_count > 1 and requested_count > existing_count:
                repeatable_violations.append(widget_type)

        return unknown, repeatable_violations


# ── Module-level singleton ─────────────────────────────────────────

widget_registry = WidgetRegistry()


__all__ = [
    "BUILTIN_WIDGETS",
    "COMMON_WIDGET_CONFIG_SCHEMA",
    "LEGACY_CATEGORY_ALIASES",
    "SPEC_CATEGORIES",
    "WidgetRegistry",
    "widget_registry",
]
