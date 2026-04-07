"""Documentation management endpoints."""

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Query

from hydra.api.v1.core.deps import CurrentUser, MongoDBDep, require_permission
from hydra.api.v1.models.common import PaginationMeta, SuccessResponse
from hydra.api.v1.models.docs import (
    CreateDocRequest,
    CreateTemplateRequest,
    DocCreatedResponse,
    DocDeletedResponse,
    DocFormat,
    DocListParams,
    DocResponse,
    DocStatus,
    DocSummary,
    DocType,
    DocumentSection,
    DocUpdatedResponse,
    EditSectionRequest,
    EntityType,
    GenerateDocRequest,
    LinkedEntity,
    RegenerateResponse,
    RenderTemplateRequest,
    RevertSectionResponse,
    StalenessReport,
    TemplateDeletedResponse,
    TemplateResponse,
    TemplateSectionDef,
    TemplateSummary,
    TemplateVariable,
    UpdateDocRequest,
    UpdateTemplateRequest,
)
from hydra.api.v1.services.docs import DocsService

router = APIRouter(prefix="/docs", tags=["Documentation"])
logger = structlog.get_logger(__name__)


def get_docs_service(mongodb: MongoDBDep) -> DocsService:
    """Get docs service dependency."""
    return DocsService(mongodb)


DocsServiceDep = Annotated[DocsService, Depends(get_docs_service)]


# ── Template Endpoints ──────────────────────────────────────────────────
# These MUST be registered before the ``/{doc_id}`` catch-all so FastAPI
# matches ``/templates`` as a literal path segment rather than treating it
# as a ``doc_id`` parameter.


@router.get(
    "/templates",
    response_model=SuccessResponse[list[TemplateSummary]],
    response_model_by_alias=True,
    summary="List Document Templates",
    description="List all document templates with pagination.",
    dependencies=[Depends(require_permission("docs:read"))],
)
async def list_templates(
    docs_service: DocsServiceDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SuccessResponse[list[TemplateSummary]]:
    """List all document templates.

    Args:
        docs_service: Documentation service instance.
        limit: Maximum number of templates to return.
        offset: Number of templates to skip.

    Returns:
        Paginated list of template summaries.
    """
    templates, total = await docs_service.list_templates(limit=limit, offset=offset)

    return SuccessResponse(
        data=[
            TemplateSummary(
                template_id=t["templateId"],
                name=t["name"],
                doc_type=t["docType"],
                section_count=len(t.get("sections", [])),
                updated_at=t["updatedAt"],
            )
            for t in templates
        ],
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.post(
    "/templates",
    response_model=SuccessResponse[TemplateResponse],
    response_model_by_alias=True,
    status_code=201,
    summary="Create Document Template",
    description="Create a new document template.",
    dependencies=[Depends(require_permission("docs:write"))],
)
async def create_template(
    request: CreateTemplateRequest,
    docs_service: DocsServiceDep,
) -> SuccessResponse[TemplateResponse]:
    """Create a new document template.

    Args:
        request: Template creation request.
        docs_service: Documentation service instance.

    Returns:
        Created template details.
    """
    template = await docs_service.create_template(request)

    return SuccessResponse(
        data=_build_template_response(template),
    )


@router.get(
    "/templates/{template_id}",
    response_model=SuccessResponse[TemplateResponse],
    response_model_by_alias=True,
    summary="Get Document Template",
    description="Get a document template by ID.",
    dependencies=[Depends(require_permission("docs:read"))],
)
async def get_template(
    template_id: str,
    docs_service: DocsServiceDep,
) -> SuccessResponse[TemplateResponse]:
    """Retrieve a document template by ID.

    Args:
        template_id: Unique identifier of the template.
        docs_service: Documentation service instance.

    Returns:
        Full template details.
    """
    template = await docs_service.get_template(template_id)

    return SuccessResponse(
        data=_build_template_response(template),
    )


@router.put(
    "/templates/{template_id}",
    response_model=SuccessResponse[TemplateResponse],
    response_model_by_alias=True,
    summary="Update Document Template",
    description="Replace an existing document template.",
    dependencies=[Depends(require_permission("docs:write"))],
)
async def update_template(
    template_id: str,
    request: UpdateTemplateRequest,
    docs_service: DocsServiceDep,
) -> SuccessResponse[TemplateResponse]:
    """Replace an existing document template.

    Args:
        template_id: Unique identifier of the template.
        request: Full replacement payload.
        docs_service: Documentation service instance.

    Returns:
        Updated template details.
    """
    template = await docs_service.update_template(template_id, request)

    return SuccessResponse(
        data=_build_template_response(template),
    )


@router.delete(
    "/templates/{template_id}",
    response_model=SuccessResponse[TemplateDeletedResponse],
    response_model_by_alias=True,
    summary="Delete Document Template",
    description="Permanently delete a document template.",
    dependencies=[Depends(require_permission("docs:write"))],
)
async def delete_template(
    template_id: str,
    docs_service: DocsServiceDep,
) -> SuccessResponse[TemplateDeletedResponse]:
    """Permanently delete a document template.

    Args:
        template_id: Unique identifier of the template.
        docs_service: Documentation service instance.

    Returns:
        Deletion confirmation.
    """
    result = await docs_service.delete_template(template_id)

    return SuccessResponse(
        data=TemplateDeletedResponse(
            template_id=result["templateId"],
        ),
    )


@router.post(
    "/templates/{template_id}/render",
    response_model=SuccessResponse[DocCreatedResponse],
    response_model_by_alias=True,
    status_code=201,
    summary="Render Template",
    description="Render a template into a new document with provided variables.",
    dependencies=[Depends(require_permission("docs:write"))],
)
async def render_template(
    template_id: str,
    request: RenderTemplateRequest,
    docs_service: DocsServiceDep,
    current_user: CurrentUser,
) -> SuccessResponse[DocCreatedResponse]:
    """Render a document template into a new document.

    Substitutes variables into each section's content template using
    ``string.Template.safe_substitute`` and creates a published document
    with generated sections.

    Args:
        template_id: Template to render.
        request: Render parameters including target doc_id and variables.
        docs_service: Documentation service instance.
        current_user: Authenticated user making the request.

    Returns:
        Created document details with ID and version.
    """
    author = (
        current_user.get("username")
        if isinstance(current_user, dict)
        else getattr(current_user, "username", None)
    )

    doc = await docs_service.render_template(template_id, request, author=author)

    return SuccessResponse(
        data=DocCreatedResponse(
            doc_id=doc["docId"],
            title=doc["title"],
            version=doc["version"],
            created_at=doc["createdAt"],
        ),
    )


# ── Staleness Endpoint ──────────────────────────────────────────────────


@router.get(
    "/stale",
    response_model=SuccessResponse[list[DocSummary]],
    response_model_by_alias=True,
    summary="List Stale Documents",
    description="Return documents whose generated content has exceeded the staleness threshold.",
    dependencies=[Depends(require_permission("docs:read"))],
)
async def list_stale_docs(
    docs_service: DocsServiceDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SuccessResponse[list[DocSummary]]:
    """Return documents whose generated content is stale.

    A document is stale when ``lastGeneratedAt + staleAfterHours < now()``.

    Args:
        docs_service: Documentation service instance.
        limit: Maximum number of documents to return.
        offset: Number of documents to skip.

    Returns:
        Paginated list of stale document summaries.
    """
    docs, total = await docs_service.get_stale_docs(limit=limit, offset=offset)

    return SuccessResponse(
        data=[
            DocSummary(
                doc_id=doc["docId"],
                title=doc["title"],
                type=DocType(doc["type"]),
                category=doc.get("category"),
                status=DocStatus(doc["status"]),
                linked_entities=[
                    LinkedEntity(entity_type=EntityType(e["entityType"]), entity_id=e["entityId"])
                    for e in doc.get("linkedEntities", [])
                ],
                version=doc["version"],
                last_generated_at=doc.get("lastGeneratedAt"),
                stale_after_hours=doc.get("staleAfterHours"),
                updated_at=doc["updatedAt"],
            )
            for doc in docs
        ],
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


# ── Auto-Generation Pipeline Endpoints ─────────────────────────────────
# These MUST be registered before ``/{doc_id}`` so FastAPI does not
# interpret ``generate`` as a doc_id path parameter.


@router.post(
    "/generate",
    response_model=SuccessResponse[DocResponse],
    status_code=201,
    response_model_by_alias=True,
    summary="Generate Document from Entity",
    description="Generate a new document from a template and live entity data.",
    dependencies=[Depends(require_permission("docs:write"))],
)
async def generate_document(
    request: GenerateDocRequest,
    docs_service: DocsServiceDep,
    current_user: CurrentUser,
) -> SuccessResponse[DocResponse]:
    """Generate a new document from a template and entity data.

    Resolves live entity data from MongoDB, merges with optional variable
    overrides, and renders all template sections into a new document.

    Args:
        request: Generation request with template ID and entity info.
        docs_service: Documentation service instance.
        current_user: Authenticated user making the request.

    Returns:
        Full document response for the newly created document.
    """
    user_id = (
        current_user.get("userId")
        if isinstance(current_user, dict)
        else getattr(current_user, "user_id", None)
    )

    doc = await docs_service.generate_document(request, user_id or "unknown")

    return SuccessResponse(
        data=DocResponse(
            doc_id=doc["docId"],
            title=doc["title"],
            description=doc.get("description"),
            type=DocType(doc["type"]),
            format=DocFormat(doc["format"]),
            content=doc["content"],
            sections=[
                DocumentSection(
                    section_id=s["sectionId"],
                    title=s["title"],
                    content=s["content"],
                    source=s.get("source", "manual"),
                    template_ref=s.get("templateRef"),
                    data_fingerprint=s.get("dataFingerprint"),
                    last_generated_at=s.get("lastGeneratedAt"),
                    last_edited_at=s.get("lastEditedAt"),
                    edited_by=s.get("editedBy"),
                    order=s.get("order", 0),
                )
                for s in doc.get("sections", [])
            ],
            linked_entities=[
                LinkedEntity(entity_type=EntityType(e["entityType"]), entity_id=e["entityId"])
                for e in doc.get("linkedEntities", [])
            ],
            category=doc.get("category"),
            tags=doc.get("tags"),
            version=doc["version"],
            author=doc.get("author"),
            status=DocStatus(doc["status"]),
            template_id=doc.get("templateId"),
            last_generated_at=doc.get("lastGeneratedAt"),
            stale_after_hours=doc.get("staleAfterHours"),
            created_at=doc["createdAt"],
            updated_at=doc["updatedAt"],
        )
    )


# ── Section Hybrid Authoring Endpoints ──────────────────────────────────


@router.patch(
    "/{doc_id}/sections/{section_id}",
    response_model=SuccessResponse[DocResponse],
    response_model_by_alias=True,
    summary="Edit Document Section",
    description="Edit an individual section. Auto-marks generated sections as manual-override.",
    dependencies=[Depends(require_permission("docs:write"))],
)
async def edit_section(
    doc_id: str,
    section_id: str,
    request: EditSectionRequest,
    docs_service: DocsServiceDep,
    current_user: CurrentUser,
) -> SuccessResponse[DocResponse]:
    """Edit an individual section within a document.

    If the section was previously generated, its source is automatically
    changed to ``"manual-override"`` to preserve the edit during
    regeneration.

    Args:
        doc_id: Unique identifier of the document.
        section_id: Unique identifier of the section within the document.
        request: Section edit payload with new content and optional title.
        docs_service: Documentation service instance.
        current_user: Authenticated user making the request.

    Returns:
        Full document response with the updated section.
    """
    user_id = (
        current_user.get("userId")
        if isinstance(current_user, dict)
        else getattr(current_user, "user_id", None)
    )

    doc = await docs_service.edit_section(doc_id, section_id, request, user_id or "unknown")

    return SuccessResponse(
        data=DocResponse(
            doc_id=doc["docId"],
            title=doc["title"],
            description=doc.get("description"),
            type=DocType(doc["type"]),
            format=DocFormat(doc["format"]),
            content=doc["content"],
            sections=[
                DocumentSection(
                    section_id=s["sectionId"],
                    title=s["title"],
                    content=s["content"],
                    source=s.get("source", "manual"),
                    template_ref=s.get("templateRef"),
                    data_fingerprint=s.get("dataFingerprint"),
                    last_generated_at=s.get("lastGeneratedAt"),
                    last_edited_at=s.get("lastEditedAt"),
                    edited_by=s.get("editedBy"),
                    order=s.get("order", 0),
                )
                for s in doc.get("sections", [])
            ],
            linked_entities=[
                LinkedEntity(entity_type=EntityType(e["entityType"]), entity_id=e["entityId"])
                for e in doc.get("linkedEntities", [])
            ],
            category=doc.get("category"),
            tags=doc.get("tags"),
            version=doc["version"],
            author=doc.get("author"),
            status=DocStatus(doc["status"]),
            template_id=doc.get("templateId"),
            last_generated_at=doc.get("lastGeneratedAt"),
            stale_after_hours=doc.get("staleAfterHours"),
            created_at=doc["createdAt"],
            updated_at=doc["updatedAt"],
        )
    )


@router.post(
    "/{doc_id}/sections/{section_id}/revert",
    response_model=SuccessResponse[RevertSectionResponse],
    response_model_by_alias=True,
    summary="Revert Section to Generated",
    description="Revert a manual-override section back to generated content.",
    dependencies=[Depends(require_permission("docs:write"))],
)
async def revert_section(
    doc_id: str,
    section_id: str,
    docs_service: DocsServiceDep,
    current_user: CurrentUser,
) -> SuccessResponse[RevertSectionResponse]:
    """Revert a manual-override section back to generated content.

    Re-renders the section from the document's associated template using
    current entity data.  Only ``"manual-override"`` sections can be
    reverted; purely ``"manual"`` sections have no template to revert to.

    Args:
        doc_id: Unique identifier of the document.
        section_id: Unique identifier of the section.
        docs_service: Documentation service instance.
        current_user: Authenticated user making the request.

    Returns:
        Reverted section info with regenerated content.
    """
    user_id = (
        current_user.get("userId")
        if isinstance(current_user, dict)
        else getattr(current_user, "user_id", None)
    )

    result = await docs_service.revert_section(doc_id, section_id, user_id or "unknown")

    return SuccessResponse(data=RevertSectionResponse(**result))


# ── Existing Document Endpoints ─────────────────────────────────────────


@router.get(
    "",
    response_model=SuccessResponse[list[DocSummary]],
    response_model_by_alias=True,
    summary="List Documentation",
    description="List documentation with optional filters.",
    dependencies=[Depends(require_permission("docs:read"))],
)
async def list_docs(
    docs_service: DocsServiceDep,
    type: DocType | None = None,
    status: DocStatus | None = None,
    category: str | None = None,
    entity_type: EntityType | None = Query(default=None, alias="entityType"),
    entity_id: str | None = Query(default=None, alias="entityId"),
    tags: list[str] | None = Query(default=None),
    search: str | None = None,
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SuccessResponse[list[DocSummary]]:
    """List documentation with optional filters.

    Args:
        docs_service: Documentation service instance.
        type: Filter by document type.
        status: Filter by document status.
        category: Filter by category name.
        entity_type: Filter by linked entity type.
        entity_id: Filter by linked entity ID.
        tags: Filter by tags (documents must have all specified tags).
        search: Full-text search query.
        limit: Maximum number of documents to return.
        offset: Number of documents to skip.

    Returns:
        Paginated list of document summaries.

    Raises:
        HTTPException 403: Insufficient permissions.
    """
    params = DocListParams(
        type=type,
        status=status,
        category=category,
        entity_type=entity_type,
        entity_id=entity_id,
        tags=tags,
        search=search,
        limit=limit,
        offset=offset,
    )

    docs, total = await docs_service.list_docs(params)

    return SuccessResponse(
        data=[
            DocSummary(
                doc_id=doc["docId"],
                title=doc["title"],
                type=DocType(doc["type"]),
                category=doc.get("category"),
                status=DocStatus(doc["status"]),
                linked_entities=[
                    LinkedEntity(entity_type=EntityType(e["entityType"]), entity_id=e["entityId"])
                    for e in doc.get("linkedEntities", [])
                ],
                version=doc["version"],
                last_generated_at=doc.get("lastGeneratedAt"),
                stale_after_hours=doc.get("staleAfterHours"),
                updated_at=doc["updatedAt"],
            )
            for doc in docs
        ],
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.post(
    "",
    response_model=SuccessResponse[DocCreatedResponse],
    response_model_by_alias=True,
    status_code=201,
    summary="Create Documentation",
    description="Create new infrastructure documentation.",
    dependencies=[Depends(require_permission("docs:create"))],
)
async def create_doc(
    request: CreateDocRequest,
    docs_service: DocsServiceDep,
    current_user: CurrentUser,
) -> SuccessResponse[DocCreatedResponse]:
    """Create new infrastructure documentation.

    Args:
        request: Document creation request with title, type, format, and content.
        docs_service: Documentation service instance.
        current_user: Authenticated user making the request.

    Returns:
        Created document details with ID and version.

    Raises:
        HTTPException 403: Insufficient permissions.
    """
    author = current_user.get("username") if isinstance(current_user, dict) else getattr(current_user, "username", None)

    doc = await docs_service.create_doc(request, author=author)

    return SuccessResponse(
        data=DocCreatedResponse(
            doc_id=doc["docId"],
            title=doc["title"],
            version=doc["version"],
            created_at=doc["createdAt"],
        )
    )


@router.get(
    "/{doc_id}",
    response_model=SuccessResponse[DocResponse],
    response_model_by_alias=True,
    summary="Get Documentation",
    description="Get documentation content by ID.",
    dependencies=[Depends(require_permission("docs:read"))],
)
async def get_doc(
    doc_id: str,
    docs_service: DocsServiceDep,
    version: int | None = Query(default=None, description="Specific version to retrieve"),
) -> SuccessResponse[DocResponse]:
    """Retrieve documentation by ID.

    Args:
        doc_id: Unique identifier of the document.
        docs_service: Documentation service instance.
        version: Optional specific version to retrieve.

    Returns:
        Full document content and metadata.

    Raises:
        HTTPException 403: Insufficient permissions.
        HTTPException 404: Document not found.
    """
    doc = await docs_service.get_doc(doc_id, version=version)

    return SuccessResponse(
        data=DocResponse(
            doc_id=doc["docId"],
            title=doc["title"],
            description=doc.get("description"),
            type=DocType(doc["type"]),
            format=DocFormat(doc["format"]),
            content=doc["content"],
            sections=[
                DocumentSection(
                    section_id=s["sectionId"],
                    title=s["title"],
                    content=s["content"],
                    source=s.get("source", "manual"),
                    template_ref=s.get("templateRef"),
                    data_fingerprint=s.get("dataFingerprint"),
                    last_generated_at=s.get("lastGeneratedAt"),
                    last_edited_at=s.get("lastEditedAt"),
                    edited_by=s.get("editedBy"),
                    order=s.get("order", 0),
                )
                for s in doc.get("sections", [])
            ],
            linked_entities=[
                LinkedEntity(entity_type=EntityType(e["entityType"]), entity_id=e["entityId"])
                for e in doc.get("linkedEntities", [])
            ],
            category=doc.get("category"),
            tags=doc.get("tags"),
            version=doc["version"],
            author=doc.get("author"),
            status=DocStatus(doc["status"]),
            template_id=doc.get("templateId"),
            last_generated_at=doc.get("lastGeneratedAt"),
            stale_after_hours=doc.get("staleAfterHours"),
            created_at=doc["createdAt"],
            updated_at=doc["updatedAt"],
        )
    )


@router.post(
    "/{doc_id}/regenerate",
    response_model=SuccessResponse[RegenerateResponse],
    response_model_by_alias=True,
    summary="Regenerate Document",
    description="Regenerate a document's generated sections from current entity data.",
    dependencies=[Depends(require_permission("docs:write"))],
)
async def regenerate_document(
    doc_id: str,
    docs_service: DocsServiceDep,
    current_user: CurrentUser,
) -> SuccessResponse[RegenerateResponse]:
    """Regenerate a document's generated sections from current entity data.

    Manual sections are preserved. Only sections with ``source == "generated"``
    are re-rendered from the template with fresh entity data.

    Args:
        doc_id: Unique identifier of the document.
        docs_service: Documentation service instance.
        current_user: Authenticated user making the request.

    Returns:
        Regeneration summary with updated/skipped section counts.
    """
    user_id = (
        current_user.get("userId")
        if isinstance(current_user, dict)
        else getattr(current_user, "user_id", None)
    )

    result = await docs_service.regenerate_document(doc_id, user_id or "unknown")

    return SuccessResponse(data=RegenerateResponse(**result))


@router.get(
    "/{doc_id}/staleness",
    response_model=SuccessResponse[StalenessReport],
    response_model_by_alias=True,
    summary="Check Document Staleness",
    description="Check per-section staleness for a document.",
    dependencies=[Depends(require_permission("docs:read"))],
)
async def check_staleness(
    doc_id: str,
    docs_service: DocsServiceDep,
) -> SuccessResponse[StalenessReport]:
    """Check per-section staleness for a document.

    Compares stored fingerprints against current entity data to identify
    which generated sections are out of date.

    Args:
        doc_id: Unique identifier of the document.
        docs_service: Documentation service instance.

    Returns:
        Staleness report listing stale sections.
    """
    report = await docs_service.check_section_staleness(doc_id)

    return SuccessResponse(data=StalenessReport(**report))


@router.put(
    "/{doc_id}",
    response_model=SuccessResponse[DocUpdatedResponse],
    response_model_by_alias=True,
    summary="Update Documentation",
    description="Update existing documentation.",
    dependencies=[Depends(require_permission("docs:update"))],
)
async def update_doc(
    doc_id: str,
    request: UpdateDocRequest,
    docs_service: DocsServiceDep,
    current_user: CurrentUser,
) -> SuccessResponse[DocUpdatedResponse]:
    """Update existing documentation.

    Creates a new version of the document with the updated content.

    Args:
        doc_id: Unique identifier of the document.
        request: Document update request with fields to modify.
        docs_service: Documentation service instance.
        current_user: Authenticated user making the request.

    Returns:
        Updated document details with new version number.

    Raises:
        HTTPException 403: Insufficient permissions.
        HTTPException 404: Document not found.
    """
    author = current_user.get("username") if isinstance(current_user, dict) else getattr(current_user, "username", None)

    doc = await docs_service.update_doc(doc_id, request, author=author)

    return SuccessResponse(
        data=DocUpdatedResponse(
            doc_id=doc["docId"],
            version=doc["version"],
            updated_at=doc["updatedAt"],
        )
    )


@router.delete(
    "/{doc_id}",
    response_model=SuccessResponse[DocDeletedResponse],
    response_model_by_alias=True,
    summary="Delete Documentation",
    description="Delete or archive documentation.",
    dependencies=[Depends(require_permission("docs:delete"))],
)
async def delete_doc(
    doc_id: str,
    docs_service: DocsServiceDep,
    permanent: bool = Query(default=False, description="Permanently delete (default: archive)"),
) -> SuccessResponse[DocDeletedResponse]:
    """Delete or archive documentation.

    By default, documents are archived rather than permanently deleted.

    Args:
        doc_id: Unique identifier of the document.
        docs_service: Documentation service instance.
        permanent: If true, permanently delete; otherwise archive.

    Returns:
        Deletion result with final document status.

    Raises:
        HTTPException 403: Insufficient permissions.
        HTTPException 404: Document not found.
    """
    result = await docs_service.delete_doc(doc_id, permanent=permanent)

    return SuccessResponse(
        data=DocDeletedResponse(
            doc_id=result["docId"],
            status=DocStatus(result["status"]) if result["status"] != "deleted" else DocStatus.ARCHIVED,
        )
    )


# ── Helpers ─────────────────────────────────────────────────────────────


def _build_template_response(template: dict[str, Any]) -> TemplateResponse:
    """Build a TemplateResponse from a raw MongoDB template document.

    Args:
        template: Raw template document from MongoDB.

    Returns:
        Validated TemplateResponse model.
    """
    return TemplateResponse(
        template_id=template["templateId"],
        name=template["name"],
        description=template.get("description"),
        doc_type=template["docType"],
        sections=[
            TemplateSectionDef(
                section_id=s["sectionId"],
                title=s["title"],
                content_template=s["contentTemplate"],
                order=s.get("order", 0),
            )
            for s in template.get("sections", [])
        ],
        variables=[
            TemplateVariable(
                name=v["name"],
                source=v["source"],
                description=v.get("description"),
            )
            for v in template.get("variables", [])
        ],
        stale_after_hours=template.get("staleAfterHours"),
        created_at=template["createdAt"],
        updated_at=template["updatedAt"],
    )
