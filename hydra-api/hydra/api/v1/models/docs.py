"""Documentation models for infrastructure knowledge base."""

from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field


class DocType(str, Enum):
    """Types of documentation."""

    GUIDE = "guide"
    ARCHITECTURE = "architecture"
    RUNBOOK = "runbook"
    TROUBLESHOOTING = "troubleshooting"
    REFERENCE = "reference"
    CHANGELOG = "changelog"
    OTHER = "other"


class DocFormat(str, Enum):
    """Documentation content format."""

    MARKDOWN = "markdown"
    PLAIN = "plain"
    HTML = "html"


class DocStatus(str, Enum):
    """Documentation status."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class EntityType(str, Enum):
    """Types of entities that can be linked to documentation."""

    NODE = "node"
    SERVICE = "service"
    NETWORK = "network"
    GROUP = "group"


# ==================== Nested Models ====================


class LinkedEntity(BaseModel):
    """Entity linked to documentation."""

    entity_type: Annotated[EntityType, Field(alias="entityType")]
    entity_id: Annotated[str, Field(alias="entityId")]

    model_config = {"populate_by_name": True}


# ==================== Request Models ====================


class CreateDocRequest(BaseModel):
    """Request to create new documentation."""

    doc_id: Annotated[
        str,
        Field(
            alias="docId",
            pattern=r"^doc::[a-z0-9][a-z0-9-]{2,63}$",
            description="Unique document ID (e.g., doc::network-architecture)",
        ),
    ]
    title: str = Field(max_length=256, description="Document title")
    description: str | None = Field(default=None, max_length=1024, description="Document description")
    type: DocType = Field(description="Document type")
    format: DocFormat = Field(default=DocFormat.MARKDOWN, description="Content format")
    content: str = Field(description="Document content")
    linked_entities: Annotated[
        list[LinkedEntity] | None,
        Field(default=None, alias="linkedEntities", description="Linked infrastructure entities"),
    ]
    category: str | None = Field(default=None, max_length=64, description="Document category")
    tags: list[str] | None = Field(default=None, description="Document tags")

    model_config = {"populate_by_name": True}


class UpdateDocRequest(BaseModel):
    """Request to update documentation."""

    title: str | None = Field(default=None, max_length=256)
    description: str | None = Field(default=None, max_length=1024)
    type: DocType | None = None
    format: DocFormat | None = None
    content: str | None = None
    linked_entities: Annotated[list[LinkedEntity] | None, Field(default=None, alias="linkedEntities")]
    category: str | None = Field(default=None, max_length=64)
    tags: list[str] | None = None
    status: DocStatus | None = None

    model_config = {"populate_by_name": True}


# ==================== Response Models ====================


class DocSummary(BaseModel):
    """Summary view of documentation."""

    doc_id: Annotated[str, Field(alias="docId")]
    title: str
    type: DocType
    category: str | None = None
    status: DocStatus
    linked_entities: Annotated[list[LinkedEntity] | None, Field(default=None, alias="linkedEntities")]
    version: int
    updated_at: Annotated[datetime, Field(alias="updatedAt")]

    model_config = {"populate_by_name": True}


class DocResponse(BaseModel):
    """Full documentation response."""

    doc_id: Annotated[str, Field(alias="docId")]
    title: str
    description: str | None = None
    type: DocType
    format: DocFormat
    content: str
    linked_entities: Annotated[list[LinkedEntity] | None, Field(default=None, alias="linkedEntities")]
    category: str | None = None
    tags: list[str] | None = None
    version: int
    author: str | None = None
    status: DocStatus
    created_at: Annotated[datetime, Field(alias="createdAt")]
    updated_at: Annotated[datetime, Field(alias="updatedAt")]

    model_config = {"populate_by_name": True}


class DocCreatedResponse(BaseModel):
    """Response when documentation is created."""

    doc_id: Annotated[str, Field(alias="docId")]
    title: str
    version: int
    created_at: Annotated[datetime, Field(alias="createdAt")]

    model_config = {"populate_by_name": True}


class DocUpdatedResponse(BaseModel):
    """Response when documentation is updated."""

    doc_id: Annotated[str, Field(alias="docId")]
    version: int
    updated_at: Annotated[datetime, Field(alias="updatedAt")]

    model_config = {"populate_by_name": True}


class DocDeletedResponse(BaseModel):
    """Response when documentation is deleted/archived."""

    doc_id: Annotated[str, Field(alias="docId")]
    status: DocStatus

    model_config = {"populate_by_name": True}


# ==================== Query Parameters ====================


class DocListParams(BaseModel):
    """Parameters for listing documentation."""

    type: DocType | None = None
    status: DocStatus | None = None
    category: str | None = None
    entity_type: EntityType | None = Field(default=None, alias="entityType")
    entity_id: str | None = Field(default=None, alias="entityId")
    tags: list[str] | None = None
    search: str | None = None
    limit: int = Field(default=20, ge=1, le=200)
    offset: int = Field(default=0, ge=0)

    model_config = {"populate_by_name": True}
