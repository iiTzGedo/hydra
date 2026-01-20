"""Authentication models."""

from datetime import datetime
from enum import Enum
from typing import Literal

import re

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from hydra.api.v1.core.validators import (
    AGENT_USERNAME_PATTERN,
    NODE_ID_PATTERN_NEW,
    TAG_PATTERN,
    validate_agent_username,
    validate_node_id,
    validate_tag,
)


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
    Role.ADMIN.value: 2,
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


class SubAccountInfo(BaseModel):
    """Information about a linked sub-account."""

    user_id: str = Field(alias="userId")
    username: str
    role: Role
    created_at: datetime = Field(alias="createdAt")

    model_config = {"populate_by_name": True}


class SubAccountLinkRequest(BaseModel):
    """Request to link an existing user as a sub-account."""

    password: str = Field(
        min_length=8,
        description="Password of the user to be linked as sub-account",
    )
    reset_password: bool = Field(
        default=False,
        alias="resetPassword",
        description="If true, reset sub-account password to match parent password",
    )

    model_config = {"populate_by_name": True}


class SubAccountLinkResponse(BaseModel):
    """Response for successful sub-account linking."""

    parent_user_id: str = Field(alias="parentUserId")
    sub_account_user_id: str = Field(alias="subAccountUserId")
    sub_account_username: str = Field(alias="subAccountUsername")
    sub_account_role: Role = Field(alias="subAccountRole")
    linked_at: datetime = Field(alias="linkedAt")
    password_reset: bool = Field(alias="passwordReset")

    model_config = {"populate_by_name": True}


class SubAccountListResponse(BaseModel):
    """Response listing all sub-accounts of a user."""

    parent_user_id: str = Field(alias="parentUserId")
    sub_accounts: list[SubAccountInfo] = Field(alias="subAccounts")
    total: int

    model_config = {"populate_by_name": True}


class TemporaryRole(BaseModel):
    """Temporary role grant for a user."""

    role: Role
    expires_at: datetime = Field(alias="expiresAt")
    granted_by: str = Field(alias="grantedBy")
    granted_at: datetime = Field(alias="grantedAt")
    reason: str | None = None

    model_config = {"populate_by_name": True}


class LoginRequest(BaseModel):
    """User login request."""

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1)  # No policy enforcement on login - just verify credentials


class RefreshTokenRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str = Field(alias="refreshToken")

    model_config = {"populate_by_name": True}


class UserRegistrationRequest(BaseModel):
    """User registration request (open endpoint)."""

    username: str | None = Field(
        default=None,
        min_length=3,
        max_length=32,
        description="Unique username (lowercase alphanumeric, hyphens, underscores)",
    )
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8)
    role: Role = Field(description="Requested role (admin, operator, viewer, family, agent)")
    registration_token: str | None = Field(
        default=None,
        alias="registrationToken",
        description="Admin-provided token for instant activation",
    )

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def validate_registration_fields(self) -> "UserRegistrationRequest":
        if self.role == Role.AGENT:
            if self.username:
                if not (
                    validate_agent_username(self.username)
                    or re.fullmatch(r"^[a-z0-9_-]{3,32}$", self.username)
                ):
                    raise ValueError(
                        "Agent username must be lowercase alphanumeric, hyphens, or underscores "
                        "(3-32 chars)"
                    )
            if self.password and len(self.password) < 8:
                raise ValueError("Password must be at least 8 characters")
            return self

        if not self.username:
            raise ValueError("Username is required")
        if not re.fullmatch(r"^[a-z0-9_-]{3,32}$", self.username):
            raise ValueError(
                "Username must be lowercase alphanumeric, hyphens, or underscores (3-32 chars)"
            )
        if not self.email:
            raise ValueError("Email is required")
        if not self.password:
            raise ValueError("Password is required")
        if len(self.password) < 8:
            raise ValueError("Password must be at least 8 characters")
        return self


class CreateRegistrationTokenRequest(BaseModel):
    """Create registration token request."""

    scope: TokenScope = Field(
        default=TokenScope.USER,
        description="Token scope: 'user' for user registration, 'node' for node registration",
    )
    description: str | None = Field(default=None, max_length=256)
    expires_in: int | None = Field(
        default=None,
        alias="expiresIn",
        description="Expiry in seconds (default: 7 days)",
    )
    max_uses: int | None = Field(
        default=None,
        alias="maxUses",
        description="Max uses (null = unlimited)",
    )
    allowed_roles: list[Role] | None = Field(
        default=None,
        alias="allowedRoles",
        description="Restrict token to specific roles (only for user scope)",
    )

    model_config = {"populate_by_name": True}

    @field_validator("allowed_roles")
    @classmethod
    def validate_allowed_roles(cls, v: list[Role] | None) -> list[Role] | None:
        return v


class NodeRegistrationRequest(BaseModel):
    """Node registration request."""

    node_id: str = Field(
        alias="nodeId",
        min_length=3,
        max_length=64,
        description=f"Node ID must match pattern: {NODE_ID_PATTERN_NEW}",
    )
    node_class: Literal["compute", "networking", "iot"] = Field(alias="class")
    node_type: Literal["physical", "logical"] = Field(alias="type")
    kind: str | None = Field(default=None)
    display_name: str | None = Field(default=None, alias="displayName", max_length=128)
    description: str | None = Field(default=None, max_length=1024)
    tags: list[str] = Field(default_factory=list)
    parent_node_id: str | None = Field(default=None, alias="parentNodeId")
    location: dict | None = None

    model_config = {"populate_by_name": True}

    @field_validator("node_id")
    @classmethod
    def validate_node_id(cls, v: str) -> str:
        """Validate node ID with strict validation."""
        is_valid, warning = validate_node_id(v, strict=True)
        if not is_valid:
            raise ValueError(
                f"Invalid node ID format. Must match: {NODE_ID_PATTERN_NEW}."
            )
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        """Validate tags match the required pattern."""
        for tag in v:
            if not validate_tag(tag):
                raise ValueError(
                    f"Invalid tag '{tag}'. Tags must match pattern: {TAG_PATTERN} "
                    f"and be max 64 characters."
                )
        return v


class CreateApiKeyRequest(BaseModel):
    """Create API key request."""

    name: str = Field(min_length=3, max_length=128)
    roles: list[Role] | None = Field(
        default=None,
        description="Roles for the API key (must not exceed user's role level)",
    )
    permissions: list[str] = Field(default_factory=list)
    expires_at: datetime | None = Field(default=None, alias="expiresAt")

    model_config = {"populate_by_name": True}


class CreateUserRequest(BaseModel):
    """Create user request (admin endpoint)."""

    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(min_length=8)
    role: Role = Role.VIEWER
    permissions: list[str] = Field(default_factory=list)
    preferences: dict = Field(default_factory=dict)

    model_config = {"populate_by_name": True}

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: Role) -> Role:
        if v == Role.AGENT:
            raise ValueError("Cannot create agent users via admin create user endpoint")
        return v


class ApproveUserRequest(BaseModel):
    """Approve pending user request."""

    user_id: str | None = Field(default=None, alias="userId")
    username: str | None = None

    model_config = {"populate_by_name": True}

    @field_validator("username")
    @classmethod
    def at_least_one_identifier(cls, v: str | None, info) -> str | None:
        user_id = info.data.get("user_id")
        if not user_id and not v:
            raise ValueError("Either userId or username must be provided")
        return v


class ElevateRoleRequest(BaseModel):
    """Request to permanently elevate a user's role."""

    new_role: Role = Field(alias="newRole")

    model_config = {"populate_by_name": True}

    @field_validator("new_role")
    @classmethod
    def validate_new_role(cls, v: Role) -> Role:
        if v == Role.AGENT:
            raise ValueError("Cannot elevate to agent role")
        return v


class GrantTemporaryRoleRequest(BaseModel):
    """Request to grant a temporary role."""

    role: Role
    expires_at: datetime = Field(alias="expiresAt")
    reason: str | None = None

    model_config = {"populate_by_name": True}

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: Role) -> Role:
        if v == Role.AGENT:
            raise ValueError("Cannot grant temporary agent role")
        return v


class ForgotPasswordRequest(BaseModel):
    """Request to initiate password reset."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Request to reset password with token."""

    token: str = Field(min_length=10)
    new_password: str = Field(min_length=8, alias="newPassword")

    model_config = {"populate_by_name": True}


class ChangePasswordRequest(BaseModel):
    """Request to change own password (authenticated)."""

    current_password: str = Field(min_length=1, alias="currentPassword")
    new_password: str = Field(min_length=8, alias="newPassword")

    model_config = {"populate_by_name": True}


class TokenResponse(BaseModel):
    """Token response for login/registration."""

    access_token: str = Field(alias="accessToken")
    refresh_token: str = Field(alias="refreshToken")
    expires_in: int = Field(alias="expiresIn", description="Access token expiry in seconds")
    token_type: str = Field(default="Bearer", alias="tokenType")

    model_config = {"populate_by_name": True}


class UserInfo(BaseModel):
    """Basic user information."""

    user_id: str = Field(alias="userId")
    username: str
    email: str
    role: Role
    permissions: list[str] = Field(default_factory=list)
    temporary_roles: list[TemporaryRole] = Field(default_factory=list, alias="temporaryRoles")

    model_config = {"populate_by_name": True}


class LoginResponse(TokenResponse):
    """Login response with user info."""

    user: UserInfo


class UserRegistrationResponse(BaseModel):
    """User registration response."""

    user_id: str = Field(alias="userId")
    username: str
    email: str | None = None
    role: Role
    status: UserStatus
    is_bootstrap: bool | None = Field(default=None, alias="isBootstrap")
    message: str | None = None
    created_at: datetime = Field(alias="createdAt")
    is_system_account: bool | None = Field(default=None, alias="isSystemAccount")
    parent_user_id: str | None = Field(default=None, alias="parentUserId")
    api_key: str | None = Field(default=None, alias="apiKey")
    api_key_id: str | None = Field(default=None, alias="apiKeyId")
    api_key_expires_at: datetime | None = Field(default=None, alias="apiKeyExpiresAt")
    password: str | None = None

    model_config = {"populate_by_name": True}


class NodeRegistrationResponse(BaseModel):
    """Node registration response with API key."""

    node_id: str = Field(alias="nodeId")
    api_key: str = Field(alias="apiKey", description="The API key (only shown once)")
    api_key_id: str = Field(alias="apiKeyId")
    registered_by: str = Field(alias="registeredBy")
    registered_at: datetime = Field(alias="registeredAt")
    status: str = "active"

    model_config = {"populate_by_name": True}


class NodeApiKeyRefreshResponse(BaseModel):
    """Response for node API key refresh."""

    node_id: str = Field(alias="nodeId")
    api_key_id: str = Field(alias="apiKeyId")
    api_key: str = Field(alias="apiKey", description="The new API key (only shown once)")
    previous_key_revoked: bool = Field(alias="previousKeyRevoked")
    refreshed_at: datetime = Field(alias="refreshedAt")

    model_config = {"populate_by_name": True}


class RegistrationTokenResponse(BaseModel):
    """Registration token creation response."""

    token: str
    scope: TokenScope = Field(default=TokenScope.USER)
    expires_at: datetime = Field(alias="expiresAt")
    max_uses: int | None = Field(alias="maxUses")
    used_count: int = Field(default=0, alias="usedCount")
    allowed_roles: list[Role] | None = Field(default=None, alias="allowedRoles")
    created_by: str = Field(alias="createdBy")

    model_config = {"populate_by_name": True}


class RegistrationTokenUsage(BaseModel):
    """Registration token usage record."""

    entity_id: str = Field(alias="entityId")
    entity_type: str = Field(alias="entityType")
    used_at: datetime = Field(alias="usedAt")

    model_config = {"populate_by_name": True}


class RegistrationTokenListItem(BaseModel):
    """Registration token list item (without actual token value for security)."""

    token_id: str = Field(alias="tokenId", description="Masked token identifier (last 8 chars)")
    scope: TokenScope
    description: str | None = None
    expires_at: datetime = Field(alias="expiresAt")
    max_uses: int | None = Field(alias="maxUses")
    used_count: int = Field(alias="usedCount")
    used_by: list[RegistrationTokenUsage] = Field(default_factory=list, alias="usedBy")
    allowed_roles: list[Role] | None = Field(default=None, alias="allowedRoles")
    created_by: str = Field(alias="createdBy")
    created_at: datetime = Field(alias="createdAt")
    is_active: bool = Field(alias="isActive", description="Whether token is still usable")

    model_config = {"populate_by_name": True}


class RegistrationTokenListResponse(BaseModel):
    """List of registration tokens response."""

    tokens: list[RegistrationTokenListItem]
    total: int
    limit: int
    offset: int

    model_config = {"populate_by_name": True}


class ApiKeyResponse(BaseModel):
    """API key creation response."""

    key_id: str = Field(alias="keyId")
    key: str = Field(description="The API key (only shown once)")
    name: str
    roles: list[Role] | None = None
    permissions: list[str]
    expires_at: datetime | None = Field(alias="expiresAt")
    created_by: str = Field(alias="createdBy")
    created_at: datetime = Field(alias="createdAt")

    model_config = {"populate_by_name": True}


class ApiKeyListItem(BaseModel):
    """API key list item (without the key itself)."""

    key_id: str = Field(alias="keyId")
    name: str
    permissions: list[str]
    expires_at: datetime | None = Field(alias="expiresAt")
    last_used_at: datetime | None = Field(alias="lastUsedAt")
    created_at: datetime = Field(alias="createdAt")

    model_config = {"populate_by_name": True}


class ApiKeyListResponse(BaseModel):
    """List of API keys response."""

    api_keys: list[ApiKeyListItem] = Field(alias="apiKeys")
    total: int

    model_config = {"populate_by_name": True}


class ApiKeyRevokeResponse(BaseModel):
    """API key revocation response."""

    key_id: str = Field(alias="keyId")
    revoked: bool = True
    revoked_at: datetime = Field(alias="revokedAt")

    model_config = {"populate_by_name": True}


class PendingUserInfo(BaseModel):
    """Pending user information."""

    user_id: str = Field(alias="userId")
    username: str
    email: str
    role: Role
    requested_at: datetime = Field(alias="requestedAt")

    model_config = {"populate_by_name": True}


class PendingUsersListResponse(BaseModel):
    """List of pending users response."""

    pending_users: list[PendingUserInfo] = Field(alias="pendingUsers")
    total: int
    limit: int
    offset: int

    model_config = {"populate_by_name": True}


class ApprovalResponse(BaseModel):
    """User approval response."""

    user_id: str = Field(alias="userId")
    username: str
    email: str
    role: Role
    status: UserStatus
    approved_by: str = Field(alias="approvedBy")
    approved_at: datetime = Field(alias="approvedAt")

    model_config = {"populate_by_name": True}


class RejectionResponse(BaseModel):
    """User rejection response."""

    user_id: str = Field(alias="userId")
    rejected: bool = True
    rejected_by: str = Field(alias="rejectedBy")
    rejected_at: datetime = Field(alias="rejectedAt")

    model_config = {"populate_by_name": True}


class RoleElevationResponse(BaseModel):
    """Role elevation response."""

    user_id: str = Field(alias="userId")
    previous_role: Role = Field(alias="previousRole")
    new_role: Role = Field(alias="newRole")
    elevated_by: str = Field(alias="elevatedBy")
    elevated_at: datetime = Field(alias="elevatedAt")

    model_config = {"populate_by_name": True}


class TemporaryRoleGrantResponse(BaseModel):
    """Temporary role grant response."""

    user_id: str = Field(alias="userId")
    base_role: Role = Field(alias="baseRole")
    temporary_roles: list[TemporaryRole] = Field(alias="temporaryRoles")

    model_config = {"populate_by_name": True}


class TemporaryRoleRevokeResponse(BaseModel):
    """Temporary role revocation response."""

    user_id: str = Field(alias="userId")
    revoked_role: Role = Field(alias="revokedRole")
    revoked_by: str = Field(alias="revokedBy")
    revoked_at: datetime = Field(alias="revokedAt")

    model_config = {"populate_by_name": True}


class CurrentUserResponse(BaseModel):
    """Current authenticated user/agent response."""

    type: Literal["user", "agent"]
    user_id: str | None = Field(default=None, alias="userId")
    node_id: str | None = Field(default=None, alias="nodeId")
    username: str | None = None
    email: str | None = None
    role: Role | None = None
    permissions: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class UserDetailResponse(BaseModel):
    """Detailed user information response."""

    user_id: str = Field(alias="userId")
    username: str
    email: str
    role: Role
    temporary_roles: list[TemporaryRole] = Field(default_factory=list, alias="temporaryRoles")
    permissions: list[str] = Field(default_factory=list)
    resource_permissions: list[str] = Field(default_factory=list, alias="resourcePermissions")
    registered_nodes: list[str] = Field(default_factory=list, alias="registeredNodes")
    preferences: dict = Field(default_factory=dict)
    status: UserStatus
    # Sub-account fields
    is_system_account: bool = Field(default=False, alias="isSystemAccount")
    parent_user_id: str | None = Field(default=None, alias="parentUserId")
    sub_accounts: list[SubAccountInfo] = Field(default_factory=list, alias="subAccounts")
    # Timestamps
    last_login: datetime | None = Field(alias="lastLogin")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}


class UserListItem(BaseModel):
    """User list item."""

    user_id: str = Field(alias="userId")
    username: str
    email: str
    role: Role
    status: UserStatus
    last_login: datetime | None = Field(alias="lastLogin")
    created_at: datetime = Field(alias="createdAt")

    model_config = {"populate_by_name": True}


class UserListResponse(BaseModel):
    """List of users response."""

    users: list[UserListItem]
    total: int
    limit: int
    offset: int

    model_config = {"populate_by_name": True}


class ForgotPasswordResponse(BaseModel):
    """Response for forgot password request."""

    message: str = "If an account with that email exists, a reset link has been sent."
    email_sent: bool = Field(alias="emailSent")

    model_config = {"populate_by_name": True}


class ResetPasswordResponse(BaseModel):
    """Response for successful password reset."""

    message: str = "Password has been reset successfully."
    reset_at: datetime = Field(alias="resetAt")

    model_config = {"populate_by_name": True}


class ChangePasswordResponse(BaseModel):
    """Response for successful password change."""

    message: str = "Password has been changed successfully."
    changed_at: datetime = Field(alias="changedAt")

    model_config = {"populate_by_name": True}


LoginResponse.model_rebuild()
