"""Plugin management endpoints."""

from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, Path, Query

from hydra.api.v1.core.deps import (
    CurrentUser,
    MongoDBDep,
    require_permission,
)
from hydra.api.v1.models.common import PaginationMeta, SuccessResponse
from hydra.api.v1.models.plugins import (
    BindNodeRequest,
    PluginCategory,
    PluginClassification,
    PluginHealthStatus,
    PluginListParams,
    PluginResponse,
    PluginStatus,
    PluginSummary,
    RegisterPluginRequest,
    UpdatePluginConfigRequest,
)
from hydra.api.v1.services.plugins.service import PluginService

router = APIRouter(prefix="/plugins", tags=["Plugins"])
logger = structlog.get_logger(__name__)


def get_plugin_service(mongodb: MongoDBDep) -> PluginService:
    """Get plugin service dependency."""
    return PluginService(mongodb)


PluginServiceDep = Annotated[PluginService, Depends(get_plugin_service)]


# ── List / Create ───────────────────────────────────────────────────


@router.get(
    "",
    response_model=SuccessResponse[list[PluginSummary]],
    response_model_by_alias=True,
    summary="List Plugins",
    description="List registered plugins with optional filters and pagination.",
    dependencies=[Depends(require_permission("plugins:read"))],
)
async def list_plugins(
    plugin_service: PluginServiceDep,
    current_user: CurrentUser,
    status: PluginStatus | None = None,
    classification: PluginClassification | None = None,
    category: PluginCategory | None = None,
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort_by: Literal["createdAt", "name", "status"] = Query(default="createdAt", alias="sortBy"),
    sort_order: Literal["asc", "desc"] = Query(default="desc", alias="sortOrder"),
) -> SuccessResponse[list[PluginSummary]]:
    """Retrieve a paginated list of plugins.

    Args:
        plugin_service: Plugin service instance.
        current_user: Authenticated user context.
        status: Filter by plugin status.
        classification: Filter by classification tier.
        category: Filter by plugin category.
        search: Search query for plugin name, description, or ID.
        limit: Maximum number of results to return.
        offset: Number of results to skip.
        sort_by: Field to sort by.
        sort_order: Sort direction.

    Returns:
        Paginated list of plugin summaries with metadata.
    """
    user_id = current_user.get("user_id") or current_user.get("userId", "")

    params = PluginListParams(
        status=status,
        classification=classification,
        category=category,
        search=search,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    plugins, total = await plugin_service.list_plugins(params, user_id)

    return SuccessResponse(
        data=[PluginSummary(**plugin) for plugin in plugins],
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.post(
    "",
    response_model=SuccessResponse[PluginResponse],
    response_model_by_alias=True,
    status_code=201,
    summary="Register Plugin",
    description="Register a new plugin with the platform.",
    dependencies=[Depends(require_permission("plugins:write"))],
)
async def register_plugin(
    request: RegisterPluginRequest,
    plugin_service: PluginServiceDep,
    current_user: CurrentUser,
) -> SuccessResponse[PluginResponse]:
    """Register a new plugin.

    Args:
        request: Plugin registration details including manifest and configuration.
        plugin_service: Plugin service instance.
        current_user: Authenticated user context.

    Returns:
        The registered plugin.
    """
    user_id = current_user.get("user_id") or current_user.get("userId", "")
    plugin = await plugin_service.register_plugin(request, user_id)
    return SuccessResponse(data=PluginResponse(**plugin))


# ── Single plugin operations ────────────────────────────────────────


@router.get(
    "/{plugin_id}",
    response_model=SuccessResponse[PluginResponse],
    response_model_by_alias=True,
    summary="Get Plugin",
    description="Get detailed information about a specific plugin.",
    dependencies=[Depends(require_permission("plugins:read"))],
)
async def get_plugin(
    plugin_service: PluginServiceDep,
    plugin_id: str = Path(description="Plugin identifier (e.g. plg::docker)"),
) -> SuccessResponse[PluginResponse]:
    """Retrieve a single plugin by its identifier.

    Args:
        plugin_service: Plugin service instance.
        plugin_id: Unique identifier of the plugin.

    Returns:
        Complete plugin details.
    """
    plugin = await plugin_service.get_plugin(plugin_id)
    return SuccessResponse(data=PluginResponse(**plugin))


@router.patch(
    "/{plugin_id}/config",
    response_model=SuccessResponse[PluginResponse],
    response_model_by_alias=True,
    summary="Configure Plugin",
    description="Update plugin configuration and/or credentials.",
    dependencies=[Depends(require_permission("plugins:write"))],
)
async def configure_plugin(
    request: UpdatePluginConfigRequest,
    plugin_service: PluginServiceDep,
    current_user: CurrentUser,
    plugin_id: str = Path(description="Plugin identifier"),
) -> SuccessResponse[PluginResponse]:
    """Update plugin configuration.

    Args:
        request: Configuration update details.
        plugin_service: Plugin service instance.
        current_user: Authenticated user context.
        plugin_id: Unique identifier of the plugin.

    Returns:
        Updated plugin details.
    """
    user_id = current_user.get("user_id") or current_user.get("userId", "")
    plugin = await plugin_service.configure_plugin(plugin_id, request, user_id)
    return SuccessResponse(data=PluginResponse(**plugin))


@router.post(
    "/{plugin_id}/enable",
    response_model=SuccessResponse[PluginResponse],
    response_model_by_alias=True,
    summary="Enable Plugin",
    description="Enable a plugin and attempt activation via health check.",
    dependencies=[Depends(require_permission("plugins:write"))],
)
async def enable_plugin(
    plugin_service: PluginServiceDep,
    current_user: CurrentUser,
    plugin_id: str = Path(description="Plugin identifier"),
) -> SuccessResponse[PluginResponse]:
    """Enable a plugin.

    Args:
        plugin_service: Plugin service instance.
        current_user: Authenticated user context.
        plugin_id: Unique identifier of the plugin.

    Returns:
        Updated plugin details (status may be 'enabled' or 'active').
    """
    user_id = current_user.get("user_id") or current_user.get("userId", "")
    plugin = await plugin_service.enable_plugin(plugin_id, user_id)
    return SuccessResponse(data=PluginResponse(**plugin))


@router.post(
    "/{plugin_id}/disable",
    response_model=SuccessResponse[PluginResponse],
    response_model_by_alias=True,
    summary="Disable Plugin",
    description="Disable an active or enabled plugin.",
    dependencies=[Depends(require_permission("plugins:write"))],
)
async def disable_plugin(
    plugin_service: PluginServiceDep,
    current_user: CurrentUser,
    plugin_id: str = Path(description="Plugin identifier"),
) -> SuccessResponse[PluginResponse]:
    """Disable a plugin.

    Args:
        plugin_service: Plugin service instance.
        current_user: Authenticated user context.
        plugin_id: Unique identifier of the plugin.

    Returns:
        Updated plugin details with disabled status.
    """
    user_id = current_user.get("user_id") or current_user.get("userId", "")
    plugin = await plugin_service.disable_plugin(plugin_id, user_id)
    return SuccessResponse(data=PluginResponse(**plugin))


@router.delete(
    "/{plugin_id}",
    response_model=SuccessResponse[PluginResponse],
    response_model_by_alias=True,
    summary="Uninstall Plugin",
    description="Uninstall a plugin (soft delete).",
    dependencies=[Depends(require_permission("plugins:write"))],
)
async def uninstall_plugin(
    plugin_service: PluginServiceDep,
    current_user: CurrentUser,
    plugin_id: str = Path(description="Plugin identifier"),
) -> SuccessResponse[PluginResponse]:
    """Uninstall a plugin.

    Args:
        plugin_service: Plugin service instance.
        current_user: Authenticated user context.
        plugin_id: Unique identifier of the plugin.

    Returns:
        The uninstalled plugin details.
    """
    user_id = current_user.get("user_id") or current_user.get("userId", "")
    plugin = await plugin_service.uninstall_plugin(plugin_id, user_id)
    return SuccessResponse(data=PluginResponse(**plugin))


# ── Health ──────────────────────────────────────────────────────────


@router.get(
    "/{plugin_id}/health",
    response_model=SuccessResponse[PluginHealthStatus],
    response_model_by_alias=True,
    summary="Get Plugin Health",
    description="Get the current health status of a plugin.",
    dependencies=[Depends(require_permission("plugins:read"))],
)
async def get_plugin_health(
    plugin_service: PluginServiceDep,
    plugin_id: str = Path(description="Plugin identifier"),
) -> SuccessResponse[PluginHealthStatus]:
    """Retrieve plugin health status.

    Args:
        plugin_service: Plugin service instance.
        plugin_id: Unique identifier of the plugin.

    Returns:
        Current health status details.
    """
    health = await plugin_service.get_health(plugin_id)
    return SuccessResponse(data=PluginHealthStatus(**health))


@router.post(
    "/{plugin_id}/test",
    response_model_by_alias=True,
    summary="Test Plugin Connection",
    description="Test plugin connectivity without changing state.",
    dependencies=[Depends(require_permission("plugins:read"))],
)
async def test_plugin_connection(
    plugin_service: PluginServiceDep,
    plugin_id: str = Path(description="Plugin identifier"),
) -> dict[str, object]:
    """Test plugin connectivity.

    Args:
        plugin_service: Plugin service instance.
        plugin_id: Unique identifier of the plugin.

    Returns:
        Connection test results.
    """
    return await plugin_service.test_connection(plugin_id)


# ── Node Bindings ───────────────────────────────────────────────────


@router.post(
    "/{plugin_id}/nodes/{node_id}",
    response_model=SuccessResponse[PluginResponse],
    response_model_by_alias=True,
    status_code=201,
    summary="Bind Node to Plugin",
    description="Create a binding between a plugin and a node.",
    dependencies=[Depends(require_permission("plugins:write"))],
)
async def bind_node(
    plugin_service: PluginServiceDep,
    current_user: CurrentUser,
    plugin_id: str = Path(description="Plugin identifier"),
    node_id: str = Path(description="Node identifier"),
    request: BindNodeRequest | None = None,
) -> SuccessResponse[PluginResponse]:
    """Bind a node to a plugin.

    Args:
        plugin_service: Plugin service instance.
        current_user: Authenticated user context.
        plugin_id: Unique identifier of the plugin.
        node_id: Unique identifier of the node to bind.
        request: Optional binding configuration.

    Returns:
        Updated plugin details with new binding.
    """
    user_id = current_user.get("user_id") or current_user.get("userId", "")
    bind_req = request or BindNodeRequest()
    plugin = await plugin_service.bind_node(plugin_id, node_id, bind_req, user_id)
    return SuccessResponse(data=PluginResponse(**plugin))


@router.delete(
    "/{plugin_id}/nodes/{node_id}",
    response_model=SuccessResponse[PluginResponse],
    response_model_by_alias=True,
    summary="Unbind Node from Plugin",
    description="Remove a node binding from a plugin.",
    dependencies=[Depends(require_permission("plugins:write"))],
)
async def unbind_node(
    plugin_service: PluginServiceDep,
    current_user: CurrentUser,
    plugin_id: str = Path(description="Plugin identifier"),
    node_id: str = Path(description="Node identifier"),
) -> SuccessResponse[PluginResponse]:
    """Unbind a node from a plugin.

    Args:
        plugin_service: Plugin service instance.
        current_user: Authenticated user context.
        plugin_id: Unique identifier of the plugin.
        node_id: Unique identifier of the node to unbind.

    Returns:
        Updated plugin details without the removed binding.
    """
    user_id = current_user.get("user_id") or current_user.get("userId", "")
    plugin = await plugin_service.unbind_node(plugin_id, node_id, user_id)
    return SuccessResponse(data=PluginResponse(**plugin))
