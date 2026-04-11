"""Documentation models for infrastructure knowledge base."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DocType(StrEnum):
    """Types of documentation."""

    GUIDE = "guide"
    ARCHITECTURE = "architecture"
    RUNBOOK = "runbook"
    TROUBLESHOOTING = "troubleshooting"
    REFERENCE = "reference"
    CHANGELOG = "changelog"
    OTHER = "other"


class DocFormat(StrEnum):
    """Documentation content format."""

    MARKDOWN = "markdown"
    PLAIN = "plain"
    HTML = "html"


class DocStatus(StrEnum):
    """Documentation status."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class EntityType(StrEnum):
    """Types of entities that can be linked to documentation."""

    NODE = "node"
    SERVICE = "service"
    NETWORK = "network"
    GROUP = "group"


class LinkedEntity(BaseModel):
    """Entity linked to documentation."""

    entity_type: Annotated[EntityType, Field(alias="entityType")]
    entity_id: Annotated[str, Field(alias="entityId")]

    model_config = ConfigDict(populate_by_name=True)


# ── Section-Aware Document Model ────────────────────────────────────────


class DocumentSection(BaseModel):
    """A section within a structured document.

    Sections track authorship provenance (generated vs. manual), data
    fingerprints for staleness detection, and ordering within the document.
    """

    section_id: Annotated[str, Field(alias="sectionId")]
    title: str
    content: str
    source: Literal["generated", "manual", "manual-override"] = "manual"
    template_ref: Annotated[str | None, Field(default=None, alias="templateRef")]
    data_fingerprint: Annotated[str | None, Field(default=None, alias="dataFingerprint")]
    last_generated_at: Annotated[datetime | None, Field(default=None, alias="lastGeneratedAt")]
    last_edited_at: Annotated[datetime | None, Field(default=None, alias="lastEditedAt")]
    edited_by: Annotated[str | None, Field(default=None, alias="editedBy")]
    order: int = 0

    model_config = ConfigDict(populate_by_name=True)


class EditableDocumentSection(BaseModel):
    """Editable section input for manual document CRUD operations."""

    section_id: Annotated[str, Field(alias="sectionId")]
    title: str
    content: str
    order: int = 0

    model_config = ConfigDict(populate_by_name=True)


# ── Template Models ─────────────────────────────────────────────────────


class TemplateSectionDef(BaseModel):
    """Definition of a section within a document template.

    Each section has a content template string that supports Python
    ``string.Template`` substitution (``$variable`` / ``${variable}``).
    """

    section_id: Annotated[str, Field(alias="sectionId")]
    title: str
    content_template: Annotated[str, Field(alias="contentTemplate")]
    order: int = 0

    model_config = ConfigDict(populate_by_name=True)


class TemplateVariable(BaseModel):
    """Variable binding for a document template.

    Describes a named variable that the render endpoint expects, its
    data source path, and an optional human-readable description.
    """

    name: str
    source: str = Field(description="Data path, e.g. 'node.nodeId', 'services[].name'")
    description: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class CreateTemplateRequest(BaseModel):
    """Request body for creating a document template."""

    template_id: Annotated[
        str,
        Field(
            alias="templateId",
            pattern=r"^tmpl::[a-z0-9][a-z0-9-]{2,63}$",
            description="Unique template ID (e.g., tmpl::runbook-overview)",
        ),
    ]
    name: str = Field(max_length=256)
    description: str | None = Field(default=None, max_length=1024)
    doc_type: Annotated[str, Field(alias="docType", description="runbook, guide, reference, troubleshooting")]
    sections: list[TemplateSectionDef] = Field(min_length=1)
    variables: list[TemplateVariable] = Field(default_factory=list)
    stale_after_hours: Annotated[int | None, Field(default=None, alias="staleAfterHours", ge=1)]

    model_config = ConfigDict(populate_by_name=True)


class UpdateTemplateRequest(BaseModel):
    """Request body for fully replacing a document template (PUT)."""

    name: str = Field(max_length=256)
    description: str | None = Field(default=None, max_length=1024)
    doc_type: Annotated[str, Field(alias="docType")]
    sections: list[TemplateSectionDef] = Field(min_length=1)
    variables: list[TemplateVariable] = Field(default_factory=list)
    stale_after_hours: Annotated[int | None, Field(default=None, alias="staleAfterHours", ge=1)]

    model_config = ConfigDict(populate_by_name=True)


class RenderTemplateRequest(BaseModel):
    """Request body for rendering a template into a new document."""

    doc_id: Annotated[
        str,
        Field(
            alias="docId",
            pattern=r"^doc::[a-z0-9][a-z0-9-]{2,63}$",
            description="ID for the resulting document",
        ),
    ]
    title: str = Field(max_length=256)
    variables: dict[str, str] = Field(default_factory=dict)
    linked_entities: Annotated[
        list[LinkedEntity] | None,
        Field(default=None, alias="linkedEntities"),
    ]
    category: str | None = Field(default=None, max_length=64)
    tags: list[str] | None = None

    model_config = ConfigDict(populate_by_name=True)


class TemplateResponse(BaseModel):
    """Full template response."""

    template_id: Annotated[str, Field(alias="templateId")]
    name: str
    description: str | None = None
    doc_type: Annotated[str, Field(alias="docType")]
    sections: list[TemplateSectionDef]
    variables: list[TemplateVariable]
    stale_after_hours: Annotated[int | None, Field(default=None, alias="staleAfterHours")]
    created_at: Annotated[datetime, Field(alias="createdAt")]
    updated_at: Annotated[datetime, Field(alias="updatedAt")]

    model_config = ConfigDict(populate_by_name=True)


class TemplateSummary(BaseModel):
    """Summary view for template listings."""

    template_id: Annotated[str, Field(alias="templateId")]
    name: str
    doc_type: Annotated[str, Field(alias="docType")]
    section_count: Annotated[int, Field(alias="sectionCount")]
    updated_at: Annotated[datetime, Field(alias="updatedAt")]

    model_config = ConfigDict(populate_by_name=True)


class TemplateDeletedResponse(BaseModel):
    """Response when a template is deleted."""

    template_id: Annotated[str, Field(alias="templateId")]
    deleted: bool = True

    model_config = ConfigDict(populate_by_name=True)


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
    content: str | None = Field(default=None, description="Document content")
    sections: list[EditableDocumentSection] | None = Field(
        default=None,
        description="Optional structured sections for manual documents",
    )
    linked_entities: Annotated[
        list[LinkedEntity] | None,
        Field(default=None, alias="linkedEntities", description="Linked infrastructure entities"),
    ]
    category: str | None = Field(default=None, max_length=64, description="Document category")
    tags: list[str] | None = Field(default=None, description="Document tags")

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def validate_content_or_sections(self) -> "CreateDocRequest":
        if self.content is None and not self.sections:
            raise ValueError("CreateDocRequest requires content, sections, or both")
        return self


class UpdateDocRequest(BaseModel):
    """Request to update documentation."""

    title: str | None = Field(default=None, max_length=256)
    description: str | None = Field(default=None, max_length=1024)
    type: DocType | None = None
    format: DocFormat | None = None
    content: str | None = None
    sections: list[EditableDocumentSection] | None = None
    linked_entities: Annotated[list[LinkedEntity] | None, Field(default=None, alias="linkedEntities")]
    category: str | None = Field(default=None, max_length=64)
    tags: list[str] | None = None
    status: DocStatus | None = None

    model_config = ConfigDict(populate_by_name=True)


class DocSummary(BaseModel):
    """Summary view of documentation."""

    doc_id: Annotated[str, Field(alias="docId")]
    title: str
    type: DocType
    category: str | None = None
    status: DocStatus
    linked_entities: Annotated[list[LinkedEntity] | None, Field(default=None, alias="linkedEntities")]
    version: int
    last_generated_at: Annotated[datetime | None, Field(default=None, alias="lastGeneratedAt")]
    stale_after_hours: Annotated[int | None, Field(default=None, alias="staleAfterHours")]
    updated_at: Annotated[datetime, Field(alias="updatedAt")]

    model_config = ConfigDict(populate_by_name=True)


class DocTreeNode(BaseModel):
    """Navigation tree node for the documentation portal."""

    node_id: Annotated[str, Field(alias="nodeId")]
    title: str
    path: str
    kind: Literal["category", "document"] = "document"
    category: str | None = None
    doc_id: Annotated[str | None, Field(default=None, alias="docId")]
    doc_type: Annotated[DocType | None, Field(default=None, alias="docType")]
    status: DocStatus | None = None
    updated_at: Annotated[datetime | None, Field(default=None, alias="updatedAt")]
    children: list["DocTreeNode"] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class DocSearchResult(BaseModel):
    """Dedicated documentation search result for portal queries."""

    doc_id: Annotated[str, Field(alias="docId")]
    title: str
    type: DocType
    status: DocStatus
    category: str | None = None
    excerpt: str | None = None
    linked_entities: Annotated[list[LinkedEntity] | None, Field(default=None, alias="linkedEntities")]
    updated_at: Annotated[datetime, Field(alias="updatedAt")]

    model_config = ConfigDict(populate_by_name=True)


class DocResponse(BaseModel):
    """Full documentation response."""

    doc_id: Annotated[str, Field(alias="docId")]
    title: str
    description: str | None = None
    type: DocType
    format: DocFormat
    content: str
    sections: list[DocumentSection] = Field(default_factory=list)
    linked_entities: Annotated[list[LinkedEntity] | None, Field(default=None, alias="linkedEntities")]
    category: str | None = None
    tags: list[str] | None = None
    version: int
    author: str | None = None
    status: DocStatus
    template_id: Annotated[str | None, Field(default=None, alias="templateId")]
    last_generated_at: Annotated[datetime | None, Field(default=None, alias="lastGeneratedAt")]
    stale_after_hours: Annotated[int | None, Field(default=None, alias="staleAfterHours")]
    created_at: Annotated[datetime, Field(alias="createdAt")]
    updated_at: Annotated[datetime, Field(alias="updatedAt")]

    model_config = ConfigDict(populate_by_name=True)


class DocCreatedResponse(BaseModel):
    """Response when documentation is created."""

    doc_id: Annotated[str, Field(alias="docId")]
    title: str
    version: int
    created_at: Annotated[datetime, Field(alias="createdAt")]

    model_config = ConfigDict(populate_by_name=True)


class DocUpdatedResponse(BaseModel):
    """Response when documentation is updated."""

    doc_id: Annotated[str, Field(alias="docId")]
    version: int
    updated_at: Annotated[datetime, Field(alias="updatedAt")]

    model_config = ConfigDict(populate_by_name=True)


class DocDeletedResponse(BaseModel):
    """Response when documentation is deleted/archived."""

    doc_id: Annotated[str, Field(alias="docId")]
    status: DocStatus

    model_config = ConfigDict(populate_by_name=True)


class DocListParams(BaseModel):
    """Parameters for listing documentation."""

    type: DocType | None = None
    status: DocStatus | None = None
    category: str | None = None
    entity_type: EntityType | None = Field(default=None, alias="entityType")
    entity_id: str | None = Field(default=None, alias="entityId")
    tags: list[str] | None = None
    search: str | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)

    model_config = ConfigDict(populate_by_name=True)


# ── Auto-Generation Pipeline Models ───────────────────────────────────


class GenerateDocRequest(BaseModel):
    """Request to generate a new document from a template + entity."""

    model_config = ConfigDict(populate_by_name=True)

    template_id: Annotated[str, Field(alias="templateId")]
    entity_type: Annotated[str, Field(alias="entityType")]
    entity_id: Annotated[str, Field(alias="entityId")]
    variables: dict[str, Any] = Field(default_factory=dict)
    title: str | None = None


class RegenerationWarning(BaseModel):
    """Warning emitted when regeneration preserves manual content."""

    model_config = ConfigDict(populate_by_name=True)

    code: Literal["MANUAL_SECTION_PRESERVED", "MANUAL_OVERRIDE_PRESERVED"]
    message: str
    section_id: Annotated[str, Field(alias="sectionId")]
    source: Literal["manual", "manual-override"]


class RegenerateResponse(BaseModel):
    """Response from regenerating a document."""

    model_config = ConfigDict(populate_by_name=True)

    doc_id: Annotated[str, Field(alias="docId")]
    version: int
    sections_updated: Annotated[int, Field(alias="sectionsUpdated")]
    sections_skipped: Annotated[int, Field(alias="sectionsSkipped")]
    skipped_section_ids: Annotated[list[str], Field(alias="skippedSectionIds", default_factory=list)]
    warning_count: Annotated[int, Field(alias="warningCount", default=0)]
    warnings: list[RegenerationWarning] = Field(default_factory=list)


class StaleSectionInfo(BaseModel):
    """Info about a stale section."""

    model_config = ConfigDict(populate_by_name=True)

    section_id: Annotated[str, Field(alias="sectionId")]
    current_fingerprint: Annotated[str, Field(alias="currentFingerprint")]
    stored_fingerprint: Annotated[str, Field(alias="storedFingerprint")]


class StalenessReport(BaseModel):
    """Per-section staleness report for a document."""

    model_config = ConfigDict(populate_by_name=True)

    doc_id: Annotated[str, Field(alias="docId")]
    is_stale: Annotated[bool, Field(alias="isStale")]
    stale_sections: Annotated[list[StaleSectionInfo], Field(alias="staleSections", default_factory=list)]
    checked_at: Annotated[datetime, Field(alias="checkedAt")]


# ── Hybrid Authoring Models ────────────────────────────────────────────


class EditSectionRequest(BaseModel):
    """Request to edit an individual section."""

    model_config = ConfigDict(populate_by_name=True)

    title: str | None = None
    content: str


class RevertSectionResponse(BaseModel):
    """Response from reverting a section to generated state."""

    model_config = ConfigDict(populate_by_name=True)

    section_id: Annotated[str, Field(alias="sectionId")]
    source: str  # will be "generated" after revert
    content: str  # regenerated content


DocTreeNode.model_rebuild()
