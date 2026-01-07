"""AI/LLM provider management endpoints."""

import structlog
from fastapi import APIRouter, Depends, Path, Query

from hydra.api.v1.core.deps import (
    CurrentUser,
    require_permission,
)
from hydra.api.v1.core.exceptions import AuthorizationError
from hydra.api.v1.models.ai import (
    LLMProviderCreate,
    LLMProviderListResponse,
    LLMProviderResponse,
    LLMProviderUpdate,
    LLMProviderValidateResponse,
)
from hydra.api.v1.models.auth import Role
from hydra.api.v1.services.ai import AIService
from hydra.db.mongodb import MongoDB, get_mongodb

router = APIRouter(prefix="/ai", tags=["AI"])
logger = structlog.get_logger(__name__)


async def get_ai_service(mongodb: MongoDB = Depends(get_mongodb)) -> AIService:
    """Get AI service."""
    return AIService(mongodb)


# ==================== LLM Provider Management ====================


@router.get(
    "/models",
    response_model=LLMProviderListResponse,
    summary="List LLM Providers",
    description="List configured LLM providers for the current user.",
)
async def list_providers(
    current_user: CurrentUser,
    ai_service: AIService = Depends(get_ai_service),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> LLMProviderListResponse:
    """List LLM providers."""
    # Agents cannot manage LLM providers
    if current_user.get("type") == "agent":
        raise AuthorizationError("ai:read")

    result = await ai_service.list_providers(
        user_id=current_user["user_id"],
        limit=limit,
        offset=offset,
    )

    return LLMProviderListResponse(
        providers=[LLMProviderResponse(**p) for p in result["providers"]],
        total=result["total"],
    )


@router.post(
    "/models",
    response_model=LLMProviderResponse,
    status_code=201,
    summary="Create LLM Provider",
    description="Create a new LLM provider configuration.",
)
async def create_provider(
    request: LLMProviderCreate,
    current_user: CurrentUser,
    ai_service: AIService = Depends(get_ai_service),
) -> LLMProviderResponse:
    """Create a new LLM provider."""
    # Agents cannot manage LLM providers
    if current_user.get("type") == "agent":
        raise AuthorizationError("ai:create")

    result = await ai_service.create_provider(
        request=request,
        user_id=current_user["user_id"],
    )

    return LLMProviderResponse(**result)


@router.get(
    "/models/{providerId}",
    response_model=LLMProviderResponse,
    summary="Get LLM Provider",
    description="Get a specific LLM provider configuration.",
)
async def get_provider(
    current_user: CurrentUser,
    ai_service: AIService = Depends(get_ai_service),
    providerId: str = Path(description="Provider ID"),
) -> LLMProviderResponse:
    """Get a specific LLM provider."""
    # Agents cannot manage LLM providers
    if current_user.get("type") == "agent":
        raise AuthorizationError("ai:read")

    result = await ai_service.get_provider(
        provider_id=providerId,
        user_id=current_user["user_id"],
    )

    return LLMProviderResponse(**result)


@router.put(
    "/models/{providerId}",
    response_model=LLMProviderResponse,
    summary="Update LLM Provider",
    description="Update an LLM provider configuration.",
)
async def update_provider(
    request: LLMProviderUpdate,
    current_user: CurrentUser,
    ai_service: AIService = Depends(get_ai_service),
    providerId: str = Path(description="Provider ID"),
) -> LLMProviderResponse:
    """Update an LLM provider."""
    # Agents cannot manage LLM providers
    if current_user.get("type") == "agent":
        raise AuthorizationError("ai:update")

    result = await ai_service.update_provider(
        provider_id=providerId,
        request=request,
        user_id=current_user["user_id"],
    )

    return LLMProviderResponse(**result)


@router.delete(
    "/models/{providerId}",
    summary="Delete LLM Provider",
    description="Delete an LLM provider configuration.",
)
async def delete_provider(
    current_user: CurrentUser,
    ai_service: AIService = Depends(get_ai_service),
    providerId: str = Path(description="Provider ID"),
) -> dict:
    """Delete an LLM provider."""
    # Agents cannot manage LLM providers
    if current_user.get("type") == "agent":
        raise AuthorizationError("ai:delete")

    result = await ai_service.delete_provider(
        provider_id=providerId,
        user_id=current_user["user_id"],
    )

    return result


@router.post(
    "/models/{providerId}/validate",
    response_model=LLMProviderValidateResponse,
    summary="Validate LLM Provider",
    description="Validate an LLM provider by testing the API connection.",
)
async def validate_provider(
    current_user: CurrentUser,
    ai_service: AIService = Depends(get_ai_service),
    providerId: str = Path(description="Provider ID"),
) -> LLMProviderValidateResponse:
    """Validate an LLM provider."""
    # Agents cannot manage LLM providers
    if current_user.get("type") == "agent":
        raise AuthorizationError("ai:read")

    result = await ai_service.validate_provider(
        provider_id=providerId,
        user_id=current_user["user_id"],
    )

    return LLMProviderValidateResponse(**result)
