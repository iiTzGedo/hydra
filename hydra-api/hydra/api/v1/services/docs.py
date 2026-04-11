"""Documentation service for infrastructure knowledge base management."""

import contextlib
import hashlib
import json
import re
import string
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from hydra.api.v1.core.exceptions import (
    ConflictError,
    DocNotFoundError,
    NotFoundError,
    ValidationError,
)
from hydra.api.v1.models.docs import (
    CreateDocRequest,
    CreateTemplateRequest,
    DocListParams,
    DocStatus,
    EditSectionRequest,
    GenerateDocRequest,
    RenderTemplateRequest,
    UpdateDocRequest,
    UpdateTemplateRequest,
)
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)


def _compute_fingerprint(variables: dict[str, str]) -> str:
    """Compute a stable SHA-256 fingerprint of the variable values.

    Args:
        variables: Mapping of variable names to their values.

    Returns:
        First 16 hex characters of the SHA-256 digest.
    """
    canonical = json.dumps(variables, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


class TemplateNotFoundError(NotFoundError):
    """Document template not found."""

    def __init__(self, template_id: str) -> None:
        super().__init__("template", template_id)


class DocsService:
    """Service for managing infrastructure documentation."""

    def __init__(self, mongodb: MongoDB):
        self.mongodb = mongodb
        self.docs = mongodb.docs
        self.doc_templates = mongodb.doc_templates

    @staticmethod
    def _sort_sections(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return sections in stable display order."""
        return sorted(
            sections,
            key=lambda section: (section.get("order", 0), section.get("sectionId", "")),
        )

    @staticmethod
    def _is_generated_doc(doc: dict[str, Any]) -> bool:
        """Return True when a document body is template-generated."""
        if doc.get("templateId") or doc.get("lastGeneratedAt"):
            return True
        return any(
            section.get("source") == "generated"
            for section in doc.get("sections", [])
        )

    def _compose_document_content(self, sections: list[dict[str, Any]]) -> str:
        """Render synchronized top-level content from ordered sections."""
        ordered_sections = self._sort_sections(sections)
        if (
            len(ordered_sections) == 1
            and ordered_sections[0].get("sectionId") == "content"
        ):
            return str(ordered_sections[0].get("content", ""))

        content_parts: list[str] = []
        for section in ordered_sections:
            title = section.get("title")
            content = section.get("content", "")
            if title:
                content_parts.append(f"## {title}\n\n{content}")
            else:
                content_parts.append(content)
        return "\n\n".join(content_parts)

    @staticmethod
    def _build_search_excerpt(doc: dict[str, Any], query: str) -> str | None:
        """Extract a short excerpt around the first query hit."""
        if not query:
            return None

        haystacks = [
            str(doc.get("description") or ""),
            str(doc.get("content") or ""),
        ]
        lowered_query = query.lower()

        for haystack in haystacks:
            lowered = haystack.lower()
            index = lowered.find(lowered_query)
            if index == -1:
                continue
            start = max(index - 60, 0)
            end = min(index + len(query) + 120, len(haystack))
            excerpt = haystack[start:end].strip()
            if start > 0:
                excerpt = f"...{excerpt}"
            if end < len(haystack):
                excerpt = f"{excerpt}..."
            return excerpt

        return None

    @staticmethod
    def _merge_sections(
        existing_sections: list[dict[str, Any]],
        generated_sections: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Merge generated sections with existing, preserving manual edits.

        Preserves sections whose source is ``"manual"`` or
        ``"manual-override"``.  Generated sections are replaced with fresh
        rendered content.  Manual sections not present in the template are
        appended after all template sections.

        Args:
            existing_sections: Current sections from the stored document.
            generated_sections: Freshly rendered sections from the template.

        Returns:
            Tuple of (merged_sections, skipped_section_ids).
        """
        existing_by_id: dict[str, dict[str, Any]] = {
            s["sectionId"]: s for s in existing_sections
        }
        merged: list[dict[str, Any]] = []
        skipped_ids: list[str] = []
        seen_ids: set[str] = set()

        # Process generated sections in template order
        for gen_section in generated_sections:
            sid = gen_section["sectionId"]
            seen_ids.add(sid)
            existing = existing_by_id.get(sid)

            if existing and existing.get("source") in ("manual", "manual-override"):
                # User has manually edited this section -- preserve their content
                merged.append(existing)
                skipped_ids.append(sid)
            else:
                # Replace with fresh generated content
                merged.append(gen_section)

        # Append remaining manual sections not in template (user-added sections)
        for section in existing_sections:
            sid = section.get("sectionId", "")
            if sid not in seen_ids and section.get("source") in ("manual", "manual-override"):
                merged.append(section)
                skipped_ids.append(sid)

        return merged, skipped_ids

    @staticmethod
    def _build_regeneration_warnings(
        merged_sections: list[dict[str, Any]],
        skipped_section_ids: list[str],
    ) -> list[dict[str, str]]:
        """Build warning records for preserved manual content."""
        sections_by_id = {
            str(section.get("sectionId")): section
            for section in merged_sections
            if section.get("sectionId")
        }
        warnings: list[dict[str, str]] = []

        for section_id in skipped_section_ids:
            section = sections_by_id.get(section_id, {})
            section_title = str(section.get("title") or section_id)
            source = str(section.get("source") or "manual")

            if source == "manual-override":
                warnings.append({
                    "code": "MANUAL_OVERRIDE_PRESERVED",
                    "message": (
                        f"Preserved manual override for section '{section_title}' "
                        "during regeneration"
                    ),
                    "sectionId": section_id,
                    "source": "manual-override",
                })
            elif source == "manual":
                warnings.append({
                    "code": "MANUAL_SECTION_PRESERVED",
                    "message": (
                        f"Preserved manual section '{section_title}' during regeneration"
                    ),
                    "sectionId": section_id,
                    "source": "manual",
                })

        return warnings

    def _build_manual_document_body(
        self,
        *,
        title: str,
        content: str | None,
        sections: list[Any] | None,
        now: datetime,
        author: str | None,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Normalize manual doc input into synchronized content + sections."""
        if not sections:
            if content is None:
                raise ValidationError(
                    "Manual document updates require content, sections, or both"
                )
            normalized_sections = [
                {
                    "sectionId": "content",
                    "title": title,
                    "content": content,
                    "source": "manual",
                    "templateRef": None,
                    "dataFingerprint": None,
                    "lastGeneratedAt": None,
                    "lastEditedAt": now,
                    "editedBy": author,
                    "order": 0,
                }
            ]
            return content, normalized_sections

        normalized_sections = [
            {
                "sectionId": section.section_id,
                "title": section.title,
                "content": section.content,
                "source": "manual",
                "templateRef": None,
                "dataFingerprint": None,
                "lastGeneratedAt": None,
                "lastEditedAt": now,
                "editedBy": author,
                "order": section.order,
            }
            for section in sections
        ]
        computed_content = self._compose_document_content(normalized_sections)

        if content is not None and content != computed_content:
            raise ValidationError(
                "Provided content does not match the provided sections",
                details={
                    "contentMismatch": True,
                    "sectionCount": len(normalized_sections),
                },
            )

        return content if content is not None else computed_content, normalized_sections

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
        normalized_content, normalized_sections = self._build_manual_document_body(
            title=request.title,
            content=request.content,
            sections=request.sections,
            now=now,
            author=author,
        )

        doc = {
            "docId": request.doc_id,
            "title": request.title,
            "description": request.description,
            "type": request.type.value,
            "format": request.format.value,
            "content": normalized_content,
            "sections": normalized_sections,
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
                    "content": normalized_content,
                    "sections": normalized_sections,
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
                    if "sections" in v:
                        doc["sections"] = v["sections"]
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

    async def get_docs_tree(self) -> list[dict[str, Any]]:
        """Build a category-aware navigation tree for the docs portal."""
        docs = await self.docs.find({}).sort("title", 1).to_list(length=None)

        categories: dict[str, list[dict[str, Any]]] = {}
        uncategorized: list[dict[str, Any]] = []

        for doc in docs:
            category = str(doc.get("category") or "").strip()
            if category:
                categories.setdefault(category, []).append(doc)
            else:
                uncategorized.append(doc)

        tree: list[dict[str, Any]] = []

        for category, category_docs in sorted(categories.items(), key=lambda item: item[0].lower()):
            tree.append({
                "nodeId": f"category::{category.lower().replace(' ', '-')}",
                "title": category,
                "path": f"/docs/category/{category.lower().replace(' ', '-')}",
                "kind": "category",
                "category": category,
                "children": [
                    {
                        "nodeId": f"doc::{doc['docId']}",
                        "title": doc["title"],
                        "path": f"/docs/{doc['docId']}",
                        "kind": "document",
                        "category": category,
                        "docId": doc["docId"],
                        "docType": doc["type"],
                        "status": doc["status"],
                        "updatedAt": doc["updatedAt"],
                        "children": [],
                    }
                    for doc in sorted(category_docs, key=lambda entry: str(entry.get("title", "")).lower())
                ],
            })

        if uncategorized:
            tree.append({
                "nodeId": "category::uncategorized",
                "title": "Uncategorized",
                "path": "/docs/category/uncategorized",
                "kind": "category",
                "category": None,
                "children": [
                    {
                        "nodeId": f"doc::{doc['docId']}",
                        "title": doc["title"],
                        "path": f"/docs/{doc['docId']}",
                        "kind": "document",
                        "category": doc.get("category"),
                        "docId": doc["docId"],
                        "docType": doc["type"],
                        "status": doc["status"],
                        "updatedAt": doc["updatedAt"],
                        "children": [],
                    }
                    for doc in sorted(uncategorized, key=lambda entry: str(entry.get("title", "")).lower())
                ],
            })

        return tree

    async def search_docs(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search documentation with excerpt generation for the portal."""
        params = DocListParams(search=query, limit=limit, offset=0)
        docs, _ = await self.list_docs(params)

        return [
            {
                "docId": doc["docId"],
                "title": doc["title"],
                "type": doc["type"],
                "status": doc["status"],
                "category": doc.get("category"),
                "excerpt": self._build_search_excerpt(doc, query),
                "linkedEntities": doc.get("linkedEntities", []),
                "updatedAt": doc["updatedAt"],
            }
            for doc in docs[:limit]
        ]

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
        body_update_requested = request.content is not None or request.sections is not None

        if self._is_generated_doc(doc) and body_update_requested:
            raise ValidationError(
                (
                    "Template-generated documents only support metadata updates via "
                    "generic CRUD until hybrid authoring is implemented"
                ),
                details={
                    "docId": doc_id,
                    "templateId": doc.get("templateId"),
                },
            )

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

        if body_update_requested:
            next_title = request.title if request.title is not None else doc["title"]
            normalized_content, normalized_sections = self._build_manual_document_body(
                title=next_title,
                content=request.content,
                sections=request.sections,
                now=now,
                author=author,
            )
            new_version = doc["version"] + 1
            update_fields["content"] = normalized_content
            update_fields["sections"] = normalized_sections
            update_fields["version"] = new_version

            await self.docs.update_one(
                {"docId": doc_id},
                {
                    "$push": {
                        "versions": {
                            "version": new_version,
                            "content": normalized_content,
                            "sections": normalized_sections,
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

    # ── Template CRUD ───────────────────────────────────────────────────

    async def create_template(self, request: CreateTemplateRequest) -> dict[str, Any]:
        """Create a new document template.

        Args:
            request: Template creation payload.

        Returns:
            The created template document.

        Raises:
            ConflictError: If a template with the same ID already exists.
        """
        existing = await self.doc_templates.find_one({"templateId": request.template_id})
        if existing:
            raise ConflictError("template", request.template_id)

        now = datetime.now(UTC)

        template: dict[str, Any] = {
            "templateId": request.template_id,
            "name": request.name,
            "description": request.description,
            "docType": request.doc_type,
            "sections": [
                {
                    "sectionId": s.section_id,
                    "title": s.title,
                    "contentTemplate": s.content_template,
                    "order": s.order,
                }
                for s in request.sections
            ],
            "variables": [
                {
                    "name": v.name,
                    "source": v.source,
                    "description": v.description,
                }
                for v in request.variables
            ],
            "staleAfterHours": request.stale_after_hours,
            "createdAt": now,
            "updatedAt": now,
        }

        await self.doc_templates.insert_one(template)

        logger.info(
            "template_created",
            template_id=request.template_id,
            name=request.name,
        )

        return template

    async def get_template(self, template_id: str) -> dict[str, Any]:
        """Get a document template by ID.

        Args:
            template_id: The template identifier.

        Returns:
            The template document.

        Raises:
            TemplateNotFoundError: If the template does not exist.
        """
        template = await self.doc_templates.find_one({"templateId": template_id})
        if not template:
            raise TemplateNotFoundError(template_id)
        return template  # type: ignore[no-any-return]

    async def list_templates(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List all document templates with pagination.

        Args:
            limit: Maximum number of templates to return.
            offset: Number of templates to skip.

        Returns:
            Tuple of (templates list, total count).
        """
        total = await self.doc_templates.count_documents({})
        cursor = self.doc_templates.find({})
        cursor = cursor.sort("updatedAt", -1).skip(offset).limit(limit)
        templates = await cursor.to_list(length=limit)
        return templates, total

    async def update_template(
        self,
        template_id: str,
        request: UpdateTemplateRequest,
    ) -> dict[str, Any]:
        """Replace a document template (full PUT replacement).

        Args:
            template_id: The template identifier.
            request: Full replacement payload.

        Returns:
            The updated template document.

        Raises:
            TemplateNotFoundError: If the template does not exist.
        """
        await self.get_template(template_id)
        now = datetime.now(UTC)

        update_fields: dict[str, Any] = {
            "name": request.name,
            "description": request.description,
            "docType": request.doc_type,
            "sections": [
                {
                    "sectionId": s.section_id,
                    "title": s.title,
                    "contentTemplate": s.content_template,
                    "order": s.order,
                }
                for s in request.sections
            ],
            "variables": [
                {
                    "name": v.name,
                    "source": v.source,
                    "description": v.description,
                }
                for v in request.variables
            ],
            "staleAfterHours": request.stale_after_hours,
            "updatedAt": now,
        }

        await self.doc_templates.update_one(
            {"templateId": template_id},
            {"$set": update_fields},
        )

        logger.info("template_updated", template_id=template_id)
        return await self.get_template(template_id)

    async def delete_template(self, template_id: str) -> dict[str, Any]:
        """Permanently delete a document template.

        Args:
            template_id: The template identifier.

        Returns:
            Dict with templateId and deleted flag.

        Raises:
            TemplateNotFoundError: If the template does not exist.
        """
        await self.get_template(template_id)
        await self.doc_templates.delete_one({"templateId": template_id})

        logger.info("template_deleted", template_id=template_id)
        return {"templateId": template_id, "deleted": True}

    # ── Template Rendering ──────────────────────────────────────────────

    async def render_template(
        self,
        template_id: str,
        request: RenderTemplateRequest,
        author: str | None = None,
    ) -> dict[str, Any]:
        """Render a template into a new document.

        Uses Python ``string.Template.safe_substitute`` to replace
        ``$variable`` placeholders in each section's content template with
        the values provided in the request.

        Args:
            template_id: The template to render.
            request: Render parameters including doc_id, title, and variables.
            author: The author's user identifier.

        Returns:
            The created document.

        Raises:
            TemplateNotFoundError: If the template does not exist.
            ConflictError: If a document with the target doc_id already exists.
        """
        template = await self.get_template(template_id)

        existing = await self.docs.find_one({"docId": request.doc_id})
        if existing:
            raise ConflictError("doc", request.doc_id)

        now = datetime.now(UTC)
        fingerprint = _compute_fingerprint(request.variables)

        rendered_sections: list[dict[str, Any]] = []
        content_parts: list[str] = []

        for section_def in sorted(template.get("sections", []), key=lambda s: s.get("order", 0)):
            tmpl = string.Template(section_def["contentTemplate"])
            rendered_content = tmpl.safe_substitute(request.variables)
            rendered_sections.append({
                "sectionId": section_def["sectionId"],
                "title": section_def["title"],
                "content": rendered_content,
                "source": "generated",
                "templateRef": template_id,
                "dataFingerprint": fingerprint,
                "lastGeneratedAt": now,
                "lastEditedAt": None,
                "editedBy": None,
                "order": section_def.get("order", 0),
            })
            content_parts.append(f"## {section_def['title']}\n\n{rendered_content}")

        combined_content = "\n\n".join(content_parts)

        doc: dict[str, Any] = {
            "docId": request.doc_id,
            "title": request.title,
            "description": template.get("description"),
            "type": template.get("docType", "reference"),
            "format": "markdown",
            "content": combined_content,
            "sections": rendered_sections,
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
            "templateId": template_id,
            "lastGeneratedAt": now,
            "staleAfterHours": template.get("staleAfterHours"),
            "createdAt": now,
            "updatedAt": now,
            "versions": [
                {
                    "version": 1,
                    "content": combined_content,
                    "sections": rendered_sections,
                    "updatedAt": now,
                    "author": author,
                }
            ],
        }

        await self.docs.insert_one(doc)

        logger.info(
            "template_rendered",
            template_id=template_id,
            doc_id=request.doc_id,
        )

        return doc

    # ── Staleness Detection ─────────────────────────────────────────────

    async def get_stale_docs(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Return documents whose generated content is stale.

        A document is stale when:
        - ``lastGeneratedAt`` is set (it was generated from a template)
        - ``staleAfterHours`` is set (a staleness threshold is defined)
        - ``lastGeneratedAt + staleAfterHours < now()``

        Args:
            limit: Maximum number of stale documents to return.
            offset: Number of documents to skip.

        Returns:
            Tuple of (stale documents, total count of stale docs).
        """
        now = datetime.now(UTC)

        # Query for documents that have both staleness fields populated
        # and where the staleness window has elapsed.
        # MongoDB doesn't natively support field-relative date math in a
        # simple find, so we fetch candidates and filter in Python.
        query: dict[str, Any] = {
            "lastGeneratedAt": {"$ne": None},
            "staleAfterHours": {"$ne": None, "$gt": 0},
            "status": {"$ne": DocStatus.ARCHIVED.value},
        }

        candidates_cursor = self.docs.find(query).sort("lastGeneratedAt", 1)
        candidates = await candidates_cursor.to_list(length=1000)

        stale_docs: list[dict[str, Any]] = []
        for doc in candidates:
            generated_at = doc.get("lastGeneratedAt")
            stale_hours = doc.get("staleAfterHours")
            if generated_at and stale_hours:
                threshold = generated_at + timedelta(hours=stale_hours)
                if threshold < now:
                    stale_docs.append(doc)

        total = len(stale_docs)
        paginated = stale_docs[offset : offset + limit]
        return paginated, total

    # ── Auto-Generation Pipeline ───────────────────────────────────────

    async def _resolve_entity_data(
        self,
        entity_type: str,
        entity_id: str,
    ) -> dict[str, Any]:
        """Fetch current data for an entity from MongoDB.

        Args:
            entity_type: The entity type (``node``, ``service``, ``network``).
            entity_id: The entity identifier.

        Returns:
            A flat dict suitable for ``string.Template.safe_substitute``.

        Raises:
            NotFoundError: If the entity does not exist.
        """
        if entity_type == "node":
            entity = await self.mongodb.nodes.find_one({"nodeId": entity_id})
            if not entity:
                raise NotFoundError("node", entity_id)
            return {
                "node_id": entity.get("nodeId", ""),
                "node_class": entity.get("class", ""),
                "node_type": entity.get("type", ""),
                "display_name": entity.get("displayName", ""),
                "hostname": entity.get("displayName", entity.get("nodeId", "")),
                "description": entity.get("description", ""),
                "tags": ", ".join(entity.get("tags", [])),
                "status": entity.get("status", ""),
                "agent_tier": entity.get("agentTier", ""),
            }
        if entity_type == "service":
            entity = await self.mongodb.services.find_one({"serviceId": entity_id})
            if not entity:
                raise NotFoundError("service", entity_id)
            return {
                "service_id": entity.get("serviceId", ""),
                "service_name": entity.get("name", ""),
                "runtime": entity.get("runtime", ""),
                "node_id": entity.get("nodeId", ""),
                "state": entity.get("state", ""),
                "version": entity.get("version", ""),
            }
        if entity_type == "network":
            entity = await self.mongodb.networks.find_one({"networkId": entity_id})
            if not entity:
                raise NotFoundError("network", entity_id)
            return {
                "network_id": entity.get("networkId", ""),
                "network_name": entity.get("name", ""),
                "cidr": entity.get("cidr", ""),
                "vlan": str(entity.get("vlan", "")),
                "gateway": entity.get("gateway", ""),
                "description": entity.get("description", ""),
            }

        raise ValueError(
            f"Unsupported entity type for document generation: {entity_type}"
        )

    async def generate_document(
        self,
        request: GenerateDocRequest,
        user_id: str,
    ) -> dict[str, Any]:
        """Generate a new document from a template and entity data.

        Args:
            request: Generation request with template ID, entity info, and overrides.
            user_id: The author's user identifier.

        Returns:
            The created document.

        Raises:
            TemplateNotFoundError: If the template does not exist.
            NotFoundError: If the entity does not exist.
            ConflictError: If a document with the computed doc_id already exists.
        """
        template = await self.get_template(request.template_id)

        entity_data = await self._resolve_entity_data(
            request.entity_type, request.entity_id,
        )

        # Merge: entity data first, then request.variables override
        variables: dict[str, str] = {
            k: str(v) for k, v in entity_data.items()
        }
        for k, v in request.variables.items():
            variables[k] = str(v)

        doc_title = request.title or f"{template['name']}: {request.entity_id}"
        # Derive a doc_id from template + entity
        safe_entity_id = request.entity_id.replace(".", "-").lower()
        safe_tmpl_id = request.template_id.replace("tmpl::", "")
        doc_id = f"doc::{safe_tmpl_id}-{safe_entity_id}"

        existing = await self.docs.find_one({"docId": doc_id})
        if existing:
            raise ConflictError("doc", doc_id)

        now = datetime.now(UTC)
        fingerprint = _compute_fingerprint(variables)

        rendered_sections: list[dict[str, Any]] = []
        content_parts: list[str] = []

        for section_def in sorted(
            template.get("sections", []),
            key=lambda s: s.get("order", 0),
        ):
            tmpl = string.Template(section_def["contentTemplate"])
            rendered_content = tmpl.safe_substitute(variables)
            rendered_sections.append({
                "sectionId": section_def["sectionId"],
                "title": section_def["title"],
                "content": rendered_content,
                "source": "generated",
                "templateRef": request.template_id,
                "dataFingerprint": fingerprint,
                "lastGeneratedAt": now,
                "lastEditedAt": None,
                "editedBy": None,
                "order": section_def.get("order", 0),
            })
            content_parts.append(f"## {section_def['title']}\n\n{rendered_content}")

        combined_content = "\n\n".join(content_parts)

        doc: dict[str, Any] = {
            "docId": doc_id,
            "title": doc_title,
            "description": template.get("description"),
            "type": template.get("docType", "reference"),
            "format": "markdown",
            "content": combined_content,
            "sections": rendered_sections,
            "linkedEntities": [
                {"entityType": request.entity_type, "entityId": request.entity_id},
            ],
            "category": None,
            "tags": [],
            "version": 1,
            "author": user_id,
            "status": DocStatus.PUBLISHED.value,
            "templateId": request.template_id,
            "lastGeneratedAt": now,
            "staleAfterHours": template.get("staleAfterHours"),
            "createdAt": now,
            "updatedAt": now,
            "versions": [
                {
                    "version": 1,
                    "content": combined_content,
                    "sections": rendered_sections,
                    "updatedAt": now,
                    "author": user_id,
                }
            ],
        }

        await self.docs.insert_one(doc)

        logger.info(
            "document_generated",
            doc_id=doc_id,
            template_id=request.template_id,
            entity_type=request.entity_type,
            entity_id=request.entity_id,
        )

        return doc

    async def regenerate_document(
        self,
        doc_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """Regenerate a document's generated sections from current entity data.

        Manual and manual-override sections are preserved.

        Args:
            doc_id: The document identifier.
            user_id: The user requesting regeneration.

        Returns:
            Dict matching ``RegenerateResponse`` fields.

        Raises:
            DocNotFoundError: If the document does not exist.
            ValidationError: If the document has no templateId.
        """
        doc = await self.get_doc(doc_id)

        template_id = doc.get("templateId")
        if not template_id:
            raise ValidationError(
                "Cannot regenerate a document that was not generated from a template",
                details={"docId": doc_id},
            )

        template = await self.get_template(template_id)

        # Resolve entity data from the first linked entity
        linked_entities = doc.get("linkedEntities", [])
        entity_data: dict[str, Any] = {}
        if linked_entities:
            first_entity = linked_entities[0]
            entity_data = await self._resolve_entity_data(
                first_entity["entityType"],
                first_entity["entityId"],
            )

        variables: dict[str, str] = {k: str(v) for k, v in entity_data.items()}
        now = datetime.now(UTC)
        fingerprint = _compute_fingerprint(variables)

        # Render all template sections as fresh "generated" sections
        rendered_sections: list[dict[str, Any]] = []
        for section_def in sorted(
            template.get("sections", []),
            key=lambda s: s.get("order", 0),
        ):
            tmpl = string.Template(section_def["contentTemplate"])
            rendered_content = tmpl.safe_substitute(variables)
            rendered_sections.append({
                "sectionId": section_def["sectionId"],
                "title": section_def["title"],
                "content": rendered_content,
                "source": "generated",
                "templateRef": template_id,
                "dataFingerprint": fingerprint,
                "lastGeneratedAt": now,
                "lastEditedAt": None,
                "editedBy": None,
                "order": section_def.get("order", 0),
            })

        # Merge: preserve manual/manual-override sections
        updated_sections, skipped_section_ids = self._merge_sections(
            doc.get("sections", []),
            rendered_sections,
        )
        warnings = self._build_regeneration_warnings(
            updated_sections,
            skipped_section_ids,
        )

        sections_skipped = len(skipped_section_ids)
        sections_updated = len(updated_sections) - sections_skipped

        combined_content = self._compose_document_content(updated_sections)
        new_version = doc["version"] + 1

        # Push version history entry
        await self.docs.update_one(
            {"docId": doc_id},
            {
                "$push": {
                    "versions": {
                        "version": new_version,
                        "content": combined_content,
                        "sections": updated_sections,
                        "updatedAt": now,
                        "author": user_id,
                    }
                }
            },
        )

        # Update the document
        await self.docs.update_one(
            {"docId": doc_id},
            {
                "$set": {
                    "content": combined_content,
                    "sections": updated_sections,
                    "version": new_version,
                    "lastGeneratedAt": now,
                    "updatedAt": now,
                }
            },
        )

        logger.info(
            "document_regenerated",
            doc_id=doc_id,
            version=new_version,
            sections_updated=sections_updated,
            sections_skipped=sections_skipped,
        )

        return {
            "docId": doc_id,
            "version": new_version,
            "sectionsUpdated": sections_updated,
            "sectionsSkipped": sections_skipped,
            "skippedSectionIds": skipped_section_ids,
            "warningCount": len(warnings),
            "warnings": warnings,
        }

    async def check_section_staleness(self, doc_id: str) -> dict[str, Any]:
        """Check per-section staleness for a document.

        For each generated section, computes the current fingerprint from
        live entity data and compares with the stored fingerprint.

        Args:
            doc_id: The document identifier.

        Returns:
            Dict matching ``StalenessReport`` fields.

        Raises:
            DocNotFoundError: If the document does not exist.
        """
        doc = await self.get_doc(doc_id)
        now = datetime.now(UTC)

        linked_entities = doc.get("linkedEntities", [])
        entity_data: dict[str, Any] = {}
        if linked_entities:
            first_entity = linked_entities[0]
            with contextlib.suppress(NotFoundError):
                entity_data = await self._resolve_entity_data(
                    first_entity["entityType"],
                    first_entity["entityId"],
                )

        variables: dict[str, str] = {k: str(v) for k, v in entity_data.items()}
        current_fingerprint = _compute_fingerprint(variables)

        stale_sections: list[dict[str, str]] = []
        for section in doc.get("sections", []):
            if section.get("source") != "generated":
                continue
            stored_fp = section.get("dataFingerprint", "")
            if stored_fp != current_fingerprint:
                stale_sections.append({
                    "sectionId": section["sectionId"],
                    "currentFingerprint": current_fingerprint,
                    "storedFingerprint": stored_fp,
                })

        return {
            "docId": doc_id,
            "isStale": len(stale_sections) > 0,
            "staleSections": stale_sections,
            "checkedAt": now,
        }

    async def flag_docs_stale_for_entity(
        self,
        entity_type: str,
        entity_id: str,
    ) -> int:
        """Flag all documents linked to an entity as stale.

        Sets ``lastGeneratedAt`` to a very old date so the staleness math
        in ``get_stale_docs`` (``lastGeneratedAt + staleAfterHours < now``)
        evaluates to true and the documents appear in stale results.

        Args:
            entity_type: The entity type.
            entity_id: The entity identifier.

        Returns:
            Count of flagged documents.
        """
        # Use a very old date rather than None so that get_stale_docs
        # (which requires lastGeneratedAt != None) still includes these docs.
        epoch = datetime(2000, 1, 1, tzinfo=UTC)
        result = await self.docs.update_many(
            {
                "linkedEntities": {
                    "$elemMatch": {
                        "entityType": entity_type,
                        "entityId": entity_id,
                    }
                },
            },
            {"$set": {"lastGeneratedAt": epoch}},
        )

        count = result.modified_count if result else 0

        logger.info(
            "docs_flagged_stale",
            entity_type=entity_type,
            entity_id=entity_id,
            count=count,
        )

        return count

    async def refresh_documents_for_entity(
        self,
        entity_type: str,
        entity_id: str,
        *,
        user_id: str,
    ) -> dict[str, int]:
        """Flag and regenerate generated documents linked to an entity."""
        flagged = await self.flag_docs_stale_for_entity(entity_type, entity_id)

        cursor = self.docs.find(
            {
                "templateId": {"$ne": None},
                "linkedEntities": {
                    "$elemMatch": {
                        "entityType": entity_type,
                        "entityId": entity_id,
                    }
                },
            }
        )
        linked_docs = await cursor.to_list(length=250)

        regenerated = 0
        warning_count = 0
        errors = 0
        for doc in linked_docs:
            doc_id = doc.get("docId")
            if not doc_id:
                continue

            try:
                result = await self.regenerate_document(str(doc_id), user_id)
            except (DocNotFoundError, NotFoundError, ValidationError, ValueError) as exc:
                errors += 1
                logger.warning(
                    "document_refresh_failed",
                    doc_id=doc_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    error=str(exc),
                )
                continue

            regenerated += 1
            warning_count += int(result.get("warningCount", 0))

        logger.info(
            "documents_refreshed_for_entity",
            entity_type=entity_type,
            entity_id=entity_id,
            flagged=flagged,
            regenerated=regenerated,
            warnings=warning_count,
            errors=errors,
        )

        return {
            "flagged": flagged,
            "regenerated": regenerated,
            "warningCount": warning_count,
            "errors": errors,
        }

    async def refresh_documents_for_entities(
        self,
        entities: list[tuple[str, str]],
        *,
        user_id: str,
    ) -> dict[str, int]:
        """Refresh linked documents for a deduplicated list of entities."""
        seen: set[tuple[str, str]] = set()
        totals = {
            "flagged": 0,
            "regenerated": 0,
            "warningCount": 0,
            "errors": 0,
            "entityCount": 0,
        }

        for entity in entities:
            if entity in seen:
                continue
            seen.add(entity)
            entity_type, entity_id = entity
            result = await self.refresh_documents_for_entity(
                entity_type,
                entity_id,
                user_id=user_id,
            )
            totals["entityCount"] += 1
            totals["flagged"] += result.get("flagged", 0)
            totals["regenerated"] += result.get("regenerated", 0)
            totals["warningCount"] += result.get("warningCount", 0)
            totals["errors"] += result.get("errors", 0)

        return totals

    # ── Hybrid Authoring ───────────────────────────────────────────────

    async def edit_section(
        self,
        doc_id: str,
        section_id: str,
        request: EditSectionRequest,
        user_id: str,
    ) -> dict[str, Any]:
        """Edit an individual section within a document.

        If the section was previously generated, its source is changed to
        ``"manual-override"`` to indicate a user has overridden the generated
        content.  Manual sections remain ``"manual"``.

        Args:
            doc_id: The document identifier.
            section_id: The section identifier within the document.
            request: Edit payload with new content and optional title.
            user_id: The user performing the edit.

        Returns:
            The updated document.

        Raises:
            DocNotFoundError: If the document does not exist.
            NotFoundError: If the section does not exist in the document.
        """
        doc = await self.get_doc(doc_id)
        now = datetime.now(UTC)

        sections: list[dict[str, Any]] = doc.get("sections", [])
        target_section: dict[str, Any] | None = None
        for section in sections:
            if section.get("sectionId") == section_id:
                target_section = section
                break

        if target_section is None:
            raise NotFoundError("section", section_id)

        # Update content
        target_section["content"] = request.content
        if request.title is not None:
            target_section["title"] = request.title

        # Transition source: generated -> manual-override
        if target_section.get("source") == "generated":
            target_section["source"] = "manual-override"

        target_section["lastEditedAt"] = now
        target_section["editedBy"] = user_id

        # Recompose document content from all sections
        combined_content = self._compose_document_content(sections)
        new_version = doc["version"] + 1

        # Push version history entry
        await self.docs.update_one(
            {"docId": doc_id},
            {
                "$push": {
                    "versions": {
                        "version": new_version,
                        "content": combined_content,
                        "sections": sections,
                        "updatedAt": now,
                        "author": user_id,
                        "changeType": "section_edited",
                    }
                }
            },
        )

        # Update the document
        await self.docs.update_one(
            {"docId": doc_id},
            {
                "$set": {
                    "content": combined_content,
                    "sections": sections,
                    "version": new_version,
                    "updatedAt": now,
                }
            },
        )

        logger.info(
            "section_edited",
            doc_id=doc_id,
            section_id=section_id,
            new_source=target_section["source"],
            version=new_version,
        )

        return await self.get_doc(doc_id)

    async def revert_section(
        self,
        doc_id: str,
        section_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """Revert a manual-override section back to generated content.

        Re-renders the section from the document's template with current
        entity data, restoring it to ``source == "generated"``.

        Args:
            doc_id: The document identifier.
            section_id: The section identifier within the document.
            user_id: The user performing the revert.

        Returns:
            Dict with reverted section data (sectionId, source, content).

        Raises:
            DocNotFoundError: If the document does not exist.
            NotFoundError: If the section does not exist in the document.
            ValidationError: If the section cannot be reverted.
        """
        doc = await self.get_doc(doc_id)
        now = datetime.now(UTC)

        sections: list[dict[str, Any]] = doc.get("sections", [])
        target_section: dict[str, Any] | None = None
        for section in sections:
            if section.get("sectionId") == section_id:
                target_section = section
                break

        if target_section is None:
            raise NotFoundError("section", section_id)

        source = target_section.get("source", "manual")
        if source == "manual":
            raise ValidationError(
                "Cannot revert a purely manual section (no template to revert to)",
                details={"sectionId": section_id, "source": source},
            )
        if source == "generated":
            raise ValidationError(
                "Section is already generated, nothing to revert",
                details={"sectionId": section_id, "source": source},
            )

        # Load the template
        template_id = doc.get("templateId")
        if not template_id:
            raise ValidationError(
                "Cannot revert section: document has no associated template",
                details={"docId": doc_id},
            )

        template = await self.get_template(template_id)

        # Find the matching template section
        tmpl_section: dict[str, Any] | None = None
        for ts in template.get("sections", []):
            if ts["sectionId"] == section_id:
                tmpl_section = ts
                break

        if tmpl_section is None:
            raise ValidationError(
                "Section not found in the associated template",
                details={"sectionId": section_id, "templateId": template_id},
            )

        # Resolve entity data
        linked_entities = doc.get("linkedEntities", [])
        entity_data: dict[str, Any] = {}
        if linked_entities:
            first_entity = linked_entities[0]
            entity_data = await self._resolve_entity_data(
                first_entity["entityType"],
                first_entity["entityId"],
            )

        variables: dict[str, str] = {k: str(v) for k, v in entity_data.items()}
        fingerprint = _compute_fingerprint(variables)

        # Re-render the section
        tmpl = string.Template(tmpl_section["contentTemplate"])
        rendered_content = tmpl.safe_substitute(variables)

        # Update the section in-place
        target_section["content"] = rendered_content
        target_section["source"] = "generated"
        target_section["dataFingerprint"] = fingerprint
        target_section["lastGeneratedAt"] = now
        target_section["lastEditedAt"] = None
        target_section["editedBy"] = None

        # Recompose document content
        combined_content = self._compose_document_content(sections)
        new_version = doc["version"] + 1

        # Push version history entry
        await self.docs.update_one(
            {"docId": doc_id},
            {
                "$push": {
                    "versions": {
                        "version": new_version,
                        "content": combined_content,
                        "sections": sections,
                        "updatedAt": now,
                        "author": user_id,
                        "changeType": "section_reverted",
                    }
                }
            },
        )

        # Update the document
        await self.docs.update_one(
            {"docId": doc_id},
            {
                "$set": {
                    "content": combined_content,
                    "sections": sections,
                    "version": new_version,
                    "updatedAt": now,
                }
            },
        )

        logger.info(
            "section_reverted",
            doc_id=doc_id,
            section_id=section_id,
            version=new_version,
        )

        return {
            "sectionId": section_id,
            "source": "generated",
            "content": rendered_content,
        }
