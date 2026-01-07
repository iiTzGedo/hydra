"""AI/LLM provider models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class LLMProviderType(str, Enum):
    """Supported LLM provider types."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OLLAMA = "ollama"


class LLMProviderCreate(BaseModel):
    """Request to create an LLM provider configuration."""

    name: str = Field(min_length=1, max_length=128, description="Display name for the provider")
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
        description="Default model to use (e.g., claude-3-5-sonnet-20241022)",
    )
    is_default: bool = Field(
        default=False,
        alias="isDefault",
        description="Set as the default provider",
    )

    model_config = {"populate_by_name": True}


class LLMProviderUpdate(BaseModel):
    """Request to update an LLM provider configuration."""

    name: str | None = Field(default=None, max_length=128)
    api_key: str | None = Field(default=None, alias="apiKey", min_length=1)
    base_url: str | None = Field(default=None, alias="baseUrl")
    model: str | None = Field(default=None, max_length=128)
    is_default: bool | None = Field(default=None, alias="isDefault")

    model_config = {"populate_by_name": True}


class LLMProviderResponse(BaseModel):
    """LLM provider response (API key masked)."""

    provider_id: str = Field(alias="providerId")
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


class LLMProviderListResponse(BaseModel):
    """List of LLM providers response."""

    providers: list[LLMProviderResponse]
    total: int


class LLMProviderValidateResponse(BaseModel):
    """Response for provider validation."""

    provider_id: str = Field(alias="providerId")
    is_valid: bool = Field(alias="isValid")
    message: str
    validated_at: datetime = Field(alias="validatedAt")
    models: list[str] | None = Field(default=None, description="Available models if validation succeeded")

    model_config = {"populate_by_name": True}
