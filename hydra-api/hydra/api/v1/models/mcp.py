"""MCP server configuration models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class MCPServerCategory(str, Enum):
    """MCP server category."""

    INFRASTRUCTURE = "infrastructure"
    MONITORING = "monitoring"
    VERSION_CONTROL = "version-control"
    DATABASES = "databases"
    CLOUD = "cloud"
    DEVELOPMENT = "development"
    OTHER = "other"


class MCPAuthType(str, Enum):
    """MCP server authentication type."""

    NONE = "none"
    API_KEY = "api_key"
    BEARER = "bearer"


class MCPServerStatus(str, Enum):
    """MCP server connection status."""

    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


# ==================== Request Models ====================


class MCPServerCreate(BaseModel):
    """Request to create an MCP server configuration."""

    name: str = Field(min_length=1, max_length=128)
    endpoint: str = Field(min_length=1, description="MCP server endpoint URL")
    description: str | None = Field(default=None, max_length=1024)
    category: MCPServerCategory = Field(default=MCPServerCategory.OTHER)
    auth_type: MCPAuthType = Field(default=MCPAuthType.NONE, alias="authType")
    auth_value: str | None = Field(
        default=None,
        alias="authValue",
        description="API key or bearer token (encrypted at rest)",
    )
    enabled: bool = Field(default=True)
    docs_url: str | None = Field(default=None, alias="docsUrl")

    model_config = {"populate_by_name": True}


class MCPServerUpdate(BaseModel):
    """Request to update an MCP server configuration."""

    name: str | None = Field(default=None, max_length=128)
    endpoint: str | None = Field(default=None)
    description: str | None = Field(default=None, max_length=1024)
    category: MCPServerCategory | None = None
    auth_type: MCPAuthType | None = Field(default=None, alias="authType")
    auth_value: str | None = Field(default=None, alias="authValue")
    enabled: bool | None = None
    docs_url: str | None = Field(default=None, alias="docsUrl")

    model_config = {"populate_by_name": True}


# ==================== Response Models ====================


class MCPServerResponse(BaseModel):
    """MCP server configuration response."""

    server_id: str = Field(alias="serverId")
    name: str
    endpoint: str
    description: str | None = None
    category: MCPServerCategory
    auth_type: MCPAuthType = Field(alias="authType")
    auth_configured: bool = Field(alias="authConfigured")
    enabled: bool
    status: MCPServerStatus = Field(default=MCPServerStatus.UNKNOWN)
    last_health_check: datetime | None = Field(default=None, alias="lastHealthCheck")
    docs_url: str | None = Field(default=None, alias="docsUrl")
    owner_id: str = Field(alias="ownerId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}


class MCPServerListResponse(BaseModel):
    """List of MCP server configurations response."""

    servers: list[MCPServerResponse]
    total: int


class MCPHealthResponse(BaseModel):
    """MCP server health check response."""

    server_id: str = Field(alias="serverId")
    status: MCPServerStatus
    message: str
    checked_at: datetime = Field(alias="checkedAt")
    tools: list[str] | None = Field(default=None, description="Available tools if healthy")
    resources: list[str] | None = Field(default=None, description="Available resources if healthy")

    model_config = {"populate_by_name": True}


class MCPToolInfo(BaseModel):
    """Information about an MCP tool."""

    name: str
    description: str | None = None


class MCPToolsResponse(BaseModel):
    """Response for listing MCP server tools."""

    server_id: str = Field(alias="serverId")
    tools: list[MCPToolInfo]

    model_config = {"populate_by_name": True}
