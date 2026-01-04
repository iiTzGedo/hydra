"""User management endpoints."""

import structlog
from fastapi import APIRouter, Depends, Path, Query

from hydra_api.core.exceptions import AdminOnlyError, AuthorizationError
from hydra_api.core.deps import (
    CurrentUser,
    UsersServiceDep,
    require_permission,
)
from hydra_api.models.auth import (
    ElevateRoleRequest,
    GrantTemporaryRoleRequest,
    Role,
    RoleElevationResponse,
    TemporaryRole,
    TemporaryRoleGrantResponse,
    TemporaryRoleRevokeResponse,
    UserListItem,
    UserListResponse,
)

router = APIRouter(prefix="/users", tags=["Users"])
logger = structlog.get_logger(__name__)


# ==================== User Directory ====================


@router.get(
    "",
    response_model=UserListResponse,
    summary="List Users",
    description="List users. Available to all authenticated users except agents.",
)
async def list_users(
    users_service: UsersServiceDep,
    current_user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> UserListResponse:
    """List users."""
    if current_user.get("type") == "agent" or current_user.get("role") == Role.AGENT.value:
        raise AuthorizationError()

    result = await users_service.list_users(limit=limit, offset=offset)
    return UserListResponse(
        users=result["users"],
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
    )


@router.delete(
    "/{userId}",
    response_model=UserListItem,
    summary="Archive User",
    description="Archive a user (soft delete). Admin only.",
)
async def archive_user(
    users_service: UsersServiceDep,
    current_user: CurrentUser,
    userId: str = Path(description="User ID to archive"),
) -> UserListItem:
    """Archive a user."""
    if current_user.get("type") != "user" or current_user.get("role") != Role.ADMIN.value:
        raise AdminOnlyError("archive_user")

    result = await users_service.archive_user(userId)
    return UserListItem(**result)


# ==================== Role Management ====================


@router.post(
    "/{userId}/roles/elevate",
    response_model=RoleElevationResponse,
    summary="Elevate User Role",
    description="Permanently elevate a user's role. Admin only.",
    dependencies=[Depends(require_permission("users:*"))],
)
async def elevate_user_role(
    request: ElevateRoleRequest,
    users_service: UsersServiceDep,
    current_user: CurrentUser,
    userId: str = Path(description="User ID to elevate"),
) -> RoleElevationResponse:
    """Permanently elevate a user's role."""
    result = await users_service.elevate_role(userId, request, current_user["user_id"])
    return RoleElevationResponse(
        user_id=result["user_id"],
        previous_role=result["previous_role"],
        new_role=result["new_role"],
        elevated_by=result["elevated_by"],
        elevated_at=result["elevated_at"],
    )


@router.post(
    "/{userId}/roles/grant-temporary",
    response_model=TemporaryRoleGrantResponse,
    summary="Grant Temporary Role",
    description="Grant a temporary role to a user. Admin only.",
    dependencies=[Depends(require_permission("users:*"))],
)
async def grant_temporary_role(
    request: GrantTemporaryRoleRequest,
    users_service: UsersServiceDep,
    current_user: CurrentUser,
    userId: str = Path(description="User ID to grant role to"),
) -> TemporaryRoleGrantResponse:
    """Grant a temporary role to a user."""
    result = await users_service.grant_temporary_role(
        userId, request, current_user["user_id"]
    )

    # Convert temporary roles to response format
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
    "/{userId}/roles/temporary/{role}",
    response_model=TemporaryRoleRevokeResponse,
    summary="Revoke Temporary Role",
    description="Revoke a temporary role from a user. Admin only.",
    dependencies=[Depends(require_permission("users:*"))],
)
async def revoke_temporary_role(
    users_service: UsersServiceDep,
    current_user: CurrentUser,
    userId: str = Path(description="User ID"),
    role: Role = Path(description="Role to revoke"),
) -> TemporaryRoleRevokeResponse:
    """Revoke a temporary role from a user."""
    result = await users_service.revoke_temporary_role(
        userId, role.value, current_user["user_id"]
    )
    return TemporaryRoleRevokeResponse(
        user_id=result["user_id"],
        revoked_role=result["revoked_role"],
        revoked_by=result["revoked_by"],
        revoked_at=result["revoked_at"],
    )
