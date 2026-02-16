"""Authentication endpoints."""

import structlog
from fastapi import APIRouter, Depends, Path, Query, Request

from hydra.api.v1.core.deps import (
    AuthServiceDep,
    CurrentUser,
    OptionalUser,
    UsersServiceDep,
    require_permission,
)
from hydra.api.v1.core.exceptions import AuthorizationError
from hydra.core.config import get_settings
from hydra.api.v1.models.auth import (
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
    RegistrationTokenListItem,
    RegistrationTokenListResponse,
    RegistrationTokenResponse,
    RegistrationTokenUsage,
    RejectionResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    Role,
    SubAccountLinkRequest,
    SubAccountLinkResponse,
    SubAccountListResponse,
    TemporaryRole,
    TokenResponse,
    TokenScope,
    UserInfo,
    UserRegistrationRequest,
    UserRegistrationResponse,
    UserStatus,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = structlog.get_logger(__name__)


@router.post(
    "/login",
    response_model=LoginResponse,
    response_model_by_alias=True,
    summary="User Login",
    description="""Authenticate a user with username and password.

Use `source=agent` query parameter to allow system/agent account login (for CLI use).
By default, system accounts are blocked from web login.""",
)
async def login(
    request: LoginRequest,
    auth_service: AuthServiceDep,
    http_request: Request,
    source: str | None = Query(
        default=None,
        description="Login source. Use 'agent' to allow system account login from CLI.",
    ),
) -> LoginResponse:
    """Authenticate a user and obtain access tokens.

    Args:
        request: Login credentials (username and password).
        auth_service: Authentication service instance.
        source: Login source identifier for agent CLI login.

    Returns:
        Access token, refresh token, and user information.

    Raises:
        HTTPException 401: Invalid credentials.
        HTTPException 403: Account locked or pending approval.
    """
    allow_system_accounts = source == "agent"
    ip = None
    forwarded_for = http_request.headers.get("x-forwarded-for")
    if forwarded_for:
        ip = forwarded_for.split(",")[0].strip()
    elif http_request.client:
        ip = http_request.client.host

    user_agent = http_request.headers.get("user-agent")

    result = await auth_service.authenticate_user(
        request.username,
        request.password,
        allow_system_accounts=allow_system_accounts,
        ip=ip,
        user_agent=user_agent,
    )

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
    response_model_by_alias=True,
    summary="Refresh Token",
    description="Get a new access token using a refresh token.",
)
async def refresh_token(
    request: RefreshTokenRequest,
    auth_service: AuthServiceDep,
) -> TokenResponse:
    """Obtain a new access token using a valid refresh token.

    Args:
        request: Refresh token.
        auth_service: Authentication service instance.

    Returns:
        New access token with expiration information.

    Raises:
        HTTPException 401: Invalid or expired refresh token.
    """
    result = await auth_service.refresh_access_token(request.refresh_token)
    return TokenResponse(
        access_token=result["access_token"],
        refresh_token=request.refresh_token,
        expires_in=result["expires_in"],
    )


@router.post(
    "/password/forgot",
    response_model=ForgotPasswordResponse,
    response_model_by_alias=True,
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
    """Request a password reset email for an account.

    Args:
        request: Email address for the account.
        users_service: Users service instance.

    Returns:
        Confirmation of email dispatch attempt.
    """
    settings = get_settings()
    result = await users_service.request_password_reset(request.email, settings)
    return ForgotPasswordResponse(
        email_sent=result["email_sent"],
    )


@router.post(
    "/password/reset",
    response_model=ResetPasswordResponse,
    response_model_by_alias=True,
    summary="Reset Password",
    description="Reset password using a reset token received via email.",
)
async def reset_password(
    request: ResetPasswordRequest,
    users_service: UsersServiceDep,
) -> ResetPasswordResponse:
    """Reset account password using a valid reset token.

    Args:
        request: Reset token and new password.
        users_service: Users service instance.

    Returns:
        Confirmation of password reset.

    Raises:
        HTTPException 400: Invalid or expired reset token.
    """
    result = await users_service.reset_password(request.token, request.new_password)
    return ResetPasswordResponse(
        reset_at=result["reset_at"],
    )


@router.post(
    "/password/change",
    response_model=ChangePasswordResponse,
    response_model_by_alias=True,
    summary="Change Password",
    description="Change password for the currently authenticated user.",
)
async def change_password(
    request: ChangePasswordRequest,
    users_service: UsersServiceDep,
    current_user: CurrentUser,
) -> ChangePasswordResponse:
    """Change the password for the authenticated user.

    Args:
        request: Current password and new password.
        users_service: Users service instance.
        current_user: Authenticated user making the request.

    Returns:
        Confirmation of password change.

    Raises:
        HTTPException 400: Current password is incorrect.
        HTTPException 401: Not authenticated.
    """
    result = await users_service.change_password(
        current_user["user_id"],
        request.current_password,
        request.new_password,
    )
    return ChangePasswordResponse(
        changed_at=result["changed_at"],
    )


@router.post(
    "/register",
    response_model=UserRegistrationResponse,
    response_model_by_alias=True,
    status_code=201,
    summary="Register User",
    description="Register a new user account. Agent registrations require admin/operator auth or a valid registration token.",
    responses={
        201: {"description": "User created (with token or bootstrap)"},
        202: {"description": "Registration pending approval"},
    },
)
async def register_user(
    request: UserRegistrationRequest,
    auth_service: AuthServiceDep,
    users_service: UsersServiceDep,
    current_user: OptionalUser,
) -> UserRegistrationResponse:
    """Register a new user or agent account.

    Args:
        request: Registration details including username, password, and role.
        auth_service: Authentication service instance.
        users_service: Users service instance.
        current_user: Optional authenticated user (for agent registration).

    Returns:
        Registration result with user details and status.

    Raises:
        HTTPException 400: Invalid registration data.
        HTTPException 401: Agent registration requires authentication.
        HTTPException 409: Username or email already exists.
    """
    if request.role == Role.AGENT:
        parent_user_id = None
        if current_user:
            if current_user.get("type") != "user":
                raise AuthorizationError()
            if current_user.get("role") not in [Role.ADMIN.value, Role.OPERATOR.value]:
                raise AuthorizationError()
            parent_user_id = current_user["user_id"]

        if not parent_user_id and not request.registration_token:
            raise AuthorizationError()

        result = await auth_service.register_agent(
            parent_user_id=parent_user_id,
            username=request.username,
            password=request.password,
            registration_token=request.registration_token,
        )

        return UserRegistrationResponse(
            user_id=result["user_id"],
            username=result["username"],
            email=None,
            role=Role(result["role"]),
            status=UserStatus.ACTIVE,
            is_bootstrap=None,
            message=result.get("message"),
            created_at=result["created_at"],
            is_system_account=result.get("is_system_account"),
            parent_user_id=result.get("parent_user_id"),
            api_key=result.get("api_key"),
            api_key_id=result.get("api_key_id"),
            api_key_expires_at=result.get("api_key_expires_at"),
            password=result.get("password"),
        )

    result = await users_service.register_user(request)

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


@router.get(
    "/approvals",
    response_model=PendingUsersListResponse,
    response_model_by_alias=True,
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
    """List user registrations awaiting admin approval.

    Args:
        users_service: Users service instance.
        role: Filter by requested role.
        limit: Maximum number of results to return.
        offset: Number of results to skip.

    Returns:
        List of pending user registrations.

    Raises:
        HTTPException 403: Insufficient permissions.
    """
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
    response_model_by_alias=True,
    summary="Approve User",
    description="Approve a pending user registration. Admin only.",
    dependencies=[Depends(require_permission("users:*"))],
)
async def approve_user(
    request: ApproveUserRequest,
    users_service: UsersServiceDep,
    current_user: CurrentUser,
) -> ApprovalResponse:
    """Approve a pending user registration.

    Args:
        request: User ID and optional role override.
        users_service: Users service instance.
        current_user: Admin user approving the request.

    Returns:
        Approved user details with assigned role.

    Raises:
        HTTPException 404: Pending user not found.
        HTTPException 403: Insufficient permissions.
    """
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
    "/approvals/{user_id}",
    response_model=RejectionResponse,
    response_model_by_alias=True,
    summary="Reject User",
    description="Reject and delete a pending user registration. Admin only.",
    dependencies=[Depends(require_permission("users:*"))],
)
async def reject_user(
    users_service: UsersServiceDep,
    current_user: CurrentUser,
    user_id: str = Path(description="Pending user ID"),
) -> RejectionResponse:
    """Reject and delete a pending user registration.

    Args:
        users_service: Users service instance.
        current_user: Admin user rejecting the request.
        user_id: ID of the pending user to reject.

    Returns:
        Rejection confirmation.

    Raises:
        HTTPException 404: Pending user not found.
        HTTPException 403: Insufficient permissions.
    """
    result = await users_service.reject_user(user_id, current_user["user_id"])
    return RejectionResponse(
        user_id=result["user_id"],
        rejected=result["rejected"],
        rejected_by=result["rejected_by"],
        rejected_at=result["rejected_at"],
    )


@router.post(
    "/tokens",
    response_model=RegistrationTokenResponse,
    response_model_by_alias=True,
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
    """Create a registration token for automated user or node provisioning.

    Args:
        request: Token configuration including scope and expiration.
        auth_service: Authentication service instance.
        current_user: User creating the token.

    Returns:
        Generated token with usage constraints.

    Raises:
        HTTPException 403: Insufficient permissions for requested scope.
    """
    user_permissions = current_user.get("permissions", [])
    user_role = current_user.get("role")

    has_full_permission = "tokens:create" in user_permissions or "*:*" in user_permissions
    has_user_permission = "tokens:create:user" in user_permissions
    has_node_permission = "tokens:create:node" in user_permissions

    if request.scope.value == "user":
        if not (has_full_permission or has_user_permission):
            raise AuthorizationError("tokens:create:user")
    elif request.scope.value == "node":
        if not (has_full_permission or has_node_permission):
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


@router.get(
    "/tokens",
    response_model=RegistrationTokenListResponse,
    response_model_by_alias=True,
    summary="List Registration Tokens",
    description="""List registration tokens created by the current user.

**Filters:**
- `scope`: Filter by token scope (`user` or `node`)
- `activeOnly`: Only return tokens that are still usable (default: true)

**Note:** For security, actual token values are masked (only last 8 characters shown).
""",
)
async def list_registration_tokens(
    auth_service: AuthServiceDep,
    current_user: CurrentUser,
    scope: TokenScope | None = Query(default=None, description="Filter by scope"),
    active_only: bool = Query(default=True, alias="activeOnly", description="Only show active tokens"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> RegistrationTokenListResponse:
    """List registration tokens created by the authenticated user.

    Args:
        auth_service: Authentication service instance.
        current_user: Authenticated user.
        scope: Filter by token scope.
        active_only: Only return usable tokens.
        limit: Maximum number of results to return.
        offset: Number of results to skip.

    Returns:
        Paginated list of registration tokens with masked values.
    """
    tokens, total = await auth_service.list_registration_tokens(
        user_id=current_user["user_id"],
        scope=scope.value if scope else None,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )

    return RegistrationTokenListResponse(
        tokens=[
            RegistrationTokenListItem(
                token_id=t["token_id"],
                scope=TokenScope(t["scope"]),
                description=t.get("description"),
                expires_at=t["expires_at"],
                max_uses=t.get("max_uses"),
                used_count=t["used_count"],
                used_by=[
                    RegistrationTokenUsage(
                        entity_id=u["entityId"],
                        entity_type=u["entityType"],
                        used_at=u["usedAt"],
                    )
                    for u in t.get("used_by", [])
                ],
                allowed_roles=[Role(r) for r in t["allowed_roles"]] if t.get("allowed_roles") else None,
                created_by=t["created_by"],
                created_at=t["created_at"],
                is_active=t["is_active"],
            )
            for t in tokens
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/apikeys",
    response_model=ApiKeyResponse,
    response_model_by_alias=True,
    status_code=201,
    summary="Create API Key",
    description="Create a new API key for programmatic access.",
    dependencies=[Depends(require_permission("tokens:create"))],
)
async def create_api_key(
    request: CreateApiKeyRequest,
    auth_service: AuthServiceDep,
    users_service: UsersServiceDep,
    current_user: CurrentUser,
    sub_account_user_id: str | None = Query(default=None, alias="subAccountUserId"),
) -> ApiKeyResponse:
    """Create an API key for programmatic access to the API.

    Args:
        request: API key configuration including permissions and expiration.
        auth_service: Authentication service instance.
        users_service: Users service instance.
        current_user: User creating the API key.
        sub_account_user_id: Create key for a sub-account (parent/admin only).

    Returns:
        Generated API key (shown only once).

    Raises:
        HTTPException 403: Cannot create key for specified sub-account.
    """
    owner_id = current_user["user_id"]
    if sub_account_user_id:
        if current_user.get("role") == Role.ADMIN.value:
            owner_id = sub_account_user_id
        elif await users_service.is_parent_of(current_user["user_id"], sub_account_user_id):
            owner_id = sub_account_user_id
        else:
            raise AuthorizationError()

    result = await auth_service.create_api_key(request, owner_id)
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
    response_model_by_alias=True,
    summary="List API Keys",
    description="List API keys owned by the current user.",
)
async def list_api_keys(
    auth_service: AuthServiceDep,
    users_service: UsersServiceDep,
    current_user: CurrentUser,
    sub_account_user_id: str | None = Query(default=None, alias="subAccountUserId"),
) -> ApiKeyListResponse:
    """List API keys owned by the authenticated user.

    Args:
        auth_service: Authentication service instance.
        users_service: Users service instance.
        current_user: Authenticated user.
        sub_account_user_id: List keys for a sub-account (parent/admin only).

    Returns:
        List of API keys with metadata (key values are not included).

    Raises:
        HTTPException 403: Cannot view keys for specified sub-account.
    """
    owner_id = current_user["user_id"]
    include_sub_ids = None

    if sub_account_user_id:
        # Explicit sub-account query
        if current_user.get("role") == Role.ADMIN.value:
            owner_id = sub_account_user_id
        elif await users_service.is_parent_of(current_user["user_id"], sub_account_user_id):
            owner_id = sub_account_user_id
        else:
            raise AuthorizationError()
    else:
        # Auto-include sub-account keys for parent users
        user_doc = await users_service.db.users.find_one({"userId": owner_id})
        if user_doc:
            sub_accounts = user_doc.get("subAccounts", [])
            if sub_accounts:
                include_sub_ids = [sa["userId"] for sa in sub_accounts]

    api_keys, total = await auth_service.list_api_keys(owner_id, include_sub_ids)
    return ApiKeyListResponse(
        api_keys=[
            {
                "key_id": k["key_id"],
                "name": k["name"],
                "type": k["type"],
                "owner_id": k["owner_id"],
                "node_id": k.get("node_id"),
                "permissions": k["permissions"],
                "expires_at": k.get("expires_at"),
                "last_used_at": k.get("last_used_at"),
                "usage_count": k.get("usage_count", 0),
                "created_at": k["created_at"],
            }
            for k in api_keys
        ],
        total=total,
    )


@router.delete(
    "/apikeys/{key_id}",
    response_model=ApiKeyRevokeResponse,
    response_model_by_alias=True,
    summary="Revoke API Key",
    description="Revoke an API key.",
)
async def revoke_api_key(
    auth_service: AuthServiceDep,
    current_user: CurrentUser,
    key_id: str = Path(description="API key ID"),
) -> ApiKeyRevokeResponse:
    """Revoke an API key to prevent further use.

    Args:
        auth_service: Authentication service instance.
        current_user: Authenticated user.
        key_id: ID of the API key to revoke.

    Returns:
        Revocation confirmation.

    Raises:
        HTTPException 404: API key not found.
        HTTPException 403: Cannot revoke key owned by another user.
    """
    result = await auth_service.revoke_api_key(
        key_id,
        current_user["user_id"],
        current_user.get("role"),
    )
    return ApiKeyRevokeResponse(
        key_id=result["key_id"],
        revoked=result["revoked"],
        revoked_at=result["revoked_at"],
    )


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    response_model_by_alias=True,
    summary="Get Current User",
    description="Get information about the currently authenticated user or agent.",
)
async def get_current_user_info(
    current_user: CurrentUser,
) -> CurrentUserResponse:
    """Retrieve information about the authenticated user or agent.

    Args:
        current_user: Authenticated user or agent.

    Returns:
        Current user/agent details including role and permissions.
    """
    return CurrentUserResponse(
        type=current_user["type"],
        user_id=current_user.get("user_id"),
        node_id=current_user.get("node_id"),
        username=current_user.get("username"),
        email=current_user.get("email"),
        role=current_user.get("role"),
        permissions=current_user.get("permissions", []),
    )


@router.post(
    "/users",
    response_model=UserInfo,
    response_model_by_alias=True,
    status_code=201,
    summary="Create User",
    description="Create a new user account directly. Admin only.",
    dependencies=[Depends(require_permission("users:create"))],
)
async def create_user(
    request: CreateUserRequest,
    users_service: UsersServiceDep,
) -> UserInfo:
    """Create a new user account directly without registration flow.

    Args:
        request: User details including username, email, password, and role.
        users_service: Users service instance.

    Returns:
        Created user information.

    Raises:
        HTTPException 400: Invalid user data.
        HTTPException 403: Insufficient permissions.
        HTTPException 409: Username or email already exists.
    """
    result = await users_service.create_user(request)
    return UserInfo(
        user_id=result["user_id"],
        username=result["username"],
        email=result["email"],
        role=result["role"],
    )


@router.post(
    "/register/sub/{user_id}",
    response_model=SubAccountLinkResponse,
    response_model_by_alias=True,
    status_code=201,
    summary="Link Sub-Account",
    description="""Link an existing user as a sub-account of the current user.

**Requirements:**
- Current user must be admin or operator
- Target user must have family, viewer, or agent role
- Target user must not already have a parent
- Target user's password is required for verification

**Options:**
- `resetPassword`: If true, resets sub-account password to match parent's password
""",
)
async def link_sub_account(
    request: SubAccountLinkRequest,
    users_service: UsersServiceDep,
    current_user: CurrentUser,
    user_id: str = Path(description="User ID of the account to link as sub-account"),
) -> SubAccountLinkResponse:
    """Link an existing user as a sub-account of the current user.

    Args:
        request: Link request with password verification.
        users_service: Users service instance.
        current_user: Parent user making the request.
        user_id: ID of the user to link as sub-account.

    Returns:
        Link confirmation with sub-account details.

    Raises:
        HTTPException 400: Invalid password or user already has parent.
        HTTPException 403: Target user role not allowed as sub-account.
        HTTPException 404: Target user not found.
    """
    result = await users_service.link_sub_account(
        parent_user_id=current_user["user_id"],
        target_user_id=user_id,
        target_password=request.password,
        reset_password=request.reset_password,
    )
    return SubAccountLinkResponse(
        parent_user_id=result["parent_user_id"],
        sub_account_user_id=result["sub_account_user_id"],
        sub_account_username=result["sub_account_username"],
        sub_account_role=Role(result["sub_account_role"]),
        linked_at=result["linked_at"],
        password_reset=result["password_reset"],
    )


@router.delete(
    "/sub/{user_id}",
    summary="Unlink Sub-Account",
    description="Unlink a sub-account from the current user.",
)
async def unlink_sub_account(
    users_service: UsersServiceDep,
    current_user: CurrentUser,
    user_id: str = Path(description="User ID of the sub-account to unlink"),
) -> dict:
    """Unlink a sub-account from the current user.

    Args:
        users_service: Users service instance.
        current_user: Parent user making the request.
        user_id: ID of the sub-account to unlink.

    Returns:
        Unlink confirmation.

    Raises:
        HTTPException 403: User is not a sub-account of current user.
        HTTPException 404: Sub-account not found.
    """
    result = await users_service.unlink_sub_account(
        parent_user_id=current_user["user_id"],
        sub_account_user_id=user_id,
    )
    return {
        "parentUserId": result["parent_user_id"],
        "subAccountUserId": result["sub_account_user_id"],
        "unlinkedAt": result["unlinked_at"],
        "message": "Sub-account unlinked successfully",
    }
