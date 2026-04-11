"""Group models for request/response validation."""

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from hydra.api.v1.core.validators import TAG_PATTERN, validate_tag
from hydra.api.v1.models.icons import IconDescriptor


class GroupEntityType(StrEnum):
    """Types of entities that can be in a group."""

    NODE = "node"
    SERVICE = "service"


class IdSelector(BaseModel):
    """Selector for explicit entity IDs."""

    model_config = ConfigDict(populate_by_name=True)

    is_all: list[str] | None = Field(default=None, alias="isAll")


class AnySelector(BaseModel):
    """Selector for matching any value in a list."""

    model_config = ConfigDict(populate_by_name=True)

    is_any: list[str] | None = Field(default=None, alias="isAny")


class TagsSelector(BaseModel):
    """Selector for tag matching with AND/OR logic."""

    model_config = ConfigDict(populate_by_name=True)

    is_any: list[str] | None = Field(default=None, alias="isAny")
    is_all: list[str] | None = Field(default=None, alias="isAll")

    @field_validator("is_any", "is_all")
    @classmethod
    def validate_tags(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        for tag in v:
            if not validate_tag(tag):
                raise ValueError(f"Invalid tag '{tag}'. Tags must match pattern: {TAG_PATTERN}")
        return v


class GroupSelectors(BaseModel):
    """Group membership selectors."""

    model_config = ConfigDict(populate_by_name=True)

    id: IdSelector | None = None
    network: AnySelector | None = None
    status: AnySelector | None = None
    kind: AnySelector | None = None
    runtime: AnySelector | None = None
    tags: TagsSelector | None = None


class MemberCount(BaseModel):
    """Cached member count for a group."""

    model_config = ConfigDict(populate_by_name=True)

    nodes: int = 0
    services: int = 0
    last_computed: datetime | None = Field(default=None, alias="lastComputed")


class GroupMemberNode(BaseModel):
    """Node member information."""

    model_config = ConfigDict(populate_by_name=True)

    node_id: str = Field(alias="nodeId")
    display_name: str = Field(alias="displayName")
    matched_selectors: list[str] = Field(default_factory=list, alias="matchedSelectors")


class GroupMemberService(BaseModel):
    """Service member information."""

    model_config = ConfigDict(populate_by_name=True)

    service_id: str = Field(alias="serviceId")
    name: str
    node_id: str = Field(alias="nodeId")
    matched_selectors: list[str] = Field(default_factory=list, alias="matchedSelectors")


class GroupMembers(BaseModel):
    """Resolved group members."""

    model_config = ConfigDict(populate_by_name=True)

    nodes: list[GroupMemberNode] = Field(default_factory=list)
    services: list[GroupMemberService] = Field(default_factory=list)


class GroupResponse(BaseModel):
    """Full group response model."""

    model_config = ConfigDict(populate_by_name=True)

    group_id: str = Field(alias="groupId")
    name: str
    description: str | None = None
    types: list[GroupEntityType]
    selectors: GroupSelectors
    parent_group_ids: list[str] = Field(default_factory=list, alias="parentGroupIds")
    member_count: MemberCount = Field(alias="memberCount")
    members: GroupMembers | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    icon: IconDescriptor | None = None


class GroupSummary(BaseModel):
    """Abbreviated group response for lists."""

    model_config = ConfigDict(populate_by_name=True)

    group_id: str = Field(alias="groupId")
    name: str
    description: str | None = None
    types: list[GroupEntityType]
    member_count: MemberCount = Field(alias="memberCount")
    tags: list[str] = Field(default_factory=list)
    icon: IconDescriptor | None = None


class GroupResolveResult(BaseModel):
    """Result of group resolution."""

    model_config = ConfigDict(populate_by_name=True)

    group_id: str = Field(alias="groupId")
    member_count: MemberCount = Field(alias="memberCount")
    changes: dict[str, Any] = Field(default_factory=dict)


class CreateGroupRequest(BaseModel):
    """Create group request."""

    model_config = ConfigDict(populate_by_name=True)

    group_id: str = Field(alias="groupId", min_length=3, max_length=64)
    name: str = Field(max_length=128)
    description: str | None = Field(default=None, max_length=1024)
    types: list[GroupEntityType] = Field(min_length=1)
    selectors: GroupSelectors
    parent_group_ids: list[str] = Field(default_factory=list, alias="parentGroupIds")
    tags: list[str] = Field(default_factory=list)

    @field_validator("group_id")
    @classmethod
    def validate_group_id(cls, v: str) -> str:
        import re

        if not re.match(r"^[a-z0-9][a-z0-9._-]*$", v):
            raise ValueError("Group ID must be lowercase alphanumeric with dots, underscores, and hyphens")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            for tag in v:
                if not validate_tag(tag):
                    raise ValueError(f"Invalid tag '{tag}'. Tags must match pattern: {TAG_PATTERN}")
        return v


class UpdateGroupRequest(BaseModel):
    """Update group request."""

    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(default=None, max_length=128)
    description: str | None = None
    selectors: GroupSelectors | None = None
    parent_group_ids: list[str] | None = Field(default=None, alias="parentGroupIds")
    tags: list[str] | None = None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            for tag in v:
                if not validate_tag(tag):
                    raise ValueError(f"Invalid tag '{tag}'. Tags must match pattern: {TAG_PATTERN}")
        return v


class GroupListParams(BaseModel):
    """Query parameters for listing groups."""

    model_config = ConfigDict(populate_by_name=True)

    types: list[GroupEntityType] | None = None
    parent_group_id: str | None = Field(default=None, alias="parentGroupId")
    tags: list[str] | None = None
    search: str | None = Field(default=None, max_length=256)
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    sort_by: Literal["groupId", "name", "createdAt", "updatedAt"] = Field(
        default="updatedAt", alias="sortBy"
    )
    sort_order: Literal["asc", "desc"] = Field(default="desc", alias="sortOrder")
