"""Node management endpoints."""

from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, Path, Query

from hydra.api.v1.core.deps import AuthServiceDep, CurrentUser, MongoDBDep, RegistrationAuth, require_permission
from hydra.api.v1.models.auth import (
    NodeApiKeyRefreshResponse,
    NodeRegistrationRequest,
    NodeRegistrationResponse,
)
from hydra.api.v1.models.common import PaginationMeta, SuccessResponse
from hydra.api.v1.models.nodes import (
    AgentInfo,
    AgentListResponse,
    NodeClass,
    NodeKind,
    NodeListParams,
    NodeResponse,
    NodeStatus,
    NodeSummary,
    NodeType,
    UpdateNodeRequest,
)
from hydra.api.v1.services.nodes import NodeService

router = APIRouter(prefix="/nodes", tags=["Nodes"])
logger = structlog.get_logger(__name__)


def get_node_service(mongodb: MongoDBDep) -> NodeService:
    """Get node service dependency."""
    return NodeService(mongodb)


NodeServiceDep = Annotated[NodeService, Depends(get_node_service)]


@router.get(
    "",
    response_model=SuccessResponse[list[NodeSummary]],
    summary="List Nodes",
    description="List all nodes with optional filters and pagination.",
    dependencies=[Depends(require_permission("nodes:read"))],
)
async def list_nodes(
    node_service: NodeServiceDep,
    # Filter params
    node_class: NodeClass | None = Query(default=None, alias="class"),
    node_type: NodeType | None = Query(default=None, alias="type"),
    kind: NodeKind | None = None,
    status: NodeStatus | None = None,
    tags: list[str] | None = Query(default=None),
    parent_node_id: str | None = Query(default=None, alias="parentNodeId"),
    network_id: str | None = Query(default=None, alias="networkId"),
    search: str | None = None,
    # Pagination
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    # Sorting
    sort_by: Literal["nodeId", "displayName", "registeredAt", "lastProfileAt", "lastUpdated"] = (
        Query(default="lastUpdated", alias="sortBy")
    ),
    sort_order: Literal["asc", "desc"] = Query(default="desc", alias="sortOrder"),
) -> SuccessResponse[list[NodeSummary]]:
    """List nodes with filters."""
    params = NodeListParams(
        node_class=node_class,
        node_type=node_type,
        kind=kind,
        status=status,
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
        data=[NodeSummary(**node) for node in nodes],
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.get(
    "/agents",
    response_model=AgentListResponse,
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
    """List all registered agents with health status."""
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
    summary="Get Node",
    description="Get detailed information about a specific node.",
    dependencies=[Depends(require_permission("nodes:read"))],
)
async def get_node(
    node_id: str,
    node_service: NodeServiceDep,
) -> SuccessResponse[NodeResponse]:
    """Get a single node by ID."""
    node = await node_service.get_node(node_id)
    return SuccessResponse(data=NodeResponse(**node))


@router.patch(
    "/{node_id}",
    response_model=SuccessResponse[NodeResponse],
    summary="Update Node",
    description="Update node metadata (display name, description, tags, etc.).",
    dependencies=[Depends(require_permission("nodes:update"))],
)
async def update_node(
    node_id: str,
    request: UpdateNodeRequest,
    node_service: NodeServiceDep,
) -> SuccessResponse[NodeResponse]:
    """Update a node's metadata."""
    node = await node_service.update_node(node_id, request)
    return SuccessResponse(data=NodeResponse(**node))


@router.delete(
    "/{node_id}",
    response_model=SuccessResponse[NodeResponse],
    summary="Archive Node",
    description="Archive a node (soft delete). The node's data is preserved.",
    dependencies=[Depends(require_permission("nodes:delete"))],
)
async def archive_node(
    node_id: str,
    node_service: NodeServiceDep,
) -> SuccessResponse[NodeResponse]:
    """Archive a node."""
    node = await node_service.archive_node(node_id)
    return SuccessResponse(data=NodeResponse(**node))


@router.get(
    "/{node_id}/children",
    response_model=SuccessResponse[list[NodeSummary]],
    summary="Get Node Children",
    description="Get all child nodes of a parent node.",
    dependencies=[Depends(require_permission("nodes:read"))],
)
async def get_node_children(
    node_id: str,
    node_service: NodeServiceDep,
) -> SuccessResponse[list[NodeSummary]]:
    """Get child nodes."""
    children = await node_service.get_node_children(node_id)
    return SuccessResponse(data=[NodeSummary(**child) for child in children])


# ==================== Node Registration ====================
# Separate router for /node prefix (singular)

node_router = APIRouter(prefix="/node", tags=["Node Registration"])


@node_router.post(
    "/register",
    response_model=NodeRegistrationResponse,
    status_code=201,
    summary="Register Node",
    description="""Register a new node and get API key credentials.

Supports three authentication methods:
1. **X-Registration-Token** header - Pre-generated token for automated deployments
2. **Bearer token** - User JWT (requires admin/operator role)
3. **X-API-Key** header - User API key with nodes:create permission

Example with registration token:
```bash
curl -X POST https://hydra.local/api/v1/node/register \\
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
    """Register a new node and get API key credentials."""
    # Get the user_id from the registration auth (either user or token creator)
    registered_by = registration_auth["user_id"]

    result = await auth_service.register_node(request, registered_by)

    # If using a registration token, mark it as used
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
    )


@node_router.post(
    "/{nodeId}/apikey/refresh",
    response_model=NodeApiKeyRefreshResponse,
    summary="Refresh Node API Key",
    description="Refresh the API key for a node. Previous key is revoked.",
    dependencies=[Depends(require_permission("nodes:update"))],
)
async def refresh_node_api_key(
    auth_service: AuthServiceDep,
    current_user: CurrentUser,
    nodeId: str = Path(description="Node ID"),
) -> NodeApiKeyRefreshResponse:
    """Refresh the API key for a node."""
    result = await auth_service.refresh_node_api_key(nodeId, current_user["user_id"])
    return NodeApiKeyRefreshResponse(
        node_id=result["node_id"],
        api_key_id=result["api_key_id"],
        api_key=result["api_key"],
        previous_key_revoked=result["previous_key_revoked"],
        refreshed_at=result["refreshed_at"],
    )
