"""Notification system models, enums, and classification rules."""


from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class NotificationType(StrEnum):
    """All notification event types, grouped by tier."""

    # RED (Tier 5) - Critical
    AGENT_PROFILE_FAILED = "agent_profile_failed"
    AGENT_REGISTRATION_FAILED = "agent_registration_failed"
    NODE_OFFLINE = "node_offline"
    SERVICE_CRASHED = "service_crashed"
    IOT_DEVICE_UNREACHABLE = "iot_device_unreachable"
    API_INTERNAL_ERROR = "api_internal_error"
    DATABASE_CONNECTION_FAILED = "database_connection_failed"
    MCP_TOOL_WRITE_FAILED = "mcp_tool_write_failed"
    COMMAND_EXECUTION_FAILED = "command_execution_failed"
    COMMAND_EXECUTION_TIMEOUT = "command_execution_timeout"
    AUTH_BRUTE_FORCE_DETECTED = "auth_brute_force_detected"
    WEBSOCKET_FAILURE = "websocket_failure"
    LLM_PROVIDER_FAILURE = "llm_provider_failure"

    # ORANGE (Tier 4) - High
    STORAGE_CRITICAL = "storage_critical"
    MEMORY_CRITICAL = "memory_critical"
    NODE_HEALTH_DEGRADED = "node_health_degraded"
    PROFILE_MAJOR_CHANGE = "profile_major_change"
    TOKEN_EXPIRING = "token_expiring"
    API_KEY_EXPIRING = "api_key_expiring"
    TOPOLOGY_GENERATION_FAILED = "topology_generation_failed"
    SERVICE_INSTABILITY = "service_instability"
    AGENT_VERSION_OUTDATED = "agent_version_outdated"
    MCP_AUTH_DENIED = "mcp_auth_denied"

    # YELLOW (Tier 3) - Warning
    STORAGE_WARNING = "storage_warning"
    NODE_PROFILE_STALE = "node_profile_stale"
    SERVICE_STATE_CHANGED = "service_state_changed"
    NETWORK_CONFIG_CHANGED = "network_config_changed"
    UNKNOWN_SERVICE_DISCOVERED = "unknown_service_discovered"
    CONFIG_FILE_CHANGED = "config_file_changed"
    GROUP_MEMBERSHIP_CHANGED = "group_membership_changed"
    PASSWORD_RESET_REQUESTED = "password_reset_requested"
    USER_PENDING_APPROVAL = "user_pending_approval"

    # GREEN (Tier 2) - System
    AGENT_PROFILE_SUBMITTED = "agent_profile_submitted"
    NODE_REGISTERED = "node_registered"
    SERVICE_DISCOVERED = "service_discovered"
    NETWORK_DISCOVERED = "network_discovered"
    TOPOLOGY_REGENERATED = "topology_regenerated"
    HEALTH_CHECK_PASSED = "health_check_passed"
    MCP_WRITE_SUCCEEDED = "mcp_write_succeeded"
    COMMAND_EXECUTION_SUCCEEDED = "command_execution_succeeded"
    AGENT_UPGRADED = "agent_upgraded"

    # BLUE (Tier 1) - User
    USER_LOGIN_NEW_DEVICE = "user_login_new_device"
    USER_SETTINGS_UPDATED = "user_settings_updated"
    CHAT_PROJECT_CREATED = "chat_project_created"
    REGISTRATION_TOKEN_CREATED = "registration_token_created"
    API_KEY_CREATED = "api_key_created"
    API_KEY_REVOKED = "api_key_revoked"
    ROLE_ELEVATION_GRANTED = "role_elevation_granted"
    ROLE_ELEVATION_REVOKED = "role_elevation_revoked"
    SUB_ACCOUNT_LINKED = "sub_account_linked"
    PASSWORD_CHANGED = "password_changed"


class TierLabel(StrEnum):
    """Human-readable tier labels."""

    LOW_USER = "low_user"
    LOW_SYSTEM = "low_system"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationStatus(StrEnum):
    """Notification lifecycle status."""

    ACTIVE = "active"
    RESOLVED = "resolved"
    EXPIRED = "expired"


class SourceComponent(StrEnum):
    """Source component identifiers."""

    HYDRA_API = "hydra-api"
    HYDRA_AGENT = "hydra-agent"
    HYDRA_MCP = "hydra-mcp"
    HYDRA_WEB = "hydra-web"
    SYSTEM = "system"


class ActorType(StrEnum):
    """Actor type identifiers."""

    SYSTEM = "system"
    USER = "user"
    AGENT = "agent"


# ---------------------------------------------------------------------------
# Classification Maps
# ---------------------------------------------------------------------------

TIER_MAP: dict[NotificationType, int] = {
    # Tier 5 - Critical (RED)
    NotificationType.AGENT_PROFILE_FAILED: 5,
    NotificationType.AGENT_REGISTRATION_FAILED: 5,
    NotificationType.NODE_OFFLINE: 5,
    NotificationType.SERVICE_CRASHED: 5,
    NotificationType.IOT_DEVICE_UNREACHABLE: 5,
    NotificationType.API_INTERNAL_ERROR: 5,
    NotificationType.DATABASE_CONNECTION_FAILED: 5,
    NotificationType.MCP_TOOL_WRITE_FAILED: 5,
    NotificationType.COMMAND_EXECUTION_FAILED: 5,
    NotificationType.COMMAND_EXECUTION_TIMEOUT: 5,
    NotificationType.AUTH_BRUTE_FORCE_DETECTED: 5,
    NotificationType.WEBSOCKET_FAILURE: 5,
    NotificationType.LLM_PROVIDER_FAILURE: 5,
    # Tier 4 - High (ORANGE)
    NotificationType.STORAGE_CRITICAL: 4,
    NotificationType.MEMORY_CRITICAL: 4,
    NotificationType.NODE_HEALTH_DEGRADED: 4,
    NotificationType.PROFILE_MAJOR_CHANGE: 4,
    NotificationType.TOKEN_EXPIRING: 4,
    NotificationType.API_KEY_EXPIRING: 4,
    NotificationType.TOPOLOGY_GENERATION_FAILED: 4,
    NotificationType.SERVICE_INSTABILITY: 4,
    NotificationType.AGENT_VERSION_OUTDATED: 4,
    NotificationType.MCP_AUTH_DENIED: 4,
    # Tier 3 - Warning (YELLOW)
    NotificationType.STORAGE_WARNING: 3,
    NotificationType.NODE_PROFILE_STALE: 3,
    NotificationType.SERVICE_STATE_CHANGED: 3,
    NotificationType.NETWORK_CONFIG_CHANGED: 3,
    NotificationType.UNKNOWN_SERVICE_DISCOVERED: 3,
    NotificationType.CONFIG_FILE_CHANGED: 3,
    NotificationType.GROUP_MEMBERSHIP_CHANGED: 3,
    NotificationType.PASSWORD_RESET_REQUESTED: 3,
    NotificationType.USER_PENDING_APPROVAL: 3,
    # Tier 2 - System (GREEN)
    NotificationType.AGENT_PROFILE_SUBMITTED: 2,
    NotificationType.NODE_REGISTERED: 2,
    NotificationType.SERVICE_DISCOVERED: 2,
    NotificationType.NETWORK_DISCOVERED: 2,
    NotificationType.TOPOLOGY_REGENERATED: 2,
    NotificationType.HEALTH_CHECK_PASSED: 2,
    NotificationType.MCP_WRITE_SUCCEEDED: 2,
    NotificationType.COMMAND_EXECUTION_SUCCEEDED: 2,
    NotificationType.AGENT_UPGRADED: 2,
    # Tier 1 - User (BLUE)
    NotificationType.USER_LOGIN_NEW_DEVICE: 1,
    NotificationType.USER_SETTINGS_UPDATED: 1,
    NotificationType.CHAT_PROJECT_CREATED: 1,
    NotificationType.REGISTRATION_TOKEN_CREATED: 1,
    NotificationType.API_KEY_CREATED: 1,
    NotificationType.API_KEY_REVOKED: 1,
    NotificationType.ROLE_ELEVATION_GRANTED: 1,
    NotificationType.ROLE_ELEVATION_REVOKED: 1,
    NotificationType.SUB_ACCOUNT_LINKED: 1,
    NotificationType.PASSWORD_CHANGED: 1,
}

TIER_LABELS: dict[int, TierLabel] = {
    1: TierLabel.LOW_USER,
    2: TierLabel.LOW_SYSTEM,
    3: TierLabel.WARNING,
    4: TierLabel.HIGH,
    5: TierLabel.CRITICAL,
}

# TTL: how long until auto-expiry (None = never auto-expire)
TTL_MAP: dict[int, timedelta | None] = {
    1: timedelta(days=7),
    2: timedelta(days=7),
    3: timedelta(days=30),
    4: None,
    5: None,
}

# Resolved notification retention before cleanup
RESOLVED_RETENTION = timedelta(days=90)

# Default deduplication window
DEDUP_WINDOW = timedelta(minutes=5)

# Escalation threshold: occurrenceCount >= this triggers tier escalation
ESCALATION_THRESHOLD = 3

# Auto-resolution pairs: resolving_type -> list of types it resolves
AUTO_RESOLVE_MAP: dict[NotificationType, list[NotificationType]] = {
    NotificationType.NODE_REGISTERED: [NotificationType.NODE_OFFLINE],
    NotificationType.AGENT_PROFILE_SUBMITTED: [
        NotificationType.NODE_OFFLINE,
        NotificationType.NODE_PROFILE_STALE,
        NotificationType.AGENT_PROFILE_FAILED,
    ],
    NotificationType.SERVICE_DISCOVERED: [NotificationType.SERVICE_CRASHED],
    NotificationType.HEALTH_CHECK_PASSED: [
        NotificationType.DATABASE_CONNECTION_FAILED,
    ],
    NotificationType.COMMAND_EXECUTION_SUCCEEDED: [
        NotificationType.COMMAND_EXECUTION_FAILED,
        NotificationType.COMMAND_EXECUTION_TIMEOUT,
    ],
}

# Default target roles per tier (who sees these notifications)
DEFAULT_TARGET_ROLES: dict[int, list[str]] = {
    1: ["admin", "operator", "viewer", "family"],  # user events visible to most
    2: ["admin", "operator"],  # system events for ops
    3: ["admin", "operator"],  # warnings for ops
    4: ["admin", "operator"],  # high severity for ops
    5: ["admin", "operator"],  # critical for ops
}

# Notification channel name for Redis pub/sub
NOTIFICATION_CHANNEL = "hydra:notifications"


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------


class NotificationSource(BaseModel):
    """Source of a notification event."""

    model_config = ConfigDict(populate_by_name=True)

    component: SourceComponent
    service: str
    node_id: str | None = Field(default=None, alias="nodeId")
    service_id: str | None = Field(default=None, alias="serviceId")


class NotificationLink(BaseModel):
    """Deep-link to a related entity in the UI."""

    model_config = ConfigDict(populate_by_name=True)

    label: str
    entity_type: str = Field(alias="entityType")
    entity_id: str = Field(alias="entityId")
    href: str


class NotificationActor(BaseModel):
    """Who or what triggered the notification."""

    model_config = ConfigDict(populate_by_name=True)

    type: ActorType
    id: str
    ip: str | None = None
    user_agent: str | None = Field(default=None, alias="userAgent")


class NotificationEvent(BaseModel):
    """Event metadata for deduplication and escalation tracking."""

    model_config = ConfigDict(populate_by_name=True)

    first_seen_at: datetime = Field(alias="firstSeenAt")
    last_seen_at: datetime = Field(alias="lastSeenAt")
    occurrence_count: int = Field(default=1, alias="occurrenceCount")


class NotificationResponse(BaseModel):
    """Full notification response returned by the API."""

    model_config = ConfigDict(populate_by_name=True)

    notification_id: str = Field(alias="notificationId")
    type: NotificationType
    tier: int
    tier_label: str = Field(alias="tierLabel")
    source: NotificationSource
    title: str
    message: str
    details: dict[str, Any] | None = None
    links: list[NotificationLink] | None = None
    actor: NotificationActor | None = None
    event: NotificationEvent | None = None
    target_user_id: str | None = Field(default=None, alias="targetUserId")
    target_roles: list[str] = Field(default_factory=list, alias="targetRoles")
    group_key: str = Field(alias="groupKey")
    correlation_id: str | None = Field(default=None, alias="correlationId")
    audit_entry_id: str | None = Field(default=None, alias="auditEntryId")
    status: NotificationStatus
    read_at: datetime | None = Field(default=None, alias="readAt")
    created_at: datetime = Field(alias="createdAt")
    expires_at: datetime | None = Field(default=None, alias="expiresAt")
    acknowledged_at: datetime | None = Field(default=None, alias="acknowledgedAt")
    acknowledged_by: str | None = Field(default=None, alias="acknowledgedBy")
    resolved_at: datetime | None = Field(default=None, alias="resolvedAt")
    resolved_by: str | None = Field(default=None, alias="resolvedBy")


class NotificationStatsResponse(BaseModel):
    """Aggregated notification statistics."""

    model_config = ConfigDict(populate_by_name=True)

    total: int
    unread: int
    needs_attention: int = Field(default=0, alias="needsAttention")
    acknowledged_pending: int = Field(default=0, alias="acknowledgedPending")
    by_tier: dict[str, int] = Field(alias="byTier")
    by_status: dict[str, int] = Field(alias="byStatus")
    by_source: dict[str, int] = Field(alias="bySource")


class NotificationBulkActionRequest(BaseModel):
    """Request body for bulk notification actions."""

    model_config = ConfigDict(populate_by_name=True)

    tier: int | None = None
    tier_min: int | None = Field(default=None, alias="tierMin")
    status: NotificationStatus | None = None
    source: SourceComponent | None = None
    node_id: str | None = Field(default=None, alias="nodeId")


class NotificationBulkDeleteRequest(BaseModel):
    """Request body for bulk notification delete."""

    model_config = ConfigDict(populate_by_name=True)

    notification_ids: list[str] | None = Field(default=None, alias="notificationIds")
    status: NotificationStatus | None = None
    tier: int | None = None
    before: datetime | None = None


class NotificationBulkActionResponse(BaseModel):
    """Response for bulk notification actions."""

    model_config = ConfigDict(populate_by_name=True)

    affected_count: int = Field(alias="affectedCount")


# ---------------------------------------------------------------------------
# Group Key Builders
# ---------------------------------------------------------------------------


def build_group_key(
    notification_type: NotificationType,
    source: NotificationSource,
    details: dict[str, Any] | None = None,
) -> str:
    """Build a deduplication group key for a notification.

    Format: {notification_type}:{primary_identifier}

    Args:
        notification_type: The notification event type.
        source: The notification source.
        details: Optional event-specific details.

    Returns:
        Group key string.
    """
    base = notification_type.value

    # Node-scoped events
    if source.node_id:
        if notification_type in (
            NotificationType.STORAGE_CRITICAL,
            NotificationType.STORAGE_WARNING,
        ):
            # Include mount point if available
            mount = (details or {}).get("mountPoint", "")
            if mount:
                return f"{base}:{source.node_id}:{mount}"
        return f"{base}:{source.node_id}"

    # Service-scoped events
    if source.service_id:
        return f"{base}:{source.service_id}"

    # Auth events scoped by IP
    if notification_type == NotificationType.AUTH_BRUTE_FORCE_DETECTED:
        ip = (details or {}).get("ip", "unknown")
        return f"{base}:{ip}"

    # User-scoped events
    if notification_type in (
        NotificationType.USER_LOGIN_NEW_DEVICE,
        NotificationType.PASSWORD_CHANGED,
        NotificationType.USER_SETTINGS_UPDATED,
    ):
        user_id = (details or {}).get("userId", "unknown")
        ip = (details or {}).get("ip", "")
        if ip:
            return f"{base}:{user_id}:{ip}"
        return f"{base}:{user_id}"

    # Token/key events
    if notification_type in (
        NotificationType.TOKEN_EXPIRING,
        NotificationType.API_KEY_EXPIRING,
    ):
        token_id = (details or {}).get("tokenId") or (details or {}).get("keyId", "unknown")
        return f"{base}:{token_id}"

    # Correlation-based grouping
    if notification_type in (
        NotificationType.CHAT_PROJECT_CREATED,
        NotificationType.REGISTRATION_TOKEN_CREATED,
        NotificationType.API_KEY_CREATED,
        NotificationType.API_KEY_REVOKED,
    ):
        entity_id = (details or {}).get("entityId")
        if entity_id:
            return f"{base}:{entity_id}"

    # Common entity identifiers (command, key, token, project, user)
    for key in ("commandId", "keyId", "token", "projectId", "userId", "entityId"):
        value = (details or {}).get(key)
        if value:
            return f"{base}:{value}"

    # Fallback: type + component
    return f"{base}:{source.component.value}"
