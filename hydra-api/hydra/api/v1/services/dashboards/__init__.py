"""Dashboard service package.

Re-exports the public dashboard service API so existing imports keep working:

    from hydra.api.v1.services.dashboards import DashboardService
"""

from hydra.api.v1.services.dashboards.service import (
    MAX_BOARDS_PER_USER,
    MAX_SHARED_BOARDS_PER_USER,
    MAX_WIDGETS_PER_BOARD,
    DashboardNotFoundError,
    DashboardService,
    WidgetNotFoundError,
)
from hydra.api.v1.services.dashboards.widget_registry import (
    SPEC_CATEGORIES,
    WidgetRegistry,
    widget_registry,
)

__all__ = [
    "DashboardNotFoundError",
    "DashboardService",
    "MAX_BOARDS_PER_USER",
    "MAX_SHARED_BOARDS_PER_USER",
    "MAX_WIDGETS_PER_BOARD",
    "SPEC_CATEGORIES",
    "WidgetNotFoundError",
    "WidgetRegistry",
    "widget_registry",
]
