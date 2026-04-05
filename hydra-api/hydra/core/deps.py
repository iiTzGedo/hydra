"""Reusable FastAPI dependencies."""

from fastapi import Query

from hydra.core.config import get_settings


def PaginationLimit(  # noqa: N802 - uppercase for FastAPI dependency convention
    description: str = "Number of results per page",
) -> int:
    """Create a pagination limit Query parameter using centralized config values."""
    settings = get_settings()
    return Query(  # type: ignore[no-any-return]
        default=settings.pagination_default_limit,
        ge=1,
        le=settings.pagination_max_limit,
        description=description,
    )
