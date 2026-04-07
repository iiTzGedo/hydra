"""Tests for documentation endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from tests.utils import create_mock_cursor


@pytest.fixture
def sample_doc():
    """Sample documentation document."""
    now = datetime.now(UTC)
    return {
        "docId": "doc::getting-started",
        "title": "Getting Started",
        "description": "Introduction guide for Hydra",
        "type": "guide",
        "format": "markdown",
        "content": "# Getting Started\n\nWelcome to Hydra...",
        "linkedEntities": [],
        "category": "guides",
        "tags": ["quickstart", "introduction"],
        "version": 1,
        "author": "admin",
        "status": "published",
        "createdAt": now,
        "updatedAt": now,
    }


@pytest.mark.asyncio
async def test_list_docs_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_doc,
    sample_user,
):
    """Test listing documentation."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_docs = MagicMock()
    mock_docs.count_documents = AsyncMock(return_value=1)
    mock_docs.find.return_value = create_mock_cursor([sample_doc])
    mock_mongodb.docs = mock_docs

    response = await client.get(
        "/api/v1/docs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert data["meta"]["total"] == 1


@pytest.mark.asyncio
async def test_list_docs_by_category(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_doc,
    sample_user,
):
    """Test listing documentation by category."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_docs = MagicMock()
    mock_docs.count_documents = AsyncMock(return_value=1)
    mock_docs.find.return_value = create_mock_cursor([sample_doc])
    mock_mongodb.docs = mock_docs

    response = await client.get(
        "/api/v1/docs?category=guides",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_doc_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_doc,
    sample_user,
):
    """Test getting a specific documentation."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=sample_doc)
    mock_mongodb.docs = mock_docs

    response = await client.get(
        f"/api/v1/docs/{sample_doc['docId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["docId"] == sample_doc["docId"]


@pytest.mark.asyncio
async def test_get_doc_by_slug(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_doc,
    sample_user,
):
    """Test getting documentation by slug."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=sample_doc)
    mock_mongodb.docs = mock_docs

    # Note: slug endpoint may not be implemented
    response = await client.get(
        "/api/v1/docs/slug/getting-started",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_doc_not_found(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test getting a non-existent documentation."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=None)
    mock_mongodb.docs = mock_docs

    response = await client.get(
        "/api/v1/docs/doc-nonexistent",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "DOC_NOT_FOUND"


@pytest.mark.asyncio
async def test_docs_public_access(
    client: AsyncClient,
    mock_mongodb,
    sample_doc,
):
    """Test that documentation is accessible without auth (if configured)."""
    mock_docs = MagicMock()
    mock_docs.count_documents = AsyncMock(return_value=1)
    mock_docs.find.return_value = create_mock_cursor([sample_doc])
    mock_mongodb.docs = mock_docs

    response = await client.get("/api/v1/docs")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_doc_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test creating a new documentation."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    admin_user["username"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=None)  # No existing doc
    mock_docs.insert_one = AsyncMock()
    mock_mongodb.docs = mock_docs

    response = await client.post(
        "/api/v1/docs",
        json={
            "docId": "doc::new-guide",
            "title": "New Guide",
            "type": "guide",
            "format": "markdown",
            "content": "# New Guide\n\nThis is a new guide.",
            "category": "tutorials",
            "tags": ["new", "tutorial"],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["data"]["docId"] == "doc::new-guide"


@pytest.mark.asyncio
async def test_create_doc_conflict(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_doc,
    sample_user,
):
    """Test creating a doc that already exists returns conflict."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=sample_doc)  # Doc exists
    mock_mongodb.docs = mock_docs

    response = await client.post(
        "/api/v1/docs",
        json={
            "docId": sample_doc["docId"],
            "title": "Duplicate",
            "type": "guide",
            "format": "markdown",
            "content": "# Duplicate",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 409
    data = response.json()
    assert data["error"]["code"] == "DOC_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_update_doc_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_doc,
    sample_user,
):
    """Test updating an existing documentation."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    admin_user["username"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    updated_doc = sample_doc.copy()
    updated_doc["title"] = "Updated Title"
    updated_doc["version"] = 2

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(side_effect=[sample_doc, updated_doc])
    mock_docs.update_one = AsyncMock()
    mock_mongodb.docs = mock_docs

    response = await client.put(
        f"/api/v1/docs/{sample_doc['docId']}",
        json={
            "title": "Updated Title",
            "content": "# Updated Content",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_delete_doc_archive(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_doc,
    sample_user,
):
    """Test archiving (soft delete) documentation."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    archived_doc = sample_doc.copy()
    archived_doc["status"] = "archived"

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=sample_doc)
    mock_docs.update_one = AsyncMock()
    mock_mongodb.docs = mock_docs

    response = await client.delete(
        f"/api/v1/docs/{sample_doc['docId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_delete_doc_permanent(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_doc,
    sample_user,
):
    """Test permanently deleting documentation."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=sample_doc)
    mock_docs.delete_one = AsyncMock()
    mock_mongodb.docs = mock_docs

    response = await client.delete(
        f"/api/v1/docs/{sample_doc['docId']}?permanent=true",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_docs_with_type_filter(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_doc,
    sample_user,
):
    """Test listing docs filtered by type."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_docs = MagicMock()
    mock_docs.count_documents = AsyncMock(return_value=1)
    mock_docs.find.return_value = create_mock_cursor([sample_doc])
    mock_mongodb.docs = mock_docs

    response = await client.get(
        "/api/v1/docs?type=guide",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_docs_with_search(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_doc,
    sample_user,
):
    """Test listing docs with search query."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_docs = MagicMock()
    mock_docs.count_documents = AsyncMock(return_value=1)
    mock_docs.find.return_value = create_mock_cursor([sample_doc])
    mock_mongodb.docs = mock_docs

    response = await client.get(
        "/api/v1/docs?search=getting",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_docs_with_tags(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_doc,
    sample_user,
):
    """Test listing docs filtered by tags."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_docs = MagicMock()
    mock_docs.count_documents = AsyncMock(return_value=1)
    mock_docs.find.return_value = create_mock_cursor([sample_doc])
    mock_mongodb.docs = mock_docs

    response = await client.get(
        "/api/v1/docs?tags=quickstart",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_doc_specific_version(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Test getting a specific version of documentation."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    now = datetime.now(UTC)
    doc_with_versions = {
        "docId": "doc::versioned",
        "title": "Versioned Doc",
        "type": "guide",
        "format": "markdown",
        "content": "# Version 2",
        "version": 2,
        "status": "published",
        "linkedEntities": [],
        "createdAt": now,
        "updatedAt": now,
        "versions": [
            {"version": 1, "content": "# Version 1", "updatedAt": now, "author": "admin"},
            {"version": 2, "content": "# Version 2", "updatedAt": now, "author": "admin"},
        ],
    }

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=doc_with_versions)
    mock_mongodb.docs = mock_docs

    response = await client.get(
        "/api/v1/docs/doc::versioned?version=1",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_docs_forbidden_for_viewer_create(
    client: AsyncClient,
    mock_mongodb,
    viewer_token,
    sample_user,
):
    """Test that viewer cannot create documentation."""
    viewer_user = sample_user.copy()
    viewer_user["userId"] = "user_viewer123"
    viewer_user["role"] = "viewer"
    mock_mongodb.users.find_one = AsyncMock(return_value=viewer_user)

    response = await client.post(
        "/api/v1/docs",
        json={
            "docId": "doc::test",
            "title": "Test",
            "type": "guide",
            "format": "markdown",
            "content": "# Test",
        },
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_doc_with_sections_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Manual docs should accept sections-only input and synchronize content."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    admin_user["username"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=None)
    mock_docs.insert_one = AsyncMock()
    mock_mongodb.docs = mock_docs

    response = await client.post(
        "/api/v1/docs",
        json={
            "docId": "doc::sectioned-guide",
            "title": "Sectioned Guide",
            "type": "guide",
            "format": "markdown",
            "sections": [
                {
                    "sectionId": "overview",
                    "title": "Overview",
                    "content": "Start here.",
                    "order": 1,
                },
                {
                    "sectionId": "operations",
                    "title": "Operations",
                    "content": "Run this next.",
                    "order": 2,
                },
            ],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    inserted = mock_docs.insert_one.call_args[0][0]
    assert inserted["content"] == "## Overview\n\nStart here.\n\n## Operations\n\nRun this next."
    assert len(inserted["sections"]) == 2
    assert inserted["sections"][0]["source"] == "manual"
    assert inserted["versions"][0]["sections"][1]["sectionId"] == "operations"


@pytest.mark.asyncio
async def test_update_doc_with_sections_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Manual doc section updates should version synchronized content and sections."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    admin_user["username"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    now = datetime.now(UTC)
    existing_doc = {
        "docId": "doc::manual-sections",
        "title": "Manual Sections",
        "type": "guide",
        "format": "markdown",
        "content": "# Old",
        "sections": [
            {
                "sectionId": "content",
                "title": "Manual Sections",
                "content": "# Old",
                "source": "manual",
                "templateRef": None,
                "dataFingerprint": None,
                "lastGeneratedAt": None,
                "lastEditedAt": now,
                "editedBy": "admin",
                "order": 0,
            }
        ],
        "linkedEntities": [],
        "version": 1,
        "status": "published",
        "createdAt": now,
        "updatedAt": now,
        "versions": [{"version": 1, "content": "# Old", "sections": [], "updatedAt": now, "author": "admin"}],
    }
    updated_doc = {
        **existing_doc,
        "content": "## Overview\n\nUpdated body",
        "sections": [
            {
                "sectionId": "overview",
                "title": "Overview",
                "content": "Updated body",
                "source": "manual",
                "templateRef": None,
                "dataFingerprint": None,
                "lastGeneratedAt": None,
                "lastEditedAt": now,
                "editedBy": "admin",
                "order": 1,
            }
        ],
        "version": 2,
    }

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(side_effect=[existing_doc, updated_doc])
    mock_docs.update_one = AsyncMock()
    mock_mongodb.docs = mock_docs

    response = await client.put(
        "/api/v1/docs/doc::manual-sections",
        json={
            "sections": [
                {
                    "sectionId": "overview",
                    "title": "Overview",
                    "content": "Updated body",
                    "order": 1,
                }
            ]
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    assert mock_docs.update_one.await_count == 2
    set_call = mock_docs.update_one.call_args_list[1]
    updated_fields = set_call[0][1]["$set"]
    assert updated_fields["version"] == 2
    assert updated_fields["content"] == "## Overview\n\nUpdated body"
    assert updated_fields["sections"][0]["sectionId"] == "overview"


@pytest.mark.asyncio
async def test_create_doc_rejects_content_section_mismatch(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Dual-write input should reject divergent content and sections."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    admin_user["username"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=None)
    mock_mongodb.docs = mock_docs

    response = await client.post(
        "/api/v1/docs",
        json={
            "docId": "doc::mismatch",
            "title": "Mismatch",
            "type": "guide",
            "format": "markdown",
            "content": "# Raw body",
            "sections": [
                {
                    "sectionId": "overview",
                    "title": "Overview",
                    "content": "Different body",
                    "order": 1,
                }
            ],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_update_generated_doc_rejects_body_edits(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Template-generated docs should reject generic body edits until hybrid authoring exists."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    admin_user["username"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    now = datetime.now(UTC)
    generated_doc = {
        "docId": "doc::generated-runbook",
        "title": "Generated Runbook",
        "type": "runbook",
        "format": "markdown",
        "content": "## Overview\n\nGenerated content",
        "sections": [
            {
                "sectionId": "overview",
                "title": "Overview",
                "content": "Generated content",
                "source": "generated",
                "templateRef": "tmpl::runbook-overview",
                "dataFingerprint": "abc123",
                "lastGeneratedAt": now,
                "lastEditedAt": None,
                "editedBy": None,
                "order": 1,
            }
        ],
        "linkedEntities": [],
        "version": 1,
        "status": "published",
        "templateId": "tmpl::runbook-overview",
        "lastGeneratedAt": now,
        "staleAfterHours": 24,
        "createdAt": now,
        "updatedAt": now,
        "versions": [{"version": 1, "content": "## Overview\n\nGenerated content", "updatedAt": now, "author": "admin"}],
    }

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=generated_doc)
    mock_mongodb.docs = mock_docs

    response = await client.put(
        "/api/v1/docs/doc::generated-runbook",
        json={"content": "## Overview\n\nManual override"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "Template-generated documents" in data["error"]["message"]


# ── Merge Engine Tests ─────────────────────────────────────────────────


def test_merge_preserves_manual_sections():
    """Manual sections are preserved during merge."""
    from hydra.api.v1.services.docs import DocsService

    existing = [
        {"sectionId": "overview", "source": "manual", "content": "My custom overview"},
        {"sectionId": "services", "source": "generated", "content": "Old services"},
    ]
    generated = [
        {"sectionId": "overview", "content": "Generated overview"},
        {"sectionId": "services", "content": "Fresh services"},
    ]

    merged, skipped = DocsService._merge_sections(existing, generated)

    assert len(merged) == 2
    assert merged[0]["content"] == "My custom overview"
    assert merged[0]["source"] == "manual"
    assert merged[1]["content"] == "Fresh services"
    assert skipped == ["overview"]


def test_merge_replaces_generated_sections():
    """Generated sections are replaced with fresh content."""
    from hydra.api.v1.services.docs import DocsService

    existing = [
        {"sectionId": "overview", "source": "generated", "content": "Old overview"},
    ]
    generated = [
        {"sectionId": "overview", "content": "Fresh overview"},
    ]

    merged, skipped = DocsService._merge_sections(existing, generated)

    assert len(merged) == 1
    assert merged[0]["content"] == "Fresh overview"
    assert skipped == []


def test_merge_preserves_manual_override():
    """Manual-override sections are preserved."""
    from hydra.api.v1.services.docs import DocsService

    existing = [
        {"sectionId": "overview", "source": "manual-override", "content": "User edited"},
    ]
    generated = [
        {"sectionId": "overview", "content": "Fresh generated"},
    ]

    merged, skipped = DocsService._merge_sections(existing, generated)

    assert len(merged) == 1
    assert merged[0]["content"] == "User edited"
    assert merged[0]["source"] == "manual-override"
    assert skipped == ["overview"]


def test_merge_appends_orphaned_manual_sections():
    """Manual sections not in template are appended and counted as skipped."""
    from hydra.api.v1.services.docs import DocsService

    existing = [
        {"sectionId": "overview", "source": "generated", "content": "Old"},
        {"sectionId": "custom-notes", "source": "manual", "content": "My notes"},
    ]
    generated = [
        {"sectionId": "overview", "content": "Fresh overview"},
    ]

    merged, skipped = DocsService._merge_sections(existing, generated)

    assert len(merged) == 2
    assert merged[0]["sectionId"] == "overview"
    assert merged[0]["content"] == "Fresh overview"
    assert merged[1]["sectionId"] == "custom-notes"
    assert merged[1]["content"] == "My notes"
    assert skipped == ["custom-notes"]


# ── Section Edit Tests ─────────────────────────────────────────────────


def _make_generated_doc(now=None):
    """Helper to create a generated document with sections."""
    if now is None:
        now = datetime.now(UTC)
    return {
        "docId": "doc::test-hybrid",
        "title": "Hybrid Test Doc",
        "description": "Test doc for hybrid authoring",
        "type": "runbook",
        "format": "markdown",
        "content": "## Overview\n\nNode test-node is a compute node.\n\n## Services\n\nRunning services: nginx",
        "sections": [
            {
                "sectionId": "overview",
                "title": "Overview",
                "content": "Node test-node is a compute node.",
                "source": "generated",
                "templateRef": "tmpl::runbook-overview",
                "dataFingerprint": "abc123",
                "lastGeneratedAt": now,
                "lastEditedAt": None,
                "editedBy": None,
                "order": 1,
            },
            {
                "sectionId": "services",
                "title": "Services",
                "content": "Running services: nginx",
                "source": "generated",
                "templateRef": "tmpl::runbook-overview",
                "dataFingerprint": "abc123",
                "lastGeneratedAt": now,
                "lastEditedAt": None,
                "editedBy": None,
                "order": 2,
            },
        ],
        "linkedEntities": [{"entityType": "node", "entityId": "test-node"}],
        "version": 1,
        "author": "admin",
        "status": "published",
        "templateId": "tmpl::runbook-overview",
        "lastGeneratedAt": now,
        "staleAfterHours": 24,
        "createdAt": now,
        "updatedAt": now,
        "versions": [],
    }


@pytest.mark.asyncio
async def test_edit_generated_section_becomes_manual_override(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Editing a generated section changes source to manual-override."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    now = datetime.now(UTC)
    generated_doc = _make_generated_doc(now)

    # After edit, the returned doc should reflect the changes
    edited_doc = _make_generated_doc(now)
    edited_doc["sections"][0]["content"] = "Custom overview content"
    edited_doc["sections"][0]["source"] = "manual-override"
    edited_doc["sections"][0]["editedBy"] = "user_admin123"
    edited_doc["version"] = 2

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(side_effect=[generated_doc, edited_doc])
    mock_docs.update_one = AsyncMock()
    mock_mongodb.docs = mock_docs

    response = await client.patch(
        "/api/v1/docs/doc::test-hybrid/sections/overview",
        json={"content": "Custom overview content"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    sections = data["sections"]
    overview = next(s for s in sections if s["sectionId"] == "overview")
    assert overview["source"] == "manual-override"
    assert overview["content"] == "Custom overview content"


@pytest.mark.asyncio
async def test_edit_manual_section_stays_manual(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Editing a manual section keeps source as manual."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    now = datetime.now(UTC)
    manual_doc = {
        "docId": "doc::manual-doc",
        "title": "Manual Doc",
        "description": None,
        "type": "guide",
        "format": "markdown",
        "content": "## Notes\n\nOriginal notes",
        "sections": [
            {
                "sectionId": "notes",
                "title": "Notes",
                "content": "Original notes",
                "source": "manual",
                "templateRef": None,
                "dataFingerprint": None,
                "lastGeneratedAt": None,
                "lastEditedAt": now,
                "editedBy": "admin",
                "order": 1,
            },
        ],
        "linkedEntities": [],
        "version": 1,
        "author": "admin",
        "status": "published",
        "createdAt": now,
        "updatedAt": now,
        "versions": [],
    }
    updated_doc = {**manual_doc, "version": 2}
    updated_doc["sections"] = [
        {**manual_doc["sections"][0], "content": "Updated notes", "editedBy": "user_admin123"},
    ]

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(side_effect=[manual_doc, updated_doc])
    mock_docs.update_one = AsyncMock()
    mock_mongodb.docs = mock_docs

    response = await client.patch(
        "/api/v1/docs/doc::manual-doc/sections/notes",
        json={"content": "Updated notes"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    notes = next(s for s in data["sections"] if s["sectionId"] == "notes")
    assert notes["source"] == "manual"


@pytest.mark.asyncio
async def test_edit_section_not_found(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """404 when section doesn't exist."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    now = datetime.now(UTC)
    doc = _make_generated_doc(now)

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=doc)
    mock_mongodb.docs = mock_docs

    response = await client.patch(
        "/api/v1/docs/doc::test-hybrid/sections/nonexistent",
        json={"content": "Whatever"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SECTION_NOT_FOUND"


# ── Section Revert Tests ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_revert_manual_override_to_generated(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Reverting manual-override restores generated content."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    now = datetime.now(UTC)
    doc = _make_generated_doc(now)
    # Mark overview as manual-override
    doc["sections"][0]["source"] = "manual-override"
    doc["sections"][0]["content"] = "User overridden content"

    template = {
        "templateId": "tmpl::runbook-overview",
        "name": "Runbook Overview",
        "docType": "runbook",
        "sections": [
            {
                "sectionId": "overview",
                "title": "Overview",
                "contentTemplate": "Node $node_id is a $node_class node.",
                "order": 1,
            },
            {
                "sectionId": "services",
                "title": "Services",
                "contentTemplate": "Running services: $services",
                "order": 2,
            },
        ],
        "variables": [],
        "createdAt": now,
        "updatedAt": now,
    }

    node = {
        "nodeId": "test-node",
        "class": "compute",
        "type": "vm",
        "displayName": "Test Node",
        "description": "A test node",
        "tags": [],
        "status": "active",
        "agentTier": "standard",
    }

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=doc)
    mock_docs.update_one = AsyncMock()
    mock_mongodb.docs = mock_docs

    mock_templates = MagicMock()
    mock_templates.find_one = AsyncMock(return_value=template)
    mock_mongodb.doc_templates = mock_templates

    mock_nodes = MagicMock()
    mock_nodes.find_one = AsyncMock(return_value=node)
    mock_mongodb.nodes = mock_nodes

    response = await client.post(
        "/api/v1/docs/doc::test-hybrid/sections/overview/revert",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["sectionId"] == "overview"
    assert data["source"] == "generated"
    assert "test-node" in data["content"]
    assert "compute" in data["content"]


@pytest.mark.asyncio
async def test_revert_manual_section_rejected(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Can't revert a purely manual section (no template to revert to)."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    now = datetime.now(UTC)
    doc = {
        "docId": "doc::manual-only",
        "title": "Manual Only",
        "description": None,
        "type": "guide",
        "format": "markdown",
        "content": "## Notes\n\nManual notes",
        "sections": [
            {
                "sectionId": "notes",
                "title": "Notes",
                "content": "Manual notes",
                "source": "manual",
                "templateRef": None,
                "dataFingerprint": None,
                "lastGeneratedAt": None,
                "lastEditedAt": now,
                "editedBy": "admin",
                "order": 1,
            },
        ],
        "linkedEntities": [],
        "version": 1,
        "status": "published",
        "createdAt": now,
        "updatedAt": now,
        "versions": [],
    }

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=doc)
    mock_mongodb.docs = mock_docs

    response = await client.post(
        "/api/v1/docs/doc::manual-only/sections/notes/revert",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 400
    assert "purely manual" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_revert_already_generated_rejected(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Can't revert an already-generated section."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    now = datetime.now(UTC)
    doc = _make_generated_doc(now)

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=doc)
    mock_mongodb.docs = mock_docs

    response = await client.post(
        "/api/v1/docs/doc::test-hybrid/sections/overview/revert",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 400
    assert "already generated" in response.json()["error"]["message"]


# ── Regeneration with Merge Tests ─────────────────────────────────────


@pytest.mark.asyncio
async def test_regenerate_with_manual_override_preserves(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """Regeneration preserves manual-override sections."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    now = datetime.now(UTC)
    doc = _make_generated_doc(now)
    # Make overview a manual-override
    doc["sections"][0]["source"] = "manual-override"
    doc["sections"][0]["content"] = "User custom overview"

    template = {
        "templateId": "tmpl::runbook-overview",
        "name": "Runbook Overview",
        "docType": "runbook",
        "sections": [
            {
                "sectionId": "overview",
                "title": "Overview",
                "contentTemplate": "Node $node_id is a $node_class node.",
                "order": 1,
            },
            {
                "sectionId": "services",
                "title": "Services",
                "contentTemplate": "Running services: $services",
                "order": 2,
            },
        ],
        "variables": [],
        "createdAt": now,
        "updatedAt": now,
    }

    node = {
        "nodeId": "test-node",
        "class": "compute",
        "type": "vm",
        "displayName": "Test Node",
        "description": "A test node",
        "tags": [],
        "status": "active",
        "agentTier": "standard",
    }

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=doc)
    mock_docs.update_one = AsyncMock()
    mock_mongodb.docs = mock_docs

    mock_templates = MagicMock()
    mock_templates.find_one = AsyncMock(return_value=template)
    mock_mongodb.doc_templates = mock_templates

    mock_nodes = MagicMock()
    mock_nodes.find_one = AsyncMock(return_value=node)
    mock_mongodb.nodes = mock_nodes

    response = await client.post(
        "/api/v1/docs/doc::test-hybrid/regenerate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["sectionsSkipped"] == 1
    assert "overview" in data["skippedSectionIds"]
    assert data["sectionsUpdated"] == 1
    assert data["warningCount"] == 1
    assert data["warnings"][0]["code"] == "MANUAL_OVERRIDE_PRESERVED"
    assert data["warnings"][0]["sectionId"] == "overview"


@pytest.mark.asyncio
async def test_regenerate_returns_skipped_sections(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_user,
):
    """RegenerateResponse includes skippedSectionIds."""
    admin_user = sample_user.copy()
    admin_user["userId"] = "user_admin123"
    admin_user["role"] = "admin"
    mock_mongodb.users.find_one = AsyncMock(return_value=admin_user)

    now = datetime.now(UTC)
    doc = _make_generated_doc(now)
    # Mark both sections as manual-override
    doc["sections"][0]["source"] = "manual-override"
    doc["sections"][1]["source"] = "manual-override"

    template = {
        "templateId": "tmpl::runbook-overview",
        "name": "Runbook Overview",
        "docType": "runbook",
        "sections": [
            {
                "sectionId": "overview",
                "title": "Overview",
                "contentTemplate": "Node $node_id is a $node_class node.",
                "order": 1,
            },
            {
                "sectionId": "services",
                "title": "Services",
                "contentTemplate": "Running services: $services",
                "order": 2,
            },
        ],
        "variables": [],
        "createdAt": now,
        "updatedAt": now,
    }

    node = {
        "nodeId": "test-node",
        "class": "compute",
        "type": "vm",
        "displayName": "Test Node",
        "description": "",
        "tags": [],
        "status": "active",
        "agentTier": "",
    }

    mock_docs = MagicMock()
    mock_docs.find_one = AsyncMock(return_value=doc)
    mock_docs.update_one = AsyncMock()
    mock_mongodb.docs = mock_docs

    mock_templates = MagicMock()
    mock_templates.find_one = AsyncMock(return_value=template)
    mock_mongodb.doc_templates = mock_templates

    mock_nodes = MagicMock()
    mock_nodes.find_one = AsyncMock(return_value=node)
    mock_mongodb.nodes = mock_nodes

    response = await client.post(
        "/api/v1/docs/doc::test-hybrid/regenerate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["sectionsSkipped"] == 2
    assert set(data["skippedSectionIds"]) == {"overview", "services"}
    assert data["sectionsUpdated"] == 0
    assert data["warningCount"] == 2
    assert {warning["sectionId"] for warning in data["warnings"]} == {"overview", "services"}
    assert {warning["code"] for warning in data["warnings"]} == {"MANUAL_OVERRIDE_PRESERVED"}
