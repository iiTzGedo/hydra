"""AI/LLM models for providers, configurations, and dynamic model fetching.

Terminology:
- LLMProvider: One of the 4 supported provider types (Anthropic, OpenAI, Ollama, OpenRouter)
- LLMModel: A model available from a provider (e.g., claude-3-5-sonnet, gpt-4o)
- LLMConfig: User's saved configuration (provider + model + API key) for a chat session
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class LLMProviderType(StrEnum):
    """Supported LLM provider types."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OLLAMA = "ollama"
    OPENROUTER = "openrouter"


# =============================================================================
# LLM Configuration Models (User's saved provider+model configurations)
# =============================================================================


class LLMConfigCreate(BaseModel):
    """Request to create an LLM configuration."""

    name: str = Field(min_length=1, max_length=128, description="Display name for the configuration")
    type: LLMProviderType = Field(description="Provider type")
    api_key: str | None = Field(
        default=None,
        alias="apiKey",
        min_length=1,
        description="API key (not required for Ollama)",
    )
    base_url: str | None = Field(
        default=None,
        alias="baseUrl",
        description="Custom base URL (required for Ollama, optional for others)",
    )
    model: str = Field(
        min_length=1,
        max_length=128,
        description="Model to use (e.g., claude-3-5-sonnet-20241022)",
    )
    is_default: bool = Field(
        default=False,
        alias="isDefault",
        description="Set as the default configuration",
    )

    model_config = {"populate_by_name": True}


class LLMConfigUpdate(BaseModel):
    """Request to update an LLM configuration."""

    name: str | None = Field(default=None, max_length=128)
    api_key: str | None = Field(default=None, alias="apiKey", min_length=1)
    base_url: str | None = Field(default=None, alias="baseUrl")
    model: str | None = Field(default=None, max_length=128)
    is_default: bool | None = Field(default=None, alias="isDefault")

    model_config = {"populate_by_name": True}


class LLMConfigResponse(BaseModel):
    """LLM configuration response (API key masked)."""

    config_id: str = Field(alias="configId")
    name: str
    type: LLMProviderType
    api_key_last4: str | None = Field(alias="apiKeyLast4", description="Last 4 characters of API key")
    api_key_set: bool = Field(alias="apiKeySet", description="Whether an API key is configured")
    base_url: str | None = Field(alias="baseUrl")
    model: str
    is_default: bool = Field(alias="isDefault")
    is_valid: bool | None = Field(alias="isValid", description="Last validation result")
    last_validated_at: datetime | None = Field(alias="lastValidatedAt")
    created_by: str = Field(alias="createdBy")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}


class LLMConfigListResponse(BaseModel):
    """List of LLM configurations response."""

    configs: list[LLMConfigResponse]
    total: int


class LLMConfigValidateResponse(BaseModel):
    """Response for configuration validation."""

    config_id: str = Field(alias="configId")
    is_valid: bool = Field(alias="isValid")
    message: str
    validated_at: datetime = Field(alias="validatedAt")
    models: list[str] | None = Field(default=None, description="Available models if validation succeeded")

    model_config = {"populate_by_name": True}


# =============================================================================
# LLM Model Models (Models available from providers)
# =============================================================================


class LLMModel(BaseModel):
    """A model available from an LLM provider."""

    id: str = Field(description="Model identifier (e.g., claude-3-5-sonnet-20241022)")
    name: str = Field(description="Human-readable model name")
    context_window: int = Field(alias="contextWindow", description="Maximum context window in tokens")
    supports_tools: bool = Field(alias="supportsTools", description="Whether model supports tool/function calling")
    supports_vision: bool = Field(default=False, alias="supportsVision", description="Whether model supports image inputs")
    supports_reasoning: bool = Field(default=False, alias="supportsReasoning", description="Whether model supports extended thinking/reasoning")
    cost_per_1k_input: float | None = Field(default=None, alias="costPer1kInput", description="Cost per 1K input tokens in USD")
    cost_per_1k_output: float | None = Field(default=None, alias="costPer1kOutput", description="Cost per 1K output tokens in USD")

    model_config = {"populate_by_name": True}


class LLMModelsResponse(BaseModel):
    """Response containing available models from a provider."""

    models: list[LLMModel]
    provider: LLMProviderType
    fetched_at: datetime = Field(alias="fetchedAt")
    cached: bool = Field(default=False, description="Whether response was served from cache")

    model_config = {"populate_by_name": True}


# =============================================================================
# Global API Key Models
# =============================================================================


class GlobalKeyScope(StrEnum):
    """Scopes for global API key usage."""

    CHAT = "chat"  # Use for chat conversations
    META = "meta"  # Use for listing models, capabilities, costs
    TITLE_GEN = "title_gen"  # Use for auto-generating session titles


class GlobalAPIKeyCreate(BaseModel):
    """Request to create or update a global API key."""

    api_key: str = Field(alias="apiKey", min_length=1, description="API key for the provider")
    scopes: list[GlobalKeyScope] = Field(
        default=[GlobalKeyScope.CHAT, GlobalKeyScope.META, GlobalKeyScope.TITLE_GEN],
        description="Scopes this key should be used for",
    )

    model_config = {"populate_by_name": True}


class GlobalAPIKeyResponse(BaseModel):
    """Global API key response (key masked)."""

    provider_type: LLMProviderType = Field(alias="providerType")
    api_key_last4: str = Field(alias="apiKeyLast4", description="Last 4 characters of API key")
    api_key_set: bool = Field(alias="apiKeySet", description="Whether an API key is configured")
    scopes: list[GlobalKeyScope]
    is_valid: bool | None = Field(alias="isValid", description="Last validation result")
    last_validated_at: datetime | None = Field(alias="lastValidatedAt")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}


class GlobalAPIKeysResponse(BaseModel):
    """Response containing all global API keys for a user."""

    keys: list[GlobalAPIKeyResponse]


class GlobalKeyValidateResponse(BaseModel):
    """Response for global key validation."""

    provider_type: LLMProviderType = Field(alias="providerType")
    is_valid: bool = Field(alias="isValid")
    message: str
    validated_at: datetime = Field(alias="validatedAt")

    model_config = {"populate_by_name": True}
