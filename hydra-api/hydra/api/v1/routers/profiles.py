"""Profile management endpoints."""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Query

from hydra.api.v1.core.deps import MongoDBDep, require_permission
from hydra.api.v1.models.common import PaginationMeta, SuccessResponse
from hydra.api.v1.models.profiles import (
    ProfileDiff,
    ProfileResponse,
    ProfileSubmission,
    ProfileSummary,
)
from hydra.api.v1.services.profiles import ProfileService

router = APIRouter(prefix="/profiles", tags=["Profiles"])
logger = structlog.get_logger(__name__)


def get_profile_service(mongodb: MongoDBDep) -> ProfileService:
    """Get profile service dependency."""
    return ProfileService(mongodb)


ProfileServiceDep = Annotated[ProfileService, Depends(get_profile_service)]


@router.post(
    "",
    response_model=SuccessResponse[ProfileResponse],
    response_model_by_alias=True,
    summary="Submit Profile",
    description="Submit a new profile from an agent. Automatically calculates version and extracts services.",
    dependencies=[Depends(require_permission("profiles:write"))],
)
async def submit_profile(
    submission: ProfileSubmission,
    profile_service: ProfileServiceDep,
) -> SuccessResponse[ProfileResponse]:
    """Submit a new infrastructure profile from an agent.

    Args:
        submission: Profile data including hardware, software, and network information.
        profile_service: Profile service instance.

    Returns:
        Created profile with calculated version and metadata.

    Raises:
        HTTPException 400: Invalid profile data.
        HTTPException 403: Insufficient permissions.
        HTTPException 404: Node not found.
    """
    profile = await profile_service.submit_profile(submission)
    return SuccessResponse(data=ProfileResponse(**profile))


@router.get(
    "/{profile_id}",
    response_model=SuccessResponse[ProfileResponse],
    response_model_by_alias=True,
    summary="Get Profile",
    description="Get a specific profile by ID.",
    dependencies=[Depends(require_permission("profiles:read"))],
)
async def get_profile(
    profile_id: str,
    profile_service: ProfileServiceDep,
) -> SuccessResponse[ProfileResponse]:
    """Retrieve a specific profile by its unique identifier.

    Args:
        profile_id: Unique identifier of the profile.
        profile_service: Profile service instance.

    Returns:
        Complete profile data including all collected sections.

    Raises:
        HTTPException 404: Profile not found.
        HTTPException 403: Insufficient permissions.
    """
    profile = await profile_service.get_profile(profile_id)
    return SuccessResponse(data=ProfileResponse(**profile))


nodes_router = APIRouter(prefix="/nodes", tags=["Profiles"])


@nodes_router.get(
    "/{node_id}/profiles",
    response_model=SuccessResponse[list[ProfileSummary]],
    response_model_by_alias=True,
    summary="List Node Profiles",
    description="Get profile history for a node.",
    dependencies=[Depends(require_permission("profiles:read"))],
)
async def list_node_profiles(
    node_id: str,
    profile_service: ProfileServiceDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SuccessResponse[list[ProfileSummary]]:
    """Retrieve profile submission history for a specific node.

    Args:
        node_id: Unique identifier of the node.
        profile_service: Profile service instance.
        limit: Maximum number of results to return.
        offset: Number of results to skip.

    Returns:
        Paginated list of profile summaries ordered by submission time.

    Raises:
        HTTPException 404: Node not found.
        HTTPException 403: Insufficient permissions.
    """
    profiles, total = await profile_service.list_node_profiles(node_id, limit, offset)
    return SuccessResponse(
        data=[ProfileSummary(**p) for p in profiles],
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@nodes_router.get(
    "/{node_id}/profiles/latest",
    response_model=SuccessResponse[ProfileResponse],
    response_model_by_alias=True,
    summary="Get Latest Profile",
    description="Get the most recent profile for a node.",
    dependencies=[Depends(require_permission("profiles:read"))],
)
async def get_latest_profile(
    node_id: str,
    profile_service: ProfileServiceDep,
) -> SuccessResponse[ProfileResponse]:
    """Retrieve the most recently submitted profile for a node.

    Args:
        node_id: Unique identifier of the node.
        profile_service: Profile service instance.

    Returns:
        The latest complete profile for the specified node.

    Raises:
        HTTPException 404: Node not found or has no profiles.
        HTTPException 403: Insufficient permissions.
    """
    profile = await profile_service.get_latest_profile(node_id)
    return SuccessResponse(data=ProfileResponse(**profile))


@nodes_router.get(
    "/{node_id}/profiles/diff",
    response_model=SuccessResponse[ProfileDiff],
    response_model_by_alias=True,
    summary="Diff Profiles",
    description="Compare two profiles for a node. If versions not specified, compares the latest two.",
    dependencies=[Depends(require_permission("profiles:read"))],
)
async def diff_profiles(
    node_id: str,
    profile_service: ProfileServiceDep,
    from_version: str | None = Query(default=None, alias="fromVersion"),
    to_version: str | None = Query(default=None, alias="toVersion"),
) -> SuccessResponse[ProfileDiff]:
    """Compare two profiles to identify configuration changes.

    Args:
        node_id: Unique identifier of the node.
        profile_service: Profile service instance.
        from_version: Starting profile version (defaults to second-latest).
        to_version: Ending profile version (defaults to latest).

    Returns:
        Diff result showing added, removed, and modified sections.

    Raises:
        HTTPException 404: Node not found or insufficient profiles for comparison.
        HTTPException 403: Insufficient permissions.
    """
    diff = await profile_service.diff_profiles(node_id, from_version, to_version)
    return SuccessResponse(data=ProfileDiff(**diff))
