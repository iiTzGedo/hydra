"""Documentation service for infrastructure knowledge base management."""

import re
from datetime import UTC, datetime
from typing import Any

import structlog

from hydra.api.v1.core.exceptions import ConflictError, DocNotFoundError
from hydra.api.v1.models.docs import (
    CreateDocRequest,
    DocListParams,
    DocStatus,
    UpdateDocRequest,
)
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)


class DocsService:
    """Service for managing infrastructure documentation."""

    def __init__(self, mongodb: MongoDB):
        self.mongodb = mongodb
        self.docs = mongodb.docs

    async def create_doc(
        self,
        request: CreateDocRequest,
        author: str | None = None,
    ) -> dict[str, Any]:
        """Create new documentation entry.

        Args:
            request: Documentation creation payload.
            author: The author's user identifier.

        Returns:
            The created document.

        Raises:
            ConflictError: If a document with the same ID already exists.
        """
        existing = await self.docs.find_one({"docId": request.doc_id})
        if existing:
            raise ConflictError("doc", request.doc_id)

        now = datetime.now(UTC)

        doc = {
            "docId": request.doc_id,
            "title": request.title,
            "description": request.description,
            "type": request.type.value,
            "format": request.format.value,
            "content": request.content,
            "linkedEntities": (
                [{"entityType": e.entity_type.value, "entityId": e.entity_id} for e in request.linked_entities]
                if request.linked_entities
                else []
            ),
            "category": request.category,
            "tags": request.tags or [],
            "version": 1,
            "author": author,
            "status": DocStatus.PUBLISHED.value,
            "createdAt": now,
            "updatedAt": now,
            "versions": [
                {
                    "version": 1,
                    "content": request.content,
                    "updatedAt": now,
                    "author": author,
                }
            ],
        }

        await self.docs.insert_one(doc)

        logger.info(
            "doc_created",
            doc_id=request.doc_id,
            title=request.title,
            type=request.type.value,
        )

        return doc

    async def get_doc(self, doc_id: str, version: int | None = None) -> dict[str, Any]:
        """Get documentation by ID.

        Args:
            doc_id: The document identifier.
            version: Optional specific version number to retrieve.

        Returns:
            The document, with content from specified version if requested.

        Raises:
            DocNotFoundError: If the document does not exist.
        """
        doc = await self.docs.find_one({"docId": doc_id})
        if not doc:
            raise DocNotFoundError(doc_id)

        if version is not None:
            versions = doc.get("versions", [])
            for v in versions:
                if v["version"] == version:
                    doc["content"] = v["content"]
                    doc["version"] = version
                    break

        return doc  # type: ignore[no-any-return]

    async def list_docs(self, params: DocListParams) -> tuple[list[dict[str, Any]], int]:
        """List documentation with filtering and pagination.

        Args:
            params: Query parameters with filters, search, and pagination.

        Returns:
            Tuple of (documents list, total count).
        """
        query: dict[str, Any] = {}

        if params.type:
            query["type"] = params.type.value
        if params.status:
            query["status"] = params.status.value
        if params.category:
            query["category"] = params.category
        if params.entity_type:
            query["linkedEntities.entityType"] = params.entity_type.value
        if params.entity_id:
            query["linkedEntities.entityId"] = params.entity_id
        if params.tags:
            query["tags"] = {"$all": params.tags}
        if params.search:
            escaped = re.escape(params.search)
            query["$or"] = [
                {"title": {"$regex": escaped, "$options": "i"}},
                {"description": {"$regex": escaped, "$options": "i"}},
                {"content": {"$regex": escaped, "$options": "i"}},
            ]

        total = await self.docs.count_documents(query)

        cursor = self.docs.find(query)
        cursor = cursor.sort("updatedAt", -1)
        cursor = cursor.skip(params.offset).limit(params.limit)

        docs = await cursor.to_list(length=params.limit)

        return docs, total

    async def update_doc(
        self,
        doc_id: str,
        request: UpdateDocRequest,
        author: str | None = None,
    ) -> dict[str, Any]:
        """Update documentation entry.

        Content updates increment the version and store the previous content
        in version history for retrieval.

        Args:
            doc_id: The document identifier.
            request: Fields to update.
            author: The author's user identifier.

        Returns:
            The updated document.

        Raises:
            DocNotFoundError: If the document does not exist.
        """
        doc = await self.get_doc(doc_id)
        now = datetime.now(UTC)

        update_fields: dict[str, Any] = {"updatedAt": now}

        if request.title is not None:
            update_fields["title"] = request.title
        if request.description is not None:
            update_fields["description"] = request.description
        if request.type is not None:
            update_fields["type"] = request.type.value
        if request.format is not None:
            update_fields["format"] = request.format.value
        if request.category is not None:
            update_fields["category"] = request.category
        if request.tags is not None:
            update_fields["tags"] = request.tags
        if request.status is not None:
            update_fields["status"] = request.status.value
        if request.linked_entities is not None:
            update_fields["linkedEntities"] = [
                {"entityType": e.entity_type.value, "entityId": e.entity_id}
                for e in request.linked_entities
            ]

        if request.content is not None:
            new_version = doc["version"] + 1
            update_fields["content"] = request.content
            update_fields["version"] = new_version

            await self.docs.update_one(
                {"docId": doc_id},
                {
                    "$push": {
                        "versions": {
                            "version": new_version,
                            "content": request.content,
                            "updatedAt": now,
                            "author": author,
                        }
                    }
                },
            )

        await self.docs.update_one(
            {"docId": doc_id},
            {"$set": update_fields},
        )

        logger.info("doc_updated", doc_id=doc_id)

        updated_doc = await self.get_doc(doc_id)
        return updated_doc

    async def delete_doc(self, doc_id: str, permanent: bool = False) -> dict[str, Any]:
        """Delete or archive documentation.

        Args:
            doc_id: The document identifier.
            permanent: If True, permanently delete. Otherwise, archive (soft delete).

        Returns:
            Dict with doc_id and final status.

        Raises:
            DocNotFoundError: If the document does not exist.
        """
        await self.get_doc(doc_id)

        if permanent:
            await self.docs.delete_one({"docId": doc_id})
            logger.info("doc_deleted_permanently", doc_id=doc_id)
            return {"docId": doc_id, "status": "deleted"}
        else:
            await self.docs.update_one(
                {"docId": doc_id},
                {
                    "$set": {
                        "status": DocStatus.ARCHIVED.value,
                        "updatedAt": datetime.now(UTC),
                    }
                },
            )
            logger.info("doc_archived", doc_id=doc_id)
            return {"docId": doc_id, "status": DocStatus.ARCHIVED.value}

    async def get_docs_for_entity(
        self,
        entity_type: str,
        entity_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get all documentation linked to a specific entity.

        Args:
            entity_type: The entity type (node, service, etc.).
            entity_id: The entity identifier.
            limit: Maximum number of documents to return.

        Returns:
            List of published documents linked to the entity.
        """
        cursor = self.docs.find({
            "linkedEntities": {
                "$elemMatch": {
                    "entityType": entity_type,
                    "entityId": entity_id,
                }
            },
            "status": DocStatus.PUBLISHED.value,
        })
        cursor = cursor.sort("updatedAt", -1).limit(limit)

        docs = await cursor.to_list(length=limit)
        return docs
