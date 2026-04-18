"""Node management endpoints."""

from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, Path, Query

from hydra.api.v1.core.deps import (
    AuthServiceDep,
    CurrentUser,
    MongoDBDep,
    RegistrationAuth,
    require_permission,
)
from hydra.api.v1.core.model_factory import safe_materialize_many
from hydra.api.v1.models.auth import (
    NodeApiKeyRefreshResponse,
    NodeRegistrationRequest,
    NodeRegistrationResponse,
)
from hydra.api.v1.models.common import PaginationMeta, SuccessResponse
from hydra.api.v1.models.groups import GroupSummary
from hydra.api.v1.models.nodes import (
    AgentInfo,
    AgentListResponse,
    AgentTier,
    NodeClass,
    NodeKind,
    NodeListParams,
    NodeResponse,
    NodeStatus,
    NodeSummary,
    NodeType,
    UpdateNodeRequest,
)
from hydra.api.v1.services.groups import GroupsService
from hydra.api.v1.services.nodes import NodeService

router = APIRouter(prefix="/nodes", tags=["Nodes"])
logger = structlog.get_logger(__name__)


def get_node_service(mongodb: MongoDBDep) -> NodeService:
    """Get node service dependency."""
    return NodeService(mongodb)


NodeServiceDep = Annotated[NodeService, Depends(get_node_service)]


def get_groups_service(mongodb: MongoDBDep) -> GroupsService:
    """Get groups service dependency."""
    return GroupsService(mongodb)


GroupsServiceDep = Annotated[GroupsService, Depends(get_groups_service)]


@router.get(
    "",
    response_model=SuccessResponse[list[NodeSummary]],
    response_model_by_alias=True,
    summary="List Nodes",
    description="List all nodes with optional filters and pagination.",
    dependencies=[Depends(require_permission("nodes:read"))],
)
async def list_nodes(
    node_service: NodeServiceDep,
    node_class: NodeClass | None = Query(default=None, alias="class"),
    node_type: NodeType | None = Query(default=None, alias="type"),
    kind: NodeKind | None = None,
    status: NodeStatus | None = None,
    agent_tier: AgentTier | None = Query(default=None, alias="agentTier"),
    tags: list[str] | None = Query(default=None),
    parent_node_id: str | None = Query(default=None, alias="parentNodeId"),
    network_id: str | None = Query(default=None, alias="networkId"),
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort_by: Literal["nodeId", "displayName", "registeredAt", "lastProfileAt", "lastUpdated"] = (
        Query(default="lastUpdated", alias="sortBy")
    ),
    sort_order: Literal["asc", "desc"] = Query(default="desc", alias="sortOrder"),
) -> SuccessResponse[list[NodeSummary]]:
    """Retrieve a paginated list of nodes with optional filtering.

    Args:
        node_service: Node service instance.
        node_class: Filter by node class (compute, networking, iot).
        node_type: Filter by node type (physical, vm, container, etc.).
        kind: Filter by node kind.
        status: Filter by node status (active, inactive, archived).
        tags: Filter by tags (nodes must have all specified tags).
        parent_node_id: Filter by parent node ID.
        network_id: Filter by network membership.
        search: Search query for node ID or display name.
        limit: Maximum number of results to return.
        offset: Number of results to skip.
        sort_by: Field to sort by.
        sort_order: Sort direction (ascending or descending).

    Returns:
        Paginated list of node summaries with metadata.

    Raises:
        HTTPException 403: Insufficient permissions.
    """
    params = NodeListParams(
        node_class=node_class,
        node_type=node_type,
        kind=kind,
        status=status,
        agent_tier=agent_tier,
        tags=tags,
        parent_node_id=parent_node_id,
        network_id=network_id,
        search=search,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    nodes, total = await node_service.list_nodes(params)

    return SuccessResponse(
        data=safe_materialize_many(
            NodeSummary, nodes, context="nodes_list", id_field="nodeId",
        ),
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.get(
    "/agents",
    response_model=AgentListResponse,
    response_model_by_alias=True,
    summary="List Agents",
    description="""List all registered agents (nodes with active hydra-agent installations).

An agent is a node that has submitted at least one profile. Agents are considered "healthy" if they
have submitted a profile within the last 24 hours.

**Use Cases:**
- Monitor agent deployment status across infrastructure
- Identify agents that have stopped reporting
- Track agent health and profile submission frequency
""",
    dependencies=[Depends(require_permission("nodes:read"))],
)
async def list_agents(
    node_service: NodeServiceDep,
    status: NodeStatus | None = Query(default=None, description="Filter by node status"),
    healthy_only: bool = Query(default=False, alias="healthyOnly", description="Only show healthy agents"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AgentListResponse:
    """Retrieve all registered agents with health status information.

    Args:
        node_service: Node service instance.
        status: Filter by node status.
        healthy_only: Only return agents that reported within 24 hours.
        limit: Maximum number of results to return.
        offset: Number of results to skip.

    Returns:
        List of agents with health status and submission statistics.

    Raises:
        HTTPException 403: Insufficient permissions.
    """
    result = await node_service.list_agents(
        status=status.value if status else None,
        healthy_only=healthy_only,
        limit=limit,
        offset=offset,
    )

    return AgentListResponse(
        agents=[AgentInfo(**agent) for agent in result["agents"]],
        total=result["total"],
        active=result["active"],
        limit=result["limit"],
        offset=result["offset"],
    )


@router.get(
    "/{node_id}",
    response_model=SuccessResponse[NodeResponse],
    response_model_by_alias=True,
    summary="Get Node",
    description="Get detailed information about a specific node.",
    dependencies=[Depends(require_permission("nodes:read"))],
)
async def get_node(
    node_id: str,
    node_service: NodeServiceDep,
) -> SuccessResponse[NodeResponse]:
    """Retrieve detailed information for a single node.

    Args:
        node_id: Unique identifier of the node.
        node_service: Node service instance.

    Returns:
        Complete node details including metadata and configuration.

    Raises:
        HTTPException 404: Node not found.
        HTTPException 403: Insufficient permissions.
    """
    node = await node_service.get_node(node_id)
    return SuccessResponse(data=NodeResponse(**node))


@router.patch(
    "/{node_id}",
    response_model=SuccessResponse[NodeResponse],
    response_model_by_alias=True,
    summary="Update Node",
    description="Update node metadata (display name, description, tags, etc.).",
    dependencies=[Depends(require_permission("nodes:update"))],
)
async def update_node(
    node_id: str,
    request: UpdateNodeRequest,
    node_service: NodeServiceDep,
) -> SuccessResponse[NodeResponse]:
    """Update metadata for an existing node.

    Args:
        node_id: Unique identifier of the node.
        request: Fields to update.
        node_service: Node service instance.

    Returns:
        Updated node details.

    Raises:
        HTTPException 404: Node not found.
        HTTPException 403: Insufficient permissions.
    """
    node = await node_service.update_node(node_id, request)
    return SuccessResponse(data=NodeResponse(**node))


@router.delete(
    "/{node_id}",
    response_model=SuccessResponse[NodeResponse],
    response_model_by_alias=True,
    summary="Archive Node",
    description="Archive a node (soft delete). The node's data is preserved.",
    dependencies=[Depends(require_permission("nodes:delete"))],
)
async def archive_node(
    node_id: str,
    node_service: NodeServiceDep,
) -> SuccessResponse[NodeResponse]:
    """Archive a node without permanently deleting its data.

    Args:
        node_id: Unique identifier of the node.
        node_service: Node service instance.

    Returns:
        Archived node details with updated status.

    Raises:
        HTTPException 404: Node not found.
        HTTPException 403: Insufficient permissions.
    """
    node = await node_service.archive_node(node_id)
    return SuccessResponse(data=NodeResponse(**node))


@router.get(
    "/{node_id}/children",
    response_model=SuccessResponse[list[NodeSummary]],
    response_model_by_alias=True,
    summary="Get Node Children",
    description="Get all child nodes of a parent node.",
    dependencies=[Depends(require_permission("nodes:read"))],
)
async def get_node_children(
    node_id: str,
    node_service: NodeServiceDep,
) -> SuccessResponse[list[NodeSummary]]:
    """Retrieve all child nodes for a given parent node.

    Args:
        node_id: Unique identifier of the parent node.
        node_service: Node service instance.

    Returns:
        List of child node summaries.

    Raises:
        HTTPException 404: Parent node not found.
        HTTPException 403: Insufficient permissions.
    """
    children = await node_service.get_node_children(node_id)
    return SuccessResponse(
        data=safe_materialize_many(
            NodeSummary, children, context="node_children", id_field="nodeId",
        ),
    )


@router.get(
    "/{node_id}/groups",
    response_model=SuccessResponse[list[GroupSummary]],
    response_model_by_alias=True,
    summary="Get Node Groups",
    description="Get all groups that a node belongs to based on selector matching.",
    dependencies=[Depends(require_permission("nodes:read"))],
)
async def get_node_groups(
    node_id: str,
    groups_service: GroupsServiceDep,
) -> SuccessResponse[list[GroupSummary]]:
    """Retrieve all groups containing a specific node.

    Evaluates group selectors server-side to avoid N+1 client queries.

    Args:
        node_id: Unique identifier of the node.
        groups_service: Groups service instance.

    Returns:
        List of group summaries the node belongs to.
    """
    groups = await groups_service.get_node_groups(node_id)
    return SuccessResponse(data=groups)  # type: ignore[arg-type]


node_router = APIRouter(prefix="/nodes", tags=["Node Registration"])


@node_router.post(
    "/register",
    response_model=NodeRegistrationResponse,
    response_model_by_alias=True,
    status_code=201,
    summary="Register Node",
    description="""Register a new node and get API key credentials.

Supports three authentication methods:
1. **X-Registration-Token** header - Pre-generated token for automated deployments
2. **Bearer token** - User JWT (requires admin/operator role)
3. **X-API-Key** header - User API key with nodes:create permission

Example with registration token:
```bash
curl -X POST https://hydra.local/api/v1/nodes/register \\
  -H "X-Registration-Token: reg_abc123..." \\
  -H "Content-Type: application/json" \\
  -d '{"nodeId": "my-server", "class": "compute", "type": "physical", "displayName": "My Server"}'
```
""",
)
async def register_node(
    request: NodeRegistrationRequest,
    auth_service: AuthServiceDep,
    registration_auth: RegistrationAuth,
) -> NodeRegistrationResponse:
    """Register a new infrastructure node and provision API credentials.

    Args:
        request: Node registration details including ID, class, and type.
        auth_service: Authentication service instance.
        registration_auth: Validated registration authentication context.

    Returns:
        Registration result with API key for the new node.

    Raises:
        HTTPException 400: Invalid node configuration.
        HTTPException 401: Invalid or expired registration token.
        HTTPException 409: Node ID already exists.
    """
    registered_by = registration_auth["user_id"]

    result = await auth_service.register_node(request, registered_by)

    if registration_auth["type"] == "registration_token":
        await auth_service.use_registration_token(
            registration_auth["token"], result["node_id"]
        )

    return NodeRegistrationResponse(
        node_id=result["node_id"],
        api_key=result["api_key"],
        api_key_id=result["api_key_id"],
        registered_by=result["registered_by"],
        registered_at=result["registered_at"],
        status=result["status"],
        agent_server_secret=result.get("agent_server_secret"),
    )


@node_router.post(
    "/{node_id}/apikey/refresh",
    response_model=NodeApiKeyRefreshResponse,
    response_model_by_alias=True,
    summary="Refresh Node API Key",
    description="Refresh the API key for a node. Previous key is revoked.",
    dependencies=[Depends(require_permission("nodes:update"))],
)
async def refresh_node_api_key(
    auth_service: AuthServiceDep,
    current_user: CurrentUser,
    node_id: str = Path(description="Node ID"),
) -> NodeApiKeyRefreshResponse:
    """Generate a new API key for a node and revoke the previous one.

    Args:
        auth_service: Authentication service instance.
        current_user: Authenticated user making the request.
        node_id: Unique identifier of the node.

    Returns:
        New API key credentials and revocation confirmation.

    Raises:
        HTTPException 404: Node not found.
        HTTPException 403: Insufficient permissions.
    """
    result = await auth_service.refresh_node_api_key(node_id, current_user["user_id"])
    return NodeApiKeyRefreshResponse(
        node_id=result["node_id"],
        api_key_id=result["api_key_id"],
        api_key=result["api_key"],
        previous_key_revoked=result["previous_key_revoked"],
        refreshed_at=result["refreshed_at"],
    )
