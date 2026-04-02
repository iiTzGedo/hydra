"""Authentication response models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .enums import Role, TokenScope, UserStatus


class TemporaryRole(BaseModel):
    """Temporary role grant for a user."""

    role: Role
    expires_at: datetime = Field(alias="expiresAt")
    granted_by: str = Field(alias="grantedBy")
    granted_at: datetime = Field(alias="grantedAt")
    reason: str | None = None

    model_config = {"populate_by_name": True}


class SubAccountInfo(BaseModel):
    """Information about a linked sub-account."""

    user_id: str = Field(alias="userId")
    username: str
    role: Role
    created_at: datetime = Field(alias="createdAt")

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


class SessionLoginResponse(BaseModel):
    """Browser session login response."""

    user: UserInfo
    expires_in: int = Field(alias="expiresIn", description="Access token expiry in seconds")

    model_config = {"populate_by_name": True}


class SessionRefreshResponse(BaseModel):
    """Browser session refresh response."""

    expires_in: int = Field(alias="expiresIn", description="Access token expiry in seconds")

    model_config = {"populate_by_name": True}


class LogoutResponse(BaseModel):
    """Logout confirmation payload."""

    logged_out: bool = Field(alias="loggedOut")

    model_config = {"populate_by_name": True}


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

    model_config = {"populate_by_name": True}


class NodeRegistrationResponse(BaseModel):
    """Node registration response with API key."""

    node_id: str = Field(alias="nodeId")
    api_key: str = Field(alias="apiKey", description="The API key (only shown once)")
    api_key_id: str = Field(alias="apiKeyId")
    registered_by: str = Field(alias="registeredBy")
    registered_at: datetime = Field(alias="registeredAt")
    status: str = "active"
    agent_server_secret: str | None = Field(
        default=None,
        alias="agentServerSecret",
        description="Control server secret for max-tier agents (shown once)",
    )

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
    type: str = "user"
    owner_id: str = Field(alias="ownerId")
    node_id: str | None = Field(default=None, alias="nodeId")
    permissions: list[str]
    expires_at: datetime | None = Field(alias="expiresAt")
    last_used_at: datetime | None = Field(alias="lastUsedAt")
    usage_count: int = Field(default=0, alias="usageCount")
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


# Rebuild forward references
LoginResponse.model_rebuild()
