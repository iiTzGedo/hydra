"""MCP server configuration management endpoints."""

import structlog
from fastapi import APIRouter, Depends, Path, Query

from hydra.api.v1.core.deps import CurrentUser
from hydra.api.v1.core.exceptions import AuthorizationError
from hydra.api.v1.models.mcp import (
    MCPHealthResponse,
    MCPServerCategory,
    MCPServerCreate,
    MCPServerListResponse,
    MCPServerResponse,
    MCPServerUpdate,
    MCPToolsResponse,
)
from hydra.api.v1.services.mcp import MCPService
from hydra.db.mongodb import MongoDB, get_mongodb

router = APIRouter(prefix="/mcp", tags=["MCP"])
logger = structlog.get_logger(__name__)


async def get_mcp_service(mongodb: MongoDB = Depends(get_mongodb)) -> MCPService:
    """Get MCP service."""
    return MCPService(mongodb)


def _check_not_agent(current_user: dict) -> None:
    """Verify user is not an agent."""
    if current_user.get("type") == "agent":
        raise AuthorizationError("mcp:read")


# ==================== Server Configuration Endpoints ====================


@router.get(
    "/servers",
    response_model=MCPServerListResponse,
    summary="List MCP Servers",
    description="List configured MCP servers for the current user.",
)
async def list_servers(
    current_user: CurrentUser,
    mcp_service: MCPService = Depends(get_mcp_service),
    category: MCPServerCategory | None = Query(default=None, description="Filter by category"),
    enabled: bool | None = Query(default=None, description="Filter by enabled status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> MCPServerListResponse:
    """List MCP servers."""
    _check_not_agent(current_user)

    result = await mcp_service.list_servers(
        user_id=current_user["user_id"],
        category=category.value if category else None,
        enabled_only=enabled if enabled is not None else False,
        limit=limit,
        offset=offset,
    )

    return MCPServerListResponse(
        servers=[MCPServerResponse(**s) for s in result["servers"]],
        total=result["total"],
    )


@router.post(
    "/servers",
    response_model=MCPServerResponse,
    status_code=201,
    summary="Create MCP Server",
    description="Create a new MCP server configuration.",
)
async def create_server(
    request: MCPServerCreate,
    current_user: CurrentUser,
    mcp_service: MCPService = Depends(get_mcp_service),
) -> MCPServerResponse:
    """Create a new MCP server configuration."""
    _check_not_agent(current_user)

    result = await mcp_service.create_server(
        request=request,
        user_id=current_user["user_id"],
    )

    return MCPServerResponse(**result)


@router.get(
    "/servers/{serverId}",
    response_model=MCPServerResponse,
    summary="Get MCP Server",
    description="Get a specific MCP server configuration.",
)
async def get_server(
    current_user: CurrentUser,
    mcp_service: MCPService = Depends(get_mcp_service),
    serverId: str = Path(description="Server ID"),
) -> MCPServerResponse:
    """Get a specific MCP server configuration."""
    _check_not_agent(current_user)

    result = await mcp_service.get_server(
        server_id=serverId,
        user_id=current_user["user_id"],
    )

    return MCPServerResponse(**result)


@router.put(
    "/servers/{serverId}",
    response_model=MCPServerResponse,
    summary="Update MCP Server",
    description="Update an MCP server configuration.",
)
async def update_server(
    request: MCPServerUpdate,
    current_user: CurrentUser,
    mcp_service: MCPService = Depends(get_mcp_service),
    serverId: str = Path(description="Server ID"),
) -> MCPServerResponse:
    """Update an MCP server configuration."""
    _check_not_agent(current_user)

    result = await mcp_service.update_server(
        server_id=serverId,
        request=request,
        user_id=current_user["user_id"],
    )

    return MCPServerResponse(**result)


@router.delete(
    "/servers/{serverId}",
    summary="Delete MCP Server",
    description="Delete an MCP server configuration.",
)
async def delete_server(
    current_user: CurrentUser,
    mcp_service: MCPService = Depends(get_mcp_service),
    serverId: str = Path(description="Server ID"),
) -> dict:
    """Delete an MCP server configuration."""
    _check_not_agent(current_user)

    result = await mcp_service.delete_server(
        server_id=serverId,
        user_id=current_user["user_id"],
    )

    return result


@router.get(
    "/servers/{serverId}/health",
    response_model=MCPHealthResponse,
    summary="Check MCP Server Health",
    description="Check the health/connectivity of an MCP server.",
)
async def check_health(
    current_user: CurrentUser,
    mcp_service: MCPService = Depends(get_mcp_service),
    serverId: str = Path(description="Server ID"),
) -> MCPHealthResponse:
    """Check the health of an MCP server."""
    _check_not_agent(current_user)

    result = await mcp_service.check_health(
        server_id=serverId,
        user_id=current_user["user_id"],
    )

    return MCPHealthResponse(**result)


@router.get(
    "/servers/{serverId}/tools",
    response_model=MCPToolsResponse,
    summary="List MCP Server Tools",
    description="List tools available on an MCP server.",
)
async def list_tools(
    current_user: CurrentUser,
    mcp_service: MCPService = Depends(get_mcp_service),
    serverId: str = Path(description="Server ID"),
) -> MCPToolsResponse:
    """List tools available on an MCP server."""
    _check_not_agent(current_user)

    result = await mcp_service.list_tools(
        server_id=serverId,
        user_id=current_user["user_id"],
    )

    return MCPToolsResponse(**result)
