"""Global search endpoints."""

import structlog
from fastapi import APIRouter, Depends, Query

from hydra.api.v1.core.deps import CurrentUser
from hydra.api.v1.core.exceptions import AuthorizationError
from hydra.api.v1.models.search import (
    SearchEntityType,
    SearchResponse,
    SearchResultGroup,
    SearchResultItem,
)
from hydra.api.v1.services.search import SearchService
from hydra.db.mongodb import MongoDB, get_mongodb

router = APIRouter(tags=["Search"])
logger = structlog.get_logger(__name__)


async def get_search_service(mongodb: MongoDB = Depends(get_mongodb)) -> SearchService:
    """Get search service."""
    return SearchService(mongodb)


@router.get(
    "/search",
    response_model=SearchResponse,
    response_model_by_alias=True,
    summary="Global Search",
    description="Search across nodes, services, groups, and networks.",
)
async def search(
    current_user: CurrentUser,
    search_service: SearchService = Depends(get_search_service),
    q: str = Query(min_length=1, max_length=256, description="Search query"),
    types: list[SearchEntityType] | None = Query(
        default=None,
        description="Entity types to search (all if not specified)",
    ),
    tags: list[str] | None = Query(
        default=None,
        description="Filter by tags (AND logic)",
    ),
    limit: int = Query(default=20, ge=1, le=100, description="Max results per entity type"),
) -> SearchResponse:
    """Search across all infrastructure entities.

    Args:
        current_user: Authenticated user making the request.
        search_service: Search service instance.
        q: Search query string.
        types: Entity types to search (searches all if not specified).
        tags: Filter results by tags (entities must have all specified tags).
        limit: Maximum results per entity type.

    Returns:
        Search results grouped by entity type with relevance scores.

    Raises:
        HTTPException 403: Agents cannot perform searches.
    """
    if current_user.get("type") == "agent":
        raise AuthorizationError("search:read")

    result = await search_service.search(
        query=q,
        types=types,
        tags=tags,
        limit=limit,
    )

    return SearchResponse(
        query=result["query"],
        results=[
            SearchResultGroup(
                entity_type=r["entity_type"],
                items=[SearchResultItem(**item) for item in r["items"]],
                total=r["total"],
            )
            for r in result["results"]
        ],
        total=result["total"],
    )
