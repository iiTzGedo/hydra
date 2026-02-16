"""AI/LLM configuration and provider management endpoints.

Terminology:
- LLMProvider: One of the 4 supported provider types (Anthropic, OpenAI, Ollama, OpenRouter)
- LLMModel: A model available from a provider (fetched dynamically)
- LLMConfig: User's saved configuration (provider + model + API key) for chat sessions
"""

import structlog
from fastapi import APIRouter, Depends, Path, Query

from hydra.api.v1.core.deps import CurrentUser, check_not_agent
from hydra.api.v1.models.ai import (
    GlobalAPIKeyCreate,
    GlobalAPIKeyResponse,
    GlobalAPIKeysResponse,
    GlobalKeyValidateResponse,
    LLMConfigCreate,
    LLMConfigListResponse,
    LLMConfigResponse,
    LLMConfigUpdate,
    LLMConfigValidateResponse,
    LLMModelsResponse,
    LLMProviderType,
)
from hydra.api.v1.services.ai import AIService
from hydra.db.mongodb import MongoDB, get_mongodb

router = APIRouter(prefix="/ai", tags=["AI"])
logger = structlog.get_logger(__name__)


async def get_ai_service(mongodb: MongoDB = Depends(get_mongodb)) -> AIService:
    """Get AI service dependency."""
    return AIService(mongodb)



# =============================================================================
# LLM Configuration Endpoints (User's saved configurations)
# =============================================================================


@router.get(
    "/configs",
    response_model=LLMConfigListResponse,
    response_model_by_alias=True,
    summary="List LLM Configurations",
    description="List saved LLM configurations for the current user.",
)
async def list_configs(
    current_user: CurrentUser,
    ai_service: AIService = Depends(get_ai_service),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> LLMConfigListResponse:
    """List all LLM configurations saved by the current user.

    Args:
        current_user: Authenticated user making the request.
        ai_service: AI service instance.
        limit: Maximum number of configs to return.
        offset: Number of configs to skip.

    Returns:
        Paginated list of LLM configurations.

    Raises:
        HTTPException 403: Agents cannot manage LLM configurations.
    """
    check_not_agent(current_user, "ai:read")

    configs, total = await ai_service.list_configs(
        user_id=current_user["user_id"],
        limit=limit,
        offset=offset,
    )

    return LLMConfigListResponse(
        configs=[LLMConfigResponse(**c) for c in configs],
        total=total,
    )


@router.post(
    "/configs",
    response_model=LLMConfigResponse,
    response_model_by_alias=True,
    status_code=201,
    summary="Create LLM Configuration",
    description="Create a new LLM configuration.",
)
async def create_config(
    request: LLMConfigCreate,
    current_user: CurrentUser,
    ai_service: AIService = Depends(get_ai_service),
) -> LLMConfigResponse:
    """Create a new LLM configuration.

    Args:
        request: Configuration creation request with name, type, model, and API key.
        current_user: Authenticated user making the request.
        ai_service: AI service instance.

    Returns:
        Created LLM configuration details.

    Raises:
        HTTPException 403: Agents cannot manage LLM configurations.
    """
    check_not_agent(current_user, "ai:create")

    result = await ai_service.create_config(
        request=request,
        user_id=current_user["user_id"],
    )

    return LLMConfigResponse(**result)


@router.get(
    "/configs/{config_id}",
    response_model=LLMConfigResponse,
    response_model_by_alias=True,
    summary="Get LLM Configuration",
    description="Get a specific LLM configuration.",
)
async def get_config(
    current_user: CurrentUser,
    ai_service: AIService = Depends(get_ai_service),
    config_id: str = Path(description="Configuration ID"),
) -> LLMConfigResponse:
    """Retrieve a specific LLM configuration by ID.

    Args:
        current_user: Authenticated user making the request.
        ai_service: AI service instance.
        config_id: Unique identifier of the LLM configuration.

    Returns:
        LLM configuration details.

    Raises:
        HTTPException 403: Agents cannot manage LLM configurations.
        HTTPException 404: Configuration not found.
    """
    check_not_agent(current_user, "ai:read")

    result = await ai_service.get_config(
        config_id=config_id,
        user_id=current_user["user_id"],
    )

    return LLMConfigResponse(**result)


@router.put(
    "/configs/{config_id}",
    response_model=LLMConfigResponse,
    response_model_by_alias=True,
    summary="Update LLM Configuration",
    description="Update an LLM configuration.",
)
async def update_config(
    request: LLMConfigUpdate,
    current_user: CurrentUser,
    ai_service: AIService = Depends(get_ai_service),
    config_id: str = Path(description="Configuration ID"),
) -> LLMConfigResponse:
    """Update an existing LLM configuration.

    Args:
        request: Configuration update request with fields to modify.
        current_user: Authenticated user making the request.
        ai_service: AI service instance.
        config_id: Unique identifier of the LLM configuration.

    Returns:
        Updated LLM configuration details.

    Raises:
        HTTPException 403: Agents cannot manage LLM configurations.
        HTTPException 404: Configuration not found.
    """
    check_not_agent(current_user, "ai:update")

    result = await ai_service.update_config(
        config_id=config_id,
        request=request,
        user_id=current_user["user_id"],
    )

    return LLMConfigResponse(**result)


@router.delete(
    "/configs/{config_id}",
    summary="Delete LLM Configuration",
    description="Delete an LLM configuration.",
)
async def delete_config(
    current_user: CurrentUser,
    ai_service: AIService = Depends(get_ai_service),
    config_id: str = Path(description="Configuration ID"),
) -> dict:
    """Delete an LLM configuration.

    Args:
        current_user: Authenticated user making the request.
        ai_service: AI service instance.
        config_id: Unique identifier of the LLM configuration.

    Returns:
        Confirmation of deletion.

    Raises:
        HTTPException 403: Agents cannot manage LLM configurations.
        HTTPException 404: Configuration not found.
    """
    check_not_agent(current_user, "ai:delete")

    result = await ai_service.delete_config(
        config_id=config_id,
        user_id=current_user["user_id"],
    )

    return result


@router.post(
    "/configs/{config_id}/validate",
    response_model=LLMConfigValidateResponse,
    response_model_by_alias=True,
    summary="Validate LLM Configuration",
    description="Validate an LLM configuration by testing the API connection.",
)
async def validate_config(
    current_user: CurrentUser,
    ai_service: AIService = Depends(get_ai_service),
    config_id: str = Path(description="Configuration ID"),
) -> LLMConfigValidateResponse:
    """Validate an LLM configuration by testing API connectivity.

    Performs a test API call to verify the configuration is correct
    and the API key is valid.

    Args:
        current_user: Authenticated user making the request.
        ai_service: AI service instance.
        config_id: Unique identifier of the LLM configuration.

    Returns:
        Validation result with success status and any error details.

    Raises:
        HTTPException 403: Agents cannot manage LLM configurations.
        HTTPException 404: Configuration not found.
    """
    check_not_agent(current_user, "ai:read")

    result = await ai_service.validate_config(
        config_id=config_id,
        user_id=current_user["user_id"],
    )

    return LLMConfigValidateResponse(**result)


# =============================================================================
# LLM Provider Model Endpoints (Available models from providers)
# =============================================================================


@router.get(
    "/providers/{provider_type}/models",
    response_model=LLMModelsResponse,
    response_model_by_alias=True,
    summary="List Provider Models",
    description="Fetch available models from an LLM provider API.",
)
async def list_provider_models(
    current_user: CurrentUser,
    ai_service: AIService = Depends(get_ai_service),
    provider_type: LLMProviderType = Path(description="Provider type to fetch models for"),
    configId: str | None = Query(
        default=None,
        alias="configId",
        description="Optional config ID to use its stored API key",
    ),
    tools_only: bool = Query(
        default=True,
        alias="toolsOnly",
        description="Filter to only show models that support tool calling",
    ),
) -> LLMModelsResponse:
    """Fetch available models from an LLM provider.

    This endpoint queries the provider's API to get a list of available models.
    The API key can come from:
    1. A stored LLM configuration (if configId is specified)
    2. A global API key for the provider type

    Args:
        current_user: Authenticated user making the request.
        ai_service: AI service instance.
        provider_type: The LLM provider type (anthropic, openai, ollama, openrouter).
        configId: Optional ID of a stored config to use its API key.
        tools_only: If true, filter to models that support tool/function calling.

    Returns:
        List of available models with their capabilities and pricing.

    Raises:
        HTTPException 403: Agents cannot fetch provider models.
        HTTPException 404: Config not found (if configId specified).
        HTTPException 400: No API key available for provider.
    """
    check_not_agent(current_user, "ai:read")

    result = await ai_service.fetch_provider_models(
        provider_type=provider_type,
        user_id=current_user["user_id"],
        config_id=configId,
        tools_only=tools_only,
    )

    return LLMModelsResponse(**result)


# =============================================================================
# Global API Key Endpoints
# =============================================================================


@router.get(
    "/global-keys",
    response_model=GlobalAPIKeysResponse,
    response_model_by_alias=True,
    summary="List Global API Keys",
    description="List all configured global API keys for the current user.",
)
async def list_global_keys(
    current_user: CurrentUser,
    ai_service: AIService = Depends(get_ai_service),
) -> GlobalAPIKeysResponse:
    """List all global API keys configured by the current user.

    Args:
        current_user: Authenticated user making the request.
        ai_service: AI service instance.

    Returns:
        List of global API keys (masked).

    Raises:
        HTTPException 403: Agents cannot manage global API keys.
    """
    check_not_agent(current_user, "ai:read")

    result = await ai_service.list_global_keys(user_id=current_user["user_id"])

    return GlobalAPIKeysResponse(**result)


@router.get(
    "/global-keys/{provider_type}",
    response_model=GlobalAPIKeyResponse,
    response_model_by_alias=True,
    summary="Get Global API Key",
    description="Get the global API key for a specific provider.",
)
async def get_global_key(
    current_user: CurrentUser,
    ai_service: AIService = Depends(get_ai_service),
    provider_type: LLMProviderType = Path(description="Provider type"),
) -> GlobalAPIKeyResponse:
    """Get the global API key for a specific provider.

    Args:
        current_user: Authenticated user making the request.
        ai_service: AI service instance.
        provider_type: The LLM provider type.

    Returns:
        Global API key details (masked).

    Raises:
        HTTPException 403: Agents cannot manage global API keys.
        HTTPException 404: No global key configured for this provider.
    """
    check_not_agent(current_user, "ai:read")

    result = await ai_service.get_global_key(
        provider_type=provider_type,
        user_id=current_user["user_id"],
    )

    return GlobalAPIKeyResponse(**result)


@router.put(
    "/global-keys/{provider_type}",
    response_model=GlobalAPIKeyResponse,
    response_model_by_alias=True,
    summary="Set Global API Key",
    description="Set or update the global API key for a provider.",
)
async def set_global_key(
    request: GlobalAPIKeyCreate,
    current_user: CurrentUser,
    ai_service: AIService = Depends(get_ai_service),
    provider_type: LLMProviderType = Path(description="Provider type"),
) -> GlobalAPIKeyResponse:
    """Set or update the global API key for a provider.

    Args:
        request: API key and scopes to set.
        current_user: Authenticated user making the request.
        ai_service: AI service instance.
        provider_type: The LLM provider type.

    Returns:
        Updated global API key details (masked).

    Raises:
        HTTPException 403: Agents cannot manage global API keys.
    """
    check_not_agent(current_user, "ai:create")

    result = await ai_service.set_global_key(
        provider_type=provider_type,
        request=request,
        user_id=current_user["user_id"],
    )

    return GlobalAPIKeyResponse(**result)


@router.delete(
    "/global-keys/{provider_type}",
    summary="Delete Global API Key",
    description="Delete the global API key for a provider.",
)
async def delete_global_key(
    current_user: CurrentUser,
    ai_service: AIService = Depends(get_ai_service),
    provider_type: LLMProviderType = Path(description="Provider type"),
) -> dict:
    """Delete the global API key for a provider.

    Args:
        current_user: Authenticated user making the request.
        ai_service: AI service instance.
        provider_type: The LLM provider type.

    Returns:
        Confirmation of deletion.

    Raises:
        HTTPException 403: Agents cannot manage global API keys.
        HTTPException 404: No global key configured for this provider.
    """
    check_not_agent(current_user, "ai:delete")

    result = await ai_service.delete_global_key(
        provider_type=provider_type,
        user_id=current_user["user_id"],
    )

    return result


@router.post(
    "/global-keys/{provider_type}/validate",
    response_model=GlobalKeyValidateResponse,
    response_model_by_alias=True,
    summary="Validate Global API Key",
    description="Validate a global API key by testing the API connection.",
)
async def validate_global_key(
    current_user: CurrentUser,
    ai_service: AIService = Depends(get_ai_service),
    provider_type: LLMProviderType = Path(description="Provider type"),
) -> GlobalKeyValidateResponse:
    """Validate a global API key by testing API connectivity.

    Args:
        current_user: Authenticated user making the request.
        ai_service: AI service instance.
        provider_type: The LLM provider type.

    Returns:
        Validation result with success status and any error details.

    Raises:
        HTTPException 403: Agents cannot manage global API keys.
        HTTPException 404: No global key configured for this provider.
    """
    check_not_agent(current_user, "ai:read")

    result = await ai_service.validate_global_key(
        provider_type=provider_type,
        user_id=current_user["user_id"],
    )

    return GlobalKeyValidateResponse(**result)
