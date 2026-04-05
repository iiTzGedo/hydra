"""User management endpoints."""

import structlog
from fastapi import APIRouter, Depends, Path, Query

from hydra.api.v1.core.deps import (
    CurrentUser,
    UsersServiceDep,
    require_permission,
)
from hydra.api.v1.core.exceptions import AdminOnlyError, AuthorizationError
from hydra.api.v1.models.auth import (
    ElevateRoleRequest,
    GrantTemporaryRoleRequest,
    Role,
    RoleElevationResponse,
    SubAccountListResponse,
    TemporaryRole,
    TemporaryRoleGrantResponse,
    TemporaryRoleRevokeResponse,
    UserListItem,
    UserListResponse,
)

router = APIRouter(prefix="/users", tags=["Users"])
logger = structlog.get_logger(__name__)


@router.get(
    "",
    response_model=UserListResponse,
    response_model_by_alias=True,
    summary="List Users",
    description="List users. Available to all authenticated users except agents.",
    dependencies=[Depends(require_permission("users:read"))],
)
async def list_users(
    users_service: UsersServiceDep,
    current_user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> UserListResponse:
    """Retrieve a paginated list of users in the system.

    Args:
        users_service: Users service instance.
        current_user: Authenticated user making the request.
        limit: Maximum number of results to return.
        offset: Number of results to skip.

    Returns:
        Paginated list of users with basic information.

    Raises:
        HTTPException 403: Agents cannot list users.
    """
    if current_user.get("type") == "agent" or current_user.get("role") == Role.AGENT.value:
        raise AuthorizationError()

    users, total = await users_service.list_users(limit=limit, offset=offset)
    return UserListResponse(
        users=users,  # type: ignore[arg-type]
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/me/subs",
    response_model=SubAccountListResponse,
    response_model_by_alias=True,
    summary="List My Sub-Accounts",
    description="List sub-accounts for the currently authenticated user.",
)
async def list_my_sub_accounts(
    users_service: UsersServiceDep,
    current_user: CurrentUser,
) -> SubAccountListResponse:
    """List sub-accounts owned by the current user.

    Args:
        users_service: Users service instance.
        current_user: Authenticated user making the request.

    Returns:
        List of sub-accounts with their details.

    Raises:
        HTTPException 403: Agents cannot have sub-accounts.
    """
    if current_user.get("type") == "agent":
        raise AuthorizationError()

    user_id = current_user.get("user_id")
    sub_accounts, total = await users_service.list_sub_accounts(user_id)  # type: ignore[arg-type]
    return SubAccountListResponse(
        parent_user_id=user_id,  # type: ignore[arg-type]
        sub_accounts=[
            {  # type: ignore[misc]
                "user_id": sub["user_id"],
                "username": sub["username"],
                "role": Role(sub["role"]),
                "created_at": sub["created_at"],
            }
            for sub in sub_accounts
        ],
        total=total,
    )


@router.get(
    "/{user_id}/subs",
    response_model=SubAccountListResponse,
    response_model_by_alias=True,
    summary="List Sub-Accounts",
    description="List sub-accounts for a user (self or admin).",
)
async def list_sub_accounts(
    users_service: UsersServiceDep,
    current_user: CurrentUser,
    user_id: str = Path(description="User ID to list sub-accounts for"),
) -> SubAccountListResponse:
    """List sub-accounts for a specific user.

    Args:
        users_service: Users service instance.
        current_user: Authenticated user making the request.
        user_id: ID of the user whose sub-accounts to list.

    Returns:
        List of sub-accounts with their details.

    Raises:
        HTTPException 403: Can only view own sub-accounts or requires admin role.
    """
    if current_user.get("type") == "agent":
        raise AuthorizationError()

    if current_user.get("user_id") != user_id and current_user.get("role") != Role.ADMIN.value:
        raise AuthorizationError()

    sub_accounts, total = await users_service.list_sub_accounts(user_id)
    return SubAccountListResponse(
        parent_user_id=user_id,
        sub_accounts=[
            {  # type: ignore[misc]
                "user_id": sub["user_id"],
                "username": sub["username"],
                "role": Role(sub["role"]),
                "created_at": sub["created_at"],
            }
            for sub in sub_accounts
        ],
        total=total,
    )


@router.delete(
    "/{user_id}",
    response_model=UserListItem,
    response_model_by_alias=True,
    summary="Archive User",
    description="Archive a user (soft delete). Admin only.",
)
async def archive_user(
    users_service: UsersServiceDep,
    current_user: CurrentUser,
    user_id: str = Path(description="User ID to archive"),
) -> UserListItem:
    """Archive a user account without permanently deleting data.

    Args:
        users_service: Users service instance.
        current_user: Admin user making the request.
        user_id: ID of the user to archive.

    Returns:
        Archived user details.

    Raises:
        HTTPException 403: Only admins can archive users.
        HTTPException 404: User not found.
    """
    if current_user.get("type") != "user" or current_user.get("role") != Role.ADMIN.value:
        raise AdminOnlyError("archive_user")

    result = await users_service.archive_user(user_id)
    return UserListItem(**result)


@router.post(
    "/{user_id}/roles/elevate",
    response_model=RoleElevationResponse,
    response_model_by_alias=True,
    summary="Elevate User Role",
    description="Permanently elevate a user's role. Admin only.",
    dependencies=[Depends(require_permission("users:*"))],
)
async def elevate_user_role(
    request: ElevateRoleRequest,
    users_service: UsersServiceDep,
    current_user: CurrentUser,
    user_id: str = Path(description="User ID to elevate"),
) -> RoleElevationResponse:
    """Permanently elevate a user's role to a higher level.

    Args:
        request: New role to assign.
        users_service: Users service instance.
        current_user: Admin user making the request.
        user_id: ID of the user to elevate.

    Returns:
        Elevation details including previous and new roles.

    Raises:
        HTTPException 400: Cannot elevate to requested role.
        HTTPException 403: Insufficient permissions.
        HTTPException 404: User not found.
    """
    result = await users_service.elevate_role(user_id, request, current_user["user_id"])
    return RoleElevationResponse(
        user_id=result["user_id"],
        previous_role=result["previous_role"],
        new_role=result["new_role"],
        elevated_by=result["elevated_by"],
        elevated_at=result["elevated_at"],
    )


@router.post(
    "/{user_id}/roles/grant-temporary",
    response_model=TemporaryRoleGrantResponse,
    response_model_by_alias=True,
    summary="Grant Temporary Role",
    description="Grant a temporary role to a user. Admin only.",
    dependencies=[Depends(require_permission("users:*"))],
)
async def grant_temporary_role(
    request: GrantTemporaryRoleRequest,
    users_service: UsersServiceDep,
    current_user: CurrentUser,
    user_id: str = Path(description="User ID to grant role to"),
) -> TemporaryRoleGrantResponse:
    """Grant a time-limited elevated role to a user.

    Args:
        request: Temporary role details including duration.
        users_service: Users service instance.
        current_user: Admin user making the request.
        user_id: ID of the user to grant role to.

    Returns:
        Updated user with temporary role information.

    Raises:
        HTTPException 403: Insufficient permissions.
        HTTPException 404: User not found.
    """
    result = await users_service.grant_temporary_role(
        user_id, request, current_user["user_id"]
    )

    temp_roles = [
        TemporaryRole(
            role=Role(tr["role"]),
            expires_at=tr["expires_at"],
            granted_by=tr["granted_by"],
            granted_at=tr["granted_at"],
            reason=tr.get("reason"),
        )
        for tr in result.get("temporary_roles", [])
    ]

    return TemporaryRoleGrantResponse(
        user_id=result["user_id"],
        base_role=result["base_role"],
        temporary_roles=temp_roles,
    )


@router.delete(
    "/{user_id}/roles/temporary/{role}",
    response_model=TemporaryRoleRevokeResponse,
    response_model_by_alias=True,
    summary="Revoke Temporary Role",
    description="Revoke a temporary role from a user. Admin only.",
    dependencies=[Depends(require_permission("users:*"))],
)
async def revoke_temporary_role(
    users_service: UsersServiceDep,
    current_user: CurrentUser,
    user_id: str = Path(description="User ID"),
    role: Role = Path(description="Role to revoke"),
) -> TemporaryRoleRevokeResponse:
    """Revoke a temporary role from a user before expiration.

    Args:
        users_service: Users service instance.
        current_user: Admin user making the request.
        user_id: ID of the user.
        role: Temporary role to revoke.

    Returns:
        Revocation confirmation.

    Raises:
        HTTPException 403: Insufficient permissions.
        HTTPException 404: User or temporary role not found.
    """
    result = await users_service.revoke_temporary_role(
        user_id, role.value, current_user["user_id"]
    )
    return TemporaryRoleRevokeResponse(
        user_id=result["user_id"],
        revoked_role=result["revoked_role"],
        revoked_by=result["revoked_by"],
        revoked_at=result["revoked_at"],
    )
