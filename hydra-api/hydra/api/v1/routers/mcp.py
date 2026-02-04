"""MCP server configuration management endpoints."""

import structlog
from fastapi import APIRouter, Depends, Path, Query

from hydra.api.v1.core.deps import CurrentUser, check_not_agent
from hydra.api.v1.models.mcp import (
    HydraMCPHealthResponse,
    MCPHealthResponse,
    MCPPromptsResponse,
    MCPServerCategory,
    MCPServerCreate,
    MCPServerListResponse,
    MCPServerResponse,
    MCPServerUpdate,
    MCPResourcesResponse,
    MCPToolsResponse,
)
from hydra.api.v1.services.mcp import MCPService
from hydra.db.mongodb import MongoDB, get_mongodb

router = APIRouter(prefix="/mcp", tags=["MCP"])
logger = structlog.get_logger(__name__)


async def get_mcp_service(mongodb: MongoDB = Depends(get_mongodb)) -> MCPService:
    """Get MCP service dependency."""
    return MCPService(mongodb)



# ============================================================================
# Hydra MCP (Built-in) Endpoints
# ============================================================================


@router.get(
    "/hydra/health",
    response_model=HydraMCPHealthResponse,
    summary="Check Hydra MCP Health",
    description="Check the health of the built-in Hydra MCP server.",
)
async def check_hydra_health(
    current_user: CurrentUser,
    mcp_service: MCPService = Depends(get_mcp_service),
) -> HydraMCPHealthResponse:
    """Check the health of the built-in Hydra MCP server.

    This endpoint directly checks the configured Hydra MCP server without
    requiring a database lookup. It returns detailed status including
    available tools count, prompts count, and resources count.

    Args:
        current_user: Authenticated user making the request.
        mcp_service: MCP service instance.

    Returns:
        Health status of the Hydra MCP server.

    Raises:
        HTTPException 403: Agents cannot access MCP endpoints.
    """
    check_not_agent(current_user, "mcp:read")

    result = await mcp_service.check_hydra_health()

    return HydraMCPHealthResponse(**result)


@router.get(
    "/hydra/tools",
    response_model=MCPToolsResponse,
    summary="List Hydra MCP Tools",
    description="List tools available on the built-in Hydra MCP server.",
)
async def list_hydra_tools(
    current_user: CurrentUser,
    mcp_service: MCPService = Depends(get_mcp_service),
) -> MCPToolsResponse:
    """List all tools available on the built-in Hydra MCP server.

    Args:
        current_user: Authenticated user making the request.
        mcp_service: MCP service instance.

    Returns:
        List of tools with their names and descriptions.

    Raises:
        HTTPException 403: Agents cannot access MCP endpoints.
    """
    check_not_agent(current_user, "mcp:read")

    result = await mcp_service.list_hydra_tools()

    return MCPToolsResponse(**result)


@router.get(
    "/hydra/prompts",
    response_model=MCPPromptsResponse,
    summary="List Hydra MCP Prompts",
    description="List prompts available on the built-in Hydra MCP server.",
)
async def list_hydra_prompts(
    current_user: CurrentUser,
    mcp_service: MCPService = Depends(get_mcp_service),
) -> MCPPromptsResponse:
    """List all prompts available on the built-in Hydra MCP server.

    Args:
        current_user: Authenticated user making the request.
        mcp_service: MCP service instance.

    Returns:
        List of prompts with their names, descriptions, and arguments.

    Raises:
        HTTPException 403: Agents cannot access MCP endpoints.
    """
    check_not_agent(current_user, "mcp:read")

    result = await mcp_service.list_hydra_prompts()

    return MCPPromptsResponse(**result)


# ============================================================================
# User MCP Server Endpoints
# ============================================================================


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
    """List all MCP servers configured by the current user.

    Args:
        current_user: Authenticated user making the request.
        mcp_service: MCP service instance.
        category: Optional filter by server category.
        enabled: Optional filter by enabled status.
        limit: Maximum number of servers to return.
        offset: Number of servers to skip.

    Returns:
        Paginated list of MCP server configurations.

    Raises:
        HTTPException 403: Agents cannot manage MCP servers.
    """
    check_not_agent(current_user, "mcp:read")

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
    """Create a new MCP server configuration.

    Args:
        request: Server creation request with name, URL, category, and optional auth.
        current_user: Authenticated user making the request.
        mcp_service: MCP service instance.

    Returns:
        Created MCP server details.

    Raises:
        HTTPException 403: Agents cannot manage MCP servers.
    """
    check_not_agent(current_user, "mcp:read")

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
    """Retrieve a specific MCP server by ID.

    Args:
        current_user: Authenticated user making the request.
        mcp_service: MCP service instance.
        serverId: Unique identifier of the MCP server.

    Returns:
        MCP server configuration details.

    Raises:
        HTTPException 403: Agents cannot manage MCP servers.
        HTTPException 404: Server not found.
    """
    check_not_agent(current_user, "mcp:read")

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
    """Update an existing MCP server configuration.

    Args:
        request: Server update request with fields to modify.
        current_user: Authenticated user making the request.
        mcp_service: MCP service instance.
        serverId: Unique identifier of the MCP server.

    Returns:
        Updated MCP server details.

    Raises:
        HTTPException 403: Agents cannot manage MCP servers.
        HTTPException 404: Server not found.
    """
    check_not_agent(current_user, "mcp:read")

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
    """Delete an MCP server configuration.

    Args:
        current_user: Authenticated user making the request.
        mcp_service: MCP service instance.
        serverId: Unique identifier of the MCP server.

    Returns:
        Confirmation of deletion.

    Raises:
        HTTPException 403: Agents cannot manage MCP servers.
        HTTPException 404: Server not found.
    """
    check_not_agent(current_user, "mcp:read")

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
    """Check the health and connectivity of an MCP server.

    Performs a connection test to verify the server is reachable and responding.

    Args:
        current_user: Authenticated user making the request.
        mcp_service: MCP service instance.
        serverId: Unique identifier of the MCP server.

    Returns:
        Health status including connectivity, latency, and any errors.

    Raises:
        HTTPException 403: Agents cannot manage MCP servers.
        HTTPException 404: Server not found.
    """
    check_not_agent(current_user, "mcp:read")

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
    """List all tools available on an MCP server.

    Queries the MCP server for its tool manifest and returns tool definitions.

    Args:
        current_user: Authenticated user making the request.
        mcp_service: MCP service instance.
        serverId: Unique identifier of the MCP server.

    Returns:
        List of tools with their names, descriptions, and input schemas.

    Raises:
        HTTPException 403: Agents cannot manage MCP servers.
        HTTPException 404: Server not found.
    """
    check_not_agent(current_user, "mcp:read")

    result = await mcp_service.list_tools(
        server_id=serverId,
        user_id=current_user["user_id"],
    )

    return MCPToolsResponse(**result)


@router.get(
    "/servers/{serverId}/resources",
    response_model=MCPResourcesResponse,
    summary="List MCP Server Resources",
    description="List resources available on an MCP server.",
)
async def list_resources(
    current_user: CurrentUser,
    mcp_service: MCPService = Depends(get_mcp_service),
    serverId: str = Path(description="Server ID"),
) -> MCPResourcesResponse:
    """List all resources available on an MCP server.

    Queries the MCP server for its resource manifest and returns resource definitions.

    Args:
        current_user: Authenticated user making the request.
        mcp_service: MCP service instance.
        serverId: Unique identifier of the MCP server.

    Returns:
        List of resources with their URIs, names, and descriptions.

    Raises:
        HTTPException 403: Agents cannot manage MCP servers.
        HTTPException 404: Server not found.
    """
    check_not_agent(current_user, "mcp:read")

    result = await mcp_service.list_resources(
        server_id=serverId,
        user_id=current_user["user_id"],
    )

    return MCPResourcesResponse(**result)


@router.get(
    "/servers/{serverId}/prompts",
    response_model=MCPPromptsResponse,
    summary="List MCP Server Prompts",
    description="List prompts available on an MCP server.",
)
async def list_prompts(
    current_user: CurrentUser,
    mcp_service: MCPService = Depends(get_mcp_service),
    serverId: str = Path(description="Server ID"),
) -> MCPPromptsResponse:
    """List all prompts available on an MCP server.

    Queries the MCP server for its prompt manifest and returns prompt definitions.

    Args:
        current_user: Authenticated user making the request.
        mcp_service: MCP service instance.
        serverId: Unique identifier of the MCP server.

    Returns:
        List of prompts with their names, descriptions, and arguments.

    Raises:
        HTTPException 403: Agents cannot manage MCP servers.
        HTTPException 404: Server not found.
    """
    check_not_agent(current_user, "mcp:read")

    result = await mcp_service.list_prompts(
        server_id=serverId,
        user_id=current_user["user_id"],
    )

    return MCPPromptsResponse(**result)
