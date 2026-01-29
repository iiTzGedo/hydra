"""Role-related utility functions.

Shared utilities for role management used across auth and users services.
"""

from datetime import datetime, timezone


def to_utc(value: datetime | None) -> datetime | None:
    """Convert a datetime to UTC timezone.

    Args:
        value: Datetime to convert, or None.

    Returns:
        Datetime in UTC, or None if input was None.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def get_active_temporary_roles(temp_roles: list) -> list:
    """Filter temporary roles to only active (non-expired) ones.

    Args:
        temp_roles: List of temporary role dicts with expiresAt, role,
            grantedBy, grantedAt, and reason fields.

    Returns:
        List of active temporary roles with normalized datetime fields.
    """
    now = datetime.now(timezone.utc)
    active = []
    for tr in temp_roles:
        expires_at = to_utc(tr.get("expiresAt"))
        if expires_at and expires_at > now:
            active.append({
                "role": tr["role"],
                "expires_at": expires_at,
                "granted_by": tr["grantedBy"],
                "granted_at": to_utc(tr.get("grantedAt")),
                "reason": tr.get("reason"),
            })
    return active
