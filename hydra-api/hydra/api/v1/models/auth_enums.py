"""Authentication enums, role constants, and role utility functions."""

from enum import Enum


class TokenType(str, Enum):
    """Token types."""

    ACCESS = "access"
    REFRESH = "refresh"
    REGISTRATION = "registration"
    API_KEY = "api_key"


class TokenScope(str, Enum):
    """Registration token scopes."""

    USER = "user"  # For user registration
    NODE = "node"  # For node registration


class Role(str, Enum):
    """User roles."""

    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"
    FAMILY = "family"
    AGENT = "agent"


class UserStatus(str, Enum):
    """User account status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"
    PENDING_APPROVAL = "pending_approval"


class ApiKeyType(str, Enum):
    """API key types."""

    USER = "user"
    NODE = "node"


ROLE_LIMITS: dict[str, int | None] = {
    Role.ADMIN.value: 3,  # Allows primary admin, backup admin, and system_admin for testing
    Role.OPERATOR.value: 10,
    Role.VIEWER.value: None,  # Unlimited
    Role.FAMILY.value: None,  # Unlimited
    Role.AGENT.value: None,  # Unlimited (one per node)
}

ROLE_LEVELS: dict[str, int] = {
    Role.ADMIN.value: 100,
    Role.OPERATOR.value: 50,
    Role.VIEWER.value: 25,
    Role.FAMILY.value: 10,
    Role.AGENT.value: 0,
}


def get_role_level(role: str) -> int:
    """Get the numeric level for a role."""
    return ROLE_LEVELS.get(role, 0)


def can_create_token_for_role(creator_role: str, target_role: str) -> bool:
    """Check if creator can create tokens for target role (same level or lower)."""
    return get_role_level(creator_role) >= get_role_level(target_role)


def can_have_sub_accounts(role: str) -> bool:
    """Check if a role can have sub-accounts (only admin and operator)."""
    return role in [Role.ADMIN.value, Role.OPERATOR.value]


def is_valid_sub_account_role(role: str) -> bool:
    """Check if a role can be a sub-account (family, viewer, or agent)."""
    return role in [Role.FAMILY.value, Role.VIEWER.value, Role.AGENT.value]
