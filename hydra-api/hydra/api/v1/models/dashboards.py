"""Dashboard models for request/response validation."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

LayoutMode = Literal["grid", "columns", "freeform"]
BoardScope = Literal["standalone", "entity-panel"]
EntityPanelType = Literal["node", "service", "network"]


class BoardType(StrEnum):
    """Board type classification aligned with Dashboard Technical Specification §3.2."""

    USER = "user"
    TEMPLATE = "template"
    SHARED = "shared"
    KIOSK = "kiosk"


class OwnerType(StrEnum):
    """Owner type for board ownership semantics."""

    USER = "user"
    SYSTEM = "system"


class TemplateSource(StrEnum):
    """Origin of a dashboard template."""

    SYSTEM = "system"
    USER = "user"


class TemplateCategory(StrEnum):
    """Template category for grouping in the template browser."""

    INFRASTRUCTURE = "infrastructure"
    MONITORING = "monitoring"
    IOT = "iot"
    NETWORKING = "networking"
    SECURITY = "security"
    CAPACITY = "capacity"
    OPERATIONS = "operations"
    GENERAL = "general"


class VisibilityScope(StrEnum):
    """Board visibility scope."""

    PRIVATE = "private"
    SHARED = "shared"
    PUBLIC = "public"


class SharedWith(BaseModel):
    """Structured audience for shared boards."""

    model_config = ConfigDict(populate_by_name=True)

    roles: list[str] = Field(default_factory=list)
    users: list[str] = Field(default_factory=list)


class BoardVisibility(BaseModel):
    """Structured visibility descriptor per Dashboard Technical Specification §3.3."""

    model_config = ConfigDict(populate_by_name=True)

    scope: VisibilityScope = Field(default=VisibilityScope.PRIVATE)
    shared_with: SharedWith = Field(default_factory=SharedWith, alias="sharedWith")


class WidgetPosition(BaseModel):
    """Widget position on the grid layout."""

    model_config = ConfigDict(populate_by_name=True)

    x: int = Field(ge=0, description="Horizontal grid position")
    y: int = Field(ge=0, description="Vertical grid position")
    w: int = Field(ge=1, le=12, description="Width in grid columns")
    h: int = Field(ge=1, le=12, description="Height in grid rows")


class FreeformPosition(BaseModel):
    """Widget pixel coordinates for freeform layout mode.

    Constraints per Dashboard Technical Specification §4 "Constraints":
    - ``x``, ``y``: 0–10000 px canvas coordinates
    - ``w``: 80–2000 px (minimum widget width)
    - ``h``: 60–2000 px (minimum widget height)
    """

    x: float = Field(ge=0, le=10000, description="Horizontal pixel offset from canvas origin")
    y: float = Field(ge=0, le=10000, description="Vertical pixel offset from canvas origin")
    w: float = Field(ge=80, le=2000, description="Widget width in pixels")
    h: float = Field(ge=60, le=2000, description="Widget height in pixels")


DEFAULT_GRID_BREAKPOINTS: dict[str, dict[str, int]] = {
    "xl": {"columns": 12, "width": 1536},
    "lg": {"columns": 12, "width": 1200},
    "md": {"columns": 8, "width": 996},
    "sm": {"columns": 4, "width": 480},
    "xs": {"columns": 2, "width": 0},
}

_BREAKPOINT_ORDER = ("xl", "lg", "md", "sm", "xs")


def _default_breakpoints() -> dict[str, "LayoutBreakpoint"]:
    return {
        key: LayoutBreakpoint(**value)
        for key, value in DEFAULT_GRID_BREAKPOINTS.items()
    }


def _scale_position(position: dict[str, Any], target_columns: int, source_columns: int = 12) -> dict[str, int]:
    width_ratio = target_columns / max(source_columns, 1)
    x = int(round(int(position.get("x", 0)) * width_ratio))
    w = max(1, min(target_columns, int(round(int(position.get("w", 1)) * width_ratio))))
    return {
        "x": max(0, min(x, max(target_columns - w, 0))),
        "y": max(0, int(position.get("y", 0))),
        "w": w,
        "h": max(1, int(position.get("h", 1))),
    }


def _expand_legacy_position(position: dict[str, Any] | None) -> dict[str, dict[str, int]]:
    base_position = position or {"x": 0, "y": 0, "w": 12, "h": 4}
    placements: dict[str, dict[str, int]] = {}
    for key, breakpoint in DEFAULT_GRID_BREAKPOINTS.items():
        placements[key] = _scale_position(base_position, breakpoint["columns"])
    return placements


class LayoutBreakpoint(BaseModel):
    """Responsive breakpoint definition."""

    model_config = ConfigDict(populate_by_name=True)

    columns: int = Field(ge=1, le=24)
    width: int = Field(ge=0)


class GridLayoutConfig(BaseModel):
    """Grid layout configuration."""

    model_config = ConfigDict(populate_by_name=True)

    columns: int = Field(default=12, ge=1, le=24, description="Number of grid columns")
    row_height: int = Field(default=80, ge=20, le=500, alias="rowHeight", description="Row height in pixels")
    breakpoints: dict[str, LayoutBreakpoint] = Field(
        default_factory=_default_breakpoints,
        description="Responsive breakpoint configurations",
    )
    compaction: Literal["vertical", "horizontal", "none"] = Field(
        default="vertical",
        description="Grid compaction strategy",
    )
    margin: tuple[int, int] = Field(default=(16, 16), description="Grid item spacing in pixels")
    padding: tuple[int, int] = Field(default=(0, 0), description="Grid container padding in pixels")


class BoardColumnDefinition(BaseModel):
    """Definition of a named dashboard column."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(min_length=1, max_length=64)
    title: str | None = None
    ratio: int = Field(default=1, ge=1, le=12)


class ColumnLayoutConfig(BaseModel):
    """Glance-style named column layout."""

    model_config = ConfigDict(populate_by_name=True)

    columns: list[BoardColumnDefinition] = Field(
        default_factory=lambda: [
            BoardColumnDefinition(id="primary", title="Primary", ratio=2),
            BoardColumnDefinition(id="secondary", title="Secondary", ratio=1),
        ]
    )
    gap: int = Field(default=16, ge=0, le=64)
    padding: tuple[int, int] = Field(default=(0, 0))


class BoardLayout(BaseModel):
    """Board layout configuration."""

    model_config = ConfigDict(populate_by_name=True)

    mode: Literal["grid", "columns"] = Field(default="grid")
    grid: GridLayoutConfig | None = None
    columns_layout: ColumnLayoutConfig | None = Field(default=None, alias="columnsLayout")
    columns: int | list[BoardColumnDefinition] | None = None
    row_height: int | None = Field(default=None, alias="rowHeight")
    breakpoints: dict[str, LayoutBreakpoint] | None = None
    compaction: Literal["vertical", "horizontal", "none"] | None = None
    margin: tuple[int, int] | None = None
    padding: tuple[int, int] | None = None
    gap: int | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_layout(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        if "mode" not in value:
            return {
                "mode": "grid",
                "grid": {
                    "columns": value.get("columns", 12),
                    "rowHeight": value.get("rowHeight", 80),
                    "breakpoints": value.get("breakpoints", DEFAULT_GRID_BREAKPOINTS),
                    "compaction": value.get("compaction", "vertical"),
                    "margin": value.get("margin", (16, 16)),
                    "padding": value.get("padding", (0, 0)),
                },
            }

        if value.get("mode") == "grid" and value.get("grid") is None:
            return {
                **value,
                "grid": {
                    "columns": value.get("columns", 12),
                    "rowHeight": value.get("rowHeight", 80),
                    "breakpoints": value.get("breakpoints", DEFAULT_GRID_BREAKPOINTS),
                    "compaction": value.get("compaction", "vertical"),
                    "margin": value.get("margin", (16, 16)),
                    "padding": value.get("padding", (0, 0)),
                },
            }

        if value.get("mode") == "columns" and value.get("columnsLayout") is None:
            raw_columns = value.get("columns")
            normalized_columns = raw_columns if isinstance(raw_columns, list) else None
            return {
                **value,
                "columnsLayout": {
                    "columns": normalized_columns or [
                        {"id": "primary", "title": "Primary", "ratio": 2},
                        {"id": "secondary", "title": "Secondary", "ratio": 1},
                    ],
                    "gap": value.get("gap", 16),
                    "padding": value.get("padding", (0, 0)),
                },
            }

        return value

    @model_validator(mode="after")
    def ensure_matching_mode(self) -> "BoardLayout":
        if self.mode == "grid":
            self.grid = self.grid or GridLayoutConfig()
            self.columns_layout = None
            self.columns = self.grid.columns
            self.row_height = self.grid.row_height
            self.breakpoints = self.grid.breakpoints
            self.compaction = self.grid.compaction
            self.margin = self.grid.margin
            self.padding = self.grid.padding
            self.gap = None
        else:
            self.columns_layout = self.columns_layout or ColumnLayoutConfig()
            self.grid = None
            self.columns = self.columns_layout.columns
            self.row_height = None
            self.breakpoints = None
            self.compaction = None
            self.margin = None
            self.padding = self.columns_layout.padding
            self.gap = self.columns_layout.gap
        return self


class DataBindingFallback(BaseModel):
    """Fallback strategy when a data source is unavailable."""

    model_config = ConfigDict(populate_by_name=True)

    type: Literal["cached", "empty", "error"] = Field(default="cached")
    max_age: int | None = Field(default=None, ge=0, alias="maxAge")


class DataBinding(BaseModel):
    """Widget data binding configuration per Dashboard Technical Specification §6."""

    model_config = ConfigDict(populate_by_name=True)

    source: str = Field(description="Data source identifier (e.g., 'hydra::nodes')")
    query: dict[str, Any] = Field(default_factory=dict, description="Query parameters for the data source")
    refresh_interval: int | None = Field(
        default=None,
        ge=5,
        alias="refreshInterval",
        description="Refresh interval in seconds",
    )
    realtime_channel: str | None = Field(
        default=None,
        alias="realtimeChannel",
        description="WebSocket channel for push updates",
    )
    fallback: DataBindingFallback | None = Field(
        default=None,
        description="Cache strategy if source is unavailable",
    )


def _normalize_widget_placement(value: Any) -> Any:
    """Normalize widget placement data for both WidgetPlacementMixin and patches."""
    if not isinstance(value, dict):
        return value

    normalized = dict(value)
    placements = normalized.get("placements")
    position = normalized.get("position")

    if placements is None and position is not None:
        normalized["placements"] = _expand_legacy_position(position)
    elif placements is not None and position is None and isinstance(placements, dict):
        normalized["position"] = (
            placements.get("lg")
            or placements.get("xl")
            or placements.get("md")
            or next(iter(placements.values()), None)
        )

    if normalized.get("column") is not None and normalized.get("order") is None:
        normalized["order"] = 0

    return normalized


class WidgetPlacementMixin(BaseModel):
    """Shared widget placement fields."""

    model_config = ConfigDict(populate_by_name=True)

    position: WidgetPosition | None = Field(default=None, description="Primary placement for compatibility")
    placements: dict[str, WidgetPosition] | None = Field(
        default=None,
        description="Per-breakpoint widget placement for grid boards",
    )
    column: str | None = Field(default=None, description="Named column for column layouts")
    order: int | None = Field(default=None, description="Column order for column layouts")
    freeform_position: FreeformPosition | None = Field(
        default=None,
        alias="freeformPosition",
        description="Pixel coordinates for freeform layout mode; null in grid/columns mode",
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_widget(cls, value: Any) -> Any:
        return _normalize_widget_placement(value)

    @model_validator(mode="after")
    def ensure_widget_placement(self) -> "WidgetPlacementMixin":
        if self.placements is None and self.position is not None:
            self.placements = {
                key: WidgetPosition(**placement)
                for key, placement in _expand_legacy_position(self.position.model_dump()).items()
            }
        if self.position is None and self.placements:
            self.position = (
                self.placements.get("lg")
                or self.placements.get("xl")
                or self.placements.get("md")
                or next(iter(self.placements.values()), None)
            )
        if self.column is not None and self.order is None:
            self.order = 0
        if self.position is None and self.column is None:
            raise ValueError("Widget placement requires grid positions or a column assignment")
        return self


class WidgetInstance(WidgetPlacementMixin):
    """A specific widget placement on a board."""

    model_config = ConfigDict(populate_by_name=True)

    instance_id: str = Field(alias="instanceId", description="Unique widget instance identifier")
    widget_type: str = Field(alias="widgetType", description="Widget type from the registry")
    config: dict[str, Any] = Field(default_factory=dict, description="Widget-specific configuration")
    data_binding: DataBinding | None = Field(default=None, alias="dataBinding", description="Data binding configuration")
    readonly: bool | None = Field(
        default=None,
        description=(
            "Kiosk-mode flag set by the sanitizer. "
            "True = controls disabled; False = normal display; None = not in kiosk context."
        ),
    )


class BoardSettings(BaseModel):
    """Board-level settings per Dashboard Technical Specification §13.1."""

    model_config = ConfigDict(populate_by_name=True)

    theme: str = Field(default="inherit", description="Board theme override")
    auto_refresh: bool = Field(default=True, alias="autoRefresh", description="Enable auto-refresh")
    refresh_interval: int = Field(
        default=30,
        ge=5,
        alias="refreshInterval",
        description="Board-level refresh interval in seconds",
    )
    show_header: bool = Field(default=True, alias="showHeader", description="Show board header")
    kiosk_mode: bool = Field(default=False, alias="kioskMode", description="Enable kiosk mode")
    kiosk_auto_scroll: bool = Field(
        default=False,
        alias="kioskAutoScroll",
        description="Enable kiosk auto-scroll",
    )
    kiosk_scroll_speed: int = Field(
        default=30,
        ge=0,
        le=300,
        alias="kioskScrollSpeed",
        description="Kiosk auto-scroll speed in pixels per second",
    )
    background_image: str | None = Field(
        default=None,
        alias="backgroundImage",
        max_length=2048,
        description="Optional background image URL",
    )
    custom_css: str | None = Field(
        default=None,
        alias="customCss",
        max_length=10_000,
        description="Custom CSS scoped to this board",
    )


# ── Response Models ──────────────────────────────────────────────────


class BoardResponse(BaseModel):
    """Full board response with all widgets."""

    model_config = ConfigDict(populate_by_name=True)

    board_id: str = Field(alias="boardId")
    name: str
    description: str | None = None
    icon: str | None = None
    owner_id: str = Field(alias="ownerId")
    owner_type: OwnerType = Field(default=OwnerType.USER, alias="ownerType")
    board_type: BoardType = Field(alias="boardType")
    visibility: BoardVisibility = Field(default_factory=BoardVisibility)
    layout: BoardLayout
    layout_mode: LayoutMode = Field(default="grid", alias="layoutMode")
    scope: BoardScope = Field(default="standalone", alias="scope")
    entity_type_filter: EntityPanelType | None = Field(default=None, alias="entityTypeFilter")
    is_system_default: bool = Field(default=False, alias="isSystemDefault")
    widgets: list[WidgetInstance] = Field(default_factory=list)
    settings: BoardSettings = Field(default_factory=BoardSettings)
    tags: list[str] = Field(default_factory=list)
    is_home: bool = Field(default=False, alias="isHome")
    version: int = Field(default=1)
    cloned_from: str | None = Field(default=None, alias="clonedFrom")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    archived_at: datetime | None = Field(default=None, alias="archivedAt")


class BoardSummary(BaseModel):
    """Abbreviated board response for list endpoints (no widgets array)."""

    model_config = ConfigDict(populate_by_name=True)

    board_id: str = Field(alias="boardId")
    name: str
    description: str | None = None
    icon: str | None = None
    owner_id: str = Field(alias="ownerId")
    owner_type: OwnerType = Field(default=OwnerType.USER, alias="ownerType")
    board_type: BoardType = Field(alias="boardType")
    visibility: BoardVisibility = Field(default_factory=BoardVisibility)
    layout_mode: LayoutMode = Field(default="grid", alias="layoutMode")
    scope: BoardScope = Field(default="standalone", alias="scope")
    entity_type_filter: EntityPanelType | None = Field(default=None, alias="entityTypeFilter")
    widget_count: int = Field(default=0, alias="widgetCount")
    tags: list[str] = Field(default_factory=list)
    is_home: bool = Field(default=False, alias="isHome")
    version: int = Field(default=1)
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


# ── Request Models ───────────────────────────────────────────────────


class AddWidgetRequest(WidgetPlacementMixin):
    """Add a widget to a board."""

    model_config = ConfigDict(populate_by_name=True)

    widget_type: str = Field(alias="widgetType", description="Widget type identifier from the registry")
    config: dict[str, Any] = Field(default_factory=dict, description="Widget-specific configuration")
    data_binding: DataBinding | None = Field(default=None, alias="dataBinding")


# UpdateWidgetRequest does NOT inherit WidgetPlacementMixin because the mixin's
# `ensure_widget_placement` model validator requires at least one of position/placements/column
# to be set — a constraint that makes sense for create but not for partial updates where all
# fields are optional. Placement fields (including freeform_position) are duplicated here.
class UpdateWidgetRequest(BaseModel):
    """Update a widget on a board."""

    model_config = ConfigDict(populate_by_name=True)

    position: WidgetPosition | None = Field(default=None, description="Updated grid position and size")
    placements: dict[str, WidgetPosition] | None = Field(default=None)
    column: str | None = None
    order: int | None = None
    freeform_position: FreeformPosition | None = Field(
        default=None,
        alias="freeformPosition",
        description="Updated pixel coordinates for freeform layout mode",
    )
    config: dict[str, Any] | None = Field(default=None, description="Updated widget configuration")
    data_binding: DataBinding | None = Field(default=None, alias="dataBinding")

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_widget(cls, value: Any) -> Any:
        return _normalize_widget_placement(value)


class CreateBoardRequest(BaseModel):
    """Create a new dashboard board."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(min_length=1, max_length=128, description="Board name")
    description: str | None = Field(default=None, max_length=2048)
    icon: str | None = Field(default=None, max_length=64)
    board_type: BoardType = Field(default=BoardType.USER, alias="boardType")
    visibility: BoardVisibility = Field(default_factory=BoardVisibility)
    layout: BoardLayout = Field(default_factory=BoardLayout)
    layout_mode: LayoutMode = Field(default="grid", alias="layoutMode")
    scope: BoardScope = Field(default="standalone", alias="scope")
    entity_type_filter: EntityPanelType | None = Field(default=None, alias="entityTypeFilter")
    widgets: list[AddWidgetRequest] = Field(default_factory=list, description="Initial widgets")
    settings: BoardSettings = Field(default_factory=BoardSettings)
    tags: list[str] = Field(default_factory=list)
    is_home: bool = Field(default=False, alias="isHome")

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        """Validate tag length and format."""
        for tag in v:
            if len(tag) > 64:
                raise ValueError(f"Tag '{tag[:20]}...' exceeds maximum length of 64 characters")
        return v

    @model_validator(mode="after")
    def validate_entity_panel_requires_filter(self) -> "CreateBoardRequest":
        """entity-panel scope requires entityTypeFilter to be set."""
        if self.scope == "entity-panel" and self.entity_type_filter is None:
            raise ValueError(
                "entityTypeFilter is required when scope is 'entity-panel'"
            )
        return self


class UpdateBoardRequest(BaseModel):
    """Update a dashboard board (PUT - full replacement of mutable fields)."""

    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2048)
    icon: str | None = Field(default=None, max_length=64)
    board_type: BoardType | None = Field(default=None, alias="boardType")
    visibility: BoardVisibility | None = None
    layout: BoardLayout | None = None
    layout_mode: LayoutMode | None = Field(default=None, alias="layoutMode")
    widgets: list[WidgetInstance] | None = None
    settings: BoardSettings | None = None
    tags: list[str] | None = None
    is_home: bool | None = Field(default=None, alias="isHome")

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str] | None) -> list[str] | None:
        """Validate tag length and format."""
        if v is not None:
            for tag in v:
                if len(tag) > 64:
                    raise ValueError(f"Tag '{tag[:20]}...' exceeds maximum length of 64 characters")
        return v


class CloneBoardRequest(BaseModel):
    """Clone an existing board."""

    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(default=None, min_length=1, max_length=128, description="Name for the cloned board")
    variables: dict[str, Any] | None = Field(
        default=None,
        description="Template variables for parameterized cloning (used when source is a template)",
    )


# ── PATCH Operations ────────────────────────────────────────────────


_ALLOWED_META_KEYS: frozenset[str] = frozenset({"layoutMode"})


class PatchUpdateSettings(BaseModel):
    """PATCH op: update board settings or board-level meta fields.

    Two usage modes (may be combined in a single operation):
    - ``settings``: replace the full ``BoardSettings`` object (existing behaviour).
    - ``value``: partial update of board-level meta fields from the allowed set
      (currently: ``layoutMode``).  Immutable fields (``scope``,
      ``entityTypeFilter``) are silently ignored if present in ``value``.
    """

    model_config = ConfigDict(populate_by_name=True)

    op: Literal["update-settings"]
    settings: BoardSettings | None = None
    value: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Board-level meta updates (e.g., layoutMode). Only keys in _ALLOWED_META_KEYS "
            "are applied; unknown keys silently ignored. Values validated in service layer."
        ),
    )


class PatchUpdateLayout(BaseModel):
    """PATCH op: update layout positions only."""

    model_config = ConfigDict(populate_by_name=True)

    op: Literal["update-layout"]
    layout: BoardLayout


class PatchAddWidget(BaseModel):
    """PATCH op: add a widget instance."""

    model_config = ConfigDict(populate_by_name=True)

    op: Literal["add-widget"]
    widget: AddWidgetRequest


class PatchUpdateWidget(BaseModel):
    """PATCH op: update a single widget config/binding/position."""

    model_config = ConfigDict(populate_by_name=True)

    op: Literal["update-widget"]
    instance_id: str = Field(alias="instanceId")
    changes: UpdateWidgetRequest


class PatchRemoveWidget(BaseModel):
    """PATCH op: remove a widget instance."""

    model_config = ConfigDict(populate_by_name=True)

    op: Literal["remove-widget"]
    instance_id: str = Field(alias="instanceId")


class PatchReorderWidgets(BaseModel):
    """PATCH op: reorder widgets within columns."""

    model_config = ConfigDict(populate_by_name=True)

    op: Literal["reorder-widgets"]
    order: list[str] = Field(description="Ordered list of widget instanceIds")


PatchBoardOperation = Annotated[
    PatchUpdateSettings
    | PatchUpdateLayout
    | PatchAddWidget
    | PatchUpdateWidget
    | PatchRemoveWidget
    | PatchReorderWidgets,
    Field(discriminator="op"),
]


class PatchBoardRequest(BaseModel):
    """PATCH /dashboards/{boardId} body."""

    model_config = ConfigDict(populate_by_name=True)

    operations: list[PatchBoardOperation] = Field(min_length=1, max_length=50)


# ── List Query Parameters ────────────────────────────────────────────


class WidgetSize(BaseModel):
    """Widget size constraints."""

    model_config = ConfigDict(populate_by_name=True)

    w: int = Field(ge=1, le=12)
    h: int = Field(ge=1, le=12)


class WidgetCategoryInfo(BaseModel):
    """Category summary entry in the widget registry response."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    count: int


class WidgetConfigOption(BaseModel):
    """Selectable option for a widget config field (enum type)."""

    model_config = ConfigDict(populate_by_name=True)

    label: str
    value: str


class WidgetConfigField(BaseModel):
    """Configurable setting descriptor exposed by the widget registry.

    Aligns with the ``FieldSchema`` shape emitted by ``widget_registry.py``
    per Dashboard Technical Specification §5 (WidgetConfigurator).
    """

    model_config = ConfigDict(populate_by_name=True)

    key: str
    label: str
    type: Literal["string", "number", "boolean", "enum", "color", "entity-ref"]
    default: Any = None
    description: str | None = None
    options: list[WidgetConfigOption] | None = None
    min: float | None = None
    max: float | None = None
    step: float | None = None
    entity_type: Literal["node", "service", "network", "group"] | None = Field(
        default=None, alias="entityType"
    )
    required: bool = False


class WidgetCapabilities(BaseModel):
    """Capabilities surfaced for a widget type."""

    model_config = ConfigDict(populate_by_name=True)

    configurable: bool = False
    supports_visibility_toggle: bool = Field(default=True, alias="supportsVisibilityToggle")
    repeatable: bool = True


class WidgetPermissions(BaseModel):
    """Role-based permission contract for a widget per spec §4.1."""

    model_config = ConfigDict(populate_by_name=True)

    view: list[str] = Field(
        default_factory=lambda: ["admin", "operator", "viewer", "family"],
        description="Roles that may view this widget",
    )
    interact: list[str] = Field(
        default_factory=list,
        description="Roles that may interact (execute commands, toggle controls)",
    )


class WidgetTypeDefinition(BaseModel):
    """A widget type available in the registry per spec §4.3."""

    model_config = ConfigDict(populate_by_name=True)

    widget_type: str = Field(alias="widgetType")
    display_name: str = Field(alias="displayName")
    description: str = ""
    category: str
    icon: str = "square"
    source: str = "hydra"
    version: str = Field(default="1.0.0", description="Semver of the widget type contract")
    supported_data_shapes: list[str] = Field(
        default_factory=list,
        alias="supportedDataShapes",
        description="Data shapes this widget accepts (e.g., 'scalar', 'time-series')",
    )
    tags: list[str] = Field(default_factory=list, description="Free-form discovery tags")
    permissions: WidgetPermissions = Field(default_factory=WidgetPermissions)
    default_size: WidgetSize = Field(alias="defaultSize")
    min_size: WidgetSize = Field(alias="minSize")
    max_size: WidgetSize = Field(alias="maxSize")
    config_schema: list[WidgetConfigField] = Field(default_factory=list, alias="configSchema")
    kiosk_mode: Literal["render", "readonly", "hide"] = Field(
        default="render",
        alias="kioskMode",
        description="How this widget behaves in kiosk view. "
        "'render' = normal display; 'readonly' = controls disabled; 'hide' = excluded entirely.",
    )
    is_available: bool = Field(
        default=True,
        alias="isAvailable",
        description="False for Tier 3 widgets that require Wave 5 features (WebSocket, plugin system). "
        "These are hidden from the widget picker but remain registered for future enablement.",
    )
    capabilities: WidgetCapabilities = Field(default_factory=WidgetCapabilities)


class WidgetRegistryResponse(BaseModel):
    """Response from widget registry endpoint."""

    model_config = ConfigDict(populate_by_name=True)

    widgets: list[WidgetTypeDefinition]
    categories: list[WidgetCategoryInfo]
    total: int


class DashboardListParams(BaseModel):
    """Query parameters for listing dashboards."""

    model_config = ConfigDict(populate_by_name=True)

    board_type: BoardType | None = Field(default=None, alias="boardType")
    owner_id: str | None = Field(default=None, alias="ownerId")
    visibility: VisibilityScope | None = Field(default=None, description="Filter by visibility scope")
    tags: list[str] | None = None
    search: str | None = Field(default=None, max_length=256)
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    sort_by: Literal["name", "createdAt", "updatedAt"] = Field(default="updatedAt", alias="sortBy")
    sort_order: Literal["asc", "desc"] = Field(default="desc", alias="sortOrder")


# ── Portable Widget (shared by templates + export) ──────────────────


class PortableWidgetInstance(WidgetPlacementMixin):
    """Widget instance for templates and export (instanceId is optional)."""

    model_config = ConfigDict(populate_by_name=True)

    instance_id: str | None = Field(default=None, alias="instanceId")
    widget_type: str = Field(alias="widgetType")
    config: dict[str, Any] = Field(default_factory=dict)
    data_binding: DataBinding | None = Field(default=None, alias="dataBinding")


# ── Template Models ─────────────────────────────────────────────────


class TemplateVariableDefinition(BaseModel):
    """Schema for a single template variable that users fill in on clone/instantiate."""

    model_config = ConfigDict(populate_by_name=True)

    type: str = Field(
        description="Variable input type (e.g., 'text', 'number', 'node-selector', 'network-selector', 'select')",
    )
    label: str = Field(min_length=1, max_length=128, description="Human-readable label shown in the UI")
    description: str | None = Field(default=None, max_length=512)
    default: Any | None = Field(default=None, description="Default value if user doesn't provide one")
    required: bool = Field(default=False, description="Whether the variable must be provided")
    options: list[str] | None = Field(
        default=None,
        description="Allowed values for 'select' type variables",
    )


MAX_TEMPLATE_VARIABLES = 10


class SaveAsTemplateRequest(BaseModel):
    """Save a board as a reusable template."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(min_length=1, max_length=128, description="Template name")
    description: str | None = Field(default=None, max_length=2048)
    category: TemplateCategory = Field(
        default=TemplateCategory.GENERAL,
        description="Template category for grouping",
    )
    target_roles: list[str] = Field(
        default_factory=lambda: ["admin", "operator", "viewer", "family"],
        alias="targetRoles",
        description="Roles this template is applicable to",
    )
    required_plugins: list[str] = Field(
        default_factory=list,
        alias="requiredPlugins",
        description="Plugins that must be enabled for this template to work",
    )
    optional_plugins: list[str] = Field(
        default_factory=list,
        alias="optionalPlugins",
        description="Plugins that enhance this template but are not required",
    )
    variables: dict[str, TemplateVariableDefinition] | None = Field(
        default=None,
        description="Template variable definitions for parameterized cloning",
    )
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        for tag in v:
            if len(tag) > 64:
                raise ValueError(f"Tag '{tag[:20]}...' exceeds maximum length of 64 characters")
        return v

    @field_validator("variables")
    @classmethod
    def validate_variables_count(
        cls, v: dict[str, TemplateVariableDefinition] | None,
    ) -> dict[str, TemplateVariableDefinition] | None:
        if v is not None and len(v) > MAX_TEMPLATE_VARIABLES:
            raise ValueError(
                f"Templates may define at most {MAX_TEMPLATE_VARIABLES} variables, got {len(v)}"
            )
        return v

    @field_validator("target_roles")
    @classmethod
    def validate_target_roles(cls, v: list[str]) -> list[str]:
        valid_roles = {"admin", "operator", "viewer", "family"}
        for role in v:
            if role not in valid_roles:
                raise ValueError(f"Invalid target role '{role}'; allowed: {sorted(valid_roles)}")
        return v


class TemplateResponse(BaseModel):
    """Dashboard template response."""

    model_config = ConfigDict(populate_by_name=True)

    template_id: str = Field(alias="templateId")
    name: str
    description: str | None = None
    category: TemplateCategory = Field(default=TemplateCategory.GENERAL)
    target_roles: list[str] = Field(
        default_factory=lambda: ["admin", "operator", "viewer", "family"],
        alias="targetRoles",
    )
    required_plugins: list[str] = Field(default_factory=list, alias="requiredPlugins")
    optional_plugins: list[str] = Field(default_factory=list, alias="optionalPlugins")
    preview: str | None = Field(default=None, description="Preview image URL")
    variables: dict[str, TemplateVariableDefinition] | None = None
    source: TemplateSource = Field(default=TemplateSource.USER)
    board_type: BoardType = Field(alias="boardType")
    layout: BoardLayout
    widgets: list[PortableWidgetInstance] = Field(default_factory=list)
    settings: BoardSettings = Field(default_factory=BoardSettings)
    tags: list[str] = Field(default_factory=list)
    widget_count: int = Field(default=0, alias="widgetCount")
    created_by: str = Field(alias="createdBy")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class TemplateSummary(BaseModel):
    """Abbreviated template response for list endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    template_id: str = Field(alias="templateId")
    name: str
    description: str | None = None
    category: TemplateCategory = Field(default=TemplateCategory.GENERAL)
    target_roles: list[str] = Field(
        default_factory=lambda: ["admin", "operator", "viewer", "family"],
        alias="targetRoles",
    )
    required_plugins: list[str] = Field(default_factory=list, alias="requiredPlugins")
    optional_plugins: list[str] = Field(default_factory=list, alias="optionalPlugins")
    preview: str | None = Field(default=None)
    source: TemplateSource = Field(default=TemplateSource.USER)
    board_type: BoardType = Field(alias="boardType")
    tags: list[str] = Field(default_factory=list)
    widget_count: int = Field(default=0, alias="widgetCount")
    created_by: str = Field(alias="createdBy")
    created_at: datetime = Field(alias="createdAt")


class InstantiateTemplateRequest(BaseModel):
    """Create a board from a template."""

    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(default=None, min_length=1, max_length=128, description="Name for the new board")
    variables: dict[str, Any] | None = Field(
        default=None,
        description="Template variables for parameterized instantiation",
    )


# ── Version History Models ──────────────────────────────────────────


class VersionSnapshotResponse(BaseModel):
    """A single board version snapshot."""

    model_config = ConfigDict(populate_by_name=True)

    board_id: str = Field(alias="boardId")
    version: int
    snapshot: dict[str, Any] = Field(description="Complete board definition at this version")
    saved_by: str = Field(alias="savedBy")
    saved_at: datetime = Field(alias="savedAt")
    change_description: str | None = Field(default=None, alias="changeDescription")


class VersionSummary(BaseModel):
    """Abbreviated version entry for list endpoints (no snapshot payload)."""

    model_config = ConfigDict(populate_by_name=True)

    board_id: str = Field(alias="boardId")
    version: int
    saved_by: str = Field(alias="savedBy")
    saved_at: datetime = Field(alias="savedAt")
    change_description: str | None = Field(default=None, alias="changeDescription")
    widget_count: int = Field(default=0, alias="widgetCount")


# ── Sharing Models ──────────────────────────────────────────────────


class ShareBoardRequest(BaseModel):
    """Update sharing settings for a board."""

    model_config = ConfigDict(populate_by_name=True)

    scope: VisibilityScope = Field(description="Board visibility scope")
    shared_with: SharedWith = Field(
        default_factory=SharedWith,
        alias="sharedWith",
        description="Roles and users the board is shared with",
    )


class ShareBoardResponse(BaseModel):
    """Response after updating sharing settings."""

    model_config = ConfigDict(populate_by_name=True)

    board_id: str = Field(alias="boardId")
    scope: VisibilityScope
    shared_with: SharedWith = Field(alias="sharedWith")


# ── Export/Import Models ────────────────────────────────────────────


class BoardExport(BaseModel):
    """Exported board definition for import/export round-tripping."""

    model_config = ConfigDict(populate_by_name=True)

    export_version: int = Field(default=1, alias="exportVersion")
    name: str
    description: str | None = None
    icon: str | None = None
    board_type: BoardType = Field(alias="boardType")
    layout: BoardLayout
    widgets: list[PortableWidgetInstance] = Field(default_factory=list)
    settings: BoardSettings = Field(default_factory=BoardSettings)
    tags: list[str] = Field(default_factory=list)


class ImportValidationIssue(BaseModel):
    """A single validation issue raised during import."""

    model_config = ConfigDict(populate_by_name=True)

    level: Literal["warning", "error"]
    code: str
    message: str
    widget_index: int | None = Field(default=None, alias="widgetIndex")


class ImportBoardRequest(BaseModel):
    """Import a board from an exported definition."""

    model_config = ConfigDict(populate_by_name=True)

    board: BoardExport = Field(description="Exported board definition to import")
    name: str | None = Field(default=None, min_length=1, max_length=128, description="Override name for imported board")


class ImportBoardResponse(BaseModel):
    """Result of an import with any validation warnings surfaced."""

    model_config = ConfigDict(populate_by_name=True)

    board: BoardResponse
    warnings: list[ImportValidationIssue] = Field(default_factory=list)


# ── Extended Sharing Models ────────────────────────────────────────


class ShareTarget(BaseModel):
    """Target audience for board sharing — roles and/or specific users."""

    model_config = ConfigDict(populate_by_name=True)

    roles: list[str] = Field(default_factory=list, alias="roles")
    users: list[str] = Field(default_factory=list, alias="users")


class ShareInfo(BaseModel):
    """Full sharing information for a board."""

    model_config = ConfigDict(populate_by_name=True)

    shared_with: ShareTarget = Field(alias="sharedWith")
    shared_at: datetime = Field(alias="sharedAt")
    shared_by: str = Field(alias="sharedBy")


class TemplateListParams(BaseModel):
    """Query parameters for listing dashboard templates."""

    model_config = ConfigDict(populate_by_name=True)

    category: TemplateCategory | None = None
    source: TemplateSource | None = None
    search: str | None = Field(default=None, max_length=256)
    tags: list[str] | None = None
    sort_by: Literal["name", "createdAt", "updatedAt"] = Field(default="createdAt", alias="sortBy")
    sort_order: Literal["asc", "desc"] = Field(default="desc", alias="sortOrder")
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


# ── Kiosk Token Models ─────────────────────────────────────────────


class CreateKioskTokenRequest(BaseModel):
    """Request body for creating a new kiosk token."""

    model_config = ConfigDict(populate_by_name=True)

    label: str = Field(min_length=1, max_length=80, description="Human-readable label for the token")
    ttl_hours: int | None = Field(
        default=168,
        ge=1,
        le=8760,
        alias="ttlHours",
        description="Token lifetime in hours (1–8760). Null means the token never expires. Default: 168 (7 days).",
    )


class KioskTokenSummary(BaseModel):
    """Summary of a kiosk token (no raw token or hash)."""

    model_config = ConfigDict(populate_by_name=True)

    token_id: str = Field(alias="tokenId")
    board_id: str = Field(alias="boardId")
    label: str
    created_by: str = Field(alias="createdBy")
    created_at: datetime = Field(alias="createdAt")
    expires_at: datetime | None = Field(default=None, alias="expiresAt")
    revoked_at: datetime | None = Field(default=None, alias="revokedAt")
    last_used_at: datetime | None = Field(default=None, alias="lastUsedAt")


class KioskTokenCreated(KioskTokenSummary):
    """Response for token creation — includes raw token (shown exactly once)."""

    token: str = Field(description="Raw bearer token — store securely; not retrievable again")


class KioskTokenDocument(BaseModel):
    """Internal representation of a kiosk_tokens MongoDB document."""

    model_config = ConfigDict(populate_by_name=True)

    token_id: str = Field(alias="tokenId")
    board_id: str = Field(alias="boardId")
    token_hash: str = Field(alias="tokenHash")
    label: str
    created_by: str = Field(alias="createdBy")
    created_at: datetime = Field(alias="createdAt")
    expires_at: datetime | None = Field(default=None, alias="expiresAt")
    revoked_at: datetime | None = Field(default=None, alias="revokedAt")
    last_used_at: datetime | None = Field(default=None, alias="lastUsedAt")


__all__ = [
    "_BREAKPOINT_ORDER",
    "AddWidgetRequest",
    "BoardColumnDefinition",
    "BoardExport",
    "BoardLayout",
    "BoardResponse",
    "BoardScope",
    "BoardSettings",
    "BoardSummary",
    "BoardType",
    "BoardVisibility",
    "CloneBoardRequest",
    "CreateKioskTokenRequest",
    "KioskTokenCreated",
    "KioskTokenDocument",
    "KioskTokenSummary",
    "ColumnLayoutConfig",
    "CreateBoardRequest",
    "DashboardListParams",
    "DataBinding",
    "DataBindingFallback",
    "DEFAULT_GRID_BREAKPOINTS",
    "EntityPanelType",
    "FreeformPosition",
    "GridLayoutConfig",
    "ImportBoardRequest",
    "ImportBoardResponse",
    "ImportValidationIssue",
    "InstantiateTemplateRequest",
    "LayoutBreakpoint",
    "LayoutMode",
    "MAX_TEMPLATE_VARIABLES",
    "OwnerType",
    "PatchAddWidget",
    "PatchBoardOperation",
    "PatchBoardRequest",
    "PatchRemoveWidget",
    "PatchReorderWidgets",
    "PatchUpdateLayout",
    "PatchUpdateSettings",
    "PatchUpdateWidget",
    "PortableWidgetInstance",
    "SaveAsTemplateRequest",
    "ShareBoardRequest",
    "ShareBoardResponse",
    "ShareInfo",
    "SharedWith",
    "ShareTarget",
    "TemplateCategory",
    "TemplateListParams",
    "TemplateResponse",
    "TemplateSource",
    "TemplateSummary",
    "TemplateVariableDefinition",
    "UpdateBoardRequest",
    "UpdateWidgetRequest",
    "VersionSnapshotResponse",
    "VersionSummary",
    "VisibilityScope",
    "WidgetCapabilities",
    "WidgetCategoryInfo",
    "WidgetConfigField",
    "WidgetConfigOption",
    "WidgetInstance",
    "WidgetPermissions",
    "WidgetPlacementMixin",
    "WidgetPosition",
    "WidgetRegistryResponse",
    "WidgetSize",
    "WidgetTypeDefinition",
]
