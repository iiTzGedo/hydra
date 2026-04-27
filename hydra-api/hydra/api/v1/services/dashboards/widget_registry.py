"""Widget registry for the dashboard framework.

Implements the WidgetRegistry class per Dashboard Technical Specification §4.3.
Supports dynamic registration (for plugin widgets in later waves), role-based
filtering, and spec-aligned widget categories.
"""

from __future__ import annotations

import copy
from threading import Lock
from typing import Any, Literal

import structlog
from pydantic import BaseModel, ConfigDict, Field

logger = structlog.get_logger(__name__)


# ── FieldSchema — typed configurator descriptor ─────────────────────

FieldType = Literal["string", "number", "boolean", "enum", "color", "entity-ref"]
KioskMode = Literal["render", "readonly", "hide"]
EntityRefType = Literal["node", "service", "network", "group"]


class FieldSchema(BaseModel):
    """Declares a single configurable field on a widget type.

    Drives the WidgetConfiguratorPopover form per spec §5.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    key: str = Field(description="Config dict key (snake_case or camelCase, matching widget expectations)")
    label: str = Field(description="Human-readable field label shown in the configurator")
    type: FieldType = Field(description="Field input type")
    default: Any = Field(default=None, description="Default value applied when user has not configured this field")
    description: str | None = Field(default=None, description="Tooltip or help text")
    options: list[dict[str, str]] | None = Field(
        default=None,
        description="Selectable options for enum fields — each entry has 'value' and 'label'",
    )
    min: float | None = Field(default=None, description="Minimum numeric value (for type=number)")
    max: float | None = Field(default=None, description="Maximum numeric value (for type=number)")
    step: float | None = Field(default=None, description="Step increment for type=number")
    entity_type: EntityRefType | None = Field(
        default=None,
        alias="entityType",
        description="Entity type for entity-ref fields",
    )
    required: bool = Field(default=False, description="Whether this field must be set before saving")


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
# These are FieldSchema instances — the common header/meta fields that every
# widget supports (title override, collapsible state, etc.).

COMMON_FIELD_SCHEMAS: list[FieldSchema] = [
    FieldSchema(key="title", label="Title", type="string", default="",
                description="Optional display title override for the widget header."),
    FieldSchema(key="subtitle", label="Subtitle", type="string", default="",
                description="Short supporting text shown beneath the title."),
    FieldSchema(key="collapsible", label="Collapsible", type="boolean", default=False,
                description="Allow the widget body to be collapsed from the header."),
    FieldSchema(key="defaultCollapsed", label="Start Collapsed", type="boolean", default=False,
                description="Collapse the widget body when the board first loads."),
]


def _fs(**kwargs: Any) -> FieldSchema:
    """Shorthand constructor for FieldSchema to keep widget definitions terse."""
    return FieldSchema(**kwargs)


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
    config_schema: list[FieldSchema] | None = None,
    kiosk_mode: KioskMode = "render",
    is_available: bool = True,
    repeatable: bool = False,
) -> dict[str, object]:
    """Build a widget type definition dict.

    All dicts are deep-copied before being returned from the registry so
    callers cannot mutate the canonical in-memory definitions.

    Args:
        config_schema: Widget-specific FieldSchema list. The common header/meta
            fields are always prepended unless an empty list ``[]`` is passed
            explicitly for Tier 3 gated widgets.
        kiosk_mode: How the widget behaves in kiosk view. Control widgets default
            to ``"readonly"``; display widgets default to ``"render"``.
        is_available: Set to ``False`` for Tier 3 widgets that depend on Wave 5
            features (WebSocket, plugin system). Gated widgets are hidden from
            the widget picker when ``availableOnly=true`` is requested.
    """
    if category not in SPEC_CATEGORIES:
        raise ValueError(f"Unknown widget category '{category}' (widget {widget_type})")

    # Build the final schema: common fields first, then widget-specific fields.
    # Tier 3 widgets use _tier3_definition() which hardcodes configSchema=[] directly.
    if config_schema is None:
        # Default: common header fields only
        final_schema: list[FieldSchema] = list(COMMON_FIELD_SCHEMAS)
    else:
        final_schema = list(COMMON_FIELD_SCHEMAS) + list(config_schema)

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
        # Serialize FieldSchema instances to dicts for the registry store.
        # The Pydantic model in models/dashboards.py deserializes them back.
        "configSchema": [f.model_dump(by_alias=True, exclude_none=True) for f in final_schema],
        "kioskMode": kiosk_mode,
        "isAvailable": is_available,
        "capabilities": {
            "configurable": True,
            "supportsVisibilityToggle": True,
            "repeatable": repeatable,
        },
    }


def _tier3_definition(
    *,
    widget_type: str,
    display_name: str,
    description: str,
    category: str,
    icon: str,
    default_size: dict[str, int],
    min_size: dict[str, int],
    max_size: dict[str, int],
    supported_data_shapes: list[str] | None = None,
    tags: list[str] | None = None,
) -> dict[str, object]:
    """Build a Tier 3 widget definition (isAvailable=False, empty configSchema).

    Tier 3 widgets require Wave 5 features (WebSocket, plugin system) and are
    hidden from the picker until those features land. Their registry entries
    remain so that future enablement is a single flag flip.
    """
    return {
        "widgetType": widget_type,
        "displayName": display_name,
        "description": description,
        "category": category,
        "icon": icon,
        "source": "hydra",
        "version": "1.0.0",
        "supportedDataShapes": list(supported_data_shapes or []),
        "tags": list(tags or []),
        "permissions": {
            "view": ["admin", "operator", "viewer", "family"],
            "interact": [],
        },
        "defaultSize": dict(default_size),
        "minSize": dict(min_size),
        "maxSize": dict(max_size),
        "configSchema": [],  # Gated — no configuration exposed until Wave 5
        "kioskMode": "render",
        "isAvailable": False,
        "capabilities": {
            "configurable": False,
            "supportsVisibilityToggle": True,
            "repeatable": False,
        },
    }


# ── Built-in widget definitions ────────────────────────────────────

BUILTIN_WIDGETS: list[dict[str, object]] = [
    # ── Tier 1 — Data Display ────────────────────────────────────────
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
        config_schema=[
            _fs(key="metrics", label="Metrics", type="string", default="",
                description="Comma-separated metric keys to display (leave blank for all defaults)."),
            _fs(key="columns", label="Columns", type="number", default=4, min=2, max=4, step=1,
                description="Number of stat cards per row."),
        ],
        kiosk_mode="render",
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
        config_schema=[
            _fs(key="showProjections", label="Show Projections", type="boolean", default=False,
                description="Display projected capacity usage trend lines."),
            _fs(key="range", label="Time Range", type="enum", default="7d",
                options=[
                    {"value": "1d", "label": "Last 24 hours"},
                    {"value": "7d", "label": "Last 7 days"},
                    {"value": "30d", "label": "Last 30 days"},
                ],
                description="Historical range for capacity trend calculations."),
        ],
        kiosk_mode="render",
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
        config_schema=[
            _fs(key="groupBy", label="Group By", type="enum", default="runtime",
                options=[
                    {"value": "runtime", "label": "Runtime"},
                    {"value": "status", "label": "Status"},
                    {"value": "node", "label": "Node"},
                ],
                description="How to group services in the summary view."),
            _fs(key="showCounts", label="Show Counts", type="boolean", default=True,
                description="Display numeric counts per group."),
        ],
        kiosk_mode="render",
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
        config_schema=[
            _fs(key="limit", label="Item Limit", type="number", default=20, min=5, max=50, step=5,
                description="Maximum number of recent activity entries to show."),
            _fs(key="showDetails", label="Show Details", type="boolean", default=True,
                description="Expand event details inline rather than requiring a click."),
        ],
        kiosk_mode="render",
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
        config_schema=[
            _fs(key="layout", label="Layout Algorithm", type="enum", default="force",
                options=[
                    {"value": "force", "label": "Force-directed"},
                    {"value": "grid", "label": "Grid"},
                    {"value": "hierarchical", "label": "Hierarchical"},
                ],
                description="Graph layout algorithm for positioning nodes."),
            _fs(key="showLabels", label="Show Labels", type="boolean", default=True,
                description="Display node labels beneath each icon."),
            _fs(key="showInactive", label="Show Inactive Nodes", type="boolean", default=False,
                description="Include archived or offline nodes in the topology view."),
        ],
        kiosk_mode="render",
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
        config_schema=[
            _fs(key="columns", label="Columns", type="number", default=6, min=3, max=8, step=1,
                description="Number of node cards per row."),
            _fs(key="showDetailsOnHover", label="Show Details on Hover", type="boolean", default=True,
                description="Show a tooltip with node details when hovering a card."),
        ],
        kiosk_mode="render",
    ),
    # ── Tier 1 — External & Embed ─────────────────────────────────────
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
        config_schema=[
            _fs(key="format", label="Time Format", type="enum", default="24h",
                options=[
                    {"value": "12h", "label": "12-hour (AM/PM)"},
                    {"value": "24h", "label": "24-hour"},
                ],
                description="Clock display format."),
            _fs(key="timezone", label="Timezone", type="string", default="",
                description="IANA timezone identifier (e.g. Europe/London). Leave blank for browser local time."),
            _fs(key="showDate", label="Show Date", type="boolean", default=True,
                description="Display the current date below the time."),
        ],
        kiosk_mode="render",
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
        config_schema=[
            _fs(key="feedUrl", label="Feed URL", type="string", required=True,
                description="Public RSS or Atom feed URL."),
            _fs(key="itemLimit", label="Item Limit", type="number", default=10, min=5, max=50, step=5,
                description="Maximum number of headlines to display."),
            _fs(key="refreshMinutes", label="Refresh Interval (min)", type="number", default=30,
                min=5, max=240, step=5,
                description="How often to re-fetch the feed, in minutes."),
        ],
        kiosk_mode="render",
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
        config_schema=[
            _fs(key="bookmarks", label="Bookmarks (JSON)", type="string", default="[]",
                description='JSON array of bookmark objects: [{"url":"...","label":"...","icon":"..."}]'),
            _fs(key="columns", label="Columns", type="number", default=4, min=2, max=6, step=1,
                description="Number of bookmark tiles per row."),
            _fs(key="showFavicons", label="Show Favicons", type="boolean", default=True,
                description="Attempt to load the site favicon next to each bookmark label."),
            _fs(key="openInNewTab", label="Open in New Tab", type="boolean", default=True,
                description="Open bookmark links in a new browser tab."),
        ],
        kiosk_mode="render",
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
        config_schema=[
            _fs(key="url", label="Source URL", type="string", required=True,
                description="Trusted URL to render in an iframe (must allow framing)."),
            _fs(key="allowFullscreen", label="Allow Fullscreen", type="boolean", default=False,
                description="Allow the embedded content to request fullscreen mode."),
            _fs(key="scrollable", label="Scrollable", type="boolean", default=True,
                description="Enable scrolling inside the iframe."),
        ],
        kiosk_mode="render",
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
        config_schema=[
            _fs(key="content", label="Markdown Content", type="string", default="",
                description="Markdown-formatted text to render inside the widget body."),
            _fs(key="theme", label="Theme", type="enum", default="default",
                options=[
                    {"value": "default", "label": "Default"},
                    {"value": "muted", "label": "Muted (less contrast)"},
                    {"value": "callout-info", "label": "Callout — Info"},
                    {"value": "callout-warning", "label": "Callout — Warning"},
                    {"value": "callout-success", "label": "Callout — Success"},
                    {"value": "callout-danger", "label": "Callout — Danger"},
                ],
                description="Visual treatment of the markdown block."),
        ],
        kiosk_mode="render",
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
        config_schema=[
            _fs(key="location", label="Location", type="string", required=True,
                description="City or provider-specific location query (e.g. 'London, UK')."),
            _fs(key="units", label="Units", type="enum", default="metric",
                options=[
                    {"value": "metric", "label": "Metric (°C)"},
                    {"value": "imperial", "label": "Imperial (°F)"},
                ],
                description="Preferred temperature unit system."),
            _fs(key="showForecast", label="Show Forecast", type="boolean", default=False,
                description="Display a multi-day forecast strip below the current conditions."),
        ],
        kiosk_mode="render",
        repeatable=True,
    ),
    # ── Tier 1 — Data Display (6 additional) ────────────────────────
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
        config_schema=[
            _fs(key="colorMode", label="Color Mode", type="enum", default="auto",
                options=[
                    {"value": "auto", "label": "Auto (threshold-based)"},
                    {"value": "success", "label": "Success (green)"},
                    {"value": "warning", "label": "Warning (amber)"},
                    {"value": "error", "label": "Error (red)"},
                    {"value": "neutral", "label": "Neutral (gray)"},
                ],
                description="Color applied to the metric value."),
            _fs(key="showTrend", label="Show Trend", type="boolean", default=True,
                description="Display an up/down trend indicator next to the value."),
            _fs(key="showSparkline", label="Show Sparkline", type="boolean", default=False,
                description="Render a mini sparkline chart below the metric value."),
            _fs(key="decimals", label="Decimal Places", type="number", default=0, min=0, max=6, step=1,
                description="Number of decimal places to show on the metric value."),
        ],
        kiosk_mode="render",
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
        config_schema=[
            _fs(key="scaleMin", label="Scale Min", type="number", default=0,
                description="Minimum scale value for the gauge."),
            _fs(key="scaleMax", label="Scale Max", type="number", default=100,
                description="Maximum scale value for the gauge."),
            _fs(key="thresholds", label="Thresholds", type="string", default="70,90",
                description="Comma-separated threshold values (e.g. '70,90'). First = warning, second = critical."),
            _fs(key="dialStyle", label="Dial Style", type="enum", default="arc",
                options=[
                    {"value": "arc", "label": "Arc (270°)"},
                    {"value": "semicircle", "label": "Semicircle (180°)"},
                    {"value": "full", "label": "Full circle"},
                ],
                description="Visual shape of the gauge dial."),
        ],
        kiosk_mode="render",
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
        config_schema=[
            _fs(key="colorMode", label="Color Mode", type="enum", default="auto",
                options=[
                    {"value": "auto", "label": "Auto (threshold-based)"},
                    {"value": "success", "label": "Success (green)"},
                    {"value": "warning", "label": "Warning (amber)"},
                    {"value": "error", "label": "Error (red)"},
                    {"value": "neutral", "label": "Neutral (gray)"},
                ],
                description="Color applied to the progress fill."),
            _fs(key="showPercent", label="Show Percentage", type="boolean", default=True,
                description="Display the percentage value inside or beside the bar."),
            _fs(key="label", label="Label", type="string", default="",
                description="Optional text label displayed above the bar."),
        ],
        kiosk_mode="render",
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
        config_schema=[
            _fs(key="strokeColor", label="Stroke Color", type="color", default="",
                description="Line color (leave blank to inherit theme accent color)."),
            _fs(key="fillColor", label="Fill Color", type="color", default="",
                description="Area fill color beneath the line (leave blank for no fill)."),
            _fs(key="smoothing", label="Smooth Curve", type="boolean", default=True,
                description="Apply Bezier curve smoothing to the sparkline."),
        ],
        kiosk_mode="render",
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
        config_schema=[
            _fs(key="layout", label="Layout", type="enum", default="horizontal",
                options=[
                    {"value": "horizontal", "label": "Horizontal (row)"},
                    {"value": "vertical", "label": "Vertical (column)"},
                    {"value": "grid", "label": "Grid (wrap)"},
                ],
                description="Arrangement of stat items."),
            _fs(key="showLabels", label="Show Labels", type="boolean", default=True,
                description="Display the metric label beneath each number."),
        ],
        kiosk_mode="render",
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
        config_schema=[
            _fs(key="showLegend", label="Show Legend", type="boolean", default=True,
                description="Display a color legend beside the donut."),
            _fs(key="showValues", label="Show Values", type="boolean", default=False,
                description="Print numeric values on each donut segment."),
            _fs(key="innerRadius", label="Inner Radius (%)", type="number", default=60,
                min=0, max=90, step=5,
                description="Percentage of the chart radius that is hollow (0 = pie chart)."),
        ],
        kiosk_mode="render",
        repeatable=True,
    ),
    # ── Tier 1 — Status & Health (4) ─────────────────────────────────
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
        config_schema=[
            _fs(key="columns", label="Columns", type="number", default=4, min=2, max=6, step=1,
                description="Number of status tiles per row."),
            _fs(key="showLabels", label="Show Labels", type="boolean", default=True,
                description="Display the entity name below each status indicator."),
        ],
        kiosk_mode="render",
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
        config_schema=[
            _fs(key="axisOrder", label="Axis Order", type="enum", default="byStatus",
                options=[
                    {"value": "byStatus", "label": "Sort by status severity"},
                    {"value": "byType", "label": "Sort by entity type"},
                ],
                description="How to order the matrix axes."),
            _fs(key="showLegend", label="Show Legend", type="boolean", default=True,
                description="Display status color legend below the matrix."),
        ],
        kiosk_mode="render",
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
        config_schema=[
            _fs(key="nodeId", label="Node", type="entity-ref", entity_type="node", required=True,
                description="Target node to display status for."),
            _fs(key="showTags", label="Show Tags", type="boolean", default=True,
                description="Display the node's tag list on the card."),
        ],
        kiosk_mode="render",
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
        config_schema=[
            _fs(key="showName", label="Show Service Name", type="boolean", default=True,
                description="Display the service name inside each bar segment."),
            _fs(key="compactMode", label="Compact Mode", type="boolean", default=False,
                description="Reduce bar height for denser display."),
        ],
        kiosk_mode="render",
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
        config_schema=[
            _fs(key="barCount", label="Bar Count", type="number", default=90, min=30, max=180, step=30,
                description="Number of daily segments to render (30, 60, 90, etc.)."),
            _fs(key="colorScheme", label="Color Scheme", type="enum", default="traffic-light",
                options=[
                    {"value": "traffic-light", "label": "Traffic light (green/amber/red)"},
                    {"value": "blue-scale", "label": "Blue scale"},
                    {"value": "monochrome", "label": "Monochrome"},
                ],
                description="Color scheme used to encode uptime percentage."),
        ],
        kiosk_mode="render",
        repeatable=True,
    ),
    # ── Tier 2 — Tables & Lists ───────────────────────────────────────
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
        config_schema=[
            _fs(key="entityType", label="Entity Type", type="enum", default="nodes",
                options=[
                    {"value": "nodes", "label": "Nodes"},
                    {"value": "services", "label": "Services"},
                    {"value": "networks", "label": "Networks"},
                    {"value": "groups", "label": "Groups"},
                ],
                description="Which entity type to display in the table."),
            _fs(key="pageSize", label="Page Size", type="number", default=20, min=5, max=50, step=5,
                description="Number of rows to display per page."),
            _fs(key="sortBy", label="Sort Field", type="string", default="",
                description="Field name to sort by (leave blank for default sort)."),
            _fs(key="sortDir", label="Sort Direction", type="enum", default="desc",
                options=[
                    {"value": "asc", "label": "Ascending"},
                    {"value": "desc", "label": "Descending"},
                ],
                description="Sort direction applied to the table."),
        ],
        kiosk_mode="render",
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
        config_schema=[
            _fs(key="filterByStatus", label="Filter by Status", type="enum", default="all",
                options=[
                    {"value": "all", "label": "All services"},
                    {"value": "running", "label": "Running"},
                    {"value": "stopped", "label": "Stopped"},
                    {"value": "failed", "label": "Failed"},
                    {"value": "unknown", "label": "Unknown"},
                ],
                description="Only show services matching the selected status."),
            _fs(key="groupByNode", label="Group by Node", type="boolean", default=False,
                description="Organize services into collapsible groups per node."),
        ],
        kiosk_mode="render",
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
        config_schema=[
            _fs(key="limit", label="Feed Length", type="number", default=25, min=10, max=100, step=5,
                description="Maximum number of events to display in the feed."),
            _fs(key="showAvatars", label="Show Avatars", type="boolean", default=True,
                description="Display user/system avatars alongside each event entry."),
        ],
        kiosk_mode="render",
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
        config_schema=[
            _fs(key="severityFilter", label="Severity Filter", type="enum", default="all",
                options=[
                    {"value": "all", "label": "All severities"},
                    {"value": "critical", "label": "Critical only"},
                    {"value": "warning", "label": "Warning and above"},
                    {"value": "info", "label": "Info and above"},
                ],
                description="Filter alerts by minimum severity level."),
            _fs(key="limit", label="Item Limit", type="number", default=20, min=5, max=50, step=5,
                description="Maximum number of alerts to display."),
        ],
        kiosk_mode="render",
    ),
    # ── Tier 3 — Log Viewer (gated) ──────────────────────────────────
    _tier3_definition(
        widget_type="hydra::log-viewer",
        display_name="Log Viewer",
        description="Scrollable log output with level filtering. Requires WebSocket (Wave 5).",
        category="tables-lists",
        icon="file-text",
        default_size={"w": 12, "h": 6},
        min_size={"w": 6, "h": 4},
        max_size={"w": 12, "h": 10},
        supported_data_shapes=["log-lines"],
        tags=["logs", "viewer"],
    ),
    # ── Tier 2 — Charts & Graphs ─────────────────────────────────────
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
        config_schema=[
            _fs(key="showLegend", label="Show Legend", type="boolean", default=True,
                description="Display a color legend for each series."),
            _fs(key="smoothing", label="Smooth Curves", type="boolean", default=False,
                description="Apply Bezier curve smoothing to chart lines."),
            _fs(key="stacking", label="Stacking", type="enum", default="none",
                options=[
                    {"value": "none", "label": "None (independent lines)"},
                    {"value": "normal", "label": "Stacked (absolute)"},
                    {"value": "percent", "label": "Stacked (100%)"},
                ],
                description="How series are stacked on the chart."),
        ],
        kiosk_mode="render",
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
        config_schema=[
            _fs(key="orientation", label="Orientation", type="enum", default="vertical",
                options=[
                    {"value": "vertical", "label": "Vertical (columns)"},
                    {"value": "horizontal", "label": "Horizontal (rows)"},
                ],
                description="Direction bars are drawn."),
            _fs(key="stacking", label="Stacking", type="enum", default="none",
                options=[
                    {"value": "none", "label": "None (grouped)"},
                    {"value": "normal", "label": "Stacked (absolute)"},
                    {"value": "percent", "label": "Stacked (100%)"},
                ],
                description="Bar stacking mode."),
            _fs(key="showValues", label="Show Values", type="boolean", default=False,
                description="Print the numeric value above each bar."),
        ],
        kiosk_mode="render",
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
        config_schema=[
            _fs(key="stacking", label="Stacking", type="enum", default="none",
                options=[
                    {"value": "none", "label": "None (independent areas)"},
                    {"value": "normal", "label": "Stacked (absolute)"},
                    {"value": "percent", "label": "Stacked (100%)"},
                ],
                description="Area stacking mode."),
            _fs(key="showPoints", label="Show Data Points", type="boolean", default=False,
                description="Display a dot at each data point."),
            _fs(key="fillOpacity", label="Fill Opacity", type="number", default=0.4,
                min=0.0, max=1.0, step=0.1,
                description="Opacity of the filled area (0 = transparent, 1 = opaque)."),
        ],
        kiosk_mode="render",
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
        config_schema=[
            _fs(key="colorScale", label="Color Scale", type="enum", default="blue-red",
                options=[
                    {"value": "blue-red", "label": "Blue → Red"},
                    {"value": "green-red", "label": "Green → Red"},
                    {"value": "grayscale", "label": "Grayscale"},
                    {"value": "spectral", "label": "Spectral"},
                ],
                description="Color scale used to encode intensity values."),
            _fs(key="showLegend", label="Show Legend", type="boolean", default=True,
                description="Display a color scale legend beside the heatmap."),
            _fs(key="aggregation", label="Aggregation", type="enum", default="avg",
                options=[
                    {"value": "sum", "label": "Sum"},
                    {"value": "avg", "label": "Average"},
                    {"value": "max", "label": "Maximum"},
                ],
                description="How values are aggregated within each heatmap cell."),
        ],
        kiosk_mode="render",
        repeatable=True,
    ),
    # ── Tier 2 — Topology & Maps ──────────────────────────────────────
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
        config_schema=[
            _fs(key="layoutAlgorithm", label="Layout Algorithm", type="enum", default="force",
                options=[
                    {"value": "force", "label": "Force-directed"},
                    {"value": "grid", "label": "Grid"},
                    {"value": "hierarchical", "label": "Hierarchical"},
                ],
                description="Algorithm used to position nodes on the map."),
            _fs(key="showLabels", label="Show Labels", type="boolean", default=True,
                description="Display node and network labels on the map."),
        ],
        kiosk_mode="render",
    ),
    # ── Controls & Actions (4 new — Wave 3 for command wiring) ────────
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
        config_schema=[
            _fs(key="actionId", label="Action ID", type="string", required=True,
                description="Registered command or action identifier to execute."),
            _fs(key="label", label="Button Label", type="string", default="",
                description="Custom label for the action button (overrides command name)."),
            _fs(key="variant", label="Button Variant", type="enum", default="default",
                options=[
                    {"value": "default", "label": "Default"},
                    {"value": "primary", "label": "Primary (accent)"},
                    {"value": "destructive", "label": "Destructive (red)"},
                    {"value": "outline", "label": "Outline"},
                ],
                description="Visual style of the action button."),
        ],
        kiosk_mode="readonly",
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
        config_schema=[
            _fs(key="commandId", label="Command ID", type="string", required=True,
                description="Command definition ID to trigger. Wave 5 will add a picker."),
            _fs(key="confirmBeforeRun", label="Confirm Before Run", type="boolean", default=True,
                description="Show a confirmation dialog before executing the command."),
        ],
        kiosk_mode="readonly",
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
        config_schema=[
            _fs(key="serviceId", label="Service", type="entity-ref", entity_type="service", required=True,
                description="Target service to control."),
            _fs(key="allowedOps", label="Allowed Operations", type="string", default="start,stop,restart",
                description="Comma-separated list of allowed operations (start, stop, restart, reload)."),
        ],
        kiosk_mode="readonly",
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
        config_schema=[
            _fs(key="workflowId", label="Workflow ID", type="string", required=True,
                description="Workflow definition ID to trigger. Wave 5 will add a picker."),
            _fs(key="confirmBeforeRun", label="Confirm Before Run", type="boolean", default=True,
                description="Show a confirmation dialog before triggering the workflow."),
        ],
        kiosk_mode="readonly",
        repeatable=True,
    ),
    # ── Infrastructure (3 new, capacity-overview already exists) ───────
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
        config_schema=[
            _fs(key="nodeId", label="Node", type="entity-ref", entity_type="node", required=True,
                description="Target node to display the summary for."),
            _fs(key="sections", label="Visible Sections", type="string", default="specs,services,status",
                description="Comma-separated list of sections to show: specs, services, status, tags, network."),
        ],
        kiosk_mode="render",
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
        config_schema=[
            _fs(key="metrics", label="Metrics", type="string", default="cpu,memory,disk",
                description="Comma-separated resource metrics to display: cpu, memory, disk, network."),
            _fs(key="showThresholds", label="Show Thresholds", type="boolean", default=True,
                description="Overlay threshold lines on each resource bar."),
        ],
        kiosk_mode="render",
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
        config_schema=[
            _fs(key="networkId", label="Network", type="entity-ref", entity_type="network", required=True,
                description="Target network to summarize."),
            _fs(key="showDevices", label="Show Device Count", type="boolean", default=True,
                description="Display the number of devices attached to this network."),
        ],
        kiosk_mode="render",
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
        config_schema=[
            _fs(key="fromProfileId", label="From Profile ID", type="string", default="",
                description="Profile ID to use as the 'before' state in the diff."),
            _fs(key="toProfileId", label="To Profile ID", type="string", default="",
                description="Profile ID to use as the 'after' state. Leave blank for the latest profile."),
            _fs(key="showUnchanged", label="Show Unchanged Sections", type="boolean", default=False,
                description="Include unchanged config sections in the diff output."),
        ],
        kiosk_mode="render",
    ),
    # ── Time & History (3) ────────────────────────────────────────────
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
        config_schema=[
            _fs(key="timeRange", label="Default Time Range", type="enum", default="7d",
                options=[
                    {"value": "1d", "label": "Last 24 hours"},
                    {"value": "7d", "label": "Last 7 days"},
                    {"value": "30d", "label": "Last 30 days"},
                    {"value": "90d", "label": "Last 90 days"},
                ],
                description="Default time window shown when the scrubber first loads."),
            _fs(key="step", label="Scrub Step", type="enum", default="1h",
                options=[
                    {"value": "15m", "label": "15 minutes"},
                    {"value": "1h", "label": "1 hour"},
                    {"value": "6h", "label": "6 hours"},
                    {"value": "1d", "label": "1 day"},
                ],
                description="Time step per keyboard nudge or scrub click."),
        ],
        kiosk_mode="readonly",
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
        config_schema=[
            _fs(key="entityFilter", label="Entity Filter", type="string", default="",
                description="Comma-separated entity IDs to filter changes by (leave blank for all)."),
            _fs(key="limit", label="Item Limit", type="number", default=25, min=5, max=100, step=5,
                description="Maximum number of change log entries to display."),
        ],
        kiosk_mode="render",
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
        config_schema=[
            _fs(key="nodeId", label="Node", type="entity-ref", entity_type="node", required=True,
                description="Target node whose profile versions to display."),
            _fs(key="range", label="History Range", type="enum", default="30d",
                options=[
                    {"value": "7d", "label": "Last 7 days"},
                    {"value": "30d", "label": "Last 30 days"},
                    {"value": "90d", "label": "Last 90 days"},
                    {"value": "all", "label": "All versions"},
                ],
                description="How far back to look for profile versions."),
        ],
        kiosk_mode="render",
    ),
    # ── External & Embed — HTML Block (1 new) ─────────────────────────
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
        config_schema=[
            _fs(key="html", label="HTML Content", type="string", default="",
                description="Raw HTML to render inside a sandboxed container."),
            _fs(key="allowScripts", label="Allow Scripts", type="boolean", default=False,
                description="Enable inline scripts (disabled by default for security)."),
        ],
        kiosk_mode="render",
        repeatable=True,
    ),
    # ── System & Meta — API Status ─────────────────────────────────────
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
        config_schema=[
            _fs(key="endpoints", label="Extra Endpoints", type="string", default="",
                description="Comma-separated additional endpoint URLs to health-check alongside the API."),
            _fs(key="pollInterval", label="Poll Interval (s)", type="number", default=30,
                min=10, max=300, step=10,
                description="How often to re-poll the API health endpoint, in seconds."),
        ],
        kiosk_mode="render",
    ),
    # ── Tier 3 — Gated (isAvailable=False) ───────────────────────────
    _tier3_definition(
        widget_type="hydra::integration-health",
        display_name="Integration Health",
        description="Status indicators for each enabled integration plugin. Requires plugin system (Wave 5).",
        category="system-meta",
        icon="puzzle",
        default_size={"w": 6, "h": 3},
        min_size={"w": 4, "h": 2},
        max_size={"w": 12, "h": 6},
        supported_data_shapes=["integration-status-array"],
        tags=["integrations", "health", "plugins"],
    ),
    _tier3_definition(
        widget_type="hydra::agent-grid",
        display_name="Agent Grid",
        description="Grid of all registered agents with tier, version, and last seen. Requires WebSocket (Wave 5).",
        category="system-meta",
        icon="cpu",
        default_size={"w": 12, "h": 4},
        min_size={"w": 6, "h": 3},
        max_size={"w": 12, "h": 6},
        supported_data_shapes=["agent-status-array"],
        tags=["agents", "grid", "status"],
    ),
    _tier3_definition(
        widget_type="hydra::audit-stream",
        display_name="Audit Stream",
        description="Live stream of audit log entries with action filtering. Requires WebSocket (Wave 5).",
        category="system-meta",
        icon="scroll-text",
        default_size={"w": 6, "h": 4},
        min_size={"w": 4, "h": 3},
        max_size={"w": 12, "h": 8},
        supported_data_shapes=["audit-log-entries"],
        tags=["audit", "stream", "log"],
    ),
    _tier3_definition(
        widget_type="hydra::mcp-query",
        display_name="MCP Query",
        description="Text input for natural language queries to the MCP service. Requires MCP integration (Wave 5).",
        category="system-meta",
        icon="message-square",
        default_size={"w": 6, "h": 4},
        min_size={"w": 4, "h": 3},
        max_size={"w": 12, "h": 8},
        tags=["mcp", "query", "ai"],
    ),
    _tier3_definition(
        widget_type="hydra::execution-queue",
        display_name="Execution Queue",
        description="Live view of pending, running, and completed command executions. Requires WebSocket (Wave 5).",
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

    def list_for_role(
        self,
        role: str | None,
        available_only: bool = False,
    ) -> list[dict[str, object]]:
        """Return definitions visible to the given role.

        If ``role`` is None or the admin role, all widgets (subject to
        ``available_only``) are returned. Otherwise only widgets whose
        ``permissions.view`` list includes the role are returned.

        Args:
            role: Caller's role name. None and ``"admin"`` mean no restriction.
            available_only: When True, Tier 3 widgets (``isAvailable: False``)
                are excluded. Used by the widget picker to hide gated widgets.
        """
        all_widgets = self.list_all()

        # Apply availability filter first (Tier 3 gating)
        if available_only:
            all_widgets = [w for w in all_widgets if bool(w.get("isAvailable", True))]

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

    def categories_for_role(
        self,
        role: str | None = None,
        available_only: bool = False,
    ) -> list[dict[str, Any]]:
        """Return ``(id, name, count)`` tuples for all spec categories.

        The count reflects the number of widgets in each category that are
        visible to ``role``. Categories with zero visible widgets are still
        included so the picker can render the full taxonomy (with disabled
        entries) in later waves.
        """
        visible = self.list_for_role(role, available_only=available_only)
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
    "COMMON_FIELD_SCHEMAS",
    "EntityRefType",
    "FieldSchema",
    "FieldType",
    "KioskMode",
    "LEGACY_CATEGORY_ALIASES",
    "SPEC_CATEGORIES",
    "WidgetRegistry",
    "widget_registry",
]
