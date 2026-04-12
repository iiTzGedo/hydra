"""Built-in dashboard template definitions.

Contains the seed data for shipping dashboards. Templates target the spec's
4-type board taxonomy via ``boardType: user`` (since end users instantiate
templates into their own user boards) and use only the built-in native
widgets available in the current widget registry.

Wave 3 will expand this with spec-aligned fields (``category``,
``targetRoles``, ``requiredPlugins``, ``variables``, ``source``, ``preview``)
once template variables and plugin widgets land.
"""

from __future__ import annotations

from typing import Any


def _grid_layout() -> dict[str, Any]:
    """Standard 5-breakpoint grid layout shared by all built-in templates."""
    return {
        "columns": 12,
        "rowHeight": 80,
        "breakpoints": {
            "xl": {"columns": 12, "width": 1536},
            "lg": {"columns": 12, "width": 1200},
            "md": {"columns": 8, "width": 996},
            "sm": {"columns": 4, "width": 480},
            "xs": {"columns": 2, "width": 0},
        },
    }


def _widget(widget_type: str, x: int, y: int, w: int, h: int) -> dict[str, Any]:
    return {
        "widgetType": widget_type,
        "position": {"x": x, "y": y, "w": w, "h": h},
        "config": {},
        "dataBinding": None,
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


BUILTIN_TEMPLATES: list[dict[str, Any]] = [
    {
        "templateId": "tmpl_infra_overview",
        "name": "Infrastructure Overview",
        "description": "A comprehensive view of your infrastructure with stats, node status, and capacity metrics.",
        "boardType": "user",
        "layout": _grid_layout(),
        "widgets": [
            _widget("hydra::stats-cards", 0, 0, 12, 2),
            _widget("hydra::node-status-grid", 0, 2, 12, 4),
            _widget("hydra::capacity-overview", 0, 6, 12, 4),
        ],
        "settings": _default_settings(),
        "tags": ["infrastructure", "overview", "builtin"],
    },
    {
        "templateId": "tmpl_service_health",
        "name": "Service Health",
        "description": "Monitor service health and key infrastructure metrics.",
        "boardType": "user",
        "layout": _grid_layout(),
        "widgets": [
            _widget("hydra::service-summary", 0, 0, 6, 4),
            _widget("hydra::stats-cards", 6, 0, 6, 2),
        ],
        "settings": _default_settings(),
        "tags": ["services", "health", "builtin"],
    },
    {
        "templateId": "tmpl_network_ops",
        "name": "Network Operations",
        "description": "Network topology and infrastructure metrics at a glance.",
        "boardType": "user",
        "layout": _grid_layout(),
        "widgets": [
            _widget("hydra::mini-topology", 0, 0, 12, 4),
            _widget("hydra::stats-cards", 0, 4, 12, 2),
        ],
        "settings": _default_settings(),
        "tags": ["network", "topology", "builtin"],
    },
    {
        "templateId": "tmpl_capacity",
        "name": "Capacity Planning",
        "description": "Resource utilization and capacity metrics for planning.",
        "boardType": "user",
        "layout": _grid_layout(),
        "widgets": [
            _widget("hydra::capacity-overview", 0, 0, 12, 4),
            _widget("hydra::stats-cards", 0, 4, 12, 2),
        ],
        "settings": _default_settings(),
        "tags": ["capacity", "planning", "builtin"],
    },
    {
        "templateId": "tmpl_activity",
        "name": "Activity Monitor",
        "description": "Track recent infrastructure events and key metrics.",
        "boardType": "user",
        "layout": _grid_layout(),
        "widgets": [
            _widget("hydra::recent-activity", 0, 0, 6, 4),
            _widget("hydra::stats-cards", 6, 0, 6, 2),
        ],
        "settings": _default_settings(),
        "tags": ["activity", "events", "builtin"],
    },
    {
        "templateId": "tmpl_minimal",
        "name": "Minimal Home",
        "description": "A clean, minimal dashboard with just the key stats.",
        "boardType": "user",
        "layout": _grid_layout(),
        "widgets": [
            _widget("hydra::stats-cards", 0, 0, 12, 2),
        ],
        "settings": _default_settings(),
        "tags": ["minimal", "home", "builtin"],
    },
    {
        "templateId": "tmpl_ops_center",
        "name": "Operations Center",
        "description": "Full operations view with all core widgets for comprehensive monitoring.",
        "boardType": "user",
        "layout": _grid_layout(),
        "widgets": [
            _widget("hydra::stats-cards", 0, 0, 12, 2),
            _widget("hydra::service-summary", 0, 2, 6, 4),
            _widget("hydra::recent-activity", 6, 2, 6, 4),
            _widget("hydra::capacity-overview", 0, 6, 12, 4),
            _widget("hydra::mini-topology", 0, 10, 12, 4),
            _widget("hydra::node-status-grid", 0, 14, 12, 4),
        ],
        "settings": _default_settings(),
        "tags": ["operations", "full", "builtin"],
    },
    {
        "templateId": "tmpl_iot",
        "name": "IoT Dashboard",
        "description": "Monitor IoT nodes and device status across your infrastructure.",
        "boardType": "user",
        "layout": _grid_layout(),
        "widgets": [
            _widget("hydra::stats-cards", 0, 0, 12, 2),
            _widget("hydra::node-status-grid", 0, 2, 12, 4),
        ],
        "settings": _default_settings(),
        "tags": ["iot", "devices", "builtin"],
    },
    {
        "templateId": "tmpl_security",
        "name": "Security Overview",
        "description": "Security-focused view with recent activity and key infrastructure metrics.",
        "boardType": "user",
        "layout": _grid_layout(),
        "widgets": [
            _widget("hydra::stats-cards", 0, 0, 12, 2),
            _widget("hydra::recent-activity", 0, 2, 12, 4),
        ],
        "settings": _default_settings(),
        "tags": ["security", "audit", "builtin"],
    },
]


__all__ = ["BUILTIN_TEMPLATES"]
