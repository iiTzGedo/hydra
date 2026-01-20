"""AI/LLM provider management endpoints."""

import structlog
from fastapi import APIRouter, Depends, Path, Query

from hydra.api.v1.core.deps import CurrentUser
from hydra.api.v1.core.exceptions import AuthorizationError
from hydra.api.v1.models.ai import (
    LLMProviderCreate,
    LLMProviderListResponse,
    LLMProviderResponse,
    LLMProviderUpdate,
    LLMProviderValidateResponse,
)
from hydra.api.v1.services.ai import AIService
from hydra.db.mongodb import MongoDB, get_mongodb

router = APIRouter(prefix="/ai", tags=["AI"])
logger = structlog.get_logger(__name__)


async def get_ai_service(mongodb: MongoDB = Depends(get_mongodb)) -> AIService:
    """Get AI service dependency."""
    return AIService(mongodb)


def _check_not_agent(current_user: dict, action: str) -> None:
    """Verify user is not an agent.

    Args:
        current_user: Current authenticated user.
        action: Permission action for error message.

    Raises:
        AuthorizationError: If user is an agent.
    """
    if current_user.get("type") == "agent":
        raise AuthorizationError(f"ai:{action}")


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
    """List all LLM providers configured by the current user.

    Args:
        current_user: Authenticated user making the request.
        ai_service: AI service instance.
        limit: Maximum number of providers to return.
        offset: Number of providers to skip.

    Returns:
        Paginated list of LLM provider configurations.

    Raises:
        HTTPException 403: Agents cannot manage LLM providers.
    """
    _check_not_agent(current_user, "read")

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
    """Create a new LLM provider configuration.

    Args:
        request: Provider creation request with name, type, model, and API key.
        current_user: Authenticated user making the request.
        ai_service: AI service instance.

    Returns:
        Created LLM provider details.

    Raises:
        HTTPException 403: Agents cannot manage LLM providers.
    """
    _check_not_agent(current_user, "create")

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
    """Retrieve a specific LLM provider by ID.

    Args:
        current_user: Authenticated user making the request.
        ai_service: AI service instance.
        providerId: Unique identifier of the LLM provider.

    Returns:
        LLM provider configuration details.

    Raises:
        HTTPException 403: Agents cannot manage LLM providers.
        HTTPException 404: Provider not found.
    """
    _check_not_agent(current_user, "read")

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
    """Update an existing LLM provider configuration.

    Args:
        request: Provider update request with fields to modify.
        current_user: Authenticated user making the request.
        ai_service: AI service instance.
        providerId: Unique identifier of the LLM provider.

    Returns:
        Updated LLM provider details.

    Raises:
        HTTPException 403: Agents cannot manage LLM providers.
        HTTPException 404: Provider not found.
    """
    _check_not_agent(current_user, "update")

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
    """Delete an LLM provider configuration.

    Args:
        current_user: Authenticated user making the request.
        ai_service: AI service instance.
        providerId: Unique identifier of the LLM provider.

    Returns:
        Confirmation of deletion.

    Raises:
        HTTPException 403: Agents cannot manage LLM providers.
        HTTPException 404: Provider not found.
    """
    _check_not_agent(current_user, "delete")

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
    """Validate an LLM provider by testing API connectivity.

    Performs a test API call to verify the provider configuration is correct
    and the API key is valid.

    Args:
        current_user: Authenticated user making the request.
        ai_service: AI service instance.
        providerId: Unique identifier of the LLM provider.

    Returns:
        Validation result with success status and any error details.

    Raises:
        HTTPException 403: Agents cannot manage LLM providers.
        HTTPException 404: Provider not found.
    """
    _check_not_agent(current_user, "read")

    result = await ai_service.validate_provider(
        provider_id=providerId,
        user_id=current_user["user_id"],
    )

    return LLMProviderValidateResponse(**result)
