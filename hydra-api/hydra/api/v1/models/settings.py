"""Settings models for user and system configuration."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ThemeMode(str, Enum):
    """UI theme mode."""

    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


class LayoutMode(str, Enum):
    """List layout mode."""

    LIST = "list"
    GRID = "grid"
    COMPACT = "compact"


class SortOrder(str, Enum):
    """Sort order."""

    ASC = "asc"
    DESC = "desc"


class UISettings(BaseModel):
    """User interface settings."""

    theme: ThemeMode = Field(default=ThemeMode.SYSTEM)
    sidebar_collapsed: bool = Field(default=False, alias="sidebarCollapsed")
    animations_enabled: bool = Field(default=True, alias="animationsEnabled")

    model_config = {"populate_by_name": True}


class EntityViewSettings(BaseModel):
    """View settings for an entity list page."""

    layout: LayoutMode = Field(default=LayoutMode.LIST)
    sort_field: str = Field(default="name", alias="sortField")
    sort_order: SortOrder = Field(default=SortOrder.ASC, alias="sortOrder")
    page_size: int = Field(default=20, alias="pageSize", ge=10, le=100)
    filters: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class ViewSettings(BaseModel):
    """View settings for all entity pages."""

    nodes: EntityViewSettings = Field(default_factory=EntityViewSettings)
    services: EntityViewSettings = Field(default_factory=EntityViewSettings)
    networks: EntityViewSettings = Field(default_factory=EntityViewSettings)
    groups: EntityViewSettings = Field(default_factory=EntityViewSettings)
    topology: EntityViewSettings = Field(default_factory=EntityViewSettings)

    model_config = {"populate_by_name": True}


class NotificationSettings(BaseModel):
    """User notification preferences."""

    # Delivery channels
    email_enabled: bool = Field(default=True, alias="emailEnabled")
    browser_enabled: bool = Field(default=True, alias="browserEnabled")

    # Per-channel minimum tier (1=all through 5=critical only)
    browser_min_tier: int = Field(default=3, ge=1, le=5, alias="browserMinTier")
    email_min_tier: int = Field(default=4, ge=1, le=5, alias="emailMinTier")

    # Category toggles
    node_notifications: bool = Field(default=True, alias="nodeNotifications")
    service_notifications: bool = Field(default=True, alias="serviceNotifications")
    profile_notifications: bool = Field(default=False, alias="profileNotifications")
    security_notifications: bool = Field(default=True, alias="securityNotifications")
    system_notifications: bool = Field(default=True, alias="systemNotifications")
    command_notifications: bool = Field(default=True, alias="commandNotifications")

    # Quiet hours
    quiet_hours_enabled: bool = Field(default=False, alias="quietHoursEnabled")
    quiet_hours_start: str | None = Field(default=None, alias="quietHoursStart")
    quiet_hours_end: str | None = Field(default=None, alias="quietHoursEnd")
    quiet_hours_min_tier: int = Field(default=5, ge=1, le=5, alias="quietHoursMinTier")

    # Timezone
    timezone: str = "UTC"

    # Muting / suppression
    muted_types: list[str] = Field(default_factory=list, alias="mutedTypes")
    muted_group_keys: list[str] = Field(default_factory=list, alias="mutedGroupKeys")

    model_config = {"populate_by_name": True}


class UserSettingsUpdate(BaseModel):
    """Request to update user settings."""

    ui: UISettings | None = None
    views: ViewSettings | None = None
    notifications: NotificationSettings | None = None

    model_config = {"populate_by_name": True}


class UserSettingsResponse(BaseModel):
    """User settings response."""

    user_id: str = Field(alias="userId")
    ui: UISettings
    views: ViewSettings
    notifications: NotificationSettings
    updated_at: datetime = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}


class SmtpSettings(BaseModel):
    """SMTP email settings."""

    enabled: bool = Field(default=False)
    host: str | None = None
    port: int = Field(default=587)
    username: str | None = None
    from_address: str | None = Field(default=None, alias="fromAddress")
    from_name: str = Field(default="Hydra", alias="fromName")
    use_tls: bool = Field(default=True, alias="useTls")

    model_config = {"populate_by_name": True}


class ObjectStorageSettings(BaseModel):
    """Object storage settings for agent binaries."""

    enabled: bool = Field(default=False)
    endpoint: str | None = None
    bucket: str = Field(default="hydra-bucket")
    region: str = Field(default="garage")

    model_config = {"populate_by_name": True}


class DefaultSettings(BaseModel):
    """Default settings for new entities."""

    node_status: str = Field(default="active", alias="nodeStatus")
    profile_retention_days: int = Field(default=90, alias="profileRetentionDays")
    session_timeout_minutes: int = Field(default=60, alias="sessionTimeoutMinutes")

    model_config = {"populate_by_name": True}


class SystemSettingsUpdate(BaseModel):
    """Request to update system settings (admin only)."""

    smtp: SmtpSettings | None = None
    object_storage: ObjectStorageSettings | None = Field(default=None, alias="objectStorage")
    defaults: DefaultSettings | None = None

    model_config = {"populate_by_name": True}


class SystemSettingsResponse(BaseModel):
    """System settings response."""

    smtp: SmtpSettings
    object_storage: ObjectStorageSettings = Field(alias="objectStorage")
    defaults: DefaultSettings
    updated_at: datetime = Field(alias="updatedAt")
    updated_by: str | None = Field(default=None, alias="updatedBy")

    model_config = {"populate_by_name": True}
