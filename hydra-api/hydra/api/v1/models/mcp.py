"""MCP server configuration models."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class MCPServerCategory(StrEnum):
    """MCP server category."""

    INFRASTRUCTURE = "infrastructure"
    MONITORING = "monitoring"
    VERSION_CONTROL = "version-control"
    DATABASES = "databases"
    CLOUD = "cloud"
    DEVELOPMENT = "development"
    OTHER = "other"


class MCPAuthType(StrEnum):
    """MCP server authentication type."""

    NONE = "none"
    API_KEY = "api_key"
    BEARER = "bearer"


class MCPServerStatus(StrEnum):
    """MCP server connection status."""

    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


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

    model_config = ConfigDict(populate_by_name=True)


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

    model_config = ConfigDict(populate_by_name=True)


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

    model_config = ConfigDict(populate_by_name=True)


class MCPServerListResponse(BaseModel):
    """List of MCP server configurations response."""

    servers: list[MCPServerResponse]
    total: int
    limit: int
    offset: int


class MCPHealthResponse(BaseModel):
    """MCP server health check response."""

    server_id: str = Field(alias="serverId")
    status: MCPServerStatus
    message: str
    checked_at: datetime = Field(alias="checkedAt")
    tools: list[str] | None = Field(default=None, description="Available tools if healthy")
    resources: list[str] | None = Field(default=None, description="Available resources if healthy")

    model_config = ConfigDict(populate_by_name=True)


class MCPToolInfo(BaseModel):
    """Information about an MCP tool."""

    name: str
    description: str | None = None


class MCPToolsResponse(BaseModel):
    """Response for listing MCP server tools."""

    server_id: str = Field(alias="serverId")
    tools: list[MCPToolInfo]

    model_config = ConfigDict(populate_by_name=True)


class MCPResourceInfo(BaseModel):
    """Information about an MCP resource."""

    uri: str
    name: str | None = None
    description: str | None = None
    mime_type: str | None = Field(default=None, alias="mimeType")

    model_config = ConfigDict(populate_by_name=True)


class MCPResourcesResponse(BaseModel):
    """Response for listing MCP server resources."""

    server_id: str = Field(alias="serverId")
    resources: list[MCPResourceInfo]

    model_config = ConfigDict(populate_by_name=True)


class MCPPromptArgument(BaseModel):
    """Argument definition for an MCP prompt."""

    name: str
    description: str | None = None
    required: bool = False


class MCPPromptInfo(BaseModel):
    """Information about an MCP prompt."""

    name: str
    description: str | None = None
    arguments: list[MCPPromptArgument] = Field(default_factory=list)


class MCPPromptsResponse(BaseModel):
    """Response for listing MCP server prompts."""

    server_id: str = Field(alias="serverId")
    prompts: list[MCPPromptInfo]

    model_config = ConfigDict(populate_by_name=True)


class HydraMCPHealthResponse(BaseModel):
    """Dedicated health response for the built-in Hydra MCP server."""

    status: MCPServerStatus
    message: str
    checked_at: datetime = Field(alias="checkedAt")
    server_name: str | None = Field(default=None, alias="serverName")
    version: str | None = None
    tools_count: int = Field(default=0, alias="toolsCount")
    prompts_count: int = Field(default=0, alias="promptsCount")
    resources_count: int = Field(default=0, alias="resourcesCount")
    endpoint: str | None = None

    model_config = ConfigDict(populate_by_name=True)
