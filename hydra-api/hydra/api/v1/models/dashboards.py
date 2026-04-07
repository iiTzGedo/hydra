"""Dashboard models for request/response validation."""

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class LayoutBreakpoint(BaseModel):
    """Responsive breakpoint definition."""

    model_config = ConfigDict(populate_by_name=True)

    columns: int = Field(ge=1, le=24)
    width: int = Field(ge=0)


class BoardLayout(BaseModel):
    """Board layout configuration."""

    model_config = ConfigDict(populate_by_name=True)

    columns: int = Field(default=12, ge=1, le=24, description="Number of grid columns")
    row_height: int = Field(default=80, ge=20, le=500, alias="rowHeight", description="Row height in pixels")
    breakpoints: dict[str, LayoutBreakpoint] = Field(
        default_factory=lambda: {
            "lg": LayoutBreakpoint(columns=12, width=1200),
            "md": LayoutBreakpoint(columns=8, width=996),
            "sm": LayoutBreakpoint(columns=4, width=768),
        },
        description="Responsive breakpoint configurations",
    )


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


class WidgetInstance(BaseModel):
    """A specific widget placement on a board."""

    model_config = ConfigDict(populate_by_name=True)

    instance_id: str = Field(alias="instanceId", description="Unique widget instance identifier")
    widget_type: str = Field(alias="widgetType", description="Widget type from the registry")
    position: WidgetPosition = Field(description="Grid position and size")
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


class AddWidgetRequest(BaseModel):
    """Add a widget to a board."""

    model_config = ConfigDict(populate_by_name=True)

    widget_type: str = Field(alias="widgetType", description="Widget type identifier from the registry")
    position: WidgetPosition = Field(description="Grid position and size")
    config: dict[str, Any] = Field(default_factory=dict, description="Widget-specific configuration")
    data_binding: DataBinding | None = Field(default=None, alias="dataBinding")


class UpdateWidgetRequest(BaseModel):
    """Update a widget on a board."""

    model_config = ConfigDict(populate_by_name=True)

    position: WidgetPosition | None = Field(default=None, description="Updated grid position and size")
    config: dict[str, Any] | None = Field(default=None, description="Updated widget configuration")
    data_binding: DataBinding | None = Field(default=None, alias="dataBinding")


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
