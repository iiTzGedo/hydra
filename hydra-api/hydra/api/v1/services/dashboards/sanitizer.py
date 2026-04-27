"""Sanitize a board document for kiosk rendering.

Applies the widget registry's ``kioskMode`` setting to each widget on a board:

- ``"hide"``     — widget is excluded entirely (not sent to the client).
- ``"readonly"`` — widget is included with ``readonly=True`` (controls disabled).
- ``"render"``   — widget is included unchanged with ``readonly=False``.

Unknown widget types are treated as ``readonly=True`` for safety (fail closed).
"""

from __future__ import annotations

from typing import Any

from hydra.api.v1.services.dashboards.widget_registry import widget_registry


def sanitize_for_kiosk(board: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *board* with widgets filtered and annotated for kiosk mode.

    NOTE: Expects camelCase keys as produced by ``DashboardService._format_board``.
    The function reads ``board["widgets"]`` and each widget's ``"widgetType"`` key.
    If the board-formatter changes the ``widgets`` key shape or renames ``widgetType``,
    this function will silently produce an empty or unfiltered widget list.
    Keep this function in sync with ``_format_board``.

    Args:
        board: Board document dict as returned by DashboardService formatters
               (camelCase keys, ``widgets`` is a list of widget instance dicts).

    Returns:
        A shallow copy of *board* with a new ``widgets`` list that:
        - Omits any widget whose registry ``kioskMode`` is ``"hide"``.
        - Adds ``readonly=True`` to widgets whose ``kioskMode`` is ``"readonly"``.
        - Adds ``readonly=False`` to widgets whose ``kioskMode`` is ``"render"``.
        - Adds ``readonly=True`` to widgets with unregistered types (safe default).
    """
    sanitized_widgets: list[dict[str, Any]] = []

    for widget in board.get("widgets", []):
        widget_type = widget.get("widgetType", "")
        defn = widget_registry.get(widget_type)

        if defn is None:
            # Unknown widget type — include but mark as readonly for safety.
            sanitized_widgets.append({**widget, "readonly": True})
            continue

        # ``kioskMode`` is stored as the camelCase key in the registry dict.
        mode: str = str(defn.get("kioskMode", "render"))

        if mode == "hide":
            # Exclude entirely — do not add to sanitized list.
            continue

        sanitized_widgets.append({**widget, "readonly": mode == "readonly"})

    return {**board, "widgets": sanitized_widgets}
