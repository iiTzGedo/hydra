"""Dashboard models for request/response validation."""

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class BoardType(StrEnum):
    """Board type classification."""

    HOME = "home"
    CUSTOM = "custom"
    TEMPLATE = "template"


class BoardVisibility(StrEnum):
    """Board visibility scope."""

    PRIVATE = "private"
    SHARED = "shared"
    PUBLIC = "public"


class WidgetPosition(BaseModel):
    """Widget position on the grid layout."""

    model_config = ConfigDict(populate_by_name=True)

    x: int = Field(ge=0, description="Horizontal grid position")
    y: int = Field(ge=0, description="Vertical grid position")
    w: int = Field(ge=1, le=12, description="Width in grid columns")
    h: int = Field(ge=1, le=12, description="Height in grid rows")


DEFAULT_GRID_BREAKPOINTS: dict[str, dict[str, int]] = {
    "lg": {"columns": 12, "width": 1200},
    "md": {"columns": 8, "width": 996},
    "sm": {"columns": 4, "width": 768},
}


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


class DataBinding(BaseModel):
    """Widget data binding configuration."""

    model_config = ConfigDict(populate_by_name=True)

    source: str = Field(description="Data source identifier (e.g., 'hydra::nodes')")
    query: dict[str, Any] = Field(default_factory=dict, description="Query parameters for the data source")
    refresh_interval: int | None = Field(
        default=None,
        ge=5,
        alias="refreshInterval",
        description="Refresh interval in seconds",
    )


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

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_widget(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        normalized = dict(value)
        placements = normalized.get("placements")
        position = normalized.get("position")

        if placements is None and position is not None:
            normalized["placements"] = _expand_legacy_position(position)
        elif placements is not None and position is None and isinstance(placements, dict):
            normalized["position"] = placements.get("lg") or next(iter(placements.values()), None)

        if normalized.get("column") is not None and normalized.get("order") is None:
            normalized["order"] = 0

        return normalized

    @model_validator(mode="after")
    def ensure_widget_placement(self) -> "WidgetPlacementMixin":
        if self.placements is None and self.position is not None:
            self.placements = {
                key: WidgetPosition(**placement)
                for key, placement in _expand_legacy_position(self.position.model_dump()).items()
            }
        if self.position is None and self.placements:
            self.position = self.placements.get("lg") or next(iter(self.placements.values()), None)
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


class BoardSettings(BaseModel):
    """Board-level settings."""

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


# ── Response Models ──────────────────────────────────────────────────


class BoardResponse(BaseModel):
    """Full board response with all widgets."""

    model_config = ConfigDict(populate_by_name=True)

    board_id: str = Field(alias="boardId")
    name: str
    description: str | None = None
    icon: str | None = None
    owner_id: str = Field(alias="ownerId")
    board_type: BoardType = Field(alias="boardType")
    visibility: BoardVisibility = Field(default=BoardVisibility.PRIVATE)
    layout: BoardLayout
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
    board_type: BoardType = Field(alias="boardType")
    visibility: BoardVisibility = Field(default=BoardVisibility.PRIVATE)
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


class UpdateWidgetRequest(BaseModel):
    """Update a widget on a board."""

    model_config = ConfigDict(populate_by_name=True)

    position: WidgetPosition | None = Field(default=None, description="Updated grid position and size")
    placements: dict[str, WidgetPosition] | None = Field(default=None)
    column: str | None = None
    order: int | None = None
    config: dict[str, Any] | None = Field(default=None, description="Updated widget configuration")
    data_binding: DataBinding | None = Field(default=None, alias="dataBinding")

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_widget(cls, value: Any) -> Any:
        return WidgetPlacementMixin.normalize_legacy_widget(value)


class CreateBoardRequest(BaseModel):
    """Create a new dashboard board."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(min_length=1, max_length=128, description="Board name")
    description: str | None = Field(default=None, max_length=1024)
    icon: str | None = Field(default=None, max_length=64)
    board_type: BoardType = Field(default=BoardType.CUSTOM, alias="boardType")
    visibility: BoardVisibility = Field(default=BoardVisibility.PRIVATE)
    layout: BoardLayout = Field(default_factory=BoardLayout)
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


class UpdateBoardRequest(BaseModel):
    """Update a dashboard board (PUT - full replacement of mutable fields)."""

    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=1024)
    icon: str | None = Field(default=None, max_length=64)
    board_type: BoardType | None = Field(default=None, alias="boardType")
    visibility: BoardVisibility | None = None
    layout: BoardLayout | None = None
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
    """Selectable option for a widget config field."""

    model_config = ConfigDict(populate_by_name=True)

    label: str
    value: str


class WidgetConfigField(BaseModel):
    """Configurable setting exposed by the widget registry."""

    model_config = ConfigDict(populate_by_name=True)

    key: str
    label: str
    field_type: Literal["text", "boolean", "number", "select"] = Field(alias="fieldType")
    description: str | None = None
    placeholder: str | None = None
    min_value: int | None = Field(default=None, alias="minValue")
    max_value: int | None = Field(default=None, alias="maxValue")
    options: list[WidgetConfigOption] = Field(default_factory=list)


class WidgetCapabilities(BaseModel):
    """Capabilities surfaced for a widget type."""

    model_config = ConfigDict(populate_by_name=True)

    configurable: bool = False
    supports_visibility_toggle: bool = Field(default=True, alias="supportsVisibilityToggle")
    repeatable: bool = True


class WidgetTypeDefinition(BaseModel):
    """A widget type available in the registry."""

    model_config = ConfigDict(populate_by_name=True)

    widget_type: str = Field(alias="widgetType")
    display_name: str = Field(alias="displayName")
    description: str = ""
    category: str
    icon: str = "square"
    source: str = "hydra"
    default_size: WidgetSize = Field(alias="defaultSize")
    min_size: WidgetSize = Field(alias="minSize")
    max_size: WidgetSize = Field(alias="maxSize")
    config_schema: list[WidgetConfigField] = Field(default_factory=list, alias="configSchema")
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
    visibility: BoardVisibility | None = None
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


class SaveAsTemplateRequest(BaseModel):
    """Save a board as a reusable template."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(min_length=1, max_length=128, description="Template name")
    description: str | None = Field(default=None, max_length=1024)
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        for tag in v:
            if len(tag) > 64:
                raise ValueError(f"Tag '{tag[:20]}...' exceeds maximum length of 64 characters")
        return v


class TemplateResponse(BaseModel):
    """Dashboard template response."""

    model_config = ConfigDict(populate_by_name=True)

    template_id: str = Field(alias="templateId")
    name: str
    description: str | None = None
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
    board_type: BoardType = Field(alias="boardType")
    tags: list[str] = Field(default_factory=list)
    widget_count: int = Field(default=0, alias="widgetCount")
    created_by: str = Field(alias="createdBy")
    created_at: datetime = Field(alias="createdAt")


class InstantiateTemplateRequest(BaseModel):
    """Create a board from a template."""

    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(default=None, min_length=1, max_length=128, description="Name for the new board")


# ── Sharing Models ──────────────────────────────────────────────────


class ShareBoardRequest(BaseModel):
    """Update sharing settings for a board."""

    model_config = ConfigDict(populate_by_name=True)

    visibility: BoardVisibility = Field(description="Board visibility scope")
    allowed_users: list[str] = Field(
        default_factory=list,
        alias="allowedUsers",
        description="User IDs allowed to view the board (only for shared visibility)",
    )


class ShareBoardResponse(BaseModel):
    """Response after updating sharing settings."""

    model_config = ConfigDict(populate_by_name=True)

    board_id: str = Field(alias="boardId")
    visibility: BoardVisibility
    allowed_users: list[str] = Field(default_factory=list, alias="allowedUsers")


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


class ImportBoardRequest(BaseModel):
    """Import a board from an exported definition."""

    model_config = ConfigDict(populate_by_name=True)

    board: BoardExport = Field(description="Exported board definition to import")
    name: str | None = Field(default=None, min_length=1, max_length=128, description="Override name for imported board")


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

    search: str | None = Field(default=None, max_length=256)
    tags: list[str] | None = None
    sort_by: Literal["name", "createdAt", "updatedAt"] = Field(default="createdAt", alias="sortBy")
    sort_order: Literal["asc", "desc"] = Field(default="desc", alias="sortOrder")
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
