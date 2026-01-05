"""Documentation service for infrastructure knowledge base management."""

from datetime import UTC, datetime
from typing import Any

import structlog

from hydra.db.mongodb import MongoDBManager
from hydra.v1.core.exceptions import ConflictError, DocNotFoundError
from hydra.v1.models.docs import (
    CreateDocRequest,
    DocListParams,
    DocStatus,
    UpdateDocRequest,
)

logger = structlog.get_logger(__name__)


class DocsService:
    """Service for managing infrastructure documentation."""

    def __init__(self, mongodb: MongoDBManager):
        self.mongodb = mongodb
        self.docs = mongodb.docs

    async def create_doc(
        self,
        request: CreateDocRequest,
        author: str | None = None,
    ) -> dict[str, Any]:
        """Create new documentation."""
        # Check if doc already exists
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
            # Store version history
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
        """Get documentation by ID."""
        doc = await self.docs.find_one({"docId": doc_id})
        if not doc:
            raise DocNotFoundError(doc_id)

        # If specific version requested, get that version's content
        if version is not None:
            versions = doc.get("versions", [])
            for v in versions:
                if v["version"] == version:
                    doc["content"] = v["content"]
                    doc["version"] = version
                    break

        return doc

    async def list_docs(self, params: DocListParams) -> tuple[list[dict[str, Any]], int]:
        """List documentation with filters."""
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
            query["$or"] = [
                {"title": {"$regex": params.search, "$options": "i"}},
                {"description": {"$regex": params.search, "$options": "i"}},
                {"content": {"$regex": params.search, "$options": "i"}},
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
        """Update documentation."""
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

        # If content is updated, increment version and store in history
        if request.content is not None:
            new_version = doc["version"] + 1
            update_fields["content"] = request.content
            update_fields["version"] = new_version

            # Add to version history
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
        """Delete or archive documentation."""
        doc = await self.get_doc(doc_id)

        if permanent:
            await self.docs.delete_one({"docId": doc_id})
            logger.info("doc_deleted_permanently", doc_id=doc_id)
            return {"docId": doc_id, "status": "deleted"}
        else:
            # Soft delete - archive
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
        """Get all documentation linked to a specific entity."""
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
