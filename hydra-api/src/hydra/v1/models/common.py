"""Common response models and utilities."""

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import ConfigDict, BaseModel, Field

T = TypeVar("T")


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""
    
    total: int = Field(description="Total number of items")
    limit: int = Field(description="Maximum items per page")
    offset: int = Field(description="Number of items skipped")


class SuccessResponse(BaseModel, Generic[T]):
    """Standard success response wrapper."""

    data: T
    meta: PaginationMeta | None = None


class ErrorDetail(BaseModel):
    """Error details."""

    code: str = Field(description="Error code")
    message: str = Field(description="Human-readable error message")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional error details")


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: ErrorDetail
    request_id: str = Field(alias="requestId", description="Request correlation ID")


class HealthCheck(BaseModel):
    """Health check response."""
    model_config = ConfigDict(populate_by_name=True)
    
    status: str = Field(description="Overall health status")
    version: str = Field(description="API version")
    timestamp: datetime = Field(description="Current server time")
    checks: dict[str, str] = Field(description="Individual component health checks")
    uptime_seconds: float = Field(alias="uptimeSeconds", description="Uptime in seconds")


class ServiceInfo(BaseModel):
    """Service information response."""
    model_config = ConfigDict(populate_by_name=True)
    
    name: str = Field(description="Service name")
    version: str = Field(description="Service version")
    api_version: str = Field(alias="apiVersion", description="API version")
    stats: dict[str, Any] = Field(description="Service statistics")
    features: dict[str, bool] = Field(description="Enabled features")


# Common field definitions for reuse
class TimestampMixin(BaseModel):
    """Mixin for created/updated timestamps."""
    model_config = ConfigDict(populate_by_name=True)

    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class AuditMixin(BaseModel):
    """Mixin for audit fields."""
    model_config = ConfigDict(populate_by_name=True)

    created_by: str | None = Field(default=None, alias="createdBy")
    updated_by: str | None = Field(default=None, alias="updatedBy")
