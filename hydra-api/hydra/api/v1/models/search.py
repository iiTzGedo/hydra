"""Search models."""

from enum import Enum

from pydantic import BaseModel, Field


class SearchEntityType(str, Enum):
    """Searchable entity types."""

    NODES = "nodes"
    SERVICES = "services"
    GROUPS = "groups"
    NETWORKS = "networks"


class SearchResultItem(BaseModel):
    """A single search result item."""

    entity_type: SearchEntityType = Field(alias="entityType")
    id: str
    name: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    score: float | None = Field(default=None, description="Search relevance score")

    model_config = {"populate_by_name": True}


class SearchResultGroup(BaseModel):
    """Search results grouped by entity type."""

    entity_type: SearchEntityType = Field(alias="entityType")
    items: list[SearchResultItem]
    total: int

    model_config = {"populate_by_name": True}


class SearchResponse(BaseModel):
    """Global search response."""

    query: str
    results: list[SearchResultGroup]
    total: int

    model_config = {"populate_by_name": True}
