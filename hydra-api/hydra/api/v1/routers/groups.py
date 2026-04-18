"""Group management endpoints."""

from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, Query

from hydra.api.v1.core.deps import MongoDBDep, require_permission
from hydra.api.v1.core.model_factory import safe_materialize_many
from hydra.api.v1.models.common import PaginationMeta, SuccessResponse
from hydra.api.v1.models.groups import (
    CreateGroupRequest,
    GroupEntityType,
    GroupListParams,
    GroupMembers,
    GroupResolveResult,
    GroupResponse,
    GroupSummary,
    UpdateGroupRequest,
)
from hydra.api.v1.services.groups import GroupsService

router = APIRouter(prefix="/groups", tags=["Groups"])
logger = structlog.get_logger(__name__)


def get_groups_service(mongodb: MongoDBDep) -> GroupsService:
    """Get groups service dependency."""
    return GroupsService(mongodb)


GroupsServiceDep = Annotated[GroupsService, Depends(get_groups_service)]


@router.get(
    "",
    response_model=SuccessResponse[list[GroupSummary]],
    response_model_by_alias=True,
    summary="List Groups",
    description="List all groups with optional filters and pagination.",
    dependencies=[Depends(require_permission("groups:read"))],
)
async def list_groups(
    groups_service: GroupsServiceDep,
    types: list[GroupEntityType] | None = Query(default=None),
    parent_group_id: str | None = Query(default=None, alias="parentGroupId"),
    tags: list[str] | None = Query(default=None),
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort_by: Literal["groupId", "name", "createdAt", "updatedAt"] = Query(
        default="updatedAt", alias="sortBy"
    ),
    sort_order: Literal["asc", "desc"] = Query(default="desc", alias="sortOrder"),
) -> SuccessResponse[list[GroupSummary]]:
    """Retrieve a paginated list of logical groups.

    Args:
        groups_service: Groups service instance.
        types: Filter by entity types the group can contain.
        parent_group_id: Filter by parent group ID.
        tags: Filter by tags (groups must have all specified tags).
        search: Search query for group name or ID.
        limit: Maximum number of results to return.
        offset: Number of results to skip.
        sort_by: Field to sort by.
        sort_order: Sort direction (ascending or descending).

    Returns:
        Paginated list of group summaries with metadata.

    Raises:
        HTTPException 403: Insufficient permissions.
    """
    params = GroupListParams(
        types=types,
        parent_group_id=parent_group_id,
        tags=tags,
        search=search,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    groups, total = await groups_service.list_groups(params)

    return SuccessResponse(
        data=safe_materialize_many(
            GroupSummary, groups, context="groups_list", id_field="groupId",
        ),
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.post(
    "",
    response_model=SuccessResponse[GroupResponse],
    response_model_by_alias=True,
    status_code=201,
    summary="Create Group",
    description="Create a new group with selector-based membership.",
    dependencies=[Depends(require_permission("groups:create"))],
)
async def create_group(
    request: CreateGroupRequest,
    groups_service: GroupsServiceDep,
) -> SuccessResponse[GroupResponse]:
    """Create a new logical group with dynamic membership.

    Args:
        request: Group configuration including selectors for membership.
        groups_service: Groups service instance.

    Returns:
        Created group details with resolved member counts.

    Raises:
        HTTPException 400: Invalid group configuration or selectors.
        HTTPException 403: Insufficient permissions.
    """
    group = await groups_service.create_group(request)
    return SuccessResponse(data=GroupResponse(**group))


@router.get(
    "/{group_id}",
    response_model=SuccessResponse[GroupResponse],
    response_model_by_alias=True,
    summary="Get Group",
    description="Get detailed information about a specific group.",
    dependencies=[Depends(require_permission("groups:read"))],
)
async def get_group(
    group_id: str,
    groups_service: GroupsServiceDep,
    resolve_members: bool = Query(default=False, alias="resolveMembers"),
    member_limit: int = Query(default=20, alias="memberLimit", ge=1, le=100),
) -> SuccessResponse[GroupResponse]:
    """Retrieve detailed information for a single group.

    Args:
        group_id: Unique identifier of the group.
        groups_service: Groups service instance.
        resolve_members: Include resolved member entities in response.
        member_limit: Maximum members to include when resolving.

    Returns:
        Complete group details including selectors and optionally members.

    Raises:
        HTTPException 404: Group not found.
        HTTPException 403: Insufficient permissions.
    """
    group = await groups_service.get_group(
        group_id,
        resolve_members=resolve_members,
        member_limit=member_limit,
    )
    return SuccessResponse(data=GroupResponse(**group))


@router.patch(
    "/{group_id}",
    response_model=SuccessResponse[GroupResponse],
    response_model_by_alias=True,
    summary="Update Group",
    description="Update group metadata and selectors.",
    dependencies=[Depends(require_permission("groups:update"))],
)
async def update_group(
    group_id: str,
    request: UpdateGroupRequest,
    groups_service: GroupsServiceDep,
) -> SuccessResponse[GroupResponse]:
    """Update configuration for an existing group.

    Args:
        group_id: Unique identifier of the group.
        request: Fields to update including selectors.
        groups_service: Groups service instance.

    Returns:
        Updated group details with recalculated member counts.

    Raises:
        HTTPException 404: Group not found.
        HTTPException 403: Insufficient permissions.
    """
    group = await groups_service.update_group(group_id, request)
    return SuccessResponse(data=GroupResponse(**group))


@router.delete(
    "/{group_id}",
    response_model=SuccessResponse[GroupResponse],
    response_model_by_alias=True,
    summary="Delete Group",
    description="Delete a group.",
    dependencies=[Depends(require_permission("groups:delete"))],
)
async def delete_group(
    group_id: str,
    groups_service: GroupsServiceDep,
) -> SuccessResponse[GroupResponse]:
    """Delete a logical group.

    Args:
        group_id: Unique identifier of the group.
        groups_service: Groups service instance.

    Returns:
        Deleted group details.

    Raises:
        HTTPException 404: Group not found.
        HTTPException 403: Insufficient permissions.
    """
    group = await groups_service.delete_group(group_id)
    return SuccessResponse(data=GroupResponse(**group))


@router.get(
    "/{group_id}/members",
    response_model=SuccessResponse[GroupMembers],
    response_model_by_alias=True,
    summary="Get Group Members",
    description="Get resolved members of a group with pagination.",
    dependencies=[Depends(require_permission("groups:read"))],
)
async def get_group_members(
    group_id: str,
    groups_service: GroupsServiceDep,
    entity_type: GroupEntityType | None = Query(default=None, alias="entityType"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SuccessResponse[GroupMembers]:
    """Retrieve resolved members of a group by evaluating selectors.

    Args:
        group_id: Unique identifier of the group.
        groups_service: Groups service instance.
        entity_type: Filter by entity type (nodes or services).
        limit: Maximum number of results to return.
        offset: Number of results to skip.

    Returns:
        Paginated list of group members with entity details.

    Raises:
        HTTPException 404: Group not found.
        HTTPException 403: Insufficient permissions.
    """
    members, totals = await groups_service.get_group_members(
        group_id,
        entity_type=entity_type,
        limit=limit,
        offset=offset,
    )
    return SuccessResponse(
        data=GroupMembers(**members),
        meta=PaginationMeta(
            total=totals.get("nodes", 0) + totals.get("services", 0),
            limit=limit,
            offset=offset,
        ),
    )


@router.post(
    "/{group_id}/resolve",
    response_model=SuccessResponse[GroupResolveResult],
    response_model_by_alias=True,
    summary="Resolve Group",
    description="Force re-resolution of group membership and update cached counts.",
    dependencies=[Depends(require_permission("groups:update"))],
)
async def resolve_group(
    group_id: str,
    groups_service: GroupsServiceDep,
) -> SuccessResponse[GroupResolveResult]:
    """Force re-evaluation of group membership selectors.

    Args:
        group_id: Unique identifier of the group.
        groups_service: Groups service instance.

    Returns:
        Updated membership counts after re-resolution.

    Raises:
        HTTPException 404: Group not found.
        HTTPException 403: Insufficient permissions.
    """
    result = await groups_service.resolve_group(group_id)
    return SuccessResponse(data=GroupResolveResult(**result))
