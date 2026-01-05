"""Authentication endpoints."""

import structlog
from fastapi import APIRouter, Depends, Path, Query

from hydra_api.core.deps import (
    AuthServiceDep,
    CurrentUser,
    UsersServiceDep,
    require_permission,
)
from hydra_api.core.config import get_settings
from hydra_api.models.auth import (
    ApiKeyListResponse,
    ApiKeyResponse,
    ApiKeyRevokeResponse,
    ApprovalResponse,
    ApproveUserRequest,
    ChangePasswordRequest,
    ChangePasswordResponse,
    CreateApiKeyRequest,
    CreateRegistrationTokenRequest,
    CreateUserRequest,
    CurrentUserResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LoginResponse,
    PendingUsersListResponse,
    RefreshTokenRequest,
    RegistrationTokenResponse,
    RejectionResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    Role,
    TemporaryRole,
    TokenResponse,
    UserInfo,
    UserRegistrationRequest,
    UserRegistrationResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = structlog.get_logger(__name__)


# ==================== User Authentication ====================


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="User Login",
    description="Authenticate a user with username and password.",
)
async def login(
    request: LoginRequest,
    auth_service: AuthServiceDep,
) -> LoginResponse:
    """Authenticate a user and return tokens."""
    result = await auth_service.authenticate_user(request.username, request.password)

    # Convert temporary roles to response format
    temp_roles = [
        TemporaryRole(
            role=Role(tr["role"]),
            expires_at=tr["expires_at"],
            granted_by=tr["granted_by"],
            granted_at=tr["granted_at"],
            reason=tr.get("reason"),
        )
        for tr in result["user"].get("temporary_roles", [])
    ]

    return LoginResponse(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        expires_in=result["expires_in"],
        user=UserInfo(
            user_id=result["user"]["user_id"],
            username=result["user"]["username"],
            email=result["user"]["email"],
            role=result["user"]["role"],
            permissions=result["user"].get("permissions", []),
            temporary_roles=temp_roles,
        ),
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh Token",
    description="Get a new access token using a refresh token.",
)
async def refresh_token(
    request: RefreshTokenRequest,
    auth_service: AuthServiceDep,
) -> TokenResponse:
    """Refresh an access token."""
    result = await auth_service.refresh_access_token(request.refresh_token)
    return TokenResponse(
        access_token=result["access_token"],
        refresh_token=request.refresh_token,
        expires_in=result["expires_in"],
    )


# ==================== Password Reset ====================


@router.post(
    "/password/forgot",
    response_model=ForgotPasswordResponse,
    summary="Forgot Password",
    description="""Request a password reset email.

For security, this endpoint always returns success even if the email doesn't exist.
If SMTP is not configured, no email will be sent but the endpoint will still succeed.
""",
)
async def forgot_password(
    request: ForgotPasswordRequest,
    users_service: UsersServiceDep,
) -> ForgotPasswordResponse:
    """Request a password reset."""
    settings = get_settings()
    result = await users_service.request_password_reset(request.email, settings)
    return ForgotPasswordResponse(
        email_sent=result["email_sent"],
    )


@router.post(
    "/password/reset",
    response_model=ResetPasswordResponse,
    summary="Reset Password",
    description="Reset password using a reset token received via email.",
)
async def reset_password(
    request: ResetPasswordRequest,
    users_service: UsersServiceDep,
) -> ResetPasswordResponse:
    """Reset password with token."""
    result = await users_service.reset_password(request.token, request.new_password)
    return ResetPasswordResponse(
        reset_at=result["reset_at"],
    )


@router.post(
    "/password/change",
    response_model=ChangePasswordResponse,
    summary="Change Password",
    description="Change password for the currently authenticated user.",
)
async def change_password(
    request: ChangePasswordRequest,
    users_service: UsersServiceDep,
    current_user: CurrentUser,
) -> ChangePasswordResponse:
    """Change password for authenticated user."""
    result = await users_service.change_password(
        current_user["user_id"],
        request.current_password,
        request.new_password,
    )
    return ChangePasswordResponse(
        changed_at=result["changed_at"],
    )


# ==================== User Registration ====================


@router.post(
    "/register",
    response_model=UserRegistrationResponse,
    status_code=201,
    summary="Register User",
    description="Register a new user account. No authentication required.",
    responses={
        201: {"description": "User created (with token or bootstrap)"},
        202: {"description": "Registration pending approval"},
    },
)
async def register_user(
    request: UserRegistrationRequest,
    users_service: UsersServiceDep,
) -> UserRegistrationResponse:
    """Register a new user account."""
    result = await users_service.register_user(request)

    # Determine status code based on result
    # Note: FastAPI doesn't easily support dynamic status codes in the return,
    # but the response model handles the status field

    return UserRegistrationResponse(
        user_id=result["user_id"],
        username=result["username"],
        email=result["email"],
        role=result["role"],
        status=result["status"],
        is_bootstrap=result.get("is_bootstrap"),
        message=result.get("message"),
        created_at=result["created_at"],
    )


# ==================== User Approval Workflow ====================


@router.get(
    "/approvals",
    response_model=PendingUsersListResponse,
    summary="List Pending Approvals",
    description="List pending user registrations awaiting approval. Admin only.",
    dependencies=[Depends(require_permission("users:*"))],
)
async def list_pending_approvals(
    users_service: UsersServiceDep,
    role: Role | None = Query(default=None, description="Filter by requested role"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PendingUsersListResponse:
    """List pending user registrations."""
    result = await users_service.list_pending_users(
        role=role.value if role else None,
        limit=limit,
        offset=offset,
    )
    return PendingUsersListResponse(
        pending_users=[
            {
                "user_id": u["user_id"],
                "username": u["username"],
                "email": u["email"],
                "role": u["role"],
                "requested_at": u["requested_at"],
            }
            for u in result["pending_users"]
        ],
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
    )


@router.post(
    "/approvals",
    response_model=ApprovalResponse,
    summary="Approve User",
    description="Approve a pending user registration. Admin only.",
    dependencies=[Depends(require_permission("users:*"))],
)
async def approve_user(
    request: ApproveUserRequest,
    users_service: UsersServiceDep,
    current_user: CurrentUser,
) -> ApprovalResponse:
    """Approve a pending user registration."""
    result = await users_service.approve_user(request, current_user["user_id"])
    return ApprovalResponse(
        user_id=result["user_id"],
        username=result["username"],
        email=result["email"],
        role=result["role"],
        status=result["status"],
        approved_by=result["approved_by"],
        approved_at=result["approved_at"],
    )


@router.delete(
    "/approvals/{userId}",
    response_model=RejectionResponse,
    summary="Reject User",
    description="Reject and delete a pending user registration. Admin only.",
    dependencies=[Depends(require_permission("users:*"))],
)
async def reject_user(
    users_service: UsersServiceDep,
    current_user: CurrentUser,
    userId: str = Path(description="Pending user ID"),
) -> RejectionResponse:
    """Reject a pending user registration."""
    result = await users_service.reject_user(userId, current_user["user_id"])
    return RejectionResponse(
        user_id=result["user_id"],
        rejected=result["rejected"],
        rejected_by=result["rejected_by"],
        rejected_at=result["rejected_at"],
    )


# ==================== Registration Tokens ====================


@router.post(
    "/tokens",
    response_model=RegistrationTokenResponse,
    status_code=201,
    summary="Create Registration Token",
    description="""Create a new registration token for user or node registration.

**Scopes:**
- `user` (default): Token can be used for user registration
- `node`: Token can be used for node registration via `X-Registration-Token` header

**Permissions:**
- Requires `tokens:create` (admin) OR `tokens:create:user`/`tokens:create:node`
- Admin can create tokens for any role
- Operator can create tokens for operator, viewer, family roles only
- Family can only create tokens for family role
- Token's `allowedRoles` is automatically restricted based on creator's role level
""",
)
async def create_registration_token(
    request: CreateRegistrationTokenRequest,
    auth_service: AuthServiceDep,
    current_user: CurrentUser,
) -> RegistrationTokenResponse:
    """Create a new registration token."""
    user_permissions = current_user.get("permissions", [])
    user_role = current_user.get("role")

    # Check permissions based on scope
    has_full_permission = "tokens:create" in user_permissions or "*:*" in user_permissions
    has_user_permission = "tokens:create:user" in user_permissions
    has_node_permission = "tokens:create:node" in user_permissions

    if request.scope.value == "user":
        if not (has_full_permission or has_user_permission):
            from hydra_api.core.exceptions import AuthorizationError
            raise AuthorizationError("tokens:create:user")
    elif request.scope.value == "node":
        if not (has_full_permission or has_node_permission):
            from hydra_api.core.exceptions import AuthorizationError
            raise AuthorizationError("tokens:create:node")

    result = await auth_service.create_registration_token(
        request, current_user["user_id"], creator_role=user_role
    )
    return RegistrationTokenResponse(
        token=result["token"],
        scope=result["scope"],
        expires_at=result["expires_at"],
        max_uses=result["max_uses"],
        used_count=result["used_count"],
        allowed_roles=result.get("allowed_roles"),
        created_by=result["created_by"],
    )


# ==================== API Keys ====================


@router.post(
    "/apikeys",
    response_model=ApiKeyResponse,
    status_code=201,
    summary="Create API Key",
    description="Create a new API key for programmatic access.",
    dependencies=[Depends(require_permission("tokens:create"))],
)
async def create_api_key(
    request: CreateApiKeyRequest,
    auth_service: AuthServiceDep,
    current_user: CurrentUser,
) -> ApiKeyResponse:
    """Create a new API key."""
    result = await auth_service.create_api_key(request, current_user["user_id"])
    return ApiKeyResponse(
        key_id=result["key_id"],
        key=result["key"],
        name=result["name"],
        roles=result.get("roles"),
        permissions=result["permissions"],
        expires_at=result["expires_at"],
        created_by=result["created_by"],
        created_at=result["created_at"],
    )


@router.get(
    "/apikeys",
    response_model=ApiKeyListResponse,
    summary="List API Keys",
    description="List API keys owned by the current user.",
)
async def list_api_keys(
    auth_service: AuthServiceDep,
    current_user: CurrentUser,
) -> ApiKeyListResponse:
    """List API keys for the current user."""
    result = await auth_service.list_api_keys(current_user["user_id"])
    return ApiKeyListResponse(
        api_keys=[
            {
                "key_id": k["key_id"],
                "name": k["name"],
                "permissions": k["permissions"],
                "expires_at": k.get("expires_at"),
                "last_used_at": k.get("last_used_at"),
                "created_at": k["created_at"],
            }
            for k in result["api_keys"]
        ],
        total=result["total"],
    )


@router.delete(
    "/apikeys/{keyId}",
    response_model=ApiKeyRevokeResponse,
    summary="Revoke API Key",
    description="Revoke an API key.",
)
async def revoke_api_key(
    auth_service: AuthServiceDep,
    current_user: CurrentUser,
    keyId: str = Path(description="API key ID"),
) -> ApiKeyRevokeResponse:
    """Revoke an API key."""
    result = await auth_service.revoke_api_key(keyId, current_user["user_id"])
    return ApiKeyRevokeResponse(
        key_id=result["key_id"],
        revoked=result["revoked"],
        revoked_at=result["revoked_at"],
    )


# ==================== Current User ====================


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="Get Current User",
    description="Get information about the currently authenticated user or agent.",
)
async def get_current_user_info(
    current_user: CurrentUser,
) -> CurrentUserResponse:
    """Get current user/agent info."""
    return CurrentUserResponse(
        type=current_user["type"],
        user_id=current_user.get("user_id"),
        node_id=current_user.get("node_id"),
        username=current_user.get("username"),
        email=current_user.get("email"),
        role=current_user.get("role"),
        permissions=current_user.get("permissions", []),
    )


# ==================== User Management (Admin) ====================


@router.post(
    "/users",
    response_model=UserInfo,
    status_code=201,
    summary="Create User",
    description="Create a new user account directly. Admin only.",
    dependencies=[Depends(require_permission("users:create"))],
)
async def create_user(
    request: CreateUserRequest,
    users_service: UsersServiceDep,
) -> UserInfo:
    """Create a new user (admin only)."""
    result = await users_service.create_user(request)
    return UserInfo(
        user_id=result["user_id"],
        username=result["username"],
        email=result["email"],
        role=result["role"],
    )
