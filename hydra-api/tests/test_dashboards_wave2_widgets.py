"""Tests for Wave 2 widget registry expansion.

Verifies that all ~45 spec-defined widget types plus the existing Hydra
custom composites are registered with correct categories, valid size
constraints, and proper config schemas.
"""

import pytest

from hydra.api.v1.services.dashboards.widget_registry import (
    SPEC_CATEGORIES,
    WidgetRegistry,
    widget_registry,
)


class TestWidgetRegistryExpansion:
    """Verify Wave 2 registry expansion."""

    def test_total_widget_count_covers_spec(self):
        """Registry should have at least 45 widgets (spec) + existing composites."""
        all_widgets = widget_registry.list_all()
        assert len(all_widgets) >= 45, f"Expected >=45 widgets, got {len(all_widgets)}"

    def test_all_native_categories_populated(self):
        """All spec categories with native widgets should have at least 1 widget.

        The ``iot-home`` category is populated exclusively by plugin-contributed
        widgets (Home Assistant, etc.) and is expected to be empty until Wave 5.
        """
        plugin_only_categories = {"iot-home"}
        all_widgets = widget_registry.list_all()
        populated_cats = {str(w.get("category", "")) for w in all_widgets}
        for cat_id in SPEC_CATEGORIES:
            if cat_id in plugin_only_categories:
                continue
            assert cat_id in populated_cats, f"Category '{cat_id}' has zero native widgets"

    def test_category_counts_match_spec(self):
        """Each category should have a reasonable count per spec §5."""
        all_widgets = widget_registry.list_all()
        counts: dict[str, int] = {}
        for w in all_widgets:
            cat = str(w.get("category", ""))
            counts[cat] = counts.get(cat, 0) + 1

        # data-display: spec has 6 + stats-cards = 7
        assert counts.get("data-display", 0) >= 6
        # status-health: spec has 5 + node-status-grid = 7
        assert counts.get("status-health", 0) >= 5
        # tables-lists: spec has 5 + recent-activity = 5 min
        assert counts.get("tables-lists", 0) >= 4
        # charts-graphs: spec has 4
        assert counts.get("charts-graphs", 0) >= 4
        # topology-maps: spec has 2
        assert counts.get("topology-maps", 0) >= 2
        # controls-actions: spec has 4
        assert counts.get("controls-actions", 0) >= 4
        # infrastructure: spec has 4 + capacity-overview = 5
        assert counts.get("infrastructure", 0) >= 4
        # time-history: spec has 3
        assert counts.get("time-history", 0) >= 3
        # external-embed: spec has 7
        assert counts.get("external-embed", 0) >= 6
        # system-meta: spec has 6 + recent-activity = 7
        assert counts.get("system-meta", 0) >= 6

    @pytest.mark.parametrize(
        "widget_type",
        [
            # Data display
            "hydra::metric-card",
            "hydra::gauge",
            "hydra::progress-bar",
            "hydra::sparkline",
            "hydra::stat-group",
            "hydra::donut-chart",
            # Status & health
            "hydra::status-grid",
            "hydra::health-matrix",
            "hydra::node-status-card",
            "hydra::service-status-bar",
            "hydra::uptime-bar",
            # Tables & lists
            "hydra::entity-table",
            "hydra::service-list",
            "hydra::activity-feed",
            "hydra::alert-list",
            "hydra::log-viewer",
            # Charts & graphs
            "hydra::line-chart",
            "hydra::bar-chart",
            "hydra::area-chart",
            "hydra::heatmap",
            # Topology & maps
            "hydra::network-map",
            # Controls & actions
            "hydra::quick-action",
            "hydra::command-trigger",
            "hydra::service-control",
            "hydra::workflow-trigger",
            # Infrastructure
            "hydra::node-summary",
            "hydra::capacity-panel",
            "hydra::network-summary",
            "hydra::profile-diff",
            # Time & history
            "hydra::time-machine-scrubber",
            "hydra::change-log",
            "hydra::profile-timeline",
            # External & embed
            "hydra::html-block",
            # System & meta
            "hydra::integration-health",
            "hydra::agent-grid",
            "hydra::audit-stream",
            "hydra::api-status",
            "hydra::mcp-query",
            "hydra::execution-queue",
        ],
    )
    def test_spec_widget_type_registered(self, widget_type: str):
        """Every spec-defined widget type must be in the registry."""
        definition = widget_registry.get(widget_type)
        assert definition is not None, f"Widget type '{widget_type}' not found in registry"

    def test_widget_definitions_have_required_fields(self):
        """All widgets must have the required fields from spec §4.1."""
        required_keys = {
            "widgetType",
            "displayName",
            "description",
            "category",
            "icon",
            "source",
            "version",
            "supportedDataShapes",
            "tags",
            "permissions",
            "defaultSize",
            "minSize",
            "maxSize",
            "configSchema",
            "capabilities",
        }
        for widget in widget_registry.list_all():
            widget_type = widget.get("widgetType", "unknown")
            for key in required_keys:
                assert key in widget, f"Widget '{widget_type}' missing field '{key}'"

    def test_size_constraints_valid(self):
        """min <= default <= max for both w and h."""
        for widget in widget_registry.list_all():
            wt = str(widget.get("widgetType", "?"))
            default = widget.get("defaultSize", {})
            min_s = widget.get("minSize", {})
            max_s = widget.get("maxSize", {})

            assert isinstance(default, dict) and isinstance(min_s, dict) and isinstance(max_s, dict), (
                f"{wt}: size fields must be dicts"
            )

            dw, dh = default.get("w", 0), default.get("h", 0)
            minw, minh = min_s.get("w", 0), min_s.get("h", 0)
            maxw, maxh = max_s.get("w", 0), max_s.get("h", 0)

            assert minw <= dw <= maxw, f"{wt}: invalid w chain {minw} <= {dw} <= {maxw}"
            assert minh <= dh <= maxh, f"{wt}: invalid h chain {minh} <= {dh} <= {maxh}"

    def test_control_widgets_restricted_to_operators(self):
        """Control widgets should only be visible to admin/operator roles."""
        control_types = [
            "hydra::quick-action",
            "hydra::command-trigger",
            "hydra::service-control",
            "hydra::workflow-trigger",
        ]
        for wt in control_types:
            defn = widget_registry.get(wt)
            assert defn is not None
            permissions = defn.get("permissions", {})
            assert isinstance(permissions, dict)
            view_roles = permissions.get("view", [])
            assert isinstance(view_roles, list)
            assert "family" not in view_roles, f"{wt} should not be visible to family role"
            assert "admin" in view_roles
            assert "operator" in view_roles

    def test_role_filter_hides_control_widgets_from_family(self):
        """Family role should not see control widgets."""
        family_widgets = widget_registry.list_for_role("family")
        family_types = {str(w.get("widgetType", "")) for w in family_widgets}
        assert "hydra::quick-action" not in family_types
        assert "hydra::command-trigger" not in family_types
        assert "hydra::service-control" not in family_types
        assert "hydra::workflow-trigger" not in family_types

    def test_role_filter_admin_sees_all(self):
        """Admin role should see all widgets."""
        admin_widgets = widget_registry.list_for_role("admin")
        all_widgets = widget_registry.list_all()
        assert len(admin_widgets) == len(all_widgets)

    def test_categories_for_role_returns_all_11(self):
        """categories_for_role should return all 11 spec categories."""
        categories = widget_registry.categories_for_role("admin")
        assert len(categories) == 11
        cat_ids = {c["id"] for c in categories}
        assert cat_ids == set(SPEC_CATEGORIES.keys())

    def test_every_widget_declares_a_data_shape(self):
        """P2DASH-T010: every widget must declare at least one data shape."""
        for widget in widget_registry.list_all():
            wt = str(widget.get("widgetType", "?"))
            shapes = widget.get("supportedDataShapes", [])
            assert isinstance(shapes, list) and len(shapes) >= 1, (
                f"{wt} must declare at least one supportedDataShapes entry"
            )

    def test_every_widget_has_requires_plugin_field(self):
        """P2DASH-T028-lite: every widget exposes a requiresPlugin field (None for core)."""
        for widget in widget_registry.list_all():
            wt = str(widget.get("widgetType", "?"))
            assert "requiresPlugin" in widget, f"{wt} missing requiresPlugin field"
            # All built-in widgets are core Hydra widgets — no plugin dependency yet.
            assert widget["requiresPlugin"] is None, (
                f"{wt} unexpectedly declares a plugin dependency"
            )

    def test_family_role_sees_only_iot_and_embed_widgets(self):
        """P2DASH-T013: family role is scoped to IoT/home and embed widgets only."""
        family_widgets = widget_registry.list_for_role("family")
        assert family_widgets, "family should see at least the embed widgets"
        allowed = {"iot-home", "external-embed"}
        for widget in family_widgets:
            cat = str(widget.get("category", ""))
            assert cat in allowed, (
                f"{widget.get('widgetType')} (category {cat}) should not be visible to family"
            )
        # Family must not see infrastructure or system/meta widgets.
        family_cats = {str(w.get("category", "")) for w in family_widgets}
        assert "infrastructure" not in family_cats
        assert "system-meta" not in family_cats
        assert "topology-maps" not in family_cats

    def test_viewer_role_sees_non_family_restricted_widgets(self):
        """Viewer sees standard widgets (in default view roles) but not control widgets."""
        viewer_widgets = widget_registry.list_for_role("viewer")
        viewer_types = {str(w.get("widgetType", "")) for w in viewer_widgets}
        # Viewer can see read-only infrastructure widgets...
        assert "hydra::capacity-overview" in viewer_types
        # ...but not interactive control widgets (admin/operator only).
        assert "hydra::quick-action" not in viewer_types

    def test_reset_to_builtins(self):
        """reset_to_builtins should restore full widget set."""
        registry = WidgetRegistry()
        initial_count = len(registry.list_all())

        # Add a custom widget
        registry.register({
            "widgetType": "test::custom",
            "displayName": "Test",
            "description": "Test widget",
            "category": "data-display",
            "icon": "test",
            "source": "test",
            "version": "1.0.0",
            "supportedDataShapes": [],
            "tags": [],
            "permissions": {"view": [], "interact": []},
            "defaultSize": {"w": 4, "h": 4},
            "minSize": {"w": 2, "h": 2},
            "maxSize": {"w": 12, "h": 12},
            "configSchema": [],
            "capabilities": {
                "configurable": False,
                "supportsVisibilityToggle": True,
                "repeatable": True,
            },
        })
        assert len(registry.list_all()) == initial_count + 1

        registry.reset_to_builtins()
        assert len(registry.list_all()) == initial_count
        assert registry.get("test::custom") is None

    def test_register_and_unregister_roundtrip(self):
        """P2DASH-T012: registry supports dynamic register/unregister of widget types."""
        registry = WidgetRegistry()
        initial_count = len(registry.list_all())

        registry.register({
            "widgetType": "plg::demo::panel",
            "displayName": "Demo Panel",
            "description": "Plugin-contributed demo widget",
            "category": "infrastructure",
            "icon": "puzzle",
            "source": "plugin",
            "version": "1.0.0",
            "supportedDataShapes": ["single-node"],
            "tags": ["demo"],
            "requiresPlugin": "plg::demo",
            "permissions": {"view": ["admin"], "interact": []},
            "defaultSize": {"w": 4, "h": 4},
            "minSize": {"w": 2, "h": 2},
            "maxSize": {"w": 12, "h": 12},
            "configSchema": [],
            "capabilities": {
                "configurable": False,
                "supportsVisibilityToggle": True,
                "repeatable": False,
            },
        })
        assert registry.has("plg::demo::panel")
        assert len(registry.list_all()) == initial_count + 1

        # Unregister returns True when present, False when already gone.
        assert registry.unregister("plg::demo::panel") is True
        assert not registry.has("plg::demo::panel")
        assert len(registry.list_all()) == initial_count
        assert registry.unregister("plg::demo::panel") is False

    def test_register_rejects_unknown_category(self):
        """register() must reject definitions with a non-spec category."""
        registry = WidgetRegistry()
        with pytest.raises(ValueError, match="unknown category"):
            registry.register({
                "widgetType": "test::bad-category",
                "displayName": "Bad",
                "category": "not-a-real-category",
                "icon": "x",
                "defaultSize": {"w": 4, "h": 4},
                "minSize": {"w": 2, "h": 2},
                "maxSize": {"w": 12, "h": 12},
            })
