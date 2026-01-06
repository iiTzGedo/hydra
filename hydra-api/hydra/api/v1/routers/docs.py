"""Documentation endpoints."""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Query

from hydra.api.v1.core.deps import CurrentUser, MongoDBDep, require_permission
from hydra.api.v1.models.common import PaginationMeta, SuccessResponse
from hydra.api.v1.models.docs import (
    CreateDocRequest,
    DocCreatedResponse,
    DocDeletedResponse,
    DocFormat,
    DocListParams,
    DocResponse,
    DocStatus,
    DocSummary,
    DocType,
    DocUpdatedResponse,
    EntityType,
    LinkedEntity,
    UpdateDocRequest,
)
from hydra.api.v1.services.docs import DocsService

router = APIRouter(prefix="/docs", tags=["Documentation"])
logger = structlog.get_logger(__name__)


def get_docs_service(mongodb: MongoDBDep) -> DocsService:
    """Get docs service dependency."""
    return DocsService(mongodb)


DocsServiceDep = Annotated[DocsService, Depends(get_docs_service)]


@router.get(
    "",
    response_model=SuccessResponse[list[DocSummary]],
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
    """List documentation with filters."""
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
                updated_at=doc["updatedAt"],
            )
            for doc in docs
        ],
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.post(
    "",
    response_model=SuccessResponse[DocCreatedResponse],
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
    """Create new documentation."""
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
    summary="Get Documentation",
    description="Get documentation content by ID.",
    dependencies=[Depends(require_permission("docs:read"))],
)
async def get_doc(
    doc_id: str,
    docs_service: DocsServiceDep,
    version: int | None = Query(default=None, description="Specific version to retrieve"),
) -> SuccessResponse[DocResponse]:
    """Get documentation by ID."""
    doc = await docs_service.get_doc(doc_id, version=version)

    return SuccessResponse(
        data=DocResponse(
            doc_id=doc["docId"],
            title=doc["title"],
            description=doc.get("description"),
            type=DocType(doc["type"]),
            format=DocFormat(doc["format"]),
            content=doc["content"],
            linked_entities=[
                LinkedEntity(entity_type=EntityType(e["entityType"]), entity_id=e["entityId"])
                for e in doc.get("linkedEntities", [])
            ],
            category=doc.get("category"),
            tags=doc.get("tags"),
            version=doc["version"],
            author=doc.get("author"),
            status=DocStatus(doc["status"]),
            created_at=doc["createdAt"],
            updated_at=doc["updatedAt"],
        )
    )


@router.put(
    "/{doc_id}",
    response_model=SuccessResponse[DocUpdatedResponse],
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
    """Update documentation."""
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
    summary="Delete Documentation",
    description="Delete or archive documentation.",
    dependencies=[Depends(require_permission("docs:delete"))],
)
async def delete_doc(
    doc_id: str,
    docs_service: DocsServiceDep,
    permanent: bool = Query(default=False, description="Permanently delete (default: archive)"),
) -> SuccessResponse[DocDeletedResponse]:
    """Delete or archive documentation."""
    result = await docs_service.delete_doc(doc_id, permanent=permanent)

    return SuccessResponse(
        data=DocDeletedResponse(
            doc_id=result["docId"],
            status=DocStatus(result["status"]) if result["status"] != "deleted" else DocStatus.ARCHIVED,
        )
    )
