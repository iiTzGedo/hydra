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
    summary="Submit Profile",
    description="Submit a new profile from an agent. Automatically calculates version and extracts services.",
    dependencies=[Depends(require_permission("profiles:write"))],
)
async def submit_profile(
    submission: ProfileSubmission,
    profile_service: ProfileServiceDep,
) -> SuccessResponse[ProfileResponse]:
    """Submit a new profile."""
    profile = await profile_service.submit_profile(submission)
    return SuccessResponse(data=ProfileResponse(**profile))


@router.get(
    "/{profile_id}",
    response_model=SuccessResponse[ProfileResponse],
    summary="Get Profile",
    description="Get a specific profile by ID.",
    dependencies=[Depends(require_permission("profiles:read"))],
)
async def get_profile(
    profile_id: str,
    profile_service: ProfileServiceDep,
) -> SuccessResponse[ProfileResponse]:
    """Get a profile by ID."""
    profile = await profile_service.get_profile(profile_id)
    return SuccessResponse(data=ProfileResponse(**profile))


# Node-specific profile endpoints (nested under /nodes)
nodes_router = APIRouter(prefix="/nodes", tags=["Profiles"])


@nodes_router.get(
    "/{node_id}/profiles",
    response_model=SuccessResponse[list[ProfileSummary]],
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
    """List profiles for a node."""
    profiles, total = await profile_service.list_node_profiles(node_id, limit, offset)
    return SuccessResponse(
        data=[ProfileSummary(**p) for p in profiles],
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@nodes_router.get(
    "/{node_id}/profiles/latest",
    response_model=SuccessResponse[ProfileResponse],
    summary="Get Latest Profile",
    description="Get the most recent profile for a node.",
    dependencies=[Depends(require_permission("profiles:read"))],
)
async def get_latest_profile(
    node_id: str,
    profile_service: ProfileServiceDep,
) -> SuccessResponse[ProfileResponse]:
    """Get the latest profile for a node."""
    profile = await profile_service.get_latest_profile(node_id)
    return SuccessResponse(data=ProfileResponse(**profile))


@nodes_router.get(
    "/{node_id}/profiles/diff",
    response_model=SuccessResponse[ProfileDiff],
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
    """Compare two profiles."""
    diff = await profile_service.diff_profiles(node_id, from_version, to_version)
    return SuccessResponse(data=ProfileDiff(**diff))
