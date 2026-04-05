"""Notification preference helpers — category mapping, quiet hours, delivery filtering."""


from datetime import UTC, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from hydra.api.v1.models.notifications import (
    TIER_MAP,
    NotificationType,
)
from hydra.api.v1.models.settings import NotificationSettings

# ------------------------------------------------------------------
# Tier-based action thresholds
# ------------------------------------------------------------------

ACKNOWLEDGE_MIN_TIER = 3  # Yellow (Warning) and above
RESOLVE_MIN_TIER = 3      # Yellow (Warning) and above

# ------------------------------------------------------------------
# Category Map
# ------------------------------------------------------------------

CATEGORY_MAP: dict[str, set[str]] = {
    "node": {
        NotificationType.NODE_OFFLINE.value,
        NotificationType.NODE_PROFILE_STALE.value,
        NotificationType.NODE_HEALTH_DEGRADED.value,
        NotificationType.NODE_REGISTERED.value,
    },
    "service": {
        NotificationType.SERVICE_DISCOVERED.value,
        NotificationType.SERVICE_STATE_CHANGED.value,
        NotificationType.SERVICE_CRASHED.value,
        NotificationType.SERVICE_INSTABILITY.value,
        NotificationType.UNKNOWN_SERVICE_DISCOVERED.value,
    },
    "profile": {
        NotificationType.AGENT_PROFILE_SUBMITTED.value,
        NotificationType.AGENT_PROFILE_FAILED.value,
        NotificationType.PROFILE_MAJOR_CHANGE.value,
        NotificationType.CONFIG_FILE_CHANGED.value,
        NotificationType.NETWORK_CONFIG_CHANGED.value,
    },
    "security": {
        NotificationType.PASSWORD_RESET_REQUESTED.value,
        NotificationType.PASSWORD_CHANGED.value,
        NotificationType.API_KEY_CREATED.value,
        NotificationType.API_KEY_REVOKED.value,
        NotificationType.API_KEY_EXPIRING.value,
        NotificationType.TOKEN_EXPIRING.value,
        NotificationType.AUTH_BRUTE_FORCE_DETECTED.value,
        NotificationType.USER_LOGIN_NEW_DEVICE.value,
        NotificationType.ROLE_ELEVATION_GRANTED.value,
        NotificationType.ROLE_ELEVATION_REVOKED.value,
        NotificationType.SUB_ACCOUNT_LINKED.value,
        NotificationType.USER_PENDING_APPROVAL.value,
    },
    "system": {
        NotificationType.API_INTERNAL_ERROR.value,
        NotificationType.DATABASE_CONNECTION_FAILED.value,
        NotificationType.WEBSOCKET_FAILURE.value,
        NotificationType.LLM_PROVIDER_FAILURE.value,
        NotificationType.MCP_AUTH_DENIED.value,
        NotificationType.MCP_TOOL_WRITE_FAILED.value,
        NotificationType.MCP_WRITE_SUCCEEDED.value,
        NotificationType.TOPOLOGY_GENERATION_FAILED.value,
        NotificationType.TOPOLOGY_REGENERATED.value,
        NotificationType.NETWORK_DISCOVERED.value,
    },
    "command": {
        NotificationType.COMMAND_EXECUTION_SUCCEEDED.value,
        NotificationType.COMMAND_EXECUTION_FAILED.value,
        NotificationType.COMMAND_EXECUTION_TIMEOUT.value,
    },
}


def resolve_category(notification_type: NotificationType | str) -> str:
    """Resolve a notification category from its type."""
    value = notification_type.value if isinstance(notification_type, NotificationType) else str(notification_type)
    for category, types in CATEGORY_MAP.items():
        if value in types:
            return category
    return "system"


def _parse_hhmm(value: str | None) -> time | None:
    if not value:
        return None
    try:
        parts = value.split(":")
        if len(parts) != 2:
            return None
        hour = int(parts[0])
        minute = int(parts[1])
        return time(hour=hour, minute=minute)
    except Exception:
        return None


def _coerce_settings(settings: NotificationSettings | dict[str, Any] | None) -> NotificationSettings:
    if isinstance(settings, NotificationSettings):
        return settings
    if isinstance(settings, dict):
        return NotificationSettings.model_validate(settings)
    return NotificationSettings()


def is_quiet_hours(settings: NotificationSettings | dict[str, Any], now: datetime) -> bool:
    """Determine if current time is within quiet hours for user settings."""
    settings = _coerce_settings(settings)
    if not settings.quiet_hours_enabled:
        return False

    start = _parse_hhmm(settings.quiet_hours_start)
    end = _parse_hhmm(settings.quiet_hours_end)
    if start is None or end is None:
        return False

    tz = None
    if settings.timezone:
        try:
            tz = ZoneInfo(settings.timezone)
        except Exception:
            tz = ZoneInfo("UTC")

    local_now = now.astimezone(tz) if tz else now
    current = local_now.time()

    if start <= end:
        return start <= current < end
    # Wrap-around case (e.g., 22:00 -> 06:00)
    return current >= start or current < end


def should_deliver(
    settings: NotificationSettings | dict[str, Any] | None,
    notification: dict[str, Any],
    channel: str,
    now: datetime | None = None,
) -> bool:
    """Check if a notification should be delivered via a specific channel."""
    settings = _coerce_settings(settings)
    now = now or datetime.now(UTC)

    notif_type = notification.get("type")
    tier = notification.get("tier")
    group_key = notification.get("groupKey")

    if tier is None and notif_type:
        try:
            tier = TIER_MAP.get(NotificationType(notif_type))
        except Exception:
            tier = None
    if tier is None:
        tier = 3

    if notif_type and notif_type in settings.muted_types:
        return False
    if group_key and group_key in settings.muted_group_keys:
        return False

    if channel == "email":
        if not settings.email_enabled:
            return False
        if tier < settings.email_min_tier:
            return False
    elif channel == "browser":
        if not settings.browser_enabled:
            return False
        if tier < settings.browser_min_tier:
            return False
    else:
        return False

    if settings.quiet_hours_enabled and is_quiet_hours(settings, now) and tier < settings.quiet_hours_min_tier:
        return False

    category = resolve_category(notif_type or "")
    if category == "node" and not settings.node_notifications:
        return False
    if category == "service" and not settings.service_notifications:
        return False
    if category == "profile" and not settings.profile_notifications:
        return False
    if category == "security" and not settings.security_notifications:
        return False
    if category == "system" and not settings.system_notifications:
        return False
    return not (category == "command" and not settings.command_notifications)
