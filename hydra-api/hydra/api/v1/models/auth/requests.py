"""Authentication request models."""

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from hydra.api.v1.core.validators import (
    NODE_ID_PATTERN_NEW,
    TAG_PATTERN,
    validate_agent_username,
    validate_node_id,
    validate_tag,
)

from .enums import Role, TokenScope


class LoginRequest(BaseModel):
    """User login request."""

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1)  # No policy enforcement on login - just verify credentials


class RefreshTokenRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str = Field(alias="refreshToken")

    model_config = ConfigDict(populate_by_name=True)


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

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def validate_registration_fields(self) -> "UserRegistrationRequest":
        if self.role == Role.AGENT:
            if self.username and not (
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

    model_config = ConfigDict(populate_by_name=True)

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
    location: dict[str, Any] | None = None
    agent_tier: str | None = Field(default=None, alias="agentTier")
    server_address: str | None = Field(default=None, alias="serverAddress", max_length=256)
    server_port: int | None = Field(default=None, alias="serverPort", ge=1, le=65535)
    server_tls_enabled: bool | None = Field(default=None, alias="serverTlsEnabled")

    model_config = ConfigDict(populate_by_name=True)

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

    @field_validator("agent_tier")
    @classmethod
    def validate_agent_tier(cls, v: str | None) -> str | None:
        """Validate agent tier is one of the allowed values."""
        if v is not None and v not in ("lite", "normal", "max"):
            raise ValueError("Agent tier must be one of: lite, normal, max")
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

    @model_validator(mode="after")
    def validate_server_metadata(self) -> "NodeRegistrationRequest":
        server_values = (
            self.server_address,
            self.server_port,
            self.server_tls_enabled,
        )
        has_any_server_metadata = any(value is not None for value in server_values)
        has_all_server_metadata = all(value is not None for value in server_values)

        if has_any_server_metadata and not has_all_server_metadata:
            raise ValueError(
                "serverAddress, serverPort, and serverTlsEnabled must be provided together"
            )

        if has_any_server_metadata and self.agent_tier != "max":
            raise ValueError(
                "Server metadata may only be provided for max-tier agents"
            )

        return self


class CreateApiKeyRequest(BaseModel):
    """Create API key request."""

    name: str = Field(min_length=3, max_length=128)
    roles: list[Role] | None = Field(
        default=None,
        description="Roles for the API key (must not exceed user's role level)",
    )
    permissions: list[str] = Field(default_factory=list)
    expires_at: datetime | None = Field(default=None, alias="expiresAt")

    model_config = ConfigDict(populate_by_name=True)


class CreateUserRequest(BaseModel):
    """Create user request (admin endpoint)."""

    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(min_length=8)
    role: Role = Role.VIEWER
    permissions: list[str] = Field(default_factory=list)
    preferences: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)

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

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("username")
    @classmethod
    def at_least_one_identifier(cls, v: str | None, info: Any) -> str | None:
        user_id = info.data.get("user_id")
        if not user_id and not v:
            raise ValueError("Either userId or username must be provided")
        return v


class ElevateRoleRequest(BaseModel):
    """Request to permanently elevate a user's role."""

    new_role: Role = Field(alias="newRole")

    model_config = ConfigDict(populate_by_name=True)

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

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: Role) -> Role:
        if v == Role.AGENT:
            raise ValueError("Cannot grant temporary agent role")
        return v


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

    model_config = ConfigDict(populate_by_name=True)


class ForgotPasswordRequest(BaseModel):
    """Request to initiate password reset."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Request to reset password with token."""

    token: str = Field(min_length=10)
    new_password: str = Field(min_length=8, alias="newPassword")

    model_config = ConfigDict(populate_by_name=True)


class ChangePasswordRequest(BaseModel):
    """Request to change own password (authenticated)."""

    current_password: str = Field(min_length=1, alias="currentPassword")
    new_password: str = Field(min_length=8, alias="newPassword")

    model_config = ConfigDict(populate_by_name=True)
