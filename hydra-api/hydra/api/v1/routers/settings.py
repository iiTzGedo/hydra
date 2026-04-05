"""Settings management endpoints."""

import structlog
from fastapi import APIRouter, Depends

from hydra.api.v1.core.deps import CurrentUser, check_not_agent, require_permission
from hydra.api.v1.models.settings import (
    SystemSettingsResponse,
    SystemSettingsUpdate,
    UserSettingsResponse,
    UserSettingsUpdate,
)
from hydra.api.v1.services.settings import SettingsService
from hydra.db.mongodb import MongoDB, get_mongodb

router = APIRouter(prefix="/settings", tags=["Settings"])
logger = structlog.get_logger(__name__)


async def get_settings_service(mongodb: MongoDB = Depends(get_mongodb)) -> SettingsService:
    """Get settings service dependency."""
    return SettingsService(mongodb)



@router.get(
    "",
    response_model=UserSettingsResponse,
    response_model_by_alias=True,
    summary="Get User Settings",
    description="Get settings for the current user.",
)
async def get_user_settings(
    current_user: CurrentUser,
    settings_service: SettingsService = Depends(get_settings_service),
) -> UserSettingsResponse:
    """Get settings for the current user.

    Args:
        current_user: Authenticated user making the request.
        settings_service: Settings service instance.

    Returns:
        User settings including preferences and UI configuration.

    Raises:
        HTTPException 403: Agents cannot access settings.
    """
    check_not_agent(current_user, "settings:read")

    result = await settings_service.get_user_settings(
        user_id=current_user["user_id"],
    )

    return UserSettingsResponse(**result)


@router.put(
    "",
    response_model=UserSettingsResponse,
    response_model_by_alias=True,
    summary="Update User Settings",
    description="Update settings for the current user.",
)
async def update_user_settings(
    request: UserSettingsUpdate,
    current_user: CurrentUser,
    settings_service: SettingsService = Depends(get_settings_service),
) -> UserSettingsResponse:
    """Update settings for the current user.

    Args:
        request: Settings update request with fields to modify.
        current_user: Authenticated user making the request.
        settings_service: Settings service instance.

    Returns:
        Updated user settings.

    Raises:
        HTTPException 403: Agents cannot access settings.
    """
    check_not_agent(current_user, "settings:read")

    result = await settings_service.update_user_settings(
        user_id=current_user["user_id"],
        request=request,
    )

    return UserSettingsResponse(**result)


@router.get(
    "/system",
    response_model=SystemSettingsResponse,
    response_model_by_alias=True,
    summary="Get System Settings",
    description="Get system-wide settings. Admin only.",
    dependencies=[Depends(require_permission("settings:*"))],
)
async def get_system_settings(
    _current_user: CurrentUser,
    settings_service: SettingsService = Depends(get_settings_service),
) -> SystemSettingsResponse:
    """Get system-wide settings.

    Args:
        current_user: Authenticated admin user making the request.
        settings_service: Settings service instance.

    Returns:
        System settings including global configuration.

    Raises:
        HTTPException 403: Insufficient permissions (admin only).
    """
    result = await settings_service.get_system_settings()

    return SystemSettingsResponse(**result)


@router.put(
    "/system",
    response_model=SystemSettingsResponse,
    response_model_by_alias=True,
    summary="Update System Settings",
    description="Update system-wide settings. Admin only.",
    dependencies=[Depends(require_permission("settings:*"))],
)
async def update_system_settings(
    request: SystemSettingsUpdate,
    current_user: CurrentUser,
    settings_service: SettingsService = Depends(get_settings_service),
) -> SystemSettingsResponse:
    """Update system-wide settings.

    Args:
        request: System settings update request with fields to modify.
        current_user: Authenticated admin user making the request.
        settings_service: Settings service instance.

    Returns:
        Updated system settings.

    Raises:
        HTTPException 403: Insufficient permissions (admin only).
    """
    result = await settings_service.update_system_settings(
        request=request,
        admin_user_id=current_user["user_id"],
    )

    return SystemSettingsResponse(**result)
